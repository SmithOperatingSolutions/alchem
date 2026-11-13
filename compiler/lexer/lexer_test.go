package lexer

import (
	"strconv"
	"strings"
	"testing"
)

func TestScan(t *testing.T) {
	tokens, err := Scan("defmodule Hello do\n IO.puts(\"hello\\nworld\") end")
	if err != nil {
		t.Fatal(err)
	}
	want := []Kind{Ident, Ident, Ident, Ident, LParen, String, RParen, Ident, EOF}
	if len(tokens) != len(want) {
		t.Fatalf("tokens=%v", tokens)
	}
	for i, k := range want {
		if tokens[i].Kind != k {
			t.Fatalf("token %d=%v want %v", i, tokens[i].Kind, k)
		}
	}
	if tokens[3].Line != 2 || tokens[3].Column != 2 {
		t.Fatalf("position=%v", tokens[3])
	}
}
func TestScanErrors(t *testing.T) {
	for _, src := range []string{"$", "\"unterminated", "\"bad\\q\"", "\"newline\n\""} {
		t.Run(strings.ReplaceAll(src, "\n", "newline"), func(t *testing.T) {
			if _, err := Scan(src); err == nil {
				t.Fatalf("expected error for %q", src)
			}
		})
	}
}

func TestAssignmentAndEqualityTokens(t *testing.T) {
	tokens, err := Scan("value = 1\nassert(value == 1)")
	if err != nil {
		t.Fatal(err)
	}
	if tokens[1].Kind != Assign || tokens[6].Kind != Operator || tokens[6].Text != "==" || tokens[6].Line != 2 {
		t.Fatalf("tokens=%v", tokens)
	}
}

func TestExpressionPunctuation(t *testing.T) {
	tokens, err := Scan("n-1+2*3/4%5, x: integer")
	if err != nil {
		t.Fatal(err)
	}
	want := []Kind{Ident, Operator, Integer, Operator, Integer, Operator, Integer, Operator, Integer, Operator, Integer, Comma, Ident, Colon, Ident, EOF}
	if len(tokens) != len(want) {
		t.Fatalf("tokens=%v", tokens)
	}
	for i, kind := range want {
		if tokens[i].Kind != kind {
			t.Fatalf("token %d=%v want %s", i, tokens[i], kind)
		}
	}
	if tokens[1].Text != "-" {
		t.Fatalf("minus token=%v", tokens[1])
	}
}

func TestCollectionAndPatternTokens(t *testing.T) {
	tokens, err := Scan("[a | tail] -> {a,tail} |> wrap()")
	if err != nil {
		t.Fatal(err)
	}
	want := []Kind{LBracket, Ident, Bar, Ident, RBracket, Arrow, LBrace, Ident, Comma, Ident, RBrace, Operator, Ident, LParen, RParen, EOF}
	if len(tokens) != len(want) {
		t.Fatalf("tokens=%v", tokens)
	}
	for i, kind := range want {
		if tokens[i].Kind != kind {
			t.Fatalf("token %d=%v want %s", i, tokens[i], kind)
		}
	}
	if tokens[5].Column != 12 || tokens[11].Text != "|>" {
		t.Fatalf("tokens=%v", tokens)
	}
}

func TestMapReferenceAndGuardTokens(t *testing.T) {
	tokens, err := Scan(`%{"x" => 1} when true -> &double`)
	if err != nil {
		t.Fatal(err)
	}
	want := []Kind{MapStart, String, Pair, Integer, RBrace, Ident, Ident, Arrow, Amp, Ident, EOF}
	if len(tokens) != len(want) {
		t.Fatalf("tokens=%v", tokens)
	}
	for i, k := range want {
		if tokens[i].Kind != k {
			t.Fatalf("token %d=%v want %s", i, tokens[i], k)
		}
	}
}

func TestScanPinToken(t *testing.T) {
	tokens, err := Scan("{^expected, _}")
	if err != nil {
		t.Fatal(err)
	}
	if len(tokens) < 3 || tokens[1].Kind != Caret || tokens[1].Column != 2 || tokens[2].Kind != Ident || tokens[2].Text != "expected" {
		t.Fatalf("unexpected tokens %+v", tokens)
	}
}

func TestScanConcatenationOperator(t *testing.T) {
	tokens, err := Scan(`a <> b < c <= d`)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"a", "<>", "b", "<", "c", "<=", "d"}
	for i, text := range want {
		if tokens[i].Text != text {
			t.Fatalf("token %d is %q, want %q", i, tokens[i].Text, text)
		}
	}
	if tokens[1].Kind != Operator || tokens[1].Column != 3 {
		t.Fatalf("unexpected concatenation token %+v", tokens[1])
	}
}

// \u{...} names a code point of one to six hex digits; an escape a string
// does not take is reported by name.
func TestBracedCodePointsAndEscapeProblems(t *testing.T) {
	for raw, want := range map[string]string{`"\u{E000}"`: "", `"\u{e9}x"`: "éx", `"\u{1F600}"`: "\U0001F600", `"a\\u{41}"`: `a\u{41}`} {
		if got, err := strconv.Unquote(Unescape(raw)); err != nil || got != want {
			t.Errorf("%s: %q %v", raw, got, err)
		}
	}
	for raw, escape := range map[string]string{`"\q"`: `\q`, `"\u{110000}"`: `\u{110000}`, `"\u{D800}"`: `\u{D800}`, `"\u{}"`: `\u{}`, `"\u12"`: `\u12`, `"\xZ1"`: `\xZ1`, `"\u{1234567}"`: `\u{1234567}`} {
		if problem := StringProblem(raw); !strings.HasPrefix(problem, "invalid escape "+escape+";") {
			t.Errorf("%s: %q", raw, problem)
		}
	}
	if problem := StringProblem(`"\u{263A} \x00 \n \#{"`); problem != "" {
		t.Errorf("valid escapes reported: %s", problem)
	}
}
