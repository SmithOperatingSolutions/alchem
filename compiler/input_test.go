package compiler

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func buildProgram(t *testing.T, source string) string {
	t.Helper()
	d := t.TempDir()
	path := filepath.Join(d, "main.alc")
	binary := filepath.Join(d, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	if err := os.WriteFile(path, []byte(source), 0600); err != nil {
		t.Fatal(err)
	}
	if err := BuildTo(path, binary); err != nil {
		t.Fatal(err)
	}
	return binary
}

func runProgram(binary, stdin string, args ...string) (string, error) {
	cmd := exec.Command(binary, args...)
	cmd.Stdin = strings.NewReader(stdin)
	var out bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &out
	err := cmd.Run()
	return out.String(), err
}

// Arguments, lines with either line ending, the remainder of standard input
// and a file all arrive as the exact text supplied.
func TestProgramInput(t *testing.T) {
	binary := buildProgram(t, `defmodule Input do
  def main() do
    IO.puts(String.join(System.argv(), "|"))
    IO.puts("lines=" <> line() <> "," <> line() <> "," <> line())
    rest = IO.read_all()
    IO.puts("rest=" <> Integer.to_string(String.length(rest)))
    assert(IO.read_line() == none)
    case File.read(System.argv()[0]) do
      ok(text) -> IO.puts("file=" <> String.trim(text))
      error(reason) -> IO.puts("unreadable: " <> reason)
    end
  end

  def line(): string do
    case IO.read_line() do
      some(text) -> text
      none -> "<end of input>"
    end
  end
end
`)
	file := filepath.Join(t.TempDir(), "data.txt")
	if err := os.WriteFile(file, []byte("contents ünïcode\n"), 0600); err != nil {
		t.Fatal(err)
	}
	out, err := runProgram(binary, "alpha\r\n\nbeta ü\ngamma\ndelta", file, "two words", "ü")
	want := file + "|two words|ü\nlines=alpha,,beta ü\nrest=11\nfile=contents ünïcode\n"
	if err != nil || out != want {
		t.Fatalf("err=%v\ngot  %q\nwant %q", err, out, want)
	}
}

// Input that cannot become an Alchem string is refused rather than passed on.
func TestProgramInputLimits(t *testing.T) {
	line := buildProgram(t, "defmodule Line do\n def main() do\n  case IO.read_line() do\n   some(text) -> IO.puts(Integer.to_string(String.length(text)))\n   none -> IO.puts(\"end\")\n  end\n end\nend\n")
	all := buildProgram(t, "defmodule All do\n def main() do\n  text = IO.read_all()\n  IO.puts(Integer.to_string(String.length(text)))\n end\nend\n")
	cases := []struct {
		name, binary, stdin, want string
		fails                     bool
	}{
		{"longest line", line, strings.Repeat("a", 1<<20) + "\n", "1048576\n", false},
		{"line too long", line, strings.Repeat("a", 1<<20+1) + "\n", "input line exceeds 1048576 bytes", true},
		{"line too long without newline", line, strings.Repeat("a", 2<<20), "input line exceeds 1048576 bytes", true},
		{"line not UTF-8", line, "caf\xe9\n", "input is not valid UTF-8", true},
		{"line at end of input", line, "", "end\n", false},
		{"all not UTF-8", all, "ok\n\xff\xfe", "input is not valid UTF-8", true},
		{"all too large", all, strings.Repeat("a", 16<<20+1), "input exceeds 16777216 bytes", true},
		{"all at limit", all, strings.Repeat("a", 16<<20), "16777216\n", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			out, err := runProgram(tc.binary, tc.stdin)
			if (err != nil) != tc.fails || !strings.Contains(out, tc.want) {
				t.Fatalf("err=%v output=%.200q", err, out)
			}
			if tc.fails && !strings.Contains(out, "main.alc:3:") {
				t.Fatalf("failure has no source location: %.200q", out)
			}
		})
	}
}

// A file that cannot become a string is an error value whose reason says why.
func TestFileReadRefusesUnusableFiles(t *testing.T) {
	binary := buildProgram(t, `defmodule Files do
  def main() do
    case File.read(System.argv()[0]) do
      ok(_) -> IO.puts("read")
      error(reason) -> IO.puts("refused: " <> reason)
    end
  end
end
`)
	d := t.TempDir()
	binaryData := filepath.Join(d, "binary.dat")
	tooLarge := filepath.Join(d, "large.txt")
	atLimit := filepath.Join(d, "limit.txt")
	missing := filepath.Join(d, "missing.txt")
	if err := os.WriteFile(binaryData, []byte("text\xff\xfe"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(tooLarge, bytes.Repeat([]byte("a"), 16<<20+1), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(atLimit, bytes.Repeat([]byte("a"), 16<<20), 0600); err != nil {
		t.Fatal(err)
	}
	_, missingErr := os.Open(missing)
	_, nameErr := os.Open("bad\x00name")
	cases := []struct{ path, want string }{
		{binaryData, "refused: file is not valid UTF-8\n"},
		{tooLarge, "refused: file exceeds 16777216 bytes\n"},
		{atLimit, "read\n"},
		{missing, "refused: " + missingErr.Error() + "\n"},
		{d, "refused: "},
		{"bad\x00name", "refused: " + nameErr.Error() + "\n"},
	}
	for _, tc := range cases {
		out, err := runProgram(binary, "", tc.path)
		if strings.Contains(tc.path, "\x00") && err != nil && out == "" {
			continue // the operating system refuses to start a program with such an argument
		}
		exact := strings.HasSuffix(tc.want, "\n")
		if err != nil || (exact && out != tc.want) || !strings.HasPrefix(out, tc.want) || len(out) <= len("refused: ") && tc.want != "read\n" {
			t.Fatalf("%q: err=%v output=%q want %q", tc.path, err, out, tc.want)
		}
	}
}
