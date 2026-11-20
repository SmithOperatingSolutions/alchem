package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
)

type flowInstruction struct {
	Count   string          `json:"count"`
	Limit   json.RawMessage `json:"limit"`
	Stream  string          `json:"stream"`
	Values  json.RawMessage `json:"values"`
	Buffer  string          `json:"buffer"`
	Index   string          `json:"index"`
	Default string          `json:"default"`
	Op      string          `json:"op"`
	Dest    string          `json:"dest"`
	Value   json.RawMessage `json:"value"`
	LHS     string          `json:"lhs"`
	RHS     string          `json:"rhs"`
	Callee  string          `json:"callee"`
	Args    []string        `json:"args"`
	Cond    string          `json:"cond"`
	Then    *flowBranch     `json:"then"`
	Else    *flowBranch     `json:"else"`
}
type flowBranch struct {
	Instructions []json.RawMessage `json:"instructions"`
	Value        string            `json:"value"`
}
type flowBlock struct {
	Label        string            `json:"label"`
	Instructions []json.RawMessage `json:"instructions"`
	Terminator   struct {
		Op    string `json:"op"`
		Value string `json:"value"`
	} `json:"terminator"`
}
type flowFunction struct {
	Name       string            `json:"name"`
	Params     []json.RawMessage `json:"params"`
	ReturnType string            `json:"return_type"`
	Blocks     []flowBlock       `json:"blocks"`
}
type flowProgram struct {
	ArenaBytes json.RawMessage `json:"arena_bytes"`
	Version    int             `json:"version"`
	Functions  []flowFunction  `json:"functions"`
}

func strictFlowDecode(data []byte, out any) error {
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	return d.Decode(out)
}
func (in *flowInstruction) UnmarshalJSON(data []byte) error {
	type plain flowInstruction
	var decoded plain
	if err := strictFlowDecode(data, &decoded); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	required := []string{"op", "dest"}
	switch decoded.Op {
	case "const.i64", "const.bool", "not.bool", "bytes.len":
		required = append(required, "value")
	case "bytes.concat", "add.i64", "sub.i64", "mul.i64", "eq.i64", "ne.i64", "lt.i64", "le.i64", "gt.i64", "ge.i64":
		required = append(required, "lhs", "rhs")
	case "bytes.write":
		required = append(required, "value", "stream")
	case "bytes.const":
		required = append(required, "values")
	case "bytes.slice":
		required = append(required, "buffer", "index", "count")
	case "bytes.get":
		required = append(required, "buffer", "index", "default")
	case "bytes.read":
		required = append(required, "limit")
	case "bytes.pack":
		required = append(required, "args")
	case "call":
		required = append(required, "callee", "args")
	case "if.i64", "if.bool", "if.bytes":
		required = append(required, "cond", "then", "else")
	default:
		*in = flowInstruction(decoded)
		return nil
	}
	allowed := map[string]bool{}
	for _, key := range required {
		allowed[key] = true
		value, ok := fields[key]
		if !ok || bytes.Equal(bytes.TrimSpace(value), []byte("null")) {
			return fmt.Errorf("missing/null %s", key)
		}
	}
	for key := range fields {
		if !allowed[key] {
			return fmt.Errorf("unexpected %s for %s", key, decoded.Op)
		}
	}
	*in = flowInstruction(decoded)
	return nil
}

type flowValue struct {
	slot int
	kind string
}
type loweredBranch struct {
	ops   []flowOp
	value int
}
type flowOp struct {
	stream                       int
	data                         []byte
	fallback                     int
	op                           string
	dest, lhs, rhs, callee, cond int
	value                        int64
	args                         []int
	yes, no                      loweredBranch
}
type flowCallable struct {
	result     string
	params     []parameter
	ops        []flowOp
	ret, frame int
	edges      []int
}
type flowContext struct {
	slicing      bool
	input        bool
	packing      bool
	construction bool
	output       bool
	buffers      bool
	dataBytes    int
	names        map[string]int
	signatures   []flowCallable
	seen         map[string]bool
	next         int
	edges        []int
}

