package syntax

import (
	"fmt"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

func isBuiltin(name string) bool {
	switch name {
	case "prepend", "concat", "map", "filter", "reduce", "put", "get", "has_key", "Map.keys", "Map.values", "Map.entries", "Map.delete", "Map.merge",
		"List.reverse", "List.take", "List.drop", "List.contains", "List.sort", "List.range", "List.zip",
		"String.length", "String.slice", "String.contains", "String.split", "String.join", "String.trim", "String.upcase", "String.downcase",
		"Integer.to_string", "Integer.parse", "Time.monotonic", "Time.now",
		"System.argv", "IO.read_line", "IO.read_all", "File.read":
		return true
	}
	return false
}

var fixedSignatures = map[string]struct {
	arguments []string
	result    string
}{
	"String.length":     {[]string{"string"}, "integer"},
	"String.slice":      {[]string{"string", "integer", "integer"}, "string"},
	"String.contains":   {[]string{"string", "string"}, "boolean"},
	"String.split":      {[]string{"string", "string"}, "list[string]"},
	"String.join":       {[]string{"list[string]", "string"}, "string"},
	"String.trim":       {[]string{"string"}, "string"},
	"String.upcase":     {[]string{"string"}, "string"},
	"String.downcase":   {[]string{"string"}, "string"},
	"Integer.to_string": {[]string{"integer"}, "string"},
	"Integer.parse":     {[]string{"string"}, "result[integer,string]"},
	"Time.monotonic":    {nil, "integer"},
	"Time.now":          {nil, "integer"},
	"System.argv":       {nil, "list[string]"},
	"IO.read_line":      {nil, "option[string]"},
	"IO.read_all":       {nil, "string"},
	"File.read":         {[]string{"string"}, "result[string,string]"},
}

func (c checker) builtin(e *ast.Expr, scope map[string]string, want string) (string, error) {
	fail := func(msg string) (string, error) { return "", diagnostic(e.Line, e.Column, "%s", msg) }
	arity := 2
	switch e.Name {
	case "reduce", "put", "get":
		arity = 3
	case "Map.keys", "Map.values", "Map.entries", "List.reverse", "List.sort",
		"String.length", "String.trim", "String.upcase", "String.downcase", "Integer.to_string", "Integer.parse", "File.read":
		arity = 1
	case "String.slice":
		arity = 3
	case "Time.monotonic", "Time.now", "System.argv", "IO.read_line", "IO.read_all":
		arity = 0
	}
	if len(e.Args) != arity {
		return fail(fmt.Sprintf("%s requires %d arguments", e.Name, arity))
	}
	// Operations whose argument and result types are fixed.
	if signature, ok := fixedSignatures[e.Name]; ok {
		for i, argument := range signature.arguments {
			if _, err := c.expr(e.Args[i], scope, argument); err != nil {
				return "", err
			}
		}
		return signature.result, nil
	}
	switch e.Name {
	case "List.reverse", "List.sort", "List.take", "List.drop", "List.contains":
		expected := ""
		if _, ok := ast.ListElement(want); ok && e.Name != "List.contains" {
			expected = want
		}
		list, err := c.expr(e.Args[0], scope, expected)
		if err != nil {
			return "", err
		}
		elem, ok := ast.ListElement(list)
		if !ok {
			return fail(e.Name + " requires a list")
		}
		switch e.Name {
		case "List.sort":
			if elem != "integer" && elem != "string" && elem != "float" {
				return fail("List.sort requires list[integer], list[float] or list[string]")
			}
		case "List.take", "List.drop":
			if _, err = c.expr(e.Args[1], scope, "integer"); err != nil {
				return "", err
			}
		case "List.contains":
			if !c.compare(elem) {
				return fail("List.contains requires elements that support equality")
			}
			if _, err = c.expr(e.Args[1], scope, elem); err != nil {
				return "", err
			}
			return "boolean", nil
		}
		return list, nil
	case "List.range":
		for _, arg := range e.Args {
			if _, err := c.expr(arg, scope, "integer"); err != nil {
				return "", err
			}
		}
		return "list[integer]", nil
	case "List.zip":
		parts := []string{}
		for _, arg := range e.Args {
			list, err := c.expr(arg, scope)
			if err != nil {
				return "", err
			}
			elem, ok := ast.ListElement(list)
			if !ok {
				return fail("List.zip requires two lists")
			}
			parts = append(parts, elem)
		}
		return "list[tuple[" + parts[0] + "," + parts[1] + "]]", nil
	case "Map.merge":
		expected := ""
		if _, _, ok := ast.MapParts(want); ok {
			expected = want
		}
		mapping, err := c.expr(e.Args[0], scope, expected)
		if err != nil {
			return "", err
		}
		if _, _, ok := ast.MapParts(mapping); !ok {
			return fail("Map.merge requires two maps of the same type")
		}
		if _, err = c.expr(e.Args[1], scope, mapping); err != nil {
			return "", err
		}
		return mapping, nil
	case "Map.keys", "Map.values", "Map.entries", "Map.delete":
		expected := ""
		if e.Name == "Map.delete" {
			if _, _, ok := ast.MapParts(want); ok {
				expected = want
			}
		}
		mapping, err := c.expr(e.Args[0], scope, expected)
		if err != nil {
			return "", err
		}
		key, value, ok := ast.MapParts(mapping)
		if !ok {
			return fail(e.Name + " requires a map")
		}
		switch e.Name {
		case "Map.keys":
			return "list[" + key + "]", nil
		case "Map.values":
			return "list[" + value + "]", nil
		case "Map.entries":
			return "list[tuple[" + key + "," + value + "]]", nil
		default:
			if _, err = c.expr(e.Args[1], scope, key); err != nil {
				return "", err
			}
			return mapping, nil
		}
	case "prepend", "concat":
		expected := want
		if _, ok := ast.ListElement(expected); !ok {
			expected = ""
		}
		if expected == "" && e.Args[0].Kind == "list" && len(e.Args[0].Args) == 0 {
			t, err := c.expr(e.Args[1], scope)
			if err != nil {
				return "", err
			}
			expected = t
			if e.Name == "prepend" {
				expected = "list[" + t + "]"
			}
		}
		list, err := c.expr(e.Args[0], scope, expected)
		if err != nil {
			return "", err
		}
		elem, ok := ast.ListElement(list)
		if !ok {
			return fail(e.Name + " requires a list")
		}
		second := elem
		if e.Name == "concat" {
			second = list
		}
		if _, err = c.expr(e.Args[1], scope, second); err != nil {
			return "", err
		}
		return list, nil
	case "map", "filter", "reduce":
		callbackIndex := 1
		if e.Name == "reduce" {
			callbackIndex = 2
		}
		callback, err := c.expr(e.Args[callbackIndex], scope)
		if err != nil {
			return "", err
		}
		params, result, ok := ast.FunctionParts(callback)
		if !ok {
			return fail("callback must be a function reference/value")
		}
		count := 1
		if e.Name == "reduce" {
			count = 2
		}
		if len(params) != count {
			return fail("callback has wrong arity")
		}
		element := params[0]
		if e.Name == "reduce" {
			element = params[1]
		}
		list, err := c.expr(e.Args[0], scope, "list["+element+"]")
		if err != nil {
			return "", err
		}
		if e.Name == "reduce" {
			if result != params[0] {
				return fail("reduce callback must return accumulator type")
			}
			if _, err = c.expr(e.Args[1], scope, result); err != nil {
				return "", err
			}
			if want != "" && want != result {
				return fail("reduce result type mismatch")
			}
			return result, nil
		}
		if e.Name == "filter" {
			if result != "boolean" {
				return fail("filter callback must return boolean")
			}
			return list, nil
		}
		return "list[" + result + "]", nil
	default:
		expected := want
		if _, _, ok := ast.MapParts(expected); !ok {
			expected = ""
		}
		if e.Name != "put" {
			expected = ""
		}
		mapping, err := c.expr(e.Args[0], scope, expected)
		if err != nil {
			return "", err
		}
		key, value, ok := ast.MapParts(mapping)
		if !ok {
			return fail(e.Name + " requires a map")
		}
		if _, err = c.expr(e.Args[1], scope, key); err != nil {
			return "", err
		}
		if e.Name == "has_key" {
			return "boolean", nil
		}
		if _, err = c.expr(e.Args[2], scope, value); err != nil {
			return "", err
		}
		if e.Name == "put" {
			return mapping, nil
		}
		return value, nil
	}
}

// SimpleBuiltin is a builtin with one fixed signature. Go names the runtime
// function it lowers to; Fails marks those that can fail at run time and so
// also receive the process context and the call's source position.
type SimpleBuiltin struct {
	Params []string
	Result string
	Go     string
	Fails  bool
}

var SimpleBuiltins = map[string]SimpleBuiltin{
	"String.reverse":     {[]string{"string"}, "string", "strReverse", false},
	"String.starts_with": {[]string{"string", "string"}, "boolean", "strings.HasPrefix", false},
	"String.ends_with":   {[]string{"string", "string"}, "boolean", "strings.HasSuffix", false},
	"String.replace":     {[]string{"string", "string", "string"}, "string", "strings.ReplaceAll", false},
	"Float.from_integer": {[]string{"integer"}, "float", "floatFrom", false},
	"Float.to_string":    {[]string{"float"}, "string", "floatString", false},
	"Float.floor":        {[]string{"float"}, "float", "math.Floor", false},
	"Float.ceil":         {[]string{"float"}, "float", "math.Ceil", false},
	"Float.parse":        {[]string{"string"}, "result[float,string]", "floatParse", false},
	"File.write":         {[]string{"string", "string"}, "result[tuple[],string]", "fileWrite", false},
	"File.append":        {[]string{"string", "string"}, "result[tuple[],string]", "fileAppend", false},
	"File.remove":        {[]string{"string"}, "result[tuple[],string]", "fileRemove", false},
	"File.list":          {[]string{"string"}, "result[list[string],string]", "fileList", false},
	"File.exists":        {[]string{"string"}, "boolean", "fileExists", false},
	"System.env":         {[]string{"string"}, "option[string]", "systemEnv", false},
	"IO.write":           {[]string{"string"}, "void", "ioWrite", false},
}

// ReservedModule reports a namespace owned by builtin operations. Modules and
// types cannot take these names.
func ReservedModule(name string) bool {
	switch name {
	case "IO", "List", "Map", "Process", "Supervisor", "Server", "String", "Integer", "Float", "File", "System", "Time",
		"Kernel", "Enum", "Stream", "MapSet", "Path", "Base", "Bitwise", "Regex", "Task", "Agent", "Function", "JSON", "Date", "DateTime", "NaiveDateTime", "Calendar", "URI", "Version", "Duration", "Logger", "OptionParser", "Atom", "Keyword", "Port", "Node", "Registry", "DynamicSupervisor", "TCP", "HTTP", "Task.Supervisor", "TCP.Event", "UDP", "UDP.Event", "Gen", "IO.ANSI", "Port.Info", "File.Stat", "Version.Requirement", "PortEvent", "Range", "WebSocket", "WebSocket.Event", "Markup.Value", "Markup.Parts", "Crypto", "Markup":
		return true
	}
	return false
}
