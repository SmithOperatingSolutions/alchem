package testrunner

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

// Run builds and executes Alchem fixtures, checking stdout and explicit exit codes.
// Test files without an .exitcode sidecar must exit successfully.
func Run(directory string) error { return RunWithTimeout(directory, 30*time.Second) }
func RunWithTimeout(directory string, timeout time.Duration) error {
	return RunContext(context.Background(), directory, timeout)
}
func RunContext(ctx context.Context, directory string, timeout time.Duration) error {
	if timeout <= 0 {
		return fmt.Errorf("fixture timeout must be positive")
	}
	entries, err := os.ReadDir(directory)
	if err != nil {
		return err
	}
	var names []string
	for _, entry := range entries {
		// Files named *_test.alc are test modules, run by RunTests.
		if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".alc") && !strings.HasSuffix(entry.Name(), "_test.alc") {
			names = append(names, entry.Name())
		}
	}
	sort.Strings(names)
	if len(names) == 0 {
		return fmt.Errorf("no executable .alc fixtures found in %s", directory)
	}
	// Fixtures are built and run a few at a time; results are reported in
	// name order, and the first failure in that order is returned.
	failures := make([]error, len(names))
	next := make(chan int)
	var workers sync.WaitGroup
	for range min(runtime.GOMAXPROCS(0), len(names)) {
		workers.Add(1)
		go func() {
			defer workers.Done()
			for i := range next {
				failures[i] = runFixture(ctx, directory, names[i], timeout)
			}
		}()
	}
	for i := range names {
		next <- i
	}
	close(next)
	workers.Wait()
	for i, name := range names {
		if failures[i] != nil {
			return failures[i]
		}
		fmt.Printf("PASS %s\n", name)
	}
	return nil
}

// runFixture builds and runs one program fixture and checks what it did.
func runFixture(ctx context.Context, directory, name string, timeout time.Duration) error {
	native := strings.HasSuffix(name, ".test.alc")
	base := strings.TrimSuffix(name, ".alc")
	expectedCode := 0
	exitBytes, err := os.ReadFile(filepath.Join(directory, base+".exitcode"))
	if err == nil {
		expectedCode, err = strconv.Atoi(strings.TrimSpace(string(exitBytes)))
		if err != nil || expectedCode < 0 {
			return fmt.Errorf("%s: invalid exitcode", name)
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	var expected []byte
	if !native {
		expected, err = os.ReadFile(filepath.Join(directory, base+".stdout"))
		if err != nil {
			return fmt.Errorf("%s: expected stdout: %w", name, err)
		}
	}
	expectedStderr, stderrErr := os.ReadFile(filepath.Join(directory, base+".stderr"))
	if stderrErr != nil && !os.IsNotExist(stderrErr) {
		return fmt.Errorf("%s: expected stderr: %w", name, stderrErr)
	}
	source, err := filepath.Abs(filepath.Join(directory, name))
	if err != nil {
		return err
	}
	work, err := os.MkdirTemp("", "alchem-test-*")
	if err != nil {
		return err
	}
	binary := filepath.Join(work, base)
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	buildErr := compiler.BuildToContext(ctx, source, binary)
	if buildErr != nil {
		os.RemoveAll(work)
		return fmt.Errorf("%s: compile: %w", name, buildErr)
	}
	cmd := exec.Command(binary)
	cmd.Dir = work
	actual, stderr, runErr := execute(ctx, cmd, timeout)
	exitCode := 0
	if runErr != nil {
		if exitErr, ok := runErr.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			os.RemoveAll(work)
			return fmt.Errorf("%s: execute: %w", name, runErr)
		}
	}
	os.RemoveAll(work)
	if exitCode != expectedCode {
		return fmt.Errorf("%s: exit code %d, expected %d; output: %s", name, exitCode, expectedCode, actual+stderr)
	}
	if !native && actual != string(expected) {
		return fmt.Errorf("%s: output mismatch: got %q want %q", name, actual, expected)
	}
	if native && expectedCode != 0 && !strings.Contains(stderr, "assertion failed") {
		return fmt.Errorf("%s: failure was not an assertion: %s", name, stderr)
	}
	if stderrErr == nil || expectedCode == 0 {
		if stderr != string(expectedStderr) {
			return fmt.Errorf("%s: stderr mismatch: got %q want %q", name, stderr, expectedStderr)
		}
	}
	return nil
}
