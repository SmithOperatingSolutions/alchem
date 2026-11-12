package syntax

import (
	"fmt"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// walk visits every statement list of a program, innermost bodies included.
func walk(p *ast.Program, visit func(body []ast.Statement) []ast.Statement) {
	var block func([]ast.Statement) []ast.Statement
	var expr func(*ast.Expr)
	expr = func(e *ast.Expr) {
		if e == nil {
			return
		}
		expr(e.Left)
		expr(e.Right)
		for _, arg := range e.Args {
			expr(arg)
		}
		for _, key := range e.Keys {
			expr(key)
		}
		e.Body = block(e.Body)
	}
	block = func(body []ast.Statement) []ast.Statement {
		if body == nil {
			return nil
		}
		body = visit(body)
		for i := range body {
			s := &body[i]
			expr(s.Expr)
			s.Then = block(s.Then)
			s.Else = block(s.Else)
			for j := range s.Arms {
				expr(s.Arms[j].Guard)
				s.Arms[j].Body = block(s.Arms[j].Body)
			}
		}
		return body
	}
	for i := range p.Functions {
		expr(p.Functions[i].Guard)
		p.Functions[i].Body = block(p.Functions[i].Body)
	}
}

// desugarUnless negates the condition of every unless, leaving an if.
func desugarUnless(p *ast.Program) {
	walk(p, func(body []ast.Statement) []ast.Statement {
		for i := range body {
			if s := &body[i]; s.Kind == "if" && s.Name == "unless" {
				s.Name = ""
				s.Expr = &ast.Expr{Kind: "unary", Op: "not", Left: s.Expr, Line: s.Expr.Line, Column: s.Expr.Column}
			}
		}
		return body
	})
}

// desugarReceives turns assert_receive(pid, pattern) into a binding of the
// pattern to the first message a matching function accepts, and
// refute_receive into a call with the same function. The function is the
// pattern, and its guard, as a case that answers true or false.
func desugarReceives(p *ast.Program) {
	walk(p, func(body []ast.Statement) []ast.Statement {
		for i := range body {
			s := body[i]
			if s.Kind != "receive" {
				continue
			}
			at := func(e ast.Expr) *ast.Expr {
				e.Line, e.Column = s.Line, s.Column
				return &e
			}
			answer := func(value bool) []ast.Statement {
				return []ast.Statement{{Kind: "call", Line: s.Line, Column: s.Column, Expr: at(ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "boolean", Boolean: value}})}}
			}
			message := fmt.Sprintf("message$%d_%d", s.Line, s.Column)
			accept := ast.Arm{Pattern: clonePattern(s.Pattern), Body: answer(true)}
			if len(s.Arms) > 0 {
				accept.Guard = s.Arms[0].Guard
			}
			arms := []ast.Arm{accept}
			// A pattern that takes anything needs no second arm.
			if accept.Guard != nil || (s.Pattern.Kind != "name" && s.Pattern.Kind != "wildcard") {
				arms = append(arms, ast.Arm{Pattern: &ast.Pattern{Kind: "wildcard", Line: s.Line, Column: s.Column}, Body: answer(false)})
			}
			matcher := at(ast.Expr{Kind: "lambda", Params: []ast.Parameter{{Name: message, Line: s.Line, Column: s.Column}},
				Body: []ast.Statement{{Kind: "case", Line: s.Line, Column: s.Column, Arms: arms, Expr: at(ast.Expr{Kind: "name", Name: message})}}})
			text := func(value string) *ast.Expr {
				return at(ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "string", Text: value}})
			}
			// -1 asks for the default wait; the received forms do not wait.
			extras := s.Expr.Args[1:]
			timeout := at(ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "integer", Integer: -1}})
			refuting := strings.HasPrefix(s.Name, "refute")
			if strings.HasSuffix(s.Name, "received") {
				timeout = at(ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "integer", Integer: 0}})
			} else if len(extras) > 0 {
				timeout, extras = extras[0], extras[1:]
			}
			custom := text("")
			if len(extras) > 0 {
				custom = extras[0]
			}
			// The failure shows the pattern as written and what each pinned
			// name held.
			shown := PatternText(s.Pattern)
			if accept.Guard != nil {
				shown += " when " + ExprText(accept.Guard)
			}
			pinned := at(ast.Expr{Kind: "list"})
			seen := map[string]bool{}
			var pins func(*ast.Pattern)
			pins = func(pattern *ast.Pattern) {
				if pattern == nil {
					return
				}
				if pattern.Kind == "pin" && !seen[pattern.Name] {
					seen[pattern.Name] = true
					pinned.Args = append(pinned.Args, at(ast.Expr{Kind: "binary", Op: "<>", Left: text(pattern.Name + " = "),
						Right: at(ast.Expr{Kind: "call", Name: "inspect", Args: []*ast.Expr{at(ast.Expr{Kind: "name", Name: pattern.Name})}})}))
				}
				for _, child := range pattern.Children {
					pins(child)
				}
				pins(pattern.Tail)
			}
			pins(s.Pattern)
			name := "assert_receive"
			if refuting {
				name = "refute_receive"
			}
			call := at(ast.Expr{Kind: "call", Name: name, Args: []*ast.Expr{s.Expr.Args[0], timeout, matcher, text(shown), pinned, custom}})
			if refuting {
				body[i] = ast.Statement{Kind: "call", Expr: call, Line: s.Line, Column: s.Column}
				continue
			}
			body[i] = ast.Statement{Kind: "bind", Pattern: s.Pattern, Name: s.Pattern.Name, Expr: call, Line: s.Line, Column: s.Column}
		}
		return body
	})
}

