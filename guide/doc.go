package guide

import (
	"fmt"
	"os"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

func moduleNamed(name string) (syntax.Module, bool) {
	for _, module := range syntax.Modules {
		if strings.EqualFold(module.Name, name) {
			return module, true
		}
	}
	return syntax.Module{}, false
}

// DocIndex lists the library modules by group.
func DocIndex() string {
	var b strings.Builder
	b.WriteString("Library modules. Run alchem doc <Module> for its functions, alchem doc <Module.function> for signatures and examples, or alchem doc --search <text>.\n")
	order, modules := groups(syntax.Modules, func(m syntax.Module) string { return m.Group })
	for _, group := range order {
		b.WriteString("\n" + group + "\n")
		for _, module := range modules[group] {
			fmt.Fprintf(&b, "  %-14s %s\n", module.Name, module.Summary)
		}
	}
	return b.String()
}

func indented(text string) string {
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		lines[i] = "    " + line
	}
	return strings.Join(lines, "\n")
}

func functionText(f syntax.Function) string {
	var b strings.Builder
	b.WriteString(f.Name + "\n\n")
	for _, signature := range f.Signatures {
		b.WriteString("    " + signature + "\n")
	}
	b.WriteString("\n" + f.Summary + "\n")
	if len(f.Requires) > 0 {
		b.WriteString("\nRequires: " + strings.Join(f.Requires, "; ") + ".\n")
	}
	if f.Examples != "" {
		b.WriteString("\nExamples\n\n" + indented(f.Examples) + "\n")
	}
	return b.String()
}

func moduleText(module syntax.Module, all bool) string {
	var b strings.Builder
	functions := functionsOf(module.Name)
	fmt.Fprintf(&b, "%s (%s)\n\n%s\n", module.Name, module.Group, module.Summary)
	if module.Name == "Kernel" || module.Name == "Testing" {
		b.WriteString("These are called without a module name: " + functions[0].Name + "(...).\n")
	}
	if all {
		for _, f := range functions {
			b.WriteString("\n" + functionText(f))
		}
		return b.String()
	}
	b.WriteString("\n")
	width := 0
	for _, f := range functions {
		width = max(width, len(f.Local))
	}
	for _, f := range functions {
		fmt.Fprintf(&b, "  %-*s  %s\n", width, f.Local, f.Summary)
	}
	example := functions[0].Name
	b.WriteString("\nRun alchem doc " + example + " for signatures and examples, or alchem doc --all " + module.Name + " for every function in full.\n")
	return b.String()
}

type functionJSON struct {
	Name       string   `json:"name"`
	Module     string   `json:"module"`
	Signatures []string `json:"signatures"`
	Summary    string   `json:"summary"`
	Requires   []string `json:"requires,omitempty"`
	Examples   string   `json:"examples,omitempty"`
}

type moduleJSON struct {
	Name      string         `json:"name"`
	Group     string         `json:"group,omitempty"`
	Summary   string         `json:"summary"`
	Types     []typeJSON     `json:"types,omitempty"`
	Functions []functionJSON `json:"functions"`
}

type typeJSON struct {
	Name       string `json:"name"`
	Definition string `json:"definition"`
	Summary    string `json:"summary,omitempty"`
}

func functionData(f syntax.Function) functionJSON {
	return functionJSON{f.Name, f.Module, f.Signatures, f.Summary, f.Requires, f.Examples}
}

func moduleData(module syntax.Module) moduleJSON {
	out := moduleJSON{Name: module.Name, Group: module.Group, Summary: module.Summary}
	for _, f := range functionsOf(module.Name) {
		out.Functions = append(out.Functions, functionData(f))
	}
	return out
}

// find resolves a query to a module or a function of the library.
func find(query string) (syntax.Module, []syntax.Function, error) {
	if module, ok := moduleNamed(query); ok {
		return module, nil, nil
	}
	// Module.function, or a bare name from Kernel or Testing; an arity
	// suffix such as Enum.map/2 is accepted and ignored.
	name := query
	if index := strings.LastIndex(name, "/"); index > 0 {
		name = name[:index]
	}
	var names []string
	for _, f := range syntax.Functions() {
		if strings.EqualFold(f.Name, name) {
			return syntax.Module{}, []syntax.Function{f}, nil
		}
		names = append(names, f.Name)
	}
	for _, module := range syntax.Modules {
		names = append(names, module.Name)
	}
	return syntax.Module{}, nil, fmt.Errorf("no module or function %q%s (alchem doc lists modules; alchem doc --search text searches)", query, suggest(name, names))
}

// Doc documents a library module, a library function, or a source file.
func Doc(query string, all, asJSON bool) (string, error) {
	if strings.HasSuffix(query, ".alc") {
		return FileDoc(query, asJSON)
	}
	if query == "" {
		if asJSON {
			var out []moduleJSON
			for _, module := range syntax.Modules {
				entry := moduleData(module)
				if !all {
					entry.Functions = nil
				}
				out = append(out, entry)
			}
			return encode(out), nil
		}
		if all {
			var parts []string
			for _, module := range syntax.Modules {
				parts = append(parts, moduleText(module, true))
			}
			return strings.Join(parts, "\n"), nil
		}
		return DocIndex(), nil
	}
	module, functions, err := find(query)
	if err != nil {
		return "", err
	}
	if functions != nil {
		if asJSON {
			return encode(functionData(functions[0])), nil
		}
		return functionText(functions[0]), nil
	}
	if asJSON {
		return encode(moduleData(module)), nil
	}
	return moduleText(module, all), nil
}

