package guide

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// A project that imports a module in place of a library module of the same
// name is shown that module, by name and when searching.
func TestDocShowsTheModuleThatReplacesALibraryModule(t *testing.T) {
	file := filepath.Join(t.TempDir(), "disk_store.alc")
	source := `defmodule DiskStore do
  @moduledoc "Records kept by the package."

  @doc "Opens the package's store, a quokka of a file."
  def open(path: string): result[string, string] do
    error(path)
  end
end
`
	if err := os.WriteFile(file, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	shown := "example.com/owner/packages@v1.0.0/disk_store/disk_store.alc"
	imported := func() []Source { return []Source{{Module: "DiskStore", File: file, Shown: shown}} }
	previous := Sources
	defer func() { Sources = previous }()

	for _, query := range []string{"DiskStore", "diskstore", "DiskStore.open", "DiskStore.open/1"} {
		Sources = nil
		text, err := Doc(query, false, false)
		if err != nil || strings.Contains(text, "quokka") || strings.Contains(text, "Records kept by the package") {
			t.Errorf("%s outside a project: %v\n%s", query, err, text)
		}
		Sources = imported
		text, err = Doc(query, false, false)
		if err != nil || !strings.Contains(text, "From "+shown) || strings.Contains(text, "disk_store,") {
			t.Errorf("%s in a project that imports the module: %v\n%s", query, err, text)
		}
	}

	Sources = imported
	if text, err := Doc("DiskStore.open", false, true); err != nil || !strings.Contains(text, "result[string,string]") {
		t.Errorf("as JSON: %v\n%s", err, text)
	}
	if _, err := Doc("DiskStore.nothing", false, false); err == nil || !strings.Contains(err.Error(), "no public function") {
		t.Errorf("a function the module does not have: %v", err)
	}
	// A library module no package takes the place of is still the library's.
	if text, err := Doc("Enum.map", false, false); err != nil || strings.Contains(text, "From ") {
		t.Errorf("Enum.map: %v\n%s", err, text)
	}

	text, err := Search("DiskStore", false)
	if err != nil {
		t.Fatal(err)
	}
	if count := strings.Count(text, "module   DiskStore "); count != 1 || !strings.Contains(text, "Records kept by the package") {
		t.Errorf("search lists the module %d times:\n%s", count, text)
	}
	if strings.Count(text, "function DiskStore.open ") != 1 || !strings.Contains(text, "quokka") || strings.Contains(text, "DiskStore.put") {
		t.Errorf("search shows the library's functions:\n%s", text)
	}
	Sources = nil
	if text, err := Search("DiskStore", false); err != nil || !strings.Contains(text, "DiskStore.put") {
		t.Errorf("search outside a project: %v\n%s", err, text)
	}
}
