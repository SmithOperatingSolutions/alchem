package syntax

import "testing"

func TestExtendedLanguage(t *testing.T) {
	_, err := Parse(`defmodule Demo do
 def add(x: integer, y: integer): integer do
  return x + y
 end
 def main() do
  count = add(2, 3 * 4)
  ready = count > 0 and not false
  if ready do
   assert(count == 14)
  else
   assert(false)
  end
 end
end`)
	if err != nil {
		t.Fatal(err)
	}
}
func TestExtendedErrors(t *testing.T) {
	for _, body := range []string{`x = 1 + true`, `if 1 do assert(true) end`, `assert(1 and 2)`, `assert(not 1)`, `x = missing(1)`, `if true do x = 1 end assert(x == 1)`, `x = 1 if true do x = 2 end`, `return 1`, `assert(1 + 2)`, `assert(true + false)`, `if true do assert(true) else end`} {
		t.Run(body, func(t *testing.T) {
			if _, err := Parse("defmodule X do def main() do " + body + " end end"); err == nil {
				t.Fatal("accepted invalid program")
			}
		})
	}
	for _, source := range []string{
		`defmodule X do def main(x: integer) do assert(true) end end`,
		`defmodule X do def main(): integer do return 1 end end`,
		`defmodule X do def f(): integer do return 1 end def f(): integer do return 2 end def main() do assert(true) end end`,
		`defmodule X do def f(x: integer, x: integer): integer do return x end def main() do assert(true) end end`,
		`defmodule X do def f(): float do return 1 end def main() do assert(true) end end`,
		`defmodule X do def f() do return 1 end def main() do assert(true) end end`,
		`defmodule X do def f(): integer do return 1 x = 2 end def main() do assert(true) end end`,
		`defmodule X do def main() do main() end end`,

		`defmodule X do def f(x: integer): integer do if x > 0 do return x end end def main() do assert(true) end end`,
		`defmodule X do def f(x: integer): boolean do return x end def main() do assert(true) end end`,
		`defmodule X do def f(x: integer): integer do return x end def main() do assert(f(true) == 1) end end`,
		`defmodule X do def f(x: integer): integer do return x end def main() do assert(f() == 1) end end`,
	} {
		if _, err := Parse(source); err == nil {
			t.Fatalf("accepted %s", source)
		}
	}
}
