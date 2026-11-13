package compiler

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// Names from source are mapped to generated identifiers; only validated AST
// values/operators reach Go source. Go evaluates call arguments left to right.
type generator struct {
	next      int
	functions map[string]string
	// defs are the program's functions by name, for looking into the one a
	// reduce is given.
	defs   map[string]*ast.Function
	source string
	// statementChecks is set only for the entry body. Functions and closures
	// check for cancellation once on entry, in actor.Enter.
	statementChecks bool
	// leaf is set while generating a function or closure that calls no other
	// function; see leafBody.
	leaf bool
	// tail describes the function being generated when a call to itself in
	// return position may become a jump back to its start; see tailCall. It
	// is nil inside anything generated as a Go function of its own.
	tail *tailTarget
	// testing is set for a test file: assertions then report the values they
	// compared. entry is that file, and points collects the statements
	// counted for coverage, which leaves the test file itself out.
	testing, cover bool
	// inTest is set while generating a test, a setup block or a documented
	// example, none of which count towards coverage.
	inTest bool
	entry  string
	points []string
	// patterns are the regular expressions of ~r sigils, compiled once as
	// package variables.
	patterns []string
	// fixed are the texts of ~h templates, each made once as a package
	// variable.
	fixed []string
	// decls are the program's struct and sum types by name. codecs numbers
	// those that cross to another node, in the order their functions are
	// generated.
	decls       map[string]ast.TypeDecl
	codecs      map[string]int
	codecOrder  []string
	readers     map[string]int
	readerOrder []string
}

func (g *generator) id() string { g.next++; return fmt.Sprintf("v%d", g.next) }
func generate(p ast.Program) string {
	return generateWithOptions(p, BuildOptions{ShutdownTimeout: 2000000000})
}
func generateWithOptions(p ast.Program, options BuildOptions) string {
	return generateProgram(p, options, &externPlan{})
}

// generateProgram emits the Go program. plan carries the code produced for
// extern declarations by binding them against their Go packages.
func generateProgram(p ast.Program, options BuildOptions, plan *externPlan) string {
	g := generator{functions: map[string]string{}, source: p.Source, entry: p.Source, decls: map[string]ast.TypeDecl{}}
	for _, decl := range append(syntax.BuiltinTypes(), p.Types...) {
		g.decls[decl.Name] = decl
	}
	for _, f := range p.Functions {
		g.testing = g.testing || f.Test != ""
	}
	g.cover = g.testing && options.Cover
	if g.source == "" {
		g.source = "<source>"
	}
	g.defs = map[string]*ast.Function{}
	for i, f := range p.Functions {
		g.functions[f.Name] = fmt.Sprintf("f%d", i)
		g.defs[f.Name] = &p.Functions[i]
	}
	g.functions["main"] = "main"
	var out strings.Builder
	out.WriteString("package main\nimport (\"bufio\";\"fmt\";\"io\";\"iter\";\"math\";\"os\";/*dynamic*/\"slices\";\"sort\";\"strconv\";\"strings\";\"sync\";\"sync/atomic\";\"time\";\"unicode/utf8\";\"alchem.local/actor\"")
	for _, imported := range plan.imports {
		out.WriteString(";" + imported)
	}
	out.WriteString(")\n")
	out.WriteString("var _ = slices.Equal[[]int64]\n")
	out.WriteString("var _ = fmt.Println\nvar _ = math.Floor\nvar _ iter.Seq[int64]\n")
	out.WriteString(arithmeticRuntime)
	out.WriteString(externRuntime)
	for _, adapter := range plan.adapters {
		out.WriteString(adapter)
	}
	for _, decl := range append(syntax.BuiltinTypes(), p.Types...) {
		if decl.Kind == "extern" {
			out.WriteString("type " + mangle(decl.Name) + " = " + plan.types[decl.Name] + "\n")
			continue
		}
		out.WriteString(typeDeclaration(decl))
	}
	for _, f := range p.Functions {
		if f.Source != "" {
			g.source = f.Source
		}
		if f.Extern != "" {
			out.WriteString("\n" + plan.functions[f.Name])
			continue
		}
		// Function headers and the entry wrapper are generated code: without
		// this reset they inherit the previous body's Alchem position and show
		// up as bogus source frames.
		out.WriteString("\n//line alchem_generated.go:1\n")
		scope := map[string]string{}
		params := []string{"ctx *actor.Context"}
		var locals, slots []string
		for _, param := range f.Params {
			id := g.id()
			scope[param.Name] = id
			params = append(params, id+" "+goType(param.Type))
			locals = append(locals, id)
		}
		for _, variable := range f.Reads {
			params = append(params, readerName(variable)+" "+readerType(variable))
		}
		g.statementChecks = f.Name == "main"
		g.leaf = f.Name != "main" && leafBody(f.Body)
		g.inTest = f.Test != "" || f.Setup
		if f.Name == "main" {
			out.WriteString("func main(){os.Exit(actor.Run(func(ctx *actor.Context){\n" + g.block(f.Body, scope) + "}," + g.runtime(p, options) + "))}\n")
			continue
		}
		// A function that may call itself in return position is generated
		// once with that in mind; only if it does is the loop written.
		var target *tailTarget
		if f.Test == "" && !f.Setup && len(f.Params) > 0 && len(syntax.Generic(&f)) == 0 {
			for range f.Params {
				slots = append(slots, g.id())
			}
			target = &tailTarget{name: f.Name, slots: slots, label: "tail" + g.id()}
		}
		g.tail = target
		body := g.block(f.Body, scope)
		g.tail = nil
		looped := target != nil && target.used
		if looped {
			// The parameters live in slots a tail call assigns; each turn of
			// the loop copies them to variables of its own, so a closure
			// made in one turn keeps that turn's values.
			params = []string{"ctx *actor.Context"}
			for i, param := range f.Params {
				params = append(params, slots[i]+" "+goType(param.Type))
			}
		}
		out.WriteString("func " + g.functions[f.Name] + typeParameters(syntax.Generic(&f)) + "(" + strings.Join(params, ",") + ")")
		if f.Type != "void" {
			out.WriteString(" " + goType(f.Type))
		}
		out.WriteString("{\n")
		if !g.leaf {
			out.WriteString(g.enter(f.Line, f.Column))
		}
		if looped {
			out.WriteString(target.label + ":\nfor {\n" + strings.Join(locals, ",") + " := " + strings.Join(slots, ",") + "\n")
			for _, local := range locals {
				out.WriteString("_ = " + local + "\n")
			}
			out.WriteString(body)
			if f.Type == "void" {
				out.WriteString("return\n")
			}
			out.WriteString("}\n")
		} else {
			out.WriteString(body)
		}
		out.WriteString("}\n")
	}
	if g.testing {
		out.WriteString(g.testMain(p, options))
	}
	for i, source := range g.patterns {
		out.WriteString(fmt.Sprintf("var pattern%d = regexp.MustCompile(%s)\n", i, strconv.Quote(source)))
	}
	for i, pieces := range g.fixed {
		out.WriteString(fmt.Sprintf("var fixed%d = %s\n", i, pieces))
	}
	out.WriteString(g.codecFunctions())
	out.WriteString(g.readerFunctions())
	usesNodes := strings.Contains(out.String(), "node.Codec[")
	generated := out.String()
	if strings.Contains(generated, "regexp.") {
		generated = strings.Replace(generated, "/*dynamic*/", "\"regexp\";/*dynamic*/", 1)
	}
	// The node package, with its networking and encryption, is imported
	// only by programs whose messages cross to other nodes.
	if usesNodes {
		generated = strings.Replace(generated, "/*dynamic*/", "\"alchem.local/actor/node\";/*dynamic*/", 1)
	}
	// Reflection is linked only into programs that compare values of a type
	// known at run time, or inspect values.
	equality := strings.Contains(generated, "equal(x,y)")
	// The receive assertions show the messages they compared.
	// The runtime that writes values is needed by the program's own code,
	// or by the library sections it uses.
	library := selectLibrary(generated)
	inspection := strings.Contains(generated, "inspectValue(") || strings.Contains(generated, "ioInspect(") || strings.Contains(generated, "assertReceive") || strings.Contains(generated, "refuteReceive(") ||
		strings.Contains(library, "inspectValue(") || strings.Contains(library, "inspectOf(") || strings.Contains(library, "inspectLess(") || strings.Contains(library, "typeNames[")
	if !equality && !inspection {
		return strings.Replace(generated, "/*dynamic*/", "", 1)
	}
	generated = strings.Replace(generated, "/*dynamic*/", "\"reflect\";", 1)
	if equality {
		generated += dynamicEquality
	}
	if inspection {
		generated += inspectRuntime + typeNames(p)
	}
	return generated
}

// runtime renders the arguments every entry point passes to actor.Run after
// its body: the names of the generated functions, for failure frames, and the
// tracing, shutdown and call-depth settings.
func (g *generator) runtime(p ast.Program, options BuildOptions) string {
	names := []string{}
	for _, other := range p.Functions {
		name := other.Name
		if other.Module != "" {
			name = other.Module + "." + other.LocalName
		}
		if other.Test != "" {
			name = "test " + other.Test
		}
		if other.Setup {
			name = "setup"
		}
		key := "main." + g.functions[other.Name]
		if other.Name == "main" {
			key = "main.main.func1"
		}
		names = append(names, strconv.Quote(key)+":"+strconv.Quote(name))
	}
	return "map[string]string{" + strings.Join(names, ",") + "}," + strconv.FormatBool(!options.NoTrace) + "," + strconv.FormatInt(options.ShutdownTimeout.Milliseconds(), 10) + "," + strconv.Itoa(options.MaxCallDepth)
}

// testMain is the entry point of a test file: it hands the entry module's
// tests to the runner, each preceded by the setup blocks that apply to it.
func (g *generator) testMain(p ast.Program, options BuildOptions) string {
	entry := func(f ast.Function) bool { return f.Module == p.Module || f.Module == "" }
	provides := func(f ast.Function) bool { return f.Type != "void" && f.Type != "tuple[]" }
	// call runs a setup block or test, passing the context if it takes one.
	call := func(f ast.Function, context string) string {
		if len(f.Params) == 1 {
			return g.functions[f.Name] + "(ctx," + context + ")"
		}
		return g.functions[f.Name] + "(ctx)"
	}
	// setup_all runs once, before any test, in the runner's own process.
	once, shared := "", ""
	for _, f := range p.Functions {
		if f.Setup && f.All && entry(f) {
			if provides(f) {
				shared = g.id()
				once += shared + " := " + call(f, shared) + ";_ = " + shared + ";"
			} else {
				once += call(f, shared) + ";"
			}
		}
	}
	var cases []string
	for _, f := range p.Functions {
		if f.Test == "" || !entry(f) {
			continue
		}
		// Setup blocks of every enclosing describe run first, outermost
		// first; one that ends in a value replaces the context.
		calls, context := "", shared
		for depth := 0; depth <= len(ast.Groups(f.Group)); depth++ {
			for _, setup := range p.Functions {
				if !setup.Setup || setup.All || !entry(setup) || len(ast.Groups(setup.Group)) != depth || !ast.Within(f.Group, setup.Group) {
					continue
				}
				if provides(setup) {
					next := g.id()
					calls += next + " := " + call(setup, context) + ";_ = " + next + ";"
					context = next
				} else {
					calls += call(setup, context) + ";"
				}
			}
		}
		tags := append([]string{}, p.GroupTags[""]...)
		path := ""
		for _, name := range ast.Groups(f.Group) {
			if path != "" {
				path += ast.GroupSeparator
			}
			path += name
			tags = append(tags, p.GroupTags[path]...)
		}
		quoted := []string{}
		for _, tag := range append(tags, f.Tags...) {
			quoted = append(quoted, strconv.Quote(tag))
		}
		name := strings.Join(append(ast.Groups(f.Group), f.Test), " ")
		cases = append(cases, "{"+strconv.Quote(name)+","+strconv.Quote(fmt.Sprintf("%s:%d", f.Source, f.Line))+",[]string{"+strings.Join(quoted, ",")+"},func(ctx *actor.Context){"+calls+call(f, context)+"}}")
	}
	return "\n//line alchem_generated.go:1\nvar coverPoints = []coverPoint{" + strings.Join(g.points, ",") + "}\nvar coverCounts = make([]atomic.Uint32, len(coverPoints))\n" +
		"func main(){code:=actor.Run(func(ctx *actor.Context){" + once + "testExit=runTests(ctx," + strconv.Quote(p.Module) + ",[]testCase{" + strings.Join(cases, ",") + "})}," + g.runtime(p, options) + ");if code==0{code=testExit};writeCoverage();os.Exit(code)}\n"
}

