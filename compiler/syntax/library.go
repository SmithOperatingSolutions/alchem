package syntax

import (
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// Library is one standard library function with a polymorphic signature.
// Parameter and result types may mention type variables, and a parameter
// written enum[T] accepts any enumerable of T: a list, a stream or range, a
// set, or a map (whose elements are its tuple[K,V] entries in key order).
type Library struct {
	Name   string
	Params []string
	Result string
	// Go is the runtime function. Ctx passes the process context first, for
	// functions that call back into Alchem, block or fail; Where passes the
	// call's source position last, for functions that can fail.
	Go         string
	Ctx, Where bool
	// Constraints on type variables. Each adds a generated function argument:
	// Equal an equality, Order a less-than, Show a conversion to string.
	// Keys must be map key types and Num integers or floats; they add none.
	Equal, Order, Show, Keys, Num []string
	// Cal variables must be one of the four date and time types.
	Cal []string
	// Codec variables are types whose values cross to another node; each
	// adds a generated argument that encodes and decodes the type.
	Codec []string
	// Read variables are types built from JSON; each adds a generated
	// argument that reads the type.
	Read []string
	// Fast names the variables whose equality argument is dropped, and "C"
	// appended to Go, when the type is directly comparable.
	Fast []string
	Vars []string
	// Explicit passes the bound types as Go type arguments, for functions
	// whose result type appears in no argument.
	Explicit bool
	// Lists says the runtime also has Go+"L", taking lists as they are
	// stored instead of iterators; it is called when every enumerable
	// argument is a list.
	Lists bool
	// Hidden entries serve a syntax form and are left out of help.
	Hidden bool
	// Key is the entry's key in Libraries.
	Key string
}

// Libraries is keyed by "Name/arity". A function overloaded by the types of
// its arguments has its further entries under "Name/arity#n", listed in
// Overloads.
var Libraries = map[string]Library{}

// Overloads lists the keys of the further entries of a "Name/arity", which
// are told apart from the first by the types of their arguments.
var Overloads = map[string][]string{}

// splitTypes splits a comma-separated list of types at the top level.
func splitTypes(list string) []string {
	var out []string
	depth, start := 0, 0
	for i, r := range list {
		switch r {
		case '[':
			depth++
		case ']':
			depth--
		case ',':
			if depth == 0 {
				out = append(out, strings.ReplaceAll(list[start:i], " ", ""))
				start = i + 1
			}
		}
	}
	if last := strings.ReplaceAll(list[start:], " ", ""); last != "" {
		out = append(out, last)
	}
	return out
}

// libAlso registers a further entry for a name and arity already registered,
// for arguments of other types: String.contains? takes a string or a list of
// them. The entries must differ in the type of at least one parameter that is
// not a function.
func libAlso(name, signature, target string) {
	left, _, _ := strings.Cut(signature, "->")
	base := name + "/" + strconv.Itoa(len(splitTypes(left)))
	if _, ok := Libraries[base]; !ok {
		panic("libAlso before lib for " + base)
	}
	key := base + "#" + strconv.Itoa(len(Overloads[base])+1)
	register(key, name, signature, target)
	Overloads[base] = append(Overloads[base], key)
}

// lib registers a function. signature is "param, param -> result" (the
// result may be "void"); target is the Go function followed by flags: ctx,
// where, lists for a variant taking lists directly, and eq:a, ord:a, show:a, key:a, num:a for constraints. "eq:a!" marks
// a directly-comparable fast path.
func lib(name, signature, target string) {
	left, _, _ := strings.Cut(signature, "->")
	key := name + "/" + strconv.Itoa(len(splitTypes(left)))
	if _, duplicate := Libraries[key]; duplicate {
		panic("duplicate library function " + key)
	}
	register(key, name, signature, target)
}

func register(key, name, signature, target string) {
	left, right, _ := strings.Cut(signature, "->")
	entry := Library{Name: name, Key: key, Params: splitTypes(left), Result: strings.ReplaceAll(right, " ", "")}
	fields := strings.Fields(target)
	entry.Go = fields[0]
	for _, flag := range fields[1:] {
		kind, variable, _ := strings.Cut(flag, ":")
		switch kind {
		case "explicit":
			entry.Explicit = true
		case "lists":
			entry.Lists = true
		case "hidden":
			entry.Hidden = true
		case "ctx":
			entry.Ctx = true
		case "where":
			entry.Where = true
		case "eq":
			if strings.HasSuffix(variable, "!") {
				variable = strings.TrimSuffix(variable, "!")
				entry.Fast = append(entry.Fast, variable)
			}
			entry.Equal = append(entry.Equal, variable)
		case "ord":
			entry.Order = append(entry.Order, variable)
		case "show":
			entry.Show = append(entry.Show, variable)
		case "key":
			entry.Keys = append(entry.Keys, variable)
		case "num":
			entry.Num = append(entry.Num, variable)
		case "cal":
			entry.Cal = append(entry.Cal, variable)
		case "codec":
			entry.Codec = append(entry.Codec, variable)
		case "read":
			entry.Read = append(entry.Read, variable)
		default:
			panic("library flag " + flag)
		}
	}
	seen := map[string]bool{}
	for _, t := range append(append([]string{}, entry.Params...), entry.Result) {
		entry.Vars = ast.TypeVariables(strings.ReplaceAll(t, "enum[", "list["), seen, entry.Vars)
	}
	Libraries[key] = entry
}

// libraryArities lists the argument counts a library function accepts.
func libraryArities(name string) []string {
	var out []string
	for key := range Libraries {
		if strings.HasPrefix(key, name+"/") && !strings.Contains(key, "#") {
			out = append(out, key[len(name)+1:])
		}
	}
	sort.Strings(out)
	return out
}

// Orderable reports a type with a defined order: integers, floats, strings,
// booleans, and tuples and lists built from them.
func Orderable(t string) bool {
	switch t {
	case "integer", "float", "string", "boolean", "atom":
		return true
	}
	if elem, ok := ast.ListElement(t); ok {
		return Orderable(elem)
	}
	if parts, ok := ast.TupleElements(t); ok {
		for _, part := range parts {
			if !Orderable(part) {
				return false
			}
		}
		return len(parts) > 0
	}
	return false
}

// library types a call to a standard library function.
func (c checker) library(e *ast.Expr, entry Library, scope map[string]string, want string) (string, error) {
	vars, bindings := set(entry.Vars), map[string]string{}
	if trial := map[string]string{}; want != "" && entry.Result != "void" && unify(entry.Result, want, vars, trial) {
		bindings = trial
	}
	order := make([]int, len(e.Args))
	for i := range order {
		order[i] = i
	}
	if entry.Name == "Enum.into" && len(e.Args) == 3 {
		// The transform says what the empty target collects.
		order = []int{0, 2, 1}
	}
	for _, i := range order {
		arg := e.Args[i]
		param := entry.Params[i]
		c.builtinReference(arg)
		head, inner := ast.Split(param)
		var t string
		var err error
		switch {
		case head == "enum":
			expected := ""
			if arg.Kind == "list" && len(arg.Args) == 0 && resolved(inner[0], vars, bindings) {
				expected = "list[" + instantiate(inner[0], vars, bindings) + "]"
			}
			if t, err = c.expr(arg, scope, expected); err != nil {
				return "", err
			}
			member, ok := element(t)
			if !ok {
				return "", diagnostic(arg.Line, arg.Column, "%s expects a list, map, set, stream or range here, found %s", entry.Name, t)
			}
			if !unify(inner[0], member, vars, bindings) {
				return "", diagnostic(arg.Line, arg.Column, "argument type mismatch for %s: expected elements of %s, found %s", entry.Name, instantiate(inner[0], vars, bindings), member)
			}
			continue
		case arg.Kind == "lambda" || arg.Kind == "capture":
			t, err = c.lambdaArgument(arg, scope, param, vars, bindings)
		default:
			expected := ""
			if resolved(param, vars, bindings) {
				expected = instantiate(param, vars, bindings)
			}
			// An empty target of Enum.into takes its type from the elements:
			// %{} for {key, value} tuples, [] for anything.
			if entry.Name == "Enum.into" && expected == "" && len(arg.Args) == 0 && len(arg.Keys) == 0 {
				element := bindings["a"]
				if head, parts := ast.Split(element); arg.Kind == "map" && head == "tuple" && len(parts) == 2 {
					expected = "map[" + parts[0] + "," + parts[1] + "]"
				} else if arg.Kind == "list" {
					expected = "list[" + element + "]"
				} else if arg.Kind == "call" && arg.Name == "MapSet.new" {
					expected = "set[" + element + "]"
				}
			}
			t, err = c.expr(arg, scope, expected)
		}
		if err != nil {
			return "", err
		}
		if !unify(param, t, vars, bindings) {
			return "", diagnostic(arg.Line, arg.Column, "argument type mismatch for %s: expected %s, found %s", entry.Name, instantiate(param, vars, bindings), t)
		}
	}
	fail := func(format string, args ...any) (string, error) {
		return "", diagnostic(e.Line, e.Column, format, args...)
	}
	e.TypeArgs = nil
	for _, name := range entry.Vars {
		bound, ok := bindings[name]
		if !ok {
			return fail("cannot infer the result type of %s here; annotate the binding it is assigned to", entry.Name)
		}
		e.TypeArgs = append(e.TypeArgs, bound)
	}
	for _, name := range entry.Equal {
		if !c.compare(bindings[name]) {
			return fail("%s needs values that support equality, which %s does not", entry.Name, bindings[name])
		}
	}
	for _, name := range entry.Order {
		if !Orderable(bindings[name]) {
			return fail("%s needs values with an order (integers, floats, strings, booleans, or tuples and lists of them), which %s does not have", entry.Name, bindings[name])
		}
	}
	for _, name := range entry.Show {
		if t := bindings[name]; t != "string" && t != "integer" && t != "float" && t != "boolean" && t != "atom" {
			return fail("%s needs strings, integers, floats or booleans, found %s", entry.Name, t)
		}
	}
	for _, name := range entry.Keys {
		if !ast.KeyType(bindings[name]) {
			return fail("%s needs keys that are integers, floats, strings, booleans, atoms or tuples of them, found %s", entry.Name, bindings[name])
		}
	}
	for _, name := range entry.Num {
		if t := bindings[name]; t != "integer" && t != "float" {
			return fail("%s needs integers or floats, found %s", entry.Name, t)
		}
	}
	if entry.Name == "Enum.into" {
		// What can be collected into depends on the target: a list or set
		// takes its elements, a map takes {key, value} tuples, and a
		// string takes strings.
		element, target := bindings["a"], bindings["c"]
		head, args := ast.Split(target)
		fits := false
		switch head {
		case "list", "set":
			fits = len(args) == 1 && args[0] == element
		case "map":
			fits = len(args) == 2 && element == "tuple["+args[0]+","+args[1]+"]"
		case "string":
			fits = element == "string"
		}
		if !fits {
			return fail("Enum.into cannot collect %s into %s: a list or set takes its own elements, a map takes {key, value} tuples, and a string takes strings", element, target)
		}
	}
	for _, name := range entry.Codec {
		if t := bindings[name]; t == "" {
			return fail("%s needs the type of the process's messages: annotate what it is bound to, as in orders: option[pid[Order]] = %s(...)", entry.Name, entry.Name)
		} else if blocked := c.unwired(t); blocked != "" {
			return fail("%s cannot be used with messages of type %s: %s cannot be sent to another node", entry.Name, t, blocked)
		}
	}
	for _, name := range entry.Read {
		if blocked := c.readable(bindings[name]); blocked != "" {
			return fail("%s cannot read %s: %s has no JSON form", entry.Name, bindings[name], blocked)
		}
	}
	for _, name := range entry.Cal {
		if t := bindings[name]; t != "Date" && t != "Time" && t != "NaiveDateTime" && t != "DateTime" {
			return fail("%s needs a Date, Time, NaiveDateTime or DateTime, found %s", entry.Name, t)
		}
	}
	e.Op = entry.Key
	result := instantiate(entry.Result, vars, bindings)
	if result != "void" {
		if message := c.wellFormed(result, c.vars); message != "" {
			return fail("%s", message)
		}
		if !ast.ValidType(result) {
			return fail("%s cannot produce %s", entry.Name, result)
		}
	}
	return result, nil
}

// overload picks among the entries of an overloaded library function the one
// whose parameters fit the arguments that tell them apart. Arguments are
// typed on copies, so that typing them again for the chosen entry starts
// from the same expressions. It returns the first entry when none fits, so
// that its message explains.
func (c checker) overload(e *ast.Expr, first Library, scope map[string]string) Library {
	entries := []Library{first}
	for _, key := range Overloads[first.Key] {
		entries = append(entries, Libraries[key])
	}
	// The arguments that tell the entries apart: those whose parameter is
	// not the same in every entry. A function written in place is told by
	// its number of parameters, and any other argument by its type.
	var telling []int
	for i := range first.Params {
		for _, entry := range entries[1:] {
			if entry.Params[i] != first.Params[i] {
				telling = append(telling, i)
				break
			}
		}
	}
	plain := map[int]string{}
	for _, entry := range entries {
		vars, bindings, fits := set(entry.Vars), map[string]string{}, true
		for _, i := range telling {
			param := entry.Params[i]
			if arity, written := functionArity(e.Args[i]); written {
				head, parts := ast.Split(param)
				fits = fits && head == "fn" && len(parts)-1 == arity
				continue
			}
			if !strings.Contains(param, "enum[") && len(ast.TypeVariables(param, map[string]bool{}, nil)) == 0 {
				// A parameter of one known type is what the argument is
				// typed against, as it would be for this entry: an empty
				// list then takes the type of the parameter.
				_, err := c.expr(cloneExpr(e.Args[i]), cloneScope(scope), param)
				fits = fits && err == nil
				continue
			}
			t, typed := plain[i]
			if !typed {
				found, err := c.expr(cloneExpr(e.Args[i]), cloneScope(scope))
				if err != nil {
					fits = false
					continue
				}
				t, plain[i] = found, found
			}
			if head, inner := ast.Split(param); head == "enum" {
				member, ok := element(t)
				fits = fits && ok && unify(inner[0], member, vars, bindings)
				continue
			}
			fits = fits && unify(param, t, vars, bindings)
		}
		if fits {
			return entry
		}
	}
	return first
}

// functionArity is the number of parameters of a function written in place:
// fn ... end, &(...) or &name/arity.
func functionArity(e *ast.Expr) (int, bool) {
	switch e.Kind {
	case "lambda":
		return len(e.Params), true
	case "capture":
		return int(e.Value.Integer), true
	case "funcref":
		if n, err := strconv.Atoi(e.Op); err == nil {
			return n, true
		}
	}
	return 0, false
}

// undefinedLibrary explains a call to a library function with the wrong
// number of arguments, or returns "".
func undefinedLibrary(name string, arity int) string {
	arities := libraryArities(name)
	if len(arities) == 0 {
		return ""
	}
	return fmt.Sprintf("%s/%d is undefined; %s takes %s arguments", name, arity, name, strings.Join(arities, " or "))
}
