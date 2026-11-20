# Verified self-hosting and first measurement baseline

The compiler now rebuilds its actual assembled Alchem source without host
compiler tools. A1, A2 and A3 are byte-identical and each passes the integer/byte
correctness/rejection suites. These gates are satisfied for the documented native
profile; they do not establish full production Alchem compatibility.

| Gate | Verified evidence |
| --- | --- |
| Profile closes over its own source | 54,038 bytes/135 functions, including typed byte helpers and 128-element construction |
| Compiler reads new source and emits executable bytes | Alchem-written native compiler IO entry, empty PATH |
| Reproducible self-rebuild | A0 -> A1 -> A2 -> A3 through both Go/Rust seeds; A1=A2=A3 |
| Correctness/rejection at generated stages | 67 integer programs/21 rejections/3 runtime limits and 49 byte programs/25 rejections/5 byte-or-slice errors/9 resource programs at each stage |
| Bounded storage | Traced arena charges 6,299,072 bytes for A0 build, 9,066,304 for A1/A2 builds; budget 16 MiB |
| Local verification | Complete verify-local --with-source passes; entry EINTR 4/4, generated mmap faults 2/2 and 3/3 |

## Initial warm-cache baseline — 2026-11-17

Raw data: [self-hosting-baseline-2026-11-17.json](../benchmarks/self-hosting-baseline-2026-11-17.json).
The script is scripts/benchmark-self-host.py. It verifies every measured output
is byte-identical to the measured compiler, including warmups.

| Quantity | Observation |
| --- | --- |
| Input | Actual assembled source, 54,038 bytes |
| Output | Self-built compiler, 81,371 bytes |
| Warmups/samples | 2 discarded warmups, 10 recorded separate processes |
| Median self-build wall time | 60.87 ms |
| Observed range | 58.35–85.18 ms |
| OS-reported peak RSS | 13,440 KiB for these samples |
| Native arena charge (separate tracing) | 9,066,304 bytes |
| Host | Linux x86-64, kernel 6.18.57, AMD EPYC 9V74; full metadata/load in JSON |

Wall time includes Python launch/wait overhead, native process startup, stdin
file reads, compilation and stdout file writes; output comparison is outside the
timed interval. Caches are warm, not controlled cold-cache runs. RSS is Linux
wait4 ru_maxrss, a process high-water mark that can include launch history; it is
not live heap size or the separately traced arena charge. The native child runs
with PATH empty and launches no host tools.

This is one cloud-session baseline with visible variance and no CPU isolation.
It is not a Go/Rust comparison or a stable cross-machine performance claim.
Historical Go/Rust numbers in benchmarks.md measured bootstrap IR compilers and
must remain separate from these native self-build measurements.

## Reproduce

```sh
bash scripts/build-native.sh
python3 scripts/benchmark-self-host.py \
  --compiler build/native/alchem-compiler \
  --source build/native/compiler-source.alc \
  --warmups 2 --samples 10 --output /tmp/self-host-baseline.json
```

Source SHA-256:
f848b2a599ad76efe8c382b66904f6418eaf255745ed44b2eca4e5ba4bcd9683.
Compiler SHA-256:
8bb870477b9cca4059d0e717717e09e6448782d9a155353a9bd2f9d226a5785c.

Next measurement work should repeat independent sessions, control host load/CPU,
and distinguish self-build throughput, startup and generated-program execution.
Keep raw samples, exact source/profile hashes and correctness gates with any
optimization result. Production Alchem remains unchanged.

## Core-module and Enum checkpoint

The core-module checkpoint used a 55,818-byte source and 83,359-byte compiler, with a separate
10-sample record in [self-hosting-core-2026-11-17.json](../benchmarks/self-hosting-core-2026-11-17.json),
with two warmups and byte equality verified for every run. Median 65.186 ms,
range 60.498–94.655 ms. This is a separate cloud sample, not a controlled
comparison with the earlier source. Exact hashes and host/load metadata are in
the JSON. Both records include launch and IO; neither compares Go against Rust.