// assertion generates an assert for a test file. A failed comparison reports
// the expression and both operands as inspect would print them.
func (g *generator) assertion(s ast.Statement, scope map[string]string) string {
	e := s.Expr
	message := strconv.Quote("assertion failed")
	if code := sourceOf(e); code != "" {
		message = strconv.Quote("assertion failed\n     code:  " + code)
	}
	where := g.location(s.Line, s.Column)
	switch {
	case e.Kind == "binary" && map[string]bool{"==": true, "!=": true, "<": true, "<=": true, ">": true, ">=": true}[e.Op]:
		l, r := g.id(), g.id()
		return l + "," + r + " := " + g.expr(e.Left, scope) + "," + g.expr(e.Right, scope) + ";if !(" + g.binary(e, l, r) + ") {failAt(ctx," + where + "," + message + "+\"\\n     left:  \"+inspectValue(" + l + ")+\"\\n     right: \"+inspectValue(" + r + "))}\n"
	}
	return "if !(" + g.expr(e, scope) + ") {failAt(ctx," + where + "," + message + ")}\n"
}

// sourceOf renders an analyzed expression back to source for a message, or
// "" when it contains a form analysis has rewritten.
func sourceOf(e *ast.Expr) (text string) {
	defer func() {
		if recover() != nil {
			text = ""
		}
	}()
	text = formatExpr(e, 0)
	if strings.HasPrefix(text, "(") && strings.HasSuffix(text, ")") {
		text = text[1 : len(text)-1]
	}
	if strings.Contains(text, "\n") {
		return ""
	}
	return text
}

// typeNames emits the table that lets inspect print declared types the way
// source writes them: the generated Go type name to the Alchem name and its
// field names.
func typeNames(p ast.Program) string {
	var out strings.Builder
	out.WriteString("var typeNames = map[string]typeName{\n")
	entry := func(key, name string, fields []ast.Parameter, record bool) {
		labels := []string{}
		for _, field := range fields {
			labels = append(labels, strconv.Quote(field.Name))
		}
		out.WriteString(fmt.Sprintf("%s: {%s, []string{%s}, %t},\n", strconv.Quote(key), strconv.Quote(name), strings.Join(labels, ","), record))
	}
	for _, decl := range append(syntax.BuiltinTypes(), p.Types...) {
		switch decl.Kind {
		case "struct":
			entry(mangle(decl.Name), decl.Local, decl.Fields, true)
		case "sum":
			for i, variant := range decl.Variants {
				name := decl.Local + "." + variant.Name
				if decl.Name == decl.Local {
					name = syntax.Constructor(decl, variant.Name)
				}
				entry(fmt.Sprintf("%s_c%d", mangle(decl.Name), i), name, variant.Fields, false)
			}
		}
	}
	out.WriteString("}\n")
	return out.String()
}

// inspectRuntime renders any value as Alchem source would write it.
const inspectRuntime = `
type typeName struct{name string;fields []string;record bool}
func ioInspect[A any](x A)A{fmt.Println(inspectValue(x));return x}
func inspectValue(x any)string{return inspectOf(reflect.ValueOf(x))}
// shownFields counts the fields of a struct that are part of its value:
// Markup's last field, P, is bookkeeping.
func shownFields(v reflect.Value)int{n:=v.NumField();if n>0&&v.Type().Field(n-1).Name=="P"{return n-1};return n}
func inspectAll(values []reflect.Value)string{parts:=make([]string,len(values));for i,v:=range values{parts[i]=inspectOf(v)};return strings.Join(parts,", ")}
func inspectOf(v reflect.Value)string{
	if !v.IsValid(){return "nil"}
	switch v.Kind(){
	case reflect.Int64:return strconv.FormatInt(v.Int(),10)
	case reflect.Float64:return floatInspect(v.Float())
	case reflect.String:if v.Type().Name()=="Atom"{return ":"+v.String()};return strconv.Quote(v.String())
	case reflect.Bool:return strconv.FormatBool(v.Bool())
	case reflect.Interface:if v.IsNil(){return "nil"};return inspectOf(v.Elem())
	case reflect.Func:return "#Function<>"
	case reflect.Pointer:name,_,_:=strings.Cut(v.Type().Elem().Name(),"[");return "#"+name+"<>"
	case reflect.Struct:
		name,_,_:=strings.Cut(v.Type().Name(),"[")
		fields:=make([]reflect.Value,shownFields(v))
		for i:=range fields{fields[i]=v.Field(i)}
		if pairs,ok:=v.Interface().(interface{Pairs()[][2]any});ok{
			entries:=pairs.Pairs()
			sort.Slice(entries,func(i,j int)bool{return inspectLess(entries[i][0],entries[j][0])})
			parts:=make([]string,len(entries))
			set:=strings.HasSuffix(v.Type().Name(),",struct {}]")
			for i,entry:=range entries{parts[i]=inspectValue(entry[0]);if !set{parts[i]+=" => "+inspectValue(entry[1])}}
			if set{return "MapSet.new(["+strings.Join(parts,", ")+"])"}
			return "%{"+strings.Join(parts,", ")+"}"
		}
		if name=="L"{
			items:=make([]reflect.Value,fields[0].Len())
			for i:=range items{items[i]=fields[0].Index(len(items)-1-i)}
			// A list of {atom, value} pairs is written as a keyword list.
			if element:=fields[0].Type().Elem();len(items)>0&&element.Kind()==reflect.Struct&&element.Name()==""&&element.NumField()==2&&element.Field(0).Type.Name()=="Atom"{
				parts:=make([]string,len(items))
				for i,item:=range items{parts[i]=item.Field(0).String()+": "+inspectOf(item.Field(1))}
				return "["+strings.Join(parts,", ")+"]"
			}
			return "["+inspectAll(items)+"]"
		}
		info,known:=typeNames[name]
		if !known{return "{"+inspectAll(fields)+"}"}
		if text,ok:=inspectCalendar(info.name,fields);ok{return text}
		if !info.record{if len(fields)==0{return info.name};return info.name+"("+inspectAll(fields)+")"}
		parts:=make([]string,len(fields))
		for i,field:=range fields{parts[i]=info.fields[i]+": "+inspectOf(field)}
		return "%"+info.name+"{"+strings.Join(parts,", ")+"}"
	}
	return "#"+v.Type().String()
}
// inspectCalendar writes dates and times as their sigils, as Elixir does.
func inspectCalendar(name string,fields []reflect.Value)(string,bool){
	n:=func(i int)int64{return fields[i].Int()}
	clock:=func(h,m,sec,micro int64)string{t:=fmt.Sprintf("%02d:%02d:%02d",h,m,sec);if micro!=0{t+=fmt.Sprintf(".%06d",micro)};return t}
	switch name{
	case "Range":if n(2)==1||n(2)==-1&&n(0)>n(1){return fmt.Sprintf("%d..%d",n(0),n(1)),true};return fmt.Sprintf("%d..%d//%d",n(0),n(1),n(2)),true
	case "Date":return fmt.Sprintf("~D[%04d-%02d-%02d]",n(0),n(1),n(2)),true
	case "Time":return "~T["+clock(n(0),n(1),n(2),n(3))+"]",true
	case "NaiveDateTime":return fmt.Sprintf("~N[%04d-%02d-%02d %s]",n(0),n(1),n(2),clock(n(3),n(4),n(5),n(6))),true
	case "DateTime":
		zone:=fields[7].String()
		day:=fmt.Sprintf("%04d-%02d-%02d %s",n(0),n(1),n(2),clock(n(3),n(4),n(5),n(6)))
		if zone=="Etc/UTC"{return "~U["+strings.Replace(day," ","T",1)+"Z]",true}
		offset:=n(8);sign:="+";if offset<0{sign,offset="-",-offset}
		return fmt.Sprintf("#DateTime<%s%s%02d:%02d %s>",day,sign,offset/3600,offset%3600/60,zone),true
	}
	return "",false
}
func inspectLess(a,b any)bool{
	switch x:=a.(type){
	case int64:return x<b.(int64)
	case float64:return x<b.(float64)
	case string:return x<b.(string)
	case actor.Atom:return x<b.(actor.Atom)
	case bool:return !x&&b.(bool)
	}
	// Tuples order element by element.
	va,vb:=reflect.ValueOf(a),reflect.ValueOf(b)
	if va.Kind()==reflect.Struct&&vb.Kind()==reflect.Struct{
		for i:=0;i<shownFields(va)&&i<shownFields(vb);i++{
			x,y:=va.Field(i).Interface(),vb.Field(i).Interface()
			if inspectLess(x,y){return true}
			if inspectLess(y,x){return false}
		}
	}
	return false
}
`

// mangle turns a qualified type name into a Go identifier; "_" is doubled so
// the "." replacement and the variant suffix cannot collide with a name.
func mangle(name string) string {
	return "T" + strings.NewReplacer("_", "__", ".", "_o").Replace(name)
}

// typeParameters declares Go type parameters for Alchem type variables.
func typeParameters(vars []string) string {
	if len(vars) == 0 {
		return ""
	}
	parts := []string{}
	for _, v := range vars {
		parts = append(parts, "T_"+v+" any")
	}
	return "[" + strings.Join(parts, ",") + "]"
}

// typeArguments renders Alchem types as a Go type argument list.
func typeArguments(args []string) string {
	if len(args) == 0 {
		return ""
	}
	parts := []string{}
	for _, arg := range args {
		parts = append(parts, goType(arg))
	}
	return "[" + strings.Join(parts, ",") + "]"
}

// variantType names the Go struct of one variant of a sum type value.
func variantType(t string, index int) string {
	head, args := ast.Split(t)
	return fmt.Sprintf("%s_c%d%s", mangle(head), index, typeArguments(args))
}

