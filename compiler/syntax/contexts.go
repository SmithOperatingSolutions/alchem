package syntax

import (
	"fmt"
	"sort"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// contexts gives the setup blocks and tests of a test file their types. A
// setup block's last expression is the context it provides, which the setup
// blocks and tests beneath it may receive as a parameter; a block that ends
// in a statement provides nothing and leaves the context as it was.
//
// setup_all runs first, then setup blocks from the outermost describe
// inwards, in the order written. Each receives the context in effect where
// it stands.
func (c *checker) contexts(p *ast.Program) error {
	var setups, tests []int
	for i := range p.Functions {
		switch f := &p.Functions[i]; {
		case f.Setup:
			setups = append(setups, i)
		case f.Test != "":
			tests = append(tests, i)
		}
	}
	depth := func(i int) int {
		if p.Functions[i].All {
			return -1
		}
		return len(ast.Groups(p.Functions[i].Group))
	}
	sort.SliceStable(setups, func(a, b int) bool { return depth(setups[a]) < depth(setups[b]) })
	// incoming is the context a function at index i receives: the value of
	// the last setup before it, among those that apply, that provides one.
	incoming := func(i int) string {
		f := &p.Functions[i]
		context := ""
		for _, s := range setups {
			setup := &p.Functions[s]
			applies := setup.All || ast.Within(f.Group, setup.Group)
			earlier := depth(s) < depth(i) || (depth(s) == depth(i) && s < i) || !f.Setup
			if s != i && applies && earlier && setup.Type != "void" && setup.Type != "tuple[]" {
				context = setup.Type
			}
		}
		return context
	}
	receive := func(f *ast.Function, context string) (map[string]string, error) {
		scope := map[string]string{}
		if len(f.Params) == 0 {
			return scope, nil
		}
		if context == "" {
			return nil, diagnostic(f.Line, f.Column, "this takes a context, but no setup block above it ends in a value")
		}
		param := &f.Params[0]
		if param.Type == "" && param.Pattern != nil {
			// The pattern is matched at the top of the body.
			name := fmt.Sprintf("arg$%d", c.fresh())
			f.Body = append([]ast.Statement{{Kind: "bind", Pattern: param.Pattern, Line: param.Line, Column: param.Column, Expr: &ast.Expr{Kind: "name", Name: name, Line: param.Line, Column: param.Column}}}, f.Body...)
			param.Name, param.Pattern = name, nil
		}
		param.Type = context
		scope[param.Name] = context
		return scope, nil
	}
	for _, i := range setups {
		f := &p.Functions[i]
		c.current, c.vars = f.Name, map[string]bool{}
		scope, err := receive(f, incoming(i))
		if err != nil {
			return err
		}
		if f.Type != "void" {
			continue // already typed by an earlier analysis of this tree
		}
		body := lambdaTail(f.Body)
		produced := ""
		inner := *c
		inner.yield, inner.infer = nil, &produced
		if _, err := inner.block(body, scope, "?"); err != nil {
			return err
		}
		if produced == "" {
			produced = "tuple[]"
		}
		f.Body, f.Type = body, produced
	}
	for _, i := range tests {
		if _, err := receive(&p.Functions[i], incoming(i)); err != nil {
			return err
		}
	}
	return nil
}
