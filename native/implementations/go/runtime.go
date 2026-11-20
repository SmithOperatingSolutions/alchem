package main

import "bytes"

const haltStatusMessage = "E_HALT_STATUS: expected status 0..255\n"

const runtimeLimitMessage = "E_RUNTIME_LIMIT: native call/stack budget exceeded\n"

// depth and stack are the bounds: 256 calls and 1 MiB, or for version 11,
// which builds the compiler, 1024 calls and 4 MiB.
func emitRuntimeGuard(code *bytes.Buffer, frame, depthLimit, stackLimit int) []int {
	code.Write([]byte{0x49, 0xff, 0xc7, 0x49, 0x81, 0xff})
	imm32(code, depthLimit)
	code.Write([]byte{0x0f, 0x87})
	depth := code.Len()
	imm32(code, 0)
	code.Write([]byte{0x49, 0x81, 0xc6})
	imm32(code, frame+16)
	code.Write([]byte{0x49, 0x81, 0xfe})
	imm32(code, stackLimit)
	code.Write([]byte{0x0f, 0x87})
	storage := code.Len()
	imm32(code, 0)
	return []int{depth, storage}
}
func emitRuntimeReturn(code *bytes.Buffer, frame int) {
	code.Write([]byte{0x49, 0x81, 0xee})
	imm32(code, frame+16)
	code.Write([]byte{0x49, 0xff, 0xcf})
}
func emitRuntimeFailure(code *bytes.Buffer, guards []int) error {
	return emitFailureMessage(code, guards, runtimeLimitMessage, 70)
}
func emitFailureMessage(code *bytes.Buffer, guards []int, diagnostic string, status int) error {
	target := code.Len()
	for _, offset := range guards {
		if err := patchFlowJump(code, offset, target); err != nil {
			return err
		}
	}
	code.Write([]byte{0xb8, 1, 0, 0, 0, 0xbf, 2, 0, 0, 0, 0x48, 0x8d, 0x35})
	message := code.Len()
	imm32(code, 0)
	code.WriteByte(0xba)
	imm32(code, len(diagnostic))
	code.Write([]byte{0x0f, 0x05, 0xb8, 0x3c, 0, 0, 0, 0xbf})
	imm32(code, status)
	code.Write([]byte{0x0f, 0x05})
	if err := patchFlowJump(code, message, code.Len()); err != nil {
		return err
	}
	code.WriteString(diagnostic)
	return nil
}
