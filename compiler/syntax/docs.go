package syntax

import (
	"sort"
	"strings"
)

// Doc is the documentation of one library function, shared by its arities:
// a one-sentence summary and examples in the alx> form doctests use. Every
// example is compiled and run by the test suite, so what help shows is true.
type Doc struct {
	Summary, Examples string
}

// Docs is keyed by function name, such as "Enum.map" or "abs".
var Docs = map[string]Doc{}

func doc(name, summary string, examples ...string) {
	if _, duplicate := Docs[name]; duplicate {
		panic("duplicate documentation for " + name)
	}
	Docs[name] = Doc{summary, strings.Join(examples, "\n")}
}

// Module is one library module as help presents it. Group gathers related
// modules so that a reader can ask for one area at a time.
type Module struct {
	Name, Group, Summary string
}

// Modules is in presentation order.
var Modules []Module

func module(name, group, summary string) {
	Modules = append(Modules, Module{name, group, summary})
}

// legacySignatures holds the signatures of operations checked by dedicated
// code rather than the signature table: the process runtime and the earliest
// collection builtins.
var legacySignatures = map[string][]string{}

func legacy(name string, signatures ...string) {
	legacySignatures[name] = signatures
}

// assertions lists the assertions, which are called without a module name but
// presented together.
var assertions = map[string]bool{"assert": true, "refute": true, "assert_raise": true, "assert_in_delta": true, "flunk": true, "capture_io": true, "on_exit": true, "assert_receive": true, "refute_receive": true, "assert_received": true, "refute_received": true}

// Function is everything help knows about one function.
type Function struct {
	Name, Module, Local  string
	Signatures, Requires []string
	Doc
}

// ModuleOf names the module a function is presented under.
func ModuleOf(name string) string {
	if assertions[name] {
		return "Testing"
	}
	if index := strings.LastIndex(name, "."); index > 0 {
		return name[:index]
	}
	return "Kernel"
}

func signature(name string, params []string, result string) string {
	if result == "void" {
		return name + "(" + strings.Join(params, ", ") + ")"
	}
	return name + "(" + strings.Join(params, ", ") + ") -> " + result
}

// Functions lists every library function, sorted by module and name.
func Functions() []Function {
	byName := map[string]*Function{}
	add := func(name, signature string, requires ...string) {
		f := byName[name]
		if f == nil {
			module := ModuleOf(name)
			f = &Function{Name: name, Module: module, Local: strings.TrimPrefix(name, module+"."), Doc: Docs[name]}
			byName[name] = f
		}
		f.Signatures = append(f.Signatures, signature)
		for _, requirement := range requires {
			if !strings.Contains(strings.Join(f.Requires, "\n"), requirement) {
				f.Requires = append(f.Requires, requirement)
			}
		}
	}
	for _, entry := range Libraries {
		if entry.Hidden {
			continue
		}
		var requires []string
		for _, constraint := range []struct {
			vars []string
			text string
		}{{entry.Equal, "supports equality"}, {entry.Order, "has an order"}, {entry.Show, "is a string, integer, float or boolean"}, {entry.Keys, "is a map key type"}, {entry.Num, "is an integer or float"}, {entry.Cal, "is a Date, Time, NaiveDateTime or DateTime"}} {
			for _, name := range constraint.vars {
				requires = append(requires, name+" "+constraint.text)
			}
		}
		add(entry.Name, signature(entry.Name, entry.Params, entry.Result), requires...)
	}
	for name, entry := range SimpleBuiltins {
		add(name, signature(name, entry.Params, entry.Result))
	}
	for name, entry := range fixedSignatures {
		add(name, signature(name, entry.arguments, entry.result))
	}
	for name, signatures := range legacySignatures {
		for _, text := range signatures {
			add(name, text)
		}
	}
	out := make([]Function, 0, len(byName))
	for _, f := range byName {
		sort.Slice(f.Signatures, func(i, j int) bool {
			if len(f.Signatures[i]) != len(f.Signatures[j]) {
				return len(f.Signatures[i]) < len(f.Signatures[j])
			}
			return f.Signatures[i] < f.Signatures[j]
		})
		sort.Strings(f.Requires)
		out = append(out, *f)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Module != out[j].Module {
			return out[i].Module < out[j].Module
		}
		return out[i].Local < out[j].Local
	})
	return out
}

