package guide

import (
	"os"
	"path/filepath"
	"slices"
	"testing"
)

// The documentation of a source file lists each form of a function defined
// for arguments of several types, shown by its first clause that names every
// type, and lists clauses of one form once.
func TestSourceDocListsForms(t *testing.T) {
	path := filepath.Join(t.TempDir(), "shapes.alc")
	source := `defmodule Shapes do
  @doc "Describes a value."
  def show(n: integer): string do
    "integer"
  end

  def show(""): string do
    "empty"
  end

  def show(text: string): string do
    text
  end

  def count(0): integer do
    0
  end

  def count(n: integer): integer do
    1 + count(n - 1)
  end
end
`
	if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	data, err := fileData(path)
	if err != nil {
		t.Fatal(err)
	}
	want := map[string][]string{
		"Shapes.show":  {"show(n: integer) -> string", "show(text: string) -> string"},
		"Shapes.count": {"count(n: integer) -> integer"},
	}
	if len(data.Functions) != len(want) {
		t.Fatalf("functions: %+v", data.Functions)
	}
	for _, f := range data.Functions {
		if !slices.Equal(f.Signatures, want[f.Name]) {
			t.Errorf("%s: %q, want %q", f.Name, f.Signatures, want[f.Name])
		}
	}
	if data.Functions[0].Summary != "Describes a value." {
		t.Errorf("summary: %q", data.Functions[0].Summary)
	}
}
