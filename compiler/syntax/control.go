package syntax

import (
	"regexp"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// unitTail makes a body run only for its effects end in the empty tuple.
func unitTail(body []ast.Statement) []ast.Statement {
	last := body[len(body)-1]
	if last.Kind == "yield" && last.Expr.Kind == "tuple" && len(last.Expr.Args) == 0 {
		return body
	}
	return append(body, ast.Statement{Kind: "yield", Line: last.Line, Column: last.Column, Expr: &ast.Expr{Kind: "tuple", Line: last.Line, Column: last.Column}})
}

// endsInEffect reports a body whose last statement has no value: IO.puts,
// assert, or a call of a function that returns none.
func endsInEffect(body []ast.Statement) bool {
	if len(body) == 0 {
		return false
	}
	last := body[len(body)-1]
	switch last.Kind {
	case "output", "assert":
		return true
	case "call":
		return last.Expr != nil && last.Expr.Kind == "call" && voidCall(last.Expr.Name)
	}
	return false
}

// RegexSource is the RE2 pattern for a ~r sigil's text and modifier letters.
func RegexSource(text, modifiers string) (string, bool) {
	flags := ""
	for _, letter := range modifiers {
		switch letter {
		case 'i', 'm', 's', 'U':
			flags += string(letter)
		case 'u':
		case 'x':
			text = extended(text)
		default:
			return "", false
		}
	}
	if flags != "" {
		return "(?" + flags + ")" + text, true
	}
	return text, true
}

// extended removes what the x modifier allows for readability: whitespace,
// and comments from # to the end of a line, outside character classes and
// escapes.
func extended(text string) string {
	var out strings.Builder
	inClass, comment := false, false
	for i := 0; i < len(text); i++ {
		ch := text[i]
		switch {
		case comment:
			comment = ch != '\n'
		case ch == '\\' && i+1 < len(text):
			out.WriteByte(ch)
			out.WriteByte(text[i+1])
			i++
		case inClass:
			inClass = ch != ']'
			out.WriteByte(ch)
		case ch == '[':
			inClass = true
			out.WriteByte(ch)
		case ch == '#':
			comment = true
		case ch == ' ', ch == '\t', ch == '\n', ch == '\r':
		default:
			out.WriteByte(ch)
		}
	}
	return out.String()
}

// control types try, for, the value of a with clause that did not match, and
// sigils.
func (c checker) control(e *ast.Expr, scope map[string]string, want string) (string, error) {
	fail := func(format string, args ...any) (string, error) {
		return "", diagnostic(e.Line, e.Column, format, args...)
	}
	// A try or for written as a statement is run for its effects.
	discard := c.statements[e]
	switch e.Kind {
	case "sigil":
		text := e.Value.Text
		// An interpolating sigil is its template: as it stands for ~s,
		// split into words for ~w, and compiled when it runs for ~r.
		if template := e.Left; template != nil {
			at := func(node ast.Expr) *ast.Expr {
				node.Line, node.Column = e.Line, e.Column
				return &node
			}
			switch e.Name {
			case "h":
				line, column := e.Line, e.Column
				*e = *markupTemplate(template, at)
				typ, err := c.expr(e, scope, want)
				if err != nil {
					if found := markupMismatch.FindStringSubmatch(err.Error()); found != nil {
						return "", diagnostic(line, column, "~h cannot put a %s into HTML: a value in a template must be a string, integer, float, atom, Markup or list of Markup; convert it to a string first", found[1])
					}
				}
				return typ, err
			case "s":
				*e = *template
			case "w":
				*e = *at(ast.Expr{Kind: "call", Name: "String.split", Args: []*ast.Expr{template}})
			case "c":
				return fail("~c does not interpolate")
			default:
				handler := c.sigilHandler(e.Name)
				if handler == "" {
					return fail("unknown sigil ~%s: define sigil_%s(text: string, modifiers: string) to give it a meaning", e.Name, e.Name)
				}
				*e = *at(ast.Expr{Kind: "call", Name: handler, Args: []*ast.Expr{template, at(ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "string", Text: e.Op}})}})
				return c.expr(e, scope, want)
			case "r":
				flags, ok := RegexSource("", e.Op)
				if !ok {
					return fail("~r accepts the modifiers i, m, s and u")
				}
				if flags != "" {
					template.Args = append([]*ast.Expr{at(ast.Expr{Kind: "literal", Op: "text", Value: ast.Literal{Kind: "string", Text: flags}})}, template.Args...)
				}
				*e = *at(ast.Expr{Kind: "call", Name: "Regex.compile!", Args: []*ast.Expr{template}})
			}
			return c.expr(e, scope, want)
		}
		switch e.Name {
		case "r":
			source, ok := RegexSource(text, e.Op)
			if !ok {
				return fail("~r accepts the modifiers i, m, s and u")
			}
			if _, err := regexp.Compile(source); err != nil {
				return fail("invalid regular expression: %v", err)
			}
			return "regex", nil
		case "w":
			e.Kind, e.Args = "list", nil
			for _, word := range strings.Fields(text) {
				e.Args = append(e.Args, &ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "string", Text: word}, Line: e.Line, Column: e.Column})
			}
			if len(e.Args) == 0 {
				e.Type = "list[string]"
				return e.Type, nil
			}
			return c.expr(e, scope, want)
		case "s", "S":
			e.Kind = "literal"
			return c.expr(e, scope, want)
		case "h", "H":
			if e.Op != "" {
				return fail("~%s takes no modifiers", e.Name)
			}
			*e = ast.Expr{Kind: "call", Name: "Markup.raw", Line: e.Line, Column: e.Column, Args: []*ast.Expr{
				{Kind: "literal", Value: ast.Literal{Kind: "string", Text: text}, Line: e.Line, Column: e.Column}}}
			return c.expr(e, scope, want)
		case "D", "T", "N", "U":
			if message := calendarSigil(e); message != "" {
				return fail("%s", message)
			}
			return c.expr(e, scope, want)
		}
		if e.Name == "c" || e.Name == "C" {
			// There are no charlists: ~c is the code points as integers.
			e.Kind, e.Args = "list", nil
			for _, r := range text {
				e.Args = append(e.Args, &ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "integer", Integer: int64(r)}, Line: e.Line, Column: e.Column})
			}
			if len(e.Args) == 0 {
				e.Type = "list[integer]"
				return e.Type, nil
			}
			return c.expr(e, scope, want)
		}
		// Any other letter is a sigil the program defines: a function
		// sigil_x(text, modifiers) in the module that uses it.
		handler := c.sigilHandler(e.Name)
		if handler == "" {
			return fail("unknown sigil ~%s: define sigil_%s(text: string, modifiers: string) to give it a meaning", e.Name, e.Name)
		}
		*e = ast.Expr{Kind: "call", Name: handler, Line: e.Line, Column: e.Column, Args: []*ast.Expr{
			{Kind: "literal", Value: ast.Literal{Kind: "string", Text: text}, Line: e.Line, Column: e.Column},
			{Kind: "literal", Value: ast.Literal{Kind: "string", Text: e.Op}, Line: e.Line, Column: e.Column}}}
		return c.expr(e, scope, want)
	case "unmatched":
		source, err := c.expr(e.Left, scope)
		if err != nil {
			return "", err
		}
		if want == "" {
			if discard {
				e.Op = "skip"
				return "void", nil
			}
			return fail("cannot infer the result of this with; a clause that does not match needs the type of the whole expression")
		}
		from, fromArgs := ast.Split(source)
		to, toArgs := ast.Split(want)
		switch {
		case source == want:
			e.Op = "same"
		case from == "result" && to == "result" && fromArgs[1] == toArgs[1]:
			e.Op = "error"
		case from == "option" && to == "option":
			e.Op = "none"
		default:
			return fail("a %s that does not match its with clause cannot become the %s this with produces; add an else", source, want)
		}
		return want, nil
	case "try":
		statement := &e.Body[0]
		produced := want
		inner := c
		inner.yield, inner.infer = &produced, nil
		prepare := func(body []ast.Statement) []ast.Statement {
			if discard {
				return unitTail(body)
			}
			yields(body)
			return body
		}
		hasElse := false
		for _, arm := range statement.Arms {
			hasElse = hasElse || arm.Kind == "else"
		}
		var complete, retry bool
		var err error
		bodyType := ""
		if hasElse {
			// The body's value goes to the else arms, which make the
			// value of the try.
			body := c
			body.yield, body.infer = &bodyType, nil
			yields(statement.Then)
			finished, err := body.block(statement.Then, cloneScope(scope), "void")
			if err != nil {
				return "", err
			}
			if !finished || bodyType == "" {
				return fail("the body of a try with else must end in a value")
			}
			complete = true
		} else {
			statement.Then = prepare(statement.Then)
			complete, err = inner.block(statement.Then, cloneScope(scope), "void")
			retry = err != nil && inner.undetermined(err)
			if err != nil && !retry {
				return "", err
			}
		}
		thrown := c.thrownTypes(statement.Then)
		for i := range statement.Arms {
			arm := &statement.Arms[i]
			branch := cloneScope(scope)
			matched, err := c.armType(arm, bodyType, thrown)
			if err != nil {
				return "", err
			}
			arm.Type = matched
			if err := c.checkPattern(arm.Pattern, matched, branch); err != nil {
				return "", err
			}
			if arm.Guard != nil {
				if _, err := c.expr(arm.Guard, branch, "boolean"); err != nil {
					return "", err
				}
			}
			arm.Body = prepare(arm.Body)
			finished, err := inner.block(arm.Body, branch, "void")
			if err != nil {
				return "", err
			}
			complete = complete && finished
		}
		if retry {
			if complete, err = inner.block(statement.Then, cloneScope(scope), "void"); err != nil {
				return "", err
			}
		}
		if !complete || produced == "" {
			return fail("the body of try and every rescue, catch and else arm must end in a value")
		}
		if len(statement.Else) > 0 {
			cleanup := c
			cleanup.yield, cleanup.infer = nil, nil
			if _, err := cleanup.block(statement.Else, cloneScope(scope), "void"); err != nil {
				return "", err
			}
		}
		return produced, nil
	case "for":
		// uniq: and into: are the plain comprehension passed on to Enum.
		if len(e.Labels) == 1 && e.Labels[0] != "reduce" {
			inner := *e
			inner.Labels, inner.Args = nil, nil
			option, value := e.Labels[0], e.Args[0]
			if option == "uniq" {
				if value.Kind != "literal" || value.Value.Kind != "boolean" {
					return fail("uniq: takes true or false")
				}
				if !value.Value.Boolean {
					*e = inner
					return c.expr(e, scope, want)
				}
				*e = ast.Expr{Kind: "call", Name: "Enum.uniq", Args: []*ast.Expr{&inner}, Line: e.Line, Column: e.Column}
			} else {
				*e = ast.Expr{Kind: "call", Name: "Enum.into", Args: []*ast.Expr{&inner, value}, Line: e.Line, Column: e.Column}
			}
			return c.expr(e, scope, want)
		}
		statement := &e.Body[0]
		local := cloneScope(scope)
		reduced := ""
		if len(e.Labels) == 1 {
			// An empty %{} or [] says nothing about its type, and the body
			// cannot supply it: it is typed from the accumulator.
			if value := e.Args[0]; want == "" && (value.Kind == "map" || value.Kind == "list") && len(value.Args) == 0 && len(value.Keys) == 0 {
				return "", diagnostic(value.Line, value.Column, "the empty reduce: value needs a type; annotate what the for is bound to, as in counts: map[string, integer] = for ... reduce: %%{} do")
			}
			initial, err := c.expr(e.Args[0], scope, want)
			if err != nil {
				return "", err
			}
			reduced = initial
		}
		for i := range statement.Arms {
			arm := &statement.Arms[i]
			if arm.Pattern == nil {
				if _, err := c.expr(arm.Guard, local, "boolean"); err != nil {
					return "", err
				}
				continue
			}
			source, err := c.expr(arm.Guard, local)
			if err != nil {
				return "", err
			}
			member, ok := element(source)
			if !ok {
				return "", diagnostic(arm.Guard.Line, arm.Guard.Column, "a for generator needs a list, map, set, stream or range, found %s", source)
			}
			if err := c.checkPattern(arm.Pattern, member, local); err != nil {
				return "", err
			}
		}
		produced := ""
		if member, ok := ast.ListElement(want); ok {
			produced = member
		}
		inner := c
		inner.yield, inner.infer = &produced, nil
		if reduced != "" {
			// The accumulator is bound for the body, whose value is the
			// next accumulator.
			local[e.Name] = reduced
			produced = reduced
			yields(statement.Then)
			complete, err := inner.block(statement.Then, local, "void")
			if err != nil {
				return "", err
			}
			if !complete || produced != reduced {
				return fail("every arm of a for with reduce: must end in the next accumulator, of type %s", reduced)
			}
			return reduced, nil
		}
		if discard || endsInEffect(statement.Then) {
			// A body run for its effects gives {} for each element, as
			// Elixir's gives :ok.
			produced = ""
			statement.Then = unitTail(statement.Then)
		} else {
			yields(statement.Then)
		}
		complete, err := inner.block(statement.Then, local, "void")
		if err != nil {
			return "", err
		}
		if !complete || produced == "" {
			return fail("the body of for must end in a value")
		}
		return "list[" + produced + "]", nil
	}
	return fail("unsupported expression")
}

