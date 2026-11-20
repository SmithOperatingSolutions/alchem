//! Complete stdout/stderr byte writes with EINTR retry and progress checks.
use super::{flow::patch, functions::slot, imm32, Result};
pub(super) fn write(
    code: &mut Vec<u8>,
    value: usize,
    stream: usize,
    guards: &mut Vec<usize>,
) -> Result<()> {
    slot(code, 0x8b, 0, value);
    code.extend_from_slice(&[
        0x48, 0x8b, 0x10, 0x48, 0x8d, 0x70, 8, 0x49, 0x89, 0xd0, 0xbf,
    ]);
    imm32(code, stream);
    let loop_ = code.len();
    code.extend_from_slice(&[0x48, 0x85, 0xd2, 0x0f, 0x84]);
    let done = code.len();
    imm32(code, 0);
    code.extend_from_slice(&[
        0xb8, 1, 0, 0, 0, 0x0f, 0x05, 0x48, 0x83, 0xf8, 0xfc, 0x0f, 0x84,
    ]);
    let retry = code.len();
    imm32(code, 0);
    patch(code, retry, loop_)?;
    code.extend_from_slice(&[0x48, 0x85, 0xc0, 0x0f, 0x8e]);
    guards.push(code.len());
    imm32(code, 0);
    code.extend_from_slice(&[0x48, 0x01, 0xc6, 0x48, 0x29, 0xc2, 0xe9]);
    let next = code.len();
    imm32(code, 0);
    patch(code, next, loop_)?;
    let target = code.len();
    patch(code, done, target)?;
    code.extend_from_slice(&[0x4c, 0x89, 0xc0]);
    Ok(())
}
