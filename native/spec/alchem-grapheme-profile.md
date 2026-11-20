# Pinned-runtime native graphemes

String.length, String.slice(string,start,count), String.first and String.last now
use the actual pinned Alchem runtime segmentation rules, not code-point count.
String.length returns integer; slice returns a fresh string; first/last return
option[string], with none on empty input. byte_size still returns encoded bytes.

The reference is compiler/library.go.txt at upstream revision0b73f880b108, paired
with Go1.27 Unicode17.0.0 categories. spec/grapheme-ranges.json stores 613 sorted
non-default property intervals, Unicode version, upstream revision and the exact
reference-section SHA-256. Hangul LV/LVT is handled algorithmically. Records pack
start21 | class4 | (length-1)11 into five little-endian bytes. The final three pad
bytes permit a bounded eight-byte load at the final record; length is masked to
11bits. Properties use binary search; ASCII without CR takes a count fast path.

UTF-8 decoding matches Go: malformed, overlong, surrogate, out-of-range and
truncated sequences consume one byte and yield RuneError. Cluster slices preserve
original bytes. The runtime implements CR/LF/control boundaries, Extend/SpacingMark/
Prepend, Hangul sequences, regional pairs and pictographic Extend*/ZWJ chains.
It deliberately inherits upstream's omitted Indic-conjunct rules and approximate
pictographic block ranges. This is compatibility with that pinned implementation,
not a claim of complete Unicode UAX#29 conformance. Changes to either rules or
Unicode version require regenerating data and rerunning reference comparisons.

Slice requires nonnegative start/count, clamps to available clusters without
signed addition overflow and returns fresh empty for an absent range. Negative
bounds exit73 under the private target ABI. Range overloads are unsupported.
First/last copy the selected cluster into a fresh string and then allocate a
16-byte some record. Empty first/last allocate no result. Length allocates no
result or temporary heap records; traversal uses bounded stack storage.

native-grapheme-data.alc contains checked runtime byte literals, constructed by
Alchem during normal native compilation. No Go Unicode library or assembler runs
in the native source compilation path. Regenerate the tracked data component only
with `python3 scripts/generate-grapheme-runtime.py` (development binutils required).
The assembly reference is graphemes-x86_64.s. Normal builds compile the checked
Alchem source and need no assembler. Reference tests build a standalone oracle
from the exact pinned section and compare the complete property snapshot before
checking outputs. Host Go Unicode-version mismatches fail explicitly.

harness/graphemes.py checks every interval endpoint in a cluster-sensitive
context, Hangul remainders, flags, ZWJ/skin-tone/family emoji, combining marks,
controls, malformed bytes, seeded streams and long clusters. Both count and
byte-preserving slice/first/last results are checked against reference boundaries
on every self-built compiler stage. harness/options.py traces exact arena charges.
