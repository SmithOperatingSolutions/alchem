package compiler

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
)

// TestFormatKeepsEveryCommentInPlace writes a comment before each line of
// every Alchem file in the repository, one at a time, and checks that the
// formatter leaves the comment where it was: directly above the same line,
// at its indentation, with nothing else moved.
func TestFormatKeepsEveryCommentInPlace(t *testing.T) {
	if testing.Short() {
		t.Skip("formats every file in the repository many times")
	}
	var files []string
	filepath.WalkDir("..", func(path string, d fs.DirEntry, err error) error {
		if err == nil && d.IsDir() && path != ".." && strings.HasPrefix(d.Name(), ".") {
			return filepath.SkipDir
		}
		if err == nil && !d.IsDir() && strings.HasSuffix(path, ".alc") {
			files = append(files, path)
		}
		return nil
	})
	// The probes of a file of n lines format it n times, so the largest
	// files would take most of the package's time: each hundred lines of a
	// file is a subtest of its own, run alongside the others.
	var failures atomic.Int64
	t.Run("files", func(t *testing.T) {
		for _, path := range files {
			source, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			base, err := Format(string(source))
			if err != nil {
				continue
			}
			lines := strings.Split(strings.TrimSuffix(base, "\n"), "\n")
			for from := 1; from < len(lines); from += 100 {
				to := min(from+100, len(lines))
				t.Run(fmt.Sprintf("%s:%d", path, from+1), func(t *testing.T) {
					t.Parallel()
					failures.Add(int64(probeComments(t, path, lines, from, to)))
				})
			}
		}
	})
	if n := failures.Load(); n > 0 {
		t.Errorf("%d comments moved", n)
	}
}

// probeComments writes a comment before each of the lines from..to-1 of a
// formatted file, one at a time, and reports each that the formatter moves:
// how many it moved.
func probeComments(t *testing.T, path string, lines []string, from, to int) int {
	failures := 0
	depth := func(line string) int { return len(line) - len(strings.TrimLeft(line, " ")) }
	for i := from; i < to; i++ {
		if strings.TrimSpace(lines[i]) == "" {
			continue
		}
		previous := i - 1
		for previous > 0 && strings.TrimSpace(lines[previous]) == "" {
			previous--
		}
		// The comment is indented as the line below it, or as the one
		// above where that is deeper, as before an end. After a line
		// that opens a block it is the block's first line.
		at := max(depth(lines[i]), depth(lines[previous]))
		if strings.HasSuffix(lines[previous], " do") {
			at = depth(lines[i])
		}
		// Not kept in place: a comment among the @tag lines above a
		// test, which moves above them, and one before the max_runs:
		// of a check all.
		line := strings.TrimSpace(lines[i])
		if at == 0 || strings.HasPrefix(strings.TrimSpace(lines[previous]), "@tag ") || strings.HasPrefix(line, "max_runs:") {
			continue
		}
		probed := append(append(append([]string{}, lines[:i]...), strings.Repeat(" ", at)+"# probe"), lines[i:]...)
		want := strings.Join(probed, "\n") + "\n"
		got, err := Format(want)
		if err != nil || got == want {
			continue
		}
		if failures++; failures <= 20 {
			t.Errorf("%s:%d: a comment before %q moved:\n%s", path, i+1, strings.TrimSpace(lines[i]), around(got, "# probe"))
		}
	}
	return failures
}

// around shows the lines near the first line holding text.
func around(source, text string) string {
	lines := strings.Split(source, "\n")
	for i, line := range lines {
		if strings.Contains(line, text) {
			from, to := max(0, i-3), min(len(lines), i+4)
			return fmt.Sprintf("%s", strings.Join(lines[from:to], "\n"))
		}
	}
	return "(the comment is gone)"
}
