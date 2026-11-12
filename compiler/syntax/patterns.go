package syntax

import (
	"unicode"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/lexer"
	"strings"
)

func (p *parser) typeName() (string, error) {
	defer p.ascend()
	if err := p.descend(); err != nil {
		return "", err
	}
	t, err := p.expect(lexer.Ident, "")
	if err != nil {
		return "", err
	}
	named := unicode.IsUpper([]rune(t.Text)[0])
	parameterized := map[string]bool{"list": true, "tuple": true, "map": true, "fn": true, "pid": true, "supervisor": true, "server": true, "option": true, "result": true, "stream": true, "set": true, "task": true, "agent": true, "step": true, "registry": true, "generator": true}[t.Text]
	if !parameterized && !(named && p.peek().Kind == lexer.LBracket) {
		if !ast.ValidType(t.Text) {
			return "", diagnostic(t.Line, t.Column, "unknown type %q", t.Text)
		}
		return t.Text, nil
	}
	if _, err = p.expect(lexer.LBracket, ""); err != nil {
		return "", err
	}
	var parts []string
	if p.peek().Kind != lexer.RBracket {
		for {
			typ, err := p.typeName()
			if err != nil {
				return "", err
			}
			parts = append(parts, typ)
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
	}
	if _, err = p.expect(lexer.RBracket, ""); err != nil {
		return "", err
	}
	if t.Text == "list" && len(parts) != 1 {
		return "", diagnostic(t.Line, t.Column, "list type requires one element type")
	}
	result := t.Text + "[" + strings.Join(parts, ",") + "]"
	if !ast.ValidType(result) {
		return "", diagnostic(t.Line, t.Column, "invalid type %q", result)
	}
	return result, nil
}
func (p *parser) pattern() (*ast.Pattern, error) {
	defer p.ascend()
	if err := p.descend(); err != nil {
		return nil, err
	}
	t := p.peek()
	pat := &ast.Pattern{Line: t.Line, Column: t.Column}
	switch t.Kind {
	case lexer.StructStart:
		p.pos++
		pat.Kind = "struct"
		pat.Name = t.Text
		if _, err := p.expect(lexer.LBrace, ""); err != nil {
			return nil, err
		}
		for p.peek().Kind != lexer.RBrace {
			label, err := p.expect(lexer.Ident, "")
			if err != nil {
				return nil, err
			}
			if _, err = p.expect(lexer.Colon, ""); err != nil {
				return nil, err
			}
			child, err := p.pattern()
			if err != nil {
				return nil, err
			}
			pat.Labels = append(pat.Labels, label.Text)
			pat.Children = append(pat.Children, child)
			if p.peek().Kind != lexer.Comma {
				break
			}
			p.pos++
		}
		if _, err := p.expect(lexer.RBrace, ""); err != nil {
			return nil, err
		}
		return pat, nil
	case lexer.Caret:
		// A pin compares against an existing binding instead of binding a name.
		p.pos++
		name, err := p.expect(lexer.Ident, "")
		if err != nil {
			return nil, err
		}
		pat.Kind = "pin"
		pat.Name = name.Text
		return pat, nil
	case lexer.MapStart:
		p.pos++
		pat.Kind = "map"
		if p.peek().Kind != lexer.RBrace {
			for {
				key, err := p.pattern()
				if err != nil {
					return nil, err
				}
				if key.Kind != "literal" {
					return nil, diagnostic(key.Line, key.Column, "map pattern keys must be literals")
				}
				if _, err = p.expect(lexer.Pair, ""); err != nil {
					return nil, err
				}
				value, err := p.pattern()
				if err != nil {
					return nil, err
				}
				pat.Keys = append(pat.Keys, key.Value)
				pat.Children = append(pat.Children, value)
				if p.peek().Kind != lexer.Comma {
					break
				}
				p.pos++
			}
		}
		if _, err := p.expect(lexer.RBrace, ""); err != nil {
			return nil, err
		}
		return pat, nil
	case lexer.LBrace, lexer.LBracket:
		p.pos++
		pat.Kind = "tuple"
		end := lexer.RBrace
		if t.Kind == lexer.LBracket {
			pat.Kind = "list"
			end = lexer.RBracket
		}
		if p.peek().Kind != end {
			for {
				child, err := p.pattern()
				if err != nil {
					return nil, err
				}
				pat.Children = append(pat.Children, child)
				if pat.Kind == "list" && p.peek().Kind == lexer.Bar {
					p.pos++
					pat.Tail, err = p.pattern()
					if err != nil {
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
		return pat, nil
	case lexer.Ident:
		p.pos++
		if t.Text == "true" || t.Text == "false" {
			pat.Kind = "literal"
			pat.Value = ast.Literal{Kind: "boolean", Boolean: t.Text == "true"}
			return pat, nil
		}
		pat.Kind = "name"
		pat.Name = t.Text
		if t.Text == "_" {
			pat.Kind = "wildcard"
		}
		// A constructor pattern: a qualified variant, or ok/error/some applied
		// to sub-patterns. A bare lowercase name stays a binding.
		qualified := unicode.IsUpper([]rune(t.Text)[0])
		applied := p.peek().Kind == lexer.LParen && !p.newLine()
		if qualified || (applied && (t.Text == "ok" || t.Text == "error" || t.Text == "some" || t.Text == "cont" || t.Text == "halt")) {
			pat.Kind = "variant"
			if applied {
				p.pos++
				for {
					child, err := p.pattern()
					if err != nil {
						return nil, err
					}
					pat.Children = append(pat.Children, child)
					if p.peek().Kind != lexer.Comma {
						break
					}
					p.pos++
				}
				if _, err := p.expect(lexer.RParen, ""); err != nil {
					return nil, err
				}
			}
		}
		return pat, nil
	case lexer.Integer, lexer.Float, lexer.String, lexer.Atom, lexer.Operator:
		// atom accepts literals and signed integer literals; all other expressions
		// are deliberately excluded from patterns.
		e, err := p.atom()
		if err != nil {
			return nil, err
		}
		if e.Kind != "literal" {
			return nil, diagnostic(t.Line, t.Column, "expected literal pattern")
		}
		pat.Kind = "literal"
		pat.Value = e.Value
		return pat, nil
	}
	return nil, diagnostic(t.Line, t.Column, "expected pattern")
}
func (p *parser) assignmentStart() bool {
	pos := p.pos
	old := p.probing
	p.probing = true
	defer func() { p.pos = pos; p.probing = old }()
	if _, err := p.pattern(); err != nil {
		return false
	}
	if p.peek().Kind == lexer.Colon {
		p.pos++
		if _, err := p.typeName(); err != nil {
			return false
		}
	}
	return p.peek().Kind == lexer.Assign
}
func (p *parser) armStart() bool {
	pos := p.pos
	old := p.probing
	p.probing = true
	defer func() { p.pos = pos; p.probing = old }()
	if p.condArms {
		// A cond arm starts with a condition followed by "->".
		capture := p.capture
		_, err := p.expr(0)
		p.capture = capture
		return err == nil && p.peek().Kind == lexer.Arrow
	}
	if _, err := p.pattern(); err != nil {
		return false
	}
	return p.peek().Kind == lexer.Arrow || p.peek().Text == "when"
}

// checkPattern types a pattern against a value and records its bindings.
// Pins may only name bindings that existed before the pattern began.
func (c checker) checkPattern(p *ast.Pattern, typ string, scope map[string]string) error {
	return c.checkPatternIn(p, typ, scope, cloneScope(scope))
}
func (c checker) checkPatternIn(p *ast.Pattern, typ string, scope, outer map[string]string) error {
	p.Type = typ
	if head, _ := ast.Split(typ); p.Kind == "name" && p.Name == "none" && head == "option" {
		// A bare none matches the empty option rather than binding a name.
		p.Kind = "variant"
	}
	switch p.Kind {
	case "struct":
		decl, types := c.fieldTypes(typ, 0)
		if c.types[p.Name] == nil || c.types[p.Name].Kind != "struct" {
			return diagnostic(p.Line, p.Column, "unknown type %q", p.Name)
		}
		if decl != c.types[p.Name] {
			return diagnostic(p.Line, p.Column, "%s pattern does not match %s", c.types[p.Name].Local, typ)
		}
		p.Fields = nil
		seen := map[string]bool{}
		for i, label := range p.Labels {
			index := -1
			for j, field := range decl.Fields {
				if field.Name == label {
					index = j
				}
			}
			if index < 0 {
				return diagnostic(p.Line, p.Column, "%s has no field %s", decl.Local, label)
			}
			if seen[label] {
				return diagnostic(p.Line, p.Column, "duplicate field %s", label)
			}
			seen[label] = true
			p.Fields = append(p.Fields, index)
			if err := c.checkPatternIn(p.Children[i], types[index], scope, outer); err != nil {
				return err
			}
		}
		return nil
	case "variant":
		ref, message, found := c.constructor(p.Name)
		if message != "" {
			return diagnostic(p.Line, p.Column, "%s", message)
		}
		if !found {
			return diagnostic(p.Line, p.Column, "unknown constructor %s", p.Name)
		}
		decl, _ := c.fieldTypes(typ, 0)
		if decl != ref.decl {
			return diagnostic(p.Line, p.Column, "pattern %s does not match %s", display(ref), typ)
		}
		_, types := c.fieldTypes(typ, ref.index)
		if len(types) != len(p.Children) {
			return diagnostic(p.Line, p.Column, "%s requires %s", display(ref), plural(len(types), "argument"))
		}
		p.Index = ref.index
		for i, child := range p.Children {
			if err := c.checkPatternIn(child, types[i], scope, outer); err != nil {
				return err
			}
		}
		return nil
	case "wildcard":
		return nil
	case "pin":
		bound, ok := outer[p.Name]
		if !ok {
			return diagnostic(p.Line, p.Column, "pinned binding %q is not defined before this pattern", p.Name)
		}
		if bound != typ {
			return diagnostic(p.Line, p.Column, "pinned binding %q has type %s, pattern requires %s", p.Name, bound, typ)
		}
		if !c.compare(typ) {
			return diagnostic(p.Line, p.Column, "pinned binding %q has a type without equality", p.Name)
		}
	case "name":
		if !generated(p.Name) && !bindingName(p.Name) {
			return diagnostic(p.Line, p.Column, "invalid pattern binding %q", p.Name)
		}
		if _, ok := scope[p.Name]; ok {
			return diagnostic(p.Line, p.Column, "immutable binding %q already defined", p.Name)
		}
		scope[p.Name] = typ
	case "literal":
		if p.Value.Kind != typ {
			return diagnostic(p.Line, p.Column, "pattern type does not match %s", typ)
		}
		if p.Value.Kind == "string" && strings.ContainsRune(p.Value.Text, 0) {
			return diagnostic(p.Line, p.Column, "string literal contains NUL")
		}
	case "list":
		elem, ok := ast.ListElement(typ)
		if !ok {
			return diagnostic(p.Line, p.Column, "list pattern requires list value")
		}
		for _, child := range p.Children {
			if err := c.checkPatternIn(child, elem, scope, outer); err != nil {
				return err
			}
		}
		if p.Tail != nil {
			return c.checkPatternIn(p.Tail, typ, scope, outer)
		}
	case "map":
		key, value, ok := ast.MapParts(typ)
		if !ok {
			return diagnostic(p.Line, p.Column, "map pattern requires map value")
		}
		seen := map[ast.Literal]bool{}
		for i, k := range p.Keys {
			if k.Kind == "string" && strings.ContainsRune(k.Text, 0) {
				return diagnostic(p.Line, p.Column, "string literal contains NUL")
			}
			if k.Kind != key {
				return diagnostic(p.Line, p.Column, "map pattern key type mismatch")
			}
			if seen[k] {
				return diagnostic(p.Line, p.Column, "duplicate map pattern key")
			}
			seen[k] = true
			if k.Kind == "string" && strings.ContainsRune(k.Text, 0) {
				return diagnostic(p.Line, p.Column, "string literal contains NUL")
			}
			if err := c.checkPatternIn(p.Children[i], value, scope, outer); err != nil {
				return err
			}
		}
	case "tuple":
		elems, ok := ast.TupleElements(typ)
		if !ok || len(elems) != len(p.Children) {
			return diagnostic(p.Line, p.Column, "tuple pattern arity/type mismatch")
		}
		for i, child := range p.Children {
			if err := c.checkPatternIn(child, elems[i], scope, outer); err != nil {
				return err
			}
		}
	}
	return nil
}
func irrefutable(p *ast.Pattern) bool {
	if p.Kind == "name" || p.Kind == "wildcard" {
		return true
	}
	if p.Kind == "map" && len(p.Keys) == 0 {
		return true
	}
	if p.Kind == "tuple" || p.Kind == "struct" {
		for _, c := range p.Children {
			if !irrefutable(c) {
				return false
			}
		}
		return true
	}
	return false
}

// subsumes proves that every value matching b also matches a. It is
// deliberately conservative for intersections that require symbolic reasoning.
func subsumes(a, b *ast.Pattern) bool {
	if irrefutable(a) {
		return true
	}
	if a.Kind != b.Kind {
		return false
	}
	if a.Kind == "literal" {
		return a.Value == b.Value
	}
	if a.Kind == "pin" {
		// Bindings are immutable and never shadowed, so one name is one value.
		return a.Name == b.Name
	}
	if a.Kind == "map" {
		for i, key := range a.Keys {
			found := false
			for j, other := range b.Keys {
				if key == other && subsumes(a.Children[i], b.Children[j]) {
					found = true
					break
				}
			}
			if !found {
				return false
			}
		}
		return true
	}
	if a.Kind == "struct" {
		for i, label := range a.Labels {
			matched := irrefutable(a.Children[i])
			for j, other := range b.Labels {
				if label == other {
					matched = subsumes(a.Children[i], b.Children[j])
				}
			}
			if !matched {
				return false
			}
		}
		return a.Name == b.Name
	}
	if a.Kind == "variant" && (a.Name != b.Name || a.Index != b.Index) {
		return false
	}
	if a.Kind == "tuple" || a.Kind == "variant" {
		if len(a.Children) != len(b.Children) {
			return false
		}
		for i, child := range a.Children {
			if !subsumes(child, b.Children[i]) {
				return false
			}
		}
		return true
	}
	if a.Kind == "list" {
		if a.Tail == nil && (b.Tail != nil || len(a.Children) != len(b.Children)) {
			return false
		}
		if len(a.Children) > len(b.Children) {
			return false
		}
		for i, child := range a.Children {
			if !subsumes(child, b.Children[i]) {
				return false
			}
		}
		if a.Tail != nil {
			return subsumes(a.Tail, &ast.Pattern{Kind: "list", Children: b.Children[len(a.Children):], Tail: b.Tail})
		}
		return true
	}
	return false
}
func (c checker) exhaustive(arms []ast.Arm, typ string) bool {
	var rows [][]*ast.Pattern
	for _, arm := range arms {
		if arm.Guard == nil {
			rows = append(rows, []*ast.Pattern{arm.Pattern})
		}
	}
	return c.covers(rows, []string{typ})
}
