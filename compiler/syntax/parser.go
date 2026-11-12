package syntax

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"unicode"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/lexer"
)

// Limits keep hostile or generated input from exhausting memory or the Go
// stack: the parser, checker, formatter and generator all recurse over the tree.
const (
	MaxSourceBytes = 1 << 20
	maxNesting     = 256
	maxChain       = 1024
)

type parser struct {
	tokens         []lexer.Token
	pos, depth     int
	inArm, probing bool
	// condArms is set inside a cond, whose arms begin with a condition
	// rather than a pattern. capture counts the &N placeholders of the
	// enclosing &(...) and is -1 outside one.
	condArms bool
	capture  int
	// comments are the source's comments in order and consumed counts those
	// already attached. keep is set when parsing for the formatter, which
	// puts comments inside bodies back; analysis only keeps the ones above
	// declarations, as documentation.
	comments []lexer.Token
	consumed int
	keep     bool
	// tags are the @tag names waiting for the test or describe that follows.
	tags []string
	// trying counts the try bodies being parsed, where a line starting with
	// rescue, catch or after ends the body.
	trying int
}

// ends reports whether the next token closes the block being parsed.
func (p *parser) ends() bool {
	t := p.peek()
	if t.Kind == lexer.EOF || t.Text == "end" || t.Text == "else" {
		return true
	}
	return p.trying > 0 && t.Kind == lexer.Ident && (t.Text == "rescue" || t.Text == "catch" || t.Text == "after") && p.tokens[p.pos+1].Kind != lexer.Assign && p.tokens[p.pos+1].Kind != lexer.Colon
}

// commentsBefore takes the comments written before a token.
func (p *parser) commentsBefore(t lexer.Token) []string {
	var out []string
	for p.consumed < len(p.comments) {
		c := p.comments[p.consumed]
		if c.Line > t.Line || (c.Line == t.Line && c.Column > t.Column) {
			break
		}
		out = append(out, c.Text)
		p.consumed++
	}
	return out
}

// remarks turns the comments before a token into comment statements, which
// only the formatter sees.
func (p *parser) remarks(t lexer.Token) []ast.Statement {
	if p.probing {
		return nil
	}
	var out []ast.Statement
	for _, text := range p.commentsBefore(t) {
		if p.keep {
			out = append(out, ast.Statement{Kind: "comment", Name: text, Line: t.Line, Column: t.Column})
		}
	}
	return out
}

// descend records one level of grammar recursion; callers defer p.ascend().
func (p *parser) descend() error {
	p.depth++
	if p.depth > maxNesting {
		t := p.peek()
		return diagnostic(t.Line, t.Column, "nesting exceeds %d levels", maxNesting)
	}
	return nil
}
func (p *parser) ascend() { p.depth-- }
func chainLimit(t lexer.Token) error {
	return diagnostic(t.Line, t.Column, "expression chains more than %d operations", maxChain)
}

func (p *parser) peek() lexer.Token { return p.tokens[p.pos] }
func (p *parser) expect(kind lexer.Kind, text string) (lexer.Token, error) {
	t := p.peek()
	if t.Kind != kind || (text != "" && t.Text != text) {
		return t, fmt.Errorf("%d:%d: expected %s %q, found %s %q", t.Line, t.Column, kind, text, t.Kind, t.Text)
	}
	p.pos++
	return t, nil
}
func Parse(source string) (ast.Program, error) { return parse(source, true) }

// ParseModule parses one file for linking: clauses are merged, types unchecked.
func ParseModule(source string) (ast.Program, error) { return parse(source, false) }

// ParseSyntax parses one file exactly as written, for formatting.
func ParseSyntax(source string) (ast.Program, error) { return parse(source, false, true) }
func parse(source string, check bool, raw ...bool) (ast.Program, error) {
	if len(source) > MaxSourceBytes {
		return ast.Program{}, diagnostic(1, 1, "source exceeds %d bytes", MaxSourceBytes)
	}
	ts, comments, err := lexer.ScanWithComments(source)
	if err != nil {
		return ast.Program{}, err
	}
	p := parser{tokens: ts, capture: -1, comments: comments, keep: len(raw) > 0}
	leading := p.commentsBefore(p.peek())
	if _, err = p.expect(lexer.Ident, "defmodule"); err != nil {
		return ast.Program{}, err
	}
	module, err := p.expect(lexer.Ident, "")
	if err != nil {
		return ast.Program{}, err
	}
	if module.Text == "" || !unicode.IsUpper([]rune(module.Text)[0]) {
		return ast.Program{}, fmt.Errorf("%d:%d: module must begin with uppercase letter", module.Line, module.Column)
	}
	if _, err = p.expect(lexer.Ident, "do"); err != nil {
		return ast.Program{}, err
	}
	result := ast.Program{Module: module.Text, ModuleLine: module.Line, ModuleColumn: module.Column, Leading: leading}
	type pending struct {
		types, functions int
		doc              []string
	}
	var docs, docstrings []pending
	for {
		keyword := p.peek()
		// The comments above a declaration document the first thing it adds.
		if doc := p.commentsBefore(keyword); len(doc) > 0 {
			docs = append(docs, pending{len(result.Types), len(result.Functions), doc})
		}
		// An import may stand anywhere among the module's declarations.
		if keyword.Text == "import" && p.tokens[p.pos+1].Kind == lexer.String {
			p.pos++
			path, _ := p.expect(lexer.String, "")
			value, err := strconv.Unquote(path.Text)
			if err != nil {
				return result, err
			}
			result.Imports = append(result.Imports, value)
			result.ImportPositions = append(result.ImportPositions, ast.Position{Line: keyword.Line, Column: keyword.Column})
			continue
		}
		if keyword.Text == "require" {
			p.pos++
			require, err := p.require(keyword)
			if err != nil {
				return ast.Program{}, err
			}
			result.Requires = append(result.Requires, require)
			continue
		}
		if keyword.Text == "extern" && p.tokens[p.pos+1].Text == "type" && p.tokens[p.pos+2].Kind == lexer.Ident {
			p.pos += 2
			name, _ := p.expect(lexer.Ident, "")
			decl := ast.TypeDecl{Kind: "extern", Name: name.Text, Local: name.Text, Line: name.Line, Column: name.Column}
			if !unicode.IsUpper([]rune(name.Text)[0]) || strings.Contains(name.Text, ".") {
				return ast.Program{}, diagnostic(name.Line, name.Column, "type name must be one capitalized word")
			}
			if _, err = p.expect(lexer.Assign, ""); err != nil {
				return ast.Program{}, err
			}
			target, err := p.expect(lexer.String, "")
			if err != nil {
				return ast.Program{}, err
			}
			if decl.Extern, err = strconv.Unquote(target.Text); err != nil || !externType.MatchString(decl.Extern) {
				return ast.Program{}, diagnostic(target.Line, target.Column, "extern type target must be \"import/path.Type\" or \"*import/path.Type\"")
			}
			result.Types = append(result.Types, decl)
			continue
		}
		if (keyword.Text == "struct" || keyword.Text == "type" || keyword.Text == "defexception") && p.tokens[p.pos+1].Kind == lexer.Ident {
			decl, err := p.typeDecl()
			if err != nil {
				return ast.Program{}, err
			}
			result.Types = append(result.Types, decl)
			continue
		}
		if keyword.Kind == lexer.At {
			// @moduledoc documents the module; @doc and @typedoc document
			// the function or type declared next.
			if kind := p.tokens[p.pos+1]; kind.Text == "moduledoc" || kind.Text == "doc" || kind.Text == "typedoc" {
				p.pos += 2
				text := ""
				if p.peek().Text != "false" {
					value, err := p.expect(lexer.String, "")
					if err != nil {
						return ast.Program{}, diagnostic(kind.Line, kind.Column, "@%s takes a string, usually a heredoc", kind.Text)
					}
					text, _ = strconv.Unquote(value.Text)
				} else {
					p.pos++
				}
				if kind.Text == "moduledoc" {
					result.ModuleDoc = text
				} else {
					docstrings = append(docstrings, pending{len(result.Types), len(result.Functions), []string{text, kind.Text, strconv.Itoa(kind.Line), strconv.Itoa(kind.Column)}})
				}
				continue
			}
			if err := p.tag(&result); err != nil {
				return ast.Program{}, err
			}
			continue
		}
		if keyword.Kind == lexer.Ident && keyword.Text == "doctest" && p.tokens[p.pos+1].Kind == lexer.Ident {
			p.pos += 2
			result.Doctests = append(result.Doctests, p.tokens[p.pos-1].Text)
			continue
		}
		if keyword.Kind == lexer.Ident && (keyword.Text == "test" || keyword.Text == "describe" || keyword.Text == "setup" || keyword.Text == "setup_all") {
			if next := p.tokens[p.pos+1]; next.Kind == lexer.String || keyword.Text == "setup" || keyword.Text == "setup_all" {
				if err := p.tests(&result, ""); err != nil {
					return ast.Program{}, err
				}
				continue
			}
		}
		if keyword.Text == "use" && p.tokens[p.pos+1].Kind == lexer.Ident && unicode.IsUpper([]rune(p.tokens[p.pos+1].Text)[0]) {
			use, err := p.use()
			if err != nil {
				return ast.Program{}, err
			}
			result.Uses = append(result.Uses, use)
			continue
		}
		if keyword.Text == "defmacro" {
			macro, err := p.macro()
			if err != nil {
				return ast.Program{}, err
			}
			for _, other := range result.Macros {
				if other.Name == macro.Name {
					return ast.Program{}, diagnostic(macro.Line, macro.Column, "macro %s is defined twice", macro.Name)
				}
			}
			result.Macros = append(result.Macros, macro)
			continue
		}
		if keyword.Text == "defprotocol" {
			protocol, err := p.protocol()
			if err != nil {
				return ast.Program{}, err
			}
			for _, other := range result.Protocols {
				if other.Name == protocol.Name {
					return ast.Program{}, diagnostic(protocol.Line, protocol.Column, "protocol %s is declared twice", protocol.Name)
				}
			}
			result.Protocols = append(result.Protocols, protocol)
			continue
		}
		if keyword.Text == "defimpl" {
			implemented, err := p.implementation(len(result.Functions))
			if err != nil {
				return ast.Program{}, err
			}
			result.Functions = append(result.Functions, implemented...)
			continue
		}
		if keyword.Text != "def" && keyword.Text != "defp" && keyword.Text != "extern" {
			break
		}
		f, err := p.function()
		if err != nil {
			return ast.Program{}, err
		}
		result.Functions = append(result.Functions, f)
	}
	for i, entry := range docs {
		limitTypes, limitFunctions := len(result.Types), len(result.Functions)
		if i+1 < len(docs) {
			limitTypes, limitFunctions = docs[i+1].types, docs[i+1].functions
		}
		switch {
		case entry.types < limitTypes:
			result.Types[entry.types].Comments = entry.doc
		case entry.functions < limitFunctions:
			result.Functions[entry.functions].Comments = entry.doc
		default:
			// Nothing was declared after these comments.
			result.Trailing = append(result.Trailing, entry.doc...)
		}
	}
	// A docstring belongs to whatever is declared right after it.
	for _, entry := range docstrings {
		switch {
		case entry.types < len(result.Types) && (entry.functions >= len(result.Functions) || result.Types[entry.types].Line < result.Functions[entry.functions].Line):
			result.Types[entry.types].Doc = entry.doc[0]
		case entry.functions < len(result.Functions):
			result.Functions[entry.functions].Doc = entry.doc[0]
		case entry.doc[0] != "":
			// Documentation with nothing declared after it documents nothing.
			line, _ := strconv.Atoi(entry.doc[2])
			column, _ := strconv.Atoi(entry.doc[3])
			return ast.Program{}, diagnostic(line, column, "@%s is not followed by anything to document", entry.doc[1])
		}
	}
	result.Trailing = append(result.Trailing, p.commentsBefore(p.peek())...)
	if _, err = p.expect(lexer.Ident, "end"); err != nil {
		return ast.Program{}, err
	}
	result.Trailing = append(result.Trailing, p.commentsBefore(p.peek())...)
	if _, err = p.expect(lexer.EOF, ""); err != nil {
		return ast.Program{}, err
	}
	if len(raw) == 0 {
		if err = lower(&result); err != nil {
			return ast.Program{}, err
		}
		// Templates are lowered like the functions they will become part
		// of, each as the body of a function of its own.
		for i := range result.Macros {
			macro := &result.Macros[i]
			template := ast.Program{Module: result.Module, Types: result.Types, Functions: macro.Definitions}
			if macro.Definitions == nil {
				template.Functions = []ast.Function{{Name: macro.Name, Type: "integer", Body: macro.Body, Line: macro.Line, Column: macro.Column}}
			}
			if err = lower(&template); err != nil {
				return ast.Program{}, err
			}
			if macro.Definitions == nil {
				macro.Body = template.Functions[0].Body
			} else {
				macro.Definitions = template.Functions
			}
		}
	}
	if check {
		if len(result.Imports) > 0 {
			return ast.Program{}, fmt.Errorf("imports require a file build")
		}
		if err = ExpandMacros([]*ast.Program{&result}); err != nil {
			return ast.Program{}, err
		}
		if err = analyze(&result); err != nil {
			return ast.Program{}, err
		}
	}
	// Retain inspection fields for the original literal-only parser API.
	for _, f := range result.Functions {
		if f.Name == "main" {
			result.Statements = f.Body
		}
	}
	if len(result.Statements) == 1 {
		s := result.Statements[0]
		e := s.Expr
		if s.Kind == "output" && e.Kind == "literal" {
			v := e.Value.Text
			result.Output = v
			result.Statements[0].Output = &v
		}
		if s.Kind == "assert" && e.Kind == "literal" {
			v := e.Value.Boolean
			result.Assertion = &v
		}
		if s.Kind == "assert" && e.Kind == "binary" && e.Left.Kind == "literal" && e.Right.Kind == "literal" {
			result.Comparison = &ast.Comparison{Left: e.Left.Value, Right: e.Right.Value, Operator: e.Op}
		}
	}
	return result, nil
}

