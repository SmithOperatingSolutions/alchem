//! The Linux system calls the programs make, over a file system held in
//! memory. Files, directories and the standard streams work; there are no
//! other processes and no network, so fork, exec and sockets fail as a
//! kernel without them would have them fail (ENOSYS).

use crate::cpu::{Cpu, RAX, RDI, RDX, RSI, RSP};
use crate::mem::{Memory, PAGE};
use std::collections::{BTreeMap, BTreeSet};

const ENOENT: i64 = 2;
const EBADF: i64 = 9;
const ECHILD: i64 = 10;
const ENOMEM: i64 = 12;
const EFAULT: i64 = 14;
const EEXIST: i64 = 17;
const ENOTDIR: i64 = 20;
const EISDIR: i64 = 21;
const EINVAL: i64 = 22;
const ESPIPE: i64 = 29;
const ENOSYS: i64 = 38;
const ENOTEMPTY: i64 = 39;
const ENOTTY: i64 = 25;

const AT_FDCWD: i64 = -100;

#[derive(Clone)]
enum Fd {
    Stdin,
    Stdout,
    Stderr,
    Null,
    File { path: String, pos: u64, append: bool },
    Dir { path: String, done: bool },
}

pub struct Kernel {
    pub files: BTreeMap<String, Vec<u8>>,
    pub modes: BTreeMap<String, u32>,
    pub dirs: BTreeSet<String>,
    fds: Vec<Option<Fd>>,
    pub stdin: Vec<u8>,
    stdin_at: usize,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub cwd: String,
    next_map: u64,
    pub exit: Option<i32>,
    pub time_ns: u64,
    seed: u64,
    pub trace: bool,
}

impl Default for Kernel {
    fn default() -> Self {
        let mut dirs = BTreeSet::new();
        for d in ["/", "/tmp", "/dev", "/home", "/work"] {
            dirs.insert(d.to_string());
        }
        Kernel {
            files: BTreeMap::new(),
            modes: BTreeMap::new(),
            dirs,
            fds: vec![Some(Fd::Stdin), Some(Fd::Stdout), Some(Fd::Stderr)],
            stdin: Vec::new(),
            stdin_at: 0,
            stdout: Vec::new(),
            stderr: Vec::new(),
            cwd: "/work".into(),
            next_map: 0x1000_0000_0000,
            exit: None,
            time_ns: 1_790_000_000_000_000_000,
            seed: 0x9e37_79b9_7f4a_7c15,
            trace: false,
        }
    }
}

fn normal(path: &str) -> String {
    let mut parts: Vec<&str> = Vec::new();
    for p in path.split('/') {
        match p {
            "" | "." => {}
            ".." => {
                parts.pop();
            }
            _ => parts.push(p),
        }
    }
    format!("/{}", parts.join("/"))
}

fn parent(path: &str) -> String {
    match path.rfind('/') {
        Some(0) | None => "/".into(),
        Some(i) => path[..i].into(),
    }
}

impl Kernel {
    /// A fresh process: its descriptors, streams and mappings, with the
    /// files, the time and the input kept.
    pub fn reset(&mut self) {
        let files = std::mem::take(&mut self.files);
        let modes = std::mem::take(&mut self.modes);
        let dirs = std::mem::take(&mut self.dirs);
        let stdin = std::mem::take(&mut self.stdin);
        *self = Kernel { files, modes, dirs, stdin, time_ns: self.time_ns, trace: self.trace, ..Kernel::default() };
    }

    pub fn add_file(&mut self, path: &str, data: Vec<u8>, mode: u32) {
        let p = normal(path);
        let mut d = parent(&p);
        loop {
            self.dirs.insert(d.clone());
            if d == "/" {
                break;
            }
            d = parent(&d);
        }
        self.files.insert(p.clone(), data);
        self.modes.insert(p, mode);
    }

    fn resolve(&self, dirfd: i64, path: &str) -> Result<String, i64> {
        if path.starts_with('/') {
            return Ok(normal(path));
        }
        let base = if dirfd == AT_FDCWD {
            self.cwd.clone()
        } else {
            match self.fds.get(dirfd as usize).cloned().flatten() {
                Some(Fd::Dir { path, .. }) => path,
                Some(_) => return Err(ENOTDIR),
                None => return Err(EBADF),
            }
        };
        Ok(normal(&format!("{}/{}", base, path)))
    }