func cloneFlowEnv(env map[string]flowValue) map[string]flowValue {
	copy := map[string]flowValue{}
	for name, value := range env {
		copy[name] = value
	}
	return copy
}
func flowUse(env map[string]flowValue, name, kind string) (int, error) {
	value, ok := env[name]
	if !ok || value.kind != kind {
		return 0, fail("E_INVALID_IR", "undefined or incorrectly typed value "+name)
	}
	return value.slot, nil
}
func (ctx *flowContext) lower(instructions []json.RawMessage, env map[string]flowValue, depth int) ([]flowOp, error) {
	if instructions == nil {
		return nil, fail("E_INVALID_IR", "instructions must be an array")
	}
	out := []flowOp{}
	for _, raw := range instructions {
		var in flowInstruction
		if err := strictFlowDecode(raw, &in); err != nil {
			return nil, fail("E_INVALID_IR", err.Error())
		}
		kind := "i64"
		switch in.Op {
		case "const.i64", "add.i64", "sub.i64", "mul.i64", "if.i64":
		case "call":
			target, ok := ctx.names[in.Callee]
			if !ok {
				return nil, fail("E_INVALID_IR", "undefined callee")
			}
			kind = ctx.signatures[target].result
		case "bytes.slice":
			if !ctx.slicing {
				return nil, fail("E_UNKNOWN_OPCODE", in.Op)
			}
			kind = "bytes"
		case "bytes.read":
			if !ctx.input {
				return nil, fail("E_UNKNOWN_OPCODE", in.Op)
			}
			kind = "bytes"
		case "bytes.pack":
			if !ctx.packing {
				return nil, fail("E_UNKNOWN_OPCODE", in.Op)
			}
			kind = "bytes"
		case "bytes.concat":
			if !ctx.construction {
				return nil, fail("E_UNKNOWN_OPCODE", in.Op)
			}
			kind = "bytes"
		case "bytes.write":
			if !ctx.output {
				return nil, fail("E_UNKNOWN_OPCODE", in.Op)
			}
		case "bytes.const", "bytes.len", "bytes.get", "if.bytes":
			if !ctx.buffers {
				return nil, fail("E_UNKNOWN_OPCODE", in.Op)
			}
			if in.Op == "bytes.const" || in.Op == "if.bytes" {
				kind = "bytes"
			}
		case "const.bool", "not.bool", "eq.i64", "ne.i64", "lt.i64", "le.i64", "gt.i64", "ge.i64", "if.bool":
			kind = "bool"
		default:
			return nil, fail("E_UNKNOWN_OPCODE", in.Op)
		}
		if in.Dest == "" || ctx.seen[in.Dest] {
			return nil, fail("E_INVALID_IR", "missing or duplicate SSA destination")
		}
		ctx.seen[in.Dest] = true
		op := flowOp{op: in.Op, dest: ctx.next * 8}
		ctx.next++
		if ctx.next > 1<<17 {
			return nil, fail("E_UNSUPPORTED", "too many IR values")
		}
		var err error
		switch in.Op {
		case "bytes.slice":
			op.lhs, err = flowUse(env, in.Buffer, "bytes")
			if err != nil {
				return nil, err
			}
			op.rhs, err = flowUse(env, in.Index, "i64")
			if err != nil {
				return nil, err
			}
			op.fallback, err = flowUse(env, in.Count, "i64")
			if err != nil {
				return nil, err
			}
		case "bytes.read":
			var limit int64
			// Version 11, which builds the compiler, reads sources up to 16 MiB.
			if err := json.Unmarshal(in.Limit, &limit); err != nil || limit < 0 || limit > 1<<24 || (!ctx.slicing && limit > 1<<20) {
				if ctx.slicing {
					return nil, fail("E_INVALID_IR", "expected input limit 0..16777216")
				}
				return nil, fail("E_INVALID_IR", "expected input limit 0..1048576")
			}
			op.value = limit
		case "bytes.pack":
			if len(in.Args) > 4096 {
				return nil, fail("E_UNSUPPORTED", "pack exceeds 4096 values")
			}
			for _, arg := range in.Args {
				slot, err := flowUse(env, arg, "i64")
				if err != nil {
					return nil, err
				}
				op.args = append(op.args, slot)
			}
		case "bytes.concat":
			op.lhs, err = flowUse(env, in.LHS, "bytes")
			if err != nil {
				return nil, err
			}
			op.rhs, err = flowUse(env, in.RHS, "bytes")
			// A concatenated payload is at most 1 MiB; version 11 leaves it to the arena.
			op.value = 1 << 20
			if ctx.slicing {
				op.value = 1 << 30
			}
			if err != nil {
				return nil, err
			}
		case "bytes.write":
			var name string
			if err := json.Unmarshal(in.Value, &name); err != nil {
				return nil, fail("E_INVALID_IR", "expected buffer name")
			}
			op.lhs, err = flowUse(env, name, "bytes")
			if err != nil {
				return nil, err
			}
			switch in.Stream {
			case "stdout":
				op.stream = 1
			case "stderr":
				op.stream = 2
			default:
				return nil, fail("E_INVALID_IR", "expected stdout/stderr stream")
			}
		case "bytes.const":
			var values []json.RawMessage
			if err := json.Unmarshal(in.Values, &values); err != nil || values == nil {
				return nil, fail("E_INVALID_IR", "expected byte array")
			}
			if len(values) > 1<<20 {
				return nil, fail("E_UNSUPPORTED", "byte literal exceeds 1 MiB")
			}
			ctx.dataBytes += len(values) + 8
			if ctx.dataBytes > dataLimit(ctx.slicing) {
				return nil, fail("E_UNSUPPORTED", dataMessage(ctx.slicing))
			}
			for _, raw := range values {
				var value int64
				if bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
					return nil, fail("E_INVALID_IR", "null byte")
				}
				if err := json.Unmarshal(raw, &value); err != nil || value < 0 || value > 255 {
					return nil, fail("E_INVALID_IR", "expected integer byte 0..255")
				}
				op.data = append(op.data, byte(value))
			}
		case "bytes.len":
			var name string
			if err := json.Unmarshal(in.Value, &name); err != nil {
				return nil, fail("E_INVALID_IR", "expected buffer name")
			}
			op.lhs, err = flowUse(env, name, "bytes")
			if err != nil {
				return nil, err
			}
		case "bytes.get":
			op.lhs, err = flowUse(env, in.Buffer, "bytes")
			if err != nil {
				return nil, err
			}
			op.rhs, err = flowUse(env, in.Index, "i64")
			if err != nil {
				return nil, err
			}
			op.fallback, err = flowUse(env, in.Default, "i64")
			if err != nil {
				return nil, err
			}
		case "const.i64":
			var value int64
			if err = json.Unmarshal(in.Value, &value); err != nil {
				return nil, fail("E_INVALID_IR", err.Error())
			}
			op.value = value
		case "const.bool":
			var value bool
			if err = json.Unmarshal(in.Value, &value); err != nil {
				return nil, fail("E_INVALID_IR", err.Error())
			}
			if value {
				op.value = 1
			}
		case "not.bool":
			var name string
			if err = json.Unmarshal(in.Value, &name); err != nil {
				return nil, fail("E_INVALID_IR", err.Error())
			}
			op.lhs, err = flowUse(env, name, "bool")
			if err != nil {
				return nil, err
			}
		case "call":
			target, ok := ctx.names[in.Callee]
			if !ok || len(in.Args) != len(ctx.signatures[target].params) {
				return nil, fail("E_INVALID_IR", "undefined callee or arity mismatch")
			}
			op.callee = target
			for i, arg := range in.Args {
				slot, err := flowUse(env, arg, ctx.signatures[target].params[i].Type)
				if err != nil {
					return nil, err
				}
				op.args = append(op.args, slot)
			}
			ctx.edges = append(ctx.edges, target)
		case "if.i64", "if.bool", "if.bytes":
			if depth >= 16 {
				return nil, fail("E_UNSUPPORTED", "conditional nesting exceeds 16")
			}
			op.cond, err = flowUse(env, in.Cond, "bool")
			if err != nil {
				return nil, err
			}
			branches := []*flowBranch{in.Then, in.Else}
			results := []*loweredBranch{&op.yes, &op.no}
			for i, branch := range branches {
				if branch == nil {
					return nil, fail("E_INVALID_IR", "missing branch")
				}
				local := cloneFlowEnv(env)
				results[i].ops, err = ctx.lower(branch.Instructions, local, depth+1)
				if err != nil {
					return nil, err
				}
				results[i].value, err = flowUse(local, branch.Value, kind)
				if err != nil {
					return nil, err
				}
			}
		default:
			op.lhs, err = flowUse(env, in.LHS, "i64")
			if err != nil {
				return nil, err
			}
			op.rhs, err = flowUse(env, in.RHS, "i64")
			if err != nil {
				return nil, err
			}
		}
		env[in.Dest] = flowValue{op.dest, kind}
		out = append(out, op)
	}
	return out, nil
}
func compileFlow(input []byte) ([]byte, error) {
	var p flowProgram
	if err := strictFlowDecode(input, &p); err != nil {
		return nil, fail("E_INVALID_IR", err.Error())
	}
	arenaBytes := 4 << 20
	if p.Version == 11 {
		var size int64
		if err := json.Unmarshal(p.ArenaBytes, &size); err != nil || size < 8 || size > 1<<34 || size%8 != 0 {
			return nil, fail("E_INVALID_IR", "expected arena_bytes multiple of 8 in 8..17179869184")
		}
		arenaBytes = int(size)
	} else if len(p.ArenaBytes) != 0 {
		return nil, fail("E_INVALID_IR", "arena_bytes requires version 11")
	}
	if len(p.Functions) == 0 {
		return nil, fail("E_INVALID_IR", "missing functions")
	}
	functionLimit := 256
	if p.Version == 11 {
		functionLimit = 65535
	}
	if len(p.Functions) > functionLimit {
		return nil, fail("E_UNSUPPORTED", "too many functions")
	}
	names := map[string]int{}
	functions := make([]flowCallable, len(p.Functions))
	for i, f := range p.Functions {
		if f.Name == "" {
			return nil, fail("E_INVALID_IR", "missing function name")
		}
		if _, ok := names[f.Name]; ok {
			return nil, fail("E_INVALID_IR", "duplicate function")
		}
		names[f.Name] = i
		functions[i].result = f.ReturnType
		if (f.ReturnType != "i64" && !(p.Version >= 8 && f.ReturnType == "bytes")) || len(f.Blocks) != 1 || f.Blocks[0].Label != "entry" {
			return nil, fail("E_UNSUPPORTED", "expected one i64 entry block")
		}
		if f.Params == nil {
			return nil, fail("E_INVALID_IR", "params must be an array")
		}
		if len(f.Params) > 6 {
			return nil, fail("E_UNSUPPORTED", "at most six parameters")
		}
		seen := map[string]bool{}
		for _, raw := range f.Params {
			var fields map[string]json.RawMessage
			if err := json.Unmarshal(raw, &fields); err != nil {
				return nil, fail("E_INVALID_IR", err.Error())
			}
			for _, key := range []string{"name", "type"} {
				value, ok := fields[key]
				if !ok || bytes.Equal(bytes.TrimSpace(value), []byte("null")) {
					return nil, fail("E_INVALID_IR", "missing/null parameter field")
				}
			}
			var param parameter
			if err := strictFlowDecode(raw, &param); err != nil {
				return nil, fail("E_INVALID_IR", err.Error())
			}
			if param.Name == "" || seen[param.Name] {
				return nil, fail("E_INVALID_IR", "invalid/duplicate parameter")
			}
			seen[param.Name] = true
			if param.Type != "i64" && !(p.Version >= 5 && param.Type == "bytes") {
				return nil, fail("E_UNSUPPORTED", "only i64 function parameters")
			}
			functions[i].params = append(functions[i].params, param)
		}
	}
	main, ok := names["main"]
	if !ok || len(functions[main].params) != 0 || functions[main].result != "i64" {
		return nil, fail("E_INVALID_IR", "expected parameterless main")
	}
	dataBytes := 0
	for i, f := range p.Functions {
		ctx := flowContext{slicing: p.Version == 11, input: p.Version >= 10, packing: p.Version >= 9, construction: p.Version >= 8, output: p.Version >= 7, buffers: p.Version >= 5, names: names, signatures: functions, seen: map[string]bool{}}
		env := map[string]flowValue{}
		for _, param := range functions[i].params {
			ctx.seen[param.Name] = true
			env[param.Name] = flowValue{ctx.next * 8, param.Type}
			ctx.next++
		}
		ops, err := ctx.lower(f.Blocks[0].Instructions, env, 0)
		if err != nil {
			return nil, err
		}
		dataBytes += ctx.dataBytes
		if dataBytes > dataLimit(ctx.slicing) {
			return nil, fail("E_UNSUPPORTED", dataMessage(ctx.slicing))
		}
		functions[i].ops = ops
		term := f.Blocks[0].Terminator
		if term.Op != "ret" {
			return nil, fail("E_UNSUPPORTED", "only ret terminators")
		}
		functions[i].ret, err = flowUse(env, term.Value, functions[i].result)
		if err != nil {
			return nil, err
		}
		functions[i].frame = (ctx.next*8 + 15) & ^15
		functions[i].edges = ctx.edges
	}
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
		for _, callee := range functions[i].edges {
			child, err := height(callee)
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
	runtime := p.Version >= 4
	if !runtime {
		for i := range functions {
			if _, err := height(i); err != nil {
				return nil, err
			}
		}
	}
	code := new(bytes.Buffer)
	if runtime {
		code.Write([]byte{0x45, 0x31, 0xf6, 0x45, 0x31, 0xff})
	}
	heapGuards := []int{}
	byteGuards := []int{}
	if p.Version >= 8 {
		emitArenaInit(code, &heapGuards, arenaBytes)
	}
	callOffset := code.Len() + 1
	guards := []int{}
	blobs := []byteLiteral{}
	outputGuards := []int{}
	code.Write([]byte{0xe8, 0, 0, 0, 0})
	statusGuards := []int{}
	if p.Version >= 6 {
		code.Write([]byte{0x48, 0x3d, 0xff, 0, 0, 0, 0x0f, 0x87})
		statusGuards = append(statusGuards, code.Len())
		imm32(code, 0)
	}
	code.Write([]byte{0x48, 0x89, 0xc7, 0xb8, 0x3c, 0, 0, 0, 0x0f, 0x05})
	patches := []relocation{{callOffset, main}}
	starts := make([]int, len(functions))
	for i, f := range functions {
		starts[i] = code.Len()
		if runtime {
			if p.Version == 11 {
				guards = append(guards, emitRuntimeGuard(code, f.frame, 1024, 4<<20)...)
			} else {
				guards = append(guards, emitRuntimeGuard(code, f.frame, 256, 1<<20)...)
			}
		}
		code.Write([]byte{0x55, 0x48, 0x89, 0xe5, 0x48, 0x81, 0xec})
		imm32(code, f.frame)
		for j := range f.params {
			functionSlot(code, 0x89, argumentRegisters[j], j*8)
		}
		if err := emitFlowOps(code, f.ops, &patches, &blobs, &outputGuards, &heapGuards, &byteGuards); err != nil {
			return nil, err
		}
		functionSlot(code, 0x8b, 0, f.ret)
		if runtime {
			emitRuntimeReturn(code, f.frame)
		}
		code.Write([]byte{0xc9, 0xc3})
	}
	for _, patch := range patches {
		if err := patchFlowJump(code, patch.offset, starts[patch.callee]); err != nil {
			return nil, err
		}
	}
	if runtime {
		if err := emitRuntimeFailure(code, guards); err != nil {
			return nil, err
		}
	}
	if p.Version >= 6 {
		if err := emitFailureMessage(code, statusGuards, haltStatusMessage, 70); err != nil {
			return nil, err
		}
	}
	if len(outputGuards) > 0 {
		if err := emitFailureMessage(code, outputGuards, outputFailureMessage, 74); err != nil {
			return nil, err
		}
	}
	if p.Version >= 8 {
		if err := emitFailureMessage(code, heapGuards, allocationMessage, 71); err != nil {
			return nil, err
		}
	}
	if len(byteGuards) > 0 {
		if err := emitFailureMessage(code, byteGuards, byteValueMessage, 72); err != nil {
			return nil, err
		}
	}
	if err := emitByteLiterals(code, blobs); err != nil {
		return nil, err
	}
	return elf(code.Bytes()), nil
}
func patchFlowJump(code *bytes.Buffer, offset, target int) error {
	delta := int64(target) - int64(offset+4)
	if delta < -1<<31 || delta > 1<<31-1 {
		return fail("E_UNSUPPORTED", "relative displacement out of range")
	}
	binary.LittleEndian.PutUint32(code.Bytes()[offset:], uint32(delta))
	return nil
}
func emitFlowOps(code *bytes.Buffer, ops []flowOp, patches *[]relocation, blobs *[]byteLiteral, outputGuards *[]int, heapGuards *[]int, byteGuards *[]int) error {
	for _, op := range ops {
		switch op.op {
		case "bytes.slice":
			if err := emitByteSlice(code, op.lhs, op.rhs, op.fallback, heapGuards); err != nil {
				return err
			}
		case "bytes.read":
			if err := emitByteRead(code, int(op.value), heapGuards); err != nil {
				return err
			}
		case "bytes.pack":
			emitPack(code, op.args, heapGuards, byteGuards)
		case "bytes.concat":
			emitConcat(code, op.lhs, op.rhs, int(op.value), heapGuards)
		case "bytes.write":
			if err := emitByteWrite(code, op.lhs, op.stream, outputGuards); err != nil {
				return err
			}
		case "bytes.const":
			code.Write([]byte{0x48, 0x8d, 0x05})
			*blobs = append(*blobs, byteLiteral{code.Len(), op.data})
			imm32(code, 0)
		case "bytes.len":
			functionSlot(code, 0x8b, 0, op.lhs)
			code.Write([]byte{0x48, 0x8b, 0x00})
		case "bytes.get":
			if err := emitByteGet(code, op.lhs, op.rhs, op.fallback); err != nil {
				return err
			}
		case "const.i64", "const.bool":
			code.Write([]byte{0x48, 0xb8})
			_ = binary.Write(code, binary.LittleEndian, int64(op.value))
		case "call":
			for i, arg := range op.args {
				functionSlot(code, 0x8b, argumentRegisters[i], arg)
			}
			code.WriteByte(0xe8)
			*patches = append(*patches, relocation{code.Len(), op.callee})
			imm32(code, 0)
		case "not.bool":
			functionSlot(code, 0x8b, 0, op.lhs)
			code.Write([]byte{0x48, 0x83, 0xf0, 1})
		case "if.i64", "if.bool", "if.bytes":
			functionSlot(code, 0x8b, 0, op.cond)
			code.Write([]byte{0x48, 0x85, 0xc0, 0x0f, 0x84})
			otherwise := code.Len()
			imm32(code, 0)
			if err := emitFlowOps(code, op.yes.ops, patches, blobs, outputGuards, heapGuards, byteGuards); err != nil {
				return err
			}
			functionSlot(code, 0x8b, 0, op.yes.value)
			code.WriteByte(0xe9)
			end := code.Len()
			imm32(code, 0)
			if err := patchFlowJump(code, otherwise, code.Len()); err != nil {
				return err
			}
			if err := emitFlowOps(code, op.no.ops, patches, blobs, outputGuards, heapGuards, byteGuards); err != nil {
				return err
			}
			functionSlot(code, 0x8b, 0, op.no.value)
			if err := patchFlowJump(code, end, code.Len()); err != nil {
				return err
			}
		default:
			functionSlot(code, 0x8b, 0, op.lhs)
			functionSlot(code, 0x8b, 1, op.rhs)
			switch op.op {
			case "add.i64":
				code.Write([]byte{0x48, 0x01, 0xc8})
			case "sub.i64":
				code.Write([]byte{0x48, 0x29, 0xc8})
			case "mul.i64":
				code.Write([]byte{0x48, 0x0f, 0xaf, 0xc1})
			default:
				cc := map[string]byte{"eq.i64": 0x94, "ne.i64": 0x95, "lt.i64": 0x9c, "le.i64": 0x9e, "gt.i64": 0x9f, "ge.i64": 0x9d}[op.op]
				code.Write([]byte{0x48, 0x39, 0xc8, 0x0f, cc, 0xc0, 0x48, 0x0f, 0xb6, 0xc0})
			}
		}
		functionSlot(code, 0x89, 0, op.dest)
	}
	return nil
}

// dataLimit is the most static byte data a program holds: 4 MiB, and 16 MiB
// in version 11, which builds the compiler and reads sources of that size.
func dataLimit(slicing bool) int {
	if slicing {
		return 16 << 20
	}
	return 4 << 20
}

func dataMessage(slicing bool) string {
	if slicing {
		return "byte data exceeds 16 MiB"
	}
	return "byte data exceeds 4 MiB"
}
