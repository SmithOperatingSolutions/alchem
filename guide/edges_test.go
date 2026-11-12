package guide

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The documentation commands in their JSON forms, for every module at once,
// for a file of generic types, and the search's mistakes.
func TestDocumentationEdges(t *testing.T) {
	all, err := Doc("", true, true)
	if err != nil || !json.Valid([]byte(all)) || !strings.Contains(all, "\"Enum\"") {
		t.Fatalf("all modules as JSON: %v %.200s", err, all)
	}
	if text, err := Doc("Kernel", false, false); err != nil || text == "" {
		t.Fatalf("Kernel: %v", err)
	}
	if _, err := Search("", false); err == nil {
		t.Fatal("an empty search was accepted")
	}
	if found, err := Search("Registry", true); err != nil || !json.Valid([]byte(found)) || !strings.Contains(found, "module") {
		t.Fatalf("search as JSON: %v %.200s", err, found)
	}
	if _, err := Search("zzzz-nothing-matches", false); err == nil || !strings.Contains(err.Error(), "nothing matches") {
		t.Fatalf("a search with no hits: %v", err)
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "shapes.alc")
	source := "defmodule Shapes do\n  @moduledoc \"Shapes.\"\n  @typedoc \"A box of something.\"\n  struct Box[t] do\n    item: t\n  end\n\n  @typedoc \"A tree.\"\n  type Tree[t] do\n    leaf\n    node(left: Tree[t], value: t, right: Tree[t])\n  end\n\n  @doc \"Wraps a value.\"\n  def wrap(value: t): Box[t] do\n    %Box{item: value}\n  end\n\n  def main() do\n    IO.inspect(wrap(1))\n  end\nend\n"
	os.WriteFile(path, []byte(source), 0o644)
	for _, asJSON := range []bool{false, true} {
		text, err := Doc(path, false, asJSON)
		if err != nil || !strings.Contains(text, "Tree") || !strings.Contains(text, "wrap") {
			t.Fatalf("file doc (json %v): %v\n%s", asJSON, err, text)
		}
	}
	if _, err := FileDoc(filepath.Join(dir, "missing.alc"), false); err == nil {
		t.Fatal("documented a missing file")
	}
	broken := filepath.Join(dir, "broken.alc")
	os.WriteFile(broken, []byte("defmodule Broken do\n  def main( do\nend\n"), 0o644)
	if _, err := FileDoc(broken, true); err == nil {
		t.Fatal("documented a file that does not parse")
	}
}
