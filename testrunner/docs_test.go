package testrunner

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// unexampled lists the functions whose effect cannot be shown by an example
// that runs unattended: they read standard input or end the program.
var unexampled = map[string]bool{
	"IO.gets": true, "IO.read_line": true, "IO.read_all": true, "IO.stream": true, "System.halt": true,
}

func TestEveryLibraryFunctionIsDocumented(t *testing.T) {
	modules := map[string]bool{}
	for _, module := range syntax.Modules {
		modules[module.Name] = true
	}
	known := map[string]bool{}
	for _, f := range syntax.Functions() {
		known[f.Name] = true
		if !modules[f.Module] {
			t.Errorf("%s belongs to %s, which has no module(...) entry", f.Name, f.Module)
		}
		if f.Summary == "" {
			t.Errorf("%s has no doc(...) entry", f.Name)
		}
		if f.Examples == "" && !unexampled[f.Name] {
			t.Errorf("%s has no example", f.Name)
		}
	}
	for name := range syntax.Docs {
		if !known[name] {
			t.Errorf("doc(%q) documents a function that does not exist", name)
		}
	}
}

// TestLibraryExamplesRun compiles and runs every example shown by help, as
// doctests of a generated module per library module.
func TestLibraryExamplesRun(t *testing.T) {
	if testing.Short() {
		t.Skip("compiles one program per library module")
	}
	dir := t.TempDir()
	t.Chdir(dir)
	byModule := map[string][]syntax.Function{}
	for _, f := range syntax.Functions() {
		if f.Examples != "" {
			byModule[f.Module] = append(byModule[f.Module], f)
		}
	}
	var files []string
	for module, functions := range byModule {
		var source strings.Builder
		fmt.Fprintf(&source, "defmodule Doc%s do\n", module)
		for index, f := range functions {
			fmt.Fprintf(&source, "  # %s\n  @doc ~S\"\"\"\n", f.Name)
			for _, line := range strings.Split(f.Examples, "\n") {
				source.WriteString("      " + line + "\n")
			}
			fmt.Fprintf(&source, "  \"\"\"\n  def example_%d(): integer do\n    0\n  end\n\n", index)
		}
		source.WriteString("end\n")
		lower := strings.ToLower(module)
		test := fmt.Sprintf("defmodule Doc%sTest do\n  import \"doc_%s.alc\"\n  doctest Doc%s\nend\n", module, lower, module)
		for name, text := range map[string]string{"doc_" + lower + ".alc": source.String(), "doc_" + lower + "_test.alc": test} {
			if err := os.WriteFile(filepath.Join(dir, name), []byte(text), 0o644); err != nil {
				t.Fatal(err)
			}
		}
		files = append(files, filepath.Join(dir, "doc_"+lower+"_test.alc"))
	}
	var out bytes.Buffer
	summary, err := RunTests(context.Background(), files, Options{Seed: 1}, &out)
	t.Logf("%+v", summary)
	if err != nil {
		report := out.String()
		for module, functions := range byModule {
			for index, f := range functions {
				report = strings.ReplaceAll(report, fmt.Sprintf("Doc%s.example_%d/0", module, index), f.Name)
			}
		}
		t.Fatalf("library examples failed: %v\n%s", err, report)
	}
}

// TestSyntaxExamplesRun compiles and runs every example of the syntax help.
func TestSyntaxExamplesRun(t *testing.T) {
	if testing.Short() {
		t.Skip("compiles one program per example")
	}
	root := t.TempDir()
	var files []string
	seen := map[string]bool{}
	for _, topic := range syntax.Topics {
		if seen[topic.Name] || topic.Summary == "" || len(topic.Notes) == 0 || len(topic.Examples) == 0 {
			t.Errorf("topic %q is a duplicate or lacks a summary, notes or examples", topic.Name)
		}
		seen[topic.Name] = true
		for index, sample := range topic.Examples {
			dir := filepath.Join(root, fmt.Sprintf("%s_%d", topic.Name, index))
			if err := os.MkdirAll(dir, 0o755); err != nil {
				t.Fatal(err)
			}
			source := sample.Program("Example", true)
			name := "example_test.alc"
			if !strings.Contains(source, "\n  test ") && !strings.Contains(source, "doctest ") {
				name = "example.alc"
			}
			sample.Files = mapsWith(sample.Files, name, source)
			for file, text := range sample.Files {
				if err := os.WriteFile(filepath.Join(dir, file), []byte(text), 0o644); err != nil {
					t.Fatal(err)
				}
			}
			path := filepath.Join(dir, name)
			if name == "example.alc" {
				if err := compiler.Check(path); err != nil {
					t.Errorf("%s example %q: %v", topic.Name, sample.Title, err)
				}
				continue
			}
			files = append(files, path)
		}
	}
	for _, topic := range syntax.Topics {
		for _, related := range topic.See {
			if _, ok := syntax.TopicNamed(related); !ok && !moduleNamed(related) {
				t.Errorf("topic %q refers to %q, which is neither a topic nor a module", topic.Name, related)
			}
		}
	}
	var out bytes.Buffer
	if _, err := RunTests(context.Background(), files, Options{Seed: 1}, &out); err != nil {
		t.Fatalf("syntax examples failed: %v\n%s", err, out.String())
	}
}

func mapsWith(files map[string]string, name, text string) map[string]string {
	out := map[string]string{name: text}
	for key, value := range files {
		out[key] = value
	}
	return out
}

func moduleNamed(name string) bool {
	for _, module := range syntax.Modules {
		if module.Name == name {
			return true
		}
	}
	return false
}
