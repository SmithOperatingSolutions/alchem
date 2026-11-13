package compiler

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// ReadSource reads one Alchem file, refusing anything larger than the parser
// accepts so an oversized or endless file is never held in memory.
// overlays holds text that stands in for files, by absolute path: an
// editor's unsaved buffers.
var overlays sync.Map

// SetOverlay makes text stand in for a file until ClearOverlay.
func SetOverlay(path string, text []byte) {
	if absolute, err := filepath.Abs(path); err == nil {
		overlays.Store(absolute, text)
	}
}

// ClearOverlay makes a file read from disk again.
func ClearOverlay(path string) {
	if absolute, err := filepath.Abs(path); err == nil {
		overlays.Delete(absolute)
	}
}

func ReadSource(path string) ([]byte, error) {
	if absolute, err := filepath.Abs(path); err == nil {
		if text, ok := overlays.Load(absolute); ok {
			return text.([]byte), nil
		}
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, syntax.MaxSourceBytes+1))
	if err != nil {
		return nil, err
	}
	if len(data) > syntax.MaxSourceBytes {
		return nil, fmt.Errorf("source exceeds %d bytes", syntax.MaxSourceBytes)
	}
	return data, nil
}

var remoteImport = regexp.MustCompile(`^([A-Za-z0-9_~-]+(?:[./][A-Za-z0-9_~-]+)*)@(v[0-9][0-9A-Za-z.+-]*)/([A-Za-z0-9_./-]+\.alc)$`)

// within reports whether path lies inside the directory root.
func within(root, path string) bool {
	relative, err := filepath.Rel(root, path)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator)) && !filepath.IsAbs(relative)
}

// fetchPackage downloads one version of a remote package through the Go
// module system, which verifies it against the checksum database, and returns
// the directory holding its files and the hash of its content.
func fetchPackage(ctx context.Context, moduleVersion string) (string, string, error) {
	goPath, err := goCommand(ctx)
	if err != nil {
		return "", "", err
	}
	cmd := exec.CommandContext(ctx, goPath, "mod", "download", "-json", moduleVersion)
	cmd.Dir = os.TempDir()
	cmd.Env = goEnvironment(goPath, append(os.Environ(), "GOWORK=off", "GO111MODULE=on"))
	cmd.WaitDelay = time.Second
	output, err := cmd.Output()
	var info struct{ Dir, Sum, Error string }
	_ = json.Unmarshal(output, &info)
	if ctx.Err() != nil {
		return "", "", ctx.Err()
	}
	if info.Error != "" {
		return "", "", errors.New(strings.TrimSpace(info.Error))
	}
	if err != nil || info.Dir == "" || info.Sum == "" {
		return "", "", fmt.Errorf("go mod download failed: %v", err)
	}
	return info.Dir, info.Sum, nil
}

// MaxModules bounds one import graph; with the per-file cap it also bounds
// the total source a build will hold.
const MaxModules = 1024

func reservedModule(name string) bool { return syntax.ReservedModule(name) }
func loadProject(entry string) (ast.Program, error) {
	return loadProjectContext(context.Background(), entry)
}
func loadProjectContext(ctx context.Context, entry string) (ast.Program, error) {
	return loadProjectAs(ctx, entry, false)
}

