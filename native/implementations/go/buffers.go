package main

import (
	"bytes"
	"encoding/binary"
)

type byteLiteral struct {
	offset int
	data   []byte
}

func emitByteLiterals(code *bytes.Buffer, blobs []byteLiteral) error {
	for _, blob := range blobs {
		if err := patchFlowJump(code, blob.offset, code.Len()); err != nil {
			return err
		}
		_ = binary.Write(code, binary.LittleEndian, uint64(len(blob.data)))
		code.Write(blob.data)
	}
	return nil
}
func emitByteGet(code *bytes.Buffer, buffer, index, fallback int) error {
	functionSlot(code, 0x8b, 0, buffer)
	functionSlot(code, 0x8b, 1, index)
	code.Write([]byte{0x48, 0x8b, 0x10, 0x48, 0x85, 0xc9, 0x0f, 0x89})
	nonnegative := code.Len()
	imm32(code, 0)
	code.Write([]byte{0x48, 0x01, 0xd1})
	if err := patchFlowJump(code, nonnegative, code.Len()); err != nil {
		return err
	}
	code.Write([]byte{0x48, 0x39, 0xd1, 0x0f, 0x83})
	outside := code.Len()
	imm32(code, 0)
	code.Write([]byte{0x48, 0x0f, 0xb6, 0x44, 0x08, 0x08, 0xe9})
	end := code.Len()
	imm32(code, 0)
	if err := patchFlowJump(code, outside, code.Len()); err != nil {
		return err
	}
	functionSlot(code, 0x8b, 0, fallback)
	return patchFlowJump(code, end, code.Len())
}
