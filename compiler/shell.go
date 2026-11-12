package compiler

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/lexer"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// Shell evaluates Alchem one input at a time, as alchem alx does. Alchem is
// compiled, so each input is checked and run as part of a program holding
// the definitions and statements accepted so far; only the output of the new
// input is shown. Earlier statements run again each time, so their effects
// on files or the network repeat.
type Shell struct {
	// Dir is where the program is built, so that imports resolve as they
	// would for a file there.
	Dir        string
	imports    []string
	defs       []string
	statements []string
	count      int
}

// ShellResult is what one input produced.
type ShellResult struct {
	// Output is what the input printed, then its value, inspected.
	Output string
	// Incomplete means the input continues on the next line.
	Incomplete bool
}

const shellMarker = "--alchem-shell-output--"

var (
	definition = regexp.MustCompile(`^\s*(def|defp|defmacro|defprotocol|defimpl|struct|type|defexception|extern|@doc|@typedoc)\b`)
	importLine = regexp.MustCompile(`^\s*import\s+"`)
	located    = regexp.MustCompile(`^(?:[^:\n]*:)?(\d+):(\d+): `)
)

// program is the source of the shell's program with one more input, whose
// statements are given as written.
func (s *Shell) program(imports, defs, statements []string) string {
	var b strings.Builder
	b.WriteString("defmodule AlchemShell do\n")
	for _, line := range imports {
		b.WriteString("  " + line + "\n")
	}
	for _, def := range defs {
		b.WriteString(def + "\n")
	}
	b.WriteString("  def main() do\n")
	for _, statement := range statements {
		b.WriteString(statement + "\n")
	}
	b.WriteString("  end\nend\n")
	return b.String()
}

// lines counts the lines of a piece of source.
func lines(text string) int { return strings.Count(strings.TrimRight(text, "\n"), "\n") + 1 }

// Eval runs one input. A compile error is returned as an error and leaves
// the shell as it was; so does a failure while the input runs.
func (s *Shell) Eval(ctx context.Context, input string) (ShellResult, error) {
	if strings.TrimSpace(input) == "" {
		return ShellResult{}, nil
	}
	if unfinished(input) {
		return ShellResult{Incomplete: true}, nil
	}
	switch {
	case importLine.MatchString(input):
		imports := append(append([]string{}, s.imports...), strings.TrimSpace(input))
		if err := s.check(ctx, s.program(imports, s.defs, []string{"    assert(true)"})); err != nil {
			return s.incomplete(input, err, len(imports)+1)
		}
		s.imports = imports
		return ShellResult{Output: ":ok\n"}, nil
	case definition.MatchString(input):
		defs := append(append([]string{}, s.defs...), input)
		source := s.program(s.imports, defs, []string{"    assert(true)"})
		if err := s.check(ctx, source); err != nil {
			return s.incomplete(input, err, 2+len(s.imports)+s.defLines())
		}
		s.defs = defs
		return ShellResult{Output: ":ok\n"}, nil
	}
	// Parse the input as the last statement of main to see what it is.
	start := 3 + len(s.imports) + s.defLines() + s.statementLines()
	trial := s.program(s.imports, s.defs, append(append([]string{}, s.statements...), input))
	parsed, err := syntax.ParseSyntax(trial)
	if err != nil {
		return s.incomplete(input, err, start)
	}
	var main *ast.Function
	for i := range parsed.Functions {
		if parsed.Functions[i].Name == "main" {
			main = &parsed.Functions[i]
		}
	}
	if main == nil || len(main.Body) == 0 {
		return ShellResult{}, fmt.Errorf("not a statement")
	}
	last := main.Body[len(main.Body)-1]
	s.count++
	value := "iex_value_" + strconv.Itoa(s.count)
	// The input's own statement is kept; the shown value comes from extra
	// statements that are not.
	kept := []string{input}
	shown := []string{"IO.puts(" + strconv.Quote(shellMarker) + ")"}
	switch last.Kind {
	case "bind":
		annotation := ""
		if last.Declared != "" {
			annotation = ": " + last.Declared
		}
		if last.Pattern != nil && last.Pattern.Kind == "name" {
			kept = []string{input}
			shown = append(shown, input, "IO.inspect("+last.Pattern.Name+")")
		} else {
			kept = []string{value + annotation + " = " + formatExpr(last.Expr, 2), formatPattern(last.Pattern) + " = " + value}
			shown = append(shown, kept[0], kept[1], "IO.inspect("+value+")")
		}
	default:
		// An input with a value is bound to a name of its own, which is
		// shown; one without, such as IO.puts, stays a statement.
		bound := value + " = " + input
		if s.check(ctx, s.program(s.imports, s.defs, append(append([]string{}, s.statements...), bound, "IO.inspect("+value+")"))) == nil {
			kept = []string{bound}
			shown = append(shown, bound, "IO.inspect("+value+")")
			break
		}
		shown = append(shown, input)
	}
	source := s.program(s.imports, s.defs, append(append([]string{}, s.statements...), shown...))
	output, err := s.run(ctx, source)
	if err != nil {
		// The marker takes the first line after the kept statements.
		return ShellResult{}, s.relocate(err, start+1)
	}
	s.statements = append(s.statements, kept...)
	return ShellResult{Output: output}, nil
}

