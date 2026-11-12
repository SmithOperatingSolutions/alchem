package compiler

import (
	"bytes"
	"context"
	"fmt"
	"go/importer"
	"go/token"
	"go/types"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// externPackage is one Go package that extern declarations bind to. Local
// packages are copied into the generated module under ext/.
type externPackage struct {
	importPath, dir string
}

// externTargets lists every extern target of a program with the directory of
// its project-local package, if any: functions first, then types.
func externTargets(p ast.Program) (targets, dirs []string) {
	for _, f := range p.Functions {
		if f.Extern != "" {
			targets, dirs = append(targets, f.Extern), append(dirs, f.ExternDir)
		}
	}
	for _, decl := range p.Types {
		if decl.Kind == "extern" {
			targets, dirs = append(targets, strings.TrimPrefix(decl.Extern, "*")), append(dirs, decl.ExternDir)
		}
	}
	return targets, dirs
}

// externPackages lists the Go packages a program binds to in declaration
// order, keyed by import path or, for local packages, resolved directory.
func externPackages(p ast.Program) ([]externPackage, map[string]externPackage) {
	var ordered []externPackage
	byKey := map[string]externPackage{}
	targets, dirs := externTargets(p)
	for i, target := range targets {
		key, _, _ := syntax.ExternLocal(target)
		if dirs[i] != "" {
			key = dirs[i]
		}
		if _, ok := byKey[key]; ok {
			continue
		}
		pkg := externPackage{importPath: key}
		if dirs[i] != "" {
			pkg.dir = dirs[i]
			pkg.importPath = fmt.Sprintf("alchem.local/ext/p%d", len(ordered)+1)
		}
		ordered = append(ordered, pkg)
		byKey[key] = pkg
	}
	return ordered, byKey
}

// resolveExtern checks a project-local extern package and returns its directory.
func resolveExtern(target, file string, line, column int) (string, error) {
	pkg, _, local := syntax.ExternLocal(strings.TrimPrefix(target, "*"))
	if !local {
		return "", nil
	}
	dir := filepath.Join(filepath.Dir(file), filepath.FromSlash(pkg))
	sources, err := externSources(dir)
	if err != nil || len(sources) == 0 {
		return "", &Diagnostic{file, line, column, fmt.Sprintf("extern package %s has no Go files", pkg)}
	}
	return dir, nil
}

// externSources lists the Go files of a local package, without tests.
func externSources(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, entry := range entries {
		name := entry.Name()
		if entry.Type().IsRegular() && strings.HasSuffix(name, ".go") && !strings.HasSuffix(name, "_test.go") {
			names = append(names, name)
		}
	}
	return names, nil
}

// externPlan is the generated Go for a program's extern declarations.
type externPlan struct {
	imports   []string          // "alias \"import/path\""
	functions map[string]string // Alchem function name -> Go function
	types     map[string]string // extern type name -> Go type expression
}

// prepareModule writes the Go module a program is built in: go.mod with the
// required modules, the runtime, project-local Go packages, and a placeholder
// main package that imports every bound package so dependencies resolve.
//
// The locked checksums are written first, so Go refuses a required module
// whose content has changed since the lock was written.
func prepareModule(ctx context.Context, dir string, program ast.Program, environment []string, lock *lockFile) error {
	if len(lock.modules) > 0 {
		if err := os.WriteFile(filepath.Join(dir, "go.sum"), []byte(strings.Join(lock.modules, "\n")+"\n"), 0600); err != nil {
			return err
		}
	}
	module := "module alchem.local\n\ngo 1.27\n"
	required := map[string]bool{}
	for _, require := range program.Requires {
		if !required[require.Path] {
			required[require.Path] = true
			module += "\nrequire " + require.Path + " " + require.Version + "\n"
		}
	}
	if err := os.WriteFile(filepath.Join(dir, "go.mod"), []byte(module), 0600); err != nil {
		return err
	}
	if err := os.Mkdir(filepath.Join(dir, "actor"), 0700); err != nil {
		return err
	}
	// The runtime is copied into the build's own module. Packages built on
	// it, in subdirectories, import it by the path it has there.
	var copyRuntime func(string) error
	copyRuntime = func(folder string) error {
		entries, err := runtimeSources.ReadDir(folder)
		if err != nil {
			return err
		}
		for _, entry := range entries {
			name := folder + "/" + entry.Name()
			if entry.IsDir() {
				if err := os.Mkdir(filepath.Join(dir, filepath.FromSlash(name)), 0700); err != nil {
					return err
				}
				if err := copyRuntime(name); err != nil {
					return err
				}
				continue
			}
			data, err := runtimeSources.ReadFile(name)
			if err != nil {
				return err
			}
			data = bytes.ReplaceAll(data, []byte(`"github.com/SmithOperatingSolutions/alchem/compiler/actor"`), []byte(`"alchem.local/actor"`))
			if err = os.WriteFile(filepath.Join(dir, filepath.FromSlash(name)), data, 0600); err != nil {
				return err
			}
		}
		return nil
	}
	if err := copyRuntime("actor"); err != nil {
		return err
	}
	packages, _ := externPackages(program)
	placeholder := "package main\n\n"
	for _, pkg := range packages {
		placeholder += "import _ " + strconv.Quote(pkg.importPath) + "\n"
		if pkg.dir == "" {
			continue
		}
		target := filepath.Join(dir, filepath.FromSlash(strings.TrimPrefix(pkg.importPath, "alchem.local/")))
		if err := os.MkdirAll(target, 0700); err != nil {
			return err
		}
		sources, err := externSources(pkg.dir)
		if err != nil {
			return err
		}
		for _, name := range sources {
			data, err := os.ReadFile(filepath.Join(pkg.dir, name))
			if err != nil {
				return err
			}
			if err = os.WriteFile(filepath.Join(target, name), data, 0600); err != nil {
				return err
			}
		}
	}
	if err := os.WriteFile(filepath.Join(dir, "main.go"), []byte(placeholder+"\nfunc main() {}\n"), 0600); err != nil {
		return err
	}
	if len(program.Requires) == 0 {
		return nil
	}
	// Resolving dependencies records their checksums; programs without a
	// require never reach the network or the module cache.
	if result, err := goTool(ctx, dir, environment, "mod", "tidy"); err != nil {
		if ctx.Err() != nil {
			return fmt.Errorf("go mod tidy: %w", ctx.Err())
		}
		return fmt.Errorf("resolve required modules: %w: %s", err, result)
	}
	return nil
}

func goTool(ctx context.Context, dir string, environment []string, arguments ...string) ([]byte, error) {
	goPath, err := goCommand(ctx)
	if err != nil {
		return nil, err
	}
	cmd := exec.CommandContext(ctx, goPath, arguments...)
	cmd.Dir = dir
	cmd.Env = goEnvironment(goPath, environment)
	cmd.WaitDelay = time.Second
	return cmd.CombinedOutput()
}

// binder checks extern declarations against the Go declarations they name
// and generates the conversions between the two type systems.
type binder struct {
	program ast.Program
	loaded  map[string]*types.Package // by import path
	keyed   map[string]externPackage  // by extern package key
	aliases map[string]string         // import path -> alias
	plan    *externPlan
	opaque  map[string]types.Type // extern type name -> Go type
	decls   map[string]*ast.TypeDecl
	where   string // quoted source position of the declaration being bound
	next    int
}

func (b *binder) id() string { b.next++; return fmt.Sprintf("e%d", b.next) }

// qualify names a package in generated code, importing it on first use.
func (b *binder) qualify(pkg *types.Package) string {
	alias, ok := b.aliases[pkg.Path()]
	if !ok {
		alias = fmt.Sprintf("x%d", len(b.aliases)+1)
		b.aliases[pkg.Path()] = alias
		b.plan.imports = append(b.plan.imports, alias+" "+strconv.Quote(pkg.Path()))
	}
	return alias
}

// name writes a Go type as generated code can refer to it.
func (b *binder) name(t types.Type) (string, error) {
	var hidden string
	var walk func(types.Type, int)
	walk = func(t types.Type, depth int) {
		if depth > 16 {
			return
		}
		switch t := t.(type) {
		case *types.Named:
			if object := t.Obj(); object.Pkg() != nil && !object.Exported() {
				hidden = object.Pkg().Path() + "." + object.Name()
			}
		case *types.Pointer:
			walk(t.Elem(), depth+1)
		case *types.Slice:
			walk(t.Elem(), depth+1)
		case *types.Map:
			walk(t.Key(), depth+1)
			walk(t.Elem(), depth+1)
		}
	}
	walk(t, 0)
	if hidden != "" {
		return "", fmt.Errorf("Go type %s is not exported", hidden)
	}
	return types.TypeString(t, b.qualify), nil
}

// bindExterns loads the Go packages a program binds to from the prepared
// module and produces the Go code for every extern declaration. Each mismatch
// is reported at the declaration that caused it.
func bindExterns(ctx context.Context, dir string, program ast.Program, environment []string) (*externPlan, error) {
	plan := &externPlan{functions: map[string]string{}, types: map[string]string{}}
	packages, keyed := externPackages(program)
	if len(packages) == 0 {
		return plan, nil
	}
	arguments := []string{"list", "-export", "-deps", "-f", "{{if .Export}}{{.ImportPath}}={{.Export}}{{end}}"}
	for _, pkg := range packages {
		arguments = append(arguments, pkg.importPath)
	}
	output, err := goTool(ctx, dir, environment, arguments...)
	if err != nil {
		if ctx.Err() != nil {
			return nil, fmt.Errorf("load Go packages: %w", ctx.Err())
		}
		return nil, fmt.Errorf("load Go packages: %s", describeGoFailure(program, string(output)))
	}
	exports := map[string]string{}
	for _, line := range strings.Split(string(output), "\n") {
		if path, file, ok := strings.Cut(strings.TrimSpace(line), "="); ok {
			exports[path] = file
		}
	}
	source := importer.ForCompiler(token.NewFileSet(), "gc", func(path string) (io.ReadCloser, error) {
		file, ok := exports[path]
		if !ok {
			return nil, fmt.Errorf("no export data for %s", path)
		}
		return os.Open(file)
	})
	b := &binder{program: program, loaded: map[string]*types.Package{}, keyed: keyed, aliases: map[string]string{}, plan: plan, opaque: map[string]types.Type{}, decls: map[string]*ast.TypeDecl{}}
	for _, pkg := range packages {
		loaded, err := source.Import(pkg.importPath)
		if err != nil {
			return nil, fmt.Errorf("load Go package %s: %w", pkg.importPath, err)
		}
		b.loaded[pkg.importPath] = loaded
	}
	for i := range program.Types {
		decl := &program.Types[i]
		b.decls[decl.Name] = decl
		if decl.Kind != "extern" {
			continue
		}
		fail := func(format string, args ...any) error {
			return &Diagnostic{decl.Source, decl.Line, decl.Column, "extern type " + decl.Local + ": " + fmt.Sprintf(format, args...)}
		}
		pkg, symbol := b.target(strings.TrimPrefix(decl.Extern, "*"), decl.ExternDir)
		object, ok := pkg.Scope().Lookup(symbol).(*types.TypeName)
		if !ok {
			return nil, fail("Go package %s has no type %s", pkg.Path(), symbol)
		}
		if named, ok := object.Type().(*types.Named); ok && named.TypeParams().Len() > 0 {
			return nil, fail("generic Go types cannot be bound")
		}
		var bound types.Type = object.Type()
		if strings.HasPrefix(decl.Extern, "*") {
			bound = types.NewPointer(bound)
		}
		b.opaque[decl.Name] = bound
		text, err := b.name(bound)
		if err != nil {
			return nil, fail("%v", err)
		}
		plan.types[decl.Name] = text
	}
	for i, f := range program.Functions {
		if f.Extern == "" {
			continue
		}
		code, err := b.function(f, fmt.Sprintf("f%d", i))
		if err != nil {
			return nil, &Diagnostic{f.Source, f.Line, f.Column, "extern " + f.LocalName + ": " + err.Error()}
		}
		plan.functions[f.Name] = code
	}
	return plan, nil
}

// describeGoFailure replaces generated package paths in Go tool output with
// the directories the user wrote.
func describeGoFailure(p ast.Program, output string) string {
	packages, _ := externPackages(p)
	for _, pkg := range packages {
		if pkg.dir != "" {
			output = strings.ReplaceAll(output, pkg.importPath, pkg.dir)
			output = strings.ReplaceAll(output, strings.TrimPrefix(pkg.importPath, "alchem.local/"), pkg.dir)
		}
	}
	return strings.TrimSpace(output)
}

// target resolves an extern target to its loaded package and symbol.
func (b *binder) target(target, dir string) (*types.Package, string) {
	key, symbol, _ := syntax.ExternLocal(target)
	if dir != "" {
		key = dir
	}
	return b.loaded[b.keyed[key].importPath], symbol
}

func isError(t types.Type) bool {
	return types.Identical(t, types.Universe.Lookup("error").Type())
}
func isEmptyInterface(t types.Type) bool {
	i, ok := t.Underlying().(*types.Interface)
	return ok && i.NumMethods() == 0 && i.NumEmbeddeds() == 0
}
func basicKind(t types.Type, info types.BasicInfo) (*types.Basic, bool) {
	basic, ok := t.Underlying().(*types.Basic)
	return basic, ok && basic.Info()&info != 0
}

// natural is the Go type an Alchem value takes when Go asks for "any".
func natural(t string) (types.Type, bool) {
	switch t {
	case "integer":
		return types.Typ[types.Int64], true
	case "float":
		return types.Typ[types.Float64], true
	case "string":
		return types.Typ[types.String], true
	case "boolean":
		return types.Typ[types.Bool], true
	}
	if elem, ok := ast.ListElement(t); ok {
		if inner, ok := natural(elem); ok {
			return types.NewSlice(inner), true
		}
	}
	if key, value, ok := ast.MapParts(t); ok {
		k, okKey := natural(key)
		v, okValue := natural(value)
		if okKey && okValue {
			return types.NewMap(k, v), true
		}
	}
	return nil, false
}

// structFields pairs the fields of an Alchem struct type with the fields of a
// Go struct: names match ignoring case and underscores.
func (b *binder) structFields(t string, target *types.Struct) ([]string, []*types.Var, error) {
	head, args := ast.Split(t)
	decl := b.decls[head]
	if decl == nil || decl.Kind != "struct" || len(args) != len(decl.Params) {
		return nil, nil, fmt.Errorf("%s is not a struct", t)
	}
	bindings := map[string]string{}
	for i, param := range decl.Params {
		bindings[param] = args[i]
	}
	fold := func(name string) string { return strings.ToLower(strings.ReplaceAll(name, "_", "")) }
	var fieldTypes []string
	var matched []*types.Var
	for _, field := range decl.Fields {
		var found *types.Var
		for i := 0; i < target.NumFields(); i++ {
			if candidate := target.Field(i); candidate.Exported() && !candidate.Embedded() && fold(candidate.Name()) == fold(field.Name) {
				found = candidate
			}
		}
		if found == nil {
			return nil, nil, fmt.Errorf("the Go struct has no exported field for %s.%s", decl.Local, field.Name)
		}
		fieldTypes = append(fieldTypes, ast.Substitute(field.Type, bindings))
		matched = append(matched, found)
	}
	return fieldTypes, matched, nil
}

// show writes a Go type for a message, with packages by name.
func show(t types.Type) string {
	return types.TypeString(t, func(pkg *types.Package) string { return pkg.Name() })
}

func mismatch(direction, alchem string, target types.Type) error {
	if direction == "to" {
		return fmt.Errorf("cannot pass %s as Go %s", alchem, show(target))
	}
	return fmt.Errorf("cannot receive Go %s as %s", show(target), alchem)
}

// toGo converts the Alchem expression value of type t to the Go type target.
func (b *binder) toGo(t string, target types.Type, value string) (string, error) {
	if declared, ok := b.opaque[t]; ok {
		if types.AssignableTo(declared, target) {
			return value, nil
		}
		return "", mismatch("to", t, target)
	}
	if isEmptyInterface(target) {
		plain, ok := natural(t)
		if !ok {
			return "", mismatch("to", t, target)
		}
		return b.toGo(t, plain, value)
	}
	name, err := b.name(target)
	if err != nil {
		return "", err
	}
	convert := "(" + name + ")(" + value + ")"
	switch under := target.Underlying().(type) {
	case *types.Basic:
		switch {
		case t == "integer" && under.Info()&types.IsInteger != 0:
			if under.Kind() == types.Int64 {
				return convert, nil
			}
			return "toInt[" + name + "](ctx," + value + "," + b.where + ")", nil
		case t == "float" && under.Info()&types.IsFloat != 0, t == "boolean" && under.Info()&types.IsBoolean != 0, t == "string" && under.Info()&types.IsString != 0:
			return convert, nil
		}
	case *types.Slice:
		if _, bytes := basicKind(under.Elem(), types.IsInteger); bytes && t == "string" && under.Elem().Underlying().(*types.Basic).Kind() == types.Uint8 {
			return convert, nil
		}
		if elem, ok := ast.ListElement(t); ok {
			xs, out, i, x := b.id(), b.id(), b.id(), b.id()
			inner, err := b.toGo(elem, under.Elem(), x)
			if err != nil {
				return "", err
			}
			return "func() " + name + " {" + xs + " := fwd(" + value + ");" + out + " := make(" + name + ",len(" + xs + "));for " + i + "," + x + " := range " + xs + " {" + out + "[" + i + "] = " + inner + "};return " + out + "}()", nil
		}
	case *types.Map:
		if key, val, ok := ast.MapParts(t); ok {
			out, k, v := b.id(), b.id(), b.id()
			innerKey, err := b.toGo(key, under.Key(), k)
			if err != nil {
				return "", err
			}
			innerValue, err := b.toGo(val, under.Elem(), v)
			if err != nil {
				return "", err
			}
			return "func() " + name + " {" + out + " := make(" + name + ");actor.MapEach(" + value + ",func(" + k + " " + goType(key) + "," + v + " " + goType(val) + "){" + out + "[" + innerKey + "] = " + innerValue + "});return " + out + "}()", nil
		}
	case *types.Struct:
		return b.structToGo(t, under, name, value, false)
	case *types.Pointer:
		if inner, ok := under.Elem().Underlying().(*types.Struct); ok {
			elem, err := b.name(under.Elem())
			if err != nil {
				return "", err
			}
			return b.structToGo(t, inner, elem, value, true)
		}
	case *types.Signature:
		return b.callbackToGo(t, under, name, value)
	}
	return "", mismatch("to", t, target)
}

func (b *binder) structToGo(t string, target *types.Struct, name, value string, pointer bool) (string, error) {
	fieldTypes, fields, err := b.structFields(t, target)
	if err != nil {
		return "", err
	}
	s := b.id()
	parts := []string{}
	for i, field := range fields {
		inner, err := b.toGo(fieldTypes[i], field.Type(), fmt.Sprintf("%s.F%d", s, i))
		if err != nil {
			return "", fmt.Errorf("field %s: %w", field.Name(), err)
		}
		parts = append(parts, field.Name()+":"+inner)
	}
	result, address := name, ""
	if pointer {
		result, address = "*"+name, "&"
	}
	return "func() " + result + " {" + s + " := " + value + ";_ = " + s + ";return " + address + name + "{" + strings.Join(parts, ",") + "}}()", nil
}

// callbackToGo wraps an Alchem function value as a Go function. The Go side
// must call it on the calling goroutine, before the extern call returns.
func (b *binder) callbackToGo(t string, target *types.Signature, name, value string) (string, error) {
	params, result, ok := ast.FunctionParts(t)
	if !ok || target.Variadic() || target.Params().Len() != len(params) || target.Results().Len() > 1 {
		return "", mismatch("to", t, target)
	}
	f := b.id()
	declared, arguments := []string{}, []string{"ctx"}
	for i, param := range params {
		id := b.id()
		paramType, err := b.name(target.Params().At(i).Type())
		if err != nil {
			return "", err
		}
		declared = append(declared, id+" "+paramType)
		inner, err := b.fromGo(param, target.Params().At(i).Type(), id)
		if err != nil {
			return "", fmt.Errorf("callback parameter %d: %w", i+1, err)
		}
		arguments = append(arguments, inner)
	}
	call := f + "(" + strings.Join(arguments, ",") + ")"
	body, returns := "_ = "+call, ""
	if target.Results().Len() == 1 {
		resultType, err := b.name(target.Results().At(0).Type())
		if err != nil {
			return "", err
		}
		out := b.id()
		inner, err := b.toGo(result, target.Results().At(0).Type(), out)
		if err != nil {
			return "", fmt.Errorf("callback result: %w", err)
		}
		body, returns = out+" := "+call+";return "+inner, " "+resultType
	}
	return "func() " + name + " {" + f + " := " + value + ";return func(" + strings.Join(declared, ",") + ")" + returns + " {" + body + "}}()", nil
}

// fromGo converts the Go expression value of type source to the Alchem type t.
func (b *binder) fromGo(t string, source types.Type, value string) (string, error) {
	if declared, ok := b.opaque[t]; ok {
		if types.AssignableTo(source, declared) {
			return "(" + goType(t) + ")(" + value + ")", nil
		}
		return "", mismatch("from", t, source)
	}
	switch under := source.Underlying().(type) {
	case *types.Basic:
		switch {
		case t == "integer" && under.Info()&types.IsInteger != 0:
			if under.Kind() == types.Int64 {
				return "int64(" + value + ")", nil
			}
			return "fromInt(ctx," + value + "," + b.where + ")", nil
		case t == "float" && under.Info()&types.IsFloat != 0:
			return "float64(" + value + ")", nil
		case t == "boolean" && under.Info()&types.IsBoolean != 0:
			return "bool(" + value + ")", nil
		case t == "string" && under.Info()&types.IsString != 0:
			return "string(" + value + ")", nil
		}
	case *types.Slice:
		if basic, ok := under.Elem().Underlying().(*types.Basic); ok && basic.Kind() == types.Uint8 && t == "string" {
			return "string(" + value + ")", nil
		}
		if elem, ok := ast.ListElement(t); ok {
			xs, out, i, x := b.id(), b.id(), b.id(), b.id()
			inner, err := b.fromGo(elem, under.Elem(), x)
			if err != nil {
				return "", err
			}
			return "func() " + goType(t) + " {" + xs + " := " + value + ";" + out + " := make([]" + goType(elem) + ",len(" + xs + "));for " + i + "," + x + " := range " + xs + " {" + out + "[" + i + "] = " + inner + "};return mk(" + out + ")}()", nil
		}
	case *types.Map:
		if key, val, ok := ast.MapParts(t); ok {
			out, k, v := b.id(), b.id(), b.id()
			innerKey, err := b.fromGo(key, under.Key(), k)
			if err != nil {
				return "", err
			}
			innerValue, err := b.fromGo(val, under.Elem(), v)
			if err != nil {
				return "", err
			}
			return "func() " + goType(t) + " {var " + out + " " + goType(t) + ";for " + k + "," + v + " := range " + value + " {" + out + " = actor.MapPut(" + out + "," + innerKey + "," + innerValue + ")};return " + out + "}()", nil
		}
	case *types.Struct:
		return b.structFromGo(t, under, source, value, false)
	case *types.Pointer:
		if inner, ok := under.Elem().Underlying().(*types.Struct); ok {
			return b.structFromGo(t, inner, source, value, true)
		}
	case *types.Signature:
		return b.callbackFromGo(t, under, value)
	}
	return "", mismatch("from", t, source)
}

func (b *binder) structFromGo(t string, shape *types.Struct, source types.Type, value string, pointer bool) (string, error) {
	fieldTypes, fields, err := b.structFields(t, shape)
	if err != nil {
		return "", err
	}
	s := b.id()
	parts := []string{}
	for i, field := range fields {
		inner, err := b.fromGo(fieldTypes[i], field.Type(), s+"."+field.Name())
		if err != nil {
			return "", fmt.Errorf("field %s: %w", field.Name(), err)
		}
		parts = append(parts, inner)
	}
	guard := ""
	if pointer {
		guard = "if " + s + " == nil {failAt(ctx," + b.where + "," + strconv.Quote("Go returned a nil "+show(source)) + ")};"
	}
	return "func() " + goType(t) + " {" + s + " := " + value + ";" + guard + "return " + goType(t) + "{" + strings.Join(parts, ",") + "}}()", nil
}

// callbackFromGo wraps a Go function value as an Alchem function value.
func (b *binder) callbackFromGo(t string, source *types.Signature, value string) (string, error) {
	params, result, ok := ast.FunctionParts(t)
	if !ok || source.Variadic() || source.Params().Len() != len(params) || source.Results().Len() != 1 {
		return "", mismatch("from", t, source)
	}
	f := b.id()
	declared, arguments := []string{"ctx *actor.Context"}, []string{}
	for i, param := range params {
		id := b.id()
		declared = append(declared, id+" "+goType(param))
		inner, err := b.toGo(param, source.Params().At(i).Type(), id)
		if err != nil {
			return "", err
		}
		arguments = append(arguments, inner)
	}
	out := b.id()
	inner, err := b.fromGo(result, source.Results().At(0).Type(), out)
	if err != nil {
		return "", err
	}
	return "func() " + goType(t) + " {" + f + " := " + value + ";return func(" + strings.Join(declared, ",") + ") " + goType(result) + " {" + out + " := " + f + "(" + strings.Join(arguments, ",") + ");return " + inner + "}}()", nil
}

// function generates the Alchem-callable Go function for one extern.
func (b *binder) function(f ast.Function, name string) (string, error) {
	b.where = strconv.Quote(fmt.Sprintf("%s:%d:%d", f.Source, f.Line, f.Column))
	pkg, symbol := b.target(f.Extern, f.ExternDir)
	typeName, method, isMethod := strings.Cut(symbol, ".")
	var signature *types.Signature
	var receiver types.Type
	callee := ""
	if isMethod {
		object, ok := pkg.Scope().Lookup(typeName).(*types.TypeName)
		if !ok {
			return "", fmt.Errorf("Go package %s has no type %s", pkg.Path(), typeName)
		}
		receiver = object.Type()
		selection := types.NewMethodSet(types.NewPointer(receiver)).Lookup(pkg, method)
		if _, isInterface := receiver.Underlying().(*types.Interface); isInterface {
			selection = types.NewMethodSet(receiver).Lookup(pkg, method)
		}
		if selection == nil {
			return "", fmt.Errorf("Go type %s.%s has no method %s", pkg.Path(), typeName, method)
		}
		signature = selection.Type().(*types.Signature)
		// Methods with pointer receivers need the pointer; others take either.
		if types.NewMethodSet(receiver).Lookup(pkg, method) == nil {
			receiver = types.NewPointer(receiver)
		}
	} else {
		object, ok := pkg.Scope().Lookup(symbol).(*types.Func)
		if !ok {
			return "", fmt.Errorf("Go package %s has no function %s", pkg.Path(), symbol)
		}
		signature = object.Type().(*types.Signature)
		callee = b.qualify(pkg) + "." + symbol
	}
	if signature.TypeParams().Len() > 0 {
		return "", fmt.Errorf("generic Go functions cannot be bound; wrap %s in a local Go package", f.Extern)
	}
	header, values := []string{"ctx *actor.Context"}, []string{}
	for _, param := range f.Params {
		id := b.id()
		header = append(header, id+" "+goType(param.Type))
		values = append(values, id)
	}
	params := f.Params
	if isMethod {
		if len(params) == 0 {
			return "", fmt.Errorf("a method needs its receiver as the first parameter")
		}
		target := receiver
		// A pointer handle can call value-receiver methods too.
		if declared, ok := b.opaque[params[0].Type]; ok && types.Identical(declared, types.NewPointer(receiver)) {
			target = declared
		}
		self, err := b.toGo(params[0].Type, target, values[0])
		if err != nil {
			return "", fmt.Errorf("receiver: %w", err)
		}
		callee = "(" + self + ")." + method
		params, values = params[1:], values[1:]
	}
	if signature.Params().Len() != len(params) {
		return "", fmt.Errorf("Go %s takes %d parameters, the declaration has %d", f.Extern, signature.Params().Len(), len(params))
	}
	arguments := []string{}
	for i, param := range params {
		target := signature.Params().At(i).Type()
		argument, err := b.toGo(param.Type, target, values[i])
		if err != nil {
			return "", fmt.Errorf("parameter %s: %w", param.Name, err)
		}
		if signature.Variadic() && i == len(params)-1 {
			argument += "..."
		}
		arguments = append(arguments, argument)
	}
	call := callee + "(" + strings.Join(arguments, ",") + ")"
	body, err := b.results(f, signature.Results(), call)
	if err != nil {
		return "", err
	}
	returns := ""
	if f.Type != "void" {
		returns = " " + goType(f.Type)
	}
	return fmt.Sprintf("//line %s:%d\nfunc %s(%s)%s {%s}\n", f.Source, f.Line, name, strings.Join(header, ","), returns, body), nil
}

// results generates the body that calls Go and converts what it returns.
func (b *binder) results(f ast.Function, results *types.Tuple, call string) (string, error) {
	count := results.Len()
	names := make([]string, count)
	for i := range names {
		names[i] = b.id()
	}
	assign := ""
	if count > 0 {
		assign = strings.Join(names, ",") + " := " + call + ";"
	}
	// values converts the first n results to an Alchem type: none is the
	// empty tuple, one is the value itself, several are a tuple.
	values := func(t string, n int) (string, error) {
		parts, isTuple := ast.TupleElements(t)
		if n == 1 {
			return b.fromGo(t, results.At(0).Type(), names[0])
		}
		if !isTuple || len(parts) != n {
			return "", fmt.Errorf("Go returns %d values here, which need a tuple of %d, not %s", n, n, t)
		}
		converted := []string{}
		for i := 0; i < n; i++ {
			inner, err := b.fromGo(parts[i], results.At(i).Type(), names[i])
			if err != nil {
				return "", fmt.Errorf("result %d: %w", i+1, err)
			}
			converted = append(converted, inner)
		}
		return goType(t) + "{" + strings.Join(converted, ",") + "}", nil
	}
	head, args := ast.Split(f.Type)
	last := count - 1
	switch {
	case f.Type == "void":
		if count != 0 {
			hint := ""
			if count == 1 && isError(results.At(0).Type()) {
				hint = "; declare the result as result[tuple[],string]"
			}
			return "", fmt.Errorf("Go %s returns %s, the declaration returns nothing%s", f.Extern, show(results), hint)
		}
		return call, nil
	case head == "result" && count > 0 && isError(results.At(last).Type()):
		if args[1] != "string" {
			return "", fmt.Errorf("a Go error becomes result[T,string], not %s", f.Type)
		}
		inner, err := values(args[0], last)
		if err != nil {
			return "", err
		}
		return assign + "if " + names[last] + "!=nil{return errOf[" + goType(args[0]) + "](" + names[last] + ".Error())};return okOf[" + goType(args[0]) + "](" + inner + ")", nil
	case head == "option" && count >= 2:
		if _, ok := basicKind(results.At(last).Type(), types.IsBoolean); !ok {
			break
		}
		inner, err := values(args[0], last)
		if err != nil {
			return "", err
		}
		return assign + "if !" + names[last] + "{return noneOf[" + goType(args[0]) + "]()};return someOf[" + goType(args[0]) + "](" + inner + ")", nil
	case head == "option" && count == 1:
		// A Go pointer result: nil is none.
		if _, ok := results.At(0).Type().Underlying().(*types.Pointer); !ok {
			break
		}
		inner, err := b.fromGo(args[0], results.At(0).Type(), names[0])
		if err != nil {
			return "", err
		}
		return assign + "if " + names[0] + "==nil{return noneOf[" + goType(args[0]) + "]()};return someOf[" + goType(args[0]) + "](" + inner + ")", nil
	}
	if count == 0 {
		return "", fmt.Errorf("Go %s returns nothing, the declaration returns %s", f.Extern, f.Type)
	}
	inner, err := values(f.Type, count)
	if err != nil {
		return "", err
	}
	return assign + "return " + inner, nil
}

const externRuntime = `
type xint interface{~int|~int8|~int16|~int32|~int64|~uint|~uint8|~uint16|~uint32|~uint64|~uintptr}
// Integers crossing into Go must fit the Go parameter, and Go results must fit
// a signed 64-bit integer; anything else fails instead of wrapping.
func toInt[T xint](ctx *actor.Context,v int64,where string)T{r:=T(v);if int64(r)!=v||(r<0)!=(v<0){failAt(ctx,where,fmt.Sprintf("integer out of range for Go %T",r))};return r}
func fromInt[T xint](ctx *actor.Context,v T,where string)int64{r:=int64(v);if T(r)!=v||(r<0)!=(v<0){failAt(ctx,where,fmt.Sprintf("Go %T result out of integer range",v))};return r}
`
