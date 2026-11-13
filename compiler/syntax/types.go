package syntax

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// variantRef locates one variant of a sum type.
type variantRef struct {
	decl  *ast.TypeDecl
	index int
}

// BuiltinTypes are the sum types every program has: option and result. Their
// constructors are written unqualified: none, some(x), ok(x), error(x).
func BuiltinTypes() []ast.TypeDecl {
	return append(CalendarTypes(), []ast.TypeDecl{
		{Kind: "sum", Name: "option", Local: "option", Params: []string{"t"}, Variants: []ast.Variant{{Name: "none"}, {Name: "some", Fields: []ast.Parameter{{Name: "value", Type: "t"}}}}},
		{Kind: "sum", Name: "result", Local: "result", Params: []string{"t", "e"}, Variants: []ast.Variant{{Name: "ok", Fields: []ast.Parameter{{Name: "value", Type: "t"}}}, {Name: "error", Fields: []ast.Parameter{{Name: "reason", Type: "e"}}}}},
		// step tells Enum.reduce_while whether to continue with a new
		// accumulator or stop with a final one.
		// JSON is any JSON document. Its constructors are qualified: JSON.null,
		// JSON.string("x"), JSON.list([...]), JSON.object(%{...}).
		// What a port sends its owner: a line the program wrote, then its
		// exit status.
		{Kind: "sum", Name: "PortEvent", Local: "PortEvent", Variants: []ast.Variant{
			{Name: "data", Fields: []ast.Parameter{{Name: "text", Type: "string"}}},
			{Name: "exit", Fields: []ast.Parameter{{Name: "status", Type: "integer"}}},
		}},
		// What an active TCP socket sends its controlling process: a packet
		// of data, the end of the connection, or a failure.
		{Kind: "sum", Name: "TCP.Event", Local: "TCP.Event", Variants: []ast.Variant{
			{Name: "data", Fields: []ast.Parameter{{Name: "text", Type: "string"}}},
			{Name: "closed"},
			{Name: "error", Fields: []ast.Parameter{{Name: "reason", Type: "string"}}},
		}},
		// What a WebSocket gives: a text or binary message, the closing
		// handshake with its code and reason, or a failure that ended it.
		{Kind: "sum", Name: "WebSocket.Event", Local: "WebSocket.Event", Variants: []ast.Variant{
			{Name: "text", Fields: []ast.Parameter{{Name: "text", Type: "string"}}},
			{Name: "binary", Fields: []ast.Parameter{{Name: "data", Type: "string"}}},
			{Name: "closed", Fields: []ast.Parameter{{Name: "code", Type: "integer"}, {Name: "reason", Type: "string"}}},
			{Name: "error", Fields: []ast.Parameter{{Name: "reason", Type: "string"}}},
		}},
		// What an active UDP socket sends: a datagram with the address it
		// came from, or a failure.
		{Kind: "sum", Name: "UDP.Event", Local: "UDP.Event", Variants: []ast.Variant{
			{Name: "datagram", Fields: []ast.Parameter{{Name: "from", Type: "string"}, {Name: "text", Type: "string"}}},
			{Name: "error", Fields: []ast.Parameter{{Name: "reason", Type: "string"}}},
		}},
		{Kind: "sum", Name: "JSON", Local: "JSON", Variants: []ast.Variant{
			{Name: "null"},
			{Name: "boolean", Fields: []ast.Parameter{{Name: "value", Type: "boolean"}}},
			{Name: "integer", Fields: []ast.Parameter{{Name: "value", Type: "integer"}}},
			{Name: "float", Fields: []ast.Parameter{{Name: "value", Type: "float"}}},
			{Name: "string", Fields: []ast.Parameter{{Name: "value", Type: "string"}}},
			{Name: "list", Fields: []ast.Parameter{{Name: "items", Type: "list[JSON]"}}},
			{Name: "object", Fields: []ast.Parameter{{Name: "fields", Type: "map[string,JSON]"}}},
		}},
		{Kind: "sum", Name: "step", Local: "step", Params: []string{"t"}, Variants: []ast.Variant{{Name: "cont", Fields: []ast.Parameter{{Name: "value", Type: "t"}}}, {Name: "halt", Fields: []ast.Parameter{{Name: "value", Type: "t"}}}}},
	}...)
}