// typeDeclaration emits a struct as a Go struct, and a sum type as an
// interface implemented by one Go struct per variant.
func typeDeclaration(decl ast.TypeDecl) string {
	name, params := mangle(decl.Name), typeParameters(decl.Params)
	uses := ""
	if len(decl.Params) > 0 {
		names := []string{}
		for _, p := range decl.Params {
			names = append(names, "T_"+p)
		}
		uses = "[" + strings.Join(names, ",") + "]"
	}
	fields := func(list []ast.Parameter) string {
		parts := []string{}
		for i, field := range list {
			parts = append(parts, fmt.Sprintf("F%d %s", i, goType(field.Type)))
		}
		return "struct{" + strings.Join(parts, ";") + "}"
	}
	if decl.Name == "Markup" {
		// Markup also carries, out of the program's sight, how a template
		// or a join made it; see markupParts. P is no part of its value:
		// comparing, printing and encoding go by the declared fields.
		return "type TMarkup struct{F0 string;P *markupShape}\ntype markupShape struct{template string;fixed L[string];values L[TMarkup];joined bool}\n"
	}
	if decl.Kind == "struct" {
		return "type " + name + params + " " + fields(decl.Fields) + "\n"
	}
	out := "type " + name + params + " interface{is" + name + "()}\n"
	for i, variant := range decl.Variants {
		out += fmt.Sprintf("type %s_c%d%s %s\nfunc (%s_c%d%s) is%s(){}\n", name, i, params, fields(variant.Fields), name, i, uses, name)
	}
	return out
}
func goType(t string) string {
	if ast.TypeVariable(t) {
		return "T_" + t
	}
	if head, args, ok := ast.Named(t); ok {
		return mangle(head) + typeArguments(args)
	}
	switch head, args := ast.Split(t); head {
	case "server":
		return "*actor.Server" + typeArguments(args)
	case "task":
		return "*actor.Task" + typeArguments(args)
	case "registry":
		return "*actor.Registry" + typeArguments(args)
	case "generator":
		return "*generator" + typeArguments(args)
	case "dynamic_supervisor":
		return "*actor.DynamicSupervisor"
	case "agent":
		return "*actor.Agent" + typeArguments(args)
	case "stream":
		return "iter.Seq" + typeArguments(args)
	case "set":
		return "actor.Map[" + goType(args[0]) + ",struct{}]"
	case "regex":
		return "*regexp.Regexp"
	case "port":
		return "*portHandle"
	case "socket":
		return "*socketHandle"
	case "http_server":
		return "*httpServer"
	case "websocket":
		return "*wsConn"
	case "file":
		return "*fileHandle"
	case "disk_store":
		return "*storeHandle"
	}
	for _, kind := range []string{"pid", "supervisor"} {
		if elem, ok := ast.CapabilityElement(t, kind); ok {
			goName := "PID"
			if kind == "supervisor" {
				goName = "Supervisor"
			}
			return "*actor." + goName + "[" + goType(elem) + "]"
		}
	}
	if key, value, ok := ast.MapParts(t); ok {
		return "actor.Map[" + goType(key) + "," + goType(value) + "]"
	}
	if params, result, ok := ast.FunctionParts(t); ok {
		parts := []string{"*actor.Context"}
		for _, p := range params {
			parts = append(parts, goType(p))
		}
		return "func(" + strings.Join(parts, ",") + ") " + goType(result)
	}
	if elem, ok := ast.ListElement(t); ok {
		return "L[" + goType(elem) + "]"
	}
	if parts, ok := ast.TupleElements(t); ok {
		var fields []string
		for i, part := range parts {
			fields = append(fields, fmt.Sprintf("E%d %s", i, goType(part)))
		}
		return "struct{" + strings.Join(fields, ";") + "}"
	}
	switch t {
	case "integer":
		return "int64"
	case "float":
		return "float64"
	case "boolean":
		return "bool"
	case "atom":
		return "actor.Atom"
	default:
		return "string"
	}
}
func (g *generator) block(body []ast.Statement, scope map[string]string) string {
	var out strings.Builder
	for _, s := range body {
		// A //line directive names the line that follows it, so it is repeated
		// before every generated line that can fail or call; otherwise runtime
		// frames drift below the Alchem statement that produced them.
		mark := g.mark(s.Line)
		if g.statementChecks {
			out.WriteString(mark + "actor.Check(ctx)")
		}
		if g.cover && g.source != g.entry && !g.inTest {
			out.WriteString(mark + fmt.Sprintf("cover(%d)", len(g.points)))
			g.points = append(g.points, fmt.Sprintf("{%s,%d}", strconv.Quote(g.source), s.Line))
		}
		out.WriteString(mark)
		// Expressions that are Go functions of their own cannot jump to the
		// start of this one.
		tail := g.tail
		g.tail = nil
		if jump, ok := g.tailCall(tail, s, scope); ok {
			g.tail = tail
			out.WriteString(jump)
			continue
		}
		expr := g.expr(s.Expr, scope)
		g.tail = tail
		switch s.Kind {
		case "bind":
			subject := g.id()
			out.WriteString(subject + " := " + expr + "; _ = " + subject + "\n")
			cond, binds := g.pattern(s.Pattern, subject, scope)
			out.WriteString(strings.TrimPrefix(mark, "\n") + "if !(" + cond + ") {failAt(ctx," + g.location(s.Line, s.Column) + ",\"pattern match failed\")}\n" + binds)

		case "output":
			out.WriteString("fmt.Println(" + expr + ")\n")
		case "assert":
			if g.testing {
				out.WriteString(g.assertion(s, scope))
				break
			}
			out.WriteString("if !(" + expr + ") {failAt(ctx," + g.location(s.Line, s.Column) + ",\"assertion failed\")}\n")
		case "call":
			if s.Expr.Type == "void" {
				out.WriteString(expr + "\n")
			} else {
				out.WriteString("_ = " + expr + "\n")
			}
		case "yield":
			out.WriteString("return " + expr + "\n")
		case "return":
			if g.leaf {
				out.WriteString("return " + expr + "\n")
			} else {
				out.WriteString("return actor.Leave(ctx," + expr + ")\n")
			}
		case "case":
			subject := g.id()
			out.WriteString(subject + " := " + expr + "; _ = " + subject + "\n")
			for i, arm := range s.Arms {
				branch := copyNames(scope)
				cond, binds := g.pattern(arm.Pattern, subject, branch)
				if arm.Guard != nil {
					guardScope := copyNames(scope)
					captureValues(arm.Pattern, subject, guardScope)
					cond = "(" + cond + ") && (" + g.expr(arm.Guard, guardScope) + ")"
				}
				if i > 0 {
					out.WriteString(" else ")
				}
				out.WriteString(mark + "if " + cond + " {\n" + binds + g.block(arm.Body, branch) + "}")
			}
			out.WriteString(" else {" + mark + "failAt(ctx," + g.location(s.Line, s.Column) + ",\"no case branch matched\");panic(\"unreachable\")}\n")

		case "if":
			a, b := map[string]string{}, map[string]string{}
			for k, v := range scope {
				a[k] = v
				b[k] = v
			}
			out.WriteString("if " + expr + " {\n" + g.block(s.Then, a) + "}")
			if len(s.Else) > 0 {
				out.WriteString(" else {\n" + g.block(s.Else, b) + "}")
			}
			out.WriteString("\n")
		}
	}
	return out.String()
}
func (g *generator) expr(e *ast.Expr, scope map[string]string) string {
	switch e.Kind {
	case "closure":
		local := copyNames(scope)
		params := []string{"ctx *actor.Context"}
		for _, param := range e.Params {
			id := g.id()
			local[param.Name] = id
			params = append(params, id+" "+goType(param.Type))
		}
		outerChecks, outerLeaf := g.statementChecks, g.leaf
		g.statementChecks, g.leaf = false, leafBody(e.Body)
		entry := ""
		if !g.leaf {
			entry = g.enter(e.Line, e.Column)
		}
		body := g.block(e.Body, local)
		g.statementChecks, g.leaf = outerChecks, outerLeaf
		return "func(" + strings.Join(params, ",") + ") " + goType(e.ReturnType) + " {\n" + entry + body + g.mark(e.Line) + "}"
	case "value":
		// An immediately called function gives the branches somewhere to return to.
		return "func() " + goType(e.Type) + " {\n" + g.block(e.Body, copyNames(scope)) + g.mark(e.Line) + "}()"
	case "invoke":
		args := []string{"ctx"}
		for _, arg := range e.Args {
			args = append(args, g.expr(arg, scope))
		}
		return "(" + g.expr(e.Left, scope) + ")(" + strings.Join(args, ",") + ")"
	case "funcref":
		if b, ok := syntax.SimpleBuiltins[e.Name]; ok {
			params, names := []string{"ctx *actor.Context"}, []string{}
			for _, t := range b.Params {
				id := g.id()
				params = append(params, id+" "+goType(t))
				names = append(names, id)
			}
			return "func(" + strings.Join(params, ",") + ") " + goType(b.Result) + " {return " + g.simpleBuiltin(b, names, e) + "}"
		}
		if readers := g.readersFor(e.Name, e.TypeArgs); len(readers) > 0 {
			// The value takes the function's own arguments; the readers
			// for the types chosen here go with it.
			parts, _, _ := ast.FunctionParts(e.Type)
			params, names := []string{"ctx *actor.Context"}, []string{"ctx"}
			for _, part := range parts {
				id := g.id()
				params, names = append(params, id+" "+goType(part)), append(names, id)
			}
			result, call := "", g.functions[e.Name]+typeArguments(e.TypeArgs)+"("+strings.Join(append(names, readers...), ",")+")"
			if def := g.defs[e.Name]; def.Type != "void" {
				_, returned, _ := ast.FunctionParts(e.Type)
				result, call = " "+goType(returned), "return "+call
			}
			return "func(" + strings.Join(params, ",") + ")" + result + " {" + call + "}"
		}
		return g.functions[e.Name] + typeArguments(e.TypeArgs)
	case "struct":
		typ := goType(e.Type)
		if e.Left == nil {
			fields := []string{}
			for i, arg := range e.Args {
				fields = append(fields, "F"+e.TypeArgs[i]+":"+g.expr(arg, scope))
			}
			return typ + "{" + strings.Join(fields, ",") + "}"
		}
		// A struct is a Go value, so assigning to the copy leaves the base intact.
		updated := g.id()
		body := updated + " := " + g.expr(e.Left, scope) + ";"
		for i, arg := range e.Args {
			body += updated + ".F" + e.TypeArgs[i] + " = " + g.expr(arg, scope) + ";"
		}
		return "func() " + typ + " {" + body + "return " + updated + "}()"
	case "field":
		return "(" + g.expr(e.Left, scope) + ").F" + e.Op
	case "variant":
		index, _ := strconv.Atoi(e.Op)
		fields := []string{}
		for _, arg := range e.Args {
			fields = append(fields, g.expr(arg, scope))
		}
		return goType(e.Type) + "(" + variantType(e.Type, index) + "{" + strings.Join(fields, ",") + "})"
	case "template":
		parts := []string{}
		for _, part := range e.Args {
			value := g.expr(part, scope)
			switch part.Type {
			case "integer":
				value = "intToString(" + value + ")"
			case "float":
				value = "floatString(" + value + ")"
			case "boolean":
				value = "strconv.FormatBool(" + value + ")"
			case "atom":
				value = "string(" + value + ")"
			}
			parts = append(parts, value)
		}
		if len(parts) == 0 {
			return `""`
		}
		return "(" + strings.Join(parts, "+") + ")"
	case "literal":
		return literalGo(e.Value)
	case "name":
		return scope[e.Name]
	case "map":
		name := g.id()
		var body strings.Builder
		// Kept on one generated line so the enclosing statement's line holds.
		body.WriteString("var " + name + " " + goType(e.Type) + ";")
		for i, key := range e.Keys {
			k, v := g.id(), g.id()
			body.WriteString(k + " := " + g.expr(key, scope) + ";" + v + " := " + g.expr(e.Args[i], scope) + ";" + name + " = actor.MapPut(" + name + "," + k + "," + v + ");")
		}
		return "func() " + goType(e.Type) + " {" + body.String() + "return " + name + " }()"
	case "list", "tuple":
		var values []string
		for _, arg := range e.Args {
			values = append(values, g.expr(arg, scope))
		}
		if elem, ok := ast.ListElement(e.Type); ok && e.Kind == "list" {
			if e.Right != nil {
				// The elements, then the tail, are evaluated in source order.
				return "listCons([]" + goType(elem) + "{" + strings.Join(values, ",") + "}," + g.expr(e.Right, scope) + ")"
			}
			// Elements are evaluated in source order, then stored reversed.
			return "mk([]" + goType(elem) + "{" + strings.Join(values, ",") + "})"
		}
		return goType(e.Type) + "{" + strings.Join(values, ",") + "}"
	case "index":
		if _, _, ok := ast.MapParts(e.Left.Type); ok {
			return "lookup(ctx," + g.expr(e.Left, scope) + "," + g.expr(e.Right, scope) + "," + g.location(e.Line, e.Column) + ")"
		}
		if _, ok := ast.TupleElements(e.Left.Type); ok {
			return "(" + g.expr(e.Left, scope) + ").E" + e.Name
		}
		return "at(ctx," + g.expr(e.Left, scope) + "," + g.expr(e.Right, scope) + "," + g.location(e.Line, e.Column) + ")"
	case "sigil":
		source, _ := syntax.RegexSource(e.Value.Text, e.Op)
		g.patterns = append(g.patterns, source)
		return fmt.Sprintf("pattern%d", len(g.patterns)-1)
	case "unmatched":
		value := g.expr(e.Left, scope)
		switch e.Op {
		case "skip":
			return "func(){}()"
		case "error":
			// The value is an error of another result type: carry its reason over.
			return "func() " + goType(e.Type) + " {if failure,ok := " + value + ".(" + variantType(e.Left.Type, 1) + ");ok{return " + goType(e.Type) + "(" + variantType(e.Type, 1) + "{failure.F0})};failAt(ctx," + g.location(e.Line, e.Column) + ",\"no with clause matched\");panic(\"unreachable\")}()"
		case "none":
			return goType(e.Type) + "(" + variantType(e.Type, 0) + "{})"
		}
		return value
	case "try":
		return g.try(e, scope)
	case "for":
		return g.comprehension(e, scope)
	case "range":
		bounds := "ctx," + g.expr(e.Left, scope) + "," + g.expr(e.Right, scope)
		if e.Type == "Range" {
			step := "0"
			if len(e.Args) == 1 {
				step = g.expr(e.Args[0], scope)
			}
			return "rangeOf(" + bounds + "," + step + "," + g.location(e.Line, e.Column) + ")"
		}
		if len(e.Args) == 1 {
			return "rangeStep(" + bounds + "," + g.expr(e.Args[0], scope) + "," + g.location(e.Line, e.Column) + ")"
		}
		return "rangeSeq(" + bounds + ")"
	case "in":
		return "enumMember(" + sequence(e.Right.Type, g.expr(e.Right, scope)) + "," + g.expr(e.Left, scope) + "," + equalityFunc(e.Left.Type) + ")"
	case "owned":
		return "actor.MapOwned(" + g.expr(e.Left, scope) + ")"
	case "fixed":
		// A template's own text is the same every time it is rendered: it
		// is made once, as a package variable.
		pieces := make([]string, len(e.Args))
		for i, piece := range e.Args {
			pieces[i] = strconv.Quote(piece.Value.Text)
		}
		g.fixed = append(g.fixed, "mk([]string{"+strings.Join(pieces, ",")+"})")
		return fmt.Sprintf("fixed%d", len(g.fixed)-1)
	case "call":
		if e.Name == "Markup.template" && len(e.Args) == 3 && e.Args[1].Kind == "list" {
			built := *e
			built.Args = append([]*ast.Expr(nil), e.Args...)
			pieces := *e.Args[1]
			pieces.Kind = "fixed"
			built.Args[1] = &pieces
			e = &built
		}
		if at := g.ownedFold(e); at >= 0 {
			// The fold's map is its own until the fold is over.
			fold := *e
			fold.Args = append([]*ast.Expr(nil), e.Args...)
			fold.Args[at] = &ast.Expr{Kind: "owned", Type: e.Args[at].Type, Left: e.Args[at], Line: e.Line, Column: e.Column}
			return "actor.MapShared(" + g.expr(&fold, scope) + ")"
		}
		if entry, ok := syntax.Libraries[e.Op]; ok {
			return g.libraryCall(e, entry, scope)
		}
		if e.Name == "throw" && len(e.Args) == 1 {
			result := goType(e.Type)
			if e.Type == "void" {
				result = "struct{}"
			}
			call := "throwOf[" + result + "](ctx," + g.location(e.Line, e.Column) + "," + g.expr(e.Args[0], scope) + ")"
			if e.Type == "void" {
				return "_ = " + call
			}
			return call
		}
		if e.Name == "raise" && e.Args[0].Type != "string" {
			raised := goType(e.Args[0].Type)
			result := goType(e.Type)
			if e.Type == "void" {
				result = "struct{}"
			}
			call := "raiseException[" + result + "," + raised + "](ctx," + g.location(e.Line, e.Column) + "," + g.expr(e.Args[0], scope) + ",func(x " + raised + ") string {return x.F" + e.Op + "})"
			if e.Type == "void" {
				return "_ = " + call
			}
			return call
		}
		if e.Name == "raise" {
			arguments := "(ctx," + g.location(e.Line, e.Column) + "," + g.expr(e.Args[0], scope) + ")"
			if e.Type == "void" {
				return "failAt" + arguments
			}
			return "raiseOf[" + goType(e.Type) + "]" + arguments
		}
		if strings.HasPrefix(e.Name, "Process.") || strings.HasPrefix(e.Name, "Supervisor.") {
			return g.actorCall(e, scope)
		}
		if strings.HasPrefix(e.Name, "Server.") {
			args := []string{"ctx"}
			for _, arg := range e.Args {
				args = append(args, g.expr(arg, scope))
			}
			call := "actor." + map[string]string{"Server.start": "StartServer", "Server.start_supervised": "StartSupervisedServer", "Server.restarts": "ServerRestarts", "Server.call": "Call", "Server.cast": "Cast", "Server.stop": "StopServer", "Server.alive": "ServerAlive", "Server.await": "AwaitServer"}[e.Name] + "(" + strings.Join(append(args, g.location(e.Line, e.Column)), ",") + ")"
			switch e.Name {
			case "Server.call":
				return "serverReply(" + call + ")"
			case "Server.await":
				return goType(e.Type) + "(" + call + ")"
			}
			return call
		}
		if e.Name == "length" {
			value := g.expr(e.Args[0], scope)
			if parts, ok := ast.TupleElements(e.Args[0].Type); ok {
				return fmt.Sprintf("func() int64 { _ = %s; return %d }()", value, len(parts))
			}
			if _, ok := ast.ListElement(e.Args[0].Type); ok {
				return "int64(len((" + value + ").S))"
			}
			return "int64(actor.MapLen(" + value + "))"
		}
		var args []string
		for _, a := range e.Args {
			args = append(args, g.expr(a, scope))
		}
		if b, ok := syntax.SimpleBuiltins[e.Name]; ok {
			return g.simpleBuiltin(b, args, e)
		}
		args = append([]string{"ctx"}, args...)
		if loop, ok := g.inlineLoop(e, args); ok {
			return loop
		}
		if e.Name == "List.contains" {
			if comparable(e.Args[1].Type) {
				return "slices.Contains((" + args[1] + ").S," + args[2] + ")"
			}
			return "listContainsBy(" + args[1] + "," + args[2] + "," + equalityFunc(e.Args[1].Type) + ")"
		}
		target := g.functions[e.Name] + typeArguments(e.TypeArgs)
		if local, ok := scope[e.Name]; ok && g.functions[e.Name] == "" {
			target = local
		}
		if builtin, ok := map[string]string{"prepend": "listPrepend", "concat": "listConcat", "map": "listMap", "filter": "listFilter", "reduce": "listReduce", "put": "mapPut", "get": "mapGet", "has_key": "mapHas", "Map.keys": "mapKeys", "Map.values": "mapValues", "Map.entries": "mapEntries", "Map.delete": "mapDelete", "Map.merge": "mapMerge", "List.reverse": "listReverse", "List.take": "listTake", "List.drop": "listDrop", "List.contains": "listContains", "List.sort": "listSort", "List.range": "listRange", "List.zip": "listZip",
			"String.length": "strLength", "String.slice": "strSlice", "String.contains": "strings.Contains", "String.split": "strSplit", "String.join": "strJoin", "String.trim": "strings.TrimSpace", "String.upcase": "strings.ToUpper", "String.downcase": "strings.ToLower",
			"Integer.to_string": "intToString", "Integer.parse": "intParse", "Time.monotonic": "timeMonotonic", "Time.now": "timeNow",
			"System.argv": "sysArgv", "IO.read_line": "ioReadLine", "IO.read_all": "ioReadAll", "File.read": "fileRead"}[e.Name]; ok {
			target = builtin
			switch e.Name {
			case "map", "filter", "reduce":
			case "List.take", "List.drop", "List.range", "String.slice", "String.split", "IO.read_line", "IO.read_all":
				// These can fail at runtime and report the call's position.
				args = append(args, g.location(e.Line, e.Column))
			default:
				args = args[1:]
			}
		}
		if e.Name == "Map.keys" || e.Name == "Map.values" || e.Name == "Map.entries" {
			key, _, _ := ast.MapParts(e.Args[0].Type)
			comparison := "a<b"
			if key == "boolean" {
				comparison = "!a&&b"
			}
			args = append(args, "func(a,b "+goType(key)+")bool{return "+comparison+"}")
		}
		if _, local := scope[e.Name]; !local {
			args = append(args, g.readersFor(e.Name, e.TypeArgs)...)
		}
		return target + "(" + strings.Join(args, ",") + ")"
	case "unary":
		if e.Op == "not" {
			return "(!" + g.expr(e.Left, scope) + ")"
		}
		if e.Type == "float" {
			// Go folds the constant -0.0 to positive zero; negating through
			// a function keeps the sign.
			return "floatNeg(" + g.expr(e.Left, scope) + ")"
		}
		return "neg(ctx," + g.expr(e.Left, scope) + "," + g.location(e.Line, e.Column) + ")"
	default:
		return g.binary(e, g.expr(e.Left, scope), g.expr(e.Right, scope))
	}
}