// calendarSigil is replaced by the date and time support; until then the
// calendar sigils are rejected.
var calendarSigil = func(e *ast.Expr) string { return "unknown sigil ~" + e.Name }

// regexForms maps the String functions that also accept a regular
// expression to the Regex function that does the work.
var regexForms = map[string]string{"String.replace/3": "Regex.replace", "String.split/2": "Regex.split"}

// regular reports whether an argument is plainly a regular expression: a
// ~r sigil, a binding of that type, or a call that compiles one.
func (c checker) regular(e *ast.Expr, scope map[string]string) bool {
	switch e.Kind {
	case "sigil":
		return e.Name == "r"
	case "name":
		return scope[e.Name] == "regex"
	case "call":
		return e.Name == "Regex.compile!"
	}
	return false
}

// sigilHandler finds the function that gives a program-defined sigil its
// meaning: sigil_x in the entry module, or the one module that defines it.
func (c checker) sigilHandler(letter string) string {
	name := "sigil_" + letter
	if c.functions[name] != nil {
		return name
	}
	found := ""
	for qualified := range c.functions {
		if strings.HasSuffix(qualified, "."+name) {
			if found != "" {
				return ""
			}
			found = qualified
		}
	}
	return found
}

// protocols records what the program's protocols declare and which
// functions implement them, and checks that every implementation is whole.
func (c *checker) protocols(p *ast.Program) (string, error) {
	c.declared, c.implementations = map[string]ast.ProtocolFunction{}, map[string][]*ast.Function{}
	names := map[string]ast.Protocol{}
	for _, protocol := range p.Protocols {
		names[protocol.Name] = protocol
		for _, function := range protocol.Functions {
			c.declared[protocol.Name+"."+function.Name] = function
		}
	}
	// Each defimpl block is the functions sharing a protocol and a type.
	blocks := map[string]map[string]bool{}
	first := map[string]*ast.Function{}
	for i := range p.Functions {
		f := &p.Functions[i]
		if f.Protocol == "" {
			continue
		}
		at := func(format string, args ...any) (string, error) {
			return f.Source, diagnostic(f.Line, f.Column, format, args...)
		}
		if _, known := names[f.Protocol]; !known {
			return at("defimpl of %s, which no module declares with defprotocol", f.Protocol)
		}
		key := f.Protocol + "." + f.ProtocolFunction
		wanted, ok := c.declared[key]
		if !ok {
			return at("%s has no function %s", f.Protocol, f.ProtocolFunction)
		}
		if len(f.Params) != len(wanted.Params) {
			return at("%s takes %d arguments, not %d", key, len(wanted.Params), len(f.Params))
		}
		if wanted.Type != f.Type {
			return at("%s returns %s, not %s", key, describeType(wanted.Type), describeType(f.Type))
		}
		for _, other := range c.implementations[key] {
			if other.Params[0].Type == f.Params[0].Type {
				return at("%s is already implemented for %s", f.Protocol, f.For)
			}
		}
		c.implementations[key] = append(c.implementations[key], f)
		block := f.Protocol + " for " + f.Params[0].Type
		if blocks[block] == nil {
			blocks[block], first[block] = map[string]bool{}, f
		}
		blocks[block][f.ProtocolFunction] = true
	}
	for block, defined := range blocks {
		f := first[block]
		for _, function := range names[f.Protocol].Functions {
			if !defined[function.Name] {
				return f.Source, diagnostic(f.Line, f.Column, "the implementation of %s for %s lacks %s", f.Protocol, f.For, function.Name)
			}
		}
	}
	return "", nil
}

