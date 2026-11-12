package syntax

import "testing"

func TestCollectionsPatternsAndPipes(t *testing.T) {
	_, err := Parse(`defmodule Data do
 def first(xs: list[integer]): integer do
  case xs do
   [] -> return 0
   [head | tail] -> return head
  end
 end
 def pair(n: integer): tuple[integer,string] do return {n,"ok"} end
 def main() do
  empty: list[integer] = []
  items = [1,2,3]
  {count, label} = pair(items[0])
  [a,b,c] = items
  assert(count == a)
  assert(label == "ok")
  assert(length(empty) == 0)
  assert(items |> first() == 1)
  case pair(b) do
   {0, _} -> assert(false)
   {value, text} -> assert(value == 2 and text == "ok")
  end
 end
end`)
	if err != nil {
		t.Fatal(err)
	}
}
func TestCollectionErrors(t *testing.T) {
	for _, body := range []string{
		`xs = [1,true]`, `x: list[] = []`, `x: tuple[integer] = {1,true}`,
		`case [1] do [head|tail] -> assert(true) [1] -> assert(false) [] -> assert(true) end`,
		`case {1,true} do {_,true} -> assert(true) {0,true} -> assert(false) _ -> assert(true) end`,
		`case true do true -> assert(true) end`,
		`case {1,2} do {x,y} -> assert(true) end assert(x == 1)`,
		`case [1] do [x|x] -> assert(true) [] -> assert(true) end`,
		`length(1)`, `length()`, `x = {1,true}[0+0]`, `x = {1}[-1]`,
		`xs = []`, `x = {1,"a"}[2]`, `xs = {1,"a"} i = 0 x = xs[i]`,
		`x = [1][true]`, `assert([1] == [true])`, `assert([1] < [2])`, `x: list[integer] = [true]`,
		`{x,x} = {1,2}`, `x = 1 {x,y} = {1,2}`, `{a,b} = [1,2]`, `[a,b] = {1,2}`,
		`case 1 do 0 -> assert(true) end`, `case true do _ -> assert(true) false -> assert(false) end`,
		`case true do true -> assert(true) true -> assert(false) false -> assert(true) end`,
		`case [1] do [] -> assert(true) [x | tail] -> assert(true) end assert(x == 1)`,
		`x = 1 |> missing()`, `x = 1 |> length()`, `x = 1 |> length`,
	} {
		t.Run(body, func(t *testing.T) {
			if _, err := Parse("defmodule X do def main() do " + body + " end end"); err == nil {
				t.Fatal("accepted invalid source")
			}
		})
	}
}
