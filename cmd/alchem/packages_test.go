package main

import (
	"archive/zip"
	"bytes"
	"context"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// publish writes one version of a package into a file proxy that the Go
// commands of this test then fetch from.
func publish(t *testing.T, module, version string, files map[string]string) {
	t.Helper()
	proxy := t.TempDir()
	url := "file://" + filepath.ToSlash(proxy)
	if runtime.GOOS == "windows" {
		url = "file:///" + filepath.ToSlash(proxy)
	}
	t.Setenv("GOPROXY", url)
	t.Setenv("GONOSUMDB", "example.test")
	t.Setenv("GOFLAGS", "-modcacherw")
	t.Setenv("GOMODCACHE", t.TempDir())
	dir := filepath.Join(proxy, filepath.FromSlash(module), "@v")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(dir, "list"), []byte(version+"\n"), 0o600)
	os.WriteFile(filepath.Join(dir, version+".info"), []byte(`{"Version":"`+version+`"}`), 0o600)
	os.WriteFile(filepath.Join(dir, version+".mod"), []byte("module "+module+"\n\ngo 1.21\n"), 0o600)
	archive, err := os.Create(filepath.Join(dir, version+".zip"))
	if err != nil {
		t.Fatal(err)
	}
	defer archive.Close()
	writer := zip.NewWriter(archive)
	files["go.mod"] = "module " + module + "\n\ngo 1.21\n"
	for name, content := range files {
		entry, err := writer.Create(module + "@" + version + "/" + name)
		if err != nil {
			t.Fatal(err)
		}
		entry.Write([]byte(content))
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
}

// A project that imports a published package reads the package's docs, by
// the path the import gives and by module name, and runs and builds the
// programs the package carries.
func TestPackageDocsAndPrograms(t *testing.T) {
	publish(t, "example.test/lib", "v0.1.0", map[string]string{
		"lib/live.alc": `defmodule Live do
  @moduledoc """
  Pages that stay connected.
  """
  import "wire.alc"

  @doc """
  Greets a visitor over the wire.

      alx> Live.greet("Ada")
      "wire: hello Ada"
  """
  def greet(name: string): string do
    Wire.frame("hello " <> name)
  end

  defp hidden(): integer do
    1
  end
end
`,
		"lib/wire.alc": `defmodule Wire do
  @doc "Frames a message for sending."
  def frame(text: string): string do
    "wire: " <> text
  end
end
`,
		"tools/dev.alc": `defmodule Dev do
  import "../lib/live.alc"

  def main() do
    IO.puts(Live.greet(Enum.join(System.argv(), "+")))
  end
end
`,
		"tools/escape.alc": "defmodule Escape do\n  import \"../../outside.alc\"\n  def main() do\n    IO.puts(\"x\")\n  end\nend\n",
	})
	project := t.TempDir()
	t.Chdir(project)
	os.WriteFile("main.alc", []byte("defmodule Main do\n  import \"example.test/lib@v0.1.0/lib/live.alc\"\n  import \"lib/notes.alc\"\n\n  def main() do\n    IO.puts(Live.greet(Notes.title()))\n  end\nend\n"), 0o644)
	os.MkdirAll("lib", 0o755)
	os.WriteFile(filepath.Join("lib", "notes.alc"), []byte("defmodule Notes do\n  @doc \"The title of the notes.\"\n  def title(): string do\n    \"notes\"\n  end\nend\n"), 0o644)

	alchem := func(args ...string) (int, string) {
		var out, errOut bytes.Buffer
		code := run(context.Background(), args, &out, &errOut)
		return code, out.String() + errOut.String()
	}
	// Before the package has been fetched, a lookup by name does not fetch
	// it: only the project's own files are known.
	if code, text := alchem("doc", "Live"); code != 1 || !strings.Contains(text, "no module or function") {
		t.Fatalf("doc Live before fetching: %d %s", code, text)
	}
	if code, text := alchem("doc", "Notes.title"); code != 0 || !strings.Contains(text, "The title of the notes.") || !strings.Contains(text, "From lib/notes.alc") {
		t.Fatalf("doc Notes.title: %d %s", code, text)
	}
	for _, c := range []struct {
		args []string
		code int
		want []string
		not  string
	}{
		{[]string{"doc", "example.test/lib@v0.1.0/lib/live.alc"}, 0, []string{"Pages that stay connected.", "greet(name: string) -> string", "Greets a visitor"}, "hidden"},
		{[]string{"run", "main.alc"}, 0, []string{"wire: hello notes"}, ""},
		{[]string{"doc", "Live"}, 0, []string{"Pages that stay connected.", "From example.test/lib@v0.1.0/lib/live.alc"}, "hidden"},
		{[]string{"doc", "live.greet/1"}, 0, []string{"Greets a visitor", "alx> Live.greet(\"Ada\")"}, "Pages that stay"},
		{[]string{"doc", "-json", "Live.greet"}, 0, []string{`"name": "Live.greet"`}, ""},
		{[]string{"doc", "Live.absent"}, 1, []string{"Live has no public function \"absent\""}, ""},
		// A module the package uses itself is found through its imports.
		{[]string{"doc", "Wire"}, 0, []string{"Frames a message", "From example.test/lib@v0.1.0/lib/wire.alc"}, ""},
		{[]string{"doc", "--search", "visitor"}, 0, []string{"Live.greet", "Greets a visitor over the wire."}, ""},
		{[]string{"doc", "--search", "connected"}, 0, []string{"module", "Live"}, ""},
		{[]string{"run", "example.test/lib@v0.1.0/tools/dev.alc", "--", "a", "b"}, 0, []string{"wire: hello a+b"}, ""},
		{[]string{"check", "example.test/lib@v0.1.0/tools/dev.alc"}, 0, nil, ""},
		{[]string{"check", "example.test/lib@v0.1.0/tools/escape.alc"}, 1, []string{"leaves the package"}, ""},
		{[]string{"run", "example.test/lib@v0.1.0/tools/absent.alc"}, 1, []string{"read source"}, ""},
		{[]string{"doc", "example.test/lib@v9.9.9/lib/live.alc"}, 1, []string{"fetch example.test/lib@v9.9.9"}, ""},
	} {
		code, text := alchem(c.args...)
		if code != c.code {
			t.Fatalf("%v: status %d, want %d\n%s", c.args, code, c.code, text)
		}
		for _, want := range c.want {
			if !strings.Contains(text, want) {
				t.Fatalf("%v: missing %q in\n%s", c.args, want, text)
			}
		}
		if c.not != "" && strings.Contains(text, c.not) {
			t.Fatalf("%v: %q should not be shown\n%s", c.args, c.not, text)
		}
	}
	// A package's program builds into the current directory, and keeps no
	// lock file: the project's own lock records only what the project uses.
	before, _ := os.ReadFile("alchem.lock")
	if !strings.Contains(string(before), "package example.test/lib v0.1.0") {
		t.Fatalf("lock: %s", before)
	}
	if code, text := alchem("build", "example.test/lib@v0.1.0/tools/dev.alc"); code != 0 {
		t.Fatalf("build: %d %s", code, text)
	}
	name := "dev"
	if runtime.GOOS == "windows" {
		name += ".exe"
	}
	if _, err := os.Stat(name); err != nil {
		t.Fatalf("no program built here: %v", err)
	}
	after, _ := os.ReadFile("alchem.lock")
	if string(after) != string(before) {
		t.Fatalf("lock changed:\n%s", after)
	}
}
