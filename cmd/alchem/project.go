package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"
	"unicode"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

// runProgram builds a program into a temporary directory and runs it with
// the given arguments, passing its input, output and exit status through.
func runProgram(ctx context.Context, entry string, arguments []string, options compiler.BuildOptions, out, errOut io.Writer) (int, error) {
	work, err := os.MkdirTemp("", "alchem-run-*")
	if err != nil {
		return 1, err
	}
	defer os.RemoveAll(work)
	name := strings.TrimSuffix(filepath.Base(entry), ".alc")
	if info, err := os.Stat(entry); err == nil && info.IsDir() {
		name = filepath.Base(filepath.Clean(entry))
	}
	if runtime.GOOS == "windows" {
		name += ".exe"
	}
	options.Output = filepath.Join(work, name)
	if err := compiler.BuildWithOptionsContext(ctx, entry, options); err != nil {
		return 1, err
	}
	cmd := exec.CommandContext(ctx, options.Output, arguments...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, out, errOut
	// When alchem run is interrupted or asked to terminate, so is the
	// program, which is then waited for; one that has not gone a few seconds
	// later is killed. Where a program cannot be signalled it is killed at
	// once.
	cmd.Cancel = func() error {
		if err := cmd.Process.Signal(syscall.SIGTERM); err != nil && !errors.Is(err, os.ErrProcessDone) {
			return cmd.Process.Kill()
		}
		return nil
	}
	cmd.WaitDelay = 5 * time.Second
	err = cmd.Run()
	if ctx.Err() != nil {
		// Ended on request: the status a shell gives a program ended by a
		// signal.
		return 130, nil
	}
	var exit *exec.ExitError
	if errors.As(err, &exit) {
		return exit.ExitCode(), nil
	}
	if err != nil {
		return 1, err
	}
	return 0, nil
}

// moduleName turns a project name such as my_app into the module name MyApp.
func moduleName(name string) string {
	var b strings.Builder
	upper := true
	for _, r := range name {
		if r == '_' || r == '-' {
			upper = true
			continue
		}
		if upper {
			r = unicode.ToUpper(r)
		}
		upper = false
		b.WriteRune(r)
	}
	return b.String()
}

// newProject writes a project: a library module, a test of it, and a main
// program that uses it.
func newProject(path string) ([]string, error) {
	name := filepath.Base(filepath.Clean(path))
	valid := name != "" && unicode.IsLetter([]rune(name)[0])
	for _, r := range name {
		valid = valid && (r < unicode.MaxASCII) && (unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_' || r == '-')
	}
	if !valid {
		return nil, fmt.Errorf("a project name starts with a letter and has only letters, digits, _ and -: %q", name)
	}
	if _, err := os.Stat(path); err == nil {
		return nil, fmt.Errorf("%s already exists", path)
	}
	module := moduleName(name)
	library := strings.ReplaceAll(strings.ToLower(name), "-", "_")
	files := []struct{ path, text string }{
		{"main.alc", fmt.Sprintf(`defmodule Main do
  import "lib/%[1]s.alc"

  def main() do
    name = case System.argv() do
      [first | _] -> first
      [] -> "world"
    end
    IO.puts(%[2]s.hello(name))
  end
end
`, library, module)},
		{filepath.Join("lib", library+".alc"), fmt.Sprintf(`defmodule %[1]s do
  @moduledoc """
  The %[2]s library.
  """

  @doc """
  Greets someone by name.

      alx> %[1]s.hello("Ada")
      "Hello, Ada!"
  """
  def hello(name: string): string do
    "Hello, " <> name <> "!"
  end
end
`, module, name)},
		{filepath.Join("test", library+"_test.alc"), fmt.Sprintf(`defmodule %[1]sTest do
  import "../lib/%[2]s.alc"
  doctest %[1]s

  test "greets the world" do
    assert(%[1]s.hello("world") == "Hello, world!")
  end
end
`, module, library)},
		{".gitignore", "/" + name + "\n/" + name + ".exe\n"},
		{"README.md", fmt.Sprintf("# %s\n\n```sh\nalchem run main.alc            # build and run\nalchem run main.alc -- Ada     # with arguments\nalchem test test               # run the tests\nalchem build -o %s main.alc   # build an executable\n```\n", name, name)},
	}
	var written []string
	for _, file := range files {
		target := filepath.Join(path, file.path)
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return written, err
		}
		if err := os.WriteFile(target, []byte(file.text), 0o644); err != nil {
			return written, err
		}
		written = append(written, target)
	}
	return written, nil
}