// binary combines two generated operands with a binary operator.
func (g *generator) binary(e *ast.Expr, a, b string) string {
	{
		switch e.Op {
		case "<>":
			// Two literals are joined by the Go compiler; anything else
			// goes through the runtime, which grows a string in place when
			// a loop keeps appending to it.
			if strings.HasPrefix(a, "\"") && strings.HasPrefix(b, "\"") {
				return "(" + a + "+" + b + ")"
			}
			return "actor.Concat(ctx," + a + "," + b + ")"
		case "++":
			return "listConcat(" + a + "," + b + ")"
		case "--":
			member, _ := ast.ListElement(e.Type)
			return "listSubtract(" + a + "," + b + "," + equalityFunc(member) + ")"
		case "**":
			if e.Type == "float" {
				return "math.Pow(" + a + "," + b + ")"
			}
			return "intPow(ctx," + a + "," + b + "," + g.location(e.Line, e.Column) + ")"
		}
		if e.Type == "float" {
			if e.Op == "/" {
				return "fdiv(ctx," + a + "," + b + "," + g.location(e.Line, e.Column) + ")"
			}
			return "(" + a + e.Op + b + ")"
		}
		if name, ok := map[string]string{"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod"}[e.Op]; ok {
			return name + "(ctx," + a + "," + b + "," + g.location(e.Line, e.Column) + ")"
		}
		if e.Op == "==" {
			return equality(e.Left.Type, a, b)
		}
		if e.Op == "!=" {
			return "(!" + equality(e.Left.Type, a, b) + ")"
		}
		op := e.Op
		if op == "<>" {
			op = "+"
		}
		if op == "and" {
			op = "&&"
		}
		if op == "or" {
			op = "||"
		}
		return "(" + a + op + b + ")"
	}
}