func plural(n int, word string) string {
	if n == 1 {
		return fmt.Sprintf("%d %s", n, word)
	}
	return fmt.Sprintf("%d %ss", n, word)
}

func set(names []string) map[string]bool {
	out := map[string]bool{}
	for _, name := range names {
		out[name] = true
	}
	return out
}

// declare registers the program's types and checks each declaration.
func (c *checker) declare(p *ast.Program) error {
	c.types = map[string]*ast.TypeDecl{}
	c.variants = map[string]variantRef{}
	builtin := BuiltinTypes()
	for i := range builtin {
		c.types[builtin[i].Name] = &builtin[i]
		for j, variant := range builtin[i].Variants {
			c.variants[Constructor(builtin[i], variant.Name)] = variantRef{&builtin[i], j}
		}
	}
	located := func(decl *ast.TypeDecl, line, col int, format string, args ...any) error {
		err := diagnostic(line, col, format, args...)
		if decl.Source != "" {
			return fmt.Errorf("%s:%w", decl.Source, err)
		}
		return err
	}
	for i := range p.Types {
		decl := &p.Types[i]
		if c.types[decl.Name] != nil {
			return located(decl, decl.Line, decl.Column, "duplicate type %s", decl.Local)
		}
		if ReservedModule(decl.Local) {
			return located(decl, decl.Line, decl.Column, "type name %s is reserved for the builtin %s functions", decl.Local, decl.Local)
		}
		c.types[decl.Name] = decl
		for j, variant := range decl.Variants {
			c.variants[decl.Name+"."+variant.Name] = variantRef{decl, j}
		}
	}
	for i := range p.Types {
		decl := &p.Types[i]
		fields := append([]ast.Parameter{}, decl.Fields...)
		for _, variant := range decl.Variants {
			fields = append(fields, variant.Fields...)
		}
		for _, field := range fields {
			if message := c.wellFormed(field.Type, set(decl.Params)); message != "" {
				return located(decl, field.Line, field.Column, "%s", message)
			}
		}
		if decl.Kind == "extern" && len(decl.Params) > 0 {
			return located(decl, decl.Line, decl.Column, "extern types take no type parameters")
		}
		if decl.Kind == "struct" && c.inline(decl.Name, decl.Name, map[string]bool{}) {
			return located(decl, decl.Line, decl.Column, "struct %s contains itself; put the recursion behind a list, option or sum type", decl.Local)
		}
	}
	return nil
}

// inline reports whether a value of the struct `from` stores a value of the
// struct `target` directly, which no finite value could satisfy.
func (c *checker) inline(from, target string, visited map[string]bool) bool {
	decl := c.types[from]
	if decl == nil || decl.Kind != "struct" || visited[from] {
		return false
	}
	visited[from] = true
	var reaches func(t string) bool
	reaches = func(t string) bool {
		head, args := ast.Split(t)
		if head == "tuple" {
			for _, arg := range args {
				if reaches(arg) {
					return true
				}
			}
			return false
		}
		if other := c.types[head]; other != nil && other.Kind == "struct" {
			if head == target || c.inline(head, target, visited) {
				return true
			}
			for _, arg := range args {
				if reaches(arg) {
					return true
				}
			}
		}
		return false
	}
	for _, field := range decl.Fields {
		if reaches(field.Type) {
			return true
		}
	}
	return false
}

// wellFormed checks that a type names only declared types, with the right
// number of arguments, and type variables that are in scope. It returns a
// message, or "" when the type is fine.
func (c checker) wellFormed(t string, vars map[string]bool) string {
	head, args := ast.Split(t)
	if ast.TypeVariable(head) {
		if !vars[head] {
			return fmt.Sprintf("unknown type %q", head)
		}
		return ""
	}
	for _, arg := range args {
		if message := c.wellFormed(arg, vars); message != "" {
			return message
		}
	}
	if decl := c.types[head]; decl != nil {
		if len(args) != len(decl.Params) {
			return fmt.Sprintf("%s requires %s", decl.Local, plural(len(decl.Params), "type argument"))
		}
		return ""
	}
	if _, _, named := ast.Named(t); named {
		return fmt.Sprintf("unknown type %q", head)
	}
	if head == "pid" || head == "supervisor" || head == "server" {
		for _, arg := range args {
			if !c.sendable(arg) {
				return "mailbox messages cannot contain functions"
			}
		}
	}
	return ""
}

