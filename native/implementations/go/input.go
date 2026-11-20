package main

import "bytes"

// Reserve lookahead capacity before IO; publish actual length only after EOF.
func emitByteRead(code *bytes.Buffer, limit int, heapGuards *[]int) error {
	code.Write([]byte{0x4d, 0x89, 0xe1, 0x4d, 0x8d, 0x9c, 0x24})
	imm32(code, (limit+16)&^7)
	code.Write([]byte{0x4d, 0x39, 0xeb, 0x0f, 0x87})
	*heapGuards = append(*heapGuards, code.Len())
	imm32(code, 0)
	code.Write([]byte{0x4d, 0x89, 0xdc, 0x49, 0x8d, 0x71, 8, 0x45, 0x31, 0xc0, 0xba})
	imm32(code, limit+1)
	code.Write([]byte{0x31, 0xff})
	loop := code.Len()
	code.Write([]byte{0x31, 0xc0, 0x0f, 0x05, 0x48, 0x83, 0xf8, 0xfc, 0x0f, 0x84})
	retry := code.Len()
	imm32(code, 0)
	if err := patchFlowJump(code, retry, loop); err != nil {
		return err
	}
	code.Write([]byte{0x48, 0x85, 0xc0, 0x0f, 0x88})
	ioError := code.Len()
	imm32(code, 0)
	code.Write([]byte{0x0f, 0x84})
	done := code.Len()
	imm32(code, 0)
	code.Write([]byte{0x49, 0x01, 0xc0, 0x49, 0x81, 0xf8})
	imm32(code, limit)
	code.Write([]byte{0x0f, 0x87})
	oversize := code.Len()
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
	code.Write([]byte{0x4d, 0x89, 0x01, 0x4c, 0x89, 0xc8, 0xe9})
	end := code.Len()
	imm32(code, 0)
	if err := emitFailureMessage(code, []int{ioError}, "E_RUNTIME_IO: input read failed\n", 74); err != nil {
		return err
	}
	if err := emitFailureMessage(code, []int{oversize}, "E_RUNTIME_INPUT: input exceeds byte limit\n", 65); err != nil {
		return err
	}
	return patchFlowJump(code, end, code.Len())
}