// comparable reports whether a type's generated Go representation supports
// the == operator with Alchem's structural meaning: primitives, and tuples
// built only from such types.
func comparable(typ string) bool {
	switch typ {
	case "integer", "boolean", "string", "float", "atom":
		return true
	}
	if parts, ok := ast.TupleElements(typ); ok {
		for _, part := range parts {
			if !comparable(part) {
				return false
			}
		}
		return true
	}
	return false
}

// equality compares two generated values of one Alchem type: Go's operator
// where the representation supports it, a slice comparison for flat lists, and
// otherwise a comparison function generated for exactly that type. Nothing is
// compared through reflection. An absent list or map equals an empty one.
func equality(typ, a, b string) string {
	if comparable(typ) {
		return "(" + a + "==" + b + ")"
	}
	if elem, ok := ast.ListElement(typ); ok && comparable(elem) {
		return "slices.Equal((" + a + ").S,(" + b + ").S)"
	}
	return equalityFunc(typ) + "(" + a + "," + b + ")"
}

// equalityFunc returns a Go function literal comparing two values of typ,
// built recursively from the type's structure.
func equalityFunc(typ string) string {
	head := "func(x,y " + goType(typ) + ")bool{return "
	if comparable(typ) {
		return head + "x==y}"
	}
	// Declared types and type variables have no fixed shape here, so they are
	// compared structurally at run time.
	if _, _, named := ast.Named(typ); named || ast.TypeVariable(typ) {
		return head + "equal(x,y)}"
	}
	if elem, ok := ast.ListElement(typ); ok {
		if comparable(elem) {
			return head + "slices.Equal(x.S,y.S)}"
		}
		return head + "listEqBy(x,y," + equalityFunc(elem) + ")}"
	}
	if _, value, ok := ast.MapParts(typ); ok {
		return head + "mapEqBy(x,y," + equalityFunc(value) + ")}"
	}
	if kind, _ := ast.Split(typ); kind == "set" {
		return head + "mapEqBy(x,y,func(a,b struct{})bool{return true})}"
	}
	parts, _ := ast.TupleElements(typ)
	fields := []string{}
	for i, part := range parts {
		fields = append(fields, equality(part, fmt.Sprintf("x.E%d", i), fmt.Sprintf("y.E%d", i)))
	}
	return head + strings.Join(fields, "&&") + "}"
}

// try generates try as a function called on the spot. A deferred recover
// hands a thrown value to the catch arms and a failure to the rescue arms;
// what no arm matches, and a stop request, keeps unwinding. The cleanup,
// deferred first, runs last on every way out. With else arms the body runs
// in a function of its own, so that a failure in an else arm is not rescued.
func (g *generator) try(e *ast.Expr, scope map[string]string) string {
	statement := e.Body[0]
	result := goType(e.Type)
	out, depth, failure := g.id(), g.id(), g.id()
	var rescues, catches, results []ast.Arm
	for _, arm := range statement.Arms {
		switch arm.Kind {
		case "catch":
			catches = append(catches, arm)
		case "else":
			results = append(results, arm)
		default:
			rescues = append(rescues, arm)
		}
	}
	var code strings.Builder
	code.WriteString("func() (" + out + " " + result + ") {\n" + depth + " := actor.Depth(ctx); _ = " + depth + "\n")
	if len(statement.Else) > 0 {
		code.WriteString("defer func(){\n" + g.block(statement.Else, copyNames(scope)) + "}()\n")
	}
	// An arm that takes any message makes a failure certain to be handled
	// here, so nothing will report where it came from: the runtime is told,
	// and skips recording the stack of failures raised inside.
	certain := false
	for _, arm := range rescues {
		certain = certain || (arm.Guard == nil && arm.Type == "string" && (arm.Pattern.Kind == "wildcard" || arm.Pattern.Kind == "name"))
	}
	leave := ""
	handled := ""
	if len(results) > 0 {
		handled = g.id()
		code.WriteString(handled + " := false\n")
	}
	// answer is the code an arm runs once it matches.
	answer := func(arm ast.Arm, branch map[string]string) string {
		text := out + " = func() " + result + " {\n" + g.block(arm.Body, branch) + "}()\n"
		if handled != "" {
			text += handled + " = true\n"
		}
		return text + "return\n"
	}
	// match writes an arm that applies when its pattern, and guard, match
	// value.
	match := func(b *strings.Builder, arm ast.Arm, value string) {
		branch := copyNames(scope)
		condition, binds := g.pattern(arm.Pattern, value, branch)
		if arm.Guard != nil {
			guardScope := copyNames(scope)
			captureValues(arm.Pattern, value, guardScope)
			condition = "(" + condition + ") && (" + g.expr(arm.Guard, guardScope) + ")"
		}
		b.WriteString("if " + condition + " {\n" + binds + answer(arm, branch) + "}\n")
	}
	var handlers strings.Builder
	if len(rescues)+len(catches) > 0 {
		if certain {
			handlers.WriteString("actor.Handling(ctx, 1)\n")
			leave = "actor.Handling(ctx, -1)\n"
		}
		handlers.WriteString("defer func(){\n" + leave + failure + " := recover()\nif " + failure + " == nil {return}\n")
		if len(catches) > 0 {
			thrown, ok := g.id(), g.id()
			handlers.WriteString("if " + thrown + "," + ok + " := actor.Caught(ctx," + failure + "," + depth + "); " + ok + " {\n")
			for _, arm := range catches {
				value, fits := g.id(), g.id()
				handlers.WriteString("if " + value + "," + fits + " := " + thrown + ".(" + goType(arm.Type) + "); " + fits + " {\n")
				match(&handlers, arm, value)
				handlers.WriteString("}\n")
			}
			handlers.WriteString("panic(" + failure + ")\n}\n")
		}
		if len(rescues) > 0 {
			message, raised, ok := g.id(), g.id(), g.id()
			handlers.WriteString(message + "," + raised + "," + ok + " := actor.Rescued(ctx," + failure + "," + depth + ")\nif !" + ok + " {panic(" + failure + ")}\n_, _ = " + message + "," + raised + "\n")
			for _, arm := range rescues {
				if arm.Type == "string" {
					match(&handlers, arm, message)
					continue
				}
				value, fits := g.id(), g.id()
				handlers.WriteString("if " + value + "," + fits + " := " + raised + ".(" + goType(arm.Type) + "); " + fits + " {\n")
				match(&handlers, arm, value)
				handlers.WriteString("}\n")
			}
		}
		handlers.WriteString("panic(" + failure + ")\n}()\n")
	}
	if len(results) == 0 {
		code.WriteString(handlers.String() + g.block(statement.Then, copyNames(scope)) + g.mark(e.Line) + "}()")
		return code.String()
	}
	bodyType := goType(results[0].Type)
	value := g.id()
	code.WriteString(value + " := func() " + bodyType + " {\n" + handlers.String() + g.block(statement.Then, copyNames(scope)) + "}()\nif " + handled + " {return}\n_ = " + value + "\n")
	for _, arm := range results {
		branch := copyNames(scope)
		condition, binds := g.pattern(arm.Pattern, value, branch)
		if arm.Guard != nil {
			guardScope := copyNames(scope)
			captureValues(arm.Pattern, value, guardScope)
			condition = "(" + condition + ") && (" + g.expr(arm.Guard, guardScope) + ")"
		}
		code.WriteString("if " + condition + " {\n" + binds + "return func() " + result + " {\n" + g.block(arm.Body, branch) + "}()\n}\n")
	}
	code.WriteString("failAt(ctx," + g.location(e.Line, e.Column) + ",\"no else clause of this try matched\")\npanic(\"unreachable\")\n}()")
	return code.String()
}

// comprehension generates for as nested loops over its generators. An
// element that does not match a generator's pattern, or fails a filter, is
// skipped.
func (g *generator) comprehension(e *ast.Expr, scope map[string]string) string {
	statement := e.Body[0]
	member, _ := ast.ListElement(e.Type)
	out := g.id()
	local := copyNames(scope)
	var code strings.Builder
	reducing := len(e.Labels) == 1 && e.Labels[0] == "reduce"
	if reducing {
		// The accumulator starts as the initial value and is replaced by
		// the body's value for every combination.
		member = e.Type
		code.WriteString("func() " + goType(e.Type) + " {\n" + out + " := " + g.expr(e.Args[0], scope) + "\n")
		local[e.Name] = out
	} else {
		code.WriteString("func() " + goType(e.Type) + " {\nvar " + out + " []" + goType(member) + "\n")
	}
	closing := ""
	for _, arm := range statement.Arms {
		if arm.Pattern == nil {
			code.WriteString("if !(" + g.expr(arm.Guard, local) + ") {return true}\n")
			continue
		}
		item := g.id()
		code.WriteString(sequence(arm.Guard.Type, g.expr(arm.Guard, local)) + "(func(" + item + " " + goType(arm.Pattern.Type) + ") bool {\n")
		condition, binds := g.pattern(arm.Pattern, item, local)
		code.WriteString("if !(" + condition + ") {return true}\n" + binds)
		closing = "return true\n})\n" + closing
	}
	if reducing {
		code.WriteString(out + " = func() " + goType(member) + " {\n" + g.block(statement.Then, local) + "}()\n" + closing + "return " + out + "\n}()")
		return code.String()
	}
	code.WriteString(out + " = append(" + out + ", func() " + goType(member) + " {\n" + g.block(statement.Then, local) + "}())\n" + closing + "return mk(" + out + ")\n}()")
	return code.String()
}

// sequence adapts a generated enumerable value to the iterator the library
// runtime works on. Maps and sets are visited in key order.
func sequence(t, value string) string {
	switch head, args := ast.Split(t); head {
	case "list":
		return "seqList(" + value + ")"
	case "map":
		return "seqMap(" + value + "," + lessFunc(args[0]) + ")"
	case "set":
		return "seqSet(" + value + "," + lessFunc(args[0]) + ")"
	case "Range":
		return "seqRange(" + value + ")"
	}
	return value
}