    fn new_fd(&mut self, fd: Fd) -> i64 {
        for (i, slot) in self.fds.iter_mut().enumerate() {
            if slot.is_none() {
                *slot = Some(fd);
                return i as i64;
            }
        }
        self.fds.push(Some(fd));
        (self.fds.len() - 1) as i64
    }

    fn random(&mut self) -> u64 {
        self.seed ^= self.seed << 13;
        self.seed ^= self.seed >> 7;
        self.seed ^= self.seed << 17;
        self.seed
    }

    pub fn set_seed(&mut self, seed: u64) {
        self.seed = seed | 1;
    }

    fn cstr(mem: &mut Memory, a: u64) -> Result<String, i64> {
        mem.read_cstr(a).map(|b| String::from_utf8_lossy(&b).into_owned()).map_err(|_| EFAULT)
    }

    fn stat(&self, mem: &mut Memory, path: &str, buf: u64) -> i64 {
        let (mode, size) = if path == "/dev/null" {
            (0o020666, 0)
        } else if self.dirs.contains(path) {
            (0o040755, 4096)
        } else if let Some(f) = self.files.get(path) {
            (0o100000 | self.modes.get(path).copied().unwrap_or(0o644), f.len() as u64)
        } else {
            return -ENOENT;
        };
        self.stat_into(mem, buf, mode, size, path)
    }

    fn stat_into(&self, mem: &mut Memory, buf: u64, mode: u32, size: u64, path: &str) -> i64 {
        let ino = path.bytes().fold(1469598103934665603u64, |h, b| (h ^ b as u64).wrapping_mul(1099511628211));
        let secs = self.time_ns / 1_000_000_000;
        let mut b = vec![0u8; 144];
        b[8..16].copy_from_slice(&ino.to_le_bytes());
        b[16..24].copy_from_slice(&1u64.to_le_bytes());
        b[24..28].copy_from_slice(&mode.to_le_bytes());
        b[48..56].copy_from_slice(&size.to_le_bytes());
        b[56..64].copy_from_slice(&4096u64.to_le_bytes());
        b[64..72].copy_from_slice(&size.div_ceil(512).to_le_bytes());
        for at in [72, 88, 104] {
            b[at..at + 8].copy_from_slice(&secs.to_le_bytes());
        }
        if mem.write_bytes(buf, &b).is_err() {
            return -EFAULT;
        }
        0
    }

    fn open(&mut self, path: String, flags: u64, mode: u64) -> i64 {
        let create = flags & 0o100 != 0;
        let excl = flags & 0o200 != 0;
        let trunc = flags & 0o1000 != 0;
        let append = flags & 0o2000 != 0;
        let dironly = flags & 0o200000 != 0;
        if path == "/dev/null" {
            return self.new_fd(Fd::Null);
        }
        if self.dirs.contains(&path) {
            if flags & 3 != 0 {
                return -EISDIR;
            }
            return self.new_fd(Fd::Dir { path, done: false });
        }
        if dironly {
            return if self.files.contains_key(&path) { -ENOTDIR } else { -ENOENT };
        }
        let exists = self.files.contains_key(&path);
        if exists && create && excl {
            return -EEXIST;
        }
        if !exists {
            if !create {
                return -ENOENT;
            }
            if !self.dirs.contains(&parent(&path)) {
                return if self.files.contains_key(&parent(&path)) { -ENOTDIR } else { -ENOENT };
            }
            self.files.insert(path.clone(), Vec::new());
            self.modes.insert(path.clone(), (mode as u32) & 0o777 & !0o022);
        } else if trunc {
            self.files.insert(path.clone(), Vec::new());
        }
        self.new_fd(Fd::File { path, pos: 0, append })
    }

    fn read(&mut self, mem: &mut Memory, fd: i64, buf: u64, len: u64, at: Option<u64>) -> i64 {
        let Some(Some(f)) = self.fds.get(fd as usize).cloned() else { return -EBADF };
        match f {
            Fd::Stdin => {
                let n = (len as usize).min(self.stdin.len() - self.stdin_at);
                let data = self.stdin[self.stdin_at..self.stdin_at + n].to_vec();
                self.stdin_at += n;
                if mem.write_bytes(buf, &data).is_err() {
                    return -EFAULT;
                }
                n as i64
            }
            Fd::Null | Fd::Stdout | Fd::Stderr => 0,
            Fd::Dir { .. } => -EISDIR,
            Fd::File { path, pos, append } => {
                let from = at.unwrap_or(pos);
                let file = self.files.get(&path).cloned().unwrap_or_default();
                let start = (from as usize).min(file.len());
                let n = (len as usize).min(file.len() - start);
                if mem.write_bytes(buf, &file[start..start + n]).is_err() {
                    return -EFAULT;
                }
                if at.is_none() {
                    self.fds[fd as usize] = Some(Fd::File { path, pos: (start + n) as u64, append });
                }
                n as i64
            }
        }
    }

