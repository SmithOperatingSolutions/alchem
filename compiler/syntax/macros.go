package syntax

import (
	"fmt"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// Macros are templates. A call of a macro is replaced, before anything is
// typed, by a copy of the macro's quoted code in which each
// unquote(parameter) has become the corresponding argument. Nothing is run:
// expansion only copies and substitutes. The copy is kept apart from the
// code around it in two ways. A name the template binds is given a new name
// in each expansion, so it can neither capture nor be captured by a name at
// the call. A function the template calls is the one in the macro's own
// module, wherever the macro is used.

// expansionLimit stops a macro that expands to a call of itself.
const expansionLimit = 64

// located carries the source file of a problem found while expanding.
type macroError struct {
	Source string
	Err    error
}

func (e *macroError) Error() string { return e.Err.Error() }
func (e *macroError) Unwrap() error { return e.Err }

// MacroSource returns the file a macro expansion error belongs to, if the
// error is one.
func MacroSource(err error) (string, error, bool) {
	if located, ok := err.(*macroError); ok {
		return located.Source, located.Err, true
	}
	return "", err, false
}

type expander struct {
	modules map[string]*ast.Program
	counter int
}

// ExpandMacros replaces every macro call and use in the modules of one
// program. The modules have been parsed and lowered; their macros stay
// behind, used up.
func ExpandMacros(modules []*ast.Program) error {
	x := &expander{modules: map[string]*ast.Program{}}
	for _, module := range modules {
		x.modules[module.Module] = module
	}
	for _, module := range modules {
		fail := func(line, column int, format string, args ...any) error {
			return &macroError{module.Source, diagnostic(line, column, format, args...)}
		}
		for _, use := range module.Uses {
			if err := x.use(module, use); err != nil {
				return &macroError{module.Source, err}
			}
		}
		for i := range module.Functions {
			f := &module.Functions[i]
			body, err := x.block(module, f.Body, 0)
			if err != nil {
				return &macroError{module.Source, err}
			}
			f.Body = body
		}
		for _, macro := range module.Macros {
			if x.function(module, macro.Name) {
				return fail(macro.Line, macro.Column, "%s is both a macro and a function", macro.Name)
			}
		}
	}
	return nil
}

func (x *expander) function(module *ast.Program, name string) bool {
	for _, f := range module.Functions {
		if f.Name == name {
			return true
		}
	}
	return false
}

// find resolves a call to a macro: a bare name in the module that defines
// it, or Module.name from anywhere.
func (x *expander) find(module *ast.Program, name string) (*ast.Macro, *ast.Program) {
	owner, local := module, name
	if index := strings.LastIndex(name, "."); index >= 0 {
		owner, local = x.modules[name[:index]], name[index+1:]
	}
	if owner == nil {
		return nil, nil
	}
	for i := range owner.Macros {
		if owner.Macros[i].Name == local && local != "__using__" {
			return &owner.Macros[i], owner
		}
	}
	return nil, nil
}

// block expands the statements of one body. A macro called as a statement
// is replaced by all the statements of its template.
func (x *expander) block(module *ast.Program, body []ast.Statement, depth int) ([]ast.Statement, error) {
	if body == nil {
		return nil, nil
	}
	var out []ast.Statement
	for _, s := range body {
		if s.Kind == "call" && s.Expr != nil && s.Expr.Kind == "call" {
			if macro, owner := x.find(module, s.Expr.Name); macro != nil {
				expanded, err := x.instantiate(module, owner, macro, s.Expr, depth)
				if err != nil {
					return nil, err
				}
				out = append(out, expanded...)
				continue
			}
		}
		if err := x.expr(module, s.Expr, depth); err != nil {
			return nil, err
		}
		var err error
		if s.Then, err = x.block(module, s.Then, depth); err != nil {
			return nil, err
		}
		if s.Else, err = x.block(module, s.Else, depth); err != nil {
			return nil, err
		}
		for i := range s.Arms {
			if err = x.expr(module, s.Arms[i].Guard, depth); err != nil {
				return nil, err
			}
			if s.Arms[i].Body, err = x.block(module, s.Arms[i].Body, depth); err != nil {
				return nil, err
			}
		}
		out = append(out, s)
	}
	return out, nil
}

// expr expands the macro calls inside an expression. One used as a value
// must expand to a single expression, or to one if, case or the like.
func (x *expander) expr(module *ast.Program, e *ast.Expr, depth int) error {
	if e == nil {
		return nil
	}
	if e.Kind == "call" {
		if macro, owner := x.find(module, e.Name); macro != nil {
			expanded, err := x.instantiate(module, owner, macro, e, depth)
			if err != nil {
				return err
			}
			if len(expanded) != 1 {
				return diagnostic(e.Line, e.Column, "%s expands to %d statements, so it is used as a statement, not as a value", e.Name, len(expanded))
			}
			only := expanded[0]
			if only.Kind == "call" {
				*e = *only.Expr
				return nil
			}
			if only.Kind != "if" && only.Kind != "case" {
				return diagnostic(e.Line, e.Column, "%s expands to a statement without a value, so it is used as a statement", e.Name)
			}
			*e = ast.Expr{Kind: "value", Body: []ast.Statement{only}, Line: e.Line, Column: e.Column}
			return nil
		}
		if e.Op == "do" {
			return diagnostic(e.Line, e.Column, "only a macro takes a do ... end block, and %s is not one", e.Name)
		}
	}
	if err := x.expr(module, e.Left, depth); err != nil {
		return err
	}
	if err := x.expr(module, e.Right, depth); err != nil {
		return err
	}
	for _, arg := range append(append([]*ast.Expr{}, e.Args...), e.Keys...) {
		if err := x.expr(module, arg, depth); err != nil {
			return err
		}
	}
	var err error
	e.Body, err = x.block(module, e.Body, depth)
	return err
}

// instantiate makes the code one call of a macro stands for.
func (x *expander) instantiate(module, owner *ast.Program, macro *ast.Macro, call *ast.Expr, depth int) ([]ast.Statement, error) {
	if depth >= expansionLimit {
		return nil, diagnostic(call.Line, call.Column, "%s keeps expanding into more macro calls", call.Name)
	}
	if len(call.Args) != len(macro.Params) {
		return nil, diagnostic(call.Line, call.Column, "%s takes %d arguments, not %d", call.Name, len(macro.Params), len(call.Args))
	}
	if (macro.Block != "") != (call.Op == "do") {
		if macro.Block != "" {
			return nil, diagnostic(call.Line, call.Column, "%s takes a do ... end block", call.Name)
		}
		return nil, diagnostic(call.Line, call.Column, "%s does not take a do ... end block", call.Name)
	}
	// The arguments are expanded first, in the module that wrote them.
	for _, arg := range call.Args {
		if err := x.expr(module, arg, depth); err != nil {
			return nil, err
		}
	}
	given, err := x.block(module, call.Body, depth)
	if err != nil {
		return nil, err
	}
	arguments := map[string]*ast.Expr{}
	for i, name := range macro.Params {
		arguments[name] = call.Args[i]
	}
	body := cloneBlock(macro.Body)
	x.counter++
	x.rename(body, fmt.Sprintf("$m%d", x.counter))
	x.adopt(body, owner, module)
	placeBlock(body, call.Line, call.Column)
	body, err = x.fill(body, arguments, macro.Block, given, call)
	if err != nil {
		return nil, err
	}
	// The template may itself call macros, of its own module.
	return x.block(templateScope{module, owner}.program(), body, depth+1)
}

// templateScope is where names in an expanded template are looked up: the
// macro's own module for its bare macro calls, the using module otherwise.
type templateScope struct{ user, owner *ast.Program }

func (s templateScope) program() *ast.Program {
	if s.user == s.owner {
		return s.user
	}
	// Bare names have been qualified by adopt, so the user's module serves.
	return s.user
}

// fill puts the arguments where the template says unquote(name). A block
// argument written as a statement is spliced in whole.
func (x *expander) fill(body []ast.Statement, arguments map[string]*ast.Expr, blockName string, given []ast.Statement, call *ast.Expr) ([]ast.Statement, error) {
	var problem error
	hole := func(e *ast.Expr) (string, bool) {
		if e == nil || e.Kind != "call" || e.Name != "unquote" {
			return "", false
		}
		if len(e.Args) != 1 || e.Args[0].Kind != "name" {
			problem = diagnostic(call.Line, call.Column, "unquote takes the name of one of the macro's parameters")
			return "", false
		}
		return e.Args[0].Name, true
	}
	var block func([]ast.Statement) []ast.Statement
	var expr func(*ast.Expr)
	expr = func(e *ast.Expr) {
		if e == nil {
			return
		}
		if name, ok := hole(e); ok {
			switch {
			case arguments[name] != nil:
				*e = *cloneExpr(arguments[name])
			case name == blockName && len(given) == 1 && given[0].Kind == "call":
				*e = *cloneExpr(given[0].Expr)
			case name == blockName:
				*e = ast.Expr{Kind: "value", Body: cloneBlock(given), Line: call.Line, Column: call.Column}
				if len(given) != 1 || (given[0].Kind != "if" && given[0].Kind != "case") {
					problem = diagnostic(call.Line, call.Column, "the block given to %s is used as a value there, so it must be a single expression", call.Name)
				}
			default:
				problem = diagnostic(call.Line, call.Column, "unquote(%s) names no parameter of %s", name, call.Name)
			}
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
	block = func(list []ast.Statement) []ast.Statement {
		if list == nil {
			return nil
		}
		var out []ast.Statement
		for _, s := range list {
			if s.Kind == "call" {
				if name, ok := hole(s.Expr); ok && name == blockName {
					out = append(out, cloneBlock(given)...)
					continue
				}
			}
			expr(s.Expr)
			s.Then, s.Else = block(s.Then), block(s.Else)
			for i := range s.Arms {
				expr(s.Arms[i].Guard)
				s.Arms[i].Body = block(s.Arms[i].Body)
			}
			out = append(out, s)
		}
		return out
	}
	body = block(body)
	return body, problem
}

// rename gives every name the template binds a name of its own, so that two
// expansions, or an expansion and the code around it, cannot clash.
func (x *expander) rename(body []ast.Statement, suffix string) {
	bound := map[string]bool{}
	var pattern func(*ast.Pattern, bool)
	pattern = func(p *ast.Pattern, collect bool) {
		if p == nil {
			return
		}
		switch {
		case (p.Kind == "name" || p.Kind == "in" || p.Kind == "typed") && collect:
			bound[p.Name] = true
		case (p.Kind == "name" || p.Kind == "pin" || p.Kind == "in" || p.Kind == "typed") && !collect && bound[p.Name]:
			p.Name += suffix
		}
		for _, child := range p.Children {
			pattern(child, collect)
		}
		pattern(p.Tail, collect)
	}
	var block func([]ast.Statement, bool)
	var expr func(*ast.Expr, bool)
	expr = func(e *ast.Expr, collect bool) {
		if e == nil {
			return
		}
		for i := range e.Params {
			parameter := &e.Params[i]
			if parameter.Pattern != nil {
				pattern(parameter.Pattern, collect)
			} else if collect {
				bound[parameter.Name] = true
			} else if bound[parameter.Name] {
				parameter.Name += suffix
			}
		}
		if !collect && (e.Kind == "name" || e.Kind == "call" || e.Kind == "invoke") && bound[e.Name] {
			e.Name += suffix
		}
		expr(e.Left, collect)
		expr(e.Right, collect)
		for _, arg := range e.Args {
			expr(arg, collect)
		}
		for _, key := range e.Keys {
			expr(key, collect)
		}
		block(e.Body, collect)
	}
	block = func(list []ast.Statement, collect bool) {
		for i := range list {
			s := &list[i]
			pattern(s.Pattern, collect)
			if s.Kind == "bind" && s.Pattern != nil && s.Pattern.Kind == "name" {
				s.Name = s.Pattern.Name
			}
			expr(s.Expr, collect)
			block(s.Then, collect)
			block(s.Else, collect)
			for j := range s.Arms {
				pattern(s.Arms[j].Pattern, collect)
				expr(s.Arms[j].Guard, collect)
				block(s.Arms[j].Body, collect)
			}
		}
	}
	block(body, true)
	// A parameter of the macro is not a binding of the template.
	delete(bound, "unquote")
	block(body, false)
}

// adopt makes the template's calls of its own module's functions work in
// the module that uses the macro, by writing them Module.function.
func (x *expander) adopt(body []ast.Statement, owner, user *ast.Program) {
	if owner == user {
		return
	}
	local := map[string]bool{}
	for _, f := range owner.Functions {
		local[f.Name] = true
	}
	for _, macro := range owner.Macros {
		local[macro.Name] = true
	}
	var block func([]ast.Statement)
	var expr func(*ast.Expr)
	expr = func(e *ast.Expr) {
		if e == nil {
			return
		}
		if (e.Kind == "call" || e.Kind == "funcref") && local[e.Name] {
			e.Name = owner.Module + "." + e.Name
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
		for i := range list {
			expr(list[i].Expr)
			block(list[i].Then)
			block(list[i].Else)
			for j := range list[i].Arms {
				expr(list[i].Arms[j].Guard)
				block(list[i].Arms[j].Body)
			}
		}
	}
	block(body)
}

// placeBlock gives copied statements the position of the call they replace,
// which is where a problem in them is reported.
func placeBlock(body []ast.Statement, line, column int) {
	for i := range body {
		s := &body[i]
		s.Line, s.Column = line, column
		if s.Expr != nil {
			placeDeep(s.Expr, line, column)
		}
		placeBlock(s.Then, line, column)
		placeBlock(s.Else, line, column)
		for j := range s.Arms {
			if s.Arms[j].Guard != nil {
				placeDeep(s.Arms[j].Guard, line, column)
			}
			placeBlock(s.Arms[j].Body, line, column)
		}
	}
}

func placeDeep(e *ast.Expr, line, column int) {
	if e == nil {
		return
	}
	e.Line, e.Column = line, column
	placeDeep(e.Left, line, column)
	placeDeep(e.Right, line, column)
	for _, arg := range append(append([]*ast.Expr{}, e.Args...), e.Keys...) {
		placeDeep(arg, line, column)
	}
	placeBlock(e.Body, line, column)
}

// use adds the functions of another module's __using__ template to a
// module, with the options given put where the template unquotes them.
func (x *expander) use(module *ast.Program, use ast.Use) error {
	owner := x.modules[use.Module]
	if owner == nil {
		return diagnostic(use.Line, use.Column, "use %s: no imported module has that name", use.Module)
	}
	var template *ast.Macro
	for i := range owner.Macros {
		if owner.Macros[i].Name == "__using__" {
			template = &owner.Macros[i]
		}
	}
	if template == nil {
		return diagnostic(use.Line, use.Column, "%s has no __using__ macro to use", use.Module)
	}
	arguments := map[string]*ast.Expr{}
	for i, name := range use.Names {
		arguments[name] = use.Values[i]
	}
	for _, parameter := range template.Params {
		if arguments[parameter] == nil {
			return diagnostic(use.Line, use.Column, "use %s needs the option %s:", use.Module, parameter)
		}
	}
	if len(arguments) != len(template.Params) {
		return diagnostic(use.Line, use.Column, "use %s takes the options %s", use.Module, strings.Join(template.Params, ", "))
	}
	call := &ast.Expr{Kind: "call", Name: "use " + use.Module, Line: use.Line, Column: use.Column}
	for _, definition := range template.Definitions {
		f := definition
		if x.function(module, f.Name) {
			return diagnostic(use.Line, use.Column, "use %s defines %s, which this module also defines", use.Module, f.Name)
		}
		f.Params = append([]ast.Parameter{}, f.Params...)
		f.Body = cloneBlock(f.Body)
		x.adopt(f.Body, owner, module)
		body, err := x.fill(f.Body, arguments, "", nil, call)
		if err != nil {
			return err
		}
		f.Body, f.Source = body, ""
		module.Functions = append(module.Functions, f)
	}
	return nil
}
