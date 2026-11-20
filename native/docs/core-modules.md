# Core modules on the self-hosted build

The standard build now compiles every existing Alchem-written compiler component
with A3, rather than rebuilding the arithmetic compiler through the host frontend.
Go/Rust still create the initial seed and provide independent reference checks.
Python assembles single-file inputs, schedules builds and publishes artifacts;
lexing, parsing, decimal conversion, code generation, ELF construction and the
resulting tools' stdin/stdout handling execute as native Alchem code.

```sh
bash scripts/build-native.sh
# After the initial bootstrap, rebuild just the core tools:
python3 scripts/build-core-modules.py --compiler build/native/alchem-compiler
printf '6*7' | build/native/core/alchem-expression   # writes 42, no newline
printf '6*7' | build/native/alchem-arithmetic > /tmp/answer
chmod 700 /tmp/answer
/tmp/answer
echo "$?"  # 42
```

The core builder runs at most four independent compilations concurrently, with
an empty child PATH. All modules must compile and smoke-test before publication.
Each output is atomic; publication of the entire set is not a transaction.
Failed compilation leaves previous files intact. The manifest records compiler,
source and artifact hashes; repeated builds must reproduce all files exactly.

| Component | Self-hosted artifact | Runtime protocol |
| --- | --- | --- |
| Full lexer, checked integer decoder and arithmetic parser/evaluator | `core/alchem-lexer` | Input <=128 bytes; kind/start/end byte triples including EOF |
| Integer decoder and new Alchem decimal formatter | `core/alchem-integer` | Optional sign, decimal and surrounding whitespace to canonical signed i64 ASCII |
| Expression evaluator | `core/alchem-expression` | Bounded arithmetic expression to canonical signed i64 ASCII |
| ELF encoder | `core/alchem-elf-emitter` | Exactly one status byte to a complete 140-byte executable |
| Arithmetic compiler | `core/alchem-arithmetic`, also `alchem-arithmetic` | Bounded arithmetic expression with result 0..255 to executable |
| Source compiler and native runtime | `alchem-compiler` | Source-profile module to native ELF; A1=A2=A3 |

Invalid service input returns 65, empty stdout and an entry diagnostic. The
underlying contracts remain in spec/lexer.md, integer-literals.md, expressions.md,
encoder.md and arithmetic-compiler.md. The integer tool returns decimal bytes. Source programs can separately call
Integer.to_string(i64), which returns the distinct native string type.

## Library coverage and next milestone

The user requested compiler components first, then standard-library modules.
Stored booleans now support literals, typed bindings/calls/returns, not, integer
comparisons, boolean equality and strict short-circuit and/or. Recursive options, tuples, results and exhaustive some/none or ok/error case
expressions are supported too.
The compiler component conversion above is complete for the existing bounded
implementation. It does not mean the production language/library is complete.

| Area | Native Alchem support now | Work still required |
| --- | --- | --- |
| Enum | Byte and general list count/lookup/concat/slice/reverse/take/drop/sum/empty?, typed map/filter/reduce and string join | Further callbacks, streams and remaining APIs |
| List/Map | General list first/last; typed immutable maps, sorted keys/values/entries and entry iteration | Optimized maps and remaining APIs |
| Integer | Checked decimal parser, byte formatter and native Integer base formatting, digits, checked undigits and Integer.parse/1,2 with exact pinned error text | pow/gcd/mod/floor_div and remaining APIs |
| String | Distinct type, bounded literals, typed calls/branches, concat, ==/!=, byte_size, predicates, pinned grapheme length/slice/first/last, duplicate, split, replace, count, valid?, trim/trim_leading/trim_trailing, upcase, downcase, to_integer, < <= > >= ordering, reverse, capitalize and pad_leading/pad_trailing | at, codepoints, graphemes, split_at and remaining String functions |
| IO | Compiler/tool entry, IO.puts/write statements in any body/branch/case arm, IO.read_line/read_all expressions | Devices, gets/inspect and binread |
| File | File.read, write, append and remove with exact pinned error reasons | exists?, stat, directories and remaining APIs |
| System | System.halt/stop, pid, wall-clock nanoseconds, argv and get_env/1,2 | put_env, commands, monotonic timing, memory and remaining APIs |
| Other modules | No compatibility claim | Inventory and port after shared type/runtime foundations |

The pinned production registry/runtime under upstream revision0b73f880b108
remains read-only. Shared structural types and collections are implemented; the
next groups are Integer parsing with exact result errors, general IO and further
String/System APIs. Do not add host service fallbacks and call them self-hosted.
Preserve A1/A2/A3 equality and check new operations at every generated stage.

## Verification

harness/core_modules.py runs the existing independent lexer, integer, expression
and encoder oracle programs through A3, including deterministic code generation.
harness/core_tools.py checks runtime protocols, all 256 executable exit images,
full-width integer formatting, hashes/modes, repeated publication equality and
failed-build preservation. harness/enum_library.py checks the new native Enum
operations against Python, including empty/extreme counts, unchanged inputs,
invalid types/arity and allocation exhaustion, on all three generated stages.
The complete command remains bash scripts/verify-local.sh --with-source.

Pinned grapheme support inherits the reference's approximate pictographic classes
and omitted Indic-conjunct rules. It is runtime compatibility, not full UAX#29
conformance. See spec/alchem-grapheme-profile.md and alchem-options-profile.md.
Each generated stage now checks131 option programs/8 rejections/11 arena cases,
478 boolean programs/16 rejections, and1546 grapheme counts/480 slices/220 option
results. Source scaling and structural types are implemented. General collections and
the added API subset are implemented; remaining library APIs are next; see spec/alchem-structural-types.md.

See [collection contracts](../spec/alchem-collections-profile.md) and
[additional APIs](../spec/alchem-library-profile.md) for exact coverage and bounds.