// lessFunc returns a Go function literal ordering two values of typ: numbers
// and strings by value, false before true, and tuples and lists position by
// position.
func lessFunc(typ string) string {
	head := "func(x,y " + goType(typ) + ")bool{"
	if typ == "boolean" {
		return head + "return !x&&y}"
	}
	if elem, ok := ast.ListElement(typ); ok {
		return head + "return listLess(x,y," + lessFunc(elem) + ")}"
	}
	if parts, ok := ast.TupleElements(typ); ok {
		body := ""
		for i, part := range parts {
			less := lessFunc(part)
			body += fmt.Sprintf("if %s(x.E%d,y.E%d){return true};if %s(y.E%d,x.E%d){return false};", less, i, i, less, i, i)
		}
		return head + body + "return false}"
	}
	return head + "return x<y}"
}

// showFunc returns a Go function literal rendering a value of typ as text.
func showFunc(typ string) string {
	switch typ {
	case "integer":
		return "intToString"
	case "float":
		return "floatString"
	case "boolean":
		return "strconv.FormatBool"
	case "atom":
		return "func(x actor.Atom)string{return string(x)}"
	}
	return "func(x string)string{return x}"
}

// libraryCall generates a call to a standard library function: enumerable
// arguments become iterators, and each constrained type variable contributes
// the comparison or conversion function for the type it was bound to.
func (g *generator) libraryCall(e *ast.Expr, entry syntax.Library, scope map[string]string) string {
	bound := map[string]string{}
	for i, name := range entry.Vars {
		bound[name] = e.TypeArgs[i]
	}
	target := entry.Go
	var args []string
	if entry.Ctx {
		args = append(args, "ctx")
	}
	// A function with a list variant gets the lists themselves when every
	// enumerable argument is one, which saves going through an iterator.
	direct := entry.Lists
	for i, arg := range e.Args {
		if head, _ := ast.Split(entry.Params[i]); head == "enum" {
			if kind, _ := ast.Split(arg.Type); kind != "list" {
				direct = false
			}
		}
	}
	if direct {
		target += "L"
	}
	for i, arg := range e.Args {
		value := g.expr(arg, scope)
		if head, _ := ast.Split(entry.Params[i]); head == "enum" && !direct {
			value = sequence(arg.Type, value)
		}
		args = append(args, value)
	}
	fast := map[string]bool{}
	for _, name := range entry.Fast {
		if comparable(bound[name]) {
			fast[name] = true
			target = entry.Go + "C"
		}
	}
	if entry.Explicit {
		target += typeArguments(e.TypeArgs)
	}
	for _, name := range entry.Equal {
		if !fast[name] {
			args = append(args, equalityFunc(bound[name]))
		}
	}
	for _, name := range entry.Order {
		args = append(args, lessFunc(bound[name]))
	}
	for _, name := range entry.Show {
		args = append(args, showFunc(bound[name]))
	}
	for _, name := range entry.Codec {
		args = append(args, g.codec(bound[name]))
	}
	for _, name := range entry.Read {
		args = append(args, g.reader(bound[name]))
	}
	if entry.Where {
		args = append(args, g.location(e.Line, e.Column))
	}
	return target + "(" + strings.Join(args, ",") + ")"
}

// inlineLoop expands map, filter and reduce over a named function into a loop
// that calls the function directly. A direct call can be inlined by the Go
// compiler; the generic helpers call through a function value and cannot.
// Arguments keep their left-to-right evaluation order.
func (g *generator) inlineLoop(e *ast.Expr, args []string) (string, bool) {
	if e.Name != "map" && e.Name != "filter" && e.Name != "reduce" {
		return "", false
	}
	callback := e.Args[len(e.Args)-1]
	if callback.Kind != "funcref" || g.functions[callback.Name] == "" || len(g.readersFor(callback.Name, callback.TypeArgs)) > 0 {
		return "", false
	}
	function := g.functions[callback.Name] + typeArguments(callback.TypeArgs)
	xs, x, out, index := g.id(), g.id(), g.id(), g.id()
	result := goType(e.Type)
	// Lists store their head last, so walking the storage backwards visits
	// elements in list order.
	head := "func() " + result + " {" + xs + " := " + args[1] + ";"
	walk := "for " + index + " := len(" + xs + ".S)-1;" + index + ">=0;" + index + "-- {" + x + " := " + xs + ".S[" + index + "];"
	switch e.Name {
	case "map":
		elem, _ := ast.ListElement(e.Type)
		return head + out + " := make([]" + goType(elem) + ",len(" + xs + ".S));" + walk + out + "[" + index + "] = " + function + "(ctx," + x + ")};return " + result + "{S:" + out + "}}()", true
	case "filter":
		elem, _ := ast.ListElement(e.Type)
		return head + out + " := make([]" + goType(elem) + ",0,len(" + xs + ".S));" + walk + "if " + function + "(ctx," + x + ") {" + out + " = append(" + out + "," + x + ")}};return mk(" + out + ")}()", true
	default:
		return head + out + " := " + args[2] + ";" + walk + out + " = " + function + "(ctx," + out + "," + x + ")};return " + out + "}()", true
	}
}
func literalGo(v ast.Literal) string {
	switch v.Kind {
	case "integer":
		return "int64(" + strconv.FormatInt(v.Integer, 10) + ")"
	case "boolean":
		return strconv.FormatBool(v.Boolean)
	case "atom":
		return "actor.Atom(" + strconv.Quote(v.Text) + ")"
	case "float":
		// Go has no negative zero constant, so -0.0 is negated when it runs.
		if v.Float == 0 && 1/v.Float < 0 {
			return "floatNeg(float64(0))"
		}
		return "float64(" + strconv.FormatFloat(v.Float, 'g', -1, 64) + ")"
	default:
		return strconv.Quote(v.Text)
	}
}

// simpleBuiltin calls a fixed-signature builtin with already generated arguments.
func (g *generator) simpleBuiltin(b syntax.SimpleBuiltin, args []string, e *ast.Expr) string {
	if b.Fails {
		args = append(append([]string{"ctx"}, args...), g.location(e.Line, e.Column))
	}
	return b.Go + "(" + strings.Join(args, ",") + ")"
}

// tailTarget is a function whose calls to itself in return position become
// jumps: slots are the Go variables holding its parameters between turns.
type tailTarget struct {
	name, label string
	slots       []string
	used        bool
}

// tailCall generates "return f(...)" inside f as an assignment to f's
// parameters and a jump to its start, so recursion in return position runs
// as a loop: it uses no stack and is not held to the call-depth limit. Each
// turn checks for cancellation, as each call would have.
func (g *generator) tailCall(target *tailTarget, s ast.Statement, scope map[string]string) (string, bool) {
	e := s.Expr
	if target == nil || s.Kind != "return" || e == nil || e.Kind != "call" || e.Name != target.name || len(e.Args) != len(target.slots) || len(e.TypeArgs) > 0 {
		return "", false
	}
	if _, shadowed := scope[e.Name]; shadowed || g.functions[e.Name] == "" {
		return "", false
	}
	args := make([]string, len(e.Args))
	for i, arg := range e.Args {
		args[i] = g.expr(arg, scope)
	}
	target.used = true
	return strings.Join(target.slots, ",") + " = " + strings.Join(args, ",") + "\nactor.Check(ctx)\ncontinue " + target.label + "\n", true
}

// leafBody reports whether a function or closure body calls no other function:
// no user function, function value, anonymous function, callback-taking
// operation or process operation. Such a body cannot recurse, block or repeat,
// so it needs neither call-depth tracking nor its own cancellation point, and
// without them it is usually small enough for the Go compiler to inline.
func leafBody(body []ast.Statement) bool {
	for _, s := range body {
		if !leafExpr(s.Expr) || !leafBody(s.Then) || !leafBody(s.Else) {
			return false
		}
		for _, arm := range s.Arms {
			if !leafExpr(arm.Guard) || !leafBody(arm.Body) {
				return false
			}
		}
	}
	return true
}
func leafExpr(e *ast.Expr) bool {
	if e == nil {
		return true
	}
	switch e.Kind {
	case "invoke", "closure", "try", "for":
		return false
	case "value":
		if !leafBody(e.Body) {
			return false
		}
	case "call":
		switch e.Name {
		case "length", "prepend", "concat", "put", "get", "has_key":
		default:
			// Pure operations cannot block. File, IO and System calls can, so a
			// function that makes one keeps its cancellation point.
			if entry, ok := syntax.Libraries[e.Op]; ok && entry.Ctx {
				return false
			}
			pure := false
			for _, namespace := range []string{"List.", "Map.", "String.", "Integer.", "Float.", "Time."} {
				pure = pure || strings.HasPrefix(e.Name, namespace)
			}
			if !pure {
				return false
			}
		}
	}
	if !leafExpr(e.Left) || !leafExpr(e.Right) {
		return false
	}
	for _, arg := range e.Args {
		if !leafExpr(arg) {
			return false
		}
	}
	for _, key := range e.Keys {
		if !leafExpr(key) {
			return false
		}
	}
	return true
}

// enter counts a function or closure activation against the call-depth limit.
// The matching decrement is the actor.Leave wrapped around every return; a
// deferred call here would cost more than the call itself and block inlining.
func (g *generator) enter(line, col int) string {
	return "actor.Enter(ctx," + g.location(line, col) + ")\n"
}

// mark emits a directive assigning the next generated line to an Alchem line.
// Source paths are rejected by the build when they contain a line break.
func (g *generator) mark(line int) string {
	return fmt.Sprintf("\n//line %s:%d\n", g.source, line)
}
func (g *generator) location(line, col int) string {
	return strconv.Quote(fmt.Sprintf("%s:%d:%d", g.source, line, col))
}
func copyNames(scope map[string]string) map[string]string {
	out := map[string]string{}
	for k, v := range scope {
		out[k] = v
	}
	return out
}
func (g *generator) pattern(p *ast.Pattern, value string, scope map[string]string) (string, string) {
	switch p.Kind {
	case "wildcard":
		return "true", ""
	case "name":
		id := g.id()
		scope[p.Name] = id
		return "true", id + " := " + value + "; _ = " + id + "\n"
	case "literal":
		return equality(p.Type, value, literalGo(p.Value)), ""
	case "pin":
		return equality(p.Type, value, scope[p.Name]), ""
	case "struct", "variant":
		conditions := []string{}
		access := "(" + value + ").F"
		if p.Kind == "variant" {
			variant := variantType(p.Type, p.Index)
			conditions = append(conditions, "is["+variant+"]("+value+")")
			access = "(" + value + ").(" + variant + ").F"
		}
		var binds strings.Builder
		for i, child := range p.Children {
			field := i
			if p.Kind == "struct" {
				field = p.Fields[i]
			}
			cond, body := g.pattern(child, access+strconv.Itoa(field), scope)
			conditions = append(conditions, "("+cond+")")
			binds.WriteString(body)
		}
		if len(conditions) == 0 {
			return "true", ""
		}
		return "(" + strings.Join(conditions, "&&") + ")", binds.String()
	}
	if p.Kind == "map" {
		conditions := []string{}
		var body strings.Builder
		for i, key := range p.Keys {
			k := literalGo(key)
			conditions = append(conditions, "mapHas("+value+","+k+")")
			cond, binds := g.pattern(p.Children[i], "mapAt("+value+","+k+")", scope)
			conditions = append(conditions, "("+cond+")")
			body.WriteString(binds)
		}
		if len(conditions) == 0 {
			return "true", body.String()
		}
		return "(" + strings.Join(conditions, "&&") + ")", body.String()
	}

	var conditions []string
	var binds strings.Builder
	if p.Kind == "list" {
		op := "=="
		if p.Tail != nil {
			op = ">="
		}
		conditions = append(conditions, fmt.Sprintf("len((%s).S)%s%d", value, op, len(p.Children)))
	}
	for i, child := range p.Children {
		access := fmt.Sprintf("(%s).E%d", value, i)
		if p.Kind == "list" {
			access = fmt.Sprintf("lat(%s,%d)", value, i)
		}
		cond, body := g.pattern(child, access, scope)
		conditions = append(conditions, "("+cond+")")
		binds.WriteString(body)
	}
	if p.Tail != nil {
		cond, body := g.pattern(p.Tail, fmt.Sprintf("lfrom(%s,%d)", value, len(p.Children)), scope)
		conditions = append(conditions, "("+cond+")")
		binds.WriteString(body)
	}
	if len(conditions) == 0 {
		return "true", binds.String()
	}
	return "(" + strings.Join(conditions, "&&") + ")", binds.String()
}