// desugarClauses turns the clauses of an anonymous function into a case
// over its one argument.
func desugarClauses(p *ast.Program) {
	walk(p, func(body []ast.Statement) []ast.Statement {
		for i := range body {
			if s := body[i]; s.Kind == "clauses" {
				body[i] = ast.Statement{Kind: "case", Arms: s.Arms, Line: s.Line, Column: s.Column, Expr: &ast.Expr{Kind: "name", Name: s.Name, Line: s.Line, Column: s.Column}}
			}
		}
		return body
	})
}

// desugarConds rewrites every cond into nested ifs. A final "true ->" arm
// becomes the last else; without one, falling through every condition fails.
func desugarConds(p *ast.Program) {
	walk(p, func(body []ast.Statement) []ast.Statement {
		for i := range body {
			if body[i].Kind != "cond" {
				continue
			}
			s := body[i]
			otherwise := []ast.Statement{{Kind: "call", Line: s.Line, Column: s.Column, Expr: &ast.Expr{Kind: "call", Name: "raise", Line: s.Line, Column: s.Column, Args: []*ast.Expr{{Kind: "literal", Value: ast.Literal{Kind: "string", Text: "no cond clause matched"}, Line: s.Line, Column: s.Column}}}}}
			for j := len(s.Arms) - 1; j >= 0; j-- {
				arm := s.Arms[j]
				if j == len(s.Arms)-1 && arm.Guard.Kind == "literal" && arm.Guard.Value.Kind == "boolean" && arm.Guard.Value.Boolean {
					otherwise = arm.Body
					continue
				}
				otherwise = []ast.Statement{{Kind: "if", Expr: arm.Guard, Then: arm.Body, Else: otherwise, Line: arm.Guard.Line, Column: arm.Guard.Column}}
			}
			if len(otherwise) == 1 && otherwise[0].Kind == "if" {
				body[i] = otherwise[0]
				continue
			}
			// A cond whose only arm is "true ->" is just its body.
			body[i] = ast.Statement{Kind: "if", Expr: &ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "boolean", Boolean: true}, Line: s.Line, Column: s.Column}, Then: otherwise, Else: otherwise, Line: s.Line, Column: s.Column}
		}
		return body
	})
}

// generated reports a name the compiler introduced: clause and lambda
// parameters ("arg$1") and capture placeholders ("&1").
func generated(name string) bool {
	return strings.Contains(name, "$") || strings.HasPrefix(name, "&")
}

// lambdaTail makes the last expression of an inferred function its result.
// A body that ends in a statement with no value, such as IO.puts, returns
// the empty tuple, so functions run only for their effect need no dummy value.
func lambdaTail(body []ast.Statement) []ast.Statement {
	last := &body[len(body)-1]
	unit := ast.Statement{Kind: "return", Line: last.Line, Column: last.Column, Expr: &ast.Expr{Kind: "tuple", Line: last.Line, Column: last.Column}}
	switch last.Kind {
	case "return":
	case "call":
		if last.Expr.Kind == "call" && voidCall(last.Expr.Name) {
			return append(body, unit)
		}
		last.Kind = "return"
	case "if":
		if len(last.Else) == 0 {
			return append(body, unit)
		}
		last.Then, last.Else = lambdaTail(last.Then), lambdaTail(last.Else)
	case "case":
		for i := range last.Arms {
			last.Arms[i].Body = lambdaTail(last.Arms[i].Body)
		}
	default:
		return append(body, unit)
	}
	return body
}

