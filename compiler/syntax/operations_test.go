package syntax

import "testing"

func TestOperationsGuardsAndMaps(t *testing.T) {
	_, err := Parse(`defmodule Data do
 def twice(n: integer): integer do return n*2 end
 def positive(n: integer): boolean do return n>0 end
 def sum(acc: integer, n: integer): integer do return acc+n end
 def main() do
  xs = [1,2] |> prepend(0) |> concat([3])
  ys = xs |> map(&twice) |> filter(&positive)
  assert(reduce(ys,0,&sum) == 12)
  data: map[string,integer] = %{"count" => 3}
  changed = put(data,"count",4)
  assert(data["count"] == 3 and changed["count"] == 4)
  case changed do
   %{"count" => n} when n > 0 -> assert(n == 4)
   _ -> assert(false)
  end
 end
end`)
	if err != nil {
		t.Fatal(err)
	}
}
func TestOperationsErrors(t *testing.T) {
	for _, body := range []string{
		`x = prepend([1],true)`, `x = concat([1],[true])`, `x = map([1],true)`, `x = filter([1],true)`,
		`x = reduce([1],0,true)`, `x = &missing`, `x = &main`, `x = %{}`, `x = %{[1] => 2}`, `x = %{"a" => 1, "b" => true}`,
		`m: map[boolean,integer] = %{1 => 2}`, `m = %{"a" => 1} x = m[1]`,
		`x = %{"a" => 1, "a" => 2}`, `m = %{"a" => 1} x = put(m,"b",true)`,
		`m = %{"a" => 1} x = get(m,"b",true)`, `m = %{"a" => 1} %{1 => x} = m`,
		`case 1 do n when n>0 -> assert(true) end`, `case 1 do n when n+1 -> assert(true) _ -> assert(false) end`,
		`case 1 do _ -> assert(true) n when n>0 -> assert(false) end`,
	} {
		t.Run(body, func(t *testing.T) {
			if _, err := Parse("defmodule X do def main() do " + body + " end end"); err == nil {
				t.Fatal("accepted invalid source")
			}
		})
	}
}

func TestCallbackAndGuardTypes(t *testing.T) {
	prefix := `defmodule X do
 def int_value(x: integer): integer do return x end
 def bool_value(x: boolean): boolean do return x end
 def two(a: integer,b: integer): integer do return a+b end
 def wrong_reduce(a: integer,b: integer): boolean do return true end
 def main() do `
	for _, body := range []string{
		`x = map([true],&int_value)`, `x = filter([1],&int_value)`, `x = map([1],&two)`,
		`x = reduce([1],true,&two)`, `x = reduce([1],0,&wrong_reduce)`,
		`f = &int_value assert(f == f)`, `assert([&int_value] == [&int_value])`,
		`f = &int_value x = f(true)`, `f = &int_value x = f()`,
		`case 1 do n when int_value(n) -> assert(true) _ -> assert(false) end`,
		`case 1 do n when n>0 -> assert(true) _ -> assert(true) end assert(n==1)`,
		`m = %{"a" => 1} %{"a" => x,"a" => y} = m`,
		`m = %{"a" => 1} %{key => value} = m`,
		`case %{"a" => 1} do %{} -> assert(true) %{"a" => x} -> assert(false) end`,
	} {
		t.Run(body, func(t *testing.T) {
			if _, err := Parse(prefix + body + " end end"); err == nil {
				t.Fatal("accepted invalid program")
			}
		})
	}
	for _, source := range []string{
		`defmodule X do def f(): fn[] do return 1 end def main() do assert(true) end end`,
		`defmodule X do def f(x: map[list[integer],integer]): integer do return 1 end def main() do assert(true) end end`,
		`defmodule X do def f(x: integer): integer do case x do n when n>0 -> return n _ -> IO.puts("no") end end def main() do assert(true) end end`,
	} {
		if _, err := Parse(source); err == nil {
			t.Fatalf("accepted %s", source)
		}
	}
}
