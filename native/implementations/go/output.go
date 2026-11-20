package main

import "bytes"

const outputFailureMessage = "E_RUNTIME_IO: output write failed\n"

func emitByteWrite(code *bytes.Buffer, value, stream int, guards *[]int) error {
	functionSlot(code, 0x8b, 0, value)
	code.Write([]byte{0x48, 0x8b, 0x10, 0x48, 0x8d, 0x70, 8, 0x49, 0x89, 0xd0, 0xbf})
	imm32(code, stream)
	loop := code.Len()
	code.Write([]byte{0x48, 0x85, 0xd2, 0x0f, 0x84})
	done := code.Len()
	imm32(code, 0)
	code.Write([]byte{0xb8, 1, 0, 0, 0, 0x0f, 0x05, 0x48, 0x83, 0xf8, 0xfc, 0x0f, 0x84})
	retry := code.Len()
	imm32(code, 0)
	if err := patchFlowJump(code, retry, loop); err != nil {
		return err
	}
	code.Write([]byte{0x48, 0x85, 0xc0, 0x0f, 0x8e})
	*guards = append(*guards, code.Len())
	imm32(code, 0)
	code.Write([]byte{0x48, 0x01, 0xc6, 0x48, 0x29, 0xc2, 0xe9})
	next := code.Len()
	imm32(code, 0)
	if err := patchFlowJump(code, next, loop); err != nil {
		return err
	}
	if err := patchFlowJump(code, done, code.Len()); err != nil {
		return err
	}
	code.Write([]byte{0x4c, 0x89, 0xc0})
	return nil
}
