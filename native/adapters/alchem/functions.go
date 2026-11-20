package main

import (
	"encoding/json"
	"fmt"
	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// Keep real machine calls in the IR. Executable status validation is native;
// the adapter never executes source main/helpers during compilation.
func lowerFunctions(p *ast.Program, entry string) ([]byte, error) {
	functions := map[string]*ast.Function{}
	buffered := false
	construction := false
	packing := false
	slicing := false
	output := false
	dataBytes := 0
	for i := range p.Functions {
		f := &p.Functions[i]
		functions[f.Name] = f
		if f.Extern != "" || f.Guard != nil || f.Test != "" || f.Setup || len(f.Params) > 6 {
			return nil, unsupported("only direct integer functions with at most six parameters")
		}
		if f.Name == "main" && entry == "" {
			if f.Private || len(f.Params) != 0 || f.Type != "void" {
				return nil, unsupported("expected public void main/0")
			}
		} else if f.Type != "integer" && f.Type != "list[integer]" {
			return nil, unsupported("helper functions must return integer or byte list")
		}
		if f.Type == "list[integer]" {
			construction = true
		}
		for _, param := range f.Params {
			if (param.Type != "integer" && param.Type != "list[integer]") || param.Pattern != nil || param.Default != nil {
				return nil, unsupported("only named integer/byte-list parameters without defaults")
			}
		}
	}
	if entry != "" {
		target, ok := functions[entry]
		if !ok || len(target.Params) != 0 || target.Type != "integer" {
			return nil, unsupported("probe entry must exist and have no parameters")
		}
	}
	emitted := []map[string]any{}
	structured := false
	edges := map[string][]string{}
	symbol := func(name string) string {
		if name == "main" && entry == "" {
			return "main"
		}
		return "fn." + name
	}
	for _, f := range p.Functions {
		name := symbol(f.Name)
		bindings := map[string]string{}
		params := []map[string]string{}
		for i, param := range f.Params {
			id := fmt.Sprintf("p%d", i)
			bindings[param.Name] = id
			kind := "i64"
			if param.Type == "list[integer]" {
				kind = "bytes"
				buffered = true
			}
			params = append(params, map[string]string{"name": id, "type": kind})
		}

		instructions := []map[string]any{}
		next := 0
		nesting := 0
		emit := func(in map[string]any) string {
			dest := fmt.Sprintf("v%d", next)
			next++
			in["dest"] = dest
			instructions = append(instructions, in)
			return dest
		}
		clone := func(parent map[string]string) map[string]string {
			copy := map[string]string{}
			for name, value := range parent {
				copy[name] = value
			}
			return copy
		}
		var expr func(*ast.Expr) (string, error)
		var bodyValue func([]ast.Statement, string, string) (string, error)
		var conditional func(ast.Statement, string, string) (string, error)
		branch := func(body []ast.Statement, kind, mode string) (map[string]any, error) {
			savedInstructions, savedBindings := instructions, bindings
			instructions = []map[string]any{}
			bindings = clone(savedBindings)
			defer func() { instructions = savedInstructions; bindings = savedBindings }()
			result, err := bodyValue(body, kind, mode)
			if err != nil {
				return nil, err
			}
			return map[string]any{"instructions": instructions, "value": result}, nil
		}
		conditional = func(statement ast.Statement, kind, mode string) (string, error) {
			if statement.Name == "unless" {
				return "", unsupported("unless is outside the conditional subset")
			}
			if nesting >= 16 {
				return "", unsupported("conditional nesting exceeds 16")
			}
			nesting++
			defer func() { nesting-- }()
			structured = true
			cond, err := expr(statement.Expr)
			if err != nil {
				return "", err
			}
			yes, err := branch(statement.Then, kind, mode)
			if err != nil {
				return "", err
			}
			no, err := branch(statement.Else, kind, mode)
			if err != nil {
				return "", err
			}
			return emit(map[string]any{"op": "if." + kind, "cond": cond, "then": yes, "else": no}), nil
		}
		expr = func(e *ast.Expr) (string, error) {
			if e == nil || (e.Type != "integer" && e.Type != "boolean" && e.Type != "list[integer]") {
				return "", unsupported("expected integer or boolean expression")
			}
			kind := "i64"
			if e.Type == "list[integer]" {
				kind = "bytes"
				buffered = true
			}
			if e.Type == "boolean" {
				kind = "bool"
				structured = true
			}
			switch e.Kind {
			case "list":
				if e.Right != nil {
					return "", unsupported("list tails are unsupported")
				}
				literal := true
				for _, arg := range e.Args {
					if arg.Kind != "literal" || arg.Type != "integer" || arg.Value.Integer < 0 || arg.Value.Integer > 255 {
						literal = false
					}
				}
				if !literal {
					if len(e.Args) > 4096 {
						return "", unsupported("pack exceeds 4096 values")
					}
					ids := []string{}
					for _, arg := range e.Args {
						if arg.Type != "integer" {
							return "", unsupported("pack requires integer elements")
						}
						id, err := expr(arg)
						if err != nil {
							return "", err
						}
						ids = append(ids, id)
					}
					construction = true
					packing = true
					return emit(map[string]any{"op": "bytes.pack", "args": ids}), nil
				}
				values, err := sourceBytes(e)
				if err != nil {
					return "", err
				}
				dataBytes += len(values) + 8
				if dataBytes > 4<<20 {
					return "", unsupported("byte data exceeds 4 MiB")
				}
				return emit(map[string]any{"op": "bytes.const", "values": values}), nil
			case "name":
				id, ok := bindings[e.Name]
				if !ok {
					return "", unsupported("undefined binding")
				}
				return id, nil
			case "literal":
				if kind == "bool" {
					return emit(map[string]any{"op": "const.bool", "value": e.Value.Boolean}), nil
				}
				return emit(map[string]any{"op": "const.i64", "value": e.Value.Integer}), nil
			case "unary":
				if e.Op == "not" {
					value, err := expr(e.Left)
					if err != nil {
						return "", err
					}
					return emit(map[string]any{"op": "not.bool", "value": value}), nil
				}
				if e.Op != "-" {
					return "", unsupported("unsupported unary operator")
				}
				zero := emit(map[string]any{"op": "const.i64", "value": int64(0)})
				rhs, err := expr(e.Left)
				if err != nil {
					return "", err
				}
				return emit(map[string]any{"op": "sub.i64", "lhs": zero, "rhs": rhs}), nil
			case "binary":
				if e.Left.Type != "integer" || e.Right.Type != "integer" {
					return "", unsupported("only integer comparisons and arithmetic")
				}
				op, ok := map[string]string{"+": "add.i64", "-": "sub.i64", "*": "mul.i64", "==": "eq.i64", "!=": "ne.i64", "<": "lt.i64", "<=": "le.i64", ">": "gt.i64", ">=": "ge.i64"}[e.Op]
				if !ok {
					return "", unsupported("unsupported operator")
				}
				lhs, err := expr(e.Left)
				if err != nil {
					return "", err
				}
				rhs, err := expr(e.Right)
				if err != nil {
					return "", err
				}
				return emit(map[string]any{"op": op, "lhs": lhs, "rhs": rhs}), nil
			case "value":
				if len(e.Body) != 1 || e.Body[0].Kind != "if" {
					return "", unsupported("only if values are supported")
				}
				return conditional(e.Body[0], kind, "yield")
			case "call":
				if e.Name == "Enum.concat" && len(e.Args) == 2 {
					if e.Args[0].Type != "list[integer]" || e.Args[1].Type != "list[integer]" {
						return "", unsupported("concat requires byte lists")
					}
					lhs, err := expr(e.Args[0])
					if err != nil {
						return "", err
					}
					rhs, err := expr(e.Args[1])
					if err != nil {
						return "", err
					}
					construction = true
					return emit(map[string]any{"op": "bytes.concat", "lhs": lhs, "rhs": rhs}), nil
				}
				if e.Name == "Enum.slice" && len(e.Args) == 3 {
					if e.Args[0].Type != "list[integer]" || e.Args[1].Type != "integer" || e.Args[2].Type != "integer" {
						return "", unsupported("byte slice expects bytes, integer, integer")
					}
					b, err := expr(e.Args[0])
					if err != nil {
						return "", err
					}
					i, err := expr(e.Args[1])
					if err != nil {
						return "", err
					}
					c, err := expr(e.Args[2])
					if err != nil {
						return "", err
					}
					slicing = true
					construction = true
					return emit(map[string]any{"op": "bytes.slice", "buffer": b, "index": i, "count": c}), nil
				}
				if (e.Name == "Enum.count" && len(e.Args) == 1) || (e.Name == "Enum.at" && len(e.Args) == 3) {
					if e.Args[0].Type != "list[integer]" {
						return "", unsupported("only byte-list Enum operations")
					}
					buffered = true
					buffer, err := expr(e.Args[0])
					if err != nil {
						return "", err
					}
					if e.Name == "Enum.count" {
						return emit(map[string]any{"op": "bytes.len", "value": buffer}), nil
					}
					index, err := expr(e.Args[1])
					if err != nil {
						return "", err
					}
					fallback, err := expr(e.Args[2])
					if err != nil {
						return "", err
					}
					return emit(map[string]any{"op": "bytes.get", "buffer": buffer, "index": index, "default": fallback}), nil
				}
				target, ok := functions[e.Name]
				if !ok || target.Name == "main" || len(target.Params) != len(e.Args) {
					return "", unsupported("only direct calls to integer helpers")
				}
				args := []string{}
				for _, argument := range e.Args {
					id, err := expr(argument)
					if err != nil {
						return "", err
					}
					args = append(args, id)
				}
				edges[name] = append(edges[name], symbol(e.Name))
				return emit(map[string]any{"op": "call", "callee": symbol(e.Name), "args": args}), nil
			}
			return "", unsupported("unsupported expression")
		}
		bodyValue = func(body []ast.Statement, kind, mode string) (string, error) {
			for i, statement := range body {
				last := i == len(body)-1
				switch statement.Kind {
				case "bind":
					if statement.Pattern == nil || statement.Pattern.Kind != "name" {
						return "", unsupported("only simple bindings")
					}
					id, err := expr(statement.Expr)
					if err != nil {
						return "", err
					}
					bindings[statement.Pattern.Name] = id
				case "return", "yield":
					if !last || mode == "main" {
						return "", unsupported("only final branch/helper values")
					}
					return expr(statement.Expr)
				case "if":
					if !last {
						return "", unsupported("only terminal if statements; use an if value for continued computation")
					}
					return conditional(statement, kind, mode)
				case "output":
					e := statement.Expr
					if entry != "" || e == nil || e.Type != "string" || e.Kind != "literal" || e.Value.Kind != "string" {
						return "", unsupported("IO.puts requires a literal string in program mode")
					}
					text := []byte(e.Value.Text)
					if len(text)+1 > 1<<20 {
						return "", unsupported("output literal exceeds 1 MiB")
					}
					values := make([]int64, 0, len(text)+1)
					for _, value := range text {
						values = append(values, int64(value))
					}
					values = append(values, 10)
					dataBytes += len(values) + 8
					if dataBytes > 4<<20 {
						return "", unsupported("byte data exceeds 4 MiB")
					}
					value := emit(map[string]any{"op": "bytes.const", "values": values})
					emit(map[string]any{"op": "bytes.write", "value": value, "stream": "stdout"})
					output = true
				case "call":
					e := statement.Expr
					if mode != "main" || !last || e == nil || e.Kind != "call" || e.Name != "System.halt" || len(e.Args) != 1 {
						return "", unsupported("only final main System.halt")
					}
					return expr(e.Args[0])
				default:
					return "", unsupported("statement is outside the supported subset")
				}
			}
			if mode != "main" {
				return "", unsupported("branch/helper requires a final value")
			}
			return emit(map[string]any{"op": "const.i64", "value": int64(0)}), nil
		}
		mode := "return"
		if f.Name == "main" && entry == "" {
			mode = "main"
		}
		kind := "i64"
		if f.Type == "list[integer]" {
			kind = "bytes"
		}
		result, err := bodyValue(f.Body, kind, mode)
		if err != nil {
			return nil, err
		}
		block := map[string]any{"label": "entry", "instructions": instructions, "terminator": map[string]string{"op": "ret", "value": result}}
		emitted = append(emitted, map[string]any{"name": name, "params": params, "return_type": kind, "blocks": []any{block}})
	}
	if entry != "" {
		edges["main"] = []string{symbol(entry)}
		block := map[string]any{"label": "entry", "instructions": []any{map[string]any{"op": "call", "dest": "result", "callee": symbol(entry), "args": []string{}}}, "terminator": map[string]string{"op": "ret", "value": "result"}}
		emitted = append(emitted, map[string]any{"name": "main", "params": []any{}, "return_type": "i64", "blocks": []any{block}})
	}
	functionLimit := 256
	if slicing {
		functionLimit = 65535
	}
	if len(emitted) > functionLimit {
		return nil, unsupported("too many functions")
	}
	active := map[string]bool{}
	heights := map[string]int{}
	recursive := false
	var height func(string) (int, error)
	height = func(name string) (int, error) {
		if active[name] {
			recursive = true
			return 0, nil
		}
		if heights[name] != 0 {
			return heights[name], nil
		}
		active[name] = true
		h := 1
		for _, callee := range edges[name] {
			child, err := height(callee)
			if err != nil {
				return 0, err
			}
			if child+1 > h {
				h = child + 1
			}
		}
		active[name] = false

		heights[name] = h
		return h, nil
	}
	for _, f := range emitted {
		if _, err := height(f["name"].(string)); err != nil {
			return nil, err
		}
	}
	if entry != "" && !recursive && !buffered {
		for _, h := range heights {
			if h > 64 {
				return nil, unsupported("call depth exceeds 64")
			}
		}
	}

	version := 2
	if structured {
		version = 3
	}
	if recursive {
		version = 4
	}
	if buffered {
		version = 5
	}
	if entry == "" {
		version = 6
	}
	if output {
		version = 7
	}
	if construction {
		if entry != "" {
			return nil, unsupported("runtime byte construction requires program mode")
		}
		version = 8
	}
	if packing {
		version = 9
	}
	result := map[string]any{"version": version, "functions": emitted}
	if slicing {
		result["version"] = 11
		result["arena_bytes"] = 4 << 20
	}
	return json.MarshalIndent(result, "", "  ")
}

func needsStructured(p *ast.Program) bool {
	var expression func(*ast.Expr) bool
	var body func([]ast.Statement) bool
	body = func(statements []ast.Statement) bool {
		for _, s := range statements {
			if s.Kind == "if" || expression(s.Expr) || body(s.Then) || body(s.Else) {
				return true
			}
		}
		return false
	}
	expression = func(e *ast.Expr) bool {
		if e == nil {
			return false
		}
		if e.Type == "list[integer]" || e.Type == "boolean" || e.Kind == "value" || (e.Kind == "call" && e.Name != "System.halt") || expression(e.Left) || expression(e.Right) || body(e.Body) {
			return true
		}
		for _, arg := range e.Args {
			if expression(arg) {
				return true
			}
		}
		return false
	}
	for _, f := range p.Functions {
		if body(f.Body) {
			return true
		}
	}
	return false
}

// A deliberately byte-only subset of immutable list semantics.
func sourceBytes(e *ast.Expr) ([]int64, error) {
	if e.Kind != "list" || e.Type != "list[integer]" || e.Right != nil {
		return nil, unsupported("expected literal byte list")
	}
	if len(e.Args) > 1<<20 {
		return nil, unsupported("byte literal exceeds 1 MiB")
	}
	values := make([]int64, 0, len(e.Args))
	for _, arg := range e.Args {
		if arg.Kind != "literal" || arg.Type != "integer" || arg.Value.Integer < 0 || arg.Value.Integer > 255 {
			return nil, unsupported("byte lists require integer literals 0..255")
		}
		values = append(values, arg.Value.Integer)
	}
	return values, nil
}
