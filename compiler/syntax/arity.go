package syntax

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// Functions of one name with different numbers of parameters are different
// functions, as in Elixir: size/1 and size/2. A module that defines a name
// with more than one arity names each one name/arity inside the compiler, and
// each call is resolved by its number of arguments: those in the module when
// it is parsed, and qualified calls from other modules once every module is
// loaded.

// span is the range of argument counts a function accepts: its parameters,
// less those with a default.
type span struct {
	name     string
	min, max int
}

func spanOf(f *ast.Function) span {
	s := span{name: f.Name, max: len(f.Params)}
	for _, param := range f.Params {
		if param.Default == nil {
			s.min++
		}
	}
	return s
}

// pick returns the function among spans that takes count arguments.
func pick(spans []span, count int) (string, bool) {
	for _, s := range spans {
		if s.min <= count && count <= s.max {
			return s.name, true
		}
	}
	return "", false
}

// arityName is the name of one arity of an overloaded function.
func arityName(name string, arity int) string { return name + "/" + strconv.Itoa(arity) }

// plainName removes the arity from a name: size/2 is size.
func plainName(name string) string {
	if i := strings.LastIndex(name, "/"); i > 0 {
		if _, err := strconv.Atoi(name[i+1:]); err == nil {
			return name[:i]
		}
	}
	return name
}

// overloadable functions take part: tests, setup blocks and implementations
// of protocols are named otherwise.
func overloadable(f *ast.Function) bool {
	return f.Test == "" && !f.Setup && f.Protocol == ""
}

// separateArities names each arity of a name the module defines more than
// once, and resolves the module's own calls to them.
func separateArities(p *ast.Program) error {
	arities := map[string]map[int]bool{}
	for i := range p.Functions {
		f := &p.Functions[i]
		if !overloadable(f) {
			continue
		}
		if arities[f.Name] == nil {
			arities[f.Name] = map[int]bool{}
		}
		arities[f.Name][len(f.Params)] = true
	}
	spans := map[string][]span{}
	for i := range p.Functions {
		f := &p.Functions[i]
		if overloadable(f) && len(arities[f.Name]) > 1 {
			original := f.Name
			f.Name = arityName(f.Name, len(f.Params))
			s := spanOf(f)
			for _, other := range spans[original] {
				if other.name != s.name && s.min <= other.max && other.min <= s.max {
					return diagnostic(f.Line, f.Column, "%s and %s both accept %d arguments; a default argument overlaps another arity", plainName(other.name)+"/"+strconv.Itoa(other.max), original+"/"+strconv.Itoa(s.max), max(s.min, other.min))
				}
			}
			if len(spans[original]) == 0 || spans[original][len(spans[original])-1].name != s.name {
				spans[original] = append(spans[original], s)
			}
		}
	}
	if len(spans) == 0 {
		return nil
	}
	var problem error
	rename := func(e *ast.Expr) {
		if (e.Kind != "call" && e.Kind != "funcref") || problem != nil {
			return
		}
		candidates, overloaded := spans[e.Name]
		if !overloaded {
			return
		}
		if e.Kind == "funcref" {
			arity, err := strconv.Atoi(e.Op)
			if err != nil {
				problem = diagnostic(e.Line, e.Column, "%s has more than one arity; write %s", e.Name, referenceList(candidates))
				return
			}
			if name, ok := pick(candidates, arity); ok {
				e.Name = name
				return
			}
			problem = diagnostic(e.Line, e.Column, "%s takes %s; no %s/%d is defined", e.Name, arityList(candidates), e.Name, arity)
			return
		}
		if name, ok := pick(candidates, len(e.Args)); ok {
			e.Name = name
			return
		}
		problem = diagnostic(e.Line, e.Column, "%s takes %s; no %s/%d is defined", e.Name, arityList(candidates), e.Name, len(e.Args))
	}
	for i := range p.Functions {
		f := &p.Functions[i]
		walkFunction(f, rename)
	}
	for i := range p.Macros {
		walkBlock(p.Macros[i].Body, rename)
	}
	return problem
}

func referenceList(spans []span) string {
	parts := []string{}
	for _, s := range spans {
		parts = append(parts, "&"+plainName(s.name)+"/"+strconv.Itoa(s.max))
	}
	return strings.Join(parts, " or ")
}

func arityList(spans []span) string {
	parts := []string{}
	for _, s := range spans {
		parts = append(parts, plainName(s.name)+"/"+strconv.Itoa(s.max))
	}
	return strings.Join(parts, " or ")
}

// ResolveArities resolves the calls of a loaded program to functions of
// other modules by their number of arguments, and keeps their private
// functions private.
func ResolveArities(p *ast.Program) error {
	spans := map[string][]span{}
	module := map[string]string{}
	private := map[string]bool{}
	for i := range p.Functions {
		f := &p.Functions[i]
		if !overloadable(f) || plainName(f.Name) == f.Name {
			continue
		}
		plain := plainName(f.Name)
		spans[plain] = append(spans[plain], spanOf(f))
		module[f.Name], private[f.Name] = f.Module, f.Private
	}
	if len(spans) == 0 {
		return nil
	}
	var problem error
	for i := range p.Functions {
		caller := &p.Functions[i]
		walkFunction(caller, func(e *ast.Expr) {
			candidates, overloaded := spans[e.Name]
			if (e.Kind != "call" && e.Kind != "funcref") || !overloaded || problem != nil {
				return
			}
			count := len(e.Args)
			if e.Kind == "funcref" {
				arity, err := strconv.Atoi(e.Op)
				if err != nil {
					problem = fmt.Errorf("%s:%d:%d: %s has more than one arity; write %s", caller.Source, e.Line, e.Column, e.Name, referenceList(candidates))
					return
				}
				count = arity
			}
			name, ok := pick(candidates, count)
			switch {
			case !ok:
				problem = fmt.Errorf("%s:%d:%d: %s takes %s; no %s/%d is defined", caller.Source, e.Line, e.Column, e.Name, arityList(candidates), e.Name, count)
			case private[name] && module[name] != caller.Module:
				problem = fmt.Errorf("%s:%d:%d: %s is private to its module", caller.Source, e.Line, e.Column, e.Name)
			default:
				e.Name = name
			}
		})
	}
	return problem
}

func walkFunction(f *ast.Function, visit func(*ast.Expr)) {
	for _, param := range f.Params {
		walkExpr(param.Default, visit)
	}
	walkExpr(f.Guard, visit)
	walkBlock(f.Body, visit)
}

func walkExpr(e *ast.Expr, visit func(*ast.Expr)) {
	if e == nil {
		return
	}
	visit(e)
	walkExpr(e.Left, visit)
	walkExpr(e.Right, visit)
	for _, arg := range e.Args {
		walkExpr(arg, visit)
	}
	for _, key := range e.Keys {
		walkExpr(key, visit)
	}
	for _, param := range e.Params {
		walkExpr(param.Default, visit)
	}
	walkBlock(e.Body, visit)
}

func walkBlock(body []ast.Statement, visit func(*ast.Expr)) {
	for _, s := range body {
		walkExpr(s.Expr, visit)
		walkBlock(s.Then, visit)
		walkBlock(s.Else, visit)
		for _, arm := range s.Arms {
			walkExpr(arm.Guard, visit)
			walkBlock(arm.Body, visit)
		}
	}
}
