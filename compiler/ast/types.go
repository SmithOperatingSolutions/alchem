package ast

import (
	"strconv"
	"strings"
)

// FormatFloat renders a float the way Alchem prints and writes it: always with
// a fractional part, switching to exponent form for very large or small values.
func FormatFloat(f float64) string {
	magnitude := f
	if magnitude < 0 {
		magnitude = -magnitude
	}
	if magnitude != 0 && (magnitude >= 1e16 || magnitude < 1e-5) {
		text := strconv.FormatFloat(f, 'e', -1, 64)
		mantissa, exponent, _ := strings.Cut(text, "e")
		if !strings.Contains(mantissa, ".") {
			mantissa += ".0"
		}
		sign := ""
		if exponent[0] == '-' {
			sign = "-"
		}
		return mantissa + "e" + sign + strings.TrimLeft(exponent[1:], "0")
	}
	text := strconv.FormatFloat(f, 'f', -1, 64)
	if !strings.Contains(text, ".") {
		text += ".0"
	}
	return text
}

func ListElement(t string) (string, bool) {
	if strings.HasPrefix(t, "list[") && strings.HasSuffix(t, "]") {
		return t[5 : len(t)-1], true
	}
	return "", false
}
func TupleElements(t string) ([]string, bool) { return typeParts(t, "tuple") }
func typeParts(t, name string) ([]string, bool) {
	if !strings.HasPrefix(t, name+"[") || !strings.HasSuffix(t, "]") {
		return nil, false
	}
	inner := t[len(name)+1 : len(t)-1]
	if inner == "" {
		return []string{}, true
	}
	var parts []string
	start, depth := 0, 0
	for i, r := range inner {
		switch r {
		case '[':
			depth++
		case ']':
			depth--
		case ',':
			if depth == 0 {
				parts = append(parts, inner[start:i])
				start = i + 1
			}
		}
	}
	return append(parts, inner[start:]), true
}
func CapabilityElement(t string, kind string) (string, bool) {
	parts, ok := typeParts(t, kind)
	if !ok || len(parts) != 1 {
		return "", false
	}
	return parts[0], true
}
func Sendable(t string) bool {
	if _, _, ok := FunctionParts(t); ok || TypeVariable(t) {
		return false
	}
	// A stream holds the functions that produce it.
	if head, _ := Split(t); head == "stream" {
		return false
	}
	if head, args, ok := Named(t); ok && (head == "option" || head == "result") {
		for _, arg := range args {
			if !Sendable(arg) {
				return false
			}
		}
	}
	if e, ok := ListElement(t); ok {
		return Sendable(e)
	}
	if _, v, ok := MapParts(t); ok {
		return Sendable(v)
	}
	if parts, ok := TupleElements(t); ok {
		for _, p := range parts {
			if !Sendable(p) {
				return false
			}
		}
	}
	return true
}

// Split separates a type into its head and type arguments: "map[string,integer]"
// is "map" with two arguments, "integer" is "integer" with none.
func Split(t string) (string, []string) {
	open := strings.IndexByte(t, '[')
	if open < 0 || !strings.HasSuffix(t, "]") {
		return t, nil
	}
	parts, _ := typeParts(t, t[:open])
	return t[:open], parts
}

// Join is the inverse of Split.
func Join(head string, args []string) string {
	if len(args) == 0 && head != "tuple" {
		return head
	}
	return head + "[" + strings.Join(args, ",") + "]"
}

var builtinHeads = map[string]bool{"integer": true, "float": true, "string": true, "boolean": true, "atom": true, "port": true, "void": true, "list": true, "tuple": true, "map": true, "fn": true, "pid": true, "supervisor": true, "server": true, "option": true, "result": true, "stream": true, "set": true, "regex": true, "task": true, "agent": true, "step": true, "registry": true, "dynamic_supervisor": true, "socket": true, "http_server": true, "websocket": true, "generator": true, "file": true}

// TypeVariable reports a type variable: a lowercase name that is not a builtin type.
func TypeVariable(t string) bool {
	if t == "" || builtinHeads[t] || strings.ContainsAny(t, "[].,") {
		return false
	}
	first := []rune(t)[0]
	return first == '_' || first != []rune(strings.ToUpper(string(first)))[0]
}

