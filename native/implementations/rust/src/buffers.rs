//! Process-lifetime packed byte literals and checked indexing.
use super::{flow::patch, functions::slot, imm32, Result};
pub(super) struct Literal {
    pub offset: usize,
    pub data: Vec<u8>,
}
pub(super) fn finish(code: &mut Vec<u8>, blobs: &[Literal]) -> Result<()> {
    for blob in blobs {
        let target = code.len();
        patch(code, blob.offset, target)?;
        code.extend_from_slice(&(blob.data.len() as u64).to_le_bytes());
        code.extend_from_slice(&blob.data);
    }
    Ok(())
}
pub(super) fn get(code: &mut Vec<u8>, buffer: usize, index: usize, fallback: usize) -> Result<()> {
    slot(code, 0x8b, 0, buffer);
    slot(code, 0x8b, 1, index);
    code.extend_from_slice(&[0x48, 0x8b, 0x10, 0x48, 0x85, 0xc9, 0x0f, 0x89]);
    let nonnegative = code.len();
    imm32(code, 0);
    code.extend_from_slice(&[0x48, 0x01, 0xd1]);
    let target = code.len();
    patch(code, nonnegative, target)?;
    code.extend_from_slice(&[0x48, 0x39, 0xd1, 0x0f, 0x83]);
    let outside = code.len();
    imm32(code, 0);
    code.extend_from_slice(&[0x48, 0x0f, 0xb6, 0x44, 0x08, 0x08, 0xe9]);
    let end = code.len();
    imm32(code, 0);
    let target = code.len();
    patch(code, outside, target)?;
    slot(code, 0x8b, 0, fallback);
    let target = code.len();
    patch(code, end, target)
}
