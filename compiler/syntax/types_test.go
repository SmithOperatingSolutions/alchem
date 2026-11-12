package syntax

import (
	"strings"
	"testing"
)

func TestTypeDeclarationErrors(t *testing.T) {
	prefix := `struct Point do x: integer y: integer end
 struct Box[t] do value: t end
 type Color do red green custom(code: integer) end
 def id(value: a): a do value end
 def first(pair: tuple[a, b]): a do pair[0] end
 `
	cases := []struct{ declarations, body, want string }{
		{``, `p = %Point{x: 1}`, "missing field y"},
		{``, `p = %Point{x: 1, y: 2, z: 3}`, "Point has no field z"},
		{``, `p = %Point{x: 1, x: 2, y: 3}`, "duplicate field x"},
		{``, `p = %Point{x: "a", y: 2}`, "expected integer, found string"},
		{``, `p = %Missing{x: 1}`, "unknown type"},
		{``, `p = %Point{x: 1, y: 2} q = p.z`, "Point has no field z"},
		{``, `q = 5 r = q.x`, "field access requires a struct"},
		{``, `p = %Point{x: 1, y: 2} %Point{z: v} = p`, "Point has no field z"},
		{``, `c = Color.blue`, "Color has no variant blue"},
		{``, `c = Color.custom`, "Color.custom requires 1 argument"},
		{``, `c = Color.red(1)`, "Color.red requires 0 arguments"},
		{``, `c = Color.custom("x")`, "expected integer, found string"},
		{``, `c = Color.red case c do Color.red -> assert(true) Color.green -> assert(true) end`, "non-exhaustive"},
		{``, `c = Color.red case c do Color.red -> assert(true) Color.red -> assert(true) _ -> assert(true) end`, "unreachable"},
		{``, `x = none`, "cannot infer"},
		{``, `x = ok(1)`, "cannot infer"},
		{``, `x: option[integer] = some("a")`, "expected integer, found string"},
		{``, `x: result[integer, string] = ok(1) case x do ok(v) -> assert(true) end`, "non-exhaustive"},
		{``, `b = %Box{value: 1} c: Box[string] = b`, "expected Main.Box[string], found Main.Box[integer]"},
		{``, `x: Box = %Box{value: 1}`, "Box requires 1 type argument"},
		{``, `x: Point[integer] = %Point{x: 1, y: 2}`, "Point requires 0 type arguments"},
		{``, `x: widget = 1`, "unknown type"},
		{``, `f = &id`, "needs an expected function type"},
		{``, `x: string = id(1)`, "expected"},
		{`def bad(x: a): b do x end`, `assert(true)`, "type variable b"},
		{`def bad(x: a): integer do x + 1 end`, `assert(true)`, "expected a, found integer"},
		{`struct Loop do next: Loop end`, `assert(true)`, "contains itself"},
		{`struct A do b: B end struct B do a: A end`, `assert(true)`, "contains itself"},
		{`struct Bad do value: t end`, `assert(true)`, "unknown type"},
		{`struct Point do x: integer end`, `assert(true)`, "duplicate type Point"},
		{`type Empty do end`, `assert(true)`, "requires at least one variant"},
		{`struct File do path: string end`, `assert(true)`, "type name File is reserved"},
		{`extern type Time = "time.Time"`, `assert(true)`, "type name Time is reserved"},
		{`type Twice do a a end`, `assert(true)`, "duplicate variant a"},
		{`struct Keyed do entries: map[Point, integer] end`, `assert(true)`, "invalid type"},
	}
	for _, tc := range cases {
		t.Run(tc.declarations+tc.body, func(t *testing.T) {
			_, err := Parse("defmodule Main do " + prefix + tc.declarations + " def main() do " + tc.body + " end end")
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

func TestGenericsAndTypesAccepted(t *testing.T) {
	_, err := Parse(`defmodule Main do
 struct Box[t] do value: t end
 type Chain[t] do stop link(head: t, rest: Chain[t]) end
 def unbox(box: Box[t]): t do box.value end
 def count(chain: Chain[t]): integer do
  case chain do
   Chain.stop -> 0
   Chain.link(_, rest) -> 1 + count(rest)
  end
 end
 def pair(x: a, y: b): tuple[a, b] do {x, y} end
 def lift(x: a): option[a] do some(x) end
 def main() do
  assert(unbox(%Box{value: 3}) == 3)
  empty: Chain[string] = Chain.stop
  assert(count(Chain.link("a", Chain.link("b", empty))) == 2)
  assert(pair(1, "a") == {1, "a"})
  maybe = lift(4)
  case maybe do
   some(4) -> assert(true)
   some(_) -> assert(false)
   none -> assert(false)
  end
  f: fn[integer, option[integer]] = &lift
  assert(f(1) == some(1))
 end
end`)
	if err != nil {
		t.Fatal(err)
	}
}

func TestStandardLibraryErrors(t *testing.T) {
	cases := []struct{ declarations, body, want string }{
		{``, `x = File.read(1)`, "expected string, found integer"},
		{``, `x = IO.write("a")`, "returns no value"},
		{``, `s = Server.start(0, 1)`, "server handler must be fn[State,Request,tuple[State,Reply]]"},
		{`def h(s: integer, q: fn[integer,integer]): tuple[integer,integer] do {s, s} end`, `s = Server.start(0, &h)`, "requests and replies cannot contain functions"},
		{`def h(s: integer, q: integer): tuple[integer,string] do {s, "x"} end`, `s = Server.start("a", &h)`, "expected integer, found string"},
		{`def h(s: integer, q: integer): tuple[integer,string] do {s, "x"} end`, `s = Server.start(0, &h) r = Server.call(s, "q", 10)`, "expected integer, found string"},
		{`def h(s: integer, q: integer): tuple[integer,string] do {s, "x"} end`, `s = Server.start(0, &h) r: result[integer,string] = Server.call(s, 1, 10)`, "expected result[integer,string], found result[string,string]"},
		{``, `r = Server.call(1, 1, 10)`, "requires a server"},
	}
	for _, tc := range cases {
		t.Run(tc.declarations+tc.body, func(t *testing.T) {
			_, err := Parse("defmodule Main do " + tc.declarations + " def main() do " + tc.body + " end end")
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

func TestValueBlocksAndGenericEquality(t *testing.T) {
	prefix := `def same(x: a, y: a): boolean do x == y end
 def member(xs: list[a], x: a): boolean do List.contains(xs, x) end
 def has(xs: list[list[b]], x: list[b]): boolean do member(xs, x) end
 def pinned(x: a, y: a): boolean do
  case y do
   ^x -> true
   _ -> false
  end
 end
 def double(n: integer): integer do n * 2 end
 `
	cases := []struct{ body, want string }{
		{`x = if true do 1 end`, "needs an else"},
		{`x = if true do 1 else "a" end`, "expected integer, found string"},
		{`x: string = if true do 1 else 2 end`, "expected string, found integer"},
		{`x = if true do IO.puts("a") else IO.puts("b") end`, "must end in a value"},
		{`x = case 1 do 1 -> "a" end`, "non-exhaustive"},
		{`x = case 1 do 1 -> "a" _ -> 2 end`, "expected string, found integer"},
		{`x = if true do y = 1 y else 2 end assert(y == 1)`, "undefined binding y"},
		{`f = &double assert(same(f, f))`, "same needs equality for a"},
		{`f = &double assert(has([[f]], [f]))`, "has needs equality for b"},
		{`f = &double assert(pinned(f, f))`, "pinned needs equality for a"},
		{`f = &double g: fn[fn[integer,integer], fn[integer,integer], boolean] = &same`, "same needs equality for a"},
	}
	for _, tc := range cases {
		t.Run(tc.body, func(t *testing.T) {
			_, err := Parse("defmodule Main do " + prefix + " def main() do " + tc.body + " end end")
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
	if _, err := Parse("defmodule Main do def f(n: integer): integer do x = if n > 0 do return 1 else 2 end x end def main() do assert(f(1) == 1) end end"); err == nil || !strings.Contains(err.Error(), "return cannot be used inside") {
		t.Fatalf("got %v", err)
	}
	if _, err := Parse("defmodule Main do " + prefix + " def main() do assert(same(1, 1) and has([[\"a\"]], [\"a\"]) and pinned(2.5, 2.5)) g: fn[integer, integer, boolean] = &same assert(g(1, 1)) end end"); err != nil {
		t.Fatal(err)
	}
}
