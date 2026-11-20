# Local Go/Rust measurements — 2026-11-16

These are bounded smoke measurements of compiler revision `8334491`, not a
statistical comparison of implementation languages. Raw samples, executable and
compiler hashes, tool versions, CPU/kernel information, and measurement-script
hashes are in [the JSON artifact](measurements/2026-11-16-smoke.json).

Go used its default optimized build with `-trimpath`; Rust used Cargo release.
Each workload/backend had 2 warmups and 20 measured invocations. Compilation
includes process launch, JSON parsing, code generation and output I/O. Runtime
includes process launch and is dominated by that overhead for these programs.
Memory is the median of 5 separate Linux `wait4` peak-RSS samples in KiB. A tiny
C helper avoids inheriting Python's memory high-water mark. Building this
measurement helper with cc is separate from the IR compilation path.

The host was an AMD EPYC 9V74 cloud VM. Runs were sequential (Go then Rust),
without CPU pinning, host-load isolation or repeated independent sessions.
Warm filesystem caches and scheduler noise can materially affect these numbers.

| Input | Backend | Compile median ms | Peak RSS median KiB | Emitted bytes | Runtime incl. launch median ms |
| --- | --- | ---: | ---: | ---: | ---: |
| add-20-22.json | go | 1.297 | 2500 | 4181 | 0.256 |
| add-20-22.json | rust | 1.045 | 1168 | 4181 | 0.218 |
| 4096-values.json | go | 23.702 | 7556 | 114701 | 0.181 |
| 4096-values.json | rust | 5.814 | 5532 | 114701 | 0.253 |

The generated larger input has 4096 SSA values: one constant followed by 4095
additions. Its expected exit code is 0; the small fixture exits 42. Both
backends' emitted bytes matched on each workload. Therefore the runtime timings
cannot establish a generated-code advantage: the executable contents are equal.
The compile timings also reflect different JSON implementations and allocation
patterns, not just Go versus Rust.

Reproduce from repository root after toolchain/dependency setup:

```sh
mkdir -p /tmp/alchem-native-bench
(cd implementations/go && go build -trimpath -o /tmp/alchem-native-bench/go .)
CARGO_TARGET_DIR=/tmp/alchem-native-bench/rust cargo build --release --locked --offline --manifest-path implementations/rust/Cargo.toml
python3 scripts/benchmark-local.py --go /tmp/alchem-native-bench/go --rust /tmp/alchem-native-bench/rust/release/alchem-native-rust --output /tmp/alchem-native-bench/results.json
```

The script requires Linux/Python, `cc` for the RSS helper, and the prebuilt
compiler paths. It validates native exit results and equality of emitted bytes.
It does not measure compiler build time or in-process instruction throughput.

Self-hosting performance has not been measured. The Alchem-written arithmetic
frontend is now testable, but an Alchem-written compiler/output writer and A2/A3
self-rebuilds are still missing. See [the readiness gates and protocol](self-hosting-benchmarks.md).
