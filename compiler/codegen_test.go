package compiler

import (
	"strings"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// Nothing is compared through reflection: primitives and tuples of them use
// Go's operator, flat lists a slice comparison, and maps and nested
// collections a comparison generated for exactly that type.
func TestEqualityUsesCheapestCorrectForm(t *testing.T) {
	program, err := syntax.Parse(`defmodule Equality do
  def main() do
    n = 1
    assert(n == 1)
    assert("a" != "b")
    assert(true == true)
    case n do
      1 -> assert(true)
      ^n -> assert(true)
      _ -> assert(false)
    end
    assert([n] == [1])
    assert({n, "a"} != {2, "a"})
    assert(%{"k" => n} == %{"k" => 1})
    assert(List.contains([{1, "a"}], {n, "a"}))
    assert([[n]] == [[1]])
  end
end
`)
	if err != nil {
		t.Fatal(err)
	}
	generated := generate(program)
	body := generated[strings.Index(generated, "func main()"):]
	if strings.Contains(generated, "reflect") || strings.Contains(body, " equal(") || strings.Contains(body, "(equal(") {
		t.Fatalf("generated code still uses reflective equality:\n%s", body)
	}
	for _, want := range []string{"==int64(1))", `("a"=="b")`, "(true==true)", "slices.Equal(", "mapEqBy(", "listEqBy(", "slices.Contains(", `"a"}==struct{`} {
		if !strings.Contains(body, want) {
			t.Fatalf("missing %q in:\n%s", want, body)
		}
	}
}

// map, filter and reduce over a named function become direct-call loops; an
// anonymous function still goes through the generic helper.
func TestNamedCallbacksBecomeDirectLoops(t *testing.T) {
	program, err := syntax.Parse(`defmodule Loops do
  def double(n: integer): integer do
    return n * 2
  end
  def even(n: integer): boolean do
    return n % 2 == 0
  end
  def add(total: integer, n: integer): integer do
    return total + n
  end
  def main() do
    xs = [1, 2, 3]
    assert(map(xs, &double) == [2, 4, 6])
    assert(filter(xs, &even) == [2])
    assert(reduce(xs, 10, &add) == 16)
    assert(map(xs, fn(n: integer): integer do
      return n + 1
    end) == [2, 3, 4])
  end
end
`)
	if err != nil {
		t.Fatal(err)
	}
	generated := generate(program)
	body := generated[strings.Index(generated, "func main()"):]
	if strings.Contains(body, "listFilter(") || strings.Contains(body, "listReduce(") || strings.Count(body, "listMap(") != 1 {
		t.Fatalf("named callbacks were not expanded, or the anonymous one was:\n%s", body)
	}
	if strings.Count(body, "-- {") != 3 || !strings.Contains(body, "= f0(ctx,") || !strings.Contains(body, "if f1(ctx,") || !strings.Contains(body, "= f2(ctx,") {
		t.Fatalf("expected three inline loops calling the functions directly:\n%s", body)
	}
}

// A function that calls nothing else carries no depth tracking; one that can
// recurse, or a body that calls a function, still does.
func TestLeafFunctionsSkipCallTracking(t *testing.T) {
	program, err := syntax.Parse(`defmodule Leaves do
  def square(n: integer): integer do
    return n * n
  end
  def tail(xs: list[integer]): list[integer] do
    return List.drop(xs, 1)
  end
  def down(n: integer): integer do
    if n == 0 do
      return 0
    end
    return down(n - 1)
  end
  def apply(f: fn[integer,integer], n: integer): integer do
    return f(n)
  end
  def total(xs: list[integer]): integer do
    return reduce(xs, 0, fn(sum: integer, n: integer): integer do
      return sum + n
    end)
  end
  def main() do
    assert(square(2) == 4)
    assert(tail([1, 2]) == [2])
    assert(down(3) == 0)
    assert(apply(&square, 3) == 9)
    assert(total([1, 2]) == 3)
  end
end
`)
	if err != nil {
		t.Fatal(err)
	}
	generated := generate(program)
	bodies := strings.Split(generated[strings.Index(generated, "func f0("):], "\nfunc ")
	tracked := []bool{false, false, true, true, true}
	names := []string{"square", "tail", "down", "apply", "total"}
	for i, want := range tracked {
		has := strings.Contains(bodies[i], "actor.Enter(") && strings.Contains(bodies[i], "actor.Leave(")
		bare := !strings.Contains(bodies[i], "actor.Enter(") && !strings.Contains(bodies[i], "actor.Leave(")
		if want && !has || !want && !bare {
			t.Fatalf("%s: tracked=%v expected %v in:\n%s", names[i], has, want, bodies[i])
		}
	}
	// The anonymous accumulator inside total is itself a leaf.
	if strings.Count(bodies[4], "actor.Enter(") != 1 {
		t.Fatalf("anonymous leaf function should not be tracked:\n%s", bodies[4])
	}
}