// contains reports whether a value of type t holds, at any depth, a value
// whose type satisfies the predicate.
func (c checker) contains(t string, predicate func(string) bool, visited map[string]bool) bool {
	if predicate(t) {
		return true
	}
	head, args := ast.Split(t)
	if head == "pid" || head == "supervisor" || head == "server" || head == "task" || head == "agent" || head == "registry" || head == "dynamic_supervisor" {
		return false
	}
	for _, arg := range args {
		if c.contains(arg, predicate, visited) {
			return true
		}
	}
	decl := c.types[head]
	if decl == nil || visited[t] || len(args) != len(decl.Params) {
		return false
	}
	visited[t] = true
	variants := len(decl.Variants)
	if decl.Kind == "struct" {
		variants = 1
	}
	for i := 0; i < variants; i++ {
		_, fields := c.fieldTypes(t, i)
		for _, field := range fields {
			if c.contains(field, predicate, visited) {
				return true
			}
		}
	}
	return false
}
func isFunction(t string) bool { _, _, ok := ast.FunctionParts(t); return ok }

// opaque reports a handle to a Go value. Go values may be mutable, so handles
// are neither compared nor sent between processes.
func (c checker) opaque(t string) bool {
	decl := c.types[t]
	return decl != nil && decl.Kind == "extern"
}

// sendable types hold no functions and no undetermined type variables.
func (c checker) sendable(t string) bool {
	return !c.contains(t, func(t string) bool {
		head, _ := ast.Split(t)
		return isFunction(t) || ast.TypeVariable(t) || c.opaque(t) || head == "stream"
	}, map[string]bool{})
}

// unwired names the first part of a type that has no form on the wire
// between nodes, or "" when all of it can cross.
func (c checker) unwired(t string) string {
	found := ""
	c.contains(t, func(part string) bool {
		head, _ := ast.Split(part)
		blocked := isFunction(part) || ast.TypeVariable(part) || c.opaque(part) || head == "stream" || head == "regex" || head == "port" || head == "task" || head == "agent" || head == "server" || head == "supervisor" || head == "registry" || head == "dynamic_supervisor" || head == "socket" || head == "http_server" || head == "websocket" || head == "generator" || head == "file" || head == "disk_store"
		if blocked && found == "" {
			found = part
		}
		return blocked
	}, map[string]bool{})
	return found
}

// unread returns the first part of a type that cannot be read from JSON,
// or "" when every part can: a function, a capability, or a map whose keys
// JSON's text keys cannot give back.
func (c checker) unread(t string) string {
	found := ""
	c.contains(t, func(part string) bool {
		head, args := ast.Split(part)
		blocked := isFunction(part) || ast.TypeVariable(part) || c.opaque(part)
		switch head {
		case "stream", "regex", "port", "task", "agent", "server", "supervisor", "registry", "dynamic_supervisor", "socket", "http_server", "websocket", "generator", "file", "disk_store", "pid":
			blocked = true
		case "map":
			blocked = blocked || len(args) == 2 && strings.HasPrefix(args[0], "tuple[")
		}
		if blocked && found == "" {
			found = part
		}
		return blocked
	}, map[string]bool{})
	return found
}

// equatable types hold no functions, capabilities or type variables.
func (c checker) equatable(t string) bool {
	return ast.Equatable(t) && !c.contains(t, func(t string) bool {
		head, _ := ast.Split(t)
		return isFunction(t) || ast.TypeVariable(t) || c.opaque(t) || head == "pid" || head == "supervisor" || head == "server" || head == "stream" || head == "regex" || head == "task" || head == "agent" || head == "registry" || head == "dynamic_supervisor" || head == "socket" || head == "http_server" || head == "websocket" || head == "generator" || head == "file" || head == "disk_store"
	}, map[string]bool{})
}