func init() {
	module("Kernel", "Core", "Functions called without a module name: arithmetic helpers, list head and tail, conversion to text, and inspect.")
	module("Atom", "Core", "Names used as values, written :name. Atoms compare, sort, key maps and match in patterns.")
	module("Function", "Core", "Helpers for working with functions as values.")
	module("Bitwise", "Core", "Bitwise operations on integers.")
	module("Enum", "Collections", "Eager operations over any enumerable: lists, maps, sets, ranges and streams. Results are finished values.")
	module("Stream", "Collections", "Lazy operations over any enumerable. Nothing runs until the stream is consumed by an Enum function, so streams may be infinite.")
	module("List", "Collections", "Operations specific to lists, such as positional updates.")
	module("Map", "Collections", "Immutable maps with integer, string or boolean keys.")
	module("Keyword", "Collections", "Keyword lists: lists of {atom, value} pairs written [name: value], kept in order and allowing a key more than once.")
	module("MapSet", "Collections", "Immutable sets of integers, strings or booleans; the type is set[T].")
	module("String", "Text", "UTF-8 strings. Lengths and positions count Unicode code points.")
	module("Regex", "Text", "Regular expressions in RE2 syntax: no backreferences or lookaround. Written ~r/pattern/ or compiled from text.")
	module("Integer", "Text", "Integer parsing, formatting and number theory.")
	module("Float", "Text", "Float parsing, formatting and rounding.")
	module("Base", "Text", "Base 16, 32 and 64 encoding.")
	module("JSON", "Text", "Converts between JSON text and the builtin JSON type.")
	module("Date", "Dates and times", "Calendar dates, written ~D[2026-01-05].")
	module("Time", "Dates and times", "Times of day, written ~T[13:04:05], and the program clock.")
	module("NaiveDateTime", "Dates and times", "A date and time without a time zone, written ~N[2026-01-05 13:04:05].")
	module("DateTime", "Dates and times", "A date and time in a time zone: UTC when written ~U[2026-01-05T13:04:05Z], another zone after DateTime.shift_zone.")
	module("Calendar", "Dates and times", "Formatting shared by the four date and time types.")
	module("Duration", "Dates and times", "An amount of time per unit, for shifting dates and times: Duration.months(1), Duration.add(...).")
	module("File", "Files and system", "Reading, writing and managing files; File.stream! reads lazily.")
	module("Path", "Files and system", "Manipulating file paths as text.")
	module("IO", "Files and system", "Standard input, output and error.")
	module("System", "Files and system", "Arguments, environment, external commands and exit.")
	module("URI", "Text", "Percent-encoding and query strings.")
	module("Version", "Text", "Parsing and comparing semantic versions.")
	module("OptionParser", "Files and system", "Reads command-line switches into a map.")
	module("Logger", "Files and system", "Leveled messages on standard error.")
	module("Port", "Files and system", "Runs an external program and exchanges text with it: its output arrives as messages, a line at a time.")
	module("Process", "Concurrency", "Lightweight processes with typed mailboxes, links and monitors.")
	module("Node", "Concurrency", "Connects this program to others so that their processes can exchange messages, which are copied between them.")
	module("Supervisor", "Concurrency", "Restarts child processes according to a strategy.")
	module("Server", "Concurrency", "A process owning a state that answers typed requests in order.")
	module("Task", "Concurrency", "Runs a function in its own process and collects its result.")
	module("Task.Supervisor", "Concurrency", "Runs tasks as temporary children of a supervisor: a task supervisor is a dynamic_supervisor, so DynamicSupervisor's functions apply to it too.")
	module("Agent", "Concurrency", "A process holding a state that functions read and update.")
	module("Testing", "Testing", "Assertions for test files, called without a module name.")
	module("Gen", "Testing", "Generators of random values for check all properties. Values grow with each run, and a failing value shrinks to the smallest that still fails.")
}