var (
	modulePath    = regexp.MustCompile(`^[A-Za-z0-9_~-]+([./][A-Za-z0-9_~-]+)*$`)
	moduleVersion = regexp.MustCompile(`^v[0-9][0-9A-Za-z.+-]*$`)
	externTarget  = regexp.MustCompile(`^((\.\.?/)+)?[A-Za-z0-9_~-]+([./][A-Za-z0-9_~-]+)*\.[A-Z][A-Za-z0-9_]*$`)
	externType    = regexp.MustCompile(`^\*?((\.\.?/)+)?[A-Za-z0-9_~-]+([./][A-Za-z0-9_~-]+)*\.[A-Z][A-Za-z0-9_]*$`)
)

// require parses a Go module dependency: require "module/path" "v1.2.3".
func (p *parser) require(keyword lexer.Token) (ast.Require, error) {
	invalid := diagnostic(keyword.Line, keyword.Column, "require needs a module path and a version such as \"v1.2.3\"")
	require := ast.Require{Line: keyword.Line, Column: keyword.Column}
	for _, field := range []*string{&require.Path, &require.Version} {
		token, err := p.expect(lexer.String, "")
		if err != nil {
			return require, invalid
		}
		if *field, err = strconv.Unquote(token.Text); err != nil {
			return require, invalid
		}
	}
	if !modulePath.MatchString(require.Path) || !moduleVersion.MatchString(require.Version) {
		return require, invalid
	}
	return require, nil
}

