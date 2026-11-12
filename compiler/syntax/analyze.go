package syntax

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

func diagnostic(line, col int, format string, args ...any) error {
	return fmt.Errorf("%d:%d: %s", line, col, fmt.Sprintf(format, args...))
}
func validType(t string) bool      { return ast.ValidType(t) }
func Analyze(p *ast.Program) error { return analyze(p) }
func analyze(p *ast.Program) (result error) {
	source := ""
	defer func() {
		if result != nil && source != "" && !strings.HasPrefix(result.Error(), source+":") {
			result = fmt.Errorf("%s:%w", source, result)
		}
	}()
	functions := map[string]*ast.Function{}
	for i := range p.Functions {
		f := &p.Functions[i]
		source = f.Source
		if _, ok := functions[f.Name]; ok {
			return diagnostic(f.Line, f.Column, "duplicate function %q", f.Name)
		}
		if f.Extern != "" {
			if functionLocalName(f) == "main" {
				return diagnostic(f.Line, f.Column, "main cannot be extern")
			}
			if !bindingName(functionLocalName(f)) {
				return diagnostic(f.Line, f.Column, "extern requires a valid name")
			}
			if len(generic(f)) > 0 {
				return diagnostic(f.Line, f.Column, "extern functions cannot use type variables")
			}
		} else if f.Name == "main" {
			if len(f.Params) != 0 || f.Type != "void" {
				return diagnostic(f.Line, f.Column, "main must have zero parameters and no return annotation")
			}
		} else if f.Test != "" || f.Setup {
			// Declared by test and setup blocks; nothing to validate.
		} else if name := functionLocalName(f); !bindingName(strings.TrimRight(name, "?!")) || strings.Count(name, "?")+strings.Count(name, "!") > 1 {
			if memberName(name) {
				return diagnostic(f.Line, f.Column, "%s is reserved for a builtin and cannot name a function", name)
			}
			return diagnostic(f.Line, f.Column, "%q is not a valid function name", name)
		} else if !validType(f.Type) {
			return diagnostic(f.Line, f.Column, "%s returns %s, which is not a valid type", name, f.Type)
		}
		functions[f.Name] = f
	}
	// A test file has tests in place of main.
	tests := false
	for i := range p.Functions {
		tests = tests || p.Functions[i].Test != ""
	}
	if main := functions["main"]; main != nil && tests {
		source = main.Source
		return diagnostic(main.Line, main.Column, "a module with tests cannot define main; the test runner is the entry point")
	}
	if functions["main"] == nil && !tests {
		source = p.Source
		return diagnostic(1, 1, "missing main/0")
	}
	c := checker{functions: functions, statements: map[*ast.Expr]bool{}, needs: map[string]map[string]bool{}, uses: &[]instantiation{}, counter: new(int)}
	if where, err := c.protocols(p); err != nil {
		source = where
		return err
	}
	source = ""
	if err := c.declare(p); err != nil {
		return err
	}
	if tests {
		source = p.Source
		if err := c.contexts(p); err != nil {
			return err
		}
		source = ""
	}
	for i := range p.Functions {
		f := &p.Functions[i]
		source = f.Source
		scope := map[string]string{}
		c.vars = set(generic(f))
		c.current = f.Name
		for _, name := range ast.TypeVariables(f.Type, map[string]bool{}, nil) {
			if !c.vars[name] {
				return diagnostic(f.Line, f.Column, "type variable %s does not appear in a parameter of %s", name, functionLocalName(f))
			}
		}
		if f.Type != "void" {
			if message := c.wellFormed(f.Type, c.vars); message != "" {
				return diagnostic(f.Line, f.Column, "%s", message)
			}
		}
		for _, param := range f.Params {
			if (!generatedName(param.Name) && !bindingName(param.Name)) || !validType(param.Type) {
				return diagnostic(param.Line, param.Column, "invalid parameter name or type")
			}
			if message := c.wellFormed(param.Type, c.vars); message != "" {
				return diagnostic(param.Line, param.Column, "%s", message)
			}
			if _, ok := scope[param.Name]; ok {
				return diagnostic(param.Line, param.Column, "duplicate parameter %q", param.Name)
			}
			scope[param.Name] = param.Type
		}
		if f.Extern != "" {
			continue
		}
		if f.Type != "void" {
			implicitReturns(f.Body)
		}
		returns, err := c.block(f.Body, scope, f.Type)
		if err != nil {
			if f.Source != "" {
				return fmt.Errorf("%s:%w", f.Source, err)
			}
			return err
		}
		if f.Type != "void" && !returns {
			return diagnostic(f.Line, f.Column, "function %q must return on every path", f.Name)
		}
	}
	// Equality on a type variable is a requirement on whoever chooses the
	// type. Push each requirement up through generic callers, then check the
	// concrete types.
	for changed := true; changed; {
		changed = false
		for _, use := range *c.uses {
			for i, name := range use.vars {
				if !c.needs[use.callee][name] {
					continue
				}
				for _, outer := range ast.TypeVariables(use.types[i], map[string]bool{}, nil) {
					if !c.needs[use.caller][outer] {
						c.require(use.caller, outer)
						changed = true
					}
				}
			}
		}
	}
	for _, use := range *c.uses {
		for i, name := range use.vars {
			if c.needs[use.callee][name] && !c.comparable(use.types[i]) {
				source = use.source
				return diagnostic(use.line, use.column, "%s needs equality for %s, which %s does not support", functionLocalName(functions[use.callee]), name, use.types[i])
			}
		}
	}
	return nil
}

