// Package guide renders the help the alchem command prints: the agent
// guide, syntax topics, library documentation and the generated reference
// files. Everything is produced from the compiler's own tables, so help
// cannot describe a function or construct the compiler does not have.
package guide

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// Command describes one subcommand of the alchem tool.
type Command struct {
	Name    string `json:"name"`
	Usage   string `json:"usage"`
	Summary string `json:"summary"`
	Flags   []Flag `json:"flags,omitempty"`
}

// Flag is one option of a command.
type Flag struct {
	Name    string `json:"name"`
	Summary string `json:"summary"`
	Default string `json:"default,omitempty"`
}

// Commands lists the subcommands in the order help shows them. The command
// line fills in Flags from the flags it actually parses.
var Commands = []Command{
	{Name: "build", Usage: "alchem build [options] <entry.alc>", Summary: "Compile a program to a native executable."},
	{Name: "run", Usage: "alchem run [options] <entry.alc> [-- arguments]", Summary: "Build a program and run it with the arguments that follow."},
	{Name: "alx", Usage: "alchem alx", Summary: "alx, the Alchem Language Executor: an interactive shell where each input is compiled and run with the definitions and statements before it."},
	{Name: "lsp", Usage: "alchem lsp", Summary: "A language server over standard input and output: diagnostics, hover documentation, completion, definitions, symbols and formatting."},
	{Name: "new", Usage: "alchem new <directory>", Summary: "Create a project: a library module, its test and a main program."},
	{Name: "check", Usage: "alchem check [options] <entry.alc>", Summary: "Report compile errors without building."},
	{Name: "fmt", Usage: "alchem fmt [--check] <path>...", Summary: "Format .alc files in place."},
	{Name: "test", Usage: "alchem test [options] <path>...", Summary: "Run *_test.alc files, with seeds, tags and coverage."},
	{Name: "syntax", Usage: "alchem syntax [--all] [--json] [topic]", Summary: "Explain a language construct, with a working example; without a topic, list them."},
	{Name: "doc", Usage: "alchem doc [--all] [--search text] [--json] [Module | Module.function | file.alc]", Summary: "Show library documentation, or the documentation written in a file."},
	{Name: "agent-guide", Usage: "alchem agent-guide [--json]", Summary: "Print the guide for coding agents: commands, topics, modules and how to learn more."},
	{Name: "agent-install", Usage: "alchem agent-install [--scope project|user] [--dir path] [--force] [--json] <agent> | --list", Summary: "Install a short instruction file that points a coding agent at agent-guide."},
	{Name: "docs", Usage: "alchem docs [--check] [--dir path]", Summary: "Write the generated reference files; --check fails if they are out of date."},
	{Name: "version", Usage: "alchem version [--json]", Summary: "Print the compiler's version and the Go toolchain builds use."},
}

// Usage is the text printed for a missing or unknown command.
func Usage() string {
	var b strings.Builder
	b.WriteString("usage: alchem <command> [options] [arguments]\n\ncommands:\n")
	for _, command := range Commands {
		fmt.Fprintf(&b, "  %-14s %s\n", command.Name, command.Summary)
	}
	b.WriteString("\nRun alchem <command> -h for a command's options, or alchem agent-guide for an overview.\n")
	return b.String()
}