// loadProjectAs loads the program an entry file makes with what it imports.
// library allows the entry to have no main, for a file that is only checked.
func loadProjectAs(ctx context.Context, entry string, library bool) (ast.Program, error) {
	if info, err := os.Stat(entry); err == nil && info.IsDir() {
		entry = filepath.Join(entry, "main.alc")
	}
	entry, err := filepath.Abs(entry)
	if err != nil {
		return ast.Program{}, err
	}
	modules := map[string]*ast.Program{}
	names := map[string]string{}
	active := map[string]bool{}
	// roots maps a file fetched as part of a remote package to that package's
	// directory; targets records where each import of each file resolved to.
	roots := map[string]string{}
	targets := map[string]map[string]string{}
	versions := map[string]string{}
	fetched := map[string]string{}
	var remotes []ast.Remote
	var order []string
	var visit func(string) error
	visit = func(path string) error {
		if err := ctx.Err(); err != nil {
			return err
		}
		path, err = filepath.Abs(path)
		if err != nil {
			return err
		}
		if active[path] {
			return fmt.Errorf("%s: import cycle", path)
		}
		if modules[path] != nil {
			return nil
		}
		if filepath.Ext(path) != ".alc" {
			return fmt.Errorf("%s: source must have .alc extension", path)
		}
		if len(names) >= MaxModules {
			return fmt.Errorf("%s: project exceeds %d modules", path, MaxModules)
		}
		data, e := ReadSource(path)
		if e != nil {
			return fmt.Errorf("%s: read source: %w", path, e)
		}
		module, e := syntax.ParseModule(string(data))
		if e != nil {
			return syntaxDiagnostic(path, e)
		}
		if previous := names[module.Module]; previous != "" {
			return &Diagnostic{path, module.ModuleLine, module.ModuleColumn, fmt.Sprintf("duplicate module %s (also %s)", module.Module, previous)}
		}
		if reservedModule(module.Module) {
			return &Diagnostic{path, module.ModuleLine, module.ModuleColumn, "reserved module name " + module.Module}
		}
		names[module.Module] = path
		module.Source = path
		root := roots[path]
		for i := range module.Functions {
			if f := &module.Functions[i]; f.Extern != "" {
				if f.ExternDir, e = resolveExtern(f.Extern, path, f.Line, f.Column); e != nil {
					return e
				}
				if root != "" && f.ExternDir != "" && !within(root, f.ExternDir) {
					return &Diagnostic{path, f.Line, f.Column, "extern package leaves the package"}
				}
			}
		}
		for i := range module.Types {
			if decl := &module.Types[i]; decl.Kind == "extern" {
				if decl.ExternDir, e = resolveExtern(decl.Extern, path, decl.Line, decl.Column); e != nil {
					return e
				}
				if root != "" && decl.ExternDir != "" && !within(root, decl.ExternDir) {
					return &Diagnostic{path, decl.Line, decl.Column, "extern package leaves the package"}
				}
			}
		}
		targets[path] = map[string]string{}
		active[path] = true
		imports := append([]string{}, module.Imports...)
		sort.Strings(imports)
		for _, imp := range imports {
			position := ast.Position{Line: 1, Column: 1}
			for i, value := range module.Imports {
				if value == imp {
					position = module.ImportPositions[i]
					break
				}
			}
			if imp == "" || strings.ContainsAny(imp, "\x00\r\n") || filepath.IsAbs(imp) {
				return &Diagnostic{path, position.Line, position.Column, "imports must be nonempty relative .alc paths"}
			}
			target, targetRoot := filepath.Join(filepath.Dir(path), imp), root
			if strings.Contains(imp, "@") {
				parts := remoteImport.FindStringSubmatch(imp)
				if parts == nil || strings.Contains(parts[3], "..") || strings.Contains(parts[3], "//") {
					return &Diagnostic{path, position.Line, position.Column, `remote imports are written "module/path@v1.2.3/file.alc"`}
				}
				if previous, ok := versions[parts[1]]; ok && previous != parts[2] {
					return &Diagnostic{path, position.Line, position.Column, fmt.Sprintf("conflicting versions of %s: %s and %s", parts[1], previous, parts[2])}
				}
				versions[parts[1]] = parts[2]
				key := parts[1] + "@" + parts[2]
				if fetched[key] == "" {
					sum := ""
					if fetched[key], sum, e = fetchPackage(ctx, key); e != nil {
						return &Diagnostic{path, position.Line, position.Column, fmt.Sprintf("fetch %s: %v", key, e)}
					}
					remotes = append(remotes, ast.Remote{Path: parts[1], Version: parts[2], Sum: sum})
				}
				targetRoot = fetched[key]
				target = filepath.Join(targetRoot, filepath.FromSlash(parts[3]))
			} else if root != "" && !within(root, target) {
				return &Diagnostic{path, position.Line, position.Column, fmt.Sprintf("import %q leaves the package", imp)}
			}
			if target, e = filepath.Abs(target); e != nil {
				return e
			}
			if _, known := roots[target]; !known {
				roots[target] = targetRoot
			}
			targets[path][imp] = target
			if e = visit(target); e != nil {
				return wrapImport(path, position.Line, position.Column, imp, e)
			}
		}
		active[path] = false
		modules[path] = &module
		order = append(order, path)
		return nil
	}
	if err := visit(entry); err != nil {
		return ast.Program{}, err
	}
	// Macros are expanded once every module is known, since a module may
	// use the macros of the modules it imports.
	parsed := make([]*ast.Program, 0, len(order))
	for _, path := range order {
		if modules[path].Source == "" {
			modules[path].Source = path
		}
		parsed = append(parsed, modules[path])
	}
	if err := syntax.ExpandMacros(parsed); err != nil {
		if source, problem, located := syntax.MacroSource(err); located {
			return ast.Program{}, syntaxDiagnostic(source, problem)
		}
		return ast.Program{}, err
	}
	sort.Slice(remotes, func(i, j int) bool { return remotes[i].Path < remotes[j].Path })
	out := ast.Program{Source: entry, Module: modules[entry].Module, Remotes: remotes, GroupTags: modules[entry].GroupTags}
	private := map[string]bool{}
	for _, module := range modules {
		for _, f := range module.Functions {
			if f.Private {
				private[module.Module+"."+f.Name] = true
			}
		}
	}
	if err := documented(modules[entry], modules); err != nil {
		return out, err
	}
	// Protocols are known by their own names throughout the program.
	protocols := map[string]string{}
	for _, path := range order {
		for _, protocol := range modules[path].Protocols {
			if other, taken := protocols[protocol.Name]; taken {
				return out, &Diagnostic{path, protocol.Line, protocol.Column, fmt.Sprintf("protocol %s is also declared in %s", protocol.Name, other)}
			}
			protocols[protocol.Name] = path
			out.Protocols = append(out.Protocols, protocol)
		}
	}
	for _, path := range order {
		module := modules[path]
		for _, require := range module.Requires {
			require.Source = path
			for _, other := range out.Requires {
				if other.Path == require.Path && other.Version != require.Version {
					return out, &Diagnostic{path, require.Line, require.Column, fmt.Sprintf("conflicting versions of %s: %s here, %s in %s", require.Path, require.Version, other.Version, other.Source)}
				}
			}
			out.Requires = append(out.Requires, require)
		}
		for _, decl := range module.Types {
			decl.Source = path
			out.Types = append(out.Types, decl)
		}
		allowed := map[string]bool{module.Module: true}
		for _, imp := range module.Imports {
			allowed[modules[targets[path][imp]].Module] = true
		}
		locals := map[string]string{}
		for _, f := range module.Functions {
			key := module.Module + "." + f.Name
			if path == entry && f.Name == "main" {
				key = "main"
			}
			locals[f.Name] = key
		}
		for _, f := range module.Functions {
			if path != entry && f.Name == "main" {
				return out, fmt.Errorf("%s:%d:%d: imported modules cannot define main", path, f.Line, f.Column)
			}
			f.LocalName = f.Name
			f.Name = locals[f.Name]
			f.Module = module.Module
			if f.Source == "" {
				f.Source = path
			}
			var resolve func(*ast.Expr) error
			var block func([]ast.Statement) error
			resolve = func(e *ast.Expr) error {
				if e == nil {
					return nil
				}
				if e.Kind == "call" || e.Kind == "funcref" {
					if builtin, ok := strings.CutPrefix(e.Name, "Kernel."); ok && !strings.Contains(builtin, ".") {
						// Kernel.name is the builtin, whatever the module
						// defines under that name itself.
						e.Name = builtin
					} else if name := locals[e.Name]; name != "" {
						e.Name = name
					} else if index := strings.LastIndex(e.Name, "."); index >= 0 {
						// A name may be Module.function or Module.Type.variant.
						namespace, visible := e.Name[:index], false
						for name := range allowed {
							visible = visible || strings.HasPrefix(e.Name, name+".")
						}
						if !reservedModule(namespace) && !visible && protocols[namespace] == "" {
							return fmt.Errorf("%s:%d:%d: module %s is not imported", path, e.Line, e.Column, namespace)
						}
						if private[e.Name] {
							return fmt.Errorf("%s:%d:%d: %s is private to its module", path, e.Line, e.Column, e.Name)
						}
					}
				}
				if err := resolve(e.Left); err != nil {
					return err
				}
				if err := resolve(e.Right); err != nil {
					return err
				}
				for _, arg := range append(append([]*ast.Expr{}, e.Args...), e.Keys...) {
					if err := resolve(arg); err != nil {
						return err
					}
				}
				return block(e.Body)
			}
			block = func(body []ast.Statement) error {
				for _, s := range body {
					if err := resolve(s.Expr); err != nil {
						return err
					}
					if err := block(s.Then); err != nil {
						return err
					}
					if err := block(s.Else); err != nil {
						return err
					}
					for _, a := range s.Arms {
						if err := resolve(a.Guard); err != nil {
							return err
						}
						if err := block(a.Body); err != nil {
							return err
						}
					}
				}
				return nil
			}
			if err := block(f.Body); err != nil {
				return out, err
			}
			out.Functions = append(out.Functions, f)
		}
	}
	if err := syntax.ResolveArities(&out); err != nil {
		return out, err
	}
	out.Library = library
	if err := syntax.Analyze(&out); err != nil {
		return out, Describe(err)
	}
	return out, nil
}