    fn write(&mut self, mem: &mut Memory, fd: i64, buf: u64, len: u64, at: Option<u64>) -> i64 {
        let Some(Some(f)) = self.fds.get(fd as usize).cloned() else { return -EBADF };
        let Ok(data) = mem.read_bytes(buf, len as usize) else { return -EFAULT };
        match f {
            Fd::Stdout => self.stdout.extend_from_slice(&data),
            Fd::Stderr => self.stderr.extend_from_slice(&data),
            Fd::Null => {}
            Fd::Stdin => return -EBADF,
            Fd::Dir { .. } => return -EISDIR,
            Fd::File { path, pos, append } => {
                let file = self.files.entry(path.clone()).or_default();
                let from = if append { file.len() } else { at.unwrap_or(pos) as usize };
                if file.len() < from + data.len() {
                    file.resize(from + data.len(), 0);
                }
                file[from..from + data.len()].copy_from_slice(&data);
                if at.is_none() {
                    self.fds[fd as usize] = Some(Fd::File { path, pos: (from + data.len()) as u64, append });
                }
            }
        }
        len as i64
    }

    fn dents(&mut self, mem: &mut Memory, fd: i64, buf: u64, len: u64) -> i64 {
        let Some(Some(Fd::Dir { path, done })) = self.fds.get(fd as usize).cloned() else { return -EBADF };
        if done {
            return 0;
        }
        let prefix = if path == "/" { "/".to_string() } else { format!("{}/", path) };
        let mut names: Vec<(String, u8)> = vec![(".".into(), 4), ("..".into(), 4)];
        for d in self.dirs.iter() {
            if let Some(rest) = d.strip_prefix(&prefix) {
                if !rest.is_empty() && !rest.contains('/') {
                    names.push((rest.into(), 4));
                }
            }
        }
        for f in self.files.keys() {
            if let Some(rest) = f.strip_prefix(&prefix) {
                if !rest.contains('/') {
                    names.push((rest.into(), 8));
                }
            }
        }
        let mut out = Vec::new();
        for (i, (name, kind)) in names.iter().enumerate() {
            let reclen = (19 + name.len() + 1).div_ceil(8) * 8;
            let mut rec = vec![0u8; reclen];
            rec[0..8].copy_from_slice(&(i as u64 + 1).to_le_bytes());
            rec[8..16].copy_from_slice(&(i as u64 + 1).to_le_bytes());
            rec[16..18].copy_from_slice(&(reclen as u16).to_le_bytes());
            rec[18] = *kind;
            rec[19..19 + name.len()].copy_from_slice(name.as_bytes());
            out.extend(rec);
        }
        if out.len() as u64 > len {
            return -EINVAL;
        }
        self.fds[fd as usize] = Some(Fd::Dir { path, done: true });
        if mem.write_bytes(buf, &out).is_err() {
            return -EFAULT;
        }
        out.len() as i64
    }

    fn mmap(&mut self, mem: &mut Memory, addr: u64, len: u64, flags: u64, fd: i64, off: u64) -> i64 {
        if len == 0 {
            return -EINVAL;
        }
        let size = len.div_ceil(PAGE) * PAGE;
        let at = if flags & 0x10 != 0 {
            addr
        } else {
            let a = self.next_map;
            self.next_map += size + PAGE;
            a
        };
        if flags & 0x10 != 0 {
            mem.unmap(at, size);
        }
        mem.map(at, size);
        if flags & 0x20 == 0 && fd >= 0 {
            if let Some(Some(Fd::File { path, .. })) = self.fds.get(fd as usize).cloned() {
                let file = self.files.get(&path).cloned().unwrap_or_default();
                let start = (off as usize).min(file.len());
                let end = (start + len as usize).min(file.len());
                if mem.write_bytes(at, &file[start..end]).is_err() {
                    return -ENOMEM;
                }
            } else {
                return -EBADF;
            }
        }
        at as i64
    }

