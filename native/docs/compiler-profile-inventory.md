# Self-hosting profile closure inventory

The current assembled compiler distribution is 89,611 UTF-8 bytes and 305
functions including native_compile and the compatibility main. The pinned
frontend reports 83 integer/221 byte returns and 383 integer/380 byte parameters
across definitions. Assembly compacts identifiers, formatting and comments, preserving quoted content and token/
statement boundaries. Readable assembled source is 135,792 bytes. The build selects
nine shared lexer primitives from the
original component, without duplicating or modifying it. All subsequent native
rebuilds consume this exact assembled source file.

| Compiler construct | Evidence |
| --- | --- |
| Modules/comments, public/private signatures, scoped names/types | Actual source compiles through A0, A1 and A2 |
| Six-register typed calls, forward/self/mutual recursion | Source rebuilds plus integer/byte program suites |
| Arithmetic, signed branches and scoped values | Same emitted compiler bytes and independent source oracles |
| Byte parameters/returns, 128-element computed/header lists | Full compiler source and explicit 128-pack fixtures |
| Enum.at/count/concat/slice plus reverse/take/drop/sum | Native emitted runtime and byte correctness/resource checks |
| Typed strings, literals, concat, byte_size, integer formatting, puts | New string/output suite at all three stages |
| Nested options, tuples, results and case extraction | Option/library cases and exact allocation on all three stages |
| General lists/maps/typed callbacks | 831 list/iteration programs,262 map programs and exact allocation/immutability checks per stage |
| Expanded library APIs | 186 independent numeric/byte programs, PID/clock checks and syscall faults per stage |
| Pinned Unicode graphemes | 1546 counts, 480 slices, 220 option results per stage against exact runtime |
| Stored booleans and predicates | Boolean/predicate suite at all generated stages |
| Compiler input/output entry | Alchem emits bounded read, complete write, EOF/errors/EINTR handling |
| Function/output storage | Batched scans, balanced construction, saved lengths; no re-emission |
| Larger metadata/layout | u32 address/size encoding; compiler image 192,202 bytes; wide fixtures |
| Self-rebuild | A1=A2=A3, same source/output hashes through Go/Rust seeds |

Profile bounds remain explicit: input 4194303 bytes, functions 512, lists 128,
body tokens 1024, 16 local/parameter slots and expression nesting 16; individual
function code 65535 and total function code 512 KiB. Compiler execution uses64MiB
arena, ordinary target programs 4 MiB. Traced native self-build charge is 34,536,120
bytes. These are supported bounds, not claims of arbitrary-source scalability.

The source hash is e321cc3dc4038f663542cc0fcd31a71d0aebab2fce64415052d5360489b35702.
A1/A2/A3 hash is fafcbae3797508b4d05a39dbaad74a3c81db70c8a775ad9b7e33d3b0b39ec932.
Build-native publishes the self-built A3, assembled source and self-host.json.
The full suite tests every generated stage's integer/byte correctness/rejections,
rebuild equality, failed-build preservation and the measured arena bounds.

The former type, input-size, output-layout and generated-entry blockers for this
implementation are resolved. Full Alchem compatibility remains separate: no
actors, imports, broad String APIs, macros, general mutation or foreign runtime integration.
Further language growth should preserve the existing self-build/correctness gates
and update this inventory against the new actual source.

Source/input capacity is now 4,194,303 bytes with24-bit source metadata; see
[source capacity](../spec/source-capacity.md) for packet/layout boundaries.

Compiler components use explicit bytes/b[...] syntax; word lists preserve full
values. See alchem-collections-profile.md and alchem-library-profile.md. V11 seeds
have512 functions while older profiles remain256; normal user arenas stay4MiB.