// documented adds, for each "doctest Module" of a test file, one test per
// documented function of that module: the alx> examples in the comment above
// it, each compared with the result the comment shows.
func documented(entry *ast.Program, modules map[string]*ast.Program) error {
	for _, name := range entry.Doctests {
		var target *ast.Program
		path := ""
		for file, module := range modules {
			if module.Module == name {
				target, path = module, file
			}
		}
		if target == nil || target == entry {
			return &Diagnostic{entry.Source, 1, 1, "doctest " + name + ": no imported module has that name"}
		}
		for _, f := range target.Functions {
			examples := syntax.Examples(strings.Split(f.Doc, "\n"))
			if len(examples) == 0 {
				continue
			}
			source := ""
			for _, example := range examples {
				if example.Expected == "" {
					source += example.Source + "\n"
				} else {
					source += "assert((" + example.Source + ") == (" + example.Expected + "))\n"
				}
			}
			body, err := syntax.ParseSnippet(source)
			if err != nil {
				return &Diagnostic{path, f.Line, f.Column, fmt.Sprintf("the examples documenting %s do not parse: %v", f.Name, err)}
			}
			// Positions inside the examples are reported at the function.
			var place func([]ast.Statement)
			var placeExpr func(*ast.Expr)
			placeExpr = func(e *ast.Expr) {
				if e == nil {
					return
				}
				e.Line, e.Column = f.Line, f.Column
				placeExpr(e.Left)
				placeExpr(e.Right)
				for _, arg := range append(append([]*ast.Expr{}, e.Args...), e.Keys...) {
					placeExpr(arg)
				}
				place(e.Body)
			}
			place = func(list []ast.Statement) {
				for i := range list {
					list[i].Line, list[i].Column = f.Line, f.Column
					placeExpr(list[i].Expr)
					place(list[i].Then)
					place(list[i].Else)
					for _, arm := range list[i].Arms {
						placeExpr(arm.Guard)
						place(arm.Body)
					}
				}
			}
			place(body)
			entry.Functions = append(entry.Functions, ast.Function{
				Name: fmt.Sprintf("doctest$%d", len(entry.Functions)+1), Type: "void", Body: body,
				Test: fmt.Sprintf("doctest %s.%s/%d", name, f.Name, len(f.Params)), Source: path, Line: f.Line, Column: f.Column,
			})
		}
	}
	return nil
}
