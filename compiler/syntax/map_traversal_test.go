package syntax

import "testing"

func TestMapTraversalTypes(t *testing.T) {
	_, err := Parse(`defmodule Maps do def main() do
  data = %{2 => "two",1 => "one"}
  keys: list[integer] = Map.keys(data)
  values: list[string] = Map.values(data)
  pairs: list[tuple[integer,string]] = Map.entries(data)
  removed: map[integer,string] = data |> Map.delete(2)
  assert(keys == [1,2] and values == ["one","two"])
 end end`)
	if err != nil {
		t.Fatal(err)
	}
}
func TestMapTraversalErrors(t *testing.T) {
	for _, body := range []string{
		`x = Map.keys([1])`, `x = Map.values(1)`, `x = Map.entries({1,true})`,
		`x = Map.keys()`, `x = Map.values(%{1 => true},1)`, `x = Map.entries()`,
		`x = Map.delete(%{1 => true},"1")`, `x = Map.delete(%{1 => true})`, `x = Map.delete([1],1)`,
		`x: list[string] = Map.keys(%{1 => true})`, `x: list[integer] = Map.values(%{1 => true})`,
		`x: list[tuple[boolean,integer]] = Map.entries(%{1 => true})`,
	} {
		t.Run(body, func(t *testing.T) {
			if _, err := Parse("defmodule X do def main() do " + body + " end end"); err == nil {
				t.Fatal("accepted invalid source")
			}
		})
	}
}