func (c checker) require(function, variable string) {
	if c.needs[function] == nil {
		c.needs[function] = map[string]bool{}
	}
	c.needs[function][variable] = true
}

// comparable reports whether == is defined for a type, treating type
// variables as comparable: their requirement falls on the caller.
func (c checker) comparable(t string) bool {
	stand := map[string]string{}
	for _, name := range ast.TypeVariables(t, map[string]bool{}, nil) {
		stand[name] = "integer"
	}
	return c.equatable(ast.Substitute(t, stand))
}

// compare checks that == is defined for a type and records the type variables
// of the current function that must support it.
func (c checker) compare(t string) bool {
	if !c.comparable(t) {
		return false
	}
	for _, name := range ast.TypeVariables(t, map[string]bool{}, nil) {
		c.require(c.current, name)
	}
	return true
}

// instantiated records the types chosen for a generic function at one use.
func (c checker) instantiated(e *ast.Expr, callee *ast.Function, names []string) {
	if len(names) > 0 {
		*c.uses = append(*c.uses, instantiation{c.current, callee.Name, c.functions[c.current].Source, names, append([]string{}, e.TypeArgs...), e.Line, e.Column})
	}
}

// checker types one program. statements holds the call expressions used as
// whole statements, the only place a call that returns no value may appear.
type checker struct {
	functions  map[string]*ast.Function
	statements map[*ast.Expr]bool
	types      map[string]*ast.TypeDecl
	variants   map[string]variantRef
	// vars holds the type variables of the function being checked.
	vars map[string]bool
	// yield is set while checking an if or case used as a value; it points at
	// the type its branches produce, empty until the first branch is typed.
	yield *string
	// current names the function being checked. needs records which of each
	// function's type variables are compared for equality, and uses records
	// every instantiation of a generic function, so the requirement can be
	// checked against the types each caller chose.
	current string
	needs   map[string]map[string]bool
	uses    *[]instantiation
	// infer is set while checking fn x -> ... end, whose result type comes
	// from its body: it points at that type, empty until the first return.
	infer *string
	// counter numbers the names generated for pattern parameters.
	counter *int
	// declared holds each protocol function by "Protocol.function", and
	// implementations the functions that implement it, one per type.
	declared        map[string]ast.ProtocolFunction
	implementations map[string][]*ast.Function
}

func (c checker) fresh() int { *c.counter++; return *c.counter }

// undetermined reports a failure to infer a type in a branch of an if or
// case whose result type is still open, which another branch may resolve.
func (c checker) undetermined(err error) bool {
	open := (c.yield != nil && *c.yield == "") || (c.infer != nil && *c.infer == "")
	return open && (strings.Contains(err.Error(), "cannot infer") || strings.Contains(err.Error(), "requires an expected"))
}

// instantiation is one call or reference to a generic function.
type instantiation struct {
	caller, callee, source string
	vars, types            []string
	line, column           int
}