    fn remove(&mut self, path: String, dir: bool) -> i64 {
        if dir {
            if !self.dirs.contains(&path) {
                return if self.files.contains_key(&path) { -ENOTDIR } else { -ENOENT };
            }
            let prefix = format!("{}/", path);
            if self.dirs.iter().any(|d| d.starts_with(&prefix)) || self.files.keys().any(|f| f.starts_with(&prefix)) {
                return -ENOTEMPTY;
            }
            self.dirs.remove(&path);
            0
        } else if self.files.remove(&path).is_some() {
            self.modes.remove(&path);
            0
        } else if self.dirs.contains(&path) {
            -EISDIR
        } else {
            -ENOENT
        }
    }

    /// The call in rax, with its arguments in rdi, rsi, rdx, r10, r8, r9;
    /// its result in rax.
    pub fn syscall(&mut self, cpu: &mut Cpu, mem: &mut Memory) {
        let n = cpu.r[RAX];
        let a = [cpu.r[RDI], cpu.r[RSI], cpu.r[RDX], cpu.r[10], cpu.r[8], cpu.r[9]];
        let r = self.call(cpu, mem, n, a);
        if self.trace {
            eprintln!("syscall {}({:#x}, {:#x}, {:#x}, {:#x}) = {}", n, a[0], a[1], a[2], a[3], r);
        }
        cpu.r[RAX] = r as u64;
        // The kernel's syscall leaves rcx and r11 changed.
        cpu.r[1] = cpu.rip;
        cpu.r[11] = 0x202;
    }

    fn path_at(&self, mem: &mut Memory, dirfd: i64, a: u64) -> Result<String, i64> {
        let p = Self::cstr(mem, a)?;
        self.resolve(dirfd, &p)
    }

