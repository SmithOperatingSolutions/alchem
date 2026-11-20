# JSON IR version 3 — typed structured conditionals

V1 and V2 remain supported unchanged. V3 keeps V2's functions, i64 parameters,
calling convention and one entry block per function, and adds typed boolean
values and structured conditional instructions. Arbitrary labels/CFGs are not
introduced in this milestone.

New instructions (all fields are required and non-null):

| Operation | Exact fields | Result |
| --- | --- | --- |
| `const.bool` | op, dest, value (JSON boolean) | bool, represented as 0/1 |
| `eq.i64`, `ne.i64`, `lt.i64`, `le.i64`, `gt.i64`, `ge.i64` | op, dest, lhs, rhs | bool; signed comparisons of i64 values |
| `not.bool` | op, dest, value (SSA name) | bool |
| `if.i64`, `if.bool` | op, dest, cond, then, else | selected i64/bool branch result |

A conditional's cond must name a bool. Each branch is an object with exactly
`instructions` (an array) and `value` (the SSA name yielded by that branch):

```json
{"op":"if.i64","dest":"answer","cond":"test",
 "then":{"instructions":[{"op":"const.i64","dest":"yes","value":42}],"value":"yes"},
 "else":{"instructions":[{"op":"const.i64","dest":"no","value":7}],"value":"no"}}
```

Only the selected branch executes. Both branches are validated, even if the
condition is a constant. Branches see the parent values defined before the
conditional plus their own earlier instructions. A branch cannot see values
from its sibling, future parent instructions, or the conditional's own result.
Both yields must match the conditional result type. Only the conditional dest
is made available to subsequent parent instructions. SSA destination names are
unique throughout a function, including branch-local names and parameters.

Arithmetic and call arguments require i64. Branch conditions and not.bool
require bool. Function parameters and returns remain i64; returning a bool as
an i64 is invalid. Empty branch instruction arrays may yield a parent value.
No implicit truthiness, integer/boolean casts or floating-point comparisons.

Conditional nesting is limited to 16, function count to 256, acyclic call depth
to 64, parameters to 6, and total per-function frame to 1 MiB. All branch-local
values receive frame slots. Type/scope/shape violations use E_INVALID_IR; unknown
opcodes use E_UNKNOWN_OPCODE; unsupported limits/recursion use E_UNSUPPORTED.

Lowering uses signed CMP/SETcc with normalized boolean results and native
conditional jumps. The branch result is loaded into RAX at the merge and stored
in its destination slot. Existing direct calls work inside either branch.
Loops, recursive calls, arbitrary early returns and unstructured branches remain
future work. This structured form avoids an undefined phi/block-argument policy.