// unify matches a type that may mention the given type variables against a
// concrete type, extending the bindings. Variables outside vars are constants.
func unify(pattern, actual string, vars map[string]bool, bindings map[string]string) bool {
	head, args := ast.Split(pattern)
	if vars[head] && len(args) == 0 {
		if bound, ok := bindings[head]; ok {
			return bound == actual
		}
		bindings[head] = actual
		return true
	}
	otherHead, otherArgs := ast.Split(actual)
	if head != otherHead || len(args) != len(otherArgs) {
		return false
	}
	for i := range args {
		if !unify(args[i], otherArgs[i], vars, bindings) {
			return false
		}
	}
	return true
}

// resolved reports whether every one of vars that t mentions is bound.
func resolved(t string, vars map[string]bool, bindings map[string]string) bool {
	for _, name := range ast.TypeVariables(t, map[string]bool{}, nil) {
		if vars[name] {
			if _, ok := bindings[name]; !ok {
				return false
			}
		}
	}
	return true
}

// instantiate substitutes only the variables in vars.
func instantiate(t string, vars map[string]bool, bindings map[string]string) string {
	scoped := map[string]string{}
	for name, bound := range bindings {
		if vars[name] {
			scoped[name] = bound
		}
	}
	return ast.Substitute(t, scoped)
}

// arguments checks call arguments against parameter types that may mention
// vars, inferring bindings from an expected result type and from each
// argument in turn.
func (c checker) arguments(e *ast.Expr, scope map[string]string, params []string, vars map[string]bool, bindings map[string]string, what string) error {
	for i, arg := range e.Args {
		expected := ""
		if resolved(params[i], vars, bindings) {
			expected = instantiate(params[i], vars, bindings)
		}
		var t string
		var err error
		if arg.Kind == "lambda" || arg.Kind == "capture" {
			t, err = c.lambdaArgument(arg, scope, params[i], vars, bindings)
		} else {
			t, err = c.expr(arg, scope, expected)
		}
		if err != nil {
			return err
		}
		if !unify(params[i], t, vars, bindings) {
			return diagnostic(arg.Line, arg.Column, "argument type mismatch for %s: expected %s, found %s", what, instantiate(params[i], vars, bindings), t)
		}
	}
	return nil
}

// display names a variant the way source writes it.
func display(ref variantRef) string {
	if ref.decl.Name == ref.decl.Local {
		return Constructor(*ref.decl, ref.decl.Variants[ref.index].Name)
	}
	return ref.decl.Local + "." + ref.decl.Variants[ref.index].Name
}

// constructor resolves a name to a variant. When the name is Type.variant for
// a known sum type without that variant, it returns a message.
func (c checker) constructor(name string) (variantRef, string, bool) {
	if ref, ok := c.variants[name]; ok {
		return ref, "", true
	}
	if index := strings.LastIndex(name, "."); index > 0 {
		if decl := c.types[name[:index]]; decl != nil && decl.Kind == "sum" {
			return variantRef{}, fmt.Sprintf("%s has no variant %s", decl.Local, name[index+1:]), false
		}
	}
	return variantRef{}, "", false
}

// construct types the application of a variant to its arguments.
func (c checker) construct(e *ast.Expr, ref variantRef, scope map[string]string, want string) (string, error) {
	decl := ref.decl
	fields := decl.Variants[ref.index].Fields
	if len(e.Args) != len(fields) {
		return "", diagnostic(e.Line, e.Column, "%s requires %s", display(ref), plural(len(fields), "argument"))
	}
	vars, bindings := set(decl.Params), map[string]string{}
	if head, args := ast.Split(want); head == decl.Name && len(args) == len(decl.Params) {
		for i, param := range decl.Params {
			if args[i] != "?" {
				bindings[param] = args[i]
			}
		}
	}
	params := []string{}
	for _, field := range fields {
		params = append(params, field.Type)
	}
	if err := c.arguments(e, scope, params, vars, bindings, display(ref)); err != nil {
		return "", err
	}
	args := []string{}
	for _, param := range decl.Params {
		bound, ok := bindings[param]
		if !ok && c.statements[e] {
			// A value written as a statement is discarded, as the last line
			// of a case arm whose case is a statement is: what it would have
			// held does not matter.
			bound, ok = "tuple[]", true
		}
		if !ok {
			if c.hintFor == e {
				c.recordHint(decl, bindings)
			}
			return "", diagnostic(e.Line, e.Column, "cannot infer the type of %s here; annotate the binding it is assigned to", display(ref))
		}
		args = append(args, bound)
	}
	e.Kind, e.Name, e.Op = "variant", decl.Name, strconv.Itoa(ref.index)
	return ast.Join(decl.Name, args), nil
}