// Search finds functions, modules and syntax topics whose name or
// description contains the text.
func Search(text string, asJSON bool) (string, error) {
	needle := strings.ToLower(strings.TrimSpace(text))
	if needle == "" {
		return "", fmt.Errorf("search needs some text")
	}
	type hit struct {
		Kind    string `json:"kind"`
		Name    string `json:"name"`
		Summary string `json:"summary"`
		Command string `json:"command"`
	}
	var hits []hit
	matches := func(parts ...string) bool {
		return strings.Contains(strings.ToLower(strings.Join(parts, " ")), needle)
	}
	for _, topic := range syntax.Topics {
		if matches(topic.Name, topic.Summary, strings.Join(topic.Notes, " ")) {
			hits = append(hits, hit{"topic", topic.Name, topic.Summary, "alchem syntax " + topic.Name})
		}
	}
	for _, module := range syntax.Modules {
		if matches(module.Name, module.Summary) {
			hits = append(hits, hit{"module", module.Name, module.Summary, "alchem doc " + module.Name})
		}
	}
	// Functions matching by name come before those matching by description.
	var described []hit
	for _, f := range syntax.Functions() {
		entry := hit{"function", f.Name, f.Summary, "alchem doc " + f.Name}
		if matches(f.Name) {
			hits = append(hits, entry)
		} else if matches(f.Summary) {
			described = append(described, entry)
		}
	}
	hits = append(hits, described...)
	if asJSON {
		if hits == nil {
			hits = []hit{}
		}
		return encode(hits), nil
	}
	if len(hits) == 0 {
		return "", fmt.Errorf("nothing matches %q", text)
	}
	var b strings.Builder
	for _, entry := range hits {
		fmt.Fprintf(&b, "%-8s %-28s %s\n", entry.Kind, entry.Name, entry.Summary)
	}
	b.WriteString("\nRun alchem doc <name> for a module or function, alchem syntax <name> for a topic.\n")
	return b.String(), nil
}

func parameters(params []ast.Parameter) string {
	var parts []string
	for _, parameter := range params {
		name := parameter.Name
		if name == "" {
			name = "_"
		}
		if parameter.Type != "" {
			name += ": " + parameter.Type
		}
		parts = append(parts, name)
	}
	return strings.Join(parts, ", ")
}

func typeDefinition(decl ast.TypeDecl) string {
	name := decl.Name
	if decl.Local != "" {
		name = decl.Local
	}
	if len(decl.Params) > 0 {
		name += "[" + strings.Join(decl.Params, ", ") + "]"
	}
	switch decl.Kind {
	case "struct":
		return "struct " + name + " { " + parameters(decl.Fields) + " }"
	case "sum":
		var variants []string
		for _, variant := range decl.Variants {
			text := variant.Name
			if len(variant.Fields) > 0 {
				text += "(" + parameters(variant.Fields) + ")"
			}
			variants = append(variants, text)
		}
		return "type " + name + " = " + strings.Join(variants, " | ")
	}
	return "extern type " + name + " = " + decl.Extern
}

// FileDoc documents the module in a source file from its @moduledoc, @doc
// and @typedoc text. Private functions and tests are left out.
func FileDoc(path string, asJSON bool) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	program, err := syntax.ParseSyntax(string(data))
	if err != nil {
		return "", fmt.Errorf("%s:%w", path, err)
	}
	out := moduleJSON{Name: program.Module, Summary: strings.TrimSpace(program.ModuleDoc)}
	for _, decl := range program.Types {
		out.Types = append(out.Types, typeJSON{decl.Name, typeDefinition(decl), strings.TrimSpace(decl.Doc)})
	}
	// The clauses of one function are documented together.
	index := map[string]int{}
	for _, f := range program.Functions {
		if f.Private || f.Test != "" || f.Setup || f.Name == "main" {
			continue
		}
		key := fmt.Sprintf("%s/%d", f.Name, len(f.Params))
		signature := f.Name + "(" + parameters(f.Params) + ")"
		if f.Type != "" && f.Type != "void" {
			signature += " -> " + f.Type
		}
		doc := strings.TrimSpace(f.Doc)
		at, seen := index[key]
		if !seen {
			index[key] = len(out.Functions)
			out.Functions = append(out.Functions, functionJSON{Name: program.Module + "." + f.Name, Module: program.Module, Signatures: []string{signature}, Summary: doc})
			continue
		}
		if out.Functions[at].Summary == "" {
			out.Functions[at].Summary = doc
		}
	}
	if asJSON {
		return encode(out), nil
	}
	var b strings.Builder
	b.WriteString(out.Name + "\n")
	if out.Summary != "" {
		b.WriteString("\n" + out.Summary + "\n")
	}
	for _, decl := range out.Types {
		b.WriteString("\n" + decl.Definition + "\n")
		if decl.Summary != "" {
			b.WriteString("\n" + indented(decl.Summary) + "\n")
		}
	}
	for _, f := range out.Functions {
		b.WriteString("\n" + f.Signatures[0] + "\n")
		if f.Summary == "" {
			b.WriteString("\n    (undocumented)\n")
		} else {
			b.WriteString("\n" + indented(f.Summary) + "\n")
		}
	}
	return b.String(), nil
}
