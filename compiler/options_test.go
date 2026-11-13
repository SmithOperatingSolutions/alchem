package compiler

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestNoTraceAndReplacement(t *testing.T) {
	d := t.TempDir()
	source := filepath.Join(d, "main.alc")
	binary := filepath.Join(d, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	os.WriteFile(source, []byte(`defmodule A do def main() do assert(false) end end`), 0600)
	if err := BuildWithOptions(source, BuildOptions{Output: binary, NoTrace: true}); err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command(binary).CombinedOutput()
	if err == nil || strings.Contains(string(out), "  at ") || !strings.Contains(string(out), "assertion failed") {
		t.Fatalf("%v %s", err, out)
	}
	os.WriteFile(source, []byte(`defmodule A do def main() do IO.puts("replacement") end end`), 0600)
	if err := BuildTo(source, binary); err != nil {
		t.Fatal(err)
	}
	out, err = exec.Command(binary).CombinedOutput()
	if err != nil || string(out) != "replacement\n" {
		t.Fatalf("%v %s", err, out)
	}
	if err := BuildWithOptions(source, BuildOptions{Output: binary, Timeout: -time.Second}); err == nil {
		t.Fatal("negative timeout accepted")
	}
}

func TestFailedBuildsNeverPublish(t *testing.T) {
	d := t.TempDir()
	source := filepath.Join(d, "bad.alc")
	output := filepath.Join(d, "existing")
	os.WriteFile(source, []byte(`defmodule A do def main() do assert(1+true) end end`), 0600)
	first := BuildTo(source, output)
	second := BuildTo(source, output)
	if first == nil || second == nil || first.Error() != second.Error() {
		t.Fatalf("nondeterministic errors: %v %v", first, second)
	}
	if _, err := os.Stat(output); !os.IsNotExist(err) {
		t.Fatal("invalid compilation created output")
	}
	os.WriteFile(source, []byte(`defmodule A do def main() do assert(true) end end`), 0600)
	os.WriteFile(output, []byte("previous"), 0600)
	if err := BuildWithOptions(source, BuildOptions{Output: output, GOOS: "invalid_os", GOARCH: "amd64"}); err == nil {
		t.Fatal("invalid target compiled")
	}
	data, _ := os.ReadFile(output)
	if string(data) != "previous" {
		t.Fatal("toolchain failure replaced output")
	}
	staged, _ := filepath.Glob(filepath.Join(d, ".alchem-output-*"))
	if len(staged) > 0 {
		t.Fatalf("staging leaked: %v", staged)
	}
}

func TestBuildCannotOverwriteSource(t *testing.T) {
	d := t.TempDir()
	source := filepath.Join(d, "main.alc")
	text := `defmodule A do def main() do assert(true) end end`
	os.WriteFile(source, []byte(text), 0600)
	if err := BuildTo(source, source); err == nil || !strings.Contains(err.Error(), "overwrite source") {
		t.Fatalf("got %v", err)
	}
	data, _ := os.ReadFile(source)
	if string(data) != text {
		t.Fatal("source was changed")
	}
}

func TestDefaultOutputNameResolvesRelativeEntries(t *testing.T) {
	project := filepath.Join(t.TempDir(), "service")
	if err := os.Mkdir(project, 0700); err != nil {
		t.Fatal(err)
	}
	options, err := BuildOptions{GOOS: "linux", GOARCH: "amd64"}.normalized(project + string(filepath.Separator) + ".")
	if err != nil || options.Output != "service" {
		t.Fatalf("output %q, error %v", options.Output, err)
	}
	if _, err = (BuildOptions{}).normalized(string(filepath.Separator)); err == nil || !strings.Contains(err.Error(), "explicit output path") {
		t.Fatalf("root entry: %v", err)
	}
}

// Runaway recursion must surface as an ordinary process failure that a parent
// can observe, and the limit must be configurable per build.
func TestCallDepthLimitIsRecoverable(t *testing.T) {
	d := t.TempDir()
	source := filepath.Join(d, "main.alc")
	binary := filepath.Join(d, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	program := `defmodule Depth do
  def down(n: integer): integer do
    if n == 0 do
      return 0
    end
    return 1 + down(n - 1)
  end
  def worker(self: pid[integer]): integer do
    return down(-1)
  end
  def main() do
    assert(down(40) == 40)
    child = Process.spawn(&worker, 1)
    {done, reason} = Process.await(child, 5000)
    assert(done and reason == "call depth exceeded")
    IO.puts("recovered")
    result = down(60)
  end
end
`
	if err := os.WriteFile(source, []byte(program), 0600); err != nil {
		t.Fatal(err)
	}
	if err := BuildWithOptions(source, BuildOptions{Output: binary, MaxCallDepth: 50}); err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command(binary).CombinedOutput()
	want := "recovered\n" + source + ":2:7: call depth exceeded\n"
	if err == nil || !strings.HasPrefix(string(out), want) || !strings.Contains(string(out), "  at Depth.main") {
		t.Fatalf("%v\n%s", err, out)
	}
	for _, depth := range []int{-1, MaxCallDepthCeiling + 1} {
		if err := BuildWithOptions(source, BuildOptions{Output: binary, MaxCallDepth: depth}); err == nil || !strings.Contains(err.Error(), "max call depth") {
			t.Fatalf("depth %d: %v", depth, err)
		}
	}
}

func TestProjectModuleLimit(t *testing.T) {
	d := t.TempDir()
	for i := 0; i <= MaxModules; i++ {
		body := fmt.Sprintf("defmodule M%d do\n import \"m%d.alc\"\n def value(): integer do\n  return 1\n end\nend\n", i, i+1)
		if i == 0 {
			body = "defmodule M0 do\n import \"m1.alc\"\n def main() do\n  assert(true)\n end\nend\n"
		}
		if i == MaxModules {
			body = fmt.Sprintf("defmodule M%d do\n def value(): integer do\n  return 1\n end\nend\n", i)
		}
		if err := os.WriteFile(filepath.Join(d, fmt.Sprintf("m%d.alc", i)), []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
	}
	if err := Check(filepath.Join(d, "m0.alc")); err == nil || !strings.Contains(err.Error(), "project exceeds 1024 modules") {
		t.Fatalf("got %.300v", err)
	}
}

// Function bodies check for cancellation on entry rather than before every
// statement. A process that never blocks must still stop promptly, whether it
// repeats through a state loop or through plain recursion.
func TestBusyProcessesAreCancellable(t *testing.T) {
	d := t.TempDir()
	source := filepath.Join(d, "main.alc")
	binary := filepath.Join(d, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	program := `defmodule Busy do
  def looper(self: pid[integer]): integer do
    return Process.loop(0, fn(count: integer): tuple[boolean,integer] do
      return {true, count % 1000 + 1}
    end)
  end
  def climb(n: integer): integer do
    if n == 0 do
      return 0
    end
    return climb(n - 1)
  end
  def recurse(self: pid[integer]): integer do
    return Process.loop(0, fn(count: integer): tuple[boolean,integer] do
      return {true, climb(100)}
    end)
  end
  def main() do
    first = Process.spawn(&looper, 1)
    second = Process.spawn(&recurse, 1)
    Process.sleep(20)
    assert(Process.stop(first))
    assert(Process.stop(second))
    {done, reason} = Process.await(first, 5000)
    assert(done and reason == "shutdown")
    {ended, why} = Process.await(second, 5000)
    assert(ended and why == "shutdown")
    IO.puts("stopped")
  end
end
`
	if err := os.WriteFile(source, []byte(program), 0600); err != nil {
		t.Fatal(err)
	}
	if err := BuildWithOptions(source, BuildOptions{Output: binary}); err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command(binary).CombinedOutput()
	if err != nil || string(out) != "stopped\n" {
		t.Fatalf("%v\n%s", err, out)
	}
}