func captureValues(p *ast.Pattern, value string, scope map[string]string) {
	if p.Kind == "name" {
		scope[p.Name] = value
		return
	}
	for i, child := range p.Children {
		access := fmt.Sprintf("(%s).E%d", value, i)
		if p.Kind == "list" {
			access = fmt.Sprintf("lat(%s,%d)", value, i)
		}
		if p.Kind == "struct" {
			access = fmt.Sprintf("(%s).F%d", value, p.Fields[i])
		}
		if p.Kind == "variant" {
			access = fmt.Sprintf("(%s).(%s).F%d", value, variantType(p.Type, p.Index), i)
		}
		if p.Kind == "map" {
			access = "mapAt(" + value + "," + literalGo(p.Keys[i]) + ")"
		}
		captureValues(child, access, scope)
	}
	if p.Tail != nil {
		captureValues(p.Tail, fmt.Sprintf("lfrom(%s,%d)", value, len(p.Children)), scope)
	}
}

const arithmeticRuntime = `
func sortedKeys[K comparable,V any](m actor.Map[K,V],less func(K,K)bool)[]K{out,_:=actor.MapSorted(m,less);return out}
func mapKeys[K comparable,V any](m actor.Map[K,V],less func(K,K)bool)L[K]{return mk(sortedKeys(m,less))}
func mapValues[K comparable,V any](m actor.Map[K,V],less func(K,K)bool)L[V]{_,out:=actor.MapSorted(m,less);return mk(out)}
func mapEntries[K comparable,V any](m actor.Map[K,V],less func(K,K)bool)L[struct{E0 K;E1 V}]{keys,values:=actor.MapSorted(m,less);out:=make([]struct{E0 K;E1 V},len(keys));for i,key:=range keys{out[i]=struct{E0 K;E1 V}{key,values[i]}};return mk(out)}
func mapDelete[K comparable,V any](m actor.Map[K,V],key K)actor.Map[K,V]{return actor.MapDelete(m,key)}

// L is an immutable list. S stores the elements with the head last: list
// index i is S[len(S)-1-i], so taking a tail is a reslice and prepending is an
// append. H, when set, belongs to the backing array and counts how many of its
// slots are claimed. A prepend extends the array in place only if it wins the
// claim for the next slot; a second prepend onto the same list loses the claim
// and copies, so neither can overwrite the other, even from another process.
// Only views that start at the array's first slot carry H.
type lh struct{used atomic.Int64}
type L[T any] struct{S []T;H *lh}
// mk takes ownership of a slice in list order and reverses it into storage order.
func mk[T any](xs []T)L[T]{for i,j:=0,len(xs)-1;i<j;i,j=i+1,j-1{xs[i],xs[j]=xs[j],xs[i]};return L[T]{S:xs}}
// fwd copies a list into a slice in list order for runtime calls that take one.
func fwd[T any](l L[T])[]T{out:=make([]T,len(l.S));for i,x:=range l.S{out[len(l.S)-1-i]=x};return out}
func lat[T any](l L[T],i int)T{return l.S[len(l.S)-1-i]}
func lfrom[T any](l L[T],k int)L[T]{return L[T]{l.S[:len(l.S)-k],l.H}}
// Strings are UTF-8; length and slice count grapheme clusters, what a
// reader takes as characters, not bytes or code points.
func strLength(s string)int64{return graphemeCount(s)}
func strSlice(ctx *actor.Context,s string,start,count int64,where string)string{if start<0||count<0{failAt(ctx,where,"slice bounds must be nonnegative")};if simple(s){size:=int64(len(s));if start>=size{return ""};return s[start:min(size,start+count)]};from,to,seen,i:=len(s),len(s),int64(0),0;for i<len(s){if seen==start{from=i};if seen==start+count{to=i;break};i+=graphemeLen(s[i:]);seen++};if seen==start{from=min(from,i)};return s[from:to]}
func strSplit(ctx *actor.Context,s,separator string,where string)L[string]{if separator==""{failAt(ctx,where,"separator must not be empty")};return mk(strings.Split(s,separator))}
func strJoin(parts L[string],separator string)string{return strings.Join(fwd(parts),separator)}
func intToString(n int64)string{return strconv.FormatInt(n,10)}
func intParse(s string)Tresult[int64,string]{n,err:=strconv.ParseInt(s,10,64);if err!=nil{return errOf[int64](strconv.Quote(s)+" is not an integer")};return okOf(n)}
var started=time.Now()
func timeMonotonic()int64{return time.Since(started).Microseconds()}
func timeNow()int64{return time.Now().UnixMilli()}
// Program input. Everything read becomes an Alchem string, so it is bounded
// and must be valid UTF-8. Standard input is shared by all processes behind one
// lock; a read blocks its process until the operating system returns.
const maxLine=1<<20
const maxInput=16<<20
var stdin=struct{sync.Mutex;reader *bufio.Reader}{reader:bufio.NewReaderSize(os.Stdin,1<<16)}
func sysArgv()L[string]{out:=make([]string,0,len(os.Args));for _,argument:=range os.Args[1:]{out=append(out,strings.ToValidUTF8(argument,"\uFFFD"))};return mk(out)}
func ioReadLine(ctx *actor.Context,where string)Toption[string]{
	stdin.Lock();defer stdin.Unlock()
	var line []byte
	for{
		chunk,err:=stdin.reader.ReadSlice('\n')
		line=append(line,chunk...)
		// The limit is on the text; allow room for the line ending while reading.
		if len(line)>maxLine+2{failAt(ctx,where,"input line exceeds 1048576 bytes")}
		if err==bufio.ErrBufferFull{continue}
		if err!=nil&&len(line)==0{return noneOf[string]()}
		break
	}
	text:=strings.TrimSuffix(strings.TrimSuffix(string(line),"\n"),"\r")
	if len(text)>maxLine{failAt(ctx,where,"input line exceeds 1048576 bytes")}
	if !utf8.ValidString(text){failAt(ctx,where,"input is not valid UTF-8")}
	return someOf(text)
}
func ioReadAll(ctx *actor.Context,where string)string{
	stdin.Lock();defer stdin.Unlock()
	data,err:=io.ReadAll(io.LimitReader(stdin.reader,maxInput+1))
	if err!=nil{failAt(ctx,where,"cannot read standard input")}
	if len(data)>maxInput{failAt(ctx,where,"input exceeds 16777216 bytes")}
	if !utf8.Valid(data){failAt(ctx,where,"input is not valid UTF-8")}
	return string(data)
}
// fileRead reports failure, rather than failing the process, for a file that
// is missing, unreadable, larger than the input limit or not UTF-8 text. The
// reason is the operating system's message for the first two.
func fileRead(path string)Tresult[string,string]{
	file,err:=os.Open(path)
	if err!=nil{return errOf[string](err.Error())}
	defer file.Close()
	data,err:=io.ReadAll(io.LimitReader(file,maxInput+1))
	if err!=nil{return errOf[string](err.Error())}
	if len(data)>maxInput{return errOf[string]("file exceeds 16777216 bytes")}
	if !utf8.Valid(data){return errOf[string]("file is not valid UTF-8")}
	return okOf(string(data))
}
func listReverse[T any](l L[T])L[T]{out:=make([]T,len(l.S));for i,x:=range l.S{out[len(l.S)-1-i]=x};return L[T]{S:out}}
func listCount(ctx *actor.Context,n int64,size int,where string)int{if n<0{failAt(ctx,where,"count must be nonnegative")};if n>int64(size){return size};return int(n)}
func listTake[T any](ctx *actor.Context,l L[T],n int64,where string)L[T]{k:=listCount(ctx,n,len(l.S),where);return L[T]{S:l.S[len(l.S)-k:]}}
func listDrop[T any](ctx *actor.Context,l L[T],n int64,where string)L[T]{return lfrom(l,listCount(ctx,n,len(l.S),where))}
func listContainsBy[T any](l L[T],value T,eq func(T,T)bool)bool{for _,x:=range l.S{if eq(x,value){return true}};return false}
func listEqBy[T any](a,b L[T],eq func(T,T)bool)bool{if len(a.S)!=len(b.S){return false};for i:=range a.S{if !eq(a.S[i],b.S[i]){return false}};return true}
func mapEqBy[K comparable,V any](a,b actor.Map[K,V],eq func(V,V)bool)bool{if actor.MapLen(a)!=actor.MapLen(b){return false};same:=true;actor.MapEach(a,func(key K,value V){if other,ok:=actor.MapGet(b,key);!ok||!eq(value,other){same=false}});return same}
func listSort[T int64|float64|string](l L[T])L[T]{out:=make([]T,len(l.S));copy(out,l.S);sort.Slice(out,func(i,j int)bool{return out[i]>out[j]});return L[T]{S:out}}
const maxRange = 1000000
func listRange(ctx *actor.Context,from,to int64,where string)L[int64]{if to<from{return L[int64]{}};span:=uint64(to)-uint64(from);if span>=maxRange{failAt(ctx,where,"range exceeds 1000000 elements")};out:=make([]int64,span+1);for i:=range out{out[i]=to-int64(i)};return L[int64]{S:out}}
func listZip[A,B any](a L[A],b L[B])L[struct{E0 A;E1 B}]{n:=len(a.S);if len(b.S)<n{n=len(b.S)};out:=make([]struct{E0 A;E1 B},n);for i:=0;i<n;i++{out[n-1-i]=struct{E0 A;E1 B}{lat(a,i),lat(b,i)}};return L[struct{E0 A;E1 B}]{S:out}}
// mapMerge inserts the smaller map into the larger; the second map's values win.
func mapMerge[K comparable,V any](a,b actor.Map[K,V])actor.Map[K,V]{
if actor.MapLen(b)==0{return a}
if actor.MapLen(a)==0{return b}
if actor.MapLen(a)<actor.MapLen(b){out:=actor.NewMapBuilder(b);actor.MapEach(a,func(key K,value V){if _,taken:=out.Get(key);!taken{out.Put(key,value)}});return out.Map()}
out:=actor.NewMapBuilder(a);actor.MapEach(b,func(key K,value V){out.Put(key,value)});return out.Map()}
func listPrepend[T any](l L[T],value T)L[T]{n:=len(l.S);if l.H!=nil&&n<cap(l.S)&&l.H.used.CompareAndSwap(int64(n),int64(n+1)){s:=l.S[:n+1];s[n]=value;return L[T]{s,l.H}};s:=make([]T,n+1,2*n+4);copy(s,l.S);s[n]=value;h:=&lh{};h.used.Store(int64(n+1));return L[T]{s,h}}
func listCons[T any](heads []T,tail L[T])L[T]{for i:=len(heads)-1;i>=0;i--{tail=listPrepend(tail,heads[i])};return tail}
func listConcat[T any](a,b L[T])L[T]{out:=make([]T,len(a.S)+len(b.S));copy(out,b.S);copy(out[len(b.S):],a.S);return L[T]{S:out}}
func listMap[T,R any](ctx *actor.Context,l L[T],f func(*actor.Context,T)R)L[R]{out:=make([]R,len(l.S));for i:=len(l.S)-1;i>=0;i--{out[i]=f(ctx,l.S[i])};return L[R]{S:out}}
func listFilter[T any](ctx *actor.Context,l L[T],f func(*actor.Context,T)bool)L[T]{out:=make([]T,0,len(l.S));for i:=len(l.S)-1;i>=0;i--{if f(ctx,l.S[i]){out=append(out,l.S[i])}};return mk(out)}
func listReduce[T,A any](ctx *actor.Context,l L[T],acc A,f func(*actor.Context,A,T)A)A{for i:=len(l.S)-1;i>=0;i--{acc=f(ctx,acc,l.S[i])};return acc}
func mapPut[K comparable,V any](m actor.Map[K,V],key K,value V)actor.Map[K,V]{return actor.MapPut(m,key,value)}
func mapHas[K comparable,V any](m actor.Map[K,V],key K)bool{_,ok:=actor.MapGet(m,key);return ok}
func mapGet[K comparable,V any](m actor.Map[K,V],key K,fallback V)V{if value,ok:=actor.MapGet(m,key);ok{return value};return fallback}
func mapAt[K comparable,V any](m actor.Map[K,V],key K)V{value,_:=actor.MapGet(m,key);return value}
func lookup[K comparable,V any](ctx *actor.Context,m actor.Map[K,V],key K,where string)V{value,ok:=actor.MapGet(m,key);if !ok{failAt(ctx,where,"map key not found")};return value}

// Failure helpers are never inlined: expanded into their callers they push the
// checked operators and accessors past the Go compiler's inlining budget.
//go:noinline
func failAt(ctx *actor.Context,where,message string){actor.Fail(ctx,where,message)}
// is reports whether a sum type value holds the variant T.
func is[T any](v any)bool{_,ok:=v.(T);return ok}
func at[T any](ctx *actor.Context,l L[T],index int64,where string)T{if index<0||index>=int64(len(l.S)){failAt(ctx,where,"list index out of bounds")};return l.S[len(l.S)-1-int(index)]}

const minInt int64 = -9223372036854775808
const maxInt int64 = 9223372036854775807
// The checked operators keep their failure path out of line so the common
// case is a few instructions the Go compiler can inline at each use.
//go:noinline
func overflow(ctx *actor.Context,where string){failAt(ctx,where,"integer overflow")}
func add(ctx *actor.Context,a,b int64,where string) int64 { r:=a+b;if (r<a)!=(b<0){overflow(ctx,where)};return r }
func sub(ctx *actor.Context,a,b int64,where string) int64 { r:=a-b;if (r>a)!=(b<0){overflow(ctx,where)};return r }
func neg(ctx *actor.Context,a int64,where string) int64 {if a==minInt{failAt(ctx,where,"integer overflow")};return -a}
func mul(ctx *actor.Context,a,b int64,where string) int64 {if int64(int32(a))==a&&int64(int32(b))==b{return a*b};return mulWide(ctx,a,b,where)}
func mulWide(ctx *actor.Context,a,b int64,where string) int64 {if a==0||b==0{return 0};if (a==minInt&&b == -1)||(b==minInt&&a == -1){failAt(ctx,where,"integer overflow")};r:=a*b;if r/b!=a{failAt(ctx,where,"integer overflow")};return r}
func div(ctx *actor.Context,a,b int64,where string) int64 {if b==0{failAt(ctx,where,"division by zero")};if a==minInt&&b == -1{failAt(ctx,where,"integer overflow")};return a/b}
func mod(ctx *actor.Context,a,b int64,where string) int64 {if b==0{failAt(ctx,where,"division by zero")};return a%b}
func fdiv(ctx *actor.Context,a,b float64,where string) float64 {if b==0{failAt(ctx,where,"division by zero")};return a/b}

func strReverse(s string)string{if simple(s){b:=[]byte(s);slices.Reverse(b);return string(b)};parts:=graphemes(s);slices.Reverse(parts);return strings.Join(parts,"")}
func okOf[T any](v T)Tresult[T,string]{return Tresult[T,string](Tresult_c0[T,string]{v})}
func errOf[T any](reason string)Tresult[T,string]{return Tresult[T,string](Tresult_c1[T,string]{reason})}
func done(err error)Tresult[struct{},string]{if err!=nil{return errOf[struct{}](err.Error())};return okOf(struct{}{})}
func someOf[T any](v T)Toption[T]{return Toption[T](Toption_c1[T]{v})}
func noneOf[T any]()Toption[T]{return Toption[T](Toption_c0[T]{})}
func serverReply[R any](r actor.Reply[R])Tresult[R,string]{if r.Error!=""{return errOf[R](r.Error)};return okOf(r.Value)}
func floatParse(s string)Tresult[float64,string]{v,err:=strconv.ParseFloat(s,64);if err!=nil||math.IsInf(v,0)||math.IsNaN(v){return errOf[float64](strconv.Quote(s)+" is not a float")};return okOf(v)}
func fileWrite(path,content string)Tresult[struct{},string]{return done(os.WriteFile(path,[]byte(content),0644))}
func fileAppend(path,content string)Tresult[struct{},string]{f,err:=os.OpenFile(path,os.O_APPEND|os.O_CREATE|os.O_WRONLY,0644);if err!=nil{return done(err)};_,err=f.WriteString(content);if closing:=f.Close();err==nil{err=closing};return done(err)}
func fileRemove(path string)Tresult[struct{},string]{return done(os.Remove(path))}
func fileList(path string)Tresult[L[string],string]{entries,err:=os.ReadDir(path);if err!=nil{return errOf[L[string]](err.Error())};names:=make([]string,len(entries));for i,entry:=range entries{names[i]=entry.Name()};return okOf(mk(names))}
func fileExists(path string)bool{_,err:=os.Stat(path);return err==nil}
func systemEnv(name string)Toption[string]{if v,ok:=os.LookupEnv(name);ok{return someOf(v)};return noneOf[string]()}
func ioWrite(s string){fmt.Print(s)}
func floatFrom(v int64)float64{return float64(v)}
func floatWhole(ctx *actor.Context,v float64,where string)int64{if !(v>= -9223372036854775808.0&&v<9223372036854775808.0){failAt(ctx,where,"float out of integer range")};return int64(v)}
func floatTrunc(ctx *actor.Context,v float64,where string)int64{return floatWhole(ctx,math.Trunc(v),where)}
func floatRound(ctx *actor.Context,v float64,where string)int64{return floatWhole(ctx,math.Round(v),where)}
// floatInspect is the text of a float in inspect: plain digits from 1 up to
// 1.0e16, and the shorter form outside that range.
func floatNeg(f float64)float64{return -f}
func floatInspect(f float64)string{m:=math.Abs(f);if m!=0&&m<1{return floatString(f)};if m>=1e16{return floatString(f)};t:=strconv.FormatFloat(f,'f',-1,64);if !strings.Contains(t,"."){t+=".0"};return t}
// floatString is the text of a float in interpolation, to_string and
// Float.to_string: the shortest digits that read back as the same value,
// written in exponent form whenever that is strictly shorter than the plain
// form or the value is at least 2**53, beyond which floats cannot hold every
// whole number, as Elixir does. 1000.0 is "1.0e3" and 100.0 stays "100.0".
func floatString(f float64)string{
if math.IsNaN(f)||math.IsInf(f,0){return strconv.FormatFloat(f,'f',-1,64)}
// One conversion gives the shortest digits and the exponent; both forms
// are laid out from those.
var space [32]byte
t:=strconv.AppendFloat(space[:0],f,'e',-1,64)
negative:=t[0]=='-';if negative{t=t[1:]}
split:=len(t)-1;for t[split]!='e'{split--}
exponent:=0;for _,c:=range t[split+2:]{exponent=exponent*10+int(c-'0')};if t[split+1]=='-'{exponent=-exponent}
digits:=make([]byte,0,20);digits=append(digits,t[0]);if split>1{digits=append(digits,t[2:split]...)}
n:=len(digits)
scientific:=n+1;if n==1{scientific=3};scientific+=1+len(t)-split-2;if exponent<0{scientific++};for k:=split+2;k<len(t)-1&&t[k]=='0';k++{scientific--}
plain:=0
switch{case exponent<0:plain=1-exponent+n;case n<=exponent+1:plain=exponent+3;default:plain=n+1}
out:=make([]byte,0,max(scientific,plain)+1)
if negative{out=append(out,'-')}
if scientific<plain||math.Abs(f)>=1<<53{
out=append(out,digits[0],'.');if n==1{out=append(out,'0')}else{out=append(out,digits[1:]...)}
out=append(out,'e');return string(strconv.AppendInt(out,int64(exponent),10))}
switch{
case exponent<0:out=append(out,'0','.');for k:=0;k< -exponent-1;k++{out=append(out,'0')};out=append(out,digits...)
case n<=exponent+1:out=append(out,digits...);for k:=n;k<exponent+1;k++{out=append(out,'0')};out=append(out,'.','0')
default:out=append(out,digits[:exponent+1]...);out=append(out,'.');out=append(out,digits[exponent+1:]...)}
return string(out)}
`