// Named reports a declared struct or sum type, or the builtin option and result.
func Named(t string) (string, []string, bool) {
	head, args := Split(t)
	if head == "option" || head == "result" || head == "step" {
		return head, args, true
	}
	if head == "" || builtinHeads[head] || TypeVariable(head) {
		return "", nil, false
	}
	return head, args, true
}

// TypeVariables lists the type variables of a type in order of first appearance.
func TypeVariables(t string, seen map[string]bool, out []string) []string {
	head, args := Split(t)
	if TypeVariable(head) && !seen[head] {
		seen[head] = true
		out = append(out, head)
	}
	for _, arg := range args {
		out = TypeVariables(arg, seen, out)
	}
	return out
}

// Substitute replaces type variables by their bindings.
func Substitute(t string, bindings map[string]string) string {
	head, args := Split(t)
	if bound, ok := bindings[head]; ok && len(args) == 0 {
		return bound
	}
	if len(args) == 0 {
		return t
	}
	out := make([]string, len(args))
	for i, arg := range args {
		out[i] = Substitute(arg, bindings)
	}
	return Join(head, out)
}

// ValidType checks the shape of a type. Whether its named types exist and its
// type variables are in scope is decided during analysis.
func ValidType(t string) bool {
	head, args := Split(t)
	for _, arg := range args {
		if !ValidType(arg) {
			return false
		}
	}
	switch head {
	case "integer", "string", "boolean", "float", "atom":
		return len(args) == 0
	case "list", "option", "stream", "agent", "step", "generator":
		return len(args) == 1
	case "set":
		return len(args) == 1 && KeyType(args[0])
	case "task":
		return len(args) == 1 && Sendable(args[0])
	case "regex", "port", "dynamic_supervisor", "socket", "http_server", "websocket", "file":
		return len(args) == 0
	case "registry":
		return len(args) == 2 && KeyType(args[0])
	case "result":
		return len(args) == 2
	case "pid", "supervisor":
		return len(args) == 1 && Sendable(args[0])
	case "server":
		return len(args) == 2 && Sendable(args[0]) && Sendable(args[1])
	case "map":
		return len(args) == 2 && KeyType(args[0])
	case "fn":
		return len(args) >= 1
	case "tuple":
		return strings.HasPrefix(t, "tuple[")
	case "", "void":
		return false
	}
	return TypeVariable(head) && len(args) == 0 || !TypeVariable(head) && !strings.ContainsAny(head, "[], ")
}

func MapParts(t string) (string, string, bool) {
	parts, ok := typeParts(t, "map")
	if !ok || len(parts) != 2 {
		return "", "", false
	}
	return parts[0], parts[1], true
}

// KeyType reports a type whose values can key a map or be members of a set:
// integers, floats, strings, booleans, atoms, and tuples of them.
func KeyType(t string) bool {
	switch t {
	case "integer", "float", "string", "boolean", "atom":
		return true
	}
	if parts, ok := TupleElements(t); ok && len(parts) > 0 {
		for _, part := range parts {
			if !KeyType(part) {
				return false
			}
		}
		return true
	}
	return false
}
func FunctionParts(t string) ([]string, string, bool) {
	parts, ok := typeParts(t, "fn")
	if !ok || len(parts) == 0 {
		return nil, "", false
	}
	return parts[:len(parts)-1], parts[len(parts)-1], true
}
func Equatable(t string) bool {
	for _, kind := range []string{"pid", "supervisor"} {
		if _, ok := CapabilityElement(t, kind); ok {
			return false
		}
	}
	if head, _ := Split(t); head == "server" || head == "stream" || head == "regex" || head == "port" || head == "task" || head == "agent" || head == "registry" || head == "dynamic_supervisor" || head == "socket" || head == "http_server" || head == "websocket" || head == "generator" || head == "file" {
		return false
	}
	if _, _, ok := FunctionParts(t); ok || TypeVariable(t) {
		return false
	}
	if _, args, ok := Named(t); ok {
		for _, arg := range args {
			if !Equatable(arg) {
				return false
			}
		}
	}
	if e, ok := ListElement(t); ok {
		return Equatable(e)
	}
	if _, v, ok := MapParts(t); ok {
		return Equatable(v)
	}
	if parts, ok := TupleElements(t); ok {
		for _, p := range parts {
			if !Equatable(p) {
				return false
			}
		}
	}
	return true
}
