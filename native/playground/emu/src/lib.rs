//! A machine that runs the Linux x86-64 programs of the native Alchem
//! compiler: the compiler's own alchem, and the programs it builds. The
//! files of its file system stay from one program to the next, so a page
//! can run `alchem build` and then what it built.
//!
//! In WebAssembly the page drives it through the functions below, which
//! take and give pointers into the module's memory.

pub mod cpu;
pub mod linux;
pub mod mem;

use cpu::{Cpu, Stop};
use linux::Kernel;
use mem::Memory;

pub struct Machine {
    pub cpu: Cpu,
    pub mem: Memory,
    pub kernel: Kernel,
    pub message: String,
    pub seed: u64,
}

pub enum Outcome {
    Running,
    Exited(i32),
    Failed(String),
}

impl Default for Machine {
    fn default() -> Self {
        Machine { cpu: Cpu::default(), mem: Memory::default(), kernel: Kernel::default(), message: String::new(), seed: 1 }
    }
}

impl Machine {
    /// Starts the program at path, with a fresh memory and fresh streams;
    /// the files are kept.
    pub fn start(&mut self, path: &str, argv: &[String], env: &[String]) -> Result<(), String> {
        let image = self.kernel.files.get(path).cloned().ok_or_else(|| format!("{}: no such file", path))?;
        self.cpu = Cpu::default();
        self.mem = Memory::default();
        self.kernel.reset();
        self.seed = self.seed.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        self.kernel.set_seed(self.seed);
        self.message.clear();
        linux::load(&mut self.cpu, &mut self.mem, &image, argv, env, self.seed)
    }

    /// Runs for about budget instructions.
    pub fn run(&mut self, budget: u64) -> Outcome {
        let mut left = budget;
        loop {
            if let Some(code) = self.kernel.exit {
                return Outcome::Exited(code);
            }
            let before = self.cpu.steps;
            match self.cpu.run(&mut self.mem, left) {
                Stop::Syscall => self.kernel.syscall(&mut self.cpu, &mut self.mem),
                Stop::Budget => return Outcome::Running,
                Stop::Fault(why) => {
                    self.message = why.clone();
                    return Outcome::Failed(why);
                }
            }
            let used = self.cpu.steps - before;
            if used >= left {
                if let Some(code) = self.kernel.exit {
                    return Outcome::Exited(code);
                }
                return Outcome::Running;
            }
            left -= used;
        }
    }
}

// The page's side: plain functions over the module's memory.

fn text(ptr: *const u8, len: usize) -> String {
    String::from_utf8_lossy(unsafe { std::slice::from_raw_parts(ptr, len) }).into_owned()
}

#[no_mangle]
pub extern "C" fn emu_alloc(len: usize) -> *mut u8 {
    let mut v = vec![0u8; len.max(1)];
    let p = v.as_mut_ptr();
    std::mem::forget(v);
    p
}

#[no_mangle]
pub extern "C" fn emu_free(ptr: *mut u8, len: usize) {
    unsafe { drop(Vec::from_raw_parts(ptr, len.max(1), len.max(1))) };
}

#[no_mangle]
pub extern "C" fn emu_new() -> *mut Machine {
    Box::into_raw(Box::default())
}

#[no_mangle]
pub extern "C" fn emu_file(m: *mut Machine, path: *const u8, path_len: usize, data: *const u8, data_len: usize, mode: u32) {
    let m = unsafe { &mut *m };
    let bytes = unsafe { std::slice::from_raw_parts(data, data_len) }.to_vec();
    m.kernel.add_file(&text(path, path_len), bytes, mode);
}

#[no_mangle]
pub extern "C" fn emu_stdin(m: *mut Machine, data: *const u8, len: usize) {
    let m = unsafe { &mut *m };
    m.kernel.stdin = unsafe { std::slice::from_raw_parts(data, len) }.to_vec();
}

#[no_mangle]
pub extern "C" fn emu_time(m: *mut Machine, seconds: f64) {
    let m = unsafe { &mut *m };
    m.kernel.time_ns = (seconds * 1e9) as u64;
}

/// Starts path with arguments separated by zero bytes; 0 when it started.
#[no_mangle]
pub extern "C" fn emu_start(m: *mut Machine, path: *const u8, path_len: usize, args: *const u8, args_len: usize) -> i32 {
    let m = unsafe { &mut *m };
    let argv: Vec<String> = text(args, args_len).split('\0').filter(|s| !s.is_empty()).map(String::from).collect();
    let env = vec!["HOME=/home".to_string(), "PATH=/bin".to_string(), "ALCHEM_CACHE=/tmp/cache".to_string()];
    match m.start(&text(path, path_len), &argv, &env) {
        Ok(()) => 0,
        Err(why) => {
            m.message = why;
            1
        }
    }
}

/// Runs for about budget instructions: -1 while the program goes on, its
/// status when it has ended, -2 when it failed (emu_message says why).
#[no_mangle]
pub extern "C" fn emu_run(m: *mut Machine, budget: u32) -> i32 {
    let m = unsafe { &mut *m };
    match m.run(budget as u64) {
        Outcome::Running => -1,
        Outcome::Exited(code) => code,
        Outcome::Failed(_) => -2,
    }
}

// What a program wrote (0 standard output, 1 standard error, 2 the message
// of a failure, 3 the file named by the last emu_read), as a pointer to its
// length (4 bytes) and then its bytes, taken from the machine.
static mut TAKEN: Vec<u8> = Vec::new();

#[no_mangle]
pub extern "C" fn emu_take(m: *mut Machine, which: u32) -> *const u8 {
    let m = unsafe { &mut *m };
    let bytes = match which {
        0 => std::mem::take(&mut m.kernel.stdout),
        1 => std::mem::take(&mut m.kernel.stderr),
        _ => m.message.clone().into_bytes(),
    };
    let mut out = (bytes.len() as u32).to_le_bytes().to_vec();
    out.extend(bytes);
    unsafe {
        TAKEN = out;
        #[allow(static_mut_refs)]
        TAKEN.as_ptr()
    }
}

/// A file of the machine's, as emu_take gives bytes; its length is
/// 0xffffffff when there is no such file.
#[no_mangle]
pub extern "C" fn emu_read(m: *mut Machine, path: *const u8, path_len: usize) -> *const u8 {
    let m = unsafe { &mut *m };
    let out = match m.kernel.files.get(&text(path, path_len)) {
        Some(bytes) => {
            let mut out = (bytes.len() as u32).to_le_bytes().to_vec();
            out.extend(bytes);
            out
        }
        None => u32::MAX.to_le_bytes().to_vec(),
    };
    unsafe {
        TAKEN = out;
        #[allow(static_mut_refs)]
        TAKEN.as_ptr()
    }
}

#[no_mangle]
pub extern "C" fn emu_steps(m: *mut Machine) -> f64 {
    let m = unsafe { &*m };
    m.cpu.steps as f64
}