// ExternLocal reports whether an extern target names a Go package directory
// relative to the declaring file, and splits the target into package and symbol.
//
// The symbol is Function, or Type.Method when the component before the last
// one, within the final path element, is capitalized: "bytes.Buffer.Len" is a
// method, "gopkg.in/yaml.v3.Marshal" is a function of package yaml.v3.
func ExternLocal(target string) (pkg, symbol string, local bool) {
	index := strings.LastIndex(target, ".")
	pkg, symbol = target[:index], target[index+1:]
	element := pkg[strings.LastIndex(pkg, "/")+1:]
	if dot := strings.LastIndex(element, "."); dot > 0 && unicode.IsUpper([]rune(element[dot+1:])[0]) {
		split := len(pkg) - len(element) + dot
		pkg, symbol = pkg[:split], pkg[split+1:]+"."+symbol
	}
	return pkg, symbol, strings.HasPrefix(pkg, "./") || strings.HasPrefix(pkg, "../")
}
func (p *parser) function() (ast.Function, error) {
	extern, private := p.peek().Text == "extern", p.peek().Text == "defp"
	p.pos++
	name, err := p.expect(lexer.Ident, "")
	if err != nil {
		return ast.Function{}, err
	}
	f := ast.Function{Name: name.Text, Line: name.Line, Column: name.Column, Type: "void", Private: private}
	if _, err = p.expect(lexer.LParen, ""); err != nil {
		return f, err
	}
	if p.peek().Kind != lexer.RParen {
		for {
			pattern, err := p.pattern()
			if err != nil {
				return f, err
			}
			param := ast.Parameter{Line: pattern.Line, Column: pattern.Column}
			if pattern.Kind == "name" {
				param.Name = pattern.Name
			} else {
				param.Pattern = pattern
			}
			if p.peek().Kind == lexer.Colon {
				p.pos++
				if param.Type, err = p.typeName(); err != nil {
					return f, err
				}
			}
			if extern && (param.Pattern != nil || param.Type == "") {
				return f, diagnostic(param.Line, param.Column, "extern parameters are typed names")
			}
			if p.peek().Kind == lexer.Default {
				mark := p.peek()
				p.pos++
				if extern || param.Pattern != nil {
					return f, diagnostic(mark.Line, mark.Column, "only a named parameter of a function can have a default value")
				}
				if param.Default, err = p.expr(0); err != nil {
					return f, err
				}
				if !constantDefault(param.Default) {
					return f, diagnostic(mark.Line, mark.Column, "a default value is a constant: literals, lists, tuples and maps of them, none, some(...), ok(...) or error(...)")
				}
			} else if len(f.Params) > 0 && f.Params[len(f.Params)-1].Default != nil {
				return f, diagnostic(param.Line, param.Column, "a parameter without a default value cannot follow one that has it")
			}
			f.Params = append(f.Params, param)
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
	}
	if _, err = p.expect(lexer.RParen, ""); err != nil {
		return f, err
	}
	if p.peek().Kind == lexer.Colon {
		p.pos++
		typ, e := p.typeName()
		if e != nil {
			return f, e
		}
		f.Type = typ
	}
	if extern {
		if _, err = p.expect(lexer.Assign, ""); err != nil {
			return f, err
		}
		target, err := p.expect(lexer.String, "")
		if err != nil {
			return f, err
		}
		if f.Extern, err = strconv.Unquote(target.Text); err != nil || !externTarget.MatchString(f.Extern) {
			return f, diagnostic(target.Line, target.Column, "extern target must be \"import/path.Function\", \"import/path.Type.Method\" or \"./directory.Function\"")
		}
		return f, nil
	}
	if p.peek().Text == "when" {
		p.pos++
		if f.Guard, err = p.expr(0); err != nil {
			return f, err
		}
	}
	if _, err = p.expect(lexer.Ident, "do"); err != nil {
		return f, err
	}
	f.Body, err = p.block()
	if err != nil {
		return f, err
	}
	_, err = p.expect(lexer.Ident, "end")
	return f, err
}

// newLine reports whether the next token starts a line. A "(", "[" or "-"
// there begins a new statement instead of continuing the expression above.
func (p *parser) newLine() bool {
	return p.pos > 0 && p.peek().Line > p.tokens[p.pos-1].Line
}
func (p *parser) block(inCase ...bool) ([]ast.Statement, error) {
	defer p.ascend()
	if err := p.descend(); err != nil {
		return nil, err
	}
	old := p.inArm
	defer func() { p.inArm = old }()
	if len(inCase) > 0 && inCase[0] {
		p.inArm = true
	}
	var body []ast.Statement
	for !p.ends() {
		if len(inCase) > 0 && inCase[0] && p.armStart() {
			break
		}
		t := p.peek()
		body = append(body, p.remarks(t)...)
		s := ast.Statement{Line: t.Line, Column: t.Column}
		switch {
		case t.Kind == lexer.Ident && (t.Text == "if" || t.Text == "unless" || t.Text == "case" || t.Text == "cond" || t.Text == "with"):
			if err := p.compound(&s); err != nil {
				return nil, err
			}
		case t.Kind == lexer.Ident && t.Text == "check" && p.tokens[p.pos+1].Text == "all" && p.tokens[p.pos+1].Kind == lexer.Ident:
			if err := p.checkAll(&s); err != nil {
				return nil, err
			}
		case t.Text == "return":
			p.pos++
			s.Kind = "return"
			e, err := p.expr(0)
			if err != nil {
				return nil, err
			}
			s.Expr = e

		case t.Kind == lexer.Ident && receiveForms[t.Text] && p.tokens[p.pos+1].Kind == lexer.LParen:
			// assert_receive(pid, pattern when guard, timeout): the second
			// argument is a pattern, not a value.
			p.pos += 2
			pid, err := p.expr(0)
			if err != nil {
				return nil, err
			}
			if _, err = p.expect(lexer.Comma, ""); err != nil {
				return nil, diagnostic(t.Line, t.Column, "%s takes a process and a pattern: %s(self, pattern)", t.Text, t.Text)
			}
			if s.Pattern, err = p.pattern(); err != nil {
				return nil, err
			}
			s.Kind, s.Name = "receive", t.Text
			s.Expr = &ast.Expr{Kind: "call", Name: t.Text, Args: []*ast.Expr{pid}, Line: t.Line, Column: t.Column}
			if p.peek().Text == "when" {
				p.pos++
				guard, err := p.expr(0)
				if err != nil {
					return nil, err
				}
				s.Arms = []ast.Arm{{Guard: guard}}
			}
			// After the pattern: a timeout and then a failure message for
			// the receive forms, a failure message alone for the received
			// forms, which do not wait.
			for limit := receiveArguments(t.Text); p.peek().Kind == lexer.Comma && len(s.Expr.Args) <= limit; {
				p.pos++
				extra, err := p.expr(0)
				if err != nil {
					return nil, err
				}
				s.Expr.Args = append(s.Expr.Args, extra)
			}
			if _, err = p.expect(lexer.RParen, ""); err != nil {
				return nil, err
			}

		case p.assignmentStart():
			pat, err := p.pattern()
			if err != nil {
				return nil, err
			}
			s.Pattern = pat
			s.Kind = "bind"
			s.Name = pat.Name
			if p.peek().Kind == lexer.Colon {
				p.pos++
				s.Declared, err = p.typeName()
				if err != nil {
					return nil, err
				}
			}
			if _, err = p.expect(lexer.Assign, ""); err != nil {
				return nil, err
			}
			s.Expr, err = p.expr(0)
			if err != nil {
				return nil, err
			}
			if err = p.doBlock(s.Expr); err != nil {
				return nil, err
			}

		default:
			e, err := p.expr(0)
			if err != nil {
				return nil, err
			}
			if err = p.doBlock(e); err != nil {
				return nil, err
			}
			if e.Op == "do" && (e.Name == "IO.puts" || e.Name == "assert") {
				return nil, diagnostic(t.Line, t.Column, "only a macro takes a do ... end block, and %s is not one", e.Name)
			}
			s.Expr = e
			s.Kind = "call"
			if e.Kind == "call" {
				// IO.puts(device, text) is a library call.
				if e.Name == "IO.puts" && len(e.Args) != 2 {
					s.Kind = "output"
				}
				if e.Name == "assert" {
					s.Kind = "assert"
				}
				if s.Kind != "call" {
					if len(e.Args) != 1 {
						return nil, fmt.Errorf("%d:%d: %s requires one argument", t.Line, t.Column, e.Name)
					}
					s.Expr = e.Args[0]
				}
			}
		}
		body = append(body, s)
	}
	body = append(body, p.remarks(p.peek())...)
	if len(body) == 0 {
		t := p.peek()
		return nil, fmt.Errorf("%d:%d: block requires a statement", t.Line, t.Column)
	}
	return body, nil
}

// Precedence is how tightly a binary operator binds; higher binds tighter.
func Precedence(op string) int { return precedence(lexer.Token{Kind: lexer.Operator, Text: op}) }

func precedence(t lexer.Token) int {
	switch t.Text {
	case "or", "|||", "^^^":
		return 1
	case "and", "&&&":
		return 2
	case "==", "!=", "<", "<=", ">", ">=", "in", "=~":
		return 3
	case "|>", "<<<", ">>>":
		return 4
	case "<>", "++", "--", "..":
		return 5
	case "+", "-":
		return 6
	case "*", "/", "%":
		return 7
	case "**":
		return 8
	}
	return -1
}
func (p *parser) expr(min int) (*ast.Expr, error) {
	defer p.ascend()
	if err := p.descend(); err != nil {
		return nil, err
	}
	left, err := p.primary()
	if err != nil {
		return nil, err
	}
	compared := false
	for links := 0; ; links++ {
		t := p.peek()
		prec := precedence(t)
		if prec < min || (t.Text == "-" && p.newLine()) {
			break
		}
		if links >= maxChain {
			return nil, chainLimit(t)
		}
		if prec == 3 && compared {
			return nil, fmt.Errorf("%d:%d: chained comparisons are unsupported", t.Line, t.Column)
		}
		p.pos++
		next := prec + 1
		if t.Text == "**" {
			next = prec // right associative
		}
		right, err := p.expr(next)
		if err != nil {
			return nil, err
		}
		if t.Text == ".." {
			left = &ast.Expr{Kind: "range", Left: left, Right: right, Line: t.Line, Column: t.Column}
			if step := p.peek(); step.Kind == lexer.Operator && step.Text == "//" {
				p.pos++
				by, err := p.expr(6)
				if err != nil {
					return nil, err
				}
				left.Args = []*ast.Expr{by}
			}
			continue
		}
		if t.Text == "=~" {
			// text =~ regex is String.match?(text, regex).
			left = &ast.Expr{Kind: "call", Name: "String.match?", Args: []*ast.Expr{left, right}, Line: t.Line, Column: t.Column}
			compared = true
			continue
		}
		if t.Text == "in" {
			left = &ast.Expr{Kind: "in", Left: left, Right: right, Line: t.Line, Column: t.Column}
			compared = true
			continue
		}
		if t.Text == "|>" {
			if right.Kind != "call" {
				return nil, diagnostic(t.Line, t.Column, "pipe target must be a function call")
			}
			right.Pipe = true
			right.Args = append([]*ast.Expr{left}, right.Args...)
			left = right
			continue
		}
		left = &ast.Expr{Kind: "binary", Op: t.Text, Left: left, Right: right, Line: t.Line, Column: t.Column}
		if prec == 3 {
			compared = true
		}
	}
	return left, nil
}
func (p *parser) primary() (*ast.Expr, error) {
	defer p.ascend()
	if err := p.descend(); err != nil {
		return nil, err
	}
	e, err := p.atom()
	if err != nil {
		return nil, err
	}
	for links := 0; p.peek().Kind == lexer.Dot || ((p.peek().Kind == lexer.LBracket || p.peek().Kind == lexer.LParen) && !p.newLine()); links++ {
		if links >= maxChain {
			return nil, chainLimit(p.peek())
		}
		if p.peek().Kind == lexer.Dot {
			p.pos++
			if p.peek().Kind == lexer.LParen {
				// (expression).(arguments) calls the function it gives.
				continue
			}
			name, err := p.expect(lexer.Ident, "")
			if err != nil {
				return nil, err
			}
			if e, err = fieldChain(e, name, strings.Split(name.Text, ".")); err != nil {
				return nil, err
			}
			continue
		}
		if p.peek().Kind == lexer.LParen {
			t := p.peek()
			p.pos++
			args := []*ast.Expr{}
			if p.peek().Kind != lexer.RParen {
				for {
					arg, err := p.expr(0)
					if err != nil {
						return nil, err
					}
					args = append(args, arg)
					if p.peek().Kind != lexer.Comma {
						break
					}
					p.pos++
				}
			}
			if _, err := p.expect(lexer.RParen, ""); err != nil {
				return nil, err
			}
			if e.Kind == "name" && !strings.Contains(e.Name, ".") {
				// f.(x) and (f)(x) are the call f(x), which reaches the
				// binding f as it reaches a function.
				e = &ast.Expr{Kind: "call", Name: e.Name, Args: args, Line: e.Line, Column: e.Column}
				continue
			}
			e = &ast.Expr{Kind: "invoke", Left: e, Args: args, Line: t.Line, Column: t.Column}
			continue
		}
		if !p.probing && ((p.inArm && p.armStart()) || p.assignmentStart()) {
			break
		}
		t := p.peek()
		p.pos++
		index, err := p.expr(0)
		if err != nil {
			return nil, err
		}
		if _, err = p.expect(lexer.RBracket, ""); err != nil {
			return nil, err
		}
		e = &ast.Expr{Kind: "index", Left: e, Right: index, Line: t.Line, Column: t.Column}
	}
	return e, nil
}
func (p *parser) atom() (*ast.Expr, error) {
	t := p.peek()
	e := &ast.Expr{Line: t.Line, Column: t.Column}
	if t.Text == "fn" && t.Kind == lexer.Ident {
		if p.tokens[p.pos+1].Kind == lexer.LParen {
			return p.closure()
		}
		return p.lambda()
	}
	if t.Kind == lexer.Ident && ((t.Text == "try" && p.tokens[p.pos+1].Text == "do") || t.Text == "for") {
		old, oldCond, oldTrying := p.inArm, p.condArms, p.trying
		p.inArm, p.condArms, p.trying = false, false, 0
		defer func() { p.inArm, p.condArms, p.trying = old, oldCond, oldTrying }()
		if t.Text == "for" {
			return p.comprehension()
		}
		return p.try()
	}
	if t.Kind == lexer.Sigil {
		p.pos++
		parts := strings.SplitN(t.Text, "\x00", 3)
		e.Kind, e.Name, e.Value, e.Op = "sigil", parts[0], ast.Literal{Kind: "string", Text: parts[1]}, parts[2]
		// The lower-case text sigils interpolate #{...}; the template is
		// kept beside the text so that the formatter still sees the source.
		if unicode.IsLower([]rune(e.Name)[0]) && strings.Contains(parts[1], "#{") {
			template, err := p.sigilTemplate(t, parts[1])
			if err != nil {
				return nil, err
			}
			e.Left = template
		}
		return e, nil
	}
	if (t.Text == "if" || t.Text == "unless" || t.Text == "case" || t.Text == "cond" || t.Text == "with") && t.Kind == lexer.Ident {
		// An if or case in value position: its body is that one statement.
		statement := ast.Statement{Line: t.Line, Column: t.Column}
		old, oldCond := p.inArm, p.condArms
		p.inArm, p.condArms = false, false
		err := p.compound(&statement)
		p.inArm, p.condArms = old, oldCond
		if err != nil {
			return nil, err
		}
		e.Kind = "value"
		e.Body = []ast.Statement{statement}
		return e, nil
	}

	if t.Kind == lexer.LParen {
		p.pos++
		v, err := p.expr(0)
		if err != nil {
			return nil, err
		}
		_, err = p.expect(lexer.RParen, "")
		return v, err
	}
	if t.Text == "-" || t.Text == "not" || t.Text == "~~~" {
		p.pos++
		// Permit the minimum signed integer without accepting its positive magnitude.
		if t.Text == "-" && p.peek().Kind == lexer.Integer {
			n := p.peek()
			p.pos++
			v, err := parseInteger("-" + n.Text)
			if err != nil {
				return nil, fmt.Errorf("%d:%d: integer outside signed 64-bit range", t.Line, t.Column)
			}
			e.Kind = "literal"
			e.Value = ast.Literal{Kind: "integer", Integer: v}
			return e, nil
		}
		if t.Text == "-" && p.peek().Kind == lexer.Float {
			v, err := p.atom()
			if err != nil {
				return nil, err
			}
			v.Value.Float = -v.Value.Float
			v.Line, v.Column = t.Line, t.Column
			return v, nil
		}
		v, err := p.primary()
		if err != nil {
			return nil, err
		}
		e.Kind = "unary"
		e.Op = t.Text
		e.Left = v
		return e, nil
	}
	switch t.Kind {
	case lexer.StructStart:
		p.pos++
		e.Kind = "struct"
		e.Name = t.Text
		if _, err := p.expect(lexer.LBrace, ""); err != nil {
			return nil, err
		}
		if !(p.peek().Kind == lexer.Ident && p.tokens[p.pos+1].Kind == lexer.Colon) {
			base, err := p.expr(0)
			if err != nil {
				return nil, err
			}
			if _, err = p.expect(lexer.Bar, ""); err != nil {
				return nil, err
			}
			e.Left = base
		}
		for {
			label, err := p.expect(lexer.Ident, "")
			if err != nil {
				return nil, err
			}
			if _, err = p.expect(lexer.Colon, ""); err != nil {
				return nil, err
			}
			value, err := p.expr(0)
			if err != nil {
				return nil, err
			}
			e.Labels = append(e.Labels, label.Text)
			e.Args = append(e.Args, value)
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
		if _, err := p.expect(lexer.RBrace, ""); err != nil {
			return nil, err
		}
	case lexer.Amp:
		p.pos++
		if next := p.peek(); next.Kind == lexer.Integer && p.capture >= 0 {
			// &1, &2, ... inside &(...) name its parameters.
			index, err := strconv.Atoi(next.Text)
			if err != nil || index < 1 || index > 16 {
				return nil, diagnostic(next.Line, next.Column, "capture placeholders are &1 to &16")
			}
			p.pos++
			if index > p.capture {
				p.capture = index
			}
			e.Kind, e.Name = "name", "&"+next.Text
			return e, nil
		}
		// A capture is &(expression), & expression, or &function(arguments),
		// with &1, &2, ... standing for its parameters. A bare &name is a
		// reference to that function.
		parenthesized := p.peek().Kind == lexer.LParen
		call := p.peek().Kind == lexer.Ident && p.tokens[p.pos+1].Kind == lexer.LParen && p.tokens[p.pos+1].Line == p.peek().Line
		if parenthesized || call || p.peek().Kind == lexer.Amp {
			if p.capture >= 0 {
				return nil, diagnostic(t.Line, t.Column, "captures cannot be nested")
			}
			if parenthesized {
				p.pos++
			}
			p.capture = 0
			body, err := p.expr(0)
			count := p.capture
			p.capture = -1
			if err != nil {
				return nil, err
			}
			if parenthesized {
				if _, err = p.expect(lexer.RParen, ""); err != nil {
					return nil, err
				}
			}
			if count == 0 {
				return nil, diagnostic(t.Line, t.Column, "a capture needs at least &1")
			}
			e.Kind, e.Left, e.Value = "capture", body, ast.Literal{Kind: "integer", Integer: int64(count)}
			return e, nil
		}
		name, err := p.expect(lexer.Ident, "")
		if err != nil {
			return nil, err
		}
		e.Kind = "funcref"
		e.Name = name.Text
		// &name/arity names one arity of the function; Op keeps it.
		if slash := p.peek(); slash.Kind == lexer.Operator && slash.Text == "/" && p.tokens[p.pos+1].Kind == lexer.Integer {
			e.Op = p.tokens[p.pos+1].Text
			p.pos += 2
		}
	case lexer.MapStart:
		p.pos++
		e.Kind = "map"
		if p.peek().Kind != lexer.RBrace {
			for {
				key, err := p.expr(0)
				if err != nil {
					return nil, err
				}
				if _, err = p.expect(lexer.Pair, ""); err != nil {
					return nil, err
				}
				value, err := p.expr(0)
				if err != nil {
					return nil, err
				}
				e.Keys = append(e.Keys, key)
				e.Args = append(e.Args, value)
				if p.peek().Kind != lexer.Comma {
					break
				}
				p.pos++
			}
		}
		if _, err := p.expect(lexer.RBrace, ""); err != nil {
			return nil, err
		}
	case lexer.LBracket, lexer.LBrace:
		p.pos++
		end := lexer.RBracket
		e.Kind = "list"
		if t.Kind == lexer.LBrace {
			end = lexer.RBrace
			e.Kind = "tuple"
		}
		if p.peek().Kind != end {
			for {
				// [name: value] is a keyword list: each pair is the tuple
				// {:name, value}.
				if key := p.peek(); t.Kind == lexer.LBracket && key.Kind == lexer.Ident && p.tokens[p.pos+1].Kind == lexer.Colon {
					p.pos += 2
					value, err := p.expr(0)
					if err != nil {
						return nil, err
					}
					name := &ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "atom", Text: key.Text}, Line: key.Line, Column: key.Column}
					e.Args = append(e.Args, &ast.Expr{Kind: "tuple", Op: "keyword", Args: []*ast.Expr{name, value}, Line: key.Line, Column: key.Column})
					if p.peek().Kind != lexer.Comma {
						break
					}
					p.pos++
					continue
				}
				arg, err := p.expr(0)
				if err != nil {
					return nil, err
				}
				e.Args = append(e.Args, arg)
				// [first, second | rest] puts elements in front of a list,
				// which is kept in Right.
				if t.Kind == lexer.LBracket && p.peek().Kind == lexer.Bar {
					p.pos++
					if e.Right, err = p.expr(0); err != nil {
						return nil, err
					}
					break
				}
				if p.peek().Kind != lexer.Comma {
					break
				}
				p.pos++
			}
		}
		if _, err := p.expect(end, ""); err != nil {
			return nil, err
		}
	case lexer.Integer:
		v, err := parseInteger(t.Text)
		if err != nil {
			return nil, fmt.Errorf("%d:%d: integer outside signed 64-bit range", t.Line, t.Column)
		}
		p.pos++
		e.Kind = "literal"
		e.Value = ast.Literal{Kind: "integer", Integer: v}
		if strings.ContainsAny(t.Text, "_xob") {
			// The spelling is kept for the formatter: 0xFF stays 0xFF.
			e.Value.Text = t.Text
		}
	case lexer.Float:
		v, err := strconv.ParseFloat(strings.ReplaceAll(t.Text, "_", ""), 64)
		if err != nil {
			return nil, fmt.Errorf("%d:%d: float outside 64-bit range", t.Line, t.Column)
		}
		p.pos++
		e.Kind = "literal"
		e.Value = ast.Literal{Kind: "float", Float: v}
	case lexer.Template:
		p.pos++
		return p.template(t)
	case lexer.Atom:
		p.pos++
		e.Kind = "literal"
		e.Value = ast.Literal{Kind: "atom", Text: t.Text}
	case lexer.String:
		v, err := strconv.Unquote(t.Text)
		if err != nil {
			return nil, err
		}
		p.pos++
		e.Kind = "literal"
		e.Value = ast.Literal{Kind: "string", Text: v}
	case lexer.Ident:
		p.pos++
		if t.Text == "true" || t.Text == "false" {
			e.Kind = "literal"
			e.Value = ast.Literal{Kind: "boolean", Boolean: t.Text == "true"}
			return e, nil
		}
		e.Kind = "name"
		e.Name = t.Text
		if strings.HasSuffix(t.Text, ".") && p.peek().Kind == lexer.LParen && !p.newLine() && !unicode.IsUpper([]rune(t.Text)[0]) {
			// f.(x) calls a function value, as in Elixir; the call itself is
			// parsed with what follows a primary expression.
			segments := strings.Split(strings.TrimSuffix(t.Text, "."), ".")
			e.Name = segments[0]
			return fieldChain(e, t, segments[1:])
		}
		if segments := strings.Split(t.Text, "."); len(segments) > 1 && !unicode.IsUpper([]rune(t.Text)[0]) {
			e.Name = segments[0]
			return fieldChain(e, t, segments[1:])
		}
		if p.peek().Kind == lexer.LParen && !p.newLine() {
			p.pos++
			e.Kind = "call"
			if p.peek().Kind != lexer.RParen {
				for {
					arg, err := p.expr(0)
					if err != nil {
						return nil, err
					}
					e.Args = append(e.Args, arg)
					if p.peek().Kind != lexer.Comma {
						break
					}
					p.pos++
				}
			}
			if _, err := p.expect(lexer.RParen, ""); err != nil {
				return nil, err
			}
		}
	default:
		return nil, fmt.Errorf("%d:%d: expected expression, found %q", t.Line, t.Column, t.Text)
	}
	return e, nil
}