// differences are what most often trips up someone writing Elixir from memory.
var differences = []string{
	"Statically typed: parameters carry types (`def add(a: integer, b: integer): integer do`), checked before anything runs.",
	"No `nil`, and `{:ok, value}` is not the convention: use `option[T]` (`some(x)` / `none`) and `result[T, E]` (`ok(x)` / `error(reason)`). Atoms exist as the type `atom`; a fixed set of alternatives is better as a sum type (`alchem syntax sum-types`).",
	"Library functions return `option` or `result` where Elixir returns `nil` or `{:ok, _}` tuples: `Map.get(map, key)` is an option, `Integer.parse(text)` a result.",
	"Bindings are immutable and cannot be rebound: `x = 1` then `x = 2` is an error; choose a new name.",
	"One module per file; other files are brought in with `import \"file.alc\"`, not `alias`, `use` or `require`.",
	"No behaviours, charlists, binaries pattern matching or `receive do` blocks. Protocols are resolved when the program is compiled (`alchem syntax protocols`), and macros are templates that substitute their arguments (`alchem syntax macros`): no code runs inside the compiler.",
	"Integers are 64-bit and overflow is an error; `1 + 1.5` is a type error; integer `/` truncates.",
	"Failures carry a string message: `raise(\"message\")`, rescued by matching the text. There are no exception structs.",
	"Map keys are integers, strings, booleans or atoms, and a map's keys share one type, as do its values. Use structs for records.",
	"Processes have typed mailboxes (`pid[T]`); `Server`, `Task` and `Agent` cover what GenServer, Task and Agent do.",
	"Nodes connect with `Node.start` and `Node.connect`, and messages between them are copied (`alchem syntax nodes`); a process is reached by a registered name, not by an Erlang-style pid from another system.",
	"Hex packages do not work. Go packages do, through `extern`.",
}

// featured names the functions whose first example introduces each group of
// library modules in the agent guide.
var featured = map[string][]string{
	"Core":             {"inspect", "then"},
	"Collections":      {"Enum.map", "Enum.reduce", "Enum.group_by", "Stream.chunk_every", "Map.update", "MapSet.new"},
	"Text":             {"String.split", "Regex.run", "Integer.parse", "JSON.decode"},
	"Dates and times":  {"Date.add", "DateTime.from_iso8601"},
	"Files and system": {"File.read", "File.stream!", "Path.join", "System.cmd"},
	"Concurrency":      {"Task.async_stream", "Server.start", "Agent.get_and_update"},
	"Testing":          {"assert", "assert_raise"},
}

func groups[T any](items []T, group func(T) string) ([]string, map[string][]T) {
	var order []string
	by := map[string][]T{}
	for _, item := range items {
		name := group(item)
		if _, seen := by[name]; !seen {
			order = append(order, name)
		}
		by[name] = append(by[name], item)
	}
	return order, by
}

func functionsByName() map[string]syntax.Function {
	out := map[string]syntax.Function{}
	for _, f := range syntax.Functions() {
		out[f.Name] = f
	}
	return out
}

func functionsOf(module string) []syntax.Function {
	var out []syntax.Function
	for _, f := range syntax.Functions() {
		if f.Module == module {
			out = append(out, f)
		}
	}
	return out
}

// firstExample is the leading example of a function: its source lines and
// the result shown under them.
func firstExample(f syntax.Function) string {
	var lines []string
	for _, line := range strings.Split(f.Examples, "\n") {
		if strings.HasPrefix(line, "alx>") && len(lines) > 0 && !strings.HasPrefix(lines[len(lines)-1], "alx>") {
			break
		}
		lines = append(lines, line)
	}
	return strings.Join(lines, "\n")
}

