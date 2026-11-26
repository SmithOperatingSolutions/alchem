//! Memory as the programs see it: 64-bit addresses over pages that are
//! made, zeroed, when first touched. A program reserves its 16 GiB arena and
//! its stacks with mmap and uses a small part, so only what it touches
//! costs anything. A page not mapped at all is a fault.

use std::collections::HashMap;

pub const PAGE_BITS: u32 = 16;
pub const PAGE: u64 = 1 << PAGE_BITS;
const MASK: u64 = PAGE - 1;
const WAYS: usize = 256;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fault(pub u64);

/// A range the program mapped: pages in it are made when touched.
#[derive(Clone, Copy, Debug)]
pub struct Region {
    pub start: u64,
    pub end: u64,
}

pub struct Memory {
    pages: HashMap<u64, Box<[u8]>>,
    regions: Vec<Region>,
    // Page number + 1 (0 is empty) and the page's bytes, by page number.
    cache: Vec<(u64, *mut u8)>,
    pub touched: usize,
}

impl Default for Memory {
    fn default() -> Self {
        Memory { pages: HashMap::new(), regions: Vec::new(), cache: vec![(0, std::ptr::null_mut()); WAYS], touched: 0 }
    }
}

impl Memory {
    pub fn map(&mut self, start: u64, len: u64) {
        let end = start.wrapping_add(len);
        self.regions.push(Region { start, end });
        self.regions.sort_by_key(|r| r.start);
        // Join ranges that touch, so lookups stay short.
        let mut joined: Vec<Region> = Vec::new();
        for r in self.regions.drain(..) {
            match joined.last_mut() {
                Some(last) if r.start <= last.end => last.end = last.end.max(r.end),
                _ => joined.push(r),
            }
        }
        self.regions = joined;
    }

    /// Unmaps whole pages of a range; what is unmapped faults again.
    pub fn unmap(&mut self, start: u64, len: u64) {
        let end = start.wrapping_add(len);
        let mut kept = Vec::new();
        for r in self.regions.drain(..) {
            if r.end <= start || r.start >= end {
                kept.push(r);
            } else {
                if r.start < start {
                    kept.push(Region { start: r.start, end: start });
                }
                if r.end > end {
                    kept.push(Region { start: end, end: r.end });
                }
            }
        }
        self.regions = kept;
        self.discard(start, len);
    }

    /// The pages wholly inside a range read as zero again (madvise
    /// DONTNEED); a partial page at either edge is cleared by hand.
    pub fn discard(&mut self, start: u64, len: u64) {
        let end = start.wrapping_add(len);
        let first = (start + MASK) >> PAGE_BITS;
        let last = end >> PAGE_BITS;
        for page in first..last {
            if self.pages.remove(&page).is_some() {
                self.touched -= 1;
            }
        }
        for way in self.cache.iter_mut() {
            *way = (0, std::ptr::null_mut());
        }
        let head_end = (first << PAGE_BITS).min(end);
        for a in start..head_end {
            let _ = self.write_u8(a, 0);
        }
        let tail_start = (last << PAGE_BITS).max(start).max(head_end);
        for a in tail_start..end {
            let _ = self.write_u8(a, 0);
        }
    }

    pub fn mapped(&self, addr: u64) -> bool {
        // Regions are sorted and apart: a binary search finds the one.
        let i = self.regions.partition_point(|r| r.end <= addr);
        i < self.regions.len() && self.regions[i].start <= addr
    }

    #[inline(always)]
    fn page(&mut self, addr: u64) -> Result<*mut u8, Fault> {
        let number = addr >> PAGE_BITS;
        let way = (number as usize) & (WAYS - 1);
        let (tag, ptr) = self.cache[way];
        if tag == number + 1 {
            return Ok(ptr);
        }
        self.page_slow(addr, number, way)
    }

    #[cold]
    fn page_slow(&mut self, addr: u64, number: u64, way: usize) -> Result<*mut u8, Fault> {
        let ptr = match self.pages.get_mut(&number) {
            Some(p) => p.as_mut_ptr(),
            None => {
                if !self.mapped(addr) {
                    return Err(Fault(addr));
                }
                self.touched += 1;
                let mut page = vec![0u8; PAGE as usize].into_boxed_slice();
                let ptr = page.as_mut_ptr();
                self.pages.insert(number, page);
                ptr
            }
        };
        self.cache[way] = (number + 1, ptr);
        Ok(ptr)
    }

