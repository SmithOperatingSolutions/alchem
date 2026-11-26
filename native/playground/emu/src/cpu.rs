//! An interpreter of the x86-64 instructions the native compiler and its
//! runtimes are made of (native/spec/arm64.md lists what the ARM64
//! translator takes, which is the same set). Instructions are decoded where
//! they stand each time they run; a system call stops the loop for the
//! kernel (linux.rs), and an instruction outside the set stops it with its
//! bytes, so that what is missing is plain.

use crate::mem::{Fault, Memory};

#[derive(Debug)]
pub enum Stop {
    Syscall,
    Fault(String),
    Budget,
}

pub const RAX: usize = 0;
pub const RCX: usize = 1;
pub const RDX: usize = 2;
pub const RBX: usize = 3;
pub const RSP: usize = 4;
pub const RSI: usize = 6;
pub const RDI: usize = 7;

#[derive(Default, Clone)]
pub struct Cpu {
    pub r: [u64; 16],
    pub rip: u64,
    pub cf: bool,
    pub pf: bool,
    pub zf: bool,
    pub sf: bool,
    pub of: bool,
    pub df: bool,
    pub xmm: [[u64; 2]; 16],
    pub fs: u64,
    pub gs: u64,
    pub steps: u64,
}

// The decoding of one instruction.
struct D {
    // The instruction's first 16 bytes, read at once (have: how many).
    buf: [u8; 16],
    have: u64,
    start: u64,
    rex: u8,
    w16: bool,
    rep: u8,
    seg: u64,
    pc: u64,
    vex_l: bool,
    vex_v: usize,
    vex: bool,
}

// A ModRM operand: a register, or an address (rip-relative ones are made
// once the instruction's length is known, by ea()).
#[derive(Clone, Copy)]
struct M {
    reg: usize,
    rm: usize,
    mem: bool,
    disp: u64,
    riprel: bool,
}

impl D {
    fn rex_w(&self) -> bool {
        self.rex & 8 != 0
    }
}

#[inline(always)]
fn mask(sz: u32) -> u64 {
    if sz == 64 {
        u64::MAX
    } else {
        (1u64 << sz) - 1
    }
}

#[inline(always)]
fn sign(sz: u32) -> u64 {
    1u64 << (sz - 1)
}

#[inline(always)]
fn sext(v: u64, sz: u32) -> i64 {
    if sz == 64 {
        v as i64
    } else {
        let s = 64 - sz;
        ((v << s) as i64) >> s
    }
}

fn f(v: u64) -> f64 {
    f64::from_bits(v)
}

fn fault(e: Fault) -> Stop {
    Stop::Fault(format!("segmentation fault at address {:#x}", e.0))
}

impl Cpu {
    #[inline(always)]
    fn fetch8(&mut self, mem: &mut Memory, d: &mut D) -> Result<u8, Stop> {
        let i = d.pc.wrapping_sub(d.start);
        let b = if i < d.have { d.buf[i as usize] } else { mem.read_u8(d.pc).map_err(fault)? };
        d.pc += 1;
        Ok(b)
    }

    #[inline(always)]
    fn fetch(&mut self, mem: &mut Memory, d: &mut D, sz: u32) -> Result<u64, Stop> {
        let n = sz as u64 / 8;
        let i = d.pc.wrapping_sub(d.start);
        let v = if i + n <= d.have {
            let mut b = [0u8; 8];
            b[..n as usize].copy_from_slice(&d.buf[i as usize..(i + n) as usize]);
            u64::from_le_bytes(b)
        } else {
            mem.read(d.pc, sz).map_err(fault)?
        };
        d.pc += n;
        Ok(v)
    }

    // The immediate of an instruction of operand size sz: 8, 16 or 32 bits,
    // the 32-bit one sign-extended for a 64-bit operand.
    fn imm(&mut self, mem: &mut Memory, d: &mut D, sz: u32) -> Result<u64, Stop> {
        Ok(match sz {
            8 => self.fetch(mem, d, 8)?,
            16 => self.fetch(mem, d, 16)?,
            32 => self.fetch(mem, d, 32)?,
            _ => sext(self.fetch(mem, d, 32)?, 32) as u64,
        })
    }

    fn imm8s(&mut self, mem: &mut Memory, d: &mut D) -> Result<u64, Stop> {
        Ok(sext(self.fetch(mem, d, 8)?, 8) as u64)
    }

    fn modrm(&mut self, mem: &mut Memory, d: &mut D) -> Result<M, Stop> {
        let b = self.fetch8(mem, d)?;
        let md = b >> 6;
        let reg = (((b >> 3) & 7) | ((d.rex & 4) << 1)) as usize;
        let rm_low = b & 7;
        if md == 3 {
            return Ok(M { reg, rm: (rm_low | ((d.rex & 1) << 3)) as usize, mem: false, disp: 0, riprel: false });
        }
        let mut addr: u64;
        let mut riprel = false;
        if rm_low == 4 {
            let sib = self.fetch8(mem, d)?;
            let scale = sib >> 6;
            let index = ((sib >> 3) & 7) | ((d.rex & 2) << 2);
            let base = (sib & 7) | ((d.rex & 1) << 3);
            addr = if index == 4 { 0 } else { self.r[index as usize] << scale };
            if (sib & 7) == 5 && md == 0 {
                addr = addr.wrapping_add(sext(self.fetch(mem, d, 32)?, 32) as u64);
            } else {
                addr = addr.wrapping_add(self.r[base as usize]);
            }
        } else if rm_low == 5 && md == 0 {
            riprel = true;
            addr = sext(self.fetch(mem, d, 32)?, 32) as u64;
        } else {
            addr = self.r[(rm_low | ((d.rex & 1) << 3)) as usize];
        }
        if md == 1 {
            addr = addr.wrapping_add(self.imm8s(mem, d)?);
        } else if md == 2 {
            addr = addr.wrapping_add(sext(self.fetch(mem, d, 32)?, 32) as u64);
        }
        Ok(M { reg, rm: 0, mem: true, disp: addr.wrapping_add(d.seg), riprel })
    }

    #[inline(always)]
    fn ea(&self, m: &M, d: &D) -> u64 {
        if m.riprel {
            m.disp.wrapping_add(d.pc)
        } else {
            m.disp
        }
    }

    #[inline(always)]
    pub fn get(&self, reg: usize, sz: u32, rex: u8) -> u64 {
        match sz {
            64 => self.r[reg],
            32 => self.r[reg] & 0xffff_ffff,
            16 => self.r[reg] & 0xffff,
            _ => {
                if rex == 0 && (4..8).contains(&reg) {
                    (self.r[reg - 4] >> 8) & 0xff
                } else {
                    self.r[reg] & 0xff
                }
            }
        }
    }

    #[inline(always)]
    pub fn set(&mut self, reg: usize, sz: u32, v: u64, rex: u8) {
        match sz {
            64 => self.r[reg] = v,
            32 => self.r[reg] = v & 0xffff_ffff,
            16 => self.r[reg] = (self.r[reg] & !0xffff) | (v & 0xffff),
            _ => {
                if rex == 0 && (4..8).contains(&reg) {
                    let r = reg - 4;
                    self.r[r] = (self.r[r] & !0xff00) | ((v & 0xff) << 8);
                } else {
                    self.r[reg] = (self.r[reg] & !0xff) | (v & 0xff);
                }
            }
        }
    }

    fn rd(&mut self, mem: &mut Memory, m: &M, d: &D, sz: u32) -> Result<u64, Stop> {
        if m.mem {
            mem.read(self.ea(m, d), sz).map_err(fault)
        } else {
            Ok(self.get(m.rm, sz, d.rex))
        }
    }

    fn wr(&mut self, mem: &mut Memory, m: &M, d: &D, sz: u32, v: u64) -> Result<(), Stop> {
        if m.mem {
            mem.write(self.ea(m, d), sz, v & mask(sz)).map_err(fault)
        } else {
            self.set(m.rm, sz, v, d.rex);
            Ok(())
        }
    }

