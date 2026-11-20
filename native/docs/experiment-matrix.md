# Experiment matrix

Use identical IR inputs, target triple, fixtures, optimization levels and hardware for Go and Rust implementations. Record compiler build toolchain versions, OS/kernel, CPU, warm-up policy and run counts.

| Metric | Go | Rust | Alchem |
| --- | --- | --- | --- |
| Correctness tests | 195 shared cases + 576 generated programs + 20 budget cases | Same shared suite | Classifier + 1,227 lexer + 135 integer + 354 expression oracle programs + 260 encoder cases |
| Compile latency | Local smoke samples recorded | Local smoke samples recorded | Future |
| Peak RSS | Local wait4 samples recorded | Local wait4 samples recorded | Future |
| Executable size | 4181 / 114701 bytes | Identical output | Future |
| Runtime latency | Includes process launch | Identical executable bytes | Future |
| Deterministic output | Verified on positive fixtures | Verified; matches Go | Future |

Do not interpret implementation language as the cause of generated-code performance without comparing code generation and runtime dependencies.

See [measurement methodology and results](benchmarks.md). These are smoke measurements, not statistically controlled performance conclusions.
