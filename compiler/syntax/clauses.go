package syntax

import (
	"fmt"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// generatedName reports a parameter name introduced by clause merging; source
// names cannot contain "$".
func generatedName(name string) bool { return strings.Contains(name, "$") }

// mergeClauses combines adjacent definitions of one function into a single
// function whose body matches its parameters against each clause in order.
// Functions written as one clause of typed names are left as they are.
func mergeClauses(p *ast.Program) error {
	var out []ast.Function
	seen := map[string]bool{}
	for i := 0; i < len(p.Functions); {
		first := p.Functions[i]
		j := i + 1
		for first.Extern == "" && len(first.Params) > 0 && j < len(p.Functions) && p.Functions[j].Name == first.Name && p.Functions[j].Extern == "" {
			j++
		}
		group := p.Functions[i:j]
		i = j
		if first.Test != "" || first.Setup {
			// Tests and setup blocks take their context's type from analysis.
			out = append(out, first)
			continue
		}
		if seen[first.Name] && first.Extern == "" && len(first.Params) > 0 {
			return diagnostic(first.Line, first.Column, "clauses of %s must be adjacent", first.Name)
		}
		seen[first.Name] = true
		plain := len(group) == 1 && first.Guard == nil
		for _, param := range first.Params {
			plain = plain && param.Pattern == nil && param.Type != ""
		}
		if plain {
			out = append(out, first)
			continue
		}
		merged, err := mergeGroup(group)
		if err != nil {
			return err
		}
		out = append(out, merged)
	}
	p.Functions = out
	return nil
}

func mergeGroup(group []ast.Function) (ast.Function, error) {
	first := group[0]
	merged := ast.Function{Name: first.Name, Type: "void", Line: first.Line, Column: first.Column, Private: first.Private, Doc: first.Doc, Comments: first.Comments}
	for _, clause := range group {
		if merged.Doc == "" {
			merged.Doc = clause.Doc
		}
	}
	types := make([]string, len(first.Params))
	for _, clause := range group {
		if clause.Private != first.Private {
			return merged, diagnostic(clause.Line, clause.Column, "clauses of %s must all be def or all be defp", first.Name)
		}
		if len(clause.Params) != len(first.Params) {
			return merged, diagnostic(clause.Line, clause.Column, "clauses of %s must have the same number of parameters", first.Name)
		}
		for i, param := range clause.Params {
			t := param.Type
			if t == "" && param.Pattern != nil && param.Pattern.Kind == "literal" {
				t = param.Pattern.Value.Kind
			}
			if t != "" && types[i] != "" && t != types[i] {
				return merged, diagnostic(param.Line, param.Column, "parameter %d of %s is %s in one clause and %s in another", i+1, first.Name, types[i], t)
			}
			if types[i] == "" {
				types[i] = t
			}
		}
		if clause.Type != "void" && merged.Type != "void" && clause.Type != merged.Type {
			return merged, diagnostic(clause.Line, clause.Column, "%s returns %s in one clause and %s in another", first.Name, merged.Type, clause.Type)
		}
		if merged.Type == "void" {
			merged.Type = clause.Type
		}
	}
	if merged.Type == "void" {
		return merged, diagnostic(first.Line, first.Column, "%s needs a return type in one clause", first.Name)
	}
	var subjects []*ast.Expr
	for i, t := range types {
		if t == "" {
			return merged, diagnostic(first.Params[i].Line, first.Params[i].Column, "parameter %d of %s needs a type in one clause", i+1, first.Name)
		}
		name := fmt.Sprintf("arg$%d", i+1)
		merged.Params = append(merged.Params, ast.Parameter{Name: name, Type: t, Default: first.Params[i].Default, Line: first.Params[i].Line, Column: first.Params[i].Column})
		subjects = append(subjects, &ast.Expr{Kind: "name", Name: name, Line: first.Line, Column: first.Column})
	}
	match := ast.Statement{Kind: "case", Line: first.Line, Column: first.Column, Expr: subjects[0]}
	if len(subjects) > 1 {
		match.Expr = &ast.Expr{Kind: "tuple", Args: subjects, Line: first.Line, Column: first.Column}
	}
	for _, clause := range group {
		var patterns []*ast.Pattern
		for _, param := range clause.Params {
			pattern := param.Pattern
			if pattern == nil {
				pattern = &ast.Pattern{Kind: "name", Name: param.Name, Line: param.Line, Column: param.Column}
			}
			patterns = append(patterns, pattern)
		}
		arm := ast.Arm{Pattern: patterns[0], Guard: clause.Guard, Body: clause.Body}
		if len(patterns) > 1 {
			arm.Pattern = &ast.Pattern{Kind: "tuple", Children: patterns, Line: clause.Line, Column: clause.Column}
		}
		match.Arms = append(match.Arms, arm)
	}
	merged.Body = []ast.Statement{match}
	return merged, nil
}

// implicitReturns turns the final expression of a body, and of each branch of
// a final if or case, into the value the body returns.
func implicitReturns(body []ast.Statement) {
	if len(body) == 0 {
		return
	}
	last := &body[len(body)-1]
	switch last.Kind {
	case "call":
		last.Kind = "return"
	case "if":
		implicitReturns(last.Then)
		implicitReturns(last.Else)
	case "case":
		for _, arm := range last.Arms {
			implicitReturns(arm.Body)
		}
	}
}

// yields marks the final expression of a body, and of each branch of a final
// if or case, as the value the body produces.
func yields(body []ast.Statement) {
	if len(body) == 0 {
		return
	}
	last := &body[len(body)-1]
	switch last.Kind {
	case "call":
		last.Kind = "yield"
	case "if":
		yields(last.Then)
		yields(last.Else)
	case "case":
		for _, arm := range last.Arms {
			yields(arm.Body)
		}
	}
}

// covers reports whether every vector of values of the given types matches at
// least one row of patterns. It splits on the constructors of the first
// column only when a row names one, so it terminates on recursive types.
func (c checker) covers(rows [][]*ast.Pattern, types []string) bool {
	if len(rows) == 0 {
		return false
	}
	if len(types) == 0 {
		return true
	}
	constructors := c.signature(types[0])
	named := false
	for _, row := range rows {
		named = named || c.constructorOf(row[0], types[0]) != ""
	}
	if !named || constructors == nil {
		var rest [][]*ast.Pattern
		for _, row := range rows {
			if open(row[0]) {
				rest = append(rest, row[1:])
			}
		}
		return c.covers(rest, types[1:])
	}
	for _, constructor := range constructors {
		var specialized [][]*ast.Pattern
		for _, row := range rows {
			if open(row[0]) {
				fill := make([]*ast.Pattern, len(constructor.types))
				for i := range fill {
					fill[i] = &ast.Pattern{Kind: "wildcard"}
				}
				specialized = append(specialized, append(fill, row[1:]...))
			} else if c.constructorOf(row[0], types[0]) == constructor.name {
				specialized = append(specialized, append(c.subpatterns(row[0]), row[1:]...))
			}
		}
		if !c.covers(specialized, append(append([]string{}, constructor.types...), types[1:]...)) {
			return false
		}
	}
	return true
}

type constructor struct {
	name  string
	types []string
}

// open reports a pattern that matches every value of its type.
func open(p *ast.Pattern) bool {
	return p.Kind == "name" || p.Kind == "wildcard" || (p.Kind == "map" && len(p.Keys) == 0)
}

// signature lists the constructors of a type with finitely many, or nil.
func (c checker) signature(t string) []constructor {
	if decl, _ := c.fieldTypes(t, 0); decl != nil {
		if decl.Kind == "struct" {
			_, types := c.fieldTypes(t, 0)
			return []constructor{{"struct", types}}
		}
		var out []constructor
		for i, variant := range decl.Variants {
			_, types := c.fieldTypes(t, i)
			out = append(out, constructor{variant.Name, types})
		}
		return out
	}
	if t == "boolean" {
		return []constructor{{"true", nil}, {"false", nil}}
	}
	if elem, ok := ast.ListElement(t); ok {
		return []constructor{{"nil", nil}, {"cons", []string{elem, t}}}
	}
	if parts, ok := ast.TupleElements(t); ok {
		return []constructor{{"tuple", parts}}
	}
	return nil
}

// constructorOf names the constructor a pattern requires, or "" when it
// requires none of a finite signature (open patterns, pins, other literals).
func (c checker) constructorOf(p *ast.Pattern, t string) string {
	switch {
	case p.Kind == "struct":
		return "struct"
	case p.Kind == "variant":
		if decl, _ := c.fieldTypes(t, 0); decl != nil && decl.Kind == "sum" {
			return decl.Variants[p.Index].Name
		}
	case p.Kind == "literal" && t == "boolean":
		if p.Value.Boolean {
			return "true"
		}
		return "false"
	case p.Kind == "list" && len(p.Children) == 0:
		return "nil"
	case p.Kind == "list":
		return "cons"
	case p.Kind == "tuple":
		return "tuple"
	}
	return ""
}

// arguments returns the sub-patterns of a constructor pattern.
func (c checker) subpatterns(p *ast.Pattern) []*ast.Pattern {
	switch p.Kind {
	case "struct":
		out := make([]*ast.Pattern, len(c.types[p.Name].Fields))
		for i := range out {
			out[i] = &ast.Pattern{Kind: "wildcard"}
		}
		for i, index := range p.Fields {
			out[index] = p.Children[i]
		}
		return out
	case "tuple", "variant":
		return p.Children
	case "list":
		if len(p.Children) == 0 {
			return nil
		}
		rest := &ast.Pattern{Kind: "list", Children: p.Children[1:], Tail: p.Tail}
		if len(rest.Children) == 0 && p.Tail != nil {
			rest = p.Tail
		}
		return []*ast.Pattern{p.Children[0], rest}
	}
	return nil
}
