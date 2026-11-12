package syntax

import "testing"

func TestClosures(t *testing.T) {
	_, err := Parse(`defmodule Closures do
 def make(offset: integer): fn[integer,integer] do
  return fn(value: integer): integer do return value+offset end
 end
 def main() do
  factor = 3
  mapped = map([1,2],fn(n: integer): integer do return n*factor end)
  assert(mapped == [3,6])
  assert(make(2)(3) == 5)
  assert((fn(): integer do return 7 end)() == 7)
 end
end`)
	if err != nil {
		t.Fatal(err)
	}
}
func TestClosureErrors(t *testing.T) {
	for _, body := range []string{
		`f = fn(n: integer): boolean do return n end`,
		`f = fn(n: integer): integer do if n>0 do return n end end`,
		`f = fn(n: integer,n: integer): integer do return n end`,
		`n = 1 f = fn(n: integer): integer do return n end`,
		`f = fn(): integer do return missing end missing = 1`,
		`f = fn(): integer do return f() end`,
		`f = fn(): integer do return 1 end assert(f(true)==1)`,
		`f = fn(): integer do return 1 end assert(f==f)`,
		`x = (1)(2)`,
		`f = fn(n: integer): integer do return n end assert(n==1)`,
	} {
		t.Run(body, func(t *testing.T) {
			if _, err := Parse("defmodule X do def main() do " + body + " end end"); err == nil {
				t.Fatal("accepted invalid source")
			}
		})
	}
}