    fn push(&mut self, mem: &mut Memory, v: u64) -> Result<(), Stop> {
        self.r[RSP] = self.r[RSP].wrapping_sub(8);
        mem.write(self.r[RSP], 64, v).map_err(fault)
    }

    fn pop(&mut self, mem: &mut Memory) -> Result<u64, Stop> {
        let v = mem.read(self.r[RSP], 64).map_err(fault)?;
        self.r[RSP] = self.r[RSP].wrapping_add(8);
        Ok(v)
    }

    #[inline(always)]
    fn szp(&mut self, res: u64, sz: u32) {
        self.zf = res & mask(sz) == 0;
        self.sf = res & sign(sz) != 0;
        self.pf = (res as u8).count_ones() % 2 == 0;
    }

    // The eight operations of the first opcode row: add or adc sbb and sub
    // xor cmp. The result, written unless the operation is cmp.
    fn alu(&mut self, op: u8, a: u64, b: u64, sz: u32) -> u64 {
        let m = mask(sz);
        let (a, b) = (a & m, b & m);
        let res;
        match op {
            0 | 2 => {
                let c = if op == 2 && self.cf { 1 } else { 0 };
                let wide = a as u128 + b as u128 + c as u128;
                res = (wide as u64) & m;
                self.cf = if sz == 64 { wide >> 64 != 0 } else { wide >> sz != 0 };
                self.of = (a ^ res) & (b ^ res) & sign(sz) != 0;
            }
            5 | 7 | 3 => {
                let c = if op == 3 && self.cf { 1u128 } else { 0 };
                res = (a.wrapping_sub(b).wrapping_sub(c as u64)) & m;
                self.cf = (a as u128) < (b as u128) + c;
                self.of = (a ^ b) & (a ^ res) & sign(sz) != 0;
            }
            1 => {
                res = a | b;
                self.cf = false;
                self.of = false;
            }
            4 => {
                res = a & b;
                self.cf = false;
                self.of = false;
            }
            _ => {
                res = a ^ b;
                self.cf = false;
                self.of = false;
            }
        }
        self.szp(res, sz);
        res
    }

    fn shift(&mut self, op: u8, a: u64, count: u64, sz: u32) -> u64 {
        let m = mask(sz);
        let a = a & m;
        let n = (count & if sz == 64 { 63 } else { 31 }) as u32;
        if n == 0 {
            return a;
        }
        let res;
        match op {
            0 => {
                let k = n % sz;
                res = if k == 0 { a } else { ((a << k) | (a >> (sz - k))) & m };
                self.cf = res & 1 != 0;
                self.of = ((res & sign(sz)) != 0) ^ self.cf;
                return res;
            }
            1 => {
                let k = n % sz;
                res = if k == 0 { a } else { ((a >> k) | (a << (sz - k))) & m };
                self.cf = res & sign(sz) != 0;
                self.of = ((res & sign(sz)) != 0) ^ ((res & (sign(sz) >> 1)) != 0);
                return res;
            }
            2 | 3 => {
                // rcl, rcr: through the carry, a bit at a time.
                let mut v = a;
                let mut c = self.cf;
                for _ in 0..(n % (sz + 1)) {
                    if op == 2 {
                        let out = v & sign(sz) != 0;
                        v = ((v << 1) | c as u64) & m;
                        c = out;
                    } else {
                        let out = v & 1 != 0;
                        v = (v >> 1) | if c { sign(sz) } else { 0 };
                        c = out;
                    }
                }
                self.cf = c;
                self.of = ((v & sign(sz)) != 0) ^ ((v & (sign(sz) >> 1)) != 0);
                return v;
            }
            4 | 6 => {
                res = if n >= 64 { 0 } else { (a << n) & m };
                self.cf = if n <= sz { (a >> (sz - n)) & 1 != 0 } else { false };
                self.of = ((res & sign(sz)) != 0) ^ self.cf;
            }
            5 => {
                res = a >> n;
                self.cf = (a >> (n - 1)) & 1 != 0;
                self.of = a & sign(sz) != 0;
            }
            _ => {
                let s = sext(a, sz);
                res = ((s >> n.min(63)) as u64) & m;
                self.cf = (s >> (n - 1).min(63)) & 1 != 0;
                self.of = false;
            }
        }
        self.szp(res, sz);
        res
    }

    pub fn cond(&self, cc: u8) -> bool {
        let v = match cc >> 1 {
            0 => self.of,
            1 => self.cf,
            2 => self.zf,
            3 => self.cf || self.zf,
            4 => self.sf,
            5 => self.pf,
            6 => self.sf != self.of,
            _ => self.zf || (self.sf != self.of),
        };
        if cc & 1 == 0 {
            v
        } else {
            !v
        }
    }

    fn osz(d: &D) -> u32 {
        if d.rex_w() {
            64
        } else if d.w16 {
            16
        } else {
            32
        }
    }

    fn xr(&self, i: usize) -> u64 {
        self.xmm[i][0]
    }

    // The low 64 bits of an xmm operand, from a register or memory.
    fn xrm64(&mut self, mem: &mut Memory, m: &M, d: &D) -> Result<u64, Stop> {
        if m.mem {
            mem.read(self.ea(m, d), 64).map_err(fault)
        } else {
            Ok(self.xmm[m.rm][0])
        }
    }

    fn xrm128(&mut self, mem: &mut Memory, m: &M, d: &D) -> Result<[u64; 2], Stop> {
        if m.mem {
            let a = self.ea(m, d);
            Ok([mem.read(a, 64).map_err(fault)?, mem.read(a + 8, 64).map_err(fault)?])
        } else {
            Ok(self.xmm[m.rm])
        }
    }

    fn xwm128(&mut self, mem: &mut Memory, m: &M, d: &D, v: [u64; 2]) -> Result<(), Stop> {
        if m.mem {
            let a = self.ea(m, d);
            mem.write(a, 64, v[0]).map_err(fault)?;
            mem.write(a + 8, 64, v[1]).map_err(fault)
        } else {
            self.xmm[m.rm] = v;
            Ok(())
        }
    }

    fn ucomi(&mut self, a: f64, b: f64) {
        self.of = false;
        self.sf = false;
        if a.is_nan() || b.is_nan() {
            self.zf = true;
            self.pf = true;
            self.cf = true;
        } else {
            self.pf = false;
            self.zf = a == b;
            self.cf = a < b;
        }
    }

    /// Runs until a system call, a fault or the end of budget instructions.
    pub fn run(&mut self, mem: &mut Memory, budget: u64) -> Stop {
        let mut left = budget;
        loop {
            if left == 0 {
                return Stop::Budget;
            }
            left -= 1;
            self.steps += 1;
            let start = self.rip;
            match self.step(mem) {
                Ok(true) => {}
                Ok(false) => return Stop::Syscall,
                Err(Stop::Fault(why)) => {
                    let bytes: Vec<String> = (0..12).filter_map(|i| mem.read_u8(start + i).ok()).map(|b| format!("{:02x}", b)).collect();
                    self.rip = start;
                    return Stop::Fault(format!("{} (at {:#x}: {})", why, start, bytes.join(" ")));
                }
                Err(other) => return other,
            }
        }
    }

    fn unsupported<T>(&self, what: &str) -> Result<T, Stop> {
        Err(Stop::Fault(format!("instruction not supported: {}", what)))
    }