    #[inline(always)]
    pub fn read_u8(&mut self, addr: u64) -> Result<u8, Fault> {
        let p = self.page(addr)?;
        Ok(unsafe { *p.add((addr & MASK) as usize) })
    }

    #[inline(always)]
    pub fn write_u8(&mut self, addr: u64, v: u8) -> Result<(), Fault> {
        let p = self.page(addr)?;
        unsafe { *p.add((addr & MASK) as usize) = v };
        Ok(())
    }

    #[inline(always)]
    pub fn read(&mut self, addr: u64, size: u32) -> Result<u64, Fault> {
        let off = addr & MASK;
        let n = size as u64 / 8;
        if off + n <= PAGE {
            let p = self.page(addr)?;
            unsafe {
                let q = p.add(off as usize);
                Ok(match size {
                    8 => *q as u64,
                    16 => (q as *const u16).read_unaligned() as u64,
                    32 => (q as *const u32).read_unaligned() as u64,
                    _ => (q as *const u64).read_unaligned(),
                })
            }
        } else {
            let mut v = 0u64;
            for i in 0..n {
                v |= (self.read_u8(addr + i)? as u64) << (8 * i);
            }
            Ok(v)
        }
    }

    #[inline(always)]
    pub fn write(&mut self, addr: u64, size: u32, v: u64) -> Result<(), Fault> {
        let off = addr & MASK;
        let n = size as u64 / 8;
        if off + n <= PAGE {
            let p = self.page(addr)?;
            unsafe {
                let q = p.add(off as usize);
                match size {
                    8 => *q = v as u8,
                    16 => (q as *mut u16).write_unaligned(v as u16),
                    32 => (q as *mut u32).write_unaligned(v as u32),
                    _ => (q as *mut u64).write_unaligned(v),
                }
            }
            Ok(())
        } else {
            for i in 0..n {
                self.write_u8(addr + i, (v >> (8 * i)) as u8)?;
            }
            Ok(())
        }
    }

    pub fn read_bytes(&mut self, addr: u64, len: usize) -> Result<Vec<u8>, Fault> {
        let mut out = Vec::with_capacity(len);
        let mut a = addr;
        let mut left = len;
        while left > 0 {
            let p = self.page(a)?;
            let off = (a & MASK) as usize;
            let n = left.min(PAGE as usize - off);
            out.extend_from_slice(unsafe { std::slice::from_raw_parts(p.add(off), n) });
            a += n as u64;
            left -= n;
        }
        Ok(out)
    }

    pub fn write_bytes(&mut self, addr: u64, data: &[u8]) -> Result<(), Fault> {
        let mut a = addr;
        let mut done = 0;
        while done < data.len() {
            let p = self.page(a)?;
            let off = (a & MASK) as usize;
            let n = (data.len() - done).min(PAGE as usize - off);
            unsafe { std::ptr::copy_nonoverlapping(data.as_ptr().add(done), p.add(off), n) };
            a += n as u64;
            done += n;
        }
        Ok(())
    }

    /// The bytes before the first zero, from addr.
    pub fn read_cstr(&mut self, addr: u64) -> Result<Vec<u8>, Fault> {
        let mut out = Vec::new();
        let mut a = addr;
        loop {
            let b = self.read_u8(a)?;
            if b == 0 {
                return Ok(out);
            }
            out.push(b);
            a += 1;
        }
    }

    /// Copies count bytes from one place to another as rep movsb does,
    /// a byte at a time upward when the two overlap that way.
    pub fn copy_within(&mut self, to: u64, from: u64, count: u64) -> Result<(), Fault> {
        if to > from && to < from + count {
            for i in 0..count {
                let b = self.read_u8(from + i)?;
                self.write_u8(to + i, b)?;
            }
            return Ok(());
        }
        let mut done = 0u64;
        while done < count {
            let n = (count - done).min(PAGE - ((from + done) & MASK)).min(PAGE - ((to + done) & MASK));
            let bytes = self.read_bytes(from + done, n as usize)?;
            self.write_bytes(to + done, &bytes)?;
            done += n;
        }
        Ok(())
    }

    pub fn fill(&mut self, to: u64, value: u8, count: u64) -> Result<(), Fault> {
        let mut done = 0u64;
        while done < count {
            let off = (to + done) & MASK;
            let n = (count - done).min(PAGE - off);
            let p = self.page(to + done)?;
            unsafe { std::ptr::write_bytes(p.add(off as usize), value, n as usize) };
            done += n;
        }
        Ok(())
    }
}
