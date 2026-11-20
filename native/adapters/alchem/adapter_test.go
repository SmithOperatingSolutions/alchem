package main

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
)

func TestLowerIntegerFunction(t *testing.T) {
	for _, expression := range []string{"42", "20 + 22", "(1 + 19) + 22", "-1", "9223372036854775807 + 1", "84 - 42", "6 * 7", "(100 - 16) * 2 - 126"} {
		source := "defmodule Native do def answer(): integer do " + expression + " end end"
		output, err := lower(source, "answer")
		if err != nil {
			t.Fatal(err)
		}
		var p map[string]any
		if err := json.Unmarshal(output, &p); err != nil {
			t.Fatal(err)
		}
		if p["version"] != float64(1) {
			t.Fatalf("wrong version: %s", output)
		}
	}
}

func TestRejectsSourceOutsidePureIntegerSubset(t *testing.T) {
	for name, source := range map[string]string{
		"malformed":     "defmodule",
		"type error":    `defmodule Native do def answer(): integer do "hello" end end`,
		"divide":        `defmodule Native do def answer(): integer do 20 / 2 end end`,
		"parameters":    `defmodule Native do def answer(x: integer): integer do x end end`,
		"wrong entry":   `defmodule Native do def other(): integer do 42 end end`,
		"string helper": `defmodule Native do def answer(): integer do 42 end def other(): string do "x" end end`,
		"case":          `defmodule Native do def answer(): integer do case 1 do 1 -> 42 _ -> 0 end end end`,
	} {
		t.Run(name, func(t *testing.T) {
			output, err := lower(source, "answer")
			if err == nil || output != nil || !strings.Contains(err.Error(), "E_") {
				t.Fatalf("expected coded rejection, got %s %v", output, err)
			}
		})
	}
}

func TestCLIArgumentsAndFailures(t *testing.T) {
	for _, args := range [][]string{nil, {"--unknown"}, {"--input"}, {"--input", "unused", "--function", "answer", "positional"}} {
		var out strings.Builder
		if err := run(args, &out); err == nil || !strings.Contains(err.Error(), "E_INVALID_ARGUMENT") || out.Len() != 0 {
			t.Fatalf("args %v: output %s error %v", args, out.String(), err)
		}
	}
}

func TestLowerExecutableMain(t *testing.T) {
	for name, body := range map[string]string{
		"invoice":                "subtotal = 12 * 5\ndiscount = 18\ntotal = subtotal - discount\nSystem.halt(total)",
		"alias":                  "x = 42\ny = x\nSystem.halt(y)",
		"zero":                   "x = 42", // A normal void main exits zero.
		"negative intermediates": "x = 1 - 7\nSystem.halt(x * -7)",
	} {
		t.Run(name, func(t *testing.T) {
			output, err := lower("defmodule Native do def main() do\n"+body+"\nend end", "")
			if err != nil {
				t.Fatal(err)
			}
			if !json.Valid(output) {
				t.Fatalf("invalid IR: %s", output)
			}
		})
	}
}

func TestRejectsUnsupportedExecutableBehavior(t *testing.T) {
	for name, body := range map[string]string{

		"after halt":          "System.halt(0)\nx = 42",
		"interpolated output": "IO.puts(\"value #{42}\")",
		"undefined variable":  "System.halt(missing)",
		"duplicate variable":  "x = 1\nx = 42\nSystem.halt(x)",
	} {
		t.Run(name, func(t *testing.T) {
			output, err := lower("defmodule Native do def main() do\n"+body+"\nend end", "")
			if err == nil || output != nil {
				t.Fatalf("accepted unsupported behavior: %s", output)
			}
		})
	}
}

func TestLowerFunctionCalls(t *testing.T) {
	source := `defmodule Native do
 def inc(x: integer): integer do x + 1 end
 def twice(x: integer): integer do inc(inc(x)) end
 def main() do
  result = twice(40)
  System.halt(result)
 end end`
	output, err := lower(source, "")
	if err != nil {
		t.Fatal(err)
	}
	var p map[string]any
	if err := json.Unmarshal(output, &p); err != nil {
		t.Fatal(err)
	}
	if p["version"] != float64(6) {
		t.Fatalf("expected runtime-checked executable IR: %s", output)
	}
}

func TestMainDoesNotExecuteStatusProof(t *testing.T) {
	var source strings.Builder
	source.WriteString("defmodule Budget do\n")
	for i := 0; i < 19; i++ {
		fmt.Fprintf(&source, "def f%d(x: integer): integer do f%d(x) + f%d(x) end\n", i, i+1, i+1)
	}
	source.WriteString("def f19(x: integer): integer do x end\ndef main() do System.halt(f0(0)) end\nend")
	output, err := lower(source.String(), "")
	if err != nil {
		t.Fatalf("status proof must not execute calls: %v", err)
	}
	var p map[string]any
	if err := json.Unmarshal(output, &p); err != nil {
		t.Fatal(err)
	}
	if p["version"] != float64(6) {
		t.Fatalf("expected checked runtime entry: %s", output)
	}
	if strings.Count(string(output), `"op": "call"`) != 39 {
		t.Fatalf("native calls were lost: %s", output)
	}
}

