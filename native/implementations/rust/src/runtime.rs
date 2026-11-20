//! Private V4 call-depth and active-frame guards; emitted code has no host runtime.
use super::{flow::patch, imm32, Result};
pub(super) const MESSAGE: &str = "E_RUNTIME_LIMIT: native call/stack budget exceeded\n";
/// depth and stack are the bounds: 256 calls and 1 MiB, or for version 11,
/// which builds the compiler, 1024 calls and 4 MiB.
pub(super) fn enter(code: &mut Vec<u8>, frame: usize, depth_limit: usize, stack_limit: usize) -> Vec<usize> {
    code.extend_from_slice(&[0x49, 0xff, 0xc7, 0x49, 0x81, 0xff]);
    imm32(code, depth_limit);
    code.extend_from_slice(&[0x0f, 0x87]);
    let depth = code.len();
    imm32(code, 0);
    code.extend_from_slice(&[0x49, 0x81, 0xc6]);
    imm32(code, frame + 16);
    code.extend_from_slice(&[0x49, 0x81, 0xfe]);
    imm32(code, stack_limit);
    code.extend_from_slice(&[0x0f, 0x87]);
    let storage = code.len();
    imm32(code, 0);
    vec![depth, storage]
}
pub(super) fn leave(code: &mut Vec<u8>, frame: usize) {
    code.extend_from_slice(&[0x49, 0x81, 0xee]);
    imm32(code, frame + 16);
    code.extend_from_slice(&[0x49, 0xff, 0xcf]);
}
pub(super) fn finish(code: &mut Vec<u8>, guards: &[usize]) -> Result<()> {
    finish_message(code, guards, MESSAGE, 70)
}
pub(super) fn finish_status(code: &mut Vec<u8>, guards: &[usize]) -> Result<()> {
    finish_message(code, guards, "E_HALT_STATUS: expected status 0..255\n", 70)
}
pub(super) fn finish_output(code: &mut Vec<u8>, guards: &[usize]) -> Result<()> {
    finish_message(code, guards, "E_RUNTIME_IO: output write failed\n", 74)
}
pub(super) fn finish_alloc(code: &mut Vec<u8>, guards: &[usize]) -> Result<()> {
    finish_message(
        code,
        guards,
        "E_RUNTIME_ALLOC: byte allocation failed or limit exceeded\n",
        71,
    )
}
pub(super) fn finish_byte(code: &mut Vec<u8>, guards: &[usize]) -> Result<()> {
    finish_message(
        code,
        guards,
        "E_RUNTIME_BYTE: expected byte value 0..255\n",
        72,
    )
}
pub(super) fn finish_message(
    code: &mut Vec<u8>,
    guards: &[usize],
    diagnostic: &str,
    status: usize,
) -> Result<()> {
    let target = code.len();
    for offset in guards {
        patch(code, *offset, target)?;
    }
    code.extend_from_slice(&[0xb8, 1, 0, 0, 0, 0xbf, 2, 0, 0, 0, 0x48, 0x8d, 0x35]);
    let message = code.len();
    imm32(code, 0);
    code.push(0xba);
    imm32(code, diagnostic.len());
    code.extend_from_slice(&[0x0f, 0x05, 0xb8, 0x3c, 0, 0, 0, 0xbf]);
    imm32(code, status);
    code.extend_from_slice(&[0x0f, 0x05]);
    let target = code.len();
    patch(code, message, target)?;
    code.extend_from_slice(diagnostic.as_bytes());
    Ok(())
}
