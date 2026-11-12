package compiler

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestArithmeticRuntimeErrors(t *testing.T) {
	cases := []struct{ expr, want string }{
		{"9223372036854775807+1", "integer overflow"},
		{"-9223372036854775808-1", "integer overflow"},
		{"3037000500*3037000500", "integer overflow"},
		{"-9223372036854775808 * -1", "integer overflow"},
		{"9223372036854775807 - -1", "integer overflow"},
		{"-9223372036854775808 + -1", "integer overflow"},
		{"-2 - 9223372036854775807", "integer overflow"},
		{"4294967296 * 2147483648", "integer overflow"},
		{"-4294967296 * 2147483649", "integer overflow"},
		{"-1 * -9223372036854775808", "integer overflow"},
		{"-(-9223372036854775808)", "integer overflow"},
		{"-9223372036854775808 / -1", "integer overflow"},
		{"1/0", "division by zero"},
		{"1%0", "division by zero"},
	}
	for _, tc := range cases {
		t.Run(tc.expr, func(t *testing.T) {
			dir := t.TempDir()
			source := filepath.Join(dir, "runtime.alc")
			binary := filepath.Join(dir, "program")
			if runtime.GOOS == "windows" {
				binary += ".exe"
			}
			if err := os.WriteFile(source, []byte("defmodule Check do def main() do value = "+tc.expr+" end end"), 0600); err != nil {
				t.Fatal(err)
			}
			if err := BuildTo(source, binary); err != nil {
				t.Fatal(err)
			}
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			output, err := exec.CommandContext(ctx, binary).CombinedOutput()
			if err == nil || ctx.Err() != nil || !strings.Contains(string(output), tc.want) {
				t.Fatalf("err=%v output=%s", err, output)
			}
		})
	}
}
func TestBuildCancellationPreservesOutput(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "cancel.alc")
	dest := filepath.Join(dir, "existing")
	if err := os.WriteFile(source, []byte(`defmodule Check do def main() do assert(true) end end`), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(dest, []byte("original"), 0600); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := BuildToContext(ctx, source, dest); !errors.Is(err, context.Canceled) {
		t.Fatalf("got %v", err)
	}
	data, err := os.ReadFile(dest)
	if err != nil || string(data) != "original" {
		t.Fatalf("output=%q err=%v", data, err)
	}
}
func TestBuildToolchainDeadline(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("shell fake toolchain is Unix only")
	}
	dir := t.TempDir()
	fake := filepath.Join(dir, "go")
	// exec keeps the fake toolchain to one process, so cancellation can reap it.
	if err := os.WriteFile(fake, []byte("#!/bin/sh\nexec /bin/sleep 10\n"), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dir)
	source := filepath.Join(dir, "timeout.alc")
	dest := filepath.Join(dir, "output")
	if err := os.WriteFile(dest, []byte("previous executable"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(source, []byte(`defmodule Check do def main() do assert(true) end end`), 0600); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()
	started := time.Now()
	err := BuildToContext(ctx, source, dest)
	if !errors.Is(err, context.DeadlineExceeded) || time.Since(started) > 8*time.Second {
		t.Fatalf("err=%v elapsed=%s", err, time.Since(started))
	}
	if data, err := os.ReadFile(dest); err != nil || string(data) != "previous executable" {
		t.Fatalf("output changed: %q %v", data, err)
	}
	matches, err := filepath.Glob(filepath.Join(dir, ".alchem-output-*"))
	if err != nil || len(matches) != 0 {
		t.Fatalf("staged artifacts=%v err=%v", matches, err)
	}
}

// Results at the edges of the checked operators' fast paths must be exact:
// values just inside and outside 32 bits, and the 64-bit extremes.
func TestArithmeticBoundaryResults(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "edges.alc")
	binary := filepath.Join(dir, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	program := `defmodule Edges do
  def main() do
    assert(9223372036854775807 + 0 == 9223372036854775807)
    assert(9223372036854775806 + 1 == 9223372036854775807)
    assert(-9223372036854775807 + -1 == -9223372036854775808)
    assert(-9223372036854775808 - 0 == -9223372036854775808)
    assert(-9223372036854775807 - 1 == -9223372036854775808)
    assert(9223372036854775807 - 9223372036854775807 == 0)
    assert(-1 - -9223372036854775808 == 9223372036854775807)
    assert(2147483647 * 2147483647 == 4611686014132420609)
    assert(-2147483648 * -2147483648 == 4611686018427387904)
    assert(-2147483648 * 2147483647 == -4611686016279904256)
    assert(2147483648 * 2147483648 == 4611686018427387904)
    assert(4294967296 * 2147483647 == 9223372032559808512)
    assert(-4294967296 * 2147483648 == -9223372036854775808)
    assert(0 * -9223372036854775808 == 0)
    assert(1 * -9223372036854775808 == -9223372036854775808)
    IO.puts("exact")
  end
end
`
	if err := os.WriteFile(source, []byte(program), 0600); err != nil {
		t.Fatal(err)
	}
	if err := BuildTo(source, binary); err != nil {
		t.Fatal(err)
	}
	output, err := exec.Command(binary).CombinedOutput()
	if err != nil || string(output) != "exact\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}
