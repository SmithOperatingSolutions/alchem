package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

type instruction struct {
	Op     string   `json:"op"`
	Dest   string   `json:"dest"`
	Value  int64    `json:"value"`
	LHS    string   `json:"lhs"`
	RHS    string   `json:"rhs"`
	Callee string   `json:"callee"`
	Args   []string `json:"args"`
}

// UnmarshalJSON validates the opcode-specific operand shape before lowering.
func (in *instruction) UnmarshalJSON(data []byte) error {
	type plain instruction
	var decoded plain
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if err := d.Decode(&decoded); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	required := []string{"op", "dest"}
	switch decoded.Op {
	case "const.i64":
		required = append(required, "value")
	case "call":
		required = append(required, "callee", "args")
	case "add.i64", "sub.i64", "mul.i64":
		required = append(required, "lhs", "rhs")
	default:
		*in = instruction(decoded)
		return nil // The compiler reports E_UNKNOWN_OPCODE.
	}
	allowed := map[string]bool{}
	for _, key := range required {
		allowed[key] = true
		value, exists := fields[key]
		if !exists || bytes.Equal(bytes.TrimSpace(value), []byte("null")) {
			return fmt.Errorf("%s requires non-null %s", decoded.Op, key)
		}
	}
	for key := range fields {
		if !allowed[key] {
			return fmt.Errorf("%s does not accept %s", decoded.Op, key)
		}
	}
	*in = instruction(decoded)
	return nil
}

type block struct {
	Label        string        `json:"label"`
	Instructions []instruction `json:"instructions"`
	Terminator   struct {
		Op    string `json:"op"`
		Value string `json:"value"`
	} `json:"terminator"`
}
type function struct {
	Name       string            `json:"name"`
	Params     []json.RawMessage `json:"params"`
	ReturnType string            `json:"return_type"`
	Blocks     []block           `json:"blocks"`
}
type program struct {
	Version   int        `json:"version"`
	Functions []function `json:"functions"`
}

