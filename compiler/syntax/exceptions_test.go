package syntax

import (
	"strings"
	"testing"
)

func TestExceptionErrors(t *testing.T) {
	prefix := `defexception Missing do message: string id: integer end
 struct Point do x: integer end
 `
	cases := []struct{ declarations, body, want string }{
		{`defexception Bare do id: integer end`, `assert(true)`, "an exception has a message: string field"},
		{``, `raise(%Point{x: 1})`, "raise takes a message or an exception"},
		{``, `v = try do 1 rescue e in Point -> 2 end`, "Point is not an exception"},
		{``, `v = try do 1 rescue %Point{x: x} -> x end`, "Point is not an exception"},
		{``, `v = try do 1 rescue n: integer -> n end`, "name: type is for catch"},
		{``, `v = try do 1 catch n -> n end`, "type of the thrown value is unknown"},
		{``, `v = try do
  if true do throw(1) else throw("a") end
catch
  n -> 0
end`, "throws both integer and string"},
		{``, `v = try do 1 rescue e in Missing -> e.name end`, "no field name"},
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

func TestExceptionsAccepted(t *testing.T) {
	source := `defmodule Main do
  defexception Missing do
    message: string
    id: integer
  end

  def main() do
    a = try do
      raise(%Missing{message: "m", id: 1})
    rescue
      e in Missing -> e.id
      %Missing{id: id} when id > 5 -> id
      _ -> 0
    end
    b = try do
      throw({1, "x"})
    catch
      {n, _} -> n
    end
    c = try do
      a + b
    rescue
      _ -> "failed"
    else
      0 -> "zero"
      n -> to_string(n)
    end
    IO.puts(c)
  end
end`
	if _, err := Parse(source); err != nil {
		t.Fatal(err)
	}
}
