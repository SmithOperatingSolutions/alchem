package compiler

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime/debug"
	"strings"
	"sync/atomic"
	"testing"
)

// Every program the compiler is given is checked without the compiler
// failing itself: each fixture is cut short after each of its lines, and
// has each of its lines taken out, and the checker must report what is wrong
// with the result, or accept it, but never panic. That is also how the
// error paths of the parser and the checker are reached.
func TestMalformedProgramsAreReported(t *testing.T) {
	if testing.Short() {
		t.Skip("checks thousands of programs")
	}
	var sources []string
	for _, pattern := range []string{"../tests/fixtures/*.alc", "testdata/*/*.alc", "../examples/*.alc", "../examples/kv/lib/*.alc"} {
		found, err := filepath.Glob(filepath.FromSlash(pattern))
		if err != nil {
			t.Fatal(err)
		}
		sources = append(sources, found...)
	}
	if len(sources) == 0 {
		t.Fatal("no programs to break")
	}
	var checked atomic.Int64
	// Each source is broken up in a subtest of its own, run in parallel
	// with the others, writing its variants to its own file.
	for _, source := range sources {
		t.Run(filepath.Base(source), func(t *testing.T) {
			t.Parallel()
			path := filepath.Join(t.TempDir(), "main.alc")
			check := func(origin, variant, text string) {
				t.Helper()
				if err := os.WriteFile(path, []byte(text), 0o600); err != nil {
					t.Fatal(err)
				}
				func() {
					defer func() {
						if v := recover(); v != nil {
							t.Errorf("%s, %s: the checker panicked: %v\n%s", origin, variant, v, debug.Stack())
						}
					}()
					_ = Check(path)
				}()
				func() {
					defer func() {
						if v := recover(); v != nil {
							t.Errorf("%s, %s: the formatter panicked: %v\n%s", origin, variant, v, debug.Stack())
						}
					}()
					_, _ = Format(text)
				}()
				checked.Add(1)
			}
			breakUp(t, source, check)
		})
	}
	t.Cleanup(func() { t.Logf("checked %d programs", checked.Load()) })
}

// breakUp gives check each broken variant of one source program.
func breakUp(t *testing.T, source string, check func(origin, variant, text string)) {
	t.Helper()
	data, err := os.ReadFile(source)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(string(data), "\n")
	name := filepath.Base(source)
	for i := range lines {
		check(name, fmt.Sprintf("cut after line %d", i+1), strings.Join(lines[:i+1], "\n"))
		without := append(append([]string{}, lines[:i]...), lines[i+1:]...)
		check(name, fmt.Sprintf("without line %d", i+1), strings.Join(without, "\n"))
		// Cut inside the line, after its first token, leaves an
		// expression or declaration unfinished at the end of the file.
		if !raceDetector {
			trimmed := strings.TrimLeft(lines[i], " ")
			if at := strings.IndexAny(trimmed, " (,.["); at > 0 && at+1 < len(trimmed) {
				prefix := strings.Join(lines[:i], "\n") + "\n" + lines[i][:len(lines[i])-len(trimmed)+at+1]
				check(name, fmt.Sprintf("cut inside line %d", i+1), prefix)
			}
		}
	}
	// Single characters taken out, at intervals through the file: a
	// bracket, quote, operator or letter missing inside a line.
	text := string(data)
	for at := 7; at < len(text) && !raceDetector; at += 23 {
		check(name, fmt.Sprintf("without byte %d", at), text[:at]+text[at+1:])
	}
}