func fail(code, msg string) error     { return fmt.Errorf("%s: %s", code, msg) }
func imm32(code *bytes.Buffer, x int) { _ = binary.Write(code, binary.LittleEndian, uint32(x)) }
func slotLoad(code *bytes.Buffer, reg byte, offset int) {
	code.Write([]byte{0x48, 0x8b, 0x84 | (reg << 3), 0x24})
	imm32(code, offset)
}
func slotStore(code *bytes.Buffer, offset int) {
	code.Write([]byte{0x48, 0x89, 0x84, 0x24})
	imm32(code, offset)
}
func compile(input []byte) ([]byte, error) {
	if err := validateJSONKeys(input); err != nil {
		return nil, fail("E_INVALID_IR", err.Error())
	}
	var version struct {
		Version int `json:"version"`
	}
	if err := json.Unmarshal(input, &version); err != nil {
		return nil, fail("E_INVALID_IR", err.Error())
	}
	if version.Version == 3 || version.Version == 4 || version.Version == 5 || version.Version == 6 || version.Version == 7 || version.Version == 8 || version.Version == 9 || version.Version == 10 || version.Version == 11 {
		return compileFlow(input)
	}
	var p program
	d := json.NewDecoder(bytes.NewReader(input))
	d.DisallowUnknownFields()
	if err := d.Decode(&p); err != nil {
		return nil, fail("E_INVALID_IR", err.Error())
	}
	var extra any
	if err := d.Decode(&extra); err != io.EOF {
		return nil, fail("E_INVALID_IR", "expected exactly one JSON document")
	}
	if p.Version == 2 {
		return compileFunctions(p)
	}
	if p.Version != 1 || len(p.Functions) != 1 {
		return nil, fail("E_INVALID_IR", "expected version 1 with exactly one function")
	}
	f := p.Functions[0]
	if f.Name != "main" || f.ReturnType != "i64" || len(f.Params) != 0 || len(f.Blocks) != 1 || f.Blocks[0].Label != "entry" {
		return nil, fail("E_UNSUPPORTED", "only parameterless main returning i64 with one entry block is supported")
	}
	b := f.Blocks[0]
	slots := map[string]int{}
	for _, in := range b.Instructions {
		switch in.Op {
		case "const.i64", "add.i64", "sub.i64", "mul.i64":
		default:
			return nil, fail("E_UNKNOWN_OPCODE", in.Op)
		}
		if in.Dest == "" {
			return nil, fail("E_INVALID_IR", "missing destination")
		}
		if _, exists := slots[in.Dest]; exists {
			return nil, fail("E_INVALID_IR", "duplicate SSA destination")
		}
		if in.Op != "const.i64" {
			if _, ok := slots[in.LHS]; !ok {
				return nil, fail("E_INVALID_IR", "undefined lhs")
			}
			if _, ok := slots[in.RHS]; !ok {
				return nil, fail("E_INVALID_IR", "undefined rhs")
			}
		}
		slots[in.Dest] = len(slots) * 8
	}
	if b.Terminator.Op != "ret" {
		return nil, fail("E_UNSUPPORTED", "only ret terminator supported")
	}
	retOffset, ok := slots[b.Terminator.Value]
	if !ok {
		return nil, fail("E_INVALID_IR", "undefined return value")
	}
	stackSize := ((len(slots)*8 + 15) / 16) * 16
	if stackSize > 1<<20 {
		return nil, fail("E_UNSUPPORTED", "too many IR values")
	}
	code := new(bytes.Buffer)
	code.Write([]byte{0x48, 0x81, 0xec})
	imm32(code, stackSize)
	seen := map[string]int{}
	for _, in := range b.Instructions {
		switch in.Op {
		case "const.i64":
			code.Write([]byte{0x48, 0xb8})
			_ = binary.Write(code, binary.LittleEndian, in.Value)
		case "add.i64", "sub.i64", "mul.i64":
			slotLoad(code, 0, seen[in.LHS])
			slotLoad(code, 3, seen[in.RHS])
			switch in.Op {
			case "add.i64":
				code.Write([]byte{0x48, 0x01, 0xd8})
			case "sub.i64":
				code.Write([]byte{0x48, 0x29, 0xd8})
			case "mul.i64":
				code.Write([]byte{0x48, 0x0f, 0xaf, 0xc3})
			}
		}
		slotStore(code, slots[in.Dest])
		seen[in.Dest] = slots[in.Dest]
	}
	slotLoad(code, 7, retOffset)
	code.Write([]byte{0xb8, 0x3c, 0, 0, 0, 0x0f, 0x05})
	return elf(code.Bytes()), nil
}
func elf(code []byte) []byte {
	const base = uint64(0x400000)
	const start = uint64(0x1000)
	total := int(start) + len(code)
	out := make([]byte, total)
	copy(out, []byte{0x7f, 'E', 'L', 'F', 2, 1, 1})
	binary.LittleEndian.PutUint16(out[16:], 2)
	binary.LittleEndian.PutUint16(out[18:], 62)
	binary.LittleEndian.PutUint32(out[20:], 1)
	binary.LittleEndian.PutUint64(out[24:], base+start)
	binary.LittleEndian.PutUint64(out[32:], 64)
	binary.LittleEndian.PutUint16(out[52:], 64)
	binary.LittleEndian.PutUint16(out[54:], 56)
	binary.LittleEndian.PutUint16(out[56:], 1)
	ph := out[64:120]
	binary.LittleEndian.PutUint32(ph[0:], 1)
	binary.LittleEndian.PutUint32(ph[4:], 5)
	binary.LittleEndian.PutUint64(ph[16:], base)
	binary.LittleEndian.PutUint64(ph[32:], uint64(total))
	binary.LittleEndian.PutUint64(ph[40:], uint64(total))
	binary.LittleEndian.PutUint64(ph[48:], 0x1000)
	copy(out[start:], code)
	return out
}
func run() error {
	flags := flag.NewFlagSet("alchem-native", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	target := flags.String("target", "", "target triple")
	input := flags.String("input", "", "input IR JSON")
	output := flags.String("output", "", "output ELF path")
	if err := flags.Parse(os.Args[1:]); err != nil {
		return fail("E_INVALID_ARGUMENT", err.Error())
	}
	if flags.NArg() != 0 {
		return fail("E_INVALID_ARGUMENT", "unexpected positional arguments")
	}
	if *target != "x86_64-unknown-linux-gnu" {
		return fail("E_UNSUPPORTED", "target must be x86_64-unknown-linux-gnu")
	}
	if *input == "" || *output == "" {
		return fail("E_INVALID_ARGUMENT", "input and output are required")
	}
	data, err := os.ReadFile(*input)
	if err != nil {
		return fail("E_IO", err.Error())
	}
	binaryData, err := compile(data)
	if err != nil {
		return err
	}
	temp, err := os.CreateTemp(filepath.Dir(*output), ".alchem-native-*")
	if err != nil {
		return fail("E_IO", err.Error())
	}
	defer os.Remove(temp.Name())
	if _, err = temp.Write(binaryData); err != nil {
		temp.Close()
		return fail("E_IO", err.Error())
	}
	if err = temp.Chmod(0700); err != nil {
		temp.Close()
		return fail("E_IO", err.Error())
	}
	if err = temp.Close(); err != nil {
		return fail("E_IO", err.Error())
	}
	if err = os.Rename(temp.Name(), *output); err != nil {
		return fail("E_IO", err.Error())
	}
	return nil
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
