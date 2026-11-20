# Native stored booleans and predicates

Boolean is a distinct type with canonical machine values false=0, true=1.
Literals, parameters/returns, local bindings, matching conditional results and
recursive calls preserve that type. Function metadata kind3 encodes flag6, or22
for private functions. Integers, strings and bytes cannot be implicitly converted.
Conditions require boolean; integer comparison expressions now return boolean.
Comparisons bind below arithmetic. Signed integer ==/!=/</<=/>/>= are supported;
boolean ==/!= require two booleans. Comparison chains are rejected. `not` requires
a boolean operand and binds as a unary operator; use parentheses around a
comparison operand. Stored booleans are not valid numbers or halt statuses.
Logical and/or are strict boolean, short-circuit operators: not binds as unary,
then arithmetic/comparison, then and, then or. Both operands are type checked
even when a constant left value skips runtime evaluation. Each logical chain has
a16-operator budget; parentheses use the existing nesting bound. Options are
specified separately in alchem-options-profile.md; result types remain absent.

Enum.empty?(bytes) returns boolean without allocating. The existing profile's
byte-only Enum type restriction remains. String.contains?(string,string),
String.starts_with?(string,string) and String.ends_with?(string,string) return
booleans from exact byte matching, consistent with the pinned strings.Contains,
HasPrefix and HasSuffix paths. Empty pattern matches every string; an oversized
pattern never matches. Both arguments evaluate left to right. Predicates allocate
no records and never read past either payload. Contains uses a bounded naive
search; this is a functional contract, not a substring-search speed claim.
Question marks are supported only at identifier ends, including helper names.

String.length now uses the pinned grapheme rules; see alchem-grapheme-profile.md.
Unicode
normalization, list-of-pattern overloads and case folding are not implied by
these byte predicates. Predicate instructions are constructed by native-booleans.alc;
string-predicates-x86_64.s is an auditable reference, not a build input.