// structLiteral types %Name{field: value} and %Name{base | field: value}.
func (c checker) structLiteral(e *ast.Expr, scope map[string]string, want string) (string, error) {
	fail := func(format string, args ...any) (string, error) {
		return "", diagnostic(e.Line, e.Column, format, args...)
	}
	decl := c.types[e.Name]
	if decl == nil || decl.Kind != "struct" {
		return fail("unknown type %q", e.Name)
	}
	vars, bindings := set(decl.Params), map[string]string{}
	bind := func(t string) bool {
		head, args := ast.Split(t)
		if head != decl.Name || len(args) != len(decl.Params) {
			return false
		}
		for i, param := range decl.Params {
			bindings[param] = args[i]
		}
		return true
	}
	if e.Left != nil {
		base, err := c.expr(e.Left, scope)
		if err != nil {
			return "", err
		}
		if !bind(base) {
			return fail("%s update requires a %s value, found %s", decl.Local, decl.Local, base)
		}
	} else {
		bind(want)
	}
	if e.Left == nil {
		// Fields left out take their defaults.
		given := map[string]bool{}
		for _, label := range e.Labels {
			given[label] = true
		}
		for _, field := range decl.Fields {
			if !given[field.Name] && field.Default != nil {
				e.Labels = append(e.Labels, field.Name)
				e.Args = append(e.Args, cloneExpr(field.Default))
			}
		}
	}
	seen := map[string]bool{}
	for i, label := range e.Labels {
		index := -1
		for j, field := range decl.Fields {
			if field.Name == label {
				index = j
			}
		}
		if index < 0 {
			return fail("%s has no field %s", decl.Local, label)
		}
		if seen[label] {
			return fail("duplicate field %s", label)
		}
		seen[label] = true
		field := decl.Fields[index].Type
		expected := ""
		if resolved(field, vars, bindings) {
			expected = instantiate(field, vars, bindings)
		}
		t, err := c.expr(e.Args[i], scope, expected)
		if err != nil {
			return "", err
		}
		if !unify(field, t, vars, bindings) {
			return "", diagnostic(e.Args[i].Line, e.Args[i].Column, "field %s: expected %s, found %s", label, instantiate(field, vars, bindings), t)
		}
		e.TypeArgs = append(e.TypeArgs, strconv.Itoa(index))
	}
	if e.Left == nil {
		for _, field := range decl.Fields {
			if !seen[field.Name] {
				return fail("missing field %s", field.Name)
			}
		}
	}
	args := []string{}
	for _, param := range decl.Params {
		bound, ok := bindings[param]
		if !ok {
			return fail("cannot infer type parameter %s of %s; annotate the binding it is assigned to", param, decl.Local)
		}
		args = append(args, bound)
	}
	return ast.Join(decl.Name, args), nil
}

// fieldTypes returns a declared type's field types for the given variant
// (ignored for structs) with its type arguments applied.
func (c checker) fieldTypes(t string, variant int) (*ast.TypeDecl, []string) {
	head, args := ast.Split(t)
	decl := c.types[head]
	if decl == nil || len(args) != len(decl.Params) {
		return nil, nil
	}
	bindings := map[string]string{}
	for i, param := range decl.Params {
		bindings[param] = args[i]
	}
	fields := decl.Fields
	if decl.Kind == "sum" {
		fields = decl.Variants[variant].Fields
	}
	if decl.Kind == "extern" {
		return nil, nil
	}
	out := make([]string, len(fields))
	for i, field := range fields {
		out[i] = ast.Substitute(field.Type, bindings)
	}
	return decl, out
}

