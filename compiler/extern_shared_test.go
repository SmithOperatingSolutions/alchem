package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const sharedCounter = `package native

import "sync/atomic"

type Counter struct{ n atomic.Int64 }

func NewCounter() *Counter { return &Counter{} }

func (c *Counter) Add(by int64) int64 { return c.n.Add(by) }

func (c *Counter) Value() int64 { return c.n.Load() }
`

// A handle declared with "extern shared type" names a Go value that several
// goroutines may use, so it is sent in messages like any built-in handle.
func TestSharedHandlesAreSentBetweenProcesses(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  extern shared type Counter = "*./native.Counter"

  struct Job do
    counter: Counter
    times: integer
  end

  extern new_counter(): Counter = "./native.NewCounter"
  extern add(counter: Counter, by: integer): integer = "./native.Counter.Add"
  extern value(counter: Counter): integer = "./native.Counter.Value"

  def work(inbox: pid[Job], done: pid[boolean]): integer do
    case Process.receive(inbox, 1000) do
      {true, job} ->
        Enum.each(Enum.to_list(1..job.times), fn _ -> add(job.counter, 1) end)
        Process.send(done, true, 100)
        0
      _ -> 1
    end
  end

  def main() do
    counter = new_counter()
    done: pid[boolean] = Process.self(16)
    workers = Enum.map(Enum.to_list(1..8), fn _ ->
      worker: pid[Job] = Process.spawn(fn(inbox: pid[Job]): integer do work(inbox, done) end, 1)
      worker
    end)
    Enum.each(workers, fn worker -> Process.send(worker, %Job{counter: counter, times: 500}, 100) end)
    Enum.each(workers, fn _ -> assert(Process.receive(done, 2000) == {true, true}) end)
    assert(value(counter) == 4000)
    IO.puts("shared")
  end
end
`, "native/native.go": sharedCounter})
	if err != nil || output != "shared\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

// A handle that was not declared shared stays with one process, and the
// refusal names the handle and the declaration that would allow it.
func TestUnsharedHandlesAreNotSent(t *testing.T) {
	cases := []struct{ declaration, want string }{
		{`extern type Buffer = "*bytes.Buffer" def keep(b: Buffer): pid[Buffer] do Process.self(1) end`, "mailbox messages cannot contain App.Buffer: declare it with extern shared type"},
		{`extern type Buffer = "*bytes.Buffer" struct Job do buffer: Buffer end def keep(): pid[list[Job]] do Process.self(1) end`, "mailbox messages cannot contain App.Buffer"},
		// Sharing a handle does not make it comparable.
		{`extern shared type Buffer = "*bytes.Buffer" def same(a: Buffer, b: Buffer): boolean do a == b end`, "do not support equality"},
		{`extern shared Buffer = "*bytes.Buffer"`, "expected"},
	}
	for _, tc := range cases {
		t.Run(tc.declaration, func(t *testing.T) {
			entry := filepath.Join(t.TempDir(), "main.alc")
			os.WriteFile(entry, []byte("defmodule App do "+tc.declaration+" def main() do assert(true) end end"), 0600)
			err := Check(entry)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

func TestSharedExternTypeFormatting(t *testing.T) {
	source := "defmodule App do\n  extern shared type Counter = \"*./native.Counter\"\n\n  extern type Builder = \"*strings.Builder\"\n\n  def main() do\n    IO.puts(\"x\")\n  end\nend\n"
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}

// A fetch that fails the way a private repository does says what to set, and
// ALCHEM_PRIVATE keeps such packages away from the public proxy.
func TestPrivatePackages(t *testing.T) {
	refused := "github.com/owner/private-repo@v0.1.0: verifying go.mod: reading https://sum.golang.org/lookup/github.com/owner/private-repo@v0.1.0: 404 Not Found\n\tfatal: could not read Username for 'https://github.com': terminal prompts disabled"
	hint := privateHint("github.com/owner/private-repo", refused)
	if !strings.Contains(hint, "set ALCHEM_PRIVATE=github.com/owner/*") || !strings.Contains(hint, "alchem syntax packages") {
		t.Fatalf("hint: %s", hint)
	}
	if hint := privateHint("example.test/lib", "example.test/lib@v9.9.9: invalid version: unknown revision v9.9.9"); hint != "" {
		t.Fatalf("unexpected hint: %s", hint)
	}
	value := func() string {
		found := ""
		for _, entry := range baseEnvironment() {
			if strings.HasPrefix(entry, "GOPRIVATE=") {
				found = strings.TrimPrefix(entry, "GOPRIVATE=")
			}
		}
		return found
	}
	t.Setenv("GOPRIVATE", "")
	t.Setenv("ALCHEM_PRIVATE", "")
	if value() != "" {
		t.Fatalf("GOPRIVATE=%s", value())
	}
	t.Setenv("ALCHEM_PRIVATE", "github.com/owner/*")
	if value() != "github.com/owner/*" {
		t.Fatalf("GOPRIVATE=%s", value())
	}
	t.Setenv("GOPRIVATE", "git.example.com")
	if value() != "git.example.com,github.com/owner/*" {
		t.Fatalf("GOPRIVATE=%s", value())
	}
}

// require "alchem" names the oldest release a file works with. A build from
// source, which has no release number, meets every requirement.
func TestCompilerRequirement(t *testing.T) {
	entry := filepath.Join(t.TempDir(), "main.alc")
	os.WriteFile(entry, []byte("defmodule App do\n  require \"alchem\" \"v0.4.0\"\n\n  def main() do\n    assert(true)\n  end\nend\n"), 0600)
	defer func(previous string) { Version = previous }(Version)
	for version, want := range map[string]string{
		"":                 "",
		"devel":            "",
		"v0.4.0":           "",
		"v0.4.1":           "",
		"v1.0.0":           "",
		"v0.10.0":          "",
		"v0.3.7":           "main.alc:2:3: this file needs Alchem v0.4.0 or newer, and this is v0.3.7",
		"v0.3.99-0.2026+x": "this file needs Alchem v0.4.0 or newer",
	} {
		Version = version
		err := Check(entry)
		if want == "" && err != nil || want != "" && (err == nil || !strings.Contains(err.Error(), want)) {
			t.Fatalf("%q: got %v, want %q", version, err, want)
		}
	}
	// The requirement asks nothing of the Go build, and needs no lock file.
	Version = "v0.4.0"
	if _, err := os.Stat(filepath.Join(filepath.Dir(entry), LockName)); err == nil {
		t.Fatal("a lock file was written")
	}
	formatted, err := Format("defmodule App do require \"alchem\" \"v0.4.0\" def main() do assert(true) end end")
	if err != nil || !strings.Contains(formatted, "  require \"alchem\" \"v0.4.0\"\n") {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}
