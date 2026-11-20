# Shared compiler harness

The manifest in `fixtures/manifest.json` specifies positive and negative cases. All compiler implementations must accept the same JSON IR and CLI contract.

```sh
python3 -m unittest discover -s harness -p 'test_*.py' -v
python3 harness/run.py --compiler /absolute/path/to/backend
```

The first command validates fixture structure and tests the runner. The second runs the backend acceptance suite. Run on Linux x86-64. Each backend must accept `--target`, `--input`, and `--output`. Invalid IR must emit a stable diagnostic code on stderr and must not produce an executable.

The runner uses argument arrays (no shell), isolated temporary directories, process timeouts, ELF magic checks, executable permission checks, byte-identical repeated compilation to distinct paths, and exit/output assertions. It does not itself enforce that a compiler never launches an external tool; that requires separate process tracing in a later milestone.

Run both backends and the seeded differential check (after fetching the locked
Rust build dependencies once):

```sh
bash scripts/verify-local.sh --with-rust
```

`differential.py GO_COMPILER RUST_COMPILER` generates 64 repeatable straight-line
i64 programs using addition, subtraction and multiplication, executes each backend's output, compares it with Python arithmetic
modulo 2^64/low-byte exit semantics, and requires byte-identical ELF output.
This is bounded correctness coverage, not exhaustive equivalence or a benchmark.

`--with-source` also runs `source_programs.py`: six real-main programs through the
Rust source CLI, compared with the Go IR reference. It checks deterministic
builds, local bindings, normal exit, halt boundaries, source rejection, output
preservation, source overwrite protection, sibling frontend discovery and empty
PATH compilation. `examples/invoice.alc` is included in these checks.

The differential runner also generates 64 v2 call programs with 0–6 parameters,
shuffled function order, nested calls, argument permutations and live caller
values, comparing native exit results with a Python evaluator and requiring
identical Go/Rust ELF bytes. Shared fixtures include 64 cases across both IR
versions. Source checks now include thirteen library probes and ten real-main
programs, including the function-based invoice, plus eight rejection cases.

V3 adds 31 shared cases, taking the total to 95. `flow_differential.py` generates
64 additional programs with signed comparisons, boolean merges, nested typed
branches and calls, bringing differential coverage to 192 programs. The source
suite runs 15 library probes and 25 real-main programs, including an Alchem-written
ASCII classifier checked on 133 inputs. An untaken-branch fixture contains an
exponentially expensive call graph to detect eager execution of both branches.
Conditional-depth checks accept 16 levels and reject 17 in both backends.