func cloneScope(s map[string]string) map[string]string {
	out := map[string]string{}
	for k, v := range s {
		out[k] = v
	}
	return out
}
func (c checker) block(body []ast.Statement, scope map[string]string, result string) (bool, error) {
	returns := false
	for i := range body {
		s := &body[i]
		if returns {
			return false, diagnostic(s.Line, s.Column, "unreachable statement after return")
		}
		expected := ""
		if s.Kind == "bind" {
			expected = s.Declared
		}
		if s.Kind == "call" {
			c.statements[s.Expr] = true
		}
		if s.Declared != "" {
			if message := c.wellFormed(s.Declared, c.vars); message != "" {
				return false, diagnostic(s.Line, s.Column, "%s", message)
			}
		}
		if s.Kind == "return" && result != "void" {
			expected = result
		}
		if s.Kind == "return" && result == "?" {
			expected = *c.infer
		}
		if s.Kind == "return" && c.yield != nil {
			return false, diagnostic(s.Line, s.Column, "return cannot be used inside an if or case that produces a value")
		}
		if s.Kind == "yield" {
			expected = *c.yield
		}
		typ, err := c.expr(s.Expr, scope, expected)
		if err != nil {
			return false, err
		}
		switch s.Kind {
		case "bind":
			if err := c.checkPattern(s.Pattern, typ, scope); err != nil {
				return false, err
			}
		case "output":
			if typ != "string" {
				return false, diagnostic(s.Line, s.Column, "IO.puts requires a string")
			}
		case "assert":
			if typ != "boolean" {
				return false, diagnostic(s.Line, s.Column, "assert requires boolean or comparison")
			}
		case "call":
			if kind := s.Expr.Kind; kind != "call" && kind != "invoke" && kind != "try" && kind != "for" && kind != "unmatched" {
				return false, diagnostic(s.Line, s.Column, "expected binding or function call")
			}
		case "yield":
			*c.yield = typ
			returns = true
		case "return":
			if result == "?" {
				*c.infer = typ
				returns = true
				break
			}
			if result == "void" || typ != result {
				return false, diagnostic(s.Line, s.Column, "return type %s does not match %s", typ, result)
			}
			returns = true
		case "case":
			if s.Name == "with-else" {
				s.Arms = c.reachable(s.Arms, s.Pattern, typ, scope)
				if len(s.Arms) == 0 {
					return false, diagnostic(s.Line, s.Column, "no else arm of this with handles a %s that does not match its clause", typ)
				}
			}
			covered := false
			allReturn := true
			var deferred []int
			for i, arm := range s.Arms {
				pat := arm.Pattern
				subsumed := false
				for _, previous := range s.Arms[:i] {
					subsumed = subsumed || (previous.Guard == nil && subsumes(previous.Pattern, pat))
				}
				if covered || subsumed {
					return false, diagnostic(pat.Line, pat.Column, "unreachable case branch")
				}
				branch := cloneScope(scope)
				if err := c.checkPattern(pat, typ, branch); err != nil {
					return false, err
				}
				if arm.Guard != nil {
					if _, err := c.expr(arm.Guard, branch, "boolean"); err != nil {
						return false, err
					}
				}
				r, err := c.block(arm.Body, branch, result)
				if err != nil && c.undetermined(err) {
					// This arm's value has no type of its own (none, an empty
					// list); a later arm may settle it.
					deferred = append(deferred, i)
					err, r = nil, true
				}
				if err != nil {
					return false, err
				}
				allReturn = allReturn && r
				covered = c.exhaustive(s.Arms[:i+1], typ)
			}
			for _, i := range deferred {
				branch := cloneScope(scope)
				if err := c.checkPattern(s.Arms[i].Pattern, typ, branch); err != nil {
					return false, err
				}
				r, err := c.block(s.Arms[i].Body, branch, result)
				if err != nil {
					return false, err
				}
				allReturn = allReturn && r
			}
			if s.Name != "with-else" && !c.exhaustive(s.Arms, typ) {
				return false, diagnostic(s.Line, s.Column, "non-exhaustive case: add a catch-all pattern")
			}
			returns = allReturn
		case "if":
			if typ != "boolean" {
				return false, diagnostic(s.Line, s.Column, "if requires boolean condition")
			}
			a, err := c.block(s.Then, cloneScope(scope), result)
			retry := err != nil && c.undetermined(err)
			if err != nil && !retry {
				return false, err
			}
			b, err := c.block(s.Else, cloneScope(scope), result)
			if err != nil {
				return false, err
			}
			if retry {
				// The else branch has settled the type the first one lacked.
				if a, err = c.block(s.Then, cloneScope(scope), result); err != nil {
					return false, err
				}
			}
			returns = returns || (a && b)
		}
	}
	return returns, nil
}
func (c checker) expr(e *ast.Expr, scope map[string]string, expected ...string) (string, error) {
	want := ""
	if len(expected) > 0 {
		want = expected[0]
	}
	fail := func(message string) (string, error) { return "", diagnostic(e.Line, e.Column, "%s", message) }
	switch e.Kind {
	case "closure":
		local := cloneScope(scope)
		parts := []string{}
		for _, param := range e.Params {
			if (!generated(param.Name) && !bindingName(param.Name)) || !validType(param.Type) || c.wellFormed(param.Type, c.vars) != "" {
				return fail("invalid closure parameter")
			}
			if _, exists := local[param.Name]; exists {
				return fail("closure parameter shadows an existing binding: " + param.Name)
			}
			local[param.Name] = param.Type
			parts = append(parts, param.Type)
		}
		if message := c.wellFormed(e.ReturnType, c.vars); message != "" {
			return fail(message)
		}
		implicitReturns(e.Body)
		inner := c
		inner.yield = nil
		returns, err := inner.block(e.Body, local, e.ReturnType)
		if err != nil {
			return "", err
		}
		if !returns {
			return fail("closure must return on every path")
		}
		parts = append(parts, e.ReturnType)
		e.Type = "fn[" + strings.Join(parts, ",") + "]"
	case "try", "for", "unmatched", "sigil":
		t, err := c.control(e, scope, want)
		if err != nil {
			return "", err
		}
		e.Type = t
	case "lambda", "capture":
		params, result, ok := ast.FunctionParts(want)
		if !ok {
			return fail("cannot infer the parameter types of this function here; write fn(name: type): type do ... end, or pass it where a function type is expected")
		}
		t, err := c.lambda(e, scope, params, result)
		if err != nil {
			return "", err
		}
		e.Type = t
	case "range":
		for _, bound := range append([]*ast.Expr{e.Left, e.Right}, e.Args...) {
			if _, err := c.expr(bound, scope, "integer"); err != nil {
				return "", err
			}
		}
		// A range is a Range, or an integer stream where one is expected.
		e.Type = "Range"
		if want == "stream[integer]" {
			e.Type = want
		}
	case "in":
		collection, err := c.expr(e.Right, scope)
		if err != nil {
			return "", err
		}
		member, ok := element(collection)
		if !ok {
			return fail("in requires a list, map, set or stream on the right, found " + collection)
		}
		if _, err = c.expr(e.Left, scope, member); err != nil {
			return "", err
		}
		if !c.compare(member) {
			return fail("in requires elements that support equality")
		}
		e.Type = "boolean"
	case "value":
		produced := want
		inner := c
		inner.yield = &produced
		yields(e.Body)
		complete, err := inner.block(e.Body, cloneScope(scope), "void")
		if err != nil {
			return "", err
		}
		if !complete {
			if e.Body[0].Kind == "if" && len(e.Body[0].Else) == 0 {
				return fail("an if used as a value needs an else")
			}
			return fail("every branch of an if or case used as a value must end in a value")
		}
		e.Type = produced
	case "invoke":
		callee, err := c.expr(e.Left, scope)
		if err != nil {
			return "", err
		}
		params, result, ok := ast.FunctionParts(callee)
		if !ok {
			return fail("expression is not callable")
		}
		if len(params) != len(e.Args) {
			return fail("wrong function argument count")
		}
		for i, arg := range e.Args {
			if _, err = c.expr(arg, scope, params[i]); err != nil {
				return "", err
			}
		}
		e.Type = result
	case "literal":
		e.Type = e.Value.Kind
		if e.Type == "string" && strings.ContainsRune(e.Value.Text, 0) {
			return fail("string literal contains NUL")
		}
	case "template":
		for _, part := range e.Args {
			t, err := c.expr(part, scope)
			if err != nil {
				return "", err
			}
			if t != "string" && t != "integer" && t != "float" && t != "boolean" && t != "atom" {
				return "", diagnostic(part.Line, part.Column, "interpolation requires a string, integer, float, boolean or atom, found %s", t)
			}
		}
		e.Type = "string"
	case "funcref":
		if b, ok := SimpleBuiltins[e.Name]; ok {
			e.Type = "fn[" + strings.Join(append(append([]string{}, b.Params...), b.Result), ",") + "]"
			break
		}
		f, ok := c.functions[e.Name]
		if !ok && c.builtinReference(e) {
			return c.expr(e, scope, want)
		}
		if !ok || e.Name == "main" {
			return fail("unknown function reference " + e.Name)
		}
		if f.Type == "void" {
			return fail(e.Name + " returns no value and cannot be referenced")
		}
		if e.Op != "" && e.Op != strconv.Itoa(len(f.Params)) {
			return fail(fmt.Sprintf("%s takes %d arguments, not %s", functionLocalName(f), len(f.Params), e.Op))
		}
		parts := []string{}
		for _, p := range f.Params {
			parts = append(parts, p.Type)
		}
		parts = append(parts, f.Type)
		e.Type = "fn[" + strings.Join(parts, ",") + "]"
		if names := generic(f); len(names) > 0 {
			vars, bindings := set(names), map[string]string{}
			if want == "" || !unify(e.Type, want, vars, bindings) || !resolved(e.Type, vars, bindings) {
				return fail("reference to generic function " + e.Name + " needs an expected function type")
			}
			e.TypeArgs = nil
			for _, name := range names {
				e.TypeArgs = append(e.TypeArgs, bindings[name])
			}
			e.Type = instantiate(e.Type, vars, bindings)
			c.instantiated(e, f, names)
		}
	case "struct":
		t, err := c.structLiteral(e, scope, want)
		if err != nil {
			return "", err
		}
		e.Type = t
	case "variant":
		// Already resolved by an earlier check of this expression.
		index, _ := strconv.Atoi(e.Op)
		t, err := c.construct(e, variantRef{c.types[e.Name], index}, scope, want)
		if err != nil {
			return "", err
		}
		e.Type = t
	case "field":
		target, err := c.expr(e.Left, scope)
		if err != nil {
			return "", err
		}
		decl, types := c.fieldTypes(target, 0)
		if decl == nil || decl.Kind != "struct" {
			return fail("field access requires a struct, found " + target)
		}
		index := -1
		for i, field := range decl.Fields {
			if field.Name == e.Name {
				index = i
			}
		}
		if index < 0 {
			return fail(decl.Local + " has no field " + e.Name)
		}
		e.Type, e.Op = types[index], strconv.Itoa(index)
	case "name":
		var ok bool
		e.Type, ok = scope[e.Name]
		if !ok {
			ref, message, found := c.constructor(e.Name)
			if message != "" {
				return fail(message)
			}
			if !found {
				return fail("undefined binding " + e.Name)
			}
			t, err := c.construct(e, ref, scope, want)
			if err != nil {
				return "", err
			}
			e.Type = t
		}
	case "map":
		key, value, _ := ast.MapParts(want)
		if len(e.Keys) == 0 && key == "" {
			return fail("empty map requires an expected map type")
		}
		seen := map[ast.Literal]bool{}
		for i, k := range e.Keys {
			kt, err := c.expr(k, scope, key)
			if err != nil {
				return "", err
			}
			if !ast.KeyType(kt) {
				return fail("map keys must be integers, floats, strings, booleans, atoms or tuples of them")
			}
			if key == "" {
				key = kt
			}
			if k.Kind == "literal" {
				if seen[k.Value] {
					return fail("duplicate literal map key")
				}
				seen[k.Value] = true
			}
			vt, err := c.expr(e.Args[i], scope, value)
			if err != nil {
				return "", err
			}
			if value == "" {
				value = vt
			}
		}
		e.Type = "map[" + key + "," + value + "]"
	case "list":
		elem, _ := ast.ListElement(want)
		if len(e.Args) == 0 && elem == "" {
			return fail("empty list requires an expected list type")
		}
		for _, arg := range e.Args {
			t, err := c.expr(arg, scope, elem)
			if err != nil {
				return "", err
			}
			if elem == "" {
				elem = t
			}
		}
		e.Type = "list[" + elem + "]"
		if e.Right != nil {
			if _, err := c.expr(e.Right, scope, e.Type); err != nil {
				return "", err
			}
		}
	case "tuple":
		parts := []string{}
		expectedParts, _ := ast.TupleElements(want)
		for i, arg := range e.Args {
			expectedType := ""
			if i < len(expectedParts) {
				expectedType = expectedParts[i]
			}
			t, err := c.expr(arg, scope, expectedType)
			if err != nil {
				return "", err
			}
			parts = append(parts, t)
		}
		e.Type = "tuple[" + strings.Join(parts, ",") + "]"
	case "index":
		collection, err := c.expr(e.Left, scope)
		if err != nil {
			return "", err
		}
		indexType := "integer"
		if key, _, ok := ast.MapParts(collection); ok {
			indexType = key
		}
		if _, err = c.expr(e.Right, scope, indexType); err != nil {
			return "", err
		}
		if _, value, ok := ast.MapParts(collection); ok {
			e.Type = value
		} else if elem, ok := ast.ListElement(collection); ok {
			e.Type = elem
		} else if parts, ok := ast.TupleElements(collection); ok {
			if e.Right.Kind != "literal" {
				return fail("tuple index must be an integer literal")
			}
			index := e.Right.Value.Integer
			if index < 0 || index >= int64(len(parts)) {
				return fail("tuple index out of bounds")
			}
			e.Type = parts[index]
			e.Name = strconv.FormatInt(index, 10)
		} else {
			return fail("indexing requires a list or tuple")
		}
	case "call":
		if (e.Name == "elem" || e.Name == "put_elem") && c.functions[e.Name] == nil && scope[e.Name] == "" {
			return c.tupleCall(e, scope, want)
		}
		if _, protocol := c.declared[e.Name]; protocol {
			if err := c.dispatch(e, scope); err != nil {
				return "", err
			}
		}
		// String.replace and String.split given a regular expression are
		// the Regex functions with the first two arguments exchanged.
		if target, ok := regexForms[e.Name+"/"+strconv.Itoa(len(e.Args))]; ok && c.regular(e.Args[1], scope) {
			e.Name = target
			e.Args[0], e.Args[1] = e.Args[1], e.Args[0]
		}
		_, library := Libraries[e.Name+"/"+strconv.Itoa(len(e.Args))]
		if _, shadowed := scope[e.Name]; !shadowed && !library {
			ref, message, found := c.constructor(e.Name)
			if message != "" {
				return fail(message)
			}
			if found {
				t, err := c.construct(e, ref, scope, want)
				if err != nil {
					return "", err
				}
				e.Type = t
				break
			}
		}
		if entry, ok := Libraries[e.Name+"/"+strconv.Itoa(len(e.Args))]; ok {
			// A program's own function or binding of the same name wins.
			if _, shadowed := scope[e.Name]; !shadowed && c.functions[e.Name] == nil {
				if len(Overloads[entry.Key]) > 0 {
					entry = c.overload(e, entry, scope)
				}
				t, err := c.library(e, entry, scope, want)
				if err != nil {
					return "", err
				}
				e.Type = t
				break
			}
		}
		if e.Name == "raise" || (e.Name == "throw" && len(e.Args) == 1) {
			if len(e.Args) != 1 {
				return fail("raise requires one argument")
			}
			if e.Name == "throw" {
				if _, err := c.expr(e.Args[0], scope); err != nil {
					return "", err
				}
			} else if arg := e.Args[0]; arg.Kind == "struct" || (arg.Kind == "name" && scope[arg.Name] != "" && scope[arg.Name] != "string") {
				t, err := c.expr(arg, scope)
				if err != nil {
					return "", err
				}
				decl := c.types[t]
				if decl == nil || !decl.Exception {
					return fail("raise takes a message or an exception, not a " + t)
				}
				// Op records where the exception keeps its message.
				for i, field := range decl.Fields {
					if field.Name == "message" {
						e.Op = strconv.Itoa(i)
					}
				}
			} else if _, err := c.expr(arg, scope, "string"); err != nil {
				return "", err
			}
			// raise never returns, so it takes whatever type is expected.
			e.Type = want
			if want == "" {
				if !c.statements[e] {
					// Another branch has to say what type this one stands in for.
					return fail("cannot infer the type this " + e.Name + " stands in for")
				}
				e.Type = "void"
			}
			break
		}
		if e.Name == "length" {
			if len(e.Args) != 1 {
				return fail("length requires one argument")
			}
			t, err := c.expr(e.Args[0], scope)
			if err != nil {
				return "", err
			}
			_, list := ast.ListElement(t)
			_, tuple := ast.TupleElements(t)
			_, _, isMap := ast.MapParts(t)
			if !list && !tuple && !isMap {
				return fail("length requires a list, tuple or map")
			}
			e.Type = "integer"
			break
		}
		if strings.HasPrefix(e.Name, "Server.") {
			t, err := c.serverBuiltin(e, scope)
			if err != nil {
				return "", err
			}
			e.Type = t
			break
		}
		if strings.HasPrefix(e.Name, "Process.") || strings.HasPrefix(e.Name, "Supervisor.") {
			t, err := c.actorBuiltin(e, scope, want)
			if err != nil {
				return "", err
			}
			e.Type = t
			break
		}
		if b, ok := SimpleBuiltins[e.Name]; ok {
			if len(e.Args) != len(b.Params) {
				plural := "s"
				if len(b.Params) == 1 {
					plural = ""
				}
				return fail(fmt.Sprintf("%s requires %d argument%s", e.Name, len(b.Params), plural))
			}
			for i, arg := range e.Args {
				if _, err := c.expr(arg, scope, b.Params[i]); err != nil {
					return "", err
				}
			}
			e.Type = b.Result
			break
		}
		if isBuiltin(e.Name) {
			t, err := c.builtin(e, scope, want)
			if err != nil {
				return "", err
			}
			e.Type = t
			break
		}
		if t, ok := scope[e.Name]; ok && c.functions[e.Name] == nil {
			params, result, ok := ast.FunctionParts(t)
			if !ok {
				return fail("binding is not callable: " + e.Name)
			}
			if len(params) != len(e.Args) {
				return fail("wrong callback argument count")
			}
			for i, arg := range e.Args {
				if _, err := c.expr(arg, scope, params[i]); err != nil {
					return "", err
				}
			}
			e.Type = result
			break
		}
		f, ok := c.functions[e.Name]
		if !ok || f.Name == "main" {
			if message := undefinedLibrary(e.Name, len(e.Args)); message != "" {
				return fail(message)
			}
			return fail("undefined function " + e.Name)
		}
		// Trailing arguments a call leaves out take the parameters' default
		// values, which are constants and so mean the same at every call.
		for len(e.Args) < len(f.Params) && f.Params[len(e.Args)].Default != nil {
			value := cloneExpr(f.Params[len(e.Args)].Default)
			place(value, e.Line, e.Column)
			e.Args = append(e.Args, value)
		}
		if len(f.Params) != len(e.Args) {
			return fail("wrong argument count for " + e.Name)
		}
		names, params := generic(f), []string{}
		for _, param := range f.Params {
			params = append(params, param.Type)
		}
		vars, bindings := set(names), map[string]string{}
		if trial := map[string]string{}; len(names) > 0 && want != "" && unify(f.Type, want, vars, trial) {
			bindings = trial
		}
		if err := c.arguments(e, scope, params, vars, bindings, e.Name); err != nil {
			return "", err
		}
		e.TypeArgs = nil
		for _, name := range names {
			e.TypeArgs = append(e.TypeArgs, bindings[name])
		}
		e.Type = instantiate(f.Type, vars, bindings)
		c.instantiated(e, f, names)
	case "unary":
		t, err := c.expr(e.Left, scope)
		if err != nil {
			return "", err
		}
		want := "integer"
		if e.Op == "not" {
			want = "boolean"
		} else if t == "float" {
			want = "float"
		}
		if t != want {
			return fail("unary " + e.Op + " requires " + want)
		}
		e.Type = want
	case "binary":
		var a, b string
		var err error
		if (e.Left.Kind == "list" || e.Left.Kind == "map") && len(e.Left.Args) == 0 {
			b, err = c.expr(e.Right, scope)
			if err != nil {
				return "", err
			}
			a, err = c.expr(e.Left, scope, b)
		} else {
			a, err = c.expr(e.Left, scope)
			if err != nil {
				return "", err
			}
			b, err = c.expr(e.Right, scope, a)
		}
		if err != nil {
			return "", err
		}
		if a != b {
			return fail("operands must have the same type")
		}
		switch e.Op {
		case "and", "or":
			if a != "boolean" {
				return fail("boolean operator requires booleans")
			}
			e.Type = "boolean"
		case "+", "-", "*", "/":
			if a != "integer" && a != "float" {
				return fail("arithmetic requires integers or floats")
			}
			e.Type = a
		case "%":
			if a != "integer" {
				return fail("% requires integers")
			}
			e.Type = "integer"
		case "<>":
			if a != "string" {
				return fail("<> requires strings")
			}
			e.Type = "string"
		case "++", "--":
			member, ok := ast.ListElement(a)
			if !ok {
				return fail(e.Op + " requires lists")
			}
			if e.Op == "--" && !c.compare(member) {
				return fail("-- requires elements that support equality")
			}
			e.Type = a
		case "**":
			if a != "integer" && a != "float" {
				return fail("** requires integers or floats")
			}
			e.Type = a
		case "==", "!=":
			if !c.compare(a) {
				return fail("function values do not support equality")
			}
			e.Type = "boolean"
		default:
			if a != "integer" && a != "float" && a != "string" && a != "atom" {
				return fail("ordering requires integers, floats, strings or atoms")
			}
			e.Type = "boolean"
		}
	}
	if e.Type == "void" && !c.statements[e] {
		return fail(e.Name + " returns no value")
	}
	if want != "" && e.Type != want {
		return fail("expected " + want + ", found " + e.Type)
	}
	return e.Type, nil
}