func describeType(t string) string {
	if t == "void" {
		return "nothing"
	}
	return t
}

// dispatch turns a call through a protocol into a call of the function that
// implements it for the type of the first argument.
func (c checker) dispatch(e *ast.Expr, scope map[string]string) error {
	if len(e.Args) == 0 {
		return diagnostic(e.Line, e.Column, "%s needs the value it is called on", e.Name)
	}
	t, err := c.expr(e.Args[0], scope)
	if err != nil {
		return err
	}
	for _, f := range c.implementations[e.Name] {
		target := f.Params[0].Type
		if target == t || unify(target, t, set(generic(f)), map[string]string{}) {
			e.Name = f.Name
			return nil
		}
	}
	protocol, _, _ := strings.Cut(e.Name, ".")
	if ast.TypeVariable(t) {
		return diagnostic(e.Line, e.Column, "%s cannot be called on a value of the type variable %s: the implementation is chosen when the program is compiled, so the type must be known here", e.Name, t)
	}
	return diagnostic(e.Line, e.Column, "%s is not implemented for %s", protocol, t)
}

// armType is the type a try arm matches, and makes its pattern an ordinary
// one: an else arm takes the body's value; a catch arm a thrown value of the
// type it names, or of the type the body throws; a rescue arm an exception,
// for name in Exception or a pattern of an exception struct, and otherwise
// the failure's message.
func (c checker) armType(arm *ast.Arm, body string, thrown []string) (string, error) {
	p := arm.Pattern
	fail := func(format string, args ...any) (string, error) {
		return "", diagnostic(p.Line, p.Column, format, args...)
	}
	plain := func(t string) (string, error) {
		if p.Name == "_" {
			*p = ast.Pattern{Kind: "wildcard", Line: p.Line, Column: p.Column}
		} else {
			*p = ast.Pattern{Kind: "name", Name: p.Name, Line: p.Line, Column: p.Column}
		}
		return t, nil
	}
	switch arm.Kind {
	case "else":
		return body, nil
	case "catch":
		if p.Kind == "typed" {
			if problem := c.wellFormed(p.Type, map[string]bool{}); problem != "" {
				return fail("%s", problem)
			}
			return plain(p.Type)
		}
		if len(thrown) > 0 {
			for _, t := range thrown[1:] {
				if t != thrown[0] {
					return fail("this try throws both %s and %s; give each catch arm its type, as in value: %s ->", thrown[0], t, thrown[0])
				}
			}
			return thrown[0], nil
		}
		if p.Kind == "literal" {
			return p.Value.Kind, nil
		}
		if p.Kind == "struct" {
			return p.Name, nil
		}
		return fail("the type of the thrown value is unknown here; write the arm as value: Type ->")
	}
	if p.Kind == "in" {
		decl := c.types[p.Type]
		if decl == nil || !decl.Exception {
			return fail("%s is not an exception; declare it with defexception", p.Type)
		}
		return plain(p.Type)
	}
	if p.Kind == "struct" {
		if decl := c.types[p.Name]; decl != nil && decl.Exception {
			return p.Name, nil
		}
		return fail("%s is not an exception; declare it with defexception", p.Name)
	}
	if p.Kind == "typed" {
		return fail("a rescue arm matches a message or an exception; name: type is for catch")
	}
	return "string", nil
}