    fn call(&mut self, cpu: &mut Cpu, mem: &mut Memory, n: u64, a: [u64; 6]) -> i64 {
        self.time_ns += 1000;
        let i = |k: usize| a[k] as i64;
        macro_rules! path {
            ($dirfd:expr, $arg:expr) => {
                match self.path_at(mem, $dirfd, a[$arg]) {
                    Ok(p) => p,
                    Err(e) => return -e,
                }
            };
        }
        match n {
            0 => self.read(mem, i(0), a[1], a[2], None),
            1 => self.write(mem, i(0), a[1], a[2], None),
            17 => self.read(mem, i(0), a[1], a[2], Some(a[3])),
            18 => self.write(mem, i(0), a[1], a[2], Some(a[3])),
            20 => {
                let mut total = 0;
                for k in 0..a[2] {
                    let base = mem.read(a[1] + 16 * k, 64).unwrap_or(0);
                    let len = mem.read(a[1] + 16 * k + 8, 64).unwrap_or(0);
                    let r = self.write(mem, i(0), base, len, None);
                    if r < 0 {
                        return r;
                    }
                    total += r;
                }
                total
            }
            2 => {
                let p = path!(AT_FDCWD, 0);
                self.open(p, a[1], a[2])
            }
            257 => {
                let p = path!(i(0), 1);
                self.open(p, a[2], a[3])
            }
            3 => match self.fds.get_mut(a[0] as usize) {
                Some(slot @ Some(_)) => {
                    *slot = None;
                    0
                }
                _ => -EBADF,
            },
            4 | 6 => {
                let p = path!(AT_FDCWD, 0);
                self.stat(mem, &p, a[1])
            }
            262 => {
                let raw = Self::cstr(mem, a[1]).unwrap_or_default();
                if raw.is_empty() && a[3] & 0x1000 != 0 {
                    return self.fstat(mem, i(0), a[2]);
                }
                let p = path!(i(0), 1);
                self.stat(mem, &p, a[2])
            }
            5 => self.fstat(mem, i(0), a[1]),
            8 => {
                let Some(Some(Fd::File { path, pos, append })) = self.fds.get(a[0] as usize).cloned() else {
                    return if matches!(self.fds.get(a[0] as usize), Some(Some(_))) { -ESPIPE } else { -EBADF };
                };
                let size = self.files.get(&path).map(|f| f.len()).unwrap_or(0) as i64;
                let to = match a[2] {
                    0 => i(1),
                    1 => pos as i64 + i(1),
                    2 => size + i(1),
                    _ => return -EINVAL,
                };
                if to < 0 {
                    return -EINVAL;
                }
                self.fds[a[0] as usize] = Some(Fd::File { path, pos: to as u64, append });
                to
            }
            9 => self.mmap(mem, a[0], a[1], a[3], i(4), a[5]),
            10 => 0,
            11 => {
                mem.unmap(a[0], a[1].div_ceil(PAGE) * PAGE);
                0
            }
            25 => {
                // mremap: a fresh range with the old bytes.
                let old = a[1];
                let new = a[2];
                let at = self.mmap(mem, 0, new, 0x22, -1, 0);
                if at < 0 {
                    return at;
                }
                let _ = mem.copy_within(at as u64, a[0], old.min(new));
                mem.unmap(a[0], old.div_ceil(PAGE) * PAGE);
                at
            }
            28 => {
                if a[2] == 4 {
                    mem.discard(a[0], a[1]);
                }
                0
            }
            12 => 0,
            13 | 14 | 131 => 0,
            16 => -ENOTTY,
            21 | 269 => {
                let p = if n == 21 { path!(AT_FDCWD, 0) } else { path!(i(0), 1) };
                if self.files.contains_key(&p) || self.dirs.contains(&p) || p == "/dev/null" {
                    0
                } else {
                    -ENOENT
                }
            }
            24 => 0,
            32 => match self.fds.get(a[0] as usize).cloned().flatten() {
                Some(f) => self.new_fd(f),
                None => -EBADF,
            },
            33 | 292 => match self.fds.get(a[0] as usize).cloned().flatten() {
                Some(f) => {
                    let to = a[1] as usize;
                    if self.fds.len() <= to {
                        self.fds.resize(to + 1, None);
                    }
                    self.fds[to] = Some(f);
                    to as i64
                }
                None => -EBADF,
            },
            // Time is the machine's own: a sleep moves it on at once.
            35 => {
                self.time_ns += Self::span(mem, a[0]);
                0
            }
            230 => {
                let t = Self::span(mem, a[2]);
                if a[1] & 1 != 0 {
                    self.time_ns = self.time_ns.max(t);
                } else {
                    self.time_ns += t;
                }
                0
            }
            39 | 186 => 1000,
            110 => 1,
            102 | 104 | 107 | 108 => 1000,
            95 => 0o022,
            56 | 57 | 58 | 59 | 22 | 293 | 41 | 42 | 43 | 49 | 50 | 53 | 288 => -ENOSYS,
            61 => -ECHILD,
            62 => 0,
            60 | 231 => {
                self.exit = Some(a[0] as i32 & 0xff);
                0
            }
            63 => {
                let mut b = vec![0u8; 65 * 6];
                for (k, s) in ["Linux", "alchem", "6.1.0", "#1", "x86_64", ""].iter().enumerate() {
                    b[k * 65..k * 65 + s.len()].copy_from_slice(s.as_bytes());
                }
                if mem.write_bytes(a[0], &b).is_err() {
                    return -EFAULT;
                }
                0
            }
            72 => 0,
            74 | 75 => 0,
            77 => {
                let Some(Some(Fd::File { path, .. })) = self.fds.get(a[0] as usize).cloned() else { return -EBADF };
                self.files.entry(path).or_default().resize(a[1] as usize, 0);
                0
            }
            78 | 217 => self.dents(mem, i(0), a[1], a[2]),
            79 => {
                let mut b = self.cwd.clone().into_bytes();
                b.push(0);
                if b.len() as u64 > a[1] {
                    return -34;
                }
                if mem.write_bytes(a[0], &b).is_err() {
                    return -EFAULT;
                }
                b.len() as i64
            }
            80 => {
                let p = path!(AT_FDCWD, 0);
                if self.dirs.contains(&p) {
                    self.cwd = p;
                    0
                } else if self.files.contains_key(&p) {
                    -ENOTDIR
                } else {
                    -ENOENT
                }
            }
            82 | 264 | 316 => {
                let (from, to) = if n == 82 { (path!(AT_FDCWD, 0), path!(AT_FDCWD, 1)) } else { (path!(i(0), 1), path!(i(2), 3)) };
                if let Some(data) = self.files.remove(&from) {
                    let mode = self.modes.remove(&from).unwrap_or(0o644);
                    if self.dirs.contains(&to) {
                        self.files.insert(from.clone(), data);
                        self.modes.insert(from, mode);
                        return -EISDIR;
                    }
                    self.files.insert(to.clone(), data);
                    self.modes.insert(to, mode);
                    0
                } else if self.dirs.contains(&from) {
                    let moved: Vec<String> = self.files.keys().filter(|f| f.starts_with(&format!("{}/", from))).cloned().collect();
                    for f in moved {
                        let d = self.files.remove(&f).unwrap();
                        let m = self.modes.remove(&f).unwrap_or(0o644);
                        let g = format!("{}{}", to, &f[from.len()..]);
                        self.files.insert(g.clone(), d);
                        self.modes.insert(g, m);
                    }
                    let dirs: Vec<String> = self.dirs.iter().filter(|d| **d == from || d.starts_with(&format!("{}/", from))).cloned().collect();
                    for d in dirs {
                        self.dirs.remove(&d);
                        self.dirs.insert(format!("{}{}", to, &d[from.len()..]));
                    }
                    0
                } else {
                    -ENOENT
                }
            }
            83 | 258 => {
                let p = if n == 83 { path!(AT_FDCWD, 0) } else { path!(i(0), 1) };
                if self.dirs.contains(&p) || self.files.contains_key(&p) {
                    -EEXIST
                } else if !self.dirs.contains(&parent(&p)) {
                    -ENOENT
                } else {
                    self.dirs.insert(p);
                    0
                }
            }
            84 => {
                let p = path!(AT_FDCWD, 0);
                self.remove(p, true)
            }
            87 => {
                let p = path!(AT_FDCWD, 0);
                self.remove(p, false)
            }
            263 => {
                let p = path!(i(0), 1);
                self.remove(p, a[2] & 0x200 != 0)
            }
            89 | 267 => -EINVAL,
            90 | 268 => {
                let p = if n == 90 { path!(AT_FDCWD, 0) } else { path!(i(0), 1) };
                let mode = if n == 90 { a[1] } else { a[2] };
                if self.files.contains_key(&p) {
                    self.modes.insert(p, mode as u32 & 0o7777);
                    0
                } else if self.dirs.contains(&p) {
                    0
                } else {
                    -ENOENT
                }
            }
            91 => 0,
            96 => {
                let t = self.time_ns;
                let _ = mem.write(a[0], 64, t / 1_000_000_000);
                let _ = mem.write(a[0] + 8, 64, (t % 1_000_000_000) / 1000);
                0
            }
            201 => (self.time_ns / 1_000_000_000) as i64,
            228 => {
                let t = self.time_ns;
                if mem.write(a[1], 64, t / 1_000_000_000).is_err() || mem.write(a[1] + 8, 64, t % 1_000_000_000).is_err() {
                    return -EFAULT;
                }
                0
            }
            97 | 302 => {
                let at = if n == 97 { a[1] } else { a[3] };
                if at != 0 {
                    let _ = mem.write(at, 64, 8 << 20);
                    let _ = mem.write(at + 8, 64, u64::MAX);
                }
                0
            }
            158 => {
                match a[0] {
                    0x1002 => cpu.fs = a[1],
                    0x1001 => cpu.gs = a[1],
                    _ => return -EINVAL,
                }
                0
            }
            202 => 0,
            7 | 271 => {
                // poll: every descriptor is ready; a wait with none passes its time.
                if a[1] == 0 {
                    if n == 7 && (a[2] as i64) > 0 {
                        self.time_ns += a[2] * 1_000_000;
                    } else if n == 271 && a[2] != 0 {
                        self.time_ns += Self::span(mem, a[2]);
                    }
                }
                a[1] as i64
            }
            280 => 0,
            318 => {
                let mut b = vec![0u8; a[1] as usize];
                for chunk in b.chunks_mut(8) {
                    let r = self.random().to_le_bytes();
                    chunk.copy_from_slice(&r[..chunk.len()]);
                }
                if mem.write_bytes(a[0], &b).is_err() {
                    return -EFAULT;
                }
                a[1] as i64
            }
            319 => {
                let path = format!("/memfd-{}", self.random());
                self.files.insert(path.clone(), Vec::new());
                self.new_fd(Fd::File { path, pos: 0, append: false })
            }
            _ => {
                if self.trace {
                    eprintln!("system call {} not supported", n);
                }
                -ENOSYS
            }
        }
    }