## Typed-string checkpoint

Current 63,989-byte source / 94,569-byte compiler: 10 verified samples after
2 warmups, median 84.080 ms, range 81.672–117.077 ms. Raw hashes, host/load and
samples: [self-hosting-strings-2026-11-17.json](../benchmarks/self-hosting-strings-2026-11-17.json).
This is a separate cloud sample; different source and uncontrolled host load
prevent treating the earlier numbers as a controlled speed comparison.

## Boolean/predicate checkpoint

Compacted 58,262-byte source / 100,073-byte compiler: 10 verified samples after
2 warmups, median 99.291 ms, range 95.678–140.871 ms. See
[self-hosting-booleans-2026-11-17.json](../benchmarks/self-hosting-booleans-2026-11-17.json)
for hashes, all samples and host/load metadata. Separate uncontrolled cloud
sample; do not interpret differences between these checkpoints as an isolated
optimization comparison. Native self-build still needs no host tool on PATH.

## Same-input parser fast-path comparison

The feature baseline is commit 43b62f599b0a4e81a31d4419c25539a83468eaa4.
[Alternating pair data](../benchmarks/boolean-parser-fastpath-2026-11-17.json)
records both compilers processing the identical final 58,542-byte source and
producing the exact final ELF. Two warmup pairs precede ten alternating AB/BA
sample pairs. Median process wall time: 101.975 ms before, 98.534 ms after.
Separate tracing measures 13,019,736 vs12,628,824 arena bytes, a reduction of
390,912 bytes on the same input. Timed runs include launch/IO, exclude equality
comparison and tracing. One shared cloud host, no CPU isolation or stable speed
claim; the arena reduction is the direct allocation observation.

To reproduce, assemble the baseline source from the baseline commit in a separate
checkout, compile it with the current native compiler and save its executable.
Then run scripts/benchmark-compiler-pair.py with --before that executable,
--after build/native/alchem-compiler, --source build/native/compiler-source.alc,
--before-commit 43b62f599b0a4e81a31d4419c25539a83468eaa4 and --output a JSON path.
Use the toolchain of mise.toml with ptrace permitted. Every emitted image must
match the final compiler. The old source/compiler hashes are in the feature
baseline and the pair JSON; neither binary is committed.

## Grapheme/option checkpoint

The current compiler has a larger256-slot layout, Unicode tables and a32MiB
compiler-entry arena. Historical pair comparisons must use both compiler and
source from their pinned versions (43b62f5 before,28c8d28 after); today's source
has unsupported features/capacity for the old compiler. For historical tracing,
pass --before-arena-mib 16 and --after-arena-mib 16. Current compilers need32.
Omitting both budgets records no arena comparison, rather than guessing a budget.

The new 63,580-byte input /128,734-byte compiler has10 verified samples after
2 warmups: median 136.523 ms, range 122.175–164.883 ms. See
[self-hosting-graphemes-options-2026-11-17.json](../benchmarks/self-hosting-graphemes-options-2026-11-17.json)
for hashes, host/load and all samples. Launch/IO included; one shared cloud
session, no controlled comparison with older feature sets. Exact native arena
charge is separately traced at18,449,112 bytes, not inferred from RSS.

## Collections/library snapshot — 2026-11-17

Raw record: [self-hosting-collections-library-2026-11-17.json](../benchmarks/self-hosting-collections-library-2026-11-17.json).
The current compiler self-builds89,611 source bytes to192,202 identical ELF bytes.
Two warmups and10 verified processes measured median220.16ms, range213.57–259.70ms;
wait4 peak RSS32,768–32,896KiB. Traced native arena charge is separately34,536,120
of64MiB; ordinary programs keep4MiB. Exact source/compiler hashes, host and load
are in the record. This is a warm shared-session observation, including launch/IO,
not a controlled comparison with older compilers or Go/Rust.
