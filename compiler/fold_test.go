package compiler

import (
	"strings"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// A reduce owns its map only when its function cannot let an older version
// be seen: it reads the accumulator, returns it or one put to it, and makes
// no function that mentions it.
func TestFoldsThatMayOwnTheirMap(t *testing.T) {
	cases := []struct {
		name, fold string
		owned      bool
	}{
		{"put", `Enum.reduce(xs, start, fn x, acc -> Map.put(acc, x, x) end)`, true},
		{"read then put", `Enum.reduce(xs, start, fn x, acc -> Map.put(acc, x, Map.get(acc, x, 0) + map_size(acc)) end)`, true},
		{"update", `Enum.reduce(xs, start, fn x, acc -> Map.update(acc, x, 1, fn n -> n + 1 end) end)`, true},
		{"branches", `Enum.reduce(xs, start, fn x, acc ->
      if Map.has_key?(acc, x) do
        acc
      else
        Map.put_new(acc, x, 1)
      end
    end)`, true},
		{"bound first", `Enum.reduce(xs, start, fn x, acc ->
      old = Map.get(acc, x, 0)
      Map.put(acc, x, old + 1)
    end)`, true},
		{"named function", `reduce(xs, start, &bump)`, true},
		{"no put", `Enum.reduce(xs, start, fn x, acc -> if x > 0, do: acc, else: acc end)`, false},
		{"two puts", `Enum.reduce(xs, start, fn x, acc -> Map.put(Map.put(acc, x, 1), x + 1, 2) end)`, false},
		{"put bound then used", `Enum.reduce(xs, start, fn x, acc ->
      next = Map.put(acc, x, 1)
      Map.put(next, x + 1, map_size(acc))
    end)`, false},
		{"passed on", `Enum.reduce(xs, start, fn x, acc -> Map.put(keep(acc), x, 1) end)`, false},
		{"merged", `Enum.reduce(xs, start, fn x, acc -> Map.merge(acc, %{x => 1}) end)`, false},
		{"deleted", `Enum.reduce(xs, start, fn x, acc -> Map.delete(acc, x) end)`, false},
		{"in a function", `Enum.reduce(xs, start, fn x, acc -> Map.update(acc, x, 1, fn n -> n + map_size(acc) end) end)`, false},
		{"in the value", `Enum.reduce(xs, start, fn x, acc -> Map.put(acc, x, Enum.sum(Map.values(acc))) end)`, false},
		{"another map", `Enum.reduce(xs, 0, fn x, acc -> acc + map_size(Map.put(start, x, 1)) end)`, false},
	}
	for _, c := range cases {
		program, err := syntax.Parse(`defmodule Folds do
  def bump(counts: map[integer, integer], x: integer): map[integer, integer] do
    put(counts, x, get(counts, x, 0) + 1)
  end

  def keep(m: map[integer, integer]): map[integer, integer] do
    m
  end

  def main() do
    xs = [1, 2, 3]
    start: map[integer, integer] = %{}
    IO.inspect(` + c.fold + `)
  end
end
`)
		if err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		generated := generate(program)
		if owned := strings.Contains(generated, "actor.MapOwned("); owned != c.owned {
			t.Errorf("%s: owned=%v, want %v", c.name, owned, c.owned)
		}
		if strings.Count(generated, "actor.MapOwned(") != strings.Count(generated, "actor.MapShared(") {
			t.Errorf("%s: a fold that owns its map does not hand it back", c.name)
		}
	}
}

// A call to itself in return position becomes a jump, and only there.
func TestSelfTailCallsBecomeLoops(t *testing.T) {
	program, err := syntax.Parse(`defmodule Tails do
  def down(n: integer, total: integer): integer do
    if n == 0 do
      total
    else
      down(n - 1, total + n)
    end
  end

  def sum(n: integer): integer do
    if n == 0 do
      0
    else
      n + sum(n - 1)
    end
  end

  def later(n: integer): fn[integer] do
    fn -> later(n).() end
  end

  def main() do
    IO.inspect(down(3, 0) + sum(3) + later(1).())
  end
end
`)
	if err != nil {
		t.Fatal(err)
	}
	generated := generate(program)
	if got := strings.Count(generated, "continue tail"); got != 1 {
		t.Fatalf("%d tail jumps, want 1 (in down):\n%s", got, generated)
	}
}