    fn span(mem: &mut Memory, at: u64) -> u64 {
        let secs = mem.read(at, 64).unwrap_or(0);
        let nanos = mem.read(at + 8, 64).unwrap_or(0);
        secs.saturating_mul(1_000_000_000).saturating_add(nanos)
    }

    fn fstat(&self, mem: &mut Memory, fd: i64, buf: u64) -> i64 {
        match self.fds.get(fd as usize).cloned().flatten() {
            Some(Fd::File { path, .. }) => self.stat(mem, &path, buf),
            Some(Fd::Dir { path, .. }) => self.stat(mem, &path, buf),
            Some(Fd::Null) => self.stat_into(mem, buf, 0o020666, 0, "/dev/null"),
            Some(_) => self.stat_into(mem, buf, 0o020620, 0, "/dev/pts/0"),
            None => -EBADF,
        }
    }
}

/// Loads a static ELF image and lays out the stack the kernel gives a new
/// program: argc, argv, envp and the auxiliary vector.
pub fn load(cpu: &mut Cpu, mem: &mut Memory, image: &[u8], argv: &[String], env: &[String], seed: u64) -> Result<(), String> {
    if image.len() < 64 || &image[..4] != b"\x7fELF" || image[4] != 2 {
        return Err("not a 64-bit ELF executable".into());
    }
    let u16_at = |o: usize| u16::from_le_bytes([image[o], image[o + 1]]) as u64;
    let u64_at = |o: usize| u64::from_le_bytes(image[o..o + 8].try_into().unwrap());
    if u16_at(18) != 62 {
        return Err("not an x86-64 executable".into());
    }
    let entry = u64_at(24);
    let phoff = u64_at(32) as usize;
    let phentsize = u16_at(54) as usize;
    let phnum = u16_at(56) as usize;
    let mut phdr = 0;
    for k in 0..phnum {
        let h = phoff + k * phentsize;
        let kind = u32::from_le_bytes(image[h..h + 4].try_into().unwrap());
        if kind != 1 {
            continue;
        }
        let off = u64_at(h + 8) as usize;
        let vaddr = u64_at(h + 16);
        let filesz = u64_at(h + 32) as usize;
        let memsz = u64_at(h + 40);
        let start = vaddr & !(PAGE - 1);
        let end = (vaddr + memsz).div_ceil(PAGE) * PAGE;
        mem.map(start, end - start);
        mem.write_bytes(vaddr, &image[off..off + filesz]).map_err(|e| format!("loading at {:#x}", e.0))?;
        if off == 0 {
            phdr = vaddr + phoff as u64;
        }
    }
    // An 8 MiB stack below the top of the user half.
    let top: u64 = 0x7fff_0000_0000;
    let size: u64 = 8 << 20;
    mem.map(top - size, size);
    let mut sp = top - 4096;
    let put = |mem: &mut Memory, bytes: &[u8], sp: &mut u64| -> u64 {
        *sp -= bytes.len() as u64 + 1;
        let _ = mem.write_bytes(*sp, bytes);
        let _ = mem.write_u8(*sp + bytes.len() as u64, 0);
        *sp
    };
    let argp: Vec<u64> = argv.iter().map(|s| put(mem, s.as_bytes(), &mut sp)).collect();
    let envp: Vec<u64> = env.iter().map(|s| put(mem, s.as_bytes(), &mut sp)).collect();
    sp -= 16;
    let random = sp;
    let _ = mem.write(random, 64, seed);
    let _ = mem.write(random + 8, 64, seed.rotate_left(29) ^ 0x5851_f42d_4c95_7f2d);
    sp &= !15;
    let mut words: Vec<u64> = vec![argv.len() as u64];
    words.extend(&argp);
    words.push(0);
    words.extend(&envp);
    words.push(0);
    for (k, v) in [(3u64, phdr), (4, phentsize as u64), (5, phnum as u64), (6, 4096), (9, entry), (25, random), (0, 0)] {
        words.push(k);
        words.push(v);
    }
    if words.len() % 2 == 1 {
        sp -= 8;
    }
    sp -= 8 * words.len() as u64;
    for (k, w) in words.iter().enumerate() {
        let _ = mem.write(sp + 8 * k as u64, 64, *w);
    }
    cpu.r[RSP] = sp;
    cpu.rip = entry;
    Ok(())
}
