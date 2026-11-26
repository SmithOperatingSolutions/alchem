//! emu-run: runs a Linux x86-64 program of the native compiler on the
//! interpreter, outside a browser, to check it against the real thing.
//!
//!   emu-run [--file HOST=GUEST]... [--out GUEST=HOST]... [--stdin] [--trace] [--stats] PROGRAM [ARG]...
//!
//! PROGRAM is a host file, put at /work/<its name>; each --file puts a host
//! file in the machine, and each --out copies a machine's file back when it
//! has ended. With --stdin the program reads this one's input to its end;
//! else it has none. The program's output is this one's, and so is its status.

use alchem_emu::{Machine, Outcome};
use std::io::{Read, Write};
use std::time::Instant;

fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut machine = Machine::default();
    let mut outs = Vec::new();
    let mut stats = false;
    let mut input = false;
    while let Some(first) = args.first().cloned() {
        if first == "--file" {
            let (host, guest) = args[1].split_once('=').expect("--file HOST=GUEST");
            let data = std::fs::read(host).unwrap_or_else(|e| panic!("{}: {}", host, e));
            machine.kernel.add_file(guest, data, 0o755);
            args.drain(..2);
        } else if first == "--out" {
            let (guest, host) = args[1].split_once('=').expect("--out GUEST=HOST");
            outs.push((guest.to_string(), host.to_string()));
            args.drain(..2);
        } else if first == "--trace" {
            machine.kernel.trace = true;
            args.remove(0);
        } else if first == "--stdin" {
            input = true;
            args.remove(0);
        } else if first == "--stats" {
            stats = true;
            args.remove(0);
        } else {
            break;
        }
    }
    let program = args[0].clone();
    let name = std::path::Path::new(&program).file_name().unwrap().to_string_lossy().into_owned();
    let guest = format!("/work/{}", name);
    machine.kernel.add_file(&guest, std::fs::read(&program).expect("program"), 0o755);
    let mut stdin = Vec::new();
    if input {
        let _ = std::io::stdin().read_to_end(&mut stdin);
    }
    machine.kernel.stdin = stdin;
    let mut argv = vec![name];
    argv.extend(args[1..].iter().cloned());
    let env = vec!["HOME=/home".to_string(), "PATH=/bin".to_string(), "ALCHEM_CACHE=/tmp/cache".to_string()];
    machine.kernel.time_ns = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos() as u64;
    machine.start(&guest, &argv, &env).expect("start");
    let began = Instant::now();
    let status = loop {
        let outcome = machine.run(50_000_000);
        std::io::stdout().write_all(&std::mem::take(&mut machine.kernel.stdout)).unwrap();
        std::io::stderr().write_all(&std::mem::take(&mut machine.kernel.stderr)).unwrap();
        match outcome {
            Outcome::Running => continue,
            Outcome::Exited(code) => break code,
            Outcome::Failed(why) => {
                eprintln!("emu-run: {}", why);
                break 139;
            }
        }
    };
    for (guest, host) in outs {
        if let Some(data) = machine.kernel.files.get(&guest) {
            std::fs::write(&host, data).unwrap();
        }
    }
    if stats {
        let secs = began.elapsed().as_secs_f64();
        eprintln!("emu-run: {} instructions in {:.2} s ({:.0} M/s), {} pages touched", machine.cpu.steps, secs, machine.cpu.steps as f64 / secs / 1e6, machine.mem.touched);
    }
    std::process::exit(status);
}