// voidCall reports a builtin that is run for its effect and has no value.
func voidCall(name string) bool {
	if b, ok := SimpleBuiltins[name]; ok && b.Result == "void" {
		return true
	}
	for key, lib := range Libraries {
		if lib.Result == "void" && strings.HasPrefix(key, name+"/") {
			return true
		}
	}
	return false
}

// lambda types fn x -> ... end and &(...) against known parameter types, and
// rewrites the expression into an ordinary typed closure. result is the
// expected result type, or "" to infer it from the body.
func (c checker) lambda(e *ast.Expr, scope map[string]string, params []string, result string) (string, error) {
	fail := func(format string, args ...any) (string, error) {
		return "", diagnostic(e.Line, e.Column, format, args...)
	}
	if e.Kind == "capture" {
		for i := int64(1); i <= e.Value.Integer; i++ {
			e.Params = append(e.Params, ast.Parameter{Name: fmt.Sprintf("&%d", i), Line: e.Line, Column: e.Column})
		}
		e.Body = []ast.Statement{{Kind: "call", Expr: e.Left, Line: e.Line, Column: e.Column}}
		e.Kind, e.Left = "lambda", nil
	}
	if len(e.Params) != len(params) {
		return fail("this function takes %s, but %d expected here", plural(len(e.Params), "parameter"), len(params))
	}
	local := cloneScope(scope)
	var binds []ast.Statement
	for i := range e.Params {
		param := &e.Params[i]
		param.Type = params[i]
		if param.Pattern != nil {
			// A pattern parameter is matched at the top of the body.
			param.Name = fmt.Sprintf("arg$%d", c.fresh())
			binds = append(binds, ast.Statement{Kind: "bind", Pattern: param.Pattern, Line: param.Line, Column: param.Column, Expr: &ast.Expr{Kind: "name", Name: param.Name, Line: param.Line, Column: param.Column}})
			param.Pattern = nil
		} else if !generated(param.Name) && !bindingName(param.Name) {
			return "", diagnostic(param.Line, param.Column, "invalid parameter name %q", param.Name)
		}
		if _, exists := local[param.Name]; exists {
			return "", diagnostic(param.Line, param.Column, "parameter %s shadows an existing binding", param.Name)
		}
		local[param.Name] = param.Type
	}
	body := lambdaTail(append(binds, e.Body...))
	produced := result
	inner := c
	inner.yield, inner.infer = nil, &produced
	returns, err := inner.block(body, local, "?")
	if err != nil {
		return "", err
	}
	if !returns || produced == "" {
		return fail("every path of this function must produce a value")
	}
	e.Kind, e.Body, e.ReturnType = "closure", body, produced
	e.Type = "fn[" + strings.Join(append(append([]string{}, params...), produced), ",") + "]"
	return e.Type, nil
}

// lambdaArgument types an inferred function passed where param, which may
// mention type variables, is expected. Its parameter types must already be
// known; its result may still be open and is then inferred.
func (c checker) lambdaArgument(arg *ast.Expr, scope map[string]string, param string, vars map[string]bool, bindings map[string]string) (string, error) {
	parts, result, ok := ast.FunctionParts(param)
	if !ok {
		return "", diagnostic(arg.Line, arg.Column, "a function is not expected here; expected %s", instantiate(param, vars, bindings))
	}
	types := []string{}
	for i, part := range parts {
		if !resolved(part, vars, bindings) {
			return "", diagnostic(arg.Line, arg.Column, "cannot infer the type of parameter %d of this function; write fn(name: type): type do ... end", i+1)
		}
		types = append(types, instantiate(part, vars, bindings))
	}
	expected := ""
	if resolved(result, vars, bindings) {
		expected = instantiate(result, vars, bindings)
	}
	return c.lambda(arg, scope, types, expected)
}

// element returns the element type of an enumerable: a list or stream of T
// yields T, a set its members, and a map its entries as tuple[K,V].
func element(t string) (string, bool) {
	head, args := ast.Split(t)
	switch head {
	case "list", "stream", "set":
		return args[0], true
	case "map":
		return "tuple[" + args[0] + "," + args[1] + "]", true
	case "Range":
		return "integer", true
	}
	return "", false
}

