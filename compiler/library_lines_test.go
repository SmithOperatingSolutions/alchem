package compiler

import (
	"strings"
	"testing"
)

// With coverage on, each line of library.go.txt is placed at the same line,
// less LibraryLineOffset, of every program's library, and the sections a
// program does not use are blank.
func TestLibraryLinesKeepTheirPlace(t *testing.T) {
	mapLibraryLines = true
	defer func() { mapLibraryLines = false }()
	source := strings.Split(librarySource, "\n")
	for _, program := range []string{"func main(){}", "func main(){ _ = calDateIso(TDate{}) }", "func main(){ _ = httpPost }"} {
		out := strings.Split(selectLibrary(program), "\n")
		if len(out) != LibraryLineOffset+len(source) {
			t.Fatalf("%s: %d lines, want %d", program, len(out), LibraryLineOffset+len(source))
		}
		kept := 0
		for i, text := range source {
			got := out[LibraryLineOffset+i]
			if got != "" && got != text {
				t.Fatalf("%s: line %d is %q, want %q", program, i+1, got, text)
			}
			if got != "" {
				kept++
			}
		}
		if program != "func main(){}" && kept < 10 {
			t.Fatalf("%s: only %d lines kept", program, kept)
		}
	}
}