func TestLowerConditionalValues(t *testing.T) {
	for _, body := range []string{
		"amount = if 1 < 2 do 42 else 7 end\nSystem.halt(amount)",
		"flag = if 1 < 2 do true else false end\nif not flag do System.halt(7) else System.halt(42) end",
	} {
		source := "defmodule Native do def main() do\n" + body + "\nend end"
		output, err := lower(source, "")
		if err != nil {
			t.Fatal(err)
		}
		var p map[string]any
		if err := json.Unmarshal(output, &p); err != nil {
			t.Fatal(err)
		}
		if p["version"] != float64(6) {
			t.Fatalf("expected runtime-checked conditional IR: %s", output)
		}
	}
}

func TestLowerBoundedRecursion(t *testing.T) {
	source := `defmodule Sum do
 def sum(n: integer): integer do if n <= 0 do 0 else n + sum(n-1) end end
 def main() do System.halt(sum(8)+6) end end`
	output, err := lower(source, "")
	if err != nil {
		t.Fatal(err)
	}
	var p map[string]any
	if err := json.Unmarshal(output, &p); err != nil {
		t.Fatal(err)
	}
	if p["version"] != float64(6) {
		t.Fatalf("expected runtime-checked recursive profile: %s", output)
	}
}

func TestLowerByteBuffers(t *testing.T) {
	source := `defmodule Bytes do
 def read(values: list[integer], index: integer): integer do Enum.at(values, index, 7) end
 def main() do values = [0, 42, 255]
 System.halt(read(values, -2)) end end`
	output, err := lower(source, "")
	if err != nil {
		t.Fatal(err)
	}
	var p map[string]any
	if err := json.Unmarshal(output, &p); err != nil {
		t.Fatal(err)
	}
	if p["version"] != float64(6) {
		t.Fatalf("expected byte-buffer profile: %s", output)
	}
}

func TestInvalidStatusLowersToRuntimeCheck(t *testing.T) {
	for _, value := range []string{"-1", "256", "-9223372036854775808", "9223372036854775807"} {
		output, err := lower("defmodule Status do def main() do System.halt("+value+") end end", "")
		if err != nil {
			t.Fatal(err)
		}
		var p map[string]any
		if err := json.Unmarshal(output, &p); err != nil {
			t.Fatal(err)
		}
		if p["version"] != float64(6) {
			t.Fatalf("expected v6: %s", output)
		}
	}
}

func TestLowerLiteralOutput(t *testing.T) {
	output, err := lower(`defmodule Hello do def main() do IO.puts("hello") end end`, "")
	if err != nil {
		t.Fatal(err)
	}
	var p map[string]any
	if err := json.Unmarshal(output, &p); err != nil {
		t.Fatal(err)
	}
	if p["version"] != float64(7) || !strings.Contains(string(output), `"op": "bytes.write"`) {
		t.Fatalf("expected native output: %s", output)
	}
}

func TestLowerRuntimeConstruction(t *testing.T) {
	source := `defmodule Join do def join(a: list[integer], b: list[integer]): list[integer] do Enum.concat(a,b) end def main() do values = join([20], [22])
 System.halt(Enum.at(values,0,0)+Enum.at(values,1,0)) end end`
	output, err := lower(source, "")
	if err != nil {
		t.Fatal(err)
	}
	var p map[string]any
	if err := json.Unmarshal(output, &p); err != nil {
		t.Fatal(err)
	}
	if p["version"] != float64(8) {
		t.Fatalf("expected V8: %s", output)
	}
}

func TestConstructionRemainsProgramOnly(t *testing.T) {
	source := `defmodule Join do def answer(): integer do Enum.count(Enum.concat([1],[2])) end end`
	output, err := lower(source, "answer")
	if err == nil || output != nil || !strings.Contains(err.Error(), "program mode") {
		t.Fatalf("expected explicit profile rejection: %s %v", output, err)
	}
}

func TestLowerComputedBytes(t *testing.T) {
	output, err := lower(`defmodule Pack do def data(x: integer): list[integer] do [x, 22] end def main() do values=data(20)
 System.halt(Enum.at(values,0,0)+Enum.at(values,1,0)) end end`, "")
	if err != nil {
		t.Fatal(err)
	}
	var p map[string]any
	if err := json.Unmarshal(output, &p); err != nil {
		t.Fatal(err)
	}
	if p["version"] != float64(9) || !strings.Contains(string(output), `"op": "bytes.pack"`) {
		t.Fatalf("expected checked packing: %s", output)
	}
}

func TestComputedPackLimitPreservesLiteralLists(t *testing.T) {
	for _, computed := range []bool{false, true} {
		element := "1"
		if computed {
			element = "x"
		}
		source := "defmodule Pack do def main() do x=1\n values=[" + strings.Repeat(element+",", 4096) + element + "]\n System.halt(0) end end"
		output, err := lower(source, "")
		if computed {
			if err == nil || output != nil || !strings.Contains(err.Error(), "4096") {
				t.Fatalf("expected computed cap: %v", err)
			}
		} else if err != nil {
			t.Fatalf("literal list incorrectly capped: %v", err)
		}
	}
}
