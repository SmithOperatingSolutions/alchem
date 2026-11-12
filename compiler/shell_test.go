package compiler

import (
	"context"
	"strings"
	"testing"
)

func TestShellKeepsWhatCameBefore(t *testing.T) {
	s := &Shell{Dir: t.TempDir()}
	steps := []struct{ input, output, problem string }{
		{"1 + 2", "3\n", ""},
		{"x = 10", "10\n", ""},
		{`IO.puts("hi #{x}")`, "hi 10\n", ""},
		{"def double(n: integer): integer do\n  n * 2\nend", ":ok\n", ""},
		{"double(x)", "20\n", ""},
		{"[a, b] = [1, 2]", "[1, 2]\n", ""},
		{"a + b", "3\n", ""},
		{"if x > 5 do\n  \"big\"\nelse\n  \"small\"\nend", "\"big\"\n", ""},
		{"nope + 1", "", "line 1: undefined binding nope"},
		{`raise("boom")`, "", "boom"},
		{"x", "10\n", ""},
		{"add = fn(n: integer): integer do n + 1 end", "", ""},
		{"add.(1)", "2\n", ""},
		{"add.(1))", "", "line 1"},
		{"Enum.map([1, 2], fn n -> n + x end)", "[11, 12]\n", ""},
	}
	for _, step := range steps {
		result, err := s.Eval(context.Background(), step.input)
		if step.problem != "" {
			if err == nil || !strings.Contains(err.Error(), step.problem) {
				t.Fatalf("%q: got %v, want %q", step.input, err, step.problem)
			}
			continue
		}
		if err != nil || (step.output != "" && result.Output != step.output) {
			t.Fatalf("%q: got %q %v, want %q", step.input, result.Output, err, step.output)
		}
	}
	// An input whose blocks are not closed goes on.
	for _, partial := range []string{"def twice(n: integer): integer do", "case x do", "Enum.map([1], fn n ->", "[1,", "\"open", "y = %{\"a\" => 1,"} {
		if result, err := s.Eval(context.Background(), partial); err != nil || !result.Incomplete {
			t.Fatalf("%q: %v %+v", partial, err, result)
		}
	}
	s.Reset()
	if _, err := s.Eval(context.Background(), "x"); err == nil {
		t.Fatal("reset kept a binding")
	}
}
