//! Bounded stdin, one extra byte detects overflow without returning truncation.
use super::{flow::patch, imm32, runtime::finish_message, Result};

pub(super) fn read(code: &mut Vec<u8>, limit: usize, heap_guards: &mut Vec<usize>) -> Result<()> {
    code.extend_from_slice(&[0x4d, 0x89, 0xe1, 0x4d, 0x8d, 0x9c, 0x24]);
    imm32(code, (limit + 16) & !7);
    code.extend_from_slice(&[0x4d, 0x39, 0xeb, 0x0f, 0x87]);
    heap_guards.push(code.len());
    imm32(code, 0);
    code.extend_from_slice(&[
        0x4d, 0x89, 0xdc, 0x49, 0x8d, 0x71, 8, 0x45, 0x31, 0xc0, 0xba,
    ]);
    imm32(code, limit + 1);
    code.extend_from_slice(&[0x31, 0xff]);
    let loop_start = code.len();
    code.extend_from_slice(&[0x31, 0xc0, 0x0f, 0x05, 0x48, 0x83, 0xf8, 0xfc, 0x0f, 0x84]);
    let retry = code.len();
    imm32(code, 0);
    patch(code, retry, loop_start)?;
    code.extend_from_slice(&[0x48, 0x85, 0xc0, 0x0f, 0x88]);
    let io_error = code.len();
    imm32(code, 0);
    code.extend_from_slice(&[0x0f, 0x84]);
    let done = code.len();
    imm32(code, 0);
    code.extend_from_slice(&[0x49, 0x01, 0xc0, 0x49, 0x81, 0xf8]);
    imm32(code, limit);
    code.extend_from_slice(&[0x0f, 0x87]);
    let oversize = code.len();
    imm32(code, 0);
    code.extend_from_slice(&[0x48, 0x01, 0xc6, 0x48, 0x29, 0xc2, 0xe9]);
    let next = code.len();
    imm32(code, 0);
    patch(code, next, loop_start)?;
    let target = code.len();
    patch(code, done, target)?;
    code.extend_from_slice(&[0x4d, 0x89, 0x01, 0x4c, 0x89, 0xc8, 0xe9]);
    let end = code.len();
    imm32(code, 0);
    finish_message(code, &[io_error], "E_RUNTIME_IO: input read failed\n", 74)?;
    finish_message(
        code,
        &[oversize],
        "E_RUNTIME_INPUT: input exceeds byte limit\n",
        65,
    )?;
    let target = code.len();
    patch(code, end, target)
}
