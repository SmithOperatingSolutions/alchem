package main

import (
	"bytes"
	debugelf "debug/elf"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestInvalidIR(t *testing.T) {
	valid, err := os.ReadFile("../../fixtures/ir/return-42.json")
	if err != nil {
		t.Fatal(err)
	}
	cases := map[string]string{"malformed": "{", "trailing object": string(valid) + "{}", "trailing garbage": string(valid) + "garbage"}
	for name, instructions := range map[string]string{
		"duplicate SSA":    `[{"op":"const.i64","dest":"x","value":1},{"op":"const.i64","dest":"x","value":2}]`,
		"undefined lhs":    `[{"op":"add.i64","dest":"x","lhs":"missing","rhs":"missing"}]`,
		"undefined rhs":    `[{"op":"const.i64","dest":"x","value":1},{"op":"add.i64","dest":"y","lhs":"x","rhs":"missing"}]`,
		"undefined return": `[]`,
	} {
		cases[name] = `{"version":1,"functions":[{"name":"main","params":[],"return_type":"i64","blocks":[{"label":"entry","instructions":` + instructions + `,"terminator":{"op":"ret","value":"x"}}]}]}`
	}
	for name, input := range cases {
		t.Run(name, func(t *testing.T) {
			output, err := compile([]byte(input))
			if err == nil || !strings.Contains(err.Error(), "E_INVALID_IR") || output != nil {
				t.Fatalf("expected rejection, got %v", err)
			}
		})
	}
}

func TestELFAndDeterminism(t *testing.T) {
	for _, name := range []string{"return-42", "add-20-22", "sub-84-42", "sub-reversed", "mul-6-7", "mul-overflow"} {
		t.Run(name, func(t *testing.T) {
			input, err := os.ReadFile("../../fixtures/ir/" + name + ".json")
			if err != nil {
				t.Fatal(err)
			}
			first, err := compile(input)
			if err != nil {
				t.Fatal(err)
			}
			second, err := compile(input)
			if err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(first, second) {
				t.Fatal("nondeterministic output")
			}
			f, err := debugelf.NewFile(bytes.NewReader(first))
			if err != nil {
				t.Fatal(err)
			}
			defer f.Close()
			if f.Class != debugelf.ELFCLASS64 || f.Data != debugelf.ELFDATA2LSB || f.Type != debugelf.ET_EXEC || f.Machine != debugelf.EM_X86_64 || f.Entry != 0x401000 || len(f.Progs) != 1 {
				t.Fatalf("unexpected ELF header: %+v", f.FileHeader)
			}
			p := f.Progs[0]
			if p.Type != debugelf.PT_LOAD || p.Flags != debugelf.PF_R|debugelf.PF_X || p.Vaddr != 0x400000 || p.Filesz != uint64(len(first)) || p.Memsz != p.Filesz || p.Align != 4096 {
				t.Fatalf("unexpected load segment: %+v", p.ProgHeader)
			}
		})
	}
}

func TestCLI(t *testing.T) {
	dir := t.TempDir()
	compiler := filepath.Join(dir, "compiler")
	if output, err := exec.Command("go", "build", "-o", compiler, ".").CombinedOutput(); err != nil {
		t.Fatalf("build: %s: %v", output, err)
	}
	output := filepath.Join(dir, "program")
	args := []string{"--target", "x86_64-unknown-linux-gnu", "--input", "../../fixtures/ir/return-42.json", "--output", output}
	for name, invalid := range map[string][]string{
		"missing": {}, "unknown": {"--unknown"}, "missing flag value": {"--input"},
		"unsupported target": {"--target", "other"}, "positional": append(append([]string{}, args...), "unexpected"),
	} {
		t.Run(name, func(t *testing.T) {
			os.Remove(output)
			diagnostics, err := exec.Command(compiler, invalid...).CombinedOutput()
			if err == nil || !bytes.Contains(diagnostics, []byte("E_")) {
				t.Fatalf("expected coded rejection: %v %s", err, diagnostics)
			}
			if _, err := os.Stat(output); !os.IsNotExist(err) {
				t.Fatal("invalid invocation emitted output")
			}
		})
	}
	os.Remove(output)
	if diagnostics, err := exec.Command(compiler, args...).CombinedOutput(); err != nil {
		t.Fatalf("compile: %v %s", err, diagnostics)
	}
	info, err := os.Stat(output)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0700 {
		t.Fatalf("permissions: %v", info.Mode())
	}
}

func TestInstructionOperands(t *testing.T) {
	for name, instructions := range map[string]string{
		"fraction constant":       `[{"op":"const.i64","dest":"x","value":1.5}]`,
		"exponent constant":       `[{"op":"const.i64","dest":"x","value":1e2}]`,
		"oversized constant":      `[{"op":"const.i64","dest":"x","value":9223372036854775808}]`,
		"undersized constant":     `[{"op":"const.i64","dest":"x","value":-9223372036854775809}]`,
		"boolean constant":        `[{"op":"const.i64","dest":"x","value":true}]`,
		"string constant":         `[{"op":"const.i64","dest":"x","value":"42"}]`,
		"missing constant":        `[{"op":"const.i64","dest":"x"}]`,
		"null constant":           `[{"op":"const.i64","dest":"x","value":null}]`,
		"constant with lhs":       `[{"op":"const.i64","dest":"x","value":0,"lhs":"x"}]`,
		"constant with rhs":       `[{"op":"const.i64","dest":"x","value":0,"rhs":"x"}]`,
		"addition with immediate": `[{"op":"const.i64","dest":"x","value":0},{"op":"add.i64","dest":"y","lhs":"x","rhs":"x","value":0}]`,
	} {
		t.Run(name, func(t *testing.T) {
			input := `{"version":1,"functions":[{"name":"main","params":[],"return_type":"i64","blocks":[{"label":"entry","instructions":` + instructions + `,"terminator":{"op":"ret","value":"x"}}]}]}`
			output, err := compile([]byte(input))
			if err == nil || !strings.Contains(err.Error(), "E_INVALID_IR") || output != nil {
				t.Fatalf("expected invalid operands, got %v", err)
			}
		})
	}
}

func TestStrictJSONKeys(t *testing.T) {
	for _, name := range []string{"duplicate-root-key", "duplicate-function-key", "duplicate-block-key", "duplicate-instruction-key", "duplicate-terminator-key", "duplicate-escaped-key", "cased-root-key", "cased-function-key", "cased-block-key", "cased-terminator-key"} {
		t.Run(name, func(t *testing.T) {
			input, err := os.ReadFile("../../fixtures/ir/invalid-" + name + ".json")
			if err != nil {
				t.Fatal(err)
			}
			output, err := compile(input)
			if err == nil || !strings.Contains(err.Error(), "E_INVALID_IR") || output != nil {
				t.Fatalf("expected strict key rejection, got %v", err)
			}
		})
	}
}

func TestVersion2Functions(t *testing.T) {
	for _, name := range []string{"identity", "forward-zero-args", "six-args", "preserves-values", "nested", "argument-order"} {
		t.Run(name, func(t *testing.T) {
			input, err := os.ReadFile("../../fixtures/ir/v2-call-" + name + ".json")
			if err != nil {
				t.Fatal(err)
			}
			first, err := compile(input)
			if err != nil {
				t.Fatal(err)
			}
			second, err := compile(input)
			if err != nil || !bytes.Equal(first, second) {
				t.Fatal("nondeterministic v2 output")
			}
		})
	}
}

func TestVersion2CallDepth(t *testing.T) {
	for _, helpers := range []int{63, 64} {
		functions := []map[string]any{}
		// Reverse dependency order exercises memoized height, not just DFS depth.
		for i := helpers - 1; i >= -1; i-- {
			name := fmt.Sprintf("f%d", i)
			if i == -1 {
				name = "main"
			}
			instruction := map[string]any{"op": "const.i64", "dest": "r", "value": 42}
			if i < helpers-1 {
				instruction = map[string]any{"op": "call", "dest": "r", "callee": fmt.Sprintf("f%d", i+1), "args": []string{}}
			}
			block := map[string]any{"label": "entry", "instructions": []any{instruction}, "terminator": map[string]string{"op": "ret", "value": "r"}}
			functions = append(functions, map[string]any{"name": name, "params": []any{}, "return_type": "i64", "blocks": []any{block}})
		}
		input, err := json.Marshal(map[string]any{"version": 2, "functions": functions})
		if err != nil {
			t.Fatal(err)
		}
		_, err = compile(input)
		if helpers == 63 && err != nil {
			t.Fatal(err)
		}
		if helpers == 64 && (err == nil || !strings.Contains(err.Error(), "E_UNSUPPORTED")) {
			t.Fatalf("expected depth rejection, got %v", err)
		}
	}
}

func TestVersion3Conditionals(t *testing.T) {
	input, err := os.ReadFile("../../fixtures/ir/v3-private-yields.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = compile(input); err != nil {
		t.Fatal(err)
	}
}

func TestVersion3NestingLimit(t *testing.T) {
	for _, depth := range []int{16, 17} {
		branch := map[string]any{"instructions": []any{map[string]any{"op": "const.i64", "dest": "leaf", "value": 42}}, "value": "leaf"}
		for i := 1; i <= depth; i++ {
			dest := fmt.Sprintf("r%d", i)
			other := fmt.Sprintf("n%d", i)
			instruction := map[string]any{"op": "if.i64", "dest": dest, "cond": "flag", "then": branch, "else": map[string]any{"instructions": []any{map[string]any{"op": "const.i64", "dest": other, "value": 7}}, "value": other}}
			branch = map[string]any{"instructions": []any{instruction}, "value": dest}
		}
		instructions := []any{map[string]any{"op": "const.bool", "dest": "flag", "value": true}}
		instructions = append(instructions, branch["instructions"].([]any)...)
		block := map[string]any{"label": "entry", "instructions": instructions, "terminator": map[string]any{"op": "ret", "value": branch["value"]}}
		input, err := json.Marshal(map[string]any{"version": 3, "functions": []any{map[string]any{"name": "main", "params": []any{}, "return_type": "i64", "blocks": []any{block}}}})
		if err != nil {
			t.Fatal(err)
		}
		_, err = compile(input)
		if depth == 16 && err != nil {
			t.Fatal(err)
		}
		if depth == 17 && (err == nil || !strings.Contains(err.Error(), "E_UNSUPPORTED")) {
			t.Fatalf("expected nesting rejection, got %v", err)
		}
	}
}

func TestVersion4RecursionCompiles(t *testing.T) {
	input, err := os.ReadFile("../../fixtures/ir/v4-infinite.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := compile(input); err != nil {
		t.Fatal(err)
	}
}

func TestVersion5BytesCompile(t *testing.T) {
	input, err := os.ReadFile("../../fixtures/ir/v5-parameter.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := compile(input); err != nil {
		t.Fatal(err)
	}
}

func TestVersion6CheckedStatus(t *testing.T) {
	input, err := os.ReadFile("../../fixtures/ir/v6-status-256.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := compile(input); err != nil {
		t.Fatal(err)
	}
}

func TestVersion7Output(t *testing.T) {
	input, err := os.ReadFile("../../fixtures/ir/v7-stdout.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := compile(input); err != nil {
		t.Fatal(err)
	}
}

func TestVersion8Construction(t *testing.T) {
	input, err := os.ReadFile("../../fixtures/ir/v8-byte-return.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := compile(input); err != nil {
		t.Fatal(err)
	}
}

func TestVersion9Packing(t *testing.T) {
	input, err := os.ReadFile("../../fixtures/ir/v9-pack-ordered.json")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := compile(input); err != nil {
		t.Fatal(err)
	}
}