// thrownTypes lists the types of the values thrown in a try's body, outside
// any try nested in it that catches them.
func (c checker) thrownTypes(body []ast.Statement) []string {
	var out []string
	seen := map[string]bool{}
	var expr func(*ast.Expr)
	var block func([]ast.Statement)
	expr = func(e *ast.Expr) {
		if e == nil {
			return
		}
		if e.Kind == "call" && e.Name == "throw" && len(e.Args) == 1 && e.Args[0].Type != "" && !seen[e.Args[0].Type] {
			seen[e.Args[0].Type] = true
			out = append(out, e.Args[0].Type)
		}
		if e.Kind == "try" {
			for _, arm := range e.Body[0].Arms {
				if arm.Kind == "catch" {
					return
				}
			}
		}
		expr(e.Left)
		expr(e.Right)
		for _, arg := range e.Args {
			expr(arg)
		}
		for _, key := range e.Keys {
			expr(key)
		}
		block(e.Body)
	}
	block = func(list []ast.Statement) {
		for _, s := range list {
			expr(s.Expr)
			block(s.Then)
			block(s.Else)
			for _, arm := range s.Arms {
				expr(arm.Guard)
				block(arm.Body)
			}
		}
	}
	block(body)
	return out
}

// markupTemplate turns the template of ~h"..." into Markup values joined in
// order: the template's text as it is written, and each interpolated value
// through Markup.of, which escapes strings and keeps markup as it is.
func markupTemplate(template *ast.Expr, at func(ast.Expr) *ast.Expr) *ast.Expr {
	var pieces []*ast.Expr
	for _, part := range template.Args {
		if part.Op == "text" {
			literal := *part
			literal.Op = ""
			pieces = append(pieces, at(ast.Expr{Kind: "call", Name: "Markup.raw", Args: []*ast.Expr{&literal}}))
			continue
		}
		pieces = append(pieces, at(ast.Expr{Kind: "call", Name: "Markup.of", Args: []*ast.Expr{part}}))
	}
	return at(ast.Expr{Kind: "call", Name: "Markup.join", Args: []*ast.Expr{at(ast.Expr{Kind: "list", Args: pieces})}})
}

// markupMismatch is the failure of Markup.of for a value a template cannot
// hold, with the value's type.
var markupMismatch = regexp.MustCompile(`expected Markup, found (\S+)$`)