// dynamicEquality is emitted only for programs that compare structs, sum
// types or values of a type variable; every other comparison is generated for
// its exact type and needs no reflection.
const dynamicEquality = `
// Structural equality for values whose type is only known at run time:
// structs, sum types and values of a type variable. Everything else is
// compared by code generated for its exact type.
func equal(a,b any)bool{return same(reflect.ValueOf(a),reflect.ValueOf(b))}
func same(a,b reflect.Value)bool{
	// An unset sum type value has no variant and equals only another unset one.
	if !a.IsValid()||!b.IsValid(){return a.IsValid()==b.IsValid()}
	if a.Type()!=b.Type(){return false}
	// A map's internal shape depends on its history, so it compares itself.
	if m,ok:=a.Interface().(interface{EqualWith(any,func(any,any)bool)bool});ok{return m.EqualWith(b.Interface(),equal)}
	switch a.Kind(){
	case reflect.Interface:
		return same(a.Elem(),b.Elem())
	case reflect.Slice:
		if a.Len()!=b.Len(){return false}
		for i:=0;i<a.Len();i++{if !same(a.Index(i),b.Index(i)){return false}}
		return true
	case reflect.Struct:
		// A list is its elements; the claim counter is bookkeeping.
		if a.NumField()==2&&a.Type().Field(1).Type==reflect.TypeOf((*lh)(nil)){return same(a.Field(0),b.Field(0))}
		// Markup's last field, P, is bookkeeping too.
		n:=a.NumField();if n>0&&a.Type().Field(n-1).Name=="P"{n--}
		for i:=0;i<n;i++{if !same(a.Field(i),b.Field(i)){return false}}
		return true
	case reflect.Int64:
		return a.Int()==b.Int()
	case reflect.Float64:
		return a.Float()==b.Float()
	case reflect.Bool:
		return a.Bool()==b.Bool()
	case reflect.String:
		return a.String()==b.String()
	}
	return false
}
`