// statementLines is how many lines the kept statements take.
func (s *Shell) statementLines() int {
	n := 0
	for _, statement := range s.statements {
		n += lines(statement)
	}
	return n
}

// defLines is how many lines the definitions take.
func (s *Shell) defLines() int {
	n := 0
	for _, def := range s.defs {
		n += lines(def)
	}
	return n
}

// incomplete decides whether a compile error means the input goes on: an
// error past the input's last line is the program's closing ends found
// where the input's own blocks should have closed.
func (s *Shell) incomplete(input string, err error, start int) (ShellResult, error) {
	message := err.Error()
	if fields := located.FindStringSubmatch(message); fields != nil {
		line, _ := strconv.Atoi(fields[1])
		if line > start+lines(input)-1 {
			return ShellResult{Incomplete: true}, nil
		}
		if line >= start {
			// Report the position within the input.
			return ShellResult{}, fmt.Errorf("line %d: %s", line-start+1, message[len(fields[0]):])
		}
	}
	return ShellResult{}, s.relocate(err, start)
}

// file writes a program beside the shell's directory, so its imports
// resolve, and returns its path and its removal.
func (s *Shell) file(source string) (string, func(), error) {
	dir := s.Dir
	if dir == "" {
		dir = "."
	}
	f, err := os.CreateTemp(dir, ".alchem-shell-*.alc")
	if err != nil {
		return "", nil, err
	}
	_, err = f.WriteString(source)
	f.Close()
	remove := func() { os.Remove(f.Name()) }
	if err != nil {
		remove()
		return "", nil, err
	}
	return f.Name(), remove, nil
}

func (s *Shell) check(ctx context.Context, source string) error {
	path, remove, err := s.file(source)
	if err != nil {
		return err
	}
	defer remove()
	return CheckContext(ctx, path)
}

// run builds and runs a program, returning what it printed after the marker.
func (s *Shell) run(ctx context.Context, source string) (string, error) {
	path, remove, err := s.file(source)
	if err != nil {
		return "", err
	}
	defer remove()
	work, err := os.MkdirTemp("", "alchem-shell-*")
	if err != nil {
		return "", err
	}
	defer os.RemoveAll(work)
	binary := filepath.Join(work, "shell")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	if err := BuildToContext(ctx, path, binary); err != nil {
		return "", err
	}
	var stdout, stderr bytes.Buffer
	cmd := exec.CommandContext(ctx, binary)
	cmd.Dir = s.Dir
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	runErr := cmd.Run()
	output := stdout.String()
	if index := strings.Index(output, shellMarker+"\n"); index >= 0 {
		output = output[index+len(shellMarker)+1:]
	} else {
		output = ""
	}
	if runErr != nil {
		problem := strings.TrimSpace(stderr.String())
		if problem == "" {
			problem = runErr.Error()
		}
		return "", fmt.Errorf("%s%s", output, problem)
	}
	return output, nil
}

// temporary matches a position in the shell's program file.
var temporary = regexp.MustCompile(`[^\s()]*\.alchem-shell-\d+\.alc:(\d+)(:\d+)?:?`)

// relocate rewrites positions in the shell's program as lines of the input,
// which starts at line start, and drops the stack lines that name it.
func (s *Shell) relocate(err error, start int) error {
	var kept []string
	for _, line := range strings.Split(err.Error(), "\n") {
		if strings.HasPrefix(strings.TrimSpace(line), "at AlchemShell.") {
			continue
		}
		kept = append(kept, temporary.ReplaceAllStringFunc(line, func(found string) string {
			fields := temporary.FindStringSubmatch(found)
			n, _ := strconv.Atoi(fields[1])
			if n < start {
				return ""
			}
			return fmt.Sprintf("line %d:", n-start+1)
		}))
	}
	return fmt.Errorf("%s", strings.TrimSpace(strings.Join(kept, "\n")))
}

// unfinished reports an input that has opened more than it has closed: a
// do or fn block without its end, a bracket, or a string or heredoc.
func unfinished(input string) bool {
	tokens, err := lexer.Scan(input)
	if err != nil {
		return strings.Contains(err.Error(), "unterminated")
	}
	blocks, brackets := 0, 0
	for i, t := range tokens {
		switch t.Kind {
		case lexer.Ident:
			switch t.Text {
			case "do":
				if i+1 >= len(tokens) || tokens[i+1].Kind != lexer.Colon {
					blocks++
				}
			case "fn":
				// fn(params): type do ... end closes with the end of its do.
				if i+1 >= len(tokens) || tokens[i+1].Kind != lexer.LParen {
					blocks++
				}
			case "end":
				blocks--
			}
		case lexer.LParen, lexer.LBracket, lexer.LBrace, lexer.MapStart:
			brackets++
		case lexer.RParen, lexer.RBracket, lexer.RBrace:
			brackets--
		}
	}
	return blocks > 0 || brackets > 0
}

// Reset forgets every definition and statement.
func (s *Shell) Reset() { *s = Shell{Dir: s.Dir} }