// tupleCall types elem(tuple, i) as tuple[i], and put_elem(tuple, i, value)
// as the tuple with element i replaced, for an integer literal i.
func (c checker) tupleCall(e *ast.Expr, scope map[string]string, want string) (string, error) {
	fail := func(format string, args ...any) (string, error) {
		return "", diagnostic(e.Line, e.Column, format, args...)
	}
	if want := map[string]int{"elem": 2, "put_elem": 3}[e.Name]; len(e.Args) != want {
		return fail("%s takes %d arguments", e.Name, want)
	}
	if index := e.Args[1]; index.Kind != "literal" || index.Value.Kind != "integer" {
		return fail("%s needs an integer literal for the index, since each element of a tuple has its own type", e.Name)
	}
	if e.Name == "elem" {
		*e = ast.Expr{Kind: "index", Left: e.Args[0], Right: e.Args[1], Line: e.Line, Column: e.Column}
		return c.expr(e, scope, want)
	}
	t, err := c.expr(cloneExpr(e.Args[0]), cloneScope(scope))
	if err != nil {
		return "", err
	}
	parts, ok := ast.TupleElements(t)
	index := e.Args[1].Value.Integer
	if !ok {
		return fail("put_elem needs a tuple, found %s", t)
	}
	if index < 0 || index >= int64(len(parts)) {
		return fail("tuple index out of bounds")
	}
	// The tuple is bound once and rebuilt with the new element.
	name := fmt.Sprintf("tuple$%d_%d", e.Line, e.Column)
	at := func(x ast.Expr) *ast.Expr { x.Line, x.Column = e.Line, e.Column; return &x }
	rebuilt := at(ast.Expr{Kind: "tuple"})
	for i := range parts {
		if int64(i) == index {
			rebuilt.Args = append(rebuilt.Args, e.Args[2])
			continue
		}
		rebuilt.Args = append(rebuilt.Args, at(ast.Expr{Kind: "index", Left: at(ast.Expr{Kind: "name", Name: name}), Right: at(ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "integer", Integer: int64(i)}})}))
	}
	*e = ast.Expr{Kind: "value", Line: e.Line, Column: e.Column, Body: []ast.Statement{
		{Kind: "bind", Pattern: &ast.Pattern{Kind: "name", Name: name, Line: e.Line, Column: e.Column}, Expr: e.Args[0], Line: e.Line, Column: e.Column},
		{Kind: "call", Expr: rebuilt, Line: e.Line, Column: e.Column},
	}}
	return c.expr(e, scope, want)
}

