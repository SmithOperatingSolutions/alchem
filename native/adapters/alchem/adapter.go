// The adapter lowers a restricted executable main or a pure integer function
// using the pinned Alchem parser and semantic analyzer.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

func unsupported(message string) error { return fmt.Errorf("E_UNSUPPORTED: %s", message) }
func lower(source, entry string) ([]byte, error) {
	p, err := syntax.ParseModule(seedByteSyntax(source))
	if err != nil {
		return nil, fmt.Errorf("E_SOURCE: %w", err)
	}
	if len(p.Functions) == 0 || len(p.Types) != 0 || len(p.Constants) != 0 || len(p.Imports) != 0 || len(p.Requires) != 0 || len(p.Macros) != 0 || len(p.Uses) != 0 || len(p.Protocols) != 0 {
		return nil, unsupported("expected integer functions without imports or declarations")
	}
	p.Library = entry != "" // Program mode retains upstream main/0 checking.
	if err := syntax.Analyze(&p); err != nil {
		return nil, fmt.Errorf("E_SOURCE: %w", err)
	}
	if entry == "" || len(p.Functions) > 1 || needsStructured(&p) {
		return lowerFunctions(&p, entry)
	}
	f := p.Functions[0]
	if len(f.Params) != 0 || f.Extern != "" || f.Guard != nil || f.Test != "" || f.Setup {
		return nil, unsupported("parameters, externs, guards and tests are unsupported")
	}
	if f.Name != entry || f.Type != "integer" {
		return nil, unsupported("probe entry must return integer")
	}
	instructions := []map[string]any{}
	bindings := map[string]string{}
	emit := func(instruction map[string]any) string {
		dest := fmt.Sprintf("v%d", len(instructions))
		instruction["dest"] = dest
		instructions = append(instructions, instruction)
		return dest
	}
	var expression func(*ast.Expr) (string, error)
	expression = func(e *ast.Expr) (string, error) {
		if e == nil || e.Type != "integer" {
			return "", unsupported("expected typed integer expression")
		}
		instruction := map[string]any{}
		var value int64
		switch {
		case e.Kind == "name":
			dest, ok := bindings[e.Name]
			if !ok {
				return "", unsupported("undefined local binding")
			}
			return dest, nil
		case e.Kind == "literal" && e.Value.Kind == "integer":
			value = e.Value.Integer
			instruction["op"], instruction["value"] = "const.i64", value
		case e.Kind == "unary" && e.Op == "-" && e.Left != nil && e.Left.Kind == "literal" && e.Left.Value.Kind == "integer":
			value = -e.Left.Value.Integer
			instruction["op"], instruction["value"] = "const.i64", value
		case e.Kind == "binary" && (e.Op == "+" || e.Op == "-" || e.Op == "*"):
			lhs, err := expression(e.Left)
			if err != nil {
				return "", err
			}
			rhs, err := expression(e.Right)
			if err != nil {
				return "", err
			}

			instruction["op"], instruction["lhs"], instruction["rhs"] = map[string]string{"+": "add.i64", "-": "sub.i64", "*": "mul.i64"}[e.Op], lhs, rhs
		default:
			return "", unsupported("only integer literals, addition, subtraction and multiplication are supported")
		}
		return emit(instruction), nil
	}
	result := ""
	for i, statement := range f.Body {
		last := i == len(f.Body)-1
		switch statement.Kind {
		case "bind":
			if statement.Pattern == nil || statement.Pattern.Kind != "name" {
				return nil, unsupported("only simple integer bindings are supported")
			}
			value, err := expression(statement.Expr)
			if err != nil {
				return nil, err
			}
			bindings[statement.Pattern.Name] = value
		case "return":
			if !last {
				return nil, unsupported("only a final probe return is supported")
			}
			value, err := expression(statement.Expr)
			if err != nil {
				return nil, err
			}
			result = value

		default:
			return nil, unsupported("statement is outside the supported integer subset")
		}
	}
	if result == "" {
		return nil, unsupported("probe requires a final integer return")
	}
	block := map[string]any{"label": "entry", "instructions": instructions, "terminator": map[string]string{"op": "ret", "value": result}}
	function := map[string]any{"name": "main", "params": []any{}, "return_type": "i64", "blocks": []any{block}}
	return json.MarshalIndent(map[string]any{"version": 1, "functions": []any{function}}, "", "  ")
}

func run(args []string, out io.Writer) error {
	flags := flag.NewFlagSet("alchem-source-probe", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	input := flags.String("input", "", "source library file")
	entry := flags.String("function", "", "pure integer function to probe")
	program := flags.Bool("program", false, "compile a restricted executable main")
	if err := flags.Parse(args); err != nil {
		return fmt.Errorf("E_INVALID_ARGUMENT: %w", err)
	}
	if flags.NArg() != 0 || *input == "" || (*program == (*entry != "")) {
		return fmt.Errorf("E_INVALID_ARGUMENT: input and exactly one of program/function are required; positional arguments are invalid")
	}
	source, err := os.ReadFile(*input)
	if err != nil {
		return fmt.Errorf("E_IO: %w", err)
	}
	output, err := lower(string(source), *entry)
	if err != nil {
		return err
	}
	if _, err := fmt.Fprintln(out, string(output)); err != nil {
		return fmt.Errorf("E_IO: %w", err)
	}
	return nil
}
func main() {
	if err := run(os.Args[1:], os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
