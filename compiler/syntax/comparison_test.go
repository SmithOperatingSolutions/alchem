package syntax

import (
	"strings"
	"testing"
)

func TestComparisonAssertions(t *testing.T) {
	for _, expr := range []string{`1 == 1`, `-2 < 0`, `10 >= 2`, `"hi" != "bye"`, `true == false`, `9223372036854775807 > -9223372036854775808`} {
		t.Run(expr, func(t *testing.T) {
			p, err := Parse("defmodule Check do def main() do assert(" + expr + ") end end")
			if err != nil {
				t.Fatal(err)
			}
			if p.Comparison == nil {
				t.Fatal("missing comparison AST")
			}
		})
	}
}
func TestInvalidComparisons(t *testing.T) {
	for _, expr := range []string{`1 == "1"`, `true < false`, `1`, `9223372036854775808 == 0`, `1 ==`, `1 == 1 == true`, `foo == foo`, `[1] < [2]`} {
		t.Run(expr, func(t *testing.T) {
			_, err := Parse("defmodule Check do def main() do assert(" + expr + ") end end")
			if err == nil || !strings.Contains(err.Error(), ":") {
				t.Fatalf("expected positioned error, got %v", err)
			}
		})
	}
}