// builtinReference rewrites &name/arity, for a name the program does not
// define, into the function &name(&1, ..., &arity), so that a library
// function such as &String.length/1 is passed like any other.
func (c checker) builtinReference(e *ast.Expr) bool {
	if e.Kind != "funcref" || c.functions[e.Name] != nil {
		return false
	}
	arity, err := strconv.Atoi(e.Op)
	if err != nil || arity < 0 || arity > 16 {
		return false
	}
	// A bare name is a builtin only when the library has it: any other is
	// reported as an unknown function.
	if !strings.Contains(e.Name, ".") {
		_, library := Libraries[e.Name+"/"+e.Op]
		if b, simple := SimpleBuiltins[e.Name]; !library && !(simple && len(b.Params) == arity) {
			return false
		}
	}
	call := &ast.Expr{Kind: "call", Name: e.Name, Line: e.Line, Column: e.Column}
	for i := 1; i <= arity; i++ {
		call.Args = append(call.Args, &ast.Expr{Kind: "name", Name: "&" + strconv.Itoa(i), Line: e.Line, Column: e.Column})
	}
	*e = ast.Expr{Kind: "capture", Left: call, Value: ast.Literal{Kind: "integer", Integer: int64(arity)}, Line: e.Line, Column: e.Column}
	return true
}

func functionLocalName(f *ast.Function) string {
	// An implementation of a protocol function is known by that name.
	if f.ProtocolFunction != "" {
		return f.ProtocolFunction
	}
	// One arity of an overloaded function, size/2, is known by its name.
	if f.LocalName != "" {
		return plainName(f.LocalName)
	}
	return plainName(f.Name)
}

// place gives an expression copied from elsewhere the position it is used at.
func place(e *ast.Expr, line, column int) {
	if e == nil {
		return
	}
	e.Line, e.Column = line, column
	place(e.Left, line, column)
	place(e.Right, line, column)
	for _, arg := range append(append([]*ast.Expr{}, e.Args...), e.Keys...) {
		place(arg, line, column)
	}
}
