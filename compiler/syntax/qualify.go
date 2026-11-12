package syntax

import (
	"strings"
	"unicode"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// Qualify rewrites the type and constructor names a module declares itself
// to their qualified form, Module.Name, wherever the module mentions them.
// Names from other modules are already written qualified.
func Qualify(m *ast.Program) {
	local := map[string]bool{}
	for _, decl := range m.Types {
		local[decl.Local] = true
	}
	var typ func(string) string
	typ = func(t string) string {
		if t == "" {
			return t
		}
		head, args := ast.Split(t)
		if local[head] {
			head = m.Module + "." + head
		}
		for i := range args {
			args[i] = typ(args[i])
		}
		return ast.Join(head, args)
	}
	// name qualifies "Type" and "Type.variant".
	name := func(n string) string {
		first, _, _ := strings.Cut(n, ".")
		if local[first] {
			return m.Module + "." + n
		}
		return n
	}
	params := func(list []ast.Parameter) {
		for i := range list {
			list[i].Type = typ(list[i].Type)
		}
	}
	var pattern func(*ast.Pattern)
	pattern = func(p *ast.Pattern) {
		if p == nil {
			return
		}
		if p.Kind == "struct" || p.Kind == "variant" {
			p.Name = name(p.Name)
		}
		if p.Kind == "in" {
			p.Type = name(p.Type)
		}
		if p.Kind == "typed" {
			p.Type = typ(p.Type)
		}
		for _, child := range p.Children {
			pattern(child)
		}
		pattern(p.Tail)
	}
	var block func([]ast.Statement)
	var expr func(*ast.Expr)
	expr = func(e *ast.Expr) {
		if e == nil {
			return
		}
		switch e.Kind {
		case "struct":
			e.Name = name(e.Name)
		case "call", "name", "funcref":
			if e.Name != "" && unicode.IsUpper([]rune(e.Name)[0]) {
				e.Name = name(e.Name)
			}
		case "closure":
			params(e.Params)
			e.ReturnType = typ(e.ReturnType)
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
	block = func(body []ast.Statement) {
		for i := range body {
			s := &body[i]
			s.Declared = typ(s.Declared)
			pattern(s.Pattern)
			expr(s.Expr)
			block(s.Then)
			block(s.Else)
			for _, arm := range s.Arms {
				pattern(arm.Pattern)
				expr(arm.Guard)
				block(arm.Body)
			}
		}
	}
	for i := range m.Types {
		decl := &m.Types[i]
		decl.Name = m.Module + "." + decl.Local
		params(decl.Fields)
		for _, variant := range decl.Variants {
			params(variant.Fields)
		}
	}
	for i := range m.Functions {
		f := &m.Functions[i]
		params(f.Params)
		for _, param := range f.Params {
			pattern(param.Pattern)
		}
		f.Type = typ(f.Type)
		expr(f.Guard)
		block(f.Body)
	}
}
