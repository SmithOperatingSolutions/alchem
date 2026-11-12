package main

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/SmithOperatingSolutions/alchem/compiler"
	"os"
	"path/filepath"
	"testing"
)

func TestCommandsAndFormatting(t *testing.T) {
	d := t.TempDir()
	path := filepath.Join(d, "main.alc")
	source := `defmodule App do def main() do IO.puts("ok") end end`
	if err := os.WriteFile(path, []byte(source), 0600); err != nil {
		t.Fatal(err)
	}
	var out, errout bytes.Buffer
	invoke := func(args ...string) int {
		out.Reset()
		errout.Reset()
		return run(context.Background(), args, &out, &errout)
	}
	if invoke("check", path) != 0 {
		t.Fatal(errout.String())
	}
	if invoke("fmt", "--check", path) != 1 {
		t.Fatal("unformatted file passed")
	}
	if invoke("fmt", path) != 0 || invoke("fmt", "--check", path) != 0 {
		t.Fatal(errout.String())
	}
	formatted, _ := os.ReadFile(path)
	want, _ := compiler.Format(source)
	if string(formatted) != want {
		t.Fatal("wrong format")
	}
	if invoke("build", "--target", "bogus", path) != 2 {
		t.Fatal("invalid target accepted")
	}
	if invoke("test", "--timeout", "0s", d) != 1 {
		t.Fatal("invalid timeout accepted")
	}
	if err := os.WriteFile(path, []byte(`defmodule App do def main() do assert(1+true) end end`), 0600); err != nil {
		t.Fatal(err)
	}
	if invoke("check", "--json", path) != 1 {
		t.Fatal("invalid program accepted")
	}
	var diagnostic compiler.Diagnostic
	if err := json.Unmarshal(errout.Bytes(), &diagnostic); err != nil {
		t.Fatal(err)
	}
	if diagnostic.File != path || diagnostic.Line != 1 || diagnostic.Column < 1 || diagnostic.Message == "" {
		t.Fatalf("%+v", diagnostic)
	}
}
func TestFormatterBatchDoesNotModifyOnSyntaxError(t *testing.T) {
	d := t.TempDir()
	first := filepath.Join(d, "a.alc")
	bad := filepath.Join(d, "b.alc")
	source := `defmodule A do def main() do assert(true) end end`
	os.WriteFile(first, []byte(source), 0600)
	os.WriteFile(bad, []byte("bad"), 0600)
	if err := formatPaths([]string{d}, false, &bytes.Buffer{}); err == nil {
		t.Fatal("accepted invalid syntax")
	}
	data, _ := os.ReadFile(first)
	if string(data) != source {
		t.Fatal("partially modified invalid batch")
	}
}
