# Function definitions: arities, defaults, clauses, forms, return, raise

The self-hosted compiler takes a function definition in every form the pinned
language has, with the pinned compiler's rules. `harness/clauses.py` holds the
programs and the pinned compiler's outcome for each.

## What is accepted

- **Arities.** Definitions of one name with different numbers of parameters
  are different functions, anywhere in the module: `size/1` and `size/2`. A
  call, piped or not, from the module or as `Module.size(...)`, takes the one
  its number of arguments fits. `&size/2` names one of them; a bare `&size`
  needs the name to have one arity.
- **Default arguments.** `name: type \\ value` on trailing parameters that are
  plain names. A call may leave them out. The value is a constant: literals,
  operators, lists, tuples, maps, `@constants`, `none`, `some(...)`, `ok(...)`
  and `error(...)`; a name or any other call is rejected where it is written.
  The value is typed where a call leaves it out, as upstream types it, so a
  default nobody uses may have any type, and a failure in one (`10 / 0`) names
  the call. Two arities may not take the same number of arguments.
  `&name/N` is the function of all N parameters.
- **Clauses.** Adjacent definitions of one name and number of parameters are
  tried top to bottom. A parameter is a pattern (every form of
  `alchem-patterns.md`), a literal or a name, with or without its type; a
  parameter's type comes from the first clause that writes it or matches a
  literal there, and the result type from the first clause that writes one.
  `when guard` follows the result type. Defaults stand in the first clause;
  later ones are ignored, as upstream ignores them.
  A struct or sum type may stand between two clauses; another function may
  not. Rejected, as upstream rejects them: clauses that are not adjacent, a mix of
  `def` and `defp`, a parameter no clause types, no result type, two result
  types, a clause no value can reach, clauses that leave a value unmatched
  (a guarded clause covers nothing), and two definitions without parameters.
- **Forms.** A clause that declares another type for a parameter than the
  clauses before it begins another form: a function of the same name and
  number of parameters for arguments of other types, with its own clauses and
  result type. A call takes the first form, in source order, that its
  arguments fit. `&show/1` is the form its expected function type names
  (a parameter such as `Enum.map`'s, or an annotated binding) and is rejected
  where nothing gives one. Two forms may not declare the same types. A trace
  names the second form `show#2`, as the pinned runtime does.
- **`return value`** leaves the function, or the `fn` it stands in, at once.
  It is a statement: it ends its block, nothing may follow it or an `if` or
  `case` that returns on every path, and it may not stand in an `if`, `case`
  or `cond` whose value is used. `main` has none. A `fn` whose result type
  comes from its body holds every `return` to that type.
- **`raise(message)`** ends the program with status 2, the message and the
  active calls. It stands for a value of whatever type its place needs.
  There is no `try` yet, so nothing catches it.

## How it is compiled

A table record (27 bytes, `alchem-modules.md`) keeps after its flags where the
result type is written (3 bytes, 0 for none), the number of defaults, and
where the guard starts (3 bytes, 0 for none). The first clause of a function
has the function's record. Each further clause has a record with flags 40: it
takes a table slot, no lookup finds it and it has no code. A form is a
function record like any other, placed after the clauses of the form before.
Records stay in source order, so the record of a struct or sum type declared
between two clauses lies between theirs, and the walk from clause to clause
steps over it.

- Lookup by name finds some function of that name; `nj_fit` then takes the one
  whose parameter count, less its defaults, fits the arguments, and `nj_form`
  the first form whose parameter types the arguments unify with.
- A call that leaves defaults out compiles each default where the call stands
  (`nj_full`), in the callee's module and with no bindings in reach.
- A function with one clause of typed names is compiled as before. Any other
  (`nj_function`) keeps its parameters in their slots; each clause binds its
  plain names to those slots, matches its patterns against them with the
  matcher of `native-patterns.alc`, runs its guard, then its body, and jumps
  past the remaining clauses. Reachability and coverage use the matrix test
  over one row of patterns per unguarded clause, which is the test a `case`
  over the tuple of the parameters would get: upstream compiles clauses to
  exactly that `case`.
- While a guard runs the frame's line is that of the first clause, where
  upstream's `case` stands.
- `return` is the value and the frame's exit (`dec r15; leave; ret`). A
  record with no name and type 40 stands in the environment inside an `if`,
  `case` or `cond` compiled as a value, where `return` is rejected; one of
  type 41 with a result type starts a `fn`. A `return` leaves a value of type
  unknown-by-return (`9, 1`), which joins any other branch's type; branches
  that all return keep it, and a statement after such an `if`, `case` or
  `cond` is rejected as unreachable.
- `raise` passes the trace routine the message string in place of a reason
  number (`alchem-traces.md`) and leaves a value of unknown type (9). What
  stands after the last arm of a `case` or `cond` has type `9, 2`, which adds
  nothing to the arms' type, so a `case` whose arms all return or raise is a
  value like any other.

## Differences from upstream that remain

- The pinned checker names a `fn` parameter that is a pattern or `_` `arg$N`
  from a program-wide counter, and the parameters of a function with clauses
  `arg$1`, `arg$2`, ...; when the two collide it rejects the program with
  `parameter arg$1 shadows an existing binding` (for instance `fn a, _ -> a end`
  in a clause of a one-parameter function, as the first such `fn` it types).
  The counter also counts each time the checker types a `fn` again, so which
  programs collide follows from its internal order of work, not from the
  program. The native compiler has no such names and runs these programs.
- Compile errors are one status (65) and no message, as everywhere in the
  native compiler.