// memberName accepts the names of variants and fields, which are always
// written after a type or a value and a dot: besides binding names, the
// names of the oldest builtins, such as get and length, which a binding may
// not take.
func memberName(name string) bool {
	switch name {
	case "length", "prepend", "concat", "map", "filter", "reduce", "put", "get", "has_key", "main":
		return true
	}
	return bindingName(name)
}

func bindingName(name string) bool {
	switch name {
	case "true", "false", "def", "defmodule", "do", "end", "else", "if", "return", "and", "or", "not", "assert", "main", "case", "length", "when", "prepend", "concat", "map", "filter", "reduce", "put", "get", "has_key", "fn", "import", "extern", "require", "defp", "in", "cond", "raise", "with", "for", "unless", "defprotocol", "defimpl", "defmacro":
		return false
	}
	for i, r := range name {
		if i == 0 {
			if !unicode.IsLower(r) && r != '_' {
				return false
			}
		} else if !unicode.IsLetter(r) && !unicode.IsDigit(r) && r != '_' {
			return false
		}
	}
	return name != ""
}

func (p *parser) closure() (*ast.Expr, error) {
	t := p.peek()
	p.pos++
	e := &ast.Expr{Kind: "closure", Line: t.Line, Column: t.Column}
	if _, err := p.expect(lexer.LParen, ""); err != nil {
		return nil, err
	}
	if p.peek().Kind != lexer.RParen {
		for {
			name, err := p.expect(lexer.Ident, "")
			if err != nil {
				return nil, err
			}
			if _, err = p.expect(lexer.Colon, ""); err != nil {
				return nil, err
			}
			typ, err := p.typeName()
			if err != nil {
				return nil, err
			}
			e.Params = append(e.Params, ast.Parameter{Name: name.Text, Type: typ, Line: name.Line, Column: name.Column})
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
	}
	if _, err := p.expect(lexer.RParen, ""); err != nil {
		return nil, err
	}
	if _, err := p.expect(lexer.Colon, ""); err != nil {
		return nil, err
	}
	typ, err := p.typeName()
	if err != nil {
		return nil, err
	}
	e.ReturnType = typ
	if _, err = p.expect(lexer.Ident, "do"); err != nil {
		return nil, err
	}
	old, oldCond, oldCapture := p.inArm, p.condArms, p.capture
	p.inArm, p.condArms, p.capture = false, false, -1
	defer func() { p.inArm, p.condArms, p.capture = old, oldCond, oldCapture }()
	e.Body, err = p.block()
	if err != nil {
		return nil, err
	}
	if _, err = p.expect(lexer.Ident, "end"); err != nil {
		return nil, err
	}
	return e, nil
}

// template splits an interpolated string into literal text and expressions.
func (p *parser) template(t lexer.Token) (*ast.Expr, error) {
	e := &ast.Expr{Kind: "template", Line: t.Line, Column: t.Column}
	raw := t.Text
	text := func(from, to int) error {
		if from == to {
			return nil
		}
		value, err := strconv.Unquote(lexer.Unescape(`"` + raw[from:to] + `"`))
		if err != nil {
			return fmt.Errorf("%d:%d: invalid string: %w", t.Line, t.Column, err)
		}
		// Op marks literal text, as opposed to an interpolated string literal.
		e.Args = append(e.Args, &ast.Expr{Kind: "literal", Op: "text", Value: ast.Literal{Kind: "string", Text: value}, Line: t.Line, Column: t.Column})
		return nil
	}
	start := 1
	for i := 1; i < len(raw)-1; i++ {
		if raw[i] == '\\' {
			i++
			continue
		}
		if raw[i] != '#' || raw[i+1] != '{' {
			continue
		}
		if err := text(start, i); err != nil {
			return nil, err
		}
		// The lexer has already matched the braces of this literal.
		end, _ := lexer.InterpolationEnd(raw, i)
		tokens, err := lexer.Scan(raw[i+2 : end])
		if err != nil {
			return nil, fmt.Errorf("%d:%d: interpolation: %w", t.Line, t.Column, err)
		}
		offset := t.Column + len([]rune(raw[:i+2])) - 1
		for j := range tokens {
			tokens[j].Line, tokens[j].Column = t.Line, tokens[j].Column+offset
		}
		inner := parser{tokens: tokens, depth: p.depth, capture: p.capture}
		value, err := inner.expr(0)
		if err != nil {
			return nil, err
		}
		if _, err = inner.expect(lexer.EOF, ""); err != nil {
			return nil, err
		}
		e.Args = append(e.Args, value)
		i = end
		start = end + 1
	}
	if err := text(start, len(raw)-1); err != nil {
		return nil, err
	}
	return e, nil
}

// parseInteger reads an integer literal: decimal digits, perhaps separated
// by underscores, or 0x, 0o or 0b and digits in that base.
func parseInteger(text string) (int64, error) {
	sign := ""
	if strings.HasPrefix(text, "-") {
		sign, text = "-", text[1:]
	}
	if len(text) > 2 && text[0] == '0' && strings.IndexByte("xob", text[1]) >= 0 {
		return strconv.ParseInt(sign+text, 0, 64)
	}
	return strconv.ParseInt(sign+strings.ReplaceAll(text, "_", ""), 10, 64)
}

// fieldChain applies field accesses, one per name, to an expression.
func fieldChain(e *ast.Expr, at lexer.Token, names []string) (*ast.Expr, error) {
	for _, name := range names {
		if !bindingName(name) {
			return nil, diagnostic(at.Line, at.Column, "invalid field name %q", name)
		}
		e = &ast.Expr{Kind: "field", Left: e, Name: name, Line: at.Line, Column: at.Column}
	}
	return e, nil
}

// typeDecl parses a struct or sum type declaration.
func (p *parser) typeDecl() (ast.TypeDecl, error) {
	keyword := p.peek()
	p.pos++
	name, _ := p.expect(lexer.Ident, "")
	decl := ast.TypeDecl{Kind: "struct", Name: name.Text, Local: name.Text, Line: name.Line, Column: name.Column, Exception: keyword.Text == "defexception"}
	if keyword.Text == "type" {
		decl.Kind = "sum"
	}
	if !unicode.IsUpper([]rune(name.Text)[0]) || strings.Contains(name.Text, ".") {
		return decl, diagnostic(name.Line, name.Column, "type name must be one capitalized word")
	}
	if p.peek().Kind == lexer.LBracket {
		p.pos++
		for {
			param, err := p.expect(lexer.Ident, "")
			if err != nil {
				return decl, err
			}
			if !ast.TypeVariable(param.Text) {
				return decl, diagnostic(param.Line, param.Column, "type parameters are lowercase names")
			}
			for _, other := range decl.Params {
				if other == param.Text {
					return decl, diagnostic(param.Line, param.Column, "duplicate type parameter %s", param.Text)
				}
			}
			decl.Params = append(decl.Params, param.Text)
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
		if _, err := p.expect(lexer.RBracket, ""); err != nil {
			return decl, err
		}
	}
	if _, err := p.expect(lexer.Ident, "do"); err != nil {
		return decl, err
	}
	field := func(seen map[string]bool) (ast.Parameter, error) {
		label, err := p.expect(lexer.Ident, "")
		if err != nil {
			return ast.Parameter{}, err
		}
		if !memberName(label.Text) {
			return ast.Parameter{}, diagnostic(label.Line, label.Column, "invalid field name %q", label.Text)
		}
		if seen[label.Text] {
			return ast.Parameter{}, diagnostic(label.Line, label.Column, "duplicate field %s", label.Text)
		}
		seen[label.Text] = true
		if _, err = p.expect(lexer.Colon, ""); err != nil {
			return ast.Parameter{}, err
		}
		typ, err := p.typeName()
		if err != nil {
			return ast.Parameter{}, err
		}
		field := ast.Parameter{Name: label.Text, Type: typ, Line: label.Line, Column: label.Column}
		if decl.Kind == "struct" && p.peek().Kind == lexer.Assign {
			// A default fills the field when a struct is built without it.
			p.pos++
			if field.Default, err = p.expr(0); err != nil {
				return ast.Parameter{}, err
			}
		}
		return field, nil
	}
	seen := map[string]bool{}
	for p.peek().Text != "end" && p.peek().Kind != lexer.EOF {
		if decl.Kind == "struct" {
			f, err := field(seen)
			if err != nil {
				return decl, err
			}
			decl.Fields = append(decl.Fields, f)
			continue
		}
		label, err := p.expect(lexer.Ident, "")
		if err != nil {
			return decl, err
		}
		if !memberName(label.Text) {
			return decl, diagnostic(label.Line, label.Column, "invalid variant name %q", label.Text)
		}
		if seen[label.Text] {
			return decl, diagnostic(label.Line, label.Column, "duplicate variant %s", label.Text)
		}
		seen[label.Text] = true
		variant := ast.Variant{Name: label.Text, Line: label.Line, Column: label.Column}
		if p.peek().Kind == lexer.LParen && !p.newLine() {
			p.pos++
			fields := map[string]bool{}
			for {
				f, err := field(fields)
				if err != nil {
					return decl, err
				}
				variant.Fields = append(variant.Fields, f)
				if p.peek().Kind != lexer.Comma {
					break
				}
				p.pos++
			}
			if _, err = p.expect(lexer.RParen, ""); err != nil {
				return decl, err
			}
		}
		decl.Variants = append(decl.Variants, variant)
	}
	if len(decl.Fields)+len(decl.Variants) == 0 {
		what := "field"
		if decl.Kind == "sum" {
			what = "variant"
		}
		return decl, diagnostic(name.Line, name.Column, "%s requires at least one %s", name.Text, what)
	}
	if decl.Exception {
		message := false
		for _, f := range decl.Fields {
			message = message || (f.Name == "message" && f.Type == "string")
		}
		if !message || len(decl.Params) > 0 {
			return decl, diagnostic(name.Line, name.Column, "an exception has a message: string field and no type parameters")
		}
	}
	_, err := p.expect(lexer.Ident, "end")
	return decl, err
}

// compound parses an if or a case into s. Both are statements, and both can
// stand where a value is expected.
func (p *parser) compound(s *ast.Statement) error {
	t := p.peek()
	if t.Text == "cond" {
		// cond do condition -> body ... end. Each arm keeps its condition in
		// Guard; analysis rewrites the whole into nested ifs.
		p.pos++
		s.Kind = "cond"
		if _, err := p.expect(lexer.Ident, "do"); err != nil {
			return err
		}
		old, oldArm := p.condArms, p.inArm
		defer func() { p.condArms, p.inArm = old, oldArm }()
		for p.peek().Text != "end" && p.peek().Kind != lexer.EOF {
			p.condArms = false
			condition, err := p.expr(0)
			if err != nil {
				return err
			}
			if _, err = p.expect(lexer.Arrow, ""); err != nil {
				return err
			}
			p.condArms = true
			body, err := p.block(true)
			if err != nil {
				return err
			}
			s.Arms = append(s.Arms, ast.Arm{Guard: condition, Body: body})
		}
		if len(s.Arms) == 0 {
			return diagnostic(t.Line, t.Column, "cond requires branches")
		}
		_, err := p.expect(lexer.Ident, "end")
		return err
	}
	if t.Text == "with" {
		// with pattern <- expression, ... do body else arms end. Each clause
		// is an arm whose Guard is its expression; the else arms sit in a
		// case statement under Else.
		p.pos++
		s.Kind = "with"
		for {
			pattern, err := p.pattern()
			if err != nil {
				return err
			}
			if _, err = p.expect(lexer.Operator, "<-"); err != nil {
				return err
			}
			value, err := p.expr(0)
			if err != nil {
				return err
			}
			s.Arms = append(s.Arms, ast.Arm{Pattern: pattern, Guard: value})
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
		if _, err := p.expect(lexer.Ident, "do"); err != nil {
			return err
		}
		body, err := p.block()
		if err != nil {
			return err
		}
		s.Then = body
		if p.peek().Text == "else" {
			p.pos++
			arms, err := p.arms()
			if err != nil {
				return err
			}
			s.Else = []ast.Statement{{Kind: "case", Arms: arms, Line: t.Line, Column: t.Column}}
		}
		_, err = p.expect(lexer.Ident, "end")
		return err
	}
	if t.Kind == lexer.Ident && t.Text == "case" {
		old := p.condArms
		p.condArms = false
		defer func() { p.condArms = old }()
	}
	if t.Text == "if" || t.Text == "unless" {
		p.pos++
		s.Kind = "if"
		// unless is an if on the opposite condition; Name keeps the
		// spelling for the formatter until the condition is negated.
		if t.Text == "unless" {
			s.Name = "unless"
		}
		e, err := p.expr(0)
		if err != nil {
			return err
		}
		s.Expr = e
		if _, err = p.expect(lexer.Ident, "do"); err != nil {
			return err
		}
		s.Then, err = p.block()
		if err != nil {
			return err
		}
		if p.peek().Text == "else" {
			p.pos++
			s.Else, err = p.block()
			if err != nil {
				return err
			}
		}
		if _, err = p.expect(lexer.Ident, "end"); err != nil {
			return err
		}
		return nil
	}
	p.pos++
	s.Kind = "case"
	e, err := p.expr(0)
	if err != nil {
		return err
	}
	s.Expr = e
	if _, err = p.expect(lexer.Ident, "do"); err != nil {
		return err
	}
	for p.peek().Text != "end" && p.peek().Kind != lexer.EOF {
		pat, err := p.pattern()
		if err != nil {
			return err
		}
		var guard *ast.Expr
		if p.peek().Text == "when" {
			p.pos++
			guard, err = p.expr(0)
			if err != nil {
				return err
			}
		}
		if _, err = p.expect(lexer.Arrow, ""); err != nil {
			return err
		}
		body, err := p.block(true)
		if err != nil {
			return err
		}
		s.Arms = append(s.Arms, ast.Arm{Pattern: pat, Guard: guard, Body: body})
	}
	if len(s.Arms) == 0 {
		return diagnostic(t.Line, t.Column, "case requires branches")
	}
	if _, err = p.expect(lexer.Ident, "end"); err != nil {
		return err
	}
	return nil
}

// lambda parses fn x, {a, b} -> body end. Parameter types are inferred from
// where the function is used.
func (p *parser) lambda() (*ast.Expr, error) {
	t := p.peek()
	p.pos++
	e := &ast.Expr{Kind: "lambda", Line: t.Line, Column: t.Column}
	// Clauses start on the line after fn: each is pattern -> body, with an
	// optional guard, and the function takes one argument.
	if first := p.peek(); first.Line > t.Line && first.Kind != lexer.Arrow {
		old, oldCond, oldCapture := p.inArm, p.condArms, p.capture
		p.inArm, p.condArms, p.capture = false, false, -1
		defer func() { p.inArm, p.condArms, p.capture = old, oldCond, oldCapture }()
		arms, err := p.arms()
		if err != nil {
			return nil, err
		}
		name := fmt.Sprintf("fn$%d_%d", t.Line, t.Column)
		e.Params = []ast.Parameter{{Name: name, Line: t.Line, Column: t.Column}}
		e.Body = []ast.Statement{{Kind: "clauses", Name: name, Arms: arms, Line: t.Line, Column: t.Column}}
		_, err = p.expect(lexer.Ident, "end")
		return e, err
	}
	for p.peek().Kind != lexer.Arrow {
		pattern, err := p.pattern()
		if err != nil {
			return nil, err
		}
		param := ast.Parameter{Line: pattern.Line, Column: pattern.Column}
		if pattern.Kind == "name" {
			param.Name = pattern.Name
		} else {
			param.Pattern = pattern
		}
		e.Params = append(e.Params, param)
		if p.peek().Kind != lexer.Comma {
			break
		}
		p.pos++
	}
	if _, err := p.expect(lexer.Arrow, ""); err != nil {
		return nil, err
	}
	old, oldCond, oldCapture := p.inArm, p.condArms, p.capture
	p.inArm, p.condArms, p.capture = false, false, -1
	defer func() { p.inArm, p.condArms, p.capture = old, oldCond, oldCapture }()
	body, err := p.block()
	if err != nil {
		return nil, err
	}
	e.Body = body
	_, err = p.expect(lexer.Ident, "end")
	return e, err
}

// tests parses one test, setup or describe declaration. Tests and setups
// become functions without parameters whose generated names cannot clash
// with source names.
func (p *parser) tests(program *ast.Program, group string) error {
	keyword := p.peek()
	p.pos++
	f := ast.Function{Type: "void", Group: group, Line: keyword.Line, Column: keyword.Column}
	tags := p.tags
	p.tags = nil
	setup := keyword.Text == "setup" || keyword.Text == "setup_all"
	if !setup {
		name, err := p.expect(lexer.String, "")
		if err != nil {
			return err
		}
		if f.Test, err = strconv.Unquote(name.Text); err != nil || f.Test == "" {
			return diagnostic(name.Line, name.Column, "a %s needs a name", keyword.Text)
		}
	}
	// A test may receive the context its setup blocks built, after a comma;
	// a setup block may receive the one built so far.
	if keyword.Text == "test" && p.peek().Kind == lexer.Comma || keyword.Text == "setup" && p.peek().Text != "do" {
		if keyword.Text == "test" {
			p.pos++
		}
		pattern, err := p.pattern()
		if err != nil {
			return err
		}
		param := ast.Parameter{Line: pattern.Line, Column: pattern.Column}
		if pattern.Kind == "name" {
			param.Name = pattern.Name
		} else {
			param.Pattern = pattern
		}
		f.Params = []ast.Parameter{param}
	}
	if _, err := p.expect(lexer.Ident, "do"); err != nil {
		return err
	}
	if keyword.Text == "setup_all" && group != "" {
		return diagnostic(keyword.Line, keyword.Column, "setup_all belongs at the top of the module, outside describe")
	}
	if keyword.Text == "describe" {
		if strings.Contains(f.Test, ast.GroupSeparator) {
			return diagnostic(keyword.Line, keyword.Column, "invalid describe name")
		}
		inside := f.Test
		if group != "" {
			inside = group + ast.GroupSeparator + f.Test
		}
		if len(ast.Groups(inside)) > 16 {
			return diagnostic(keyword.Line, keyword.Column, "describe blocks nest at most 16 deep")
		}
		if len(tags) > 0 {
			if program.GroupTags == nil {
				program.GroupTags = map[string][]string{}
			}
			program.GroupTags[inside] = tags
		}
		for p.peek().Text != "end" && p.peek().Kind != lexer.EOF {
			if p.peek().Kind == lexer.At {
				if err := p.tag(program); err != nil {
					return err
				}
				continue
			}
			if inner := p.peek(); inner.Text != "test" && inner.Text != "setup" && inner.Text != "describe" {
				return diagnostic(inner.Line, inner.Column, "a describe block holds tests, setup blocks and describe blocks")
			}
			if err := p.tests(program, inside); err != nil {
				return err
			}
		}
		_, err := p.expect(lexer.Ident, "end")
		return err
	}
	f.Setup, f.All, f.Tags = setup, keyword.Text == "setup_all", tags
	f.Name = fmt.Sprintf("%s$%d", keyword.Text, len(program.Functions)+1)
	body, err := p.block()
	if err != nil {
		return err
	}
	f.Body = body
	program.Functions = append(program.Functions, f)
	_, err = p.expect(lexer.Ident, "end")
	return err
}

// arms parses pattern [when guard] -> body arms up to the end of their block.
func (p *parser) arms() ([]ast.Arm, error) {
	old := p.condArms
	p.condArms = false
	defer func() { p.condArms = old }()
	var arms []ast.Arm
	for !p.ends() {
		pattern, err := p.pattern()
		if err != nil {
			return nil, err
		}
		var guard *ast.Expr
		if p.peek().Text == "when" {
			p.pos++
			if guard, err = p.expr(0); err != nil {
				return nil, err
			}
		}
		if _, err = p.expect(lexer.Arrow, ""); err != nil {
			return nil, err
		}
		body, err := p.block(true)
		if err != nil {
			return nil, err
		}
		arms = append(arms, ast.Arm{Pattern: pattern, Guard: guard, Body: body})
	}
	if len(arms) == 0 {
		t := p.peek()
		return nil, diagnostic(t.Line, t.Column, "expected at least one pattern -> body arm")
	}
	return arms, nil
}

// tryHandles reports whether a try has a rescue or catch arm.
func tryHandles(s ast.Statement) bool {
	for _, arm := range s.Arms {
		if arm.Kind != "else" {
			return true
		}
	}
	return false
}

// handlerArms parses the arms of rescue or catch. A rescue arm may be
// name in Exception, binding the raised exception; a catch arm may be
// name: type, binding a thrown value of that type.
func (p *parser) handlerArms(rescue bool) ([]ast.Arm, error) {
	old := p.condArms
	p.condArms = false
	defer func() { p.condArms = old }()
	var arms []ast.Arm
	for !p.ends() {
		t := p.peek()
		next := p.tokens[p.pos+1]
		var pattern *ast.Pattern
		switch {
		case rescue && t.Kind == lexer.Ident && next.Kind == lexer.Ident && next.Text == "in":
			p.pos += 2
			kind, err := p.expect(lexer.Ident, "")
			if err != nil {
				return nil, err
			}
			if !bindingName(t.Text) && t.Text != "_" {
				return nil, diagnostic(t.Line, t.Column, "invalid binding name %q", t.Text)
			}
			pattern = &ast.Pattern{Kind: "in", Name: t.Text, Type: kind.Text, Line: t.Line, Column: t.Column}
		case t.Kind == lexer.Ident && next.Kind == lexer.Colon && bindingName(t.Text):
			p.pos += 2
			typ, err := p.typeName()
			if err != nil {
				return nil, err
			}
			pattern = &ast.Pattern{Kind: "typed", Name: t.Text, Type: typ, Line: t.Line, Column: t.Column}
		default:
			var err error
			if pattern, err = p.pattern(); err != nil {
				return nil, err
			}
		}
		arm := ast.Arm{Pattern: pattern}
		var err error
		if p.peek().Text == "when" {
			p.pos++
			if arm.Guard, err = p.expr(0); err != nil {
				return nil, err
			}
		}
		if _, err = p.expect(lexer.Arrow, ""); err != nil {
			return nil, err
		}
		if arm.Body, err = p.block(true); err != nil {
			return nil, err
		}
		arms = append(arms, arm)
	}
	if len(arms) == 0 {
		t := p.peek()
		return nil, diagnostic(t.Line, t.Column, "expected at least one pattern -> body arm")
	}
	return arms, nil
}

// try parses try do body rescue arms catch arms else arms after cleanup end.
// The rescue arms match a failure, the catch arms a thrown value and the
// else arms the body's value; the cleanup always runs.
func (p *parser) try() (*ast.Expr, error) {
	t := p.peek()
	p.pos += 2
	statement := ast.Statement{Kind: "try", Line: t.Line, Column: t.Column}
	p.trying++
	body, err := p.block()
	if err != nil {
		return nil, err
	}
	statement.Then = body
	if p.peek().Text == "rescue" {
		p.pos++
		if statement.Arms, err = p.handlerArms(true); err != nil {
			return nil, err
		}
	}
	for _, kind := range []string{"catch", "else"} {
		if p.peek().Text != kind {
			continue
		}
		p.pos++
		var arms []ast.Arm
		if kind == "catch" {
			arms, err = p.handlerArms(false)
		} else {
			arms, err = p.arms()
		}
		if err != nil {
			return nil, err
		}
		for _, arm := range arms {
			arm.Kind = kind
			statement.Arms = append(statement.Arms, arm)
		}
	}
	p.trying--
	if p.peek().Text == "after" {
		p.pos++
		if statement.Else, err = p.block(); err != nil {
			return nil, err
		}
	}
	if !tryHandles(statement) && len(statement.Else) == 0 {
		return nil, diagnostic(t.Line, t.Column, "try needs a rescue, a catch or an after")
	}
	if _, err = p.expect(lexer.Ident, "end"); err != nil {
		return nil, err
	}
	return &ast.Expr{Kind: "try", Body: []ast.Statement{statement}, Line: t.Line, Column: t.Column}, nil
}

// comprehension parses for pattern <- enumerable, filter, ... do body end,
// or its one-line form ending in ", do: expression". Generators are arms
// with a pattern; filters are arms without one.
func (p *parser) comprehension() (*ast.Expr, error) {
	t := p.peek()
	p.pos++
	statement := ast.Statement{Kind: "for", Line: t.Line, Column: t.Column}
	// The one-line form may be written with parentheses: for(x <- xs, do: x).
	parenthesized := p.peek().Kind == lexer.LParen
	if parenthesized {
		p.pos++
	}
	keyword := func() bool {
		return p.peek().Text == "do" && p.tokens[p.pos+1].Kind == lexer.Colon
	}
	e := &ast.Expr{Kind: "for", Line: t.Line, Column: t.Column}
	for !keyword() && !(p.peek().Text == "do" && len(statement.Arms) > 0) {
		// Options follow the generators and filters: into: collectable,
		// uniq: true, or reduce: initial with accumulator -> body arms.
		if option := p.peek(); option.Kind == lexer.Ident && p.tokens[p.pos+1].Kind == lexer.Colon {
			if option.Text != "into" && option.Text != "uniq" && option.Text != "reduce" {
				return nil, diagnostic(option.Line, option.Column, "for accepts the options into:, uniq: and reduce:, not %s:", option.Text)
			}
			if len(e.Labels) > 0 {
				return nil, diagnostic(option.Line, option.Column, "for takes one option")
			}
			p.pos += 2
			value, err := p.expr(0)
			if err != nil {
				return nil, err
			}
			e.Labels, e.Args = []string{option.Text}, []*ast.Expr{value}
			if p.peek().Kind == lexer.Comma {
				p.pos++
			}
			continue
		}
		start := p.pos
		probing := p.probing
		p.probing = true
		pattern, err := p.pattern()
		p.probing = probing
		arm := ast.Arm{}
		if err == nil && p.peek().Kind == lexer.Operator && p.peek().Text == "<-" {
			p.pos++
			arm.Pattern = pattern
		} else {
			p.pos = start
		}
		if arm.Guard, err = p.expr(0); err != nil {
			return nil, err
		}
		statement.Arms = append(statement.Arms, arm)
		if p.peek().Kind != lexer.Comma {
			break
		}
		p.pos++
	}
	if len(statement.Arms) == 0 || statement.Arms[0].Pattern == nil {
		return nil, diagnostic(t.Line, t.Column, "for starts with a generator: pattern <- enumerable")
	}
	reducing := len(e.Labels) == 1 && e.Labels[0] == "reduce"
	if reducing {
		if keyword() || parenthesized {
			return nil, diagnostic(t.Line, t.Column, "for with reduce: needs a do ... end block of accumulator -> body arms")
		}
		if _, err := p.expect(lexer.Ident, "do"); err != nil {
			return nil, err
		}
		arms, err := p.arms()
		if err != nil {
			return nil, err
		}
		name := fmt.Sprintf("acc$%d_%d", t.Line, t.Column)
		statement.Then = []ast.Statement{{Kind: "clauses", Name: name, Arms: arms, Line: t.Line, Column: t.Column}}
		e.Name = name
		if _, err = p.expect(lexer.Ident, "end"); err != nil {
			return nil, err
		}
	} else if keyword() {
		p.pos += 2
		value, err := p.expr(0)
		if err != nil {
			return nil, err
		}
		statement.Then = []ast.Statement{{Kind: "call", Expr: value, Line: value.Line, Column: value.Column}}
		// Name marks the one-line form for the formatter.
		statement.Name = "do:"
		if parenthesized {
			if _, err := p.expect(lexer.RParen, ""); err != nil {
				return nil, err
			}
		}
	} else if parenthesized {
		return nil, diagnostic(t.Line, t.Column, "for(...) needs the one-line form ending in \", do: expression\"")
	} else {
		if _, err := p.expect(lexer.Ident, "do"); err != nil {
			return nil, err
		}
		body, err := p.block()
		if err != nil {
			return nil, err
		}
		statement.Then = body
		if _, err = p.expect(lexer.Ident, "end"); err != nil {
			return nil, err
		}
	}
	e.Body = []ast.Statement{statement}
	return e, nil
}

// checkAll parses a property: check all pattern <- generator, ..., filter,
// max_runs: n do ... end. Generators are arms with a pattern and filters
// arms without one; a generator may use what earlier ones bound. Expr holds
// max_runs when it is given.
func (p *parser) checkAll(s *ast.Statement) error {
	t := p.peek()
	p.pos += 2
	s.Kind = "check"
	for p.peek().Text != "do" {
		if option := p.peek(); option.Kind == lexer.Ident && p.tokens[p.pos+1].Kind == lexer.Colon {
			if option.Text != "max_runs" || s.Expr != nil {
				return diagnostic(option.Line, option.Column, "check all takes one option, max_runs:")
			}
			p.pos += 2
			value, err := p.expr(0)
			if err != nil {
				return err
			}
			s.Expr = value
		} else {
			start := p.pos
			probing := p.probing
			p.probing = true
			pattern, err := p.pattern()
			p.probing = probing
			arm := ast.Arm{}
			if err == nil && p.peek().Kind == lexer.Operator && p.peek().Text == "<-" {
				p.pos++
				arm.Pattern = pattern
			} else {
				p.pos = start
			}
			if arm.Guard, err = p.expr(0); err != nil {
				return err
			}
			s.Arms = append(s.Arms, arm)
		}
		if p.peek().Kind != lexer.Comma {
			break
		}
		p.pos++
	}
	if len(s.Arms) == 0 || s.Arms[0].Pattern == nil {
		return diagnostic(t.Line, t.Column, "check all starts with a generator: pattern <- generator")
	}
	if _, err := p.expect(lexer.Ident, "do"); err != nil {
		return err
	}
	body, err := p.block()
	if err != nil {
		return err
	}
	s.Then = body
	_, err = p.expect(lexer.Ident, "end")
	return err
}

// tag parses @tag, which marks the next test or describe, @describetag,
// which marks the describe that follows, or @moduletag, which marks every
// test in the module. A tag is a name, "slow" or :slow, or names with
// values, timeout: 500, kind: :db or owner: "ada", kept as "name:value".
func (p *parser) tag(program *ast.Program) error {
	at := p.peek()
	p.pos++
	kind, err := p.expect(lexer.Ident, "")
	if err != nil || (kind.Text != "tag" && kind.Text != "moduletag" && kind.Text != "describetag") {
		return diagnostic(at.Line, at.Column, "expected @tag, @describetag or @moduletag")
	}
	var tags []string
	valid := func(t lexer.Token, text string) error {
		if text == "" || strings.ContainsAny(text, ", ") {
			return diagnostic(t.Line, t.Column, "a tag is a name without spaces or commas")
		}
		return nil
	}
	switch next := p.peek(); next.Kind {
	case lexer.String:
		p.pos++
		text, err := strconv.Unquote(next.Text)
		if err != nil {
			return err
		}
		if err := valid(next, text); err != nil {
			return err
		}
		tags = append(tags, text)
	case lexer.Atom:
		p.pos++
		if err := valid(next, next.Text); err != nil {
			return err
		}
		tags = append(tags, next.Text)
	default:
		for {
			name, err := p.expect(lexer.Ident, "")
			if err != nil {
				return diagnostic(at.Line, at.Column, "a tag is \"name\", :name or name: value")
			}
			if _, err := p.expect(lexer.Colon, ""); err != nil {
				return err
			}
			value := p.peek()
			text := value.Text
			switch value.Kind {
			case lexer.String:
				if text, err = strconv.Unquote(value.Text); err != nil {
					return err
				}
			case lexer.Atom, lexer.Integer:
			case lexer.Ident:
				if text != "true" && text != "false" {
					return diagnostic(value.Line, value.Column, "a tag's value is a string, atom, integer or boolean")
				}
			default:
				return diagnostic(value.Line, value.Column, "a tag's value is a string, atom, integer or boolean")
			}
			p.pos++
			if text == "" || strings.Contains(text, ",") {
				return diagnostic(value.Line, value.Column, "a tag's value is not empty and has no commas")
			}
			if err := valid(name, name.Text); err != nil {
				return err
			}
			tags = append(tags, name.Text+":"+text)
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
	}
	if kind.Text != "moduletag" {
		p.tags = append(p.tags, tags...)
		return nil
	}
	if program.GroupTags == nil {
		program.GroupTags = map[string][]string{}
	}
	program.GroupTags[""] = append(program.GroupTags[""], tags...)
	return nil
}

// ParseSnippet parses statements written outside any function, such as the
// examples in a documentation comment.
func ParseSnippet(source string) ([]ast.Statement, error) {
	program, err := ParseModule("defmodule Snippet do def main() do\n" + source + "\nend end")
	if err != nil {
		return nil, err
	}
	return program.Functions[0].Body, nil
}

// Example is one documented example: source to run and, when the comment
// shows a result, the source of the value it should equal.
type Example struct {
	Source, Expected string
}

// Examples extracts the alx> examples of a documentation comment. A line
// starting with "...>" continues the one above, and the lines after an
// example, up to a blank one, are its expected result.
func Examples(doc []string) []Example {
	var out []Example
	open := false
	for _, line := range doc {
		text := strings.TrimSpace(line)
		switch {
		case strings.HasPrefix(text, "alx>"):
			out = append(out, Example{Source: strings.TrimSpace(text[len("alx>"):])})
			open = true
		case strings.HasPrefix(text, "...>") && open:
			out[len(out)-1].Source += "\n" + strings.TrimSpace(text[4:])
		case text == "":
			open = false
		case open:
			out[len(out)-1].Expected = strings.TrimSpace(out[len(out)-1].Expected + "\n" + text)
		}
	}
	return out
}

// constantDefault reports whether a default value can be evaluated wherever
// the function is called: it may not read bindings or call functions other
// than the option and result constructors.
func constantDefault(e *ast.Expr) bool {
	if e == nil {
		return true
	}
	switch e.Kind {
	case "name":
		return e.Name == "none"
	case "call":
		if e.Name != "some" && e.Name != "ok" && e.Name != "error" {
			return false
		}
	case "fn", "lambda", "capture", "case", "if", "cond", "try", "for", "with":
		return false
	}
	if len(e.Body) > 0 || !constantDefault(e.Left) || !constantDefault(e.Right) {
		return false
	}
	for _, arg := range append(append([]*ast.Expr{}, e.Args...), e.Keys...) {
		if !constantDefault(arg) {
			return false
		}
	}
	return true
}

// sigilTemplate reads the text of a sigil as an interpolated string. Sigil
// text has no escapes, so everything outside #{...} is taken literally.
func (p *parser) sigilTemplate(t lexer.Token, text string) (*ast.Expr, error) {
	var raw strings.Builder
	raw.WriteByte('"')
	literal := func(part string) {
		raw.WriteString(strings.NewReplacer(`\`, `\\`, `"`, `\"`).Replace(part))
	}
	start := 0
	for i := 0; i+1 < len(text); i++ {
		if text[i] != '#' || text[i+1] != '{' {
			continue
		}
		end, problem := lexer.InterpolationEnd(text, i)
		if problem != "" {
			return nil, diagnostic(t.Line, t.Column, "sigil interpolation: %s", problem)
		}
		literal(text[start:i])
		raw.WriteString(text[i : end+1])
		i, start = end, end+1
	}
	literal(text[start:])
	raw.WriteByte('"')
	return p.template(lexer.Token{Kind: lexer.Template, Text: raw.String(), Line: t.Line, Column: t.Column})
}

// receiveForms are the mailbox assertions, whose second argument is a
// pattern. The received forms look only at what has already arrived.
var receiveForms = map[string]bool{"assert_receive": true, "refute_receive": true, "assert_received": true, "refute_received": true}

// receiveArguments is how many arguments may follow the pattern.
func receiveArguments(name string) int {
	if strings.HasSuffix(name, "received") {
		return 1
	}
	return 2
}

// PatternText and ExprText render a pattern and an expression as source,
// for messages. The formatter, which lives in another package, sets them.
var (
	PatternText = func(*ast.Pattern) string { return "the pattern" }
	ExprText    = func(*ast.Expr) string { return "..." }
)

// protocol parses defprotocol Name do def function(parameters): type ... end.
// The functions have no bodies: each type supplies them in a defimpl.
func (p *parser) protocol() (ast.Protocol, error) {
	p.pos++
	name, err := p.expect(lexer.Ident, "")
	if err != nil {
		return ast.Protocol{}, err
	}
	protocol := ast.Protocol{Name: name.Text, Line: name.Line, Column: name.Column}
	if !unicode.IsUpper([]rune(name.Text)[0]) || strings.Contains(name.Text, ".") {
		return protocol, diagnostic(name.Line, name.Column, "a protocol name is one capitalized word")
	}
	if _, err = p.expect(lexer.Ident, "do"); err != nil {
		return protocol, err
	}
	for p.peek().Text == "def" {
		p.pos++
		function, err := p.expect(lexer.Ident, "")
		if err != nil {
			return protocol, err
		}
		declared := ast.ProtocolFunction{Name: function.Text, Type: "void"}
		if _, err = p.expect(lexer.LParen, ""); err != nil {
			return protocol, err
		}
		for p.peek().Kind != lexer.RParen {
			parameter, err := p.expect(lexer.Ident, "")
			if err != nil {
				return protocol, err
			}
			declared.Params = append(declared.Params, parameter.Text)
			if p.peek().Kind == lexer.Colon {
				// A type written here documents the parameter; each
				// implementation states its own.
				p.pos++
				if _, err = p.typeName(); err != nil {
					return protocol, err
				}
			}
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
		if _, err = p.expect(lexer.RParen, ""); err != nil {
			return protocol, err
		}
		if len(declared.Params) == 0 {
			return protocol, diagnostic(function.Line, function.Column, "a protocol function takes at least the value it is called on")
		}
		if p.peek().Kind == lexer.Colon {
			p.pos++
			if declared.Type, err = p.typeName(); err != nil {
				return protocol, err
			}
		}
		protocol.Functions = append(protocol.Functions, declared)
	}
	if len(protocol.Functions) == 0 {
		return protocol, diagnostic(name.Line, name.Column, "protocol %s declares no functions", name.Text)
	}
	_, err = p.expect(lexer.Ident, "end")
	return protocol, err
}

// implementation parses defimpl Protocol, for: Type do definitions end. The
// functions become ordinary functions under names no source can write; a
// call through the protocol is resolved to one of them by type.
func (p *parser) implementation(index int) ([]ast.Function, error) {
	start := p.peek()
	p.pos++
	protocol, err := p.expect(lexer.Ident, "")
	if err != nil {
		return nil, err
	}
	if _, err = p.expect(lexer.Comma, ""); err != nil {
		return nil, diagnostic(start.Line, start.Column, "defimpl names a protocol and a type: defimpl %s, for: Type do", protocol.Text)
	}
	if word := p.peek(); word.Text != "for" || p.tokens[p.pos+1].Kind != lexer.Colon {
		return nil, diagnostic(word.Line, word.Column, "defimpl names a protocol and a type: defimpl %s, for: Type do", protocol.Text)
	}
	p.pos += 2
	target, err := p.typeName()
	if err != nil {
		return nil, err
	}
	if _, err = p.expect(lexer.Ident, "do"); err != nil {
		return nil, err
	}
	var out []ast.Function
	for p.peek().Text == "def" || p.peek().Text == "defp" {
		f, err := p.function()
		if err != nil {
			return nil, err
		}
		if len(f.Params) == 0 {
			return nil, diagnostic(f.Line, f.Column, "%s.%s takes at least the %s it is called on", protocol.Text, f.Name, target)
		}
		// The first parameter is the value of the implementing type.
		if first := &f.Params[0]; first.Type == "" {
			first.Type = target
		} else if first.Type != target {
			return nil, diagnostic(first.Line, first.Column, "the first parameter of %s.%s is the %s it is implemented for, not %s", protocol.Text, f.Name, target, first.Type)
		}
		f.Protocol, f.ProtocolFunction, f.For = protocol.Text, f.Name, target
		f.Name = fmt.Sprintf("%s$%s$%d", f.Name, protocol.Text, index)
		out = append(out, f)
	}
	if len(out) == 0 {
		return nil, diagnostic(start.Line, start.Column, "defimpl %s, for: %s defines no functions", protocol.Text, target)
	}
	_, err = p.expect(lexer.Ident, "end")
	return out, err
}

// lower rewrites a parsed module into the forms analysis works on.
func lower(p *ast.Program) error {
	if err := separateArities(p); err != nil {
		return err
	}
	if err := mergeClauses(p); err != nil {
		return err
	}
	desugarUnless(p)
	desugarReceives(p)
	desugarClauses(p)
	desugarConds(p)
	desugarWiths(p)
	desugarChecks(p)
	desugarBitwise(p)
	Qualify(p)
	return nil
}

// bitwiseCalls are the Bitwise functions the operators stand for.
var bitwiseCalls = map[string]string{"&&&": "Bitwise.band", "|||": "Bitwise.bor", "^^^": "Bitwise.bxor", "<<<": "Bitwise.bsl", ">>>": "Bitwise.bsr", "~~~": "Bitwise.bnot"}

// desugarBitwise rewrites a &&& b and its kin into calls of Bitwise.
func desugarBitwise(p *ast.Program) {
	rewrite := func(e *ast.Expr) {
		name, ok := bitwiseCalls[e.Op]
		if !ok || (e.Kind != "binary" && e.Kind != "unary") {
			return
		}
		args := []*ast.Expr{e.Left}
		if e.Kind == "binary" {
			args = append(args, e.Right)
		}
		*e = ast.Expr{Kind: "call", Name: name, Args: args, Line: e.Line, Column: e.Column}
	}
	for i := range p.Functions {
		walkFunction(&p.Functions[i], rewrite)
	}
}

// doBlock reads the do ... end block that may follow a call written as a
// statement or bound to a name. Only a macro takes one; Op marks the call
// so that anything else is reported.
func (p *parser) doBlock(e *ast.Expr) error {
	if e.Kind != "call" || p.peek().Text != "do" || p.peek().Kind != lexer.Ident || p.newLine() {
		return nil
	}
	p.pos++
	old, oldCond := p.inArm, p.condArms
	p.inArm, p.condArms = false, false
	body, err := p.block()
	p.inArm, p.condArms = old, oldCond
	if err != nil {
		return err
	}
	e.Body, e.Op = body, "do"
	_, err = p.expect(lexer.Ident, "end")
	return err
}

// macro parses defmacro name(parameters, do: block) do quote do ... end end.
// A macro named __using__ holds function definitions instead of statements.
func (p *parser) macro() (ast.Macro, error) {
	p.pos++
	name, err := p.expect(lexer.Ident, "")
	if err != nil {
		return ast.Macro{}, err
	}
	macro := ast.Macro{Name: name.Text, Line: name.Line, Column: name.Column}
	if _, err = p.expect(lexer.LParen, ""); err != nil {
		return macro, err
	}
	for p.peek().Kind != lexer.RParen {
		parameter, err := p.expect(lexer.Ident, "")
		if err != nil {
			return macro, err
		}
		if parameter.Text == "do" && p.peek().Kind == lexer.Colon {
			p.pos++
			block, err := p.expect(lexer.Ident, "")
			if err != nil {
				return macro, err
			}
			macro.Block = block.Text
			break
		}
		macro.Params = append(macro.Params, parameter.Text)
		if p.peek().Kind != lexer.Comma {
			break
		}
		p.pos++
	}
	if _, err = p.expect(lexer.RParen, ""); err != nil {
		return macro, diagnostic(name.Line, name.Column, "the parameters of a macro are names, the last of which may be do: name for a block")
	}
	for _, word := range []string{"do", "quote", "do"} {
		if _, err = p.expect(lexer.Ident, word); err != nil {
			return macro, diagnostic(name.Line, name.Column, "the body of a macro is one quote do ... end")
		}
	}
	if macro.Name == "__using__" {
		macro.Definitions = []ast.Function{}
		for p.peek().Text == "def" || p.peek().Text == "defp" {
			f, err := p.function()
			if err != nil {
				return macro, err
			}
			macro.Definitions = append(macro.Definitions, f)
		}
		if len(macro.Definitions) == 0 {
			return macro, diagnostic(name.Line, name.Column, "__using__ holds the function definitions that use adds to a module")
		}
	} else if macro.Body, err = p.block(); err != nil {
		return macro, err
	}
	for range 2 {
		if _, err = p.expect(lexer.Ident, "end"); err != nil {
			return macro, err
		}
	}
	return macro, nil
}

// use parses use Module, name: value, ... .
func (p *parser) use() (ast.Use, error) {
	keyword := p.peek()
	p.pos++
	module, _ := p.expect(lexer.Ident, "")
	use := ast.Use{Module: module.Text, Line: keyword.Line, Column: keyword.Column}
	for p.peek().Kind == lexer.Comma {
		p.pos++
		name, err := p.expect(lexer.Ident, "")
		if err != nil {
			return use, err
		}
		if _, err = p.expect(lexer.Colon, ""); err != nil {
			return use, diagnostic(name.Line, name.Column, "use takes options written name: value")
		}
		value, err := p.expr(0)
		if err != nil {
			return use, err
		}
		use.Names, use.Values = append(use.Names, name.Text), append(use.Values, value)
	}
	return use, nil
}