    // One instruction. Ok(false) for syscall, which leaves rip after it.
    fn step(&mut self, mem: &mut Memory) -> Result<bool, Stop> {
        let mut d = D { buf: [0; 16], have: 0, start: self.rip, rex: 0, w16: false, rep: 0, seg: 0, pc: self.rip, vex_l: false, vex_v: 0, vex: false };
        if let (Ok(lo), Ok(hi)) = (mem.read(self.rip, 64), mem.read(self.rip + 8, 64)) {
            d.buf[..8].copy_from_slice(&lo.to_le_bytes());
            d.buf[8..].copy_from_slice(&hi.to_le_bytes());
            d.have = 16;
        }
        let mut op;
        loop {
            op = self.fetch8(mem, &mut d)?;
            match op {
                0x66 => d.w16 = true,
                0xf2 | 0xf3 => d.rep = op,
                0xf0 | 0x2e | 0x3e | 0x26 | 0x36 => {}
                0x64 => d.seg = self.fs,
                0x65 => d.seg = self.gs,
                _ => break,
            }
        }
        if (0x40..0x50).contains(&op) {
            d.rex = op;
            op = self.fetch8(mem, &mut d)?;
        }
        if op == 0xc4 || op == 0xc5 {
            return self.vex(mem, &mut d, op);
        }
        let sz = Self::osz(&d);
        match op {
            0x00..=0x3f if op & 7 < 6 && op != 0x0f && !(op & 0xe7 == 0x26) => {
                let kind = op >> 3;
                match op & 7 {
                    0 | 1 => {
                        let s = if op & 1 == 0 { 8 } else { sz };
                        let m = self.modrm(mem, &mut d)?;
                        let a = self.rd(mem, &m, &d, s)?;
                        let b = self.get(m.reg, s, d.rex);
                        let r = self.alu(kind, a, b, s);
                        if kind != 7 {
                            self.wr(mem, &m, &d, s, r)?;
                        }
                    }
                    2 | 3 => {
                        let s = if op & 1 == 0 { 8 } else { sz };
                        let m = self.modrm(mem, &mut d)?;
                        let b = self.rd(mem, &m, &d, s)?;
                        let a = self.get(m.reg, s, d.rex);
                        let r = self.alu(kind, a, b, s);
                        if kind != 7 {
                            self.set(m.reg, s, r, d.rex);
                        }
                    }
                    4 => {
                        let b = self.fetch(mem, &mut d, 8)?;
                        let a = self.get(RAX, 8, d.rex);
                        let r = self.alu(kind, a, b, 8);
                        if kind != 7 {
                            self.set(RAX, 8, r, d.rex);
                        }
                    }
                    _ => {
                        let b = self.imm(mem, &mut d, sz)?;
                        let a = self.get(RAX, sz, d.rex);
                        let r = self.alu(kind, a, b, sz);
                        if kind != 7 {
                            self.set(RAX, sz, r, d.rex);
                        }
                    }
                }
            }
            0x0f => return self.two(mem, &mut d),
            0x50..=0x57 => {
                let v = self.r[((op & 7) | ((d.rex & 1) << 3)) as usize];
                self.push(mem, v)?;
            }
            0x58..=0x5f => {
                let v = self.pop(mem)?;
                self.r[((op & 7) | ((d.rex & 1) << 3)) as usize] = v;
            }
            0x63 => {
                let m = self.modrm(mem, &mut d)?;
                let v = self.rd(mem, &m, &d, 32)?;
                self.set(m.reg, sz, sext(v, 32) as u64, d.rex);
            }
            0x68 => {
                let v = sext(self.fetch(mem, &mut d, 32)?, 32) as u64;
                self.push(mem, v)?;
            }
            0x6a => {
                let v = self.imm8s(mem, &mut d)?;
                self.push(mem, v)?;
            }
            0x69 | 0x6b => {
                let m = self.modrm(mem, &mut d)?;
                let b = if op == 0x69 { self.imm(mem, &mut d, sz)? } else { self.imm8s(mem, &mut d)? };
                let a = self.rd(mem, &m, &d, sz)?;
                let r = self.imul2(a, b, sz);
                self.set(m.reg, sz, r, d.rex);
            }
            0x70..=0x7f => {
                let rel = self.imm8s(mem, &mut d)?;
                if self.cond(op & 15) {
                    d.pc = d.pc.wrapping_add(rel);
                }
            }
            0x80 | 0x81 | 0x83 => {
                let s = if op == 0x80 { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let b = if op == 0x81 { self.imm(mem, &mut d, s)? } else if op == 0x83 { self.imm8s(mem, &mut d)? } else { self.fetch(mem, &mut d, 8)? };
                let a = self.rd(mem, &m, &d, s)?;
                let kind = (m.reg & 7) as u8;
                let r = self.alu(kind, a, b, s);
                if kind != 7 {
                    self.wr(mem, &m, &d, s, r)?;
                }
            }
            0x84 | 0x85 => {
                let s = if op == 0x84 { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let a = self.rd(mem, &m, &d, s)?;
                let b = self.get(m.reg, s, d.rex);
                self.alu(4, a, b, s);
            }
            0x86 | 0x87 => {
                let s = if op == 0x86 { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let a = self.rd(mem, &m, &d, s)?;
                let b = self.get(m.reg, s, d.rex);
                self.wr(mem, &m, &d, s, b)?;
                self.set(m.reg, s, a, d.rex);
            }
            0x88 | 0x89 => {
                let s = if op == 0x88 { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let v = self.get(m.reg, s, d.rex);
                self.wr(mem, &m, &d, s, v)?;
            }
            0x8a | 0x8b => {
                let s = if op == 0x8a { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let v = self.rd(mem, &m, &d, s)?;
                self.set(m.reg, s, v, d.rex);
            }
            0x8d => {
                let m = self.modrm(mem, &mut d)?;
                if !m.mem {
                    return self.unsupported("lea of a register");
                }
                let a = self.ea(&m, &d).wrapping_sub(d.seg);
                self.set(m.reg, sz, a, d.rex);
            }
            0x8f => {
                let m = self.modrm(mem, &mut d)?;
                let v = self.pop(mem)?;
                self.wr(mem, &m, &d, 64, v)?;
            }
            0x90 => {
                if d.rex & 1 != 0 {
                    let (a, b) = (self.r[RAX], self.r[8]);
                    self.set(RAX, sz, b, d.rex);
                    self.set(8, sz, a, d.rex);
                }
            }
            0x91..=0x97 => {
                let reg = ((op & 7) | ((d.rex & 1) << 3)) as usize;
                let (a, b) = (self.get(RAX, sz, d.rex), self.get(reg, sz, d.rex));
                self.set(RAX, sz, b, d.rex);
                self.set(reg, sz, a, d.rex);
            }
            0x98 => match sz {
                64 => self.r[RAX] = sext(self.r[RAX], 32) as u64,
                32 => self.r[RAX] = (sext(self.r[RAX], 16) as u64) & 0xffff_ffff,
                _ => self.set(RAX, 16, sext(self.r[RAX], 8) as u64, d.rex),
            },
            0x99 => {
                let neg = self.get(RAX, sz, d.rex) & sign(sz) != 0;
                self.set(RDX, sz, if neg { u64::MAX } else { 0 }, d.rex);
            }
            0xa8 => {
                let b = self.fetch(mem, &mut d, 8)?;
                let a = self.get(RAX, 8, d.rex);
                self.alu(4, a, b, 8);
            }
            0xa9 => {
                let b = self.imm(mem, &mut d, sz)?;
                let a = self.get(RAX, sz, d.rex);
                self.alu(4, a, b, sz);
            }
            0xa4 | 0xa5 | 0xaa | 0xab | 0xa6 | 0xa7 | 0xae | 0xaf | 0xac | 0xad => {
                let s = if op & 1 == 0 { 8 } else { sz };
                self.string(mem, &d, op, s)?;
            }
            0xb0..=0xb7 => {
                let v = self.fetch(mem, &mut d, 8)?;
                self.set(((op & 7) | ((d.rex & 1) << 3)) as usize, 8, v, d.rex);
            }
            0xb8..=0xbf => {
                let v = if d.rex_w() { self.fetch(mem, &mut d, 64)? } else { self.imm(mem, &mut d, sz)? };
                self.set(((op & 7) | ((d.rex & 1) << 3)) as usize, sz, v, d.rex);
            }
            0xc0 | 0xc1 | 0xd0 | 0xd1 | 0xd2 | 0xd3 => {
                let s = if op & 1 == 0 { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let count = match op {
                    0xc0 | 0xc1 => self.fetch(mem, &mut d, 8)?,
                    0xd0 | 0xd1 => 1,
                    _ => self.r[RCX] & 0xff,
                };
                let a = self.rd(mem, &m, &d, s)?;
                let r = self.shift((m.reg & 7) as u8, a, count, s);
                self.wr(mem, &m, &d, s, r)?;
            }
            0xc2 => {
                let n = self.fetch(mem, &mut d, 16)?;
                d.pc = self.pop(mem)?;
                self.r[RSP] = self.r[RSP].wrapping_add(n);
            }
            0xc3 => d.pc = self.pop(mem)?,
            0xc6 | 0xc7 => {
                let s = if op == 0xc6 { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let v = self.imm(mem, &mut d, s)?;
                self.wr(mem, &m, &d, s, v)?;
            }
            0xc9 => {
                self.r[RSP] = self.r[5];
                self.r[5] = self.pop(mem)?;
            }
            0xcc => return Err(Stop::Fault("trace/breakpoint trap".into())),
            0xe8 => {
                let rel = sext(self.fetch(mem, &mut d, 32)?, 32) as u64;
                let back = d.pc;
                self.push(mem, back)?;
                d.pc = d.pc.wrapping_add(rel);
            }
            0xe9 => {
                let rel = sext(self.fetch(mem, &mut d, 32)?, 32) as u64;
                d.pc = d.pc.wrapping_add(rel);
            }
            0xeb => {
                let rel = self.imm8s(mem, &mut d)?;
                d.pc = d.pc.wrapping_add(rel);
            }
            0xf4 => return Err(Stop::Fault("hlt".into())),
            0xf5 => self.cf = !self.cf,
            0xf8 => self.cf = false,
            0xf9 => self.cf = true,
            0xfc => self.df = false,
            0xfd => self.df = true,
            0xf6 | 0xf7 => {
                let s = if op == 0xf6 { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                let kind = m.reg & 7;
                if kind < 2 {
                    let b = self.imm(mem, &mut d, s)?;
                    let a = self.rd(mem, &m, &d, s)?;
                    self.alu(4, a, b, s);
                } else {
                    let a = self.rd(mem, &m, &d, s)?;
                    match kind {
                        2 => self.wr(mem, &m, &d, s, !a)?,
                        3 => {
                            let r = self.alu(5, 0, a, s);
                            self.cf = a & mask(s) != 0;
                            self.wr(mem, &m, &d, s, r)?;
                        }
                        _ => self.muldiv(kind, a, s, d.rex)?,
                    }
                }
            }
            0xfe | 0xff => {
                let s = if op == 0xfe { 8 } else { sz };
                let m = self.modrm(mem, &mut d)?;
                match m.reg & 7 {
                    0 | 1 => {
                        let a = self.rd(mem, &m, &d, s)?;
                        let c = self.cf;
                        let r = self.alu(if m.reg & 7 == 0 { 0 } else { 5 }, a, 1, s);
                        self.cf = c;
                        self.wr(mem, &m, &d, s, r)?;
                    }
                    2 => {
                        let t = self.rd(mem, &m, &d, 64)?;
                        let back = d.pc;
                        self.push(mem, back)?;
                        d.pc = t;
                    }
                    4 => d.pc = self.rd(mem, &m, &d, 64)?,
                    6 => {
                        let v = self.rd(mem, &m, &d, 64)?;
                        self.push(mem, v)?;
                    }
                    _ => return self.unsupported("ff /3 or /5"),
                }
            }
            _ => return self.unsupported(&format!("opcode {:#04x}", op)),
        }
        self.rip = d.pc;
        Ok(true)
    }

    fn imul2(&mut self, a: u64, b: u64, sz: u32) -> u64 {
        let p = sext(a, sz) as i128 * sext(b, sz) as i128;
        let r = (p as u64) & mask(sz);
        let over = sext(r, sz) as i128 != p;
        self.cf = over;
        self.of = over;
        self.szp(r, sz);
        r
    }

    fn muldiv(&mut self, kind: usize, src: u64, sz: u32, rex: u8) -> Result<(), Stop> {
        let m = mask(sz);
        let lo = self.get(RAX, sz, rex);
        let hi = if sz == 8 { (self.r[RAX] >> 8) & 0xff } else { self.get(RDX, sz, rex) };
        let put = |cpu: &mut Cpu, low: u64, high: u64| {
            if sz == 8 {
                cpu.r[RAX] = (cpu.r[RAX] & !0xffff) | (low & 0xff) | ((high & 0xff) << 8);
            } else {
                cpu.set(RAX, sz, low, rex);
                cpu.set(RDX, sz, high, rex);
            }
        };
        match kind {
            4 => {
                let p = (lo as u128) * (src & m) as u128;
                let (l, h) = ((p as u64) & m, ((p >> sz) as u64) & m);
                put(self, l, h);
                self.cf = h != 0;
                self.of = h != 0;
            }
            5 => {
                let p = sext(lo, sz) as i128 * sext(src, sz) as i128;
                let l = (p as u64) & m;
                let h = ((p >> sz) as u64) & m;
                put(self, l, h);
                let over = sext(l, sz) as i128 != p;
                self.cf = over;
                self.of = over;
            }
            6 => {
                let n = ((hi as u128) << sz) | lo as u128;
                let v = (src & m) as u128;
                if v == 0 {
                    return Err(Stop::Fault("integer divide by zero".into()));
                }
                let q = n / v;
                if q > m as u128 {
                    return Err(Stop::Fault("integer divide overflow".into()));
                }
                put(self, q as u64, (n % v) as u64);
            }
            _ => {
                let n = (((hi as u128) << sz) | lo as u128) as i128;
                let n = if sz == 64 { n } else { (n << (128 - 2 * sz)) >> (128 - 2 * sz) };
                let v = sext(src, sz) as i128;
                if v == 0 {
                    return Err(Stop::Fault("integer divide by zero".into()));
                }
                let q = n.wrapping_div(v);
                let lim = 1i128 << (sz - 1);
                if q >= lim || q < -lim {
                    return Err(Stop::Fault("integer divide overflow".into()));
                }
                put(self, (q as u64) & m, (n.wrapping_rem(v) as u64) & m);
            }
        }
        Ok(())
    }

    // movs, stos, cmps, scas and lods, with rep, repe and repne.
    fn string(&mut self, mem: &mut Memory, d: &D, op: u8, sz: u32) -> Result<(), Stop> {
        let step = (sz / 8) as u64;
        let delta = if self.df { step.wrapping_neg() } else { step };
        let counted = d.rep != 0;
        // A forward rep movsb or stosb is done as one copy or fill.
        if counted && !self.df && sz == 8 && (op == 0xa4 || op == 0xaa) {
            let n = self.r[RCX];
            if op == 0xa4 {
                mem.copy_within(self.r[RDI], self.r[RSI], n).map_err(fault)?;
                self.r[RSI] = self.r[RSI].wrapping_add(n);
            } else {
                mem.fill(self.r[RDI], self.r[RAX] as u8, n).map_err(fault)?;
            }
            self.r[RDI] = self.r[RDI].wrapping_add(n);
            self.r[RCX] = 0;
            return Ok(());
        }
        loop {
            if counted && self.r[RCX] == 0 {
                return Ok(());
            }
            match op {
                0xa4 | 0xa5 => {
                    let v = mem.read(self.r[RSI], sz).map_err(fault)?;
                    mem.write(self.r[RDI], sz, v).map_err(fault)?;
                    self.r[RSI] = self.r[RSI].wrapping_add(delta);
                    self.r[RDI] = self.r[RDI].wrapping_add(delta);
                }
                0xaa | 0xab => {
                    mem.write(self.r[RDI], sz, self.r[RAX] & mask(sz)).map_err(fault)?;
                    self.r[RDI] = self.r[RDI].wrapping_add(delta);
                }
                0xac | 0xad => {
                    let v = mem.read(self.r[RSI], sz).map_err(fault)?;
                    self.set(RAX, sz, v, d.rex);
                    self.r[RSI] = self.r[RSI].wrapping_add(delta);
                }
                0xa6 | 0xa7 => {
                    let a = mem.read(self.r[RSI], sz).map_err(fault)?;
                    let b = mem.read(self.r[RDI], sz).map_err(fault)?;
                    self.alu(7, a, b, sz);
                    self.r[RSI] = self.r[RSI].wrapping_add(delta);
                    self.r[RDI] = self.r[RDI].wrapping_add(delta);
                }
                _ => {
                    let b = mem.read(self.r[RDI], sz).map_err(fault)?;
                    let a = self.get(RAX, sz, d.rex);
                    self.alu(7, a, b, sz);
                    self.r[RDI] = self.r[RDI].wrapping_add(delta);
                }
            }
            if !counted {
                return Ok(());
            }
            self.r[RCX] = self.r[RCX].wrapping_sub(1);
            let compares = matches!(op, 0xa6 | 0xa7 | 0xae | 0xaf);
            if compares && ((d.rep == 0xf3 && !self.zf) || (d.rep == 0xf2 && self.zf)) {
                return Ok(());
            }
        }
    }

    fn two(&mut self, mem: &mut Memory, d: &mut D) -> Result<bool, Stop> {
        let op = self.fetch8(mem, d)?;
        let sz = Self::osz(d);
        match op {
            0x05 => {
                self.rip = d.pc;
                return Ok(false);
            }
            0x0b => return Err(Stop::Fault("illegal instruction (ud2)".into())),
            0x0d | 0x18..=0x1f => {
                // prefetch, nop Ev, endbr64.
                if op == 0x1e && d.rep == 0xf3 {
                    self.fetch8(mem, d)?;
                } else {
                    self.modrm(mem, d)?;
                }
            }
            0x10 | 0x11 => {
                let m = self.modrm(mem, d)?;
                match (d.rep, op) {
                    (0xf2, 0x10) => {
                        let v = self.xrm64(mem, &m, d)?;
                        if m.mem {
                            self.xmm[m.reg] = [v, 0];
                        } else {
                            self.xmm[m.reg][0] = v;
                        }
                    }
                    (0xf2, _) => {
                        let v = self.xr(m.reg);
                        if m.mem {
                            mem.write(self.ea(&m, d), 64, v).map_err(fault)?;
                        } else {
                            self.xmm[m.rm][0] = v;
                        }
                    }
                    (0xf3, 0x10) => {
                        let v = if m.mem { mem.read(self.ea(&m, d), 32).map_err(fault)? } else { self.xmm[m.rm][0] & 0xffff_ffff };
                        if m.mem {
                            self.xmm[m.reg] = [v, 0];
                        } else {
                            self.xmm[m.reg][0] = (self.xmm[m.reg][0] & !0xffff_ffff) | v;
                        }
                    }
                    (0xf3, _) => {
                        let v = self.xr(m.reg) & 0xffff_ffff;
                        if m.mem {
                            mem.write(self.ea(&m, d), 32, v).map_err(fault)?;
                        } else {
                            self.xmm[m.rm][0] = (self.xmm[m.rm][0] & !0xffff_ffff) | v;
                        }
                    }
                    (_, 0x10) => {
                        let v = self.xrm128(mem, &m, d)?;
                        self.xmm[m.reg] = v;
                    }
                    _ => {
                        let v = self.xmm[m.reg];
                        self.xwm128(mem, &m, d, v)?;
                    }
                }
            }
            0x28 | 0x29 | 0x6f | 0x7f => {
                let m = self.modrm(mem, d)?;
                if op == 0x28 || op == 0x6f {
                    let v = self.xrm128(mem, &m, d)?;
                    self.xmm[m.reg] = v;
                } else {
                    let v = self.xmm[m.reg];
                    self.xwm128(mem, &m, d, v)?;
                }
            }
            0x2a => {
                let m = self.modrm(mem, d)?;
                let s = if d.rex_w() { 64 } else { 32 };
                let v = sext(self.rd(mem, &m, d, s)?, s);
                self.xmm[m.reg][0] = (v as f64).to_bits();
            }
            0x2c | 0x2d => {
                let m = self.modrm(mem, d)?;
                let x = f(self.xrm64(mem, &m, d)?);
                let s = if d.rex_w() { 64 } else { 32 };
                let y = if op == 0x2c { x.trunc() } else { round_even(x) };
                let lim = if s == 64 { 9.223372036854775807e18 } else { 2147483648.0 };
                let v = if y.is_nan() || y >= lim || y < -lim { sign(s) } else { (y as i64 as u64) & mask(s) };
                self.set(m.reg, s, v, d.rex);
            }
            0x2e | 0x2f => {
                let m = self.modrm(mem, d)?;
                let b = f(self.xrm64(mem, &m, d)?);
                let a = f(self.xr(m.reg));
                self.ucomi(a, b);
            }
            0x31 => {
                let t = self.steps;
                self.r[RAX] = t & 0xffff_ffff;
                self.r[RDX] = t >> 32;
            }
            0x40..=0x4f => {
                let m = self.modrm(mem, d)?;
                let v = self.rd(mem, &m, d, sz)?;
                if self.cond(op & 15) {
                    self.set(m.reg, sz, v, d.rex);
                } else if sz == 32 {
                    let keep = self.r[m.reg] & 0xffff_ffff;
                    self.r[m.reg] = keep;
                }
            }
            0x51 | 0x58 | 0x59 | 0x5c | 0x5d | 0x5e | 0x5f if d.rep == 0xf2 => {
                let m = self.modrm(mem, d)?;
                let b = f(self.xrm64(mem, &m, d)?);
                let a = f(self.xr(m.reg));
                let r = match op {
                    0x51 => b.sqrt(),
                    0x58 => a + b,
                    0x59 => a * b,
                    0x5c => a - b,
                    0x5d => {
                        if a < b {
                            a
                        } else {
                            b
                        }
                    }
                    0x5e => a / b,
                    _ => {
                        if a > b {
                            a
                        } else {
                            b
                        }
                    }
                };
                self.xmm[m.reg][0] = r.to_bits();
            }
            0x5a => {
                let m = self.modrm(mem, d)?;
                if d.rep == 0xf2 {
                    let x = f(self.xrm64(mem, &m, d)?);
                    self.xmm[m.reg][0] = (self.xmm[m.reg][0] & !0xffff_ffff) | (x as f32).to_bits() as u64;
                } else if d.rep == 0xf3 {
                    let x = if m.mem { mem.read(self.ea(&m, d), 32).map_err(fault)? } else { self.xmm[m.rm][0] & 0xffff_ffff };
                    self.xmm[m.reg][0] = (f32::from_bits(x as u32) as f64).to_bits();
                } else {
                    return self.unsupported("cvtps2pd");
                }
            }
            0x54..=0x57 | 0xdb | 0xdf | 0xeb | 0xef | 0xd4 | 0xfb | 0x6c | 0x6d | 0x14 | 0x15 | 0xfe | 0xfa | 0x74 | 0x75 | 0x76 | 0xd7 => {
                let m = self.modrm(mem, d)?;
                if op == 0xd7 {
                    let v = self.xmm[m.rm];
                    let mut bits = 0u64;
                    for i in 0..16 {
                        let byte = (v[i / 8] >> ((i % 8) * 8)) & 0xff;
                        bits |= ((byte >> 7) & 1) << i;
                    }
                    self.set(m.reg, 32, bits, d.rex);
                } else {
                    let b = self.xrm128(mem, &m, d)?;
                    let a = self.xmm[m.reg];
                    self.xmm[m.reg] = packed(op, a, b);
                }
            }
            0x6e => {
                let m = self.modrm(mem, d)?;
                let s = if d.rex_w() { 64 } else { 32 };
                let v = self.rd(mem, &m, d, s)?;
                self.xmm[m.reg] = [v, 0];
            }
            0x7e => {
                let m = self.modrm(mem, d)?;
                if d.rep == 0xf3 {
                    let v = self.xrm64(mem, &m, d)?;
                    self.xmm[m.reg] = [v, 0];
                } else {
                    let s = if d.rex_w() { 64 } else { 32 };
                    let v = self.xr(m.reg) & mask(s);
                    self.wr(mem, &m, d, s, v)?;
                }
            }
            0xd6 => {
                let m = self.modrm(mem, d)?;
                let v = self.xr(m.reg);
                if m.mem {
                    mem.write(self.ea(&m, d), 64, v).map_err(fault)?;
                } else {
                    self.xmm[m.rm] = [v, 0];
                }
            }
            0x70 => {
                let m = self.modrm(mem, d)?;
                let k = self.fetch(mem, d, 8)? as u32;
                let v = self.xrm128(mem, &m, d)?;
                let lane = |i: u32| (v[(i / 2) as usize] >> ((i % 2) * 32)) & 0xffff_ffff;
                let pick = |j: u32| lane((k >> (2 * j)) & 3);
                self.xmm[m.reg] = [pick(0) | (pick(1) << 32), pick(2) | (pick(3) << 32)];
            }
            0x73 => {
                let m = self.modrm(mem, d)?;
                let n = self.fetch(mem, d, 8)? as u32;
                let v = self.xmm[m.rm];
                let wide = (v[1] as u128) << 64 | v[0] as u128;
                let r = match m.reg & 7 {
                    2 => {
                        if n > 63 {
                            [0, 0]
                        } else {
                            [v[0] >> n, v[1] >> n]
                        }
                    }
                    3 => {
                        let w = if n > 15 { 0 } else { wide >> (8 * n) };
                        [w as u64, (w >> 64) as u64]
                    }
                    6 => {
                        if n > 63 {
                            [0, 0]
                        } else {
                            [v[0] << n, v[1] << n]
                        }
                    }
                    7 => {
                        let w = if n > 15 { 0 } else { wide << (8 * n) };
                        [w as u64, (w >> 64) as u64]
                    }
                    _ => return self.unsupported("0f 73"),
                };
                self.xmm[m.rm] = r;
            }
            0x80..=0x8f => {
                let rel = sext(self.fetch(mem, d, 32)?, 32) as u64;
                if self.cond(op & 15) {
                    d.pc = d.pc.wrapping_add(rel);
                }
            }
            0x90..=0x9f => {
                let m = self.modrm(mem, d)?;
                let v = self.cond(op & 15) as u64;
                self.wr(mem, &m, d, 8, v)?;
            }
            0xa2 => {
                self.r[RAX] = 0;
                self.r[RBX] = 0;
                self.r[RCX] = 0;
                self.r[RDX] = 0;
            }
            0xa3 | 0xab | 0xb3 | 0xbb | 0xba => {
                let m = self.modrm(mem, d)?;
                let (kind, bit) = if op == 0xba {
                    let n = self.fetch(mem, d, 8)?;
                    ((m.reg & 7) as u8 - 4, n)
                } else {
                    (((op >> 3) & 3) as u8, self.get(m.reg, sz, d.rex))
                };
                let (addr_shift, n): (i64, u64) = if m.mem && op != 0xba { ((sext(bit, sz) >> sz.trailing_zeros()) * (sz as i64 / 8), bit & (sz as u64 - 1)) } else { (0, bit & (sz as u64 - 1)) };
                let mm = if m.mem { M { disp: m.disp.wrapping_add(addr_shift as u64), ..m } } else { m };
                let v = self.rd(mem, &mm, d, sz)?;
                self.cf = (v >> n) & 1 != 0;
                let r = match kind {
                    0 => None,
                    1 => Some(v | (1 << n)),
                    2 => Some(v & !(1 << n)),
                    _ => Some(v ^ (1 << n)),
                };
                if let Some(r) = r {
                    self.wr(mem, &mm, d, sz, r)?;
                }
            }
            0xa4 | 0xa5 | 0xac | 0xad => {
                let m = self.modrm(mem, d)?;
                let n = if op & 1 == 0 { self.fetch(mem, d, 8)? } else { self.r[RCX] & 0xff };
                let n = (n & if sz == 64 { 63 } else { 31 }) as u32;
                let a = self.rd(mem, &m, d, sz)?;
                let b = self.get(m.reg, sz, d.rex);
                if n != 0 {
                    let r = if op < 0xac {
                        self.cf = (a >> (sz - n)) & 1 != 0;
                        ((a << n) | (b >> (sz - n))) & mask(sz)
                    } else {
                        self.cf = (a >> (n - 1)) & 1 != 0;
                        ((a >> n) | (b << (sz - n))) & mask(sz)
                    };
                    self.szp(r, sz);
                    self.of = false;
                    self.wr(mem, &m, d, sz, r)?;
                }
            }
            0xaf => {
                let m = self.modrm(mem, d)?;
                let b = self.rd(mem, &m, d, sz)?;
                let a = self.get(m.reg, sz, d.rex);
                let r = self.imul2(a, b, sz);
                self.set(m.reg, sz, r, d.rex);
            }
            0xb0 | 0xb1 => {
                let s = if op == 0xb0 { 8 } else { sz };
                let m = self.modrm(mem, d)?;
                let v = self.rd(mem, &m, d, s)?;
                let a = self.get(RAX, s, d.rex);
                self.alu(7, a, v, s);
                if self.zf {
                    let n = self.get(m.reg, s, d.rex);
                    self.wr(mem, &m, d, s, n)?;
                } else {
                    self.set(RAX, s, v, d.rex);
                }
            }
            0xc0 | 0xc1 => {
                let s = if op == 0xc0 { 8 } else { sz };
                let m = self.modrm(mem, d)?;
                let a = self.rd(mem, &m, d, s)?;
                let b = self.get(m.reg, s, d.rex);
                let r = self.alu(0, a, b, s);
                self.set(m.reg, s, a, d.rex);
                self.wr(mem, &m, d, s, r)?;
            }
            0xb6 | 0xb7 | 0xbe | 0xbf => {
                let s = if op & 1 == 0 { 8 } else { 16 };
                let m = self.modrm(mem, d)?;
                let v = self.rd(mem, &m, d, s)?;
                let v = if op >= 0xbe { (sext(v, s) as u64) & mask(sz) } else { v };
                self.set(m.reg, sz, v, d.rex);
            }
            0xb8 | 0xbc | 0xbd => {
                let m = self.modrm(mem, d)?;
                let v = self.rd(mem, &m, d, sz)?;
                let r = match (op, d.rep) {
                    (0xb8, 0xf3) => v.count_ones() as u64,
                    (0xbc, 0xf3) => {
                        self.cf = v == 0;
                        if v == 0 {
                            sz as u64
                        } else {
                            v.trailing_zeros() as u64
                        }
                    }
                    (0xbd, 0xf3) => {
                        self.cf = v == 0;
                        let lz = if v == 0 { sz } else { v.leading_zeros() - (64 - sz) };
                        lz as u64
                    }
                    (0xbc, _) => {
                        if v == 0 {
                            self.zf = true;
                            self.rip = d.pc;
                            return Ok(true);
                        }
                        v.trailing_zeros() as u64
                    }
                    (0xbd, _) => {
                        if v == 0 {
                            self.zf = true;
                            self.rip = d.pc;
                            return Ok(true);
                        }
                        63 - v.leading_zeros() as u64
                    }
                    _ => return self.unsupported("0f b8"),
                };
                self.zf = if op == 0xb8 || d.rep == 0xf3 { r == 0 } else { false };
                if op == 0xb8 {
                    self.cf = false;
                    self.of = false;
                    self.sf = false;
                    self.pf = false;
                }
                self.set(m.reg, sz, r, d.rex);
            }
            0xc2 => {
                let m = self.modrm(mem, d)?;
                let k = self.fetch(mem, d, 8)?;
                let b = f(self.xrm64(mem, &m, d)?);
                let a = f(self.xr(m.reg));
                let unord = a.is_nan() || b.is_nan();
                let t = match k & 7 {
                    0 => !unord && a == b,
                    1 => !unord && a < b,
                    2 => !unord && a <= b,
                    3 => unord,
                    4 => unord || a != b,
                    5 => unord || !(a < b),
                    6 => unord || !(a <= b),
                    _ => !unord,
                };
                if d.rep == 0xf2 {
                    self.xmm[m.reg][0] = if t { u64::MAX } else { 0 };
                } else {
                    return self.unsupported("cmpps");
                }
            }
            0xc6 => {
                let m = self.modrm(mem, d)?;
                let k = self.fetch(mem, d, 8)?;
                let b = self.xrm128(mem, &m, d)?;
                let a = self.xmm[m.reg];
                if d.w16 {
                    self.xmm[m.reg] = [a[(k & 1) as usize], b[((k >> 1) & 1) as usize]];
                } else {
                    return self.unsupported("shufps");
                }
            }
            0xc8..=0xcf => {
                let reg = ((op & 7) | ((d.rex & 1) << 3)) as usize;
                if sz == 64 {
                    self.r[reg] = self.r[reg].swap_bytes();
                } else {
                    self.r[reg] = (self.r[reg] as u32).swap_bytes() as u64;
                }
            }
            0x38 => return self.three38(mem, d),
            0x3a => return self.three3a(mem, d),
            _ => return self.unsupported(&format!("opcode 0f {:02x}", op)),
        }
        self.rip = d.pc;
        Ok(true)
    }

    fn three38(&mut self, mem: &mut Memory, d: &mut D) -> Result<bool, Stop> {
        let op = self.fetch8(mem, d)?;
        let m = self.modrm(mem, d)?;
        let b = self.xrm128(mem, &m, d)?;
        let a = self.xmm[m.reg];
        self.xmm[m.reg] = match op {
            0x00 => pshufb(a, b),
            0xdc => aes(a, b, false, false),
            0xdd => aes(a, b, true, false),
            0xde => aes(a, b, false, true),
            0xdf => aes(a, b, true, true),
            _ => return self.unsupported(&format!("opcode 0f 38 {:02x}", op)),
        };
        self.rip = d.pc;
        Ok(true)
    }

    fn three3a(&mut self, mem: &mut Memory, d: &mut D) -> Result<bool, Stop> {
        let op = self.fetch8(mem, d)?;
        let m = self.modrm(mem, d)?;
        let k = self.fetch(mem, d, 8)?;
        match op {
            0x0b => {
                let x = f(self.xrm64(mem, &m, d)?);
                let r = if k & 4 != 0 {
                    round_even(x)
                } else {
                    match k & 3 {
                        0 => round_even(x),
                        1 => x.floor(),
                        2 => x.ceil(),
                        _ => x.trunc(),
                    }
                };
                self.xmm[m.reg][0] = r.to_bits();
            }
            0x16 => {
                let v = self.xmm[m.reg];
                let s = if d.rex_w() { 64 } else { 32 };
                let r = if s == 64 { v[(k & 1) as usize] } else { (v[((k >> 1) & 1) as usize] >> ((k & 1) * 32)) & 0xffff_ffff };
                self.wr(mem, &m, d, s, r)?;
            }
            0x22 => {
                let s = if d.rex_w() { 64 } else { 32 };
                let v = self.rd(mem, &m, d, s)?;
                if s == 64 {
                    self.xmm[m.reg][(k & 1) as usize] = v;
                } else {
                    let i = ((k >> 1) & 1) as usize;
                    let sh = (k & 1) * 32;
                    self.xmm[m.reg][i] = (self.xmm[m.reg][i] & !(0xffff_ffff << sh)) | (v << sh);
                }
            }
            0x0f => {
                let b = self.xrm128(mem, &m, d)?;
                let a = self.xmm[m.reg];
                let wide = ((a[1] as u128) << 64 | a[0] as u128, (b[1] as u128) << 64 | b[0] as u128);
                let n = k as u32;
                let r: u128 = if n >= 32 {
                    0
                } else if n >= 16 {
                    wide.0 >> (8 * (n - 16))
                } else if n == 0 {
                    wide.1
                } else {
                    (wide.1 >> (8 * n)) | (wide.0 << (8 * (16 - n)))
                };
                self.xmm[m.reg] = [r as u64, (r >> 64) as u64];
            }
            0x44 => {
                let b = self.xrm128(mem, &m, d)?;
                let a = self.xmm[m.reg];
                let x = a[(k & 1) as usize];
                let y = b[((k >> 4) & 1) as usize];
                let mut r: u128 = 0;
                for i in 0..64 {
                    if (y >> i) & 1 != 0 {
                        r ^= (x as u128) << i;
                    }
                }
                self.xmm[m.reg] = [r as u64, (r >> 64) as u64];
            }
            0xdf => {
                let b = self.xrm128(mem, &m, d)?;
                self.xmm[m.reg] = aes_keygen(b, k as u8);
            }
            _ => return self.unsupported(&format!("opcode 0f 3a {:02x}", op)),
        }
        self.rip = d.pc;
        Ok(true)
    }

    // The VEX instructions the runtimes use: the scalar double arithmetic
    // and fused multiply-adds of the float runtime.
    fn vex(&mut self, mem: &mut Memory, d: &mut D, first: u8) -> Result<bool, Stop> {
        let b1 = self.fetch8(mem, d)?;
        let (map, w, vvvv, l, pp);
        if first == 0xc5 {
            d.rex = if b1 & 0x80 == 0 { 0x44 } else { 0x40 };
            map = 1;
            w = false;
            vvvv = (!b1 >> 3) & 15;
            l = b1 & 4 != 0;
            pp = b1 & 3;
        } else {
            let b2 = self.fetch8(mem, d)?;
            let r = if b1 & 0x80 == 0 { 4 } else { 0 };
            let x = if b1 & 0x40 == 0 { 2 } else { 0 };
            let b = if b1 & 0x20 == 0 { 1 } else { 0 };
            w = b2 & 0x80 != 0;
            d.rex = 0x40 | r | x | b | if w { 8 } else { 0 };
            map = b1 & 31;
            vvvv = (!b2 >> 3) & 15;
            l = b2 & 4 != 0;
            pp = b2 & 3;
        }
        d.vex = true;
        d.vex_l = l;
        d.vex_v = vvvv as usize;
        let op = self.fetch8(mem, d)?;
        let m = self.modrm(mem, d)?;
        let v = d.vex_v;
        match (map, pp, op) {
            (1, 3, 0x58) | (1, 3, 0x59) | (1, 3, 0x5c) | (1, 3, 0x5e) | (1, 3, 0x51) | (1, 3, 0x5d) | (1, 3, 0x5f) => {
                let b = f(self.xrm64(mem, &m, d)?);
                let a = f(self.xmm[v][0]);
                let r = match op {
                    0x58 => a + b,
                    0x59 => a * b,
                    0x5c => a - b,
                    0x5e => a / b,
                    0x51 => b.sqrt(),
                    0x5d => {
                        if a < b {
                            a
                        } else {
                            b
                        }
                    }
                    _ => {
                        if a > b {
                            a
                        } else {
                            b
                        }
                    }
                };
                self.xmm[m.reg] = [r.to_bits(), self.xmm[v][1]];
            }
            (2, 1, 0x99) | (2, 1, 0xa9) | (2, 1, 0xb9) | (2, 1, 0x9b) | (2, 1, 0xab) | (2, 1, 0xbb) | (2, 1, 0x9d) | (2, 1, 0xad) | (2, 1, 0xbd) | (2, 1, 0x9f) | (2, 1, 0xaf) | (2, 1, 0xbf) if w => {
                // vfmadd/vfmsub/vfnmadd/vfnmsub 132, 213, 231 sd.
                let x1 = f(self.xmm[m.reg][0]);
                let x2 = f(self.xmm[v][0]);
                let x3 = f(self.xrm64(mem, &m, d)?);
                let (a, b, c) = match op & 0xf0 {
                    0x90 => (x1, x3, x2),
                    0xa0 => (x2, x1, x3),
                    _ => (x2, x3, x1),
                };
                let r = match op & 0x0f {
                    0x09 => a.mul_add(b, c),
                    0x0b => a.mul_add(b, -c),
                    0x0d => (-a).mul_add(b, c),
                    _ => (-a).mul_add(b, -c),
                };
                self.xmm[m.reg][0] = r.to_bits();
            }
            _ => return self.unsupported(&format!("VEX map {} pp {} opcode {:02x}", map, pp, op)),
        }
        self.rip = d.pc;
        Ok(true)
    }
}

fn round_even(x: f64) -> f64 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 {
        2.0 * (x / 2.0).round_ties_even_compat()
    } else {
        r
    }
}

trait TiesEven {
    fn round_ties_even_compat(self) -> f64;
}

impl TiesEven for f64 {
    fn round_ties_even_compat(self) -> f64 {
        let r = self.round();
        if (self - self.trunc()).abs() == 0.5 && r % 2.0 != 0.0 {
            r - self.signum()
        } else {
            r
        }
    }
}

fn lanes8(v: [u64; 2]) -> [u8; 16] {
    let mut out = [0u8; 16];
    out[..8].copy_from_slice(&v[0].to_le_bytes());
    out[8..].copy_from_slice(&v[1].to_le_bytes());
    out
}

fn from8(b: [u8; 16]) -> [u64; 2] {
    [u64::from_le_bytes(b[..8].try_into().unwrap()), u64::from_le_bytes(b[8..].try_into().unwrap())]
}

fn packed(op: u8, a: [u64; 2], b: [u64; 2]) -> [u64; 2] {
    match op {
        0x54 | 0xdb => [a[0] & b[0], a[1] & b[1]],
        0x55 | 0xdf => [!a[0] & b[0], !a[1] & b[1]],
        0x56 | 0xeb => [a[0] | b[0], a[1] | b[1]],
        0x57 | 0xef => [a[0] ^ b[0], a[1] ^ b[1]],
        0xd4 => [a[0].wrapping_add(b[0]), a[1].wrapping_add(b[1])],
        0xfb => [a[0].wrapping_sub(b[0]), a[1].wrapping_sub(b[1])],
        0x6c | 0x14 => [a[0], b[0]],
        0x6d | 0x15 => [a[1], b[1]],
        0xfe | 0xfa => {
            let lane = |v: [u64; 2], i: usize| ((v[i / 2] >> ((i % 2) * 32)) & 0xffff_ffff) as u32;
            let mut out = [0u64; 2];
            for i in 0..4 {
                let r = if op == 0xfe { lane(a, i).wrapping_add(lane(b, i)) } else { lane(a, i).wrapping_sub(lane(b, i)) };
                out[i / 2] |= (r as u64) << ((i % 2) * 32);
            }
            out
        }
        _ => {
            // pcmpeqb, pcmpeqw, pcmpeqd.
            let (x, y) = (lanes8(a), lanes8(b));
            let width = match op {
                0x74 => 1,
                0x75 => 2,
                _ => 4,
            };
            let mut out = [0u8; 16];
            for i in (0..16).step_by(width) {
                let same = x[i..i + width] == y[i..i + width];
                for j in 0..width {
                    out[i + j] = if same { 0xff } else { 0 };
                }
            }
            from8(out)
        }
    }
}

fn pshufb(a: [u64; 2], b: [u64; 2]) -> [u64; 2] {
    let (x, k) = (lanes8(a), lanes8(b));
    let mut out = [0u8; 16];
    for i in 0..16 {
        out[i] = if k[i] & 0x80 != 0 { 0 } else { x[(k[i] & 15) as usize] };
    }
    from8(out)
}

// AES rounds, for the TLS runtime: enc/dec, last or not.
const SBOX: [u8; 256] = {
    let mut s = [0u8; 256];
    let mut p: u8 = 1;
    let mut q: u8 = 1;
    loop {
        // p * 3
        p = p ^ (p << 1) ^ if p & 0x80 != 0 { 0x1b } else { 0 };
        // q / 3
        q ^= q << 1;
        q ^= q << 2;
        q ^= q << 4;
        if q & 0x80 != 0 {
            q ^= 0x09;
        }
        let x = q ^ q.rotate_left(1) ^ q.rotate_left(2) ^ q.rotate_left(3) ^ q.rotate_left(4);
        s[p as usize] = x ^ 0x63;
        if p == 1 {
            break;
        }
    }
    s[0] = 0x63;
    s
};

const INV: [u8; 256] = {
    let mut t = [0u8; 256];
    let mut i = 0;
    while i < 256 {
        t[SBOX[i] as usize] = i as u8;
        i += 1;
    }
    t
};

fn xt(x: u8) -> u8 {
    (x << 1) ^ if x & 0x80 != 0 { 0x1b } else { 0 }
}

fn mulg(a: u8, b: u8) -> u8 {
    let (mut a, mut b, mut r) = (a, b, 0u8);
    while b != 0 {
        if b & 1 != 0 {
            r ^= a;
        }
        a = xt(a);
        b >>= 1;
    }
    r
}

fn aes(state: [u64; 2], key: [u64; 2], dec: bool, last: bool) -> [u64; 2] {
    let s = lanes8(state);
    let mut t = [0u8; 16];
    for c in 0..4 {
        for r in 0..4 {
            let from = if dec { ((c + 4 - r) % 4) * 4 + r } else { ((c + r) % 4) * 4 + r };
            t[c * 4 + r] = if dec { INV[s[from] as usize] } else { SBOX[s[from] as usize] };
        }
    }
    if !last {
        let mut u = [0u8; 16];
        for c in 0..4 {
            let col = &t[c * 4..c * 4 + 4];
            for r in 0..4 {
                u[c * 4 + r] = if dec {
                    mulg(col[r], 14) ^ mulg(col[(r + 1) % 4], 11) ^ mulg(col[(r + 2) % 4], 13) ^ mulg(col[(r + 3) % 4], 9)
                } else {
                    mulg(col[r], 2) ^ mulg(col[(r + 1) % 4], 3) ^ col[(r + 2) % 4] ^ col[(r + 3) % 4]
                };
            }
        }
        t = u;
    }
    let k = lanes8(key);
    for i in 0..16 {
        t[i] ^= k[i];
    }
    from8(t)
}

fn aes_keygen(src: [u64; 2], rcon: u8) -> [u64; 2] {
    let w = |i: usize| ((src[i / 2] >> ((i % 2) * 32)) & 0xffff_ffff) as u32;
    let sub = |x: u32| -> u32 {
        let b = x.to_le_bytes();
        u32::from_le_bytes([SBOX[b[0] as usize], SBOX[b[1] as usize], SBOX[b[2] as usize], SBOX[b[3] as usize]])
    };
    let x1 = sub(w(1));
    let x3 = sub(w(3));
    let r = [x1, x1.rotate_right(8) ^ rcon as u32, x3, x3.rotate_right(8) ^ rcon as u32];
    [r[0] as u64 | (r[1] as u64) << 32, r[2] as u64 | (r[3] as u64) << 32]
}