// Generic returns a function's type variables in order of first appearance.
func Generic(f *ast.Function) []string { return generic(f) }
func generic(f *ast.Function) []string {
	seen := map[string]bool{}
	var out []string
	for _, param := range f.Params {
		out = ast.TypeVariables(param.Type, seen, out)
	}
	return out
}

// serverBuiltin types the Server operations: a process that owns a state and
// answers typed requests.
func (c checker) serverBuiltin(e *ast.Expr, scope map[string]string) (string, error) {
	fail := func(s string) (string, error) { return "", diagnostic(e.Line, e.Column, "%s", s) }
	counts := map[string]int{"Server.start": 2, "Server.start_supervised": 4, "Server.call": 3, "Server.cast": 2, "Server.stop": 1, "Server.alive": 1, "Server.await": 2, "Server.restarts": 1}
	count, ok := counts[e.Name]
	if !ok {
		return fail("unknown runtime operation " + e.Name)
	}
	if len(e.Args) != count {
		return fail(fmt.Sprintf("%s requires %s", e.Name, plural(count, "argument")))
	}
	if e.Name == "Server.start" || e.Name == "Server.start_supervised" {
		for _, limit := range e.Args[2:] {
			if _, err := c.expr(limit, scope, "integer"); err != nil {
				return "", err
			}
		}
		handler, err := c.expr(e.Args[1], scope)
		if err != nil {
			return "", err
		}
		params, result, ok := ast.FunctionParts(handler)
		parts, tuple := ast.TupleElements(result)
		if !ok || !tuple || len(params) != 2 || len(parts) != 2 || parts[0] != params[0] {
			return fail("server handler must be fn[State,Request,tuple[State,Reply]]")
		}
		if !c.sendable(params[1]) || !c.sendable(parts[1]) {
			return fail("server requests and replies cannot contain functions")
		}
		if _, err = c.expr(e.Args[0], scope, params[0]); err != nil {
			return "", err
		}
		return "server[" + params[1] + "," + parts[1] + "]", nil
	}
	target, err := c.expr(e.Args[0], scope)
	if err != nil {
		return "", err
	}
	head, args := ast.Split(target)
	if head != "server" {
		return fail(e.Name + " requires a server, found " + target)
	}
	switch e.Name {
	case "Server.call":
		if _, err = c.expr(e.Args[1], scope, args[0]); err != nil {
			return "", err
		}
		if _, err = c.expr(e.Args[2], scope, "integer"); err != nil {
			return "", err
		}
		return "result[" + args[1] + ",string]", nil
	case "Server.cast":
		if _, err = c.expr(e.Args[1], scope, args[0]); err != nil {
			return "", err
		}
	case "Server.await":
		if _, err = c.expr(e.Args[1], scope, "integer"); err != nil {
			return "", err
		}
		return "tuple[boolean,string]", nil
	case "Server.restarts":
		return "integer", nil
	}
	return "boolean", nil
}

// Constructor is how source writes a variant of a builtin sum type: bare for
// option, result and step (some, ok, cont), qualified for JSON (JSON.null).
func Constructor(decl ast.TypeDecl, variant string) string {
	if decl.Name[:1] == strings.ToLower(decl.Name[:1]) {
		return variant
	}
	return decl.Name + "." + variant
}

// recordHint adds what a constructor showed of its type, with "?" for the
// parameters it left open, to the hint of the if or case value it ends.
func (c checker) recordHint(decl *ast.TypeDecl, bindings map[string]string) {
	if c.hint == nil || c.yield == nil || *c.yield != "" || c.hintFor == nil {
		return
	}
	known := make([]string, len(decl.Params))
	for i, param := range decl.Params {
		known[i] = "?"
		if bound, ok := bindings[param]; ok {
			known[i] = bound
		}
	}
	if head, previous := ast.Split(*c.hint); head == decl.Name && len(previous) == len(known) {
		for i := range known {
			if known[i] == "?" {
				known[i] = previous[i]
			}
		}
	} else if *c.hint != "" {
		return
	}
	*c.hint = ast.Join(decl.Name, known)
}