// desugarChecks rewrites every check all into a call of Gen.check. The
// generators are joined with Gen.bind, so that each sees what the earlier
// ones bound, and the last makes the tuple of every value; the filters
// become a Gen.filter of it, and the body a function of it. Each value is
// bound to a name of its own and matched against its pattern inside:
//
//	check all a <- ga, b <- gb, a < b do body end
//	Gen.check(Gen.filter(Gen.bind(ga, fn v0 -> case v0 do a ->
//	  Gen.map(gb, fn v1 -> case v1 do b -> {v0, v1} end end) end end),
//	  fn {a, b} -> a < b end), fn {a, b} -> body end)
func desugarChecks(p *ast.Program) {
	walk(p, func(body []ast.Statement) []ast.Statement {
		for i := range body {
			if body[i].Kind != "check" {
				continue
			}
			s := body[i]
			at := func(e ast.Expr) *ast.Expr { e.Line, e.Column = s.Line, s.Column; return &e }
			call := func(name string, args ...*ast.Expr) *ast.Expr {
				return at(ast.Expr{Kind: "call", Name: name, Args: args})
			}
			result := func(e *ast.Expr) []ast.Statement {
				return []ast.Statement{{Kind: "call", Expr: e, Line: s.Line, Column: s.Column}}
			}
			fn := func(param ast.Parameter, body []ast.Statement) *ast.Expr {
				param.Line, param.Column = s.Line, s.Column
				return at(ast.Expr{Kind: "lambda", Params: []ast.Parameter{param}, Body: body})
			}
			var generators []ast.Arm
			var filters []*ast.Expr
			for _, arm := range s.Arms {
				if arm.Pattern == nil {
					filters = append(filters, arm.Guard)
				} else {
					generators = append(generators, arm)
				}
			}
			name := func(j int) string { return fmt.Sprintf("check$%d_%d_%d", s.Line, s.Column, j) }
			// whole matches every value at once with the patterns written.
			whole := func() ast.Parameter {
				if len(generators) == 1 {
					if only := generators[0].Pattern; only.Kind == "name" {
						return ast.Parameter{Name: only.Name}
					}
					return ast.Parameter{Pattern: clonePattern(generators[0].Pattern)}
				}
				tuple := &ast.Pattern{Kind: "tuple", Line: s.Line, Column: s.Column}
				for _, arm := range generators {
					tuple.Children = append(tuple.Children, clonePattern(arm.Pattern))
				}
				return ast.Parameter{Pattern: tuple}
			}
			var values []*ast.Expr
			for j := range generators {
				values = append(values, at(ast.Expr{Kind: "name", Name: name(j)}))
			}
			var made *ast.Expr
			if len(values) == 1 {
				made = values[0]
			} else {
				made = at(ast.Expr{Kind: "tuple", Args: values})
			}
			var generator *ast.Expr
			for j := len(generators) - 1; j >= 0; j-- {
				arm := generators[j]
				inner := made
				if generator != nil {
					inner = generator
				}
				matched := []ast.Statement{{Kind: "case", Expr: at(ast.Expr{Kind: "name", Name: name(j)}), Arms: []ast.Arm{{Pattern: clonePattern(arm.Pattern), Body: result(inner)}}, Line: s.Line, Column: s.Column}}
				if generator == nil {
					generator = call("Gen.map", arm.Guard, fn(ast.Parameter{Name: name(j)}, matched))
				} else {
					generator = call("Gen.bind", arm.Guard, fn(ast.Parameter{Name: name(j)}, matched))
				}
			}
			if len(filters) > 0 {
				condition := filters[0]
				for _, filter := range filters[1:] {
					condition = at(ast.Expr{Kind: "binary", Op: "and", Left: condition, Right: filter})
				}
				generator = call("Gen.filter", generator, fn(whole(), result(condition)))
			}
			args := []*ast.Expr{generator, fn(whole(), s.Then)}
			if s.Expr != nil {
				args = append(args, s.Expr)
			}
			body[i] = ast.Statement{Kind: "call", Expr: call("Gen.check", args...), Line: s.Line, Column: s.Column}
		}
		return body
	})
}