// AgentGuide is the overview a coding agent reads first.
func AgentGuide() string {
	var b strings.Builder
	b.WriteString("# Alchem agent guide\n\n")
	b.WriteString("Alchem is a statically typed, Elixir-inspired language compiled to native executables. Source files end in `.alc`. This guide is printed by the compiler you have installed, so it matches what that compiler accepts.\n\n")
	b.WriteString("## Commands\n\n")
	for _, command := range Commands {
		fmt.Fprintf(&b, "- `%s`: %s\n", command.Usage, command.Summary)
	}
	b.WriteString("\n## Looking things up\n\n")
	b.WriteString("Ask for one thing at a time; each answer is short.\n\n")
	b.WriteString("- `alchem syntax <topic>`: the rules of one construct and a working example. Topics are listed below.\n")
	b.WriteString("- `alchem doc <Module>`: every function of a library module with a one-line description.\n")
	b.WriteString("- `alchem doc <Module.function>`: signatures and examples, such as `alchem doc Enum.chunk_every`.\n")
	b.WriteString("- `alchem doc --search <text>`: functions and topics whose name or description contains the text.\n")
	b.WriteString("- `alchem doc <file.alc>`: the `@moduledoc` and `@doc` text of a project file.\n")
	b.WriteString("- Add `--json` to any of these for structured output.\n\n")
	b.WriteString("Every example shown by `syntax` and `doc` is compiled and run by the compiler's own tests.\n\n")
	b.WriteString("## A first program\n\n```elixir\n")
	if program, ok := syntax.TopicNamed("program"); ok && len(program.Examples) > 0 {
		b.WriteString(program.Examples[0].Program("Hello", false))
	}
	b.WriteString("```\n\n")
	b.WriteString("Save it as `hello.alc`, then `alchem build hello.alc && ./hello`.\n\n")
	b.WriteString("## Working loop\n\n")
	b.WriteString("1. `alchem check --json <entry.alc>` after each change. A diagnostic gives the file, line, column and message; fix all of them before going on.\n")
	b.WriteString("2. `alchem fmt <path>` formats files in place.\n")
	b.WriteString("3. `alchem test <path>` runs `*_test.alc` files. A failing run prints its seed; `--seed N` repeats that order. `--cover` reports line coverage.\n")
	b.WriteString("4. Document public functions with `@doc` and `alx>` examples, and run them with `doctest Module` (see `alchem syntax doctests`).\n\n")
	b.WriteString("## Differences from Elixir\n\n")
	for _, line := range differences {
		b.WriteString("- " + line + "\n")
	}
	b.WriteString("\n## Syntax topics\n\nRun `alchem syntax <topic>`.\n")
	order, topics := groups(syntax.Topics, func(t syntax.Topic) string { return t.Group })
	for _, group := range order {
		b.WriteString("\n**" + group + "**\n\n")
		for _, topic := range topics[group] {
			fmt.Fprintf(&b, "- `%s`: %s\n", topic.Name, topic.Summary)
		}
	}
	b.WriteString("\n## Library modules\n\nNo import is needed. The number is how many functions the module has; run `alchem doc <Module>` to list them.\n")
	byName := functionsByName()
	moduleOrder, modules := groups(syntax.Modules, func(m syntax.Module) string { return m.Group })
	for _, group := range moduleOrder {
		b.WriteString("\n**" + group + "**\n\n")
		for _, module := range modules[group] {
			fmt.Fprintf(&b, "- `%s` (%d): %s\n", module.Name, len(functionsOf(module.Name)), module.Summary)
		}
		if names := featured[group]; len(names) > 0 {
			b.WriteString("\n```elixir\n")
			for _, name := range names {
				b.WriteString(firstExample(byName[name]) + "\n")
			}
			b.WriteString("```\n")
		}
	}
	return b.String()
}

// AgentGuideJSON is the same overview as data.
func AgentGuideJSON() string {
	type entry struct {
		Name    string `json:"name"`
		Group   string `json:"group"`
		Summary string `json:"summary"`
		Count   int    `json:"functions,omitempty"`
	}
	out := struct {
		Commands    []Command `json:"commands"`
		Differences []string  `json:"differences_from_elixir"`
		Topics      []entry   `json:"topics"`
		Modules     []entry   `json:"modules"`
	}{Commands: Commands, Differences: differences}
	for _, topic := range syntax.Topics {
		out.Topics = append(out.Topics, entry{Name: topic.Name, Group: topic.Group, Summary: topic.Summary})
	}
	for _, module := range syntax.Modules {
		out.Modules = append(out.Modules, entry{Name: module.Name, Group: module.Group, Summary: module.Summary, Count: len(functionsOf(module.Name))})
	}
	return encode(out)
}

func encode(value any) string {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		panic(err)
	}
	return string(data) + "\n"
}

func suggest(name string, candidates []string) string {
	lower := strings.ToLower(name)
	var close []string
	for _, candidate := range candidates {
		other := strings.ToLower(candidate)
		if strings.Contains(other, lower) || strings.Contains(lower, other) {
			close = append(close, candidate)
		}
	}
	sort.Strings(close)
	if len(close) == 0 {
		return ""
	}
	if len(close) > 8 {
		close = close[:8]
	}
	return "; did you mean " + strings.Join(close, ", ") + "?"
}
