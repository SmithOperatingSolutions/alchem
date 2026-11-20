package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
)

type parameter struct {
	Name string `json:"name"`
	Type string `json:"type"`
}
type callable struct {
	function function
	params   []parameter
	slots    map[string]int
	frame    int
	ret      int
	edges    []int
}
type relocation struct {
	offset int
	callee int
}

var argumentRegisters = []byte{7, 6, 2, 1, 8, 9}

func compileFunctions(p program) ([]byte, error) {
	if len(p.Functions) == 0 {
		return nil, fail("E_INVALID_IR", "missing functions")
	}
	if len(p.Functions) > 256 {
		return nil, fail("E_UNSUPPORTED", "too many functions")
	}
	names := map[string]int{}
	functions := make([]callable, len(p.Functions))
	for i, f := range p.Functions {
		if f.Name == "" {
			return nil, fail("E_INVALID_IR", "missing function name")
		}
		if _, ok := names[f.Name]; ok {
			return nil, fail("E_INVALID_IR", "duplicate function")
		}
		names[f.Name] = i
		if f.ReturnType != "i64" || len(f.Blocks) != 1 || f.Blocks[0].Label != "entry" {
			return nil, fail("E_UNSUPPORTED", "expected i64 function with one entry block")
		}
		if f.Params == nil {
			return nil, fail("E_INVALID_IR", "params must be an array")
		}
		if len(f.Params) > 6 {
			return nil, fail("E_UNSUPPORTED", "at most six integer parameters")
		}
		c := callable{function: f, slots: map[string]int{}}
		for _, raw := range f.Params {
			var fields map[string]json.RawMessage
			if err := json.Unmarshal(raw, &fields); err != nil {
				return nil, fail("E_INVALID_IR", err.Error())
			}
			for _, key := range []string{"name", "type"} {
				value, ok := fields[key]
				if !ok || bytes.Equal(bytes.TrimSpace(value), []byte("null")) {
					return nil, fail("E_INVALID_IR", "parameter fields must be present and non-null")
				}
			}
			var param parameter
			d := json.NewDecoder(bytes.NewReader(raw))
			d.DisallowUnknownFields()
			if err := d.Decode(&param); err != nil {
				return nil, fail("E_INVALID_IR", err.Error())
			}
			if param.Name == "" {
				return nil, fail("E_INVALID_IR", "missing parameter name")
			}
			if _, ok := c.slots[param.Name]; ok {
				return nil, fail("E_INVALID_IR", "duplicate parameter")
			}
			if param.Type != "i64" {
				return nil, fail("E_UNSUPPORTED", "only i64 parameters are supported")
			}
			c.slots[param.Name] = len(c.params) * 8
			c.params = append(c.params, param)
		}
		functions[i] = c
	}
	main, ok := names["main"]
	if !ok {
		return nil, fail("E_INVALID_IR", "missing main")
	}
	if len(functions[main].params) != 0 {
		return nil, fail("E_INVALID_IR", "main must have no parameters")
	}
	for i := range functions {
		c := &functions[i]
		b := c.function.Blocks[0]
		if b.Instructions == nil {
			return nil, fail("E_INVALID_IR", "instructions must be an array")
		}
		for _, in := range b.Instructions {
			switch in.Op {
			case "const.i64", "add.i64", "sub.i64", "mul.i64", "call":
			default:
				return nil, fail("E_UNKNOWN_OPCODE", in.Op)
			}
			if in.Dest == "" {
				return nil, fail("E_INVALID_IR", "missing destination")
			}
			if _, ok := c.slots[in.Dest]; ok {
				return nil, fail("E_INVALID_IR", "duplicate SSA destination")
			}
			switch in.Op {
			case "call":
				target, ok := names[in.Callee]
				if !ok {
					return nil, fail("E_INVALID_IR", "undefined callee")
				}
				if len(in.Args) != len(functions[target].params) {
					return nil, fail("E_INVALID_IR", "call arity mismatch")
				}
				for _, arg := range in.Args {
					if _, ok := c.slots[arg]; !ok {
						return nil, fail("E_INVALID_IR", "undefined call argument")
					}
				}
				c.edges = append(c.edges, target)
			case "add.i64", "sub.i64", "mul.i64":
				if _, ok := c.slots[in.LHS]; !ok {
					return nil, fail("E_INVALID_IR", "undefined lhs")
				}
				if _, ok := c.slots[in.RHS]; !ok {
					return nil, fail("E_INVALID_IR", "undefined rhs")
				}
			}
			c.slots[in.Dest] = len(c.slots) * 8
		}
		if b.Terminator.Op != "ret" {
			return nil, fail("E_UNSUPPORTED", "only ret terminators")
		}
		ret, ok := c.slots[b.Terminator.Value]
		if !ok {
			return nil, fail("E_INVALID_IR", "undefined return value")
		}
		c.ret = ret
		c.frame = (len(c.slots)*8 + 15) & ^15
		if c.frame > 1<<20 {
			return nil, fail("E_UNSUPPORTED", "too many IR values")
		}
	}
	// Memoize path height, rather than visit order, so shared callees do not hide
	// a longer path discovered after their first visit.
	active := make([]bool, len(functions))
	heights := make([]int, len(functions))
	var height func(int) (int, error)
	height = func(i int) (int, error) {
		if active[i] {
			return 0, fail("E_UNSUPPORTED", "recursive call graph")
		}
		if heights[i] != 0 {
			return heights[i], nil
		}
		active[i] = true
		h := 1
		for _, target := range functions[i].edges {
			child, err := height(target)
			if err != nil {
				return 0, err
			}
			if child+1 > h {
				h = child + 1
			}
		}
		active[i] = false
		if h > 64 {
			return 0, fail("E_UNSUPPORTED", "call depth exceeds 64")
		}
		heights[i] = h
		return h, nil
	}
	for i := range functions {
		if _, err := height(i); err != nil {
			return nil, err
		}
	}
	code := new(bytes.Buffer)
	code.WriteByte(0xe8)
	imm32(code, 0)
	patches := []relocation{{1, main}}
	code.Write([]byte{0x48, 0x89, 0xc7, 0xb8, 0x3c, 0, 0, 0, 0x0f, 0x05})
	starts := make([]int, len(functions))
	for i, c := range functions {
		starts[i] = code.Len()
		code.Write([]byte{0x55, 0x48, 0x89, 0xe5, 0x48, 0x81, 0xec})
		imm32(code, c.frame)
		for j, param := range c.params {
			functionSlot(code, 0x89, argumentRegisters[j], c.slots[param.Name])
		}
		for _, in := range c.function.Blocks[0].Instructions {
			switch in.Op {
			case "const.i64":
				code.Write([]byte{0x48, 0xb8})
				_ = binary.Write(code, binary.LittleEndian, in.Value)
			case "call":
				for j, arg := range in.Args {
					functionSlot(code, 0x8b, argumentRegisters[j], c.slots[arg])
				}
				code.WriteByte(0xe8)
				patches = append(patches, relocation{code.Len(), names[in.Callee]})
				imm32(code, 0)
			default:
				functionSlot(code, 0x8b, 0, c.slots[in.LHS])
				functionSlot(code, 0x8b, 1, c.slots[in.RHS])
				switch in.Op {
				case "add.i64":
					code.Write([]byte{0x48, 0x01, 0xc8})
				case "sub.i64":
					code.Write([]byte{0x48, 0x29, 0xc8})
				case "mul.i64":
					code.Write([]byte{0x48, 0x0f, 0xaf, 0xc1})
				}
			}
			functionSlot(code, 0x89, 0, c.slots[in.Dest])
		}
		functionSlot(code, 0x8b, 0, c.ret)
		code.Write([]byte{0xc9, 0xc3})
	}
	for _, patch := range patches {
		displacement := int64(starts[patch.callee]) - int64(patch.offset+4)
		if displacement < -1<<31 || displacement > 1<<31-1 {
			return nil, fail("E_UNSUPPORTED", "call displacement out of range")
		}
		binary.LittleEndian.PutUint32(code.Bytes()[patch.offset:], uint32(displacement))
	}
	return elf(code.Bytes()), nil
}

func functionSlot(code *bytes.Buffer, op, reg byte, offset int) {
	code.Write([]byte{0x48 | ((reg >> 3) << 2), op, 0x84 | ((reg & 7) << 3), 0x24})
	imm32(code, offset)
}
