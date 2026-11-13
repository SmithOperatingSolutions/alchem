package compiler

import "github.com/SmithOperatingSolutions/alchem/compiler/ast"

// A reduce that builds a map or a set normally copies a path of the map for
// every element, because each put returns a new map and leaves the old one
// valid. When the function given to reduce cannot let anything see an older
// version, the copies are wasted: the fold may change one map in place. That
// holds when the function uses its accumulator only
//
//   - as the map read by a lookup, and
//   - as its result: unchanged, or as the map of one put or update,
//
// and never inside a function it makes. Then every version but the newest is
// out of reach as soon as the next one exists. ownedFold recognizes such a
// reduce, and the generated code marks the starting map as owned by the fold
// (actor.MapOwned), which makes the puts change it in place.

// foldReads take a map or set first and return nothing that shares its
// structure.
var foldReads = map[string]bool{
	"get": true, "has_key": true, "length": true, "map_size": true,
	"Map.get": true, "Map.fetch": true, "Map.fetch!": true, "Map.has_key?": true,
	"MapSet.member?": true, "MapSet.size": true,
}

// foldPuts take a map or set first and return it with one entry put, through
// actor.MapPut.
var foldPuts = map[string]bool{
	"put": true, "Map.put": true, "Map.put_new": true, "Map.update": true, "MapSet.put": true,
}

// ownedFold returns the index of the starting value among the arguments of
// a reduce that may own its map, or -1.
func (g *generator) ownedFold(e *ast.Expr) int {
	// start and param are where the accumulator is among the call's
	// arguments and among the function's parameters.
	var start, param int
	switch {
	case e.Name == "reduce" && len(e.Args) == 3:
		start, param = 1, 0
	case e.Name == "Enum.reduce" && len(e.Args) == 3:
		start, param = 1, 1
	default:
		return -1
	}
	if e.Args[start].Kind == "owned" {
		return -1
	}
	if head, _ := ast.Split(e.Args[start].Type); head != "map" && head != "set" {
		return -1
	}
	var params []ast.Parameter
	var body []ast.Statement
	switch callback := e.Args[2]; callback.Kind {
	case "closure":
		params, body = callback.Params, callback.Body
	case "funcref":
		f := g.defs[callback.Name]
		if f == nil {
			return -1
		}
		params, body = f.Params, f.Body
	default:
		return -1
	}
	if len(params) != 2 {
		return -1
	}
	check := foldCheck{name: params[param].Name, ok: true}
	check.statements(body, true)
	if !check.ok || check.puts == 0 {
		return -1
	}
	return start
}

// foldCheck walks a function to see whether it uses the accumulator called
// name only in the ways a fold that owns its map allows.
type foldCheck struct {
	name string
	puts int
	ok   bool
}

func (c *foldCheck) accumulator(e *ast.Expr) bool {
	return e != nil && e.Kind == "name" && e.Name == c.name
}

// statements checks a body. result says whether its return and yield
// statements give the function's result.
func (c *foldCheck) statements(body []ast.Statement, result bool) {
	for _, s := range body {
		if (s.Kind == "return" || s.Kind == "yield") && result {
			c.result(s.Expr)
		} else {
			c.read(s.Expr)
		}
		c.statements(s.Then, result)
		c.statements(s.Else, result)
		for _, arm := range s.Arms {
			c.read(arm.Guard)
			c.statements(arm.Body, result)
		}
	}
}

// result checks an expression whose value the function returns.
func (c *foldCheck) result(e *ast.Expr) {
	switch {
	case e == nil || c.accumulator(e):
	case e.Kind == "call" && foldPuts[e.Name] && len(e.Args) > 0 && c.accumulator(e.Args[0]):
		// The other arguments are evaluated before the put changes the map.
		c.puts++
		for _, arg := range e.Args[1:] {
			c.read(arg)
		}
	case e.Kind == "value":
		// An if or case in result position: each branch gives the result.
		c.statements(e.Body, true)
	default:
		c.read(e)
	}
}

// read checks an expression evaluated on the way to the result: it may look
// things up in the accumulator and nothing else.
func (c *foldCheck) read(e *ast.Expr) {
	if e == nil || !c.ok {
		return
	}
	switch {
	case c.accumulator(e):
		c.ok = false
		return
	case e.Kind == "closure" || e.Kind == "funcref":
		// A function made here could read the map later, after a put.
		if mentions(e, c.name) {
			c.ok = false
		}
		return
	case e.Kind == "call" && foldReads[e.Name] && len(e.Args) > 0 && c.accumulator(e.Args[0]):
		for _, arg := range e.Args[1:] {
			c.read(arg)
		}
		return
	case e.Kind == "index" && c.accumulator(e.Left):
		if _, _, isMap := ast.MapParts(e.Left.Type); isMap {
			c.read(e.Right)
			return
		}
	}
	c.read(e.Left)
	c.read(e.Right)
	for _, arg := range e.Args {
		c.read(arg)
	}
	for _, key := range e.Keys {
		c.read(key)
	}
	c.statements(e.Body, false)
}

// mentions reports whether name is used anywhere in e.
func mentions(e *ast.Expr, name string) bool {
	if e == nil {
		return false
	}
	if e.Kind == "name" && e.Name == name {
		return true
	}
	if mentions(e.Left, name) || mentions(e.Right, name) {
		return true
	}
	for _, arg := range e.Args {
		if mentions(arg, name) {
			return true
		}
	}
	for _, key := range e.Keys {
		if mentions(key, name) {
			return true
		}
	}
	return mentionedIn(e.Body, name)
}

func mentionedIn(body []ast.Statement, name string) bool {
	for _, s := range body {
		if mentions(s.Expr, name) || mentionedIn(s.Then, name) || mentionedIn(s.Else, name) {
			return true
		}
		for _, arm := range s.Arms {
			if mentions(arm.Guard, name) || mentionedIn(arm.Body, name) {
				return true
			}
		}
	}
	return false
}
