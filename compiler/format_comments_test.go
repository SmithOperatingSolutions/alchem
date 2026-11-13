package compiler

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
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
	failures := 0
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
		depth := func(line string) int { return len(line) - len(strings.TrimLeft(line, " ")) }
		for i := 1; i < len(lines); i++ {
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
	}
	if failures > 0 {
		t.Errorf("%d comments moved", failures)
	}
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
