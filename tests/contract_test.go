package tests

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

// The same fixture will eventually be exercised by both Go and Alchem runners.
// Today this is the Go-side contract; native Alchem assertions are not supported.
func TestHelloContract(t *testing.T) {
	source := filepath.Join("fixtures", "hello.alc")
	expected, err := os.ReadFile(filepath.Join("fixtures", "hello.stdout"))
	if err != nil {
		t.Fatal(err)
	}
	work := t.TempDir()
	previous, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(work); err != nil {
		t.Fatal(err)
	}
	defer os.Chdir(previous)
	absolute, err := filepath.Abs(filepath.Join(previous, source))
	if err != nil {
		t.Fatal(err)
	}
	if err := compiler.Build(absolute); err != nil {
		t.Fatal(err)
	}
	binary := filepath.Join(work, "hello")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	actual, err := exec.Command(binary).CombinedOutput()
	if err != nil {
		t.Fatalf("execute compiled Alchem: %v: %s", err, actual)
	}
	if string(actual) != string(expected) {
		t.Fatalf("stdout mismatch: got %q want %q", actual, expected)
	}
}