// desugarWiths rewrites every with into nested case statements: one per
// clause, matching its pattern and continuing, with a second arm for a value
// that does not match. That value goes to the else arms when there are any;
// otherwise it becomes the result, as the "unmatched" expression works out.
func desugarWiths(p *ast.Program) {
	walk(p, func(body []ast.Statement) []ast.Statement {
		for i := range body {
			if body[i].Kind != "with" {
				continue
			}
			s := body[i]
			var build func(clause int) []ast.Statement
			build = func(clause int) []ast.Statement {
				if clause == len(s.Arms) {
					return s.Then
				}
				arm := s.Arms[clause]
				arms := []ast.Arm{{Pattern: arm.Pattern, Body: build(clause + 1)}}
				if !irrefutable(arm.Pattern) {
					name := fmt.Sprintf("with$%d_%d_%d", s.Line, s.Column, clause)
					value := &ast.Expr{Kind: "name", Name: name, Line: arm.Guard.Line, Column: arm.Guard.Column}
					miss := []ast.Statement{{Kind: "call", Expr: &ast.Expr{Kind: "unmatched", Left: value, Line: arm.Guard.Line, Column: arm.Guard.Column}, Line: s.Line, Column: s.Column}}
					if len(s.Else) > 0 {
						// Marked so that the else arms need not be exhaustive:
						// a value none of them matches fails at run time.
						// Each clause gets its own copy of the arms: clauses
						// may produce different types, and an arm is typed
						// for the clause it is reached from. Pattern is the
						// clause's own, which the missed value did not match.
						miss = []ast.Statement{{Kind: "case", Name: "with-else", Expr: value, Pattern: arm.Pattern, Arms: cloneArms(s.Else[0].Arms), Line: s.Line, Column: s.Column}}
					}
					arms = append(arms, ast.Arm{Pattern: &ast.Pattern{Kind: "name", Name: name, Line: arm.Guard.Line, Column: arm.Guard.Column}, Body: miss})
				}
				return []ast.Statement{{Kind: "case", Expr: arm.Guard, Arms: arms, Line: s.Line, Column: s.Column}}
			}
			body[i] = build(0)[0]
		}
		return body
	})
}

// The clone functions copy a syntax tree, so that one piece of source can be
// analyzed more than once with different types.
func cloneArms(arms []ast.Arm) []ast.Arm {
	out := make([]ast.Arm, len(arms))
	for i, arm := range arms {
		out[i] = ast.Arm{Pattern: clonePattern(arm.Pattern), Guard: cloneExpr(arm.Guard), Body: cloneBlock(arm.Body)}
	}
	return out
}

func cloneBlock(body []ast.Statement) []ast.Statement {
	if body == nil {
		return nil
	}
	out := make([]ast.Statement, len(body))
	for i, s := range body {
		s.Pattern, s.Expr = clonePattern(s.Pattern), cloneExpr(s.Expr)
		s.Then, s.Else = cloneBlock(s.Then), cloneBlock(s.Else)
		if s.Arms != nil {
			s.Arms = cloneArms(s.Arms)
		}
		out[i] = s
	}
	return out
}

func cloneExpr(e *ast.Expr) *ast.Expr {
	if e == nil {
		return nil
	}
	copied := *e
	copied.Left, copied.Right = cloneExpr(e.Left), cloneExpr(e.Right)
	copied.Args, copied.Keys = cloneExprs(e.Args), cloneExprs(e.Keys)
	copied.Body = cloneBlock(e.Body)
	copied.Params = append([]ast.Parameter(nil), e.Params...)
	for i := range copied.Params {
		copied.Params[i].Pattern = clonePattern(copied.Params[i].Pattern)
	}
	copied.Labels = append([]string(nil), e.Labels...)
	copied.TypeArgs = append([]string(nil), e.TypeArgs...)
	return &copied
}

func cloneExprs(list []*ast.Expr) []*ast.Expr {
	if list == nil {
		return nil
	}
	out := make([]*ast.Expr, len(list))
	for i, e := range list {
		out[i] = cloneExpr(e)
	}
	return out
}

func clonePattern(p *ast.Pattern) *ast.Pattern {
	if p == nil {
		return nil
	}
	copied := *p
	copied.Tail = clonePattern(p.Tail)
	if p.Children != nil {
		copied.Children = make([]*ast.Pattern, len(p.Children))
		for i, child := range p.Children {
			copied.Children[i] = clonePattern(child)
		}
	}
	copied.Labels = append([]string(nil), p.Labels...)
	copied.Fields = append([]int(nil), p.Fields...)
	copied.Keys = append([]ast.Literal(nil), p.Keys...)
	return &copied
}

// reachable keeps the else arms of a with that can apply to a value of the
// given type which failed to match the clause's pattern: arms whose pattern
// fits the type, up to the point where every such value is already handled.
func (c checker) reachable(arms []ast.Arm, clause *ast.Pattern, typ string, scope map[string]string) []ast.Arm {
	rows := [][]*ast.Pattern{{clause}}
	var out []ast.Arm
	for _, arm := range arms {
		if c.covers(rows, []string{typ}) {
			break
		}
		if c.checkPattern(arm.Pattern, typ, cloneScope(scope)) != nil {
			continue
		}
		out = append(out, arm)
		if arm.Guard == nil {
			rows = append(rows, []*ast.Pattern{arm.Pattern})
		}
	}
	return out
}
