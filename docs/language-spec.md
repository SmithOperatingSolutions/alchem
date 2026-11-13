# Alchem language specification — experimental subset

An Alchem file contains one `defmodule UppercaseName do ... end`. The entry module has exactly one zero-argument `main/0`; imported library modules do not. Relative imports and qualified calls connect modules without global mutable state. See [modules](modules.md). The compiler checks the entire file before invoking Go, including unused functions and untaken branches.

## Values, bindings and expressions

Primitive types are `integer` (signed 64-bit), `float` (64-bit IEEE 754), `boolean` (`true`/`false`) and `string` (decoded UTF-8 with Go-style quoted escapes). Invalid UTF-8, invalid escapes and out-of-range integer literals are compilation errors. A byte escape such as `\x00` or `\xff` writes a byte that cannot be typed, so a literal can hold binary data. A code point is written `\uHHHH`, `\UHHHHHHHH` or, as in Elixir, `\u{H...}` with one to six hex digits; an invalid escape is reported by name, with the escapes a string takes. String equality compares decoded bytes without Unicode normalization.

Bindings use `name = expression`, with optional annotations such as `xs: list[integer] = []`. Destructuring bindings are described below. Names start with a lowercase Unicode letter or underscore and continue with letters, digits or underscores. Keywords and builtin names are reserved. Bindings are immutable: an existing name cannot be redefined or shadowed in a nested branch. Unused bindings are allowed. Names must be defined before use. Each function has its own scope; branch-local bindings do not escape their branch, and separate branches may use the same new name.

```elixir
count = 2 + 3 * 4
ready = count > 0 and not false
assert(ready and count == 14)
```

Operators, from highest to lowest precedence:

| Operators | Behavior |
| --- | --- |
| postfix `[index]`, `(arguments)` | Collection access or invocation of a function-valued expression |
| unary `-`, `not` | Integer negation; boolean negation |
| `*`, `/`, `%` | Checked integer multiplication, division, remainder |
| `+`, `-` | Checked integer addition, subtraction |
| `|>` | Insert the left value as the first call argument |
| `==`, `!=`, `<`, `<=`, `>`, `>=` | Same-type equality; ordering of integers, floats and strings |
| `and` | Boolean conjunction, short-circuits on false |
| `or` | Boolean disjunction, short-circuits on true |

Arithmetic operators associate left to right. Comparisons cannot be chained; use boolean operators between comparisons. Parentheses group any expression. Unary minus is separate from subtraction, so `n-1` is valid. Leading-zero integer literals are decimal. Positive literals cannot exceed 9223372036854775807; `-9223372036854775808` is valid.

All integer arithmetic detects overflow and fails with `integer overflow`. Division truncates toward zero; remainder has the dividend's sign. Zero divisors fail with `division by zero`. Minimum integer divided by -1 overflows; its remainder modulo -1 is zero. Only booleans may be conditions or boolean operands; there is no implicit truthiness or numeric conversion. Untaken branches and short-circuited operands are not evaluated, but are still type-checked. Language-defined runtime failures exit with status 2 and source diagnostics.

## Statements and conditionals

Function bodies contain one or more bindings, `IO.puts(stringExpression)`, `assert(booleanExpression)`, function calls, returns, conditionals, or `case` statements. Statements run in source order and are separated by whitespace, including newlines. Binary expressions may continue across whitespace, but a line that starts with `(`, `[` or `-` begins a new statement instead of continuing the expression above it; end the previous line with the operator to continue. `IO.puts` writes a string plus newline to stdout. A false assertion reports `assertion failed` on stderr and stops execution with status 2.

```elixir
if ready do
  IO.puts("ready")
else
  IO.puts("waiting")
end
```

`else` is optional. Branches may contain nested conditionals. Present blocks must contain a statement. An `if` can also produce a value (see If and case as values).

## Functions

Functions other than `main` require typed parameters and an explicit return type. The final expression of a body is its value and `return` exits early (see Implicit returns and function clauses). Zero parameters are allowed. `return expression` must match the declared type, and all paths must return. Unreachable statements after a guaranteed return are rejected. `main` has no return annotation and cannot use `return`.

```elixir
defmodule Example do
  def factorial(n: integer): integer do
    if n <= 1 do
      return 1
    else
      return n * factorial(n - 1)
    end
  end

  def main() do
    answer = factorial(5)
    assert(answer == 120)
  end
end
```

Functions may call functions declared later, including recursive and mutually recursive calls. Arguments are evaluated left to right and checked for exact type and arity. Each function name has one signature, shared by all of its clauses (see Implicit returns and function clauses); arity overloading is unsupported. Calls may appear in expressions or as statements that discard their result. `main` cannot be called. Functions may emit output and assert; `IO.puts` and `assert` themselves are statements, not expression values. Source identifiers are mapped to generated Go identifiers.

A function's call to itself in return position, such as `count(rest, seen + 1)` as the value of a branch, runs as a loop: it uses no stack, is not counted against the call depth, and checks for cancellation on every turn. This covers a call that is the whole value a function returns, directly or as the last expression of an `if` or `case` branch; a call whose result is used further (`n * factorial(n - 1)`), a call between two different functions, a call inside a `try`, and a call in a generic function are ordinary calls. All other recursion uses the Go stack. Each process may nest at most 100,000 function and closure calls by default (`--max-call-depth`); going deeper fails that process with `call depth exceeded` at the called function's definition, which callers, monitors and supervisors observe like any other failure. Limits raised far above the default can still exhaust the Go stack, which is fatal. This is not a BEAM implementation. Typed local processes and supervision are described in [runtime](runtime.md). Explicit annotations and returns are Alchem design choices, not Elixir syntax compatibility.

## Typed lists and tuples

Lists are homogeneous and preserve element order: `[1,2,3]` has type `list[integer]`. Tuples have a fixed shape with independently typed positions: `{1,"ok"}` has type `tuple[integer,string]`. Nesting is supported in both values and function parameter/return types, for example `list[tuple[integer,string]]`. The empty tuple `{}` has type `tuple[]`.

```elixir
empty: list[integer] = []
nested: list[list[integer]] = [[],[1,2]]
pair = {[1,2],"ok"}
assert(pair[0][1] == 2)
assert(length(pair) == 2)
```

Empty list literals need an expected type, supplied by a binding annotation, function parameter/return type, a prior list element, or a known opposite equality operand. Inference proceeds through list elements from left to right: unannotated `[]` or `[[],[1]]` cannot infer a type. `length([])` also requires a typed binding instead. There are no implicit conversions; type variables are described under Generics.

Indexing is zero-based. List indices may be any integer expression and are checked at runtime; negative or out-of-range indices report `list index out of bounds`. Tuple indices must be integer literals in range and are checked at compile time. `length(value)` returns an integer for either collection and evaluates its argument exactly once.

`==` and `!=` compare collections structurally, recursively, with matching types. List order and length matter; tuple arity, order and element types matter. Empty lists and empty tails compare equal within the same type, including the placeholder list or map in a timed-out `Process.receive` result. Ordering comparisons on collections are unsupported. Values cannot be updated or mutated. List tails may share read-only storage. This implementation emits Go slices/structs and uses deep equality; it does not promise linked-list complexity or a particular allocation cost. List operations are described below; head-cons construction expressions remain deferred.

## Patterns and case

A list is also built in front of another with `[first | rest]` or `[first, second | rest]`, which shares `rest` and costs as much as one `prepend` per element.

Bindings may destructure a value using names, `_`, primitive literals, tuples, exact-length lists, and head/tail list patterns:

```elixir
{count,label} = {3,"ok"}
[first | rest] = [1,2,3]
[1,2,3] = [1,2,3]
true = count > 0
_ = rest
```

Names must be fresh; repeated names, rebinding and shadowing are rejected. `_` discards without defining a name. Matching an existing variable uses a pin pattern, described below. Fixed lists match exact lengths. `[a,b | rest]` matches at least two elements, then matches `rest` against the remaining list. Patterns may nest, including in the tail position. Type/tuple-shape mismatches fail compilation. A binding whose literal or list-length pattern fails reports `pattern match failed` at runtime. The subject is evaluated once, and names are introduced only after the whole pattern succeeds. Optional binding type annotations apply to the subject and can type nested empty lists.

```elixir
case items do
  [] -> IO.puts("empty")
  [head | tail] -> assert(length(tail) >= 0)
end
```

`case` evaluates its subject once, selects the first matching arm in source order, and runs that arm only. Each arm has a nonempty body and its own scope; captures cannot escape the arm or shadow outer names. Nested `if`/`case` and returns are supported. A function using a terminal `case` must return from every arm.

Cases must be statically exhaustive. The checker recognizes an irrefutable name/`_`, an irrefutable tuple pattern, both boolean literals, or `[]` together with an irrefutable `[head | tail]` pattern. More complex combinations require a final catch-all even if a human could prove coverage. Duplicate branches, branches subsumed by an earlier pattern, and branches after proven complete coverage are rejected when the checker can prove them unreachable. Other overlaps retain first-match semantics. Guard conditions are described below; pattern alternatives and case expressions remain deferred.

## Pin patterns

`^name` matches only a value equal to the existing binding `name`; it binds nothing. A plain name in a pattern always introduces a new binding, so a pin is how a pattern refers to a value already in scope.

```elixir
expected = 1
case pair do
  {^expected, label} -> return label
  {_, _} -> return "other"
end
```

The pinned binding must exist before the pattern begins (a name bound earlier in the same pattern cannot be pinned), must have exactly the type at that position, and that type must support equality. Pins work in bindings, `case` arms, and inside list, tuple and map patterns. A pin can fail to match, so it never makes a `case` exhaustive; a repeated identical pin arm is reported as unreachable. A failed pinned binding reports `pattern match failed` at the pattern.

## Pipes

`value |> function(extraArguments)` means `function(value, extraArguments)`. The target must be a named call with parentheses, including for zero additional arguments. Pipe chains associate left to right, bind less tightly than arithmetic and more tightly than comparisons, and preserve exact function type/arity checks. The left value is evaluated exactly once, before the remaining arguments. There are no placeholders or anonymous targets. `IO.puts` and `assert` may be final pipe targets as statements.

```elixir
answer = 1 |> add(2) |> double()
assert(answer == 6)
"ready" |> IO.puts()
```

## Runtime diagnostics

Assertions, checked arithmetic, list bounds and failed destructuring emit one diagnostic line on stderr:

```text
program.alc:12:8: division by zero
```

The path is the source path passed to the build API, embedded safely in generated code. Lines and columns are one-based; columns count decoded Unicode characters. Arithmetic locations identify the operator, indexing identifies `[`, and assertion/match locations identify the statement start. Called functions report the failing operation's own source location. Missing map keys use the same location format. Known failures exit with status 2 and omit generated Go temporary paths and tracebacks. These are error locations, not an Alchem call-stack implementation; Go fatal failures such as stack exhaustion remain outside this mapping.

## Function values and list operations

`&name` references a declared user function, and `&name/arity` one arity of it. References are typed: `fn[Arg1,Arg2,...,Result]`, with the result type last (`fn[integer]` is a zero-argument function returning integer). References may be bound, passed, returned, or stored in collections. A callable binding is invoked by name, e.g. `callback(value)`. Function parameters accept the same `fn[...]` annotations. For backward compatibility, direct calls prefer declared functions over equally named local bindings; a local callable is used when no declared function has that name. Choose distinct callback names to avoid this ambiguity.

Functions of one name with different numbers of parameters are different functions, as in Elixir: `area/1` and `area/2` may both be defined, anywhere in the module, and each call goes to the one that takes its number of arguments, from the module itself or, written `Module.area(...)`, from another. A reference to such a name must give the arity, `&area/2`. A default argument makes a function accept a range of argument counts, and two arities of one name may not both accept the same count. There are no references to generic builtins. Function values, and collections containing them, cannot be compared for equality. Function-valued expressions can be called directly, including `callbacks[0](value)` or `make_callback()(value)`.

| Operation | Contract |
| --- | --- |
| `prepend(xs, value)` | Return a list with `value` before all `xs` elements, leaving `xs` unchanged; the element type must match |
| `concat(xs, ys)` | Return a fresh list containing both lists in order; their element types must match |
| `map(xs, callback)` | Call `fn[T,R]` once per element in order and return `list[R]` |
| `filter(xs, predicate)` | Call `fn[T,boolean]` once per element in order; retain true elements in their original order |
| `reduce(xs, initial, callback)` | Left-fold using `fn[A,T,A]`, calling `(accumulator, element)` in order; return `initial` unchanged for an empty list |

```elixir
def double(n: integer): integer do return n*2 end
def positive(n: integer): boolean do return n>0 end
def sum(acc: integer,n: integer): integer do return acc+n end
```

Inside `main`, `[-1,0,1,2] |> map(&double) |> filter(&positive) |> reduce(0,&sum)` evaluates to 6. Callback arguments and results are checked exactly. Empty inputs do not call callbacks. Typed callbacks supply context for empty list literals, e.g. `map([],&double)`. `prepend([],1)` can infer its element type; ambiguous `concat([],[])` still needs an annotated context.

Arguments follow normal eager, left-to-right evaluation before the operation. Callback failures preserve their source location and stop execution. Operations never mutate inputs. Costs with the current backend: `prepend` is amortized O(1) when a list is grown one element at a time, so building a list by repeated `prepend` is linear overall; a second `prepend` onto a list that has already been extended copies it once (O(n)) and is then cheap again. Taking a tail with `[head | tail]` or `List.drop`, and `List.take`, are O(1) and share storage with the original. Indexing and `length` are O(1). `concat` is O(n+m), and `map`/`filter`/`reduce` visit the input once, excluding callback costs. A `reduce` or `Enum.reduce` that builds a map or set updates one map in place, instead of copying a path of it for every element, when its function only looks things up in the accumulator and returns it unchanged or with one `put`, `Map.put`, `Map.put_new`, `Map.update` or `MapSet.put`, and makes no function that mentions it; the map it starts from is not changed, and any other function gets the ordinary copying behaviour. Sharing is never observable: no operation changes a list another binding or process can see. A short list taken from a long one keeps the long one's storage alive until it is no longer referenced.

## List and map operations

These operations never mutate their arguments and compose with pipes. `List` joins `IO`, `Map`, `Process` and `Supervisor` as a reserved module name.

| Operation | Result |
| --- | --- |
| `List.reverse(list)` | Elements in reverse order |
| `List.take(list, count)` | The first `count` elements, or the whole list when it is shorter |
| `List.drop(list, count)` | The list without its first `count` elements, or `[]` when it is shorter |
| `List.contains(list, value)` | `true` when an element equals `value` structurally; the element type must support equality |
| `List.sort(list)` | Ascending order for `list[integer]` or `list[string]` (strings compare by bytes) |
| `List.range(from, to)` | `[from, ..., to]` inclusive and ascending; `[]` when `to < from` |
| `List.zip(left, right)` | `list[tuple[A,B]]`, as long as the shorter input |
| `Map.merge(base, updates)` | A map with every entry of both; `updates` wins on equal keys |

`List.take` and `List.drop` fail with `count must be nonnegative` for a negative count. `List.range` fails with `range exceeds 1000000 elements` rather than allocate without bound. Both failures carry the call's source location. An empty list or map literal argument needs an expected type from context, as elsewhere.

## Strings, integer conversion and time

`left <> right` concatenates two strings. It binds tighter than comparisons and pipes and looser than arithmetic, so `"n=" <> Integer.to_string(a + b) == expected` reads as written. Strings are UTF-8; `String.length` and `String.slice` count Unicode code points, not bytes.

| Operation | Result |
| --- | --- |
| `String.length(text)` | Number of code points |
| `String.slice(text, start, count)` | Up to `count` code points beginning at zero-based `start`; shorter or empty when the string ends first |
| `String.contains(text, part)` | `true` when `part` occurs in `text`; the empty string is always contained |
| `String.split(text, separator)` | `list[string]` of the pieces between separators, including empty pieces |
| `String.join(parts, separator)` | The strings of `list[string]` joined with `separator` |
| `String.trim(text)` | `text` without leading and trailing whitespace |
| `String.upcase(text)`, `String.downcase(text)` | Simple per-character Unicode case mapping (`ß` stays `ß`) |
| `Integer.to_string(number)` | Decimal text |
| `Integer.parse(text)` | `result[integer,string]`: `ok(value)` for an optionally signed decimal that fits 64 bits, otherwise `error(reason)`, where the reason quotes the text, as in `"12a" is not an integer`; no spaces, separators or other bases |
| `Time.monotonic()` | Microseconds since the program started, from a clock that never goes backwards; use it to measure intervals |
| `Time.now()` | Milliseconds since the Unix epoch from the system clock; use it to report when something happened |

`String.slice` fails with `slice bounds must be nonnegative` for a negative start or count, and `String.split` fails with `separator must not be empty`; both carry the call's source location. `Integer`, `String` and `Time` are reserved module names. There is no implicit conversion: `"n=" <> 1` is a compile error.

## Program input

| Operation | Result |
| --- | --- |
| `System.argv()` | `list[string]` of the command-line arguments after the program name |
| `IO.read_line()` | `option[string]`: `some(line)` without its line ending (`\n` or `\r\n`), or `none` at end of input |
| `IO.read_all()` | The rest of standard input as one string; `""` when nothing remains |
| `File.read(path)` | `result[string,string]`: `ok(contents)`, or `error(reason)` when the file is missing, unreadable, a directory, larger than 16 MiB or not UTF-8 text |

Everything read becomes an ordinary string, so input is bounded and must be valid UTF-8. A line longer than 1 MiB fails with `input line exceeds 1048576 bytes`, standard input beyond 16 MiB read at once fails with `input exceeds 16777216 bytes`, and bytes that are not UTF-8 fail with `input is not valid UTF-8`; each carries the call's source location. `File.read` reports the same conditions as an `error` value instead of failing, because a missing or unsuitable file is an expected outcome: the reason is the operating system's message for a file that is missing, unreadable or a directory, `file exceeds 16777216 bytes` for one that is too large and `file is not valid UTF-8` for one that is not text. Arguments that are not valid UTF-8 have the invalid bytes replaced with U+FFFD.

Standard input is shared by all processes, and reads are serialized. A read blocks its process until the operating system returns and cannot be cancelled while it waits. `File`, `IO` and `System` are reserved module names. File writing and the other `File`, `System` and `IO` functions are listed in the [standard library](stdlib.md).

## Typed maps

`map[K,V]` is an immutable map with homogeneous keys and values. Keys must be `integer`, `boolean` or `string`; values may be any supported type, including nested collections. A literal uses `%{key => value, ...}`. An empty `%{}` requires expected map type context, such as `empty: map[string,integer] = %{}` or a typed parameter/return. Keys and values infer left to right when no annotation is supplied.

```elixir
data = %{"count" => 3,"zero" => 0}
changed = data |> put("count",4)
assert(data["count"] == 3 and changed["count"] == 4)
assert(has_key(data,"zero"))
assert(get(data,"absent",7) == 7)
```

| Operation | Contract |
| --- | --- |
| `m[key]` | Return the value; a missing key reports `map key not found` at the indexing location and exits 2 |
| `has_key(m,key)` | Return whether the key exists, independently of its value |
| `get(m,key,fallback)` | Return the value if present, otherwise the fallback; the fallback is eagerly evaluated even when the key exists |
| `put(m,key,value)` | Insert or replace a key in a new map; the original is unchanged |
| `length(m)` | Return the number of entries |

Every operation checks exact key/value types. Literal construction evaluates each key followed by its value, in source order. Duplicate literal keys are rejected at compile time. When evaluated dynamic key expressions collide, the later entry wins. Map equality is structural and independent of insertion order, subject to the restriction against function-containing equality. Map traversal returns sorted snapshots as described below; raw map storage has no user-visible iteration order. Indexed assignment, mutable updates and collection-valued keys remain unsupported.

Maps are persistent hash tries: `put` copies only the few nodes on the path to the changed key and shares the rest with the original, so it costs O(log n) rather than copying the map, and the original stays valid. Lookup and `has_key` are O(log n) with a small constant; `length` is O(1). Nested immutable values share storage. List `map`/`filter`/`reduce` operate on lists, not on maps.

## Map patterns and guards

Map patterns match a required subset of literal keys; extra subject keys are allowed. Values may contain any nested pattern. `%{}` is irrefutable for a map. Missing required keys or nonmatching values make a case arm fail; in a destructuring assignment they report `pattern match failed`. Pattern keys must be unique literals of the map key type. Map captures obey the same fresh-name and scope rules as other captures.

```elixir
case changed do
  %{"count" => n} when n>0 -> assert(n == 4)
  _ -> assert(false)
end
```

A case arm may add `when booleanExpression` between its pattern and `->`. The guard can refer to pattern captures and outer bindings. It runs once only after the entire pattern matches. A false guard continues to the next arm without running the body; an error in the guard fails execution with its own source location. Guards may use ordinary expressions and typed calls, including side effects; this is deliberately broader than Elixir's restricted guard language.

Guarded arms do not establish exhaustiveness or subsume later arms, even for a literal `true` guard. An unguarded fallback is therefore required unless other unguarded arms already prove coverage. An earlier unguarded pattern can still make a later guarded branch unreachable. Guard/body captures do not escape the selected arm. The compiler type-checks all guards and bodies, including ones that will not run for a particular input.

## Anonymous functions and lexical closures

Anonymous functions use explicit parameter and return types, consistent with named functions:

```elixir
factor = 3
tripled = map([1,2],fn(n: integer): integer do
  return n*factor
end)
assert(tripled == [3,6])
```

A closure has the same `fn[parameters...,result]` type as a named function reference. Its body supports bindings, calls, assertions, conditionals, guarded cases, nested closures and explicit returns. Every path must return the declared result type. There is no inferred parameter/return syntax, shorthand body, multi-clause anonymous function or variadic form.

Closures capture the lexical bindings visible when the function expression is checked/created. All captured values are immutable. Collections may share read-only storage; captures do not deep-copy lists or maps. Returned closures retain the values they need after the enclosing call returns. Separate factory or callback invocations retain separate parameter/local bindings. Later bindings are not visible, self-reference through the name being defined is unsupported, and parameters/local bindings cannot shadow an existing captured binding. Parameter names must be distinct and cannot be reserved keywords. Use named functions for recursion.

```elixir
def adder(offset: integer): fn[integer,integer] do
  return fn(value: integer): integer do return offset+value end
end
```

Within `main`, `adder(2)(3)` evaluates to 5. Zero-argument closures are supported, for example `(fn(): integer do return 7 end)()`. Closure bodies execute only when called; construction itself does not execute the body. Errors inside a closure report the failed operation's Alchem source location.

Postfix invocation accepts any function-valued expression, checks exact arity/types, evaluates the callee once before arguments, and evaluates arguments left to right. It supports returned, indexed and parenthesized values. Direct named calls retain declared-function precedence; `(callback)(value)` explicitly invokes the lexical binding when a declared function shares the same name. Pipe targets remain named calls; inline closures can be passed as callback arguments, e.g. `xs |> map(fn(n: integer): integer do return n+1 end)`.

## Deterministic map traversal and deletion

Map traversal uses the `Map` namespace, preserving ordinary binding names such as `keys` and `values`.

| Operation | Result |
| --- | --- |
| `Map.keys(m)` | `list[K]` of keys in ascending order |
| `Map.values(m)` | `list[V]` aligned with the same sorted key order |
| `Map.entries(m)` | `list[tuple[K,V]]` of sorted key/value pairs |
| `Map.delete(m,key)` | A new `map[K,V]` without the key; absent keys are allowed |

Integer keys sort numerically across the full signed 64-bit range. Strings sort by byte-lexical order, without locale rules or normalization. Boolean keys sort `false` before `true`. Ordering is independent of insertion order and Go map iteration. Map arguments are evaluated once; deletion evaluates the map before its key. Traversal never invokes function-valued entries.

```elixir
data = %{"pear" => 3,"apple" => 2}
assert(Map.keys(data) == ["apple","pear"])
assert(Map.values(data) == [2,3])
assert(Map.entries(data) == [{"apple",2},{"pear",3}])
changed = data |> Map.delete("pear")
assert(length(data) == 2 and length(changed) == 1)
```

Traversal returns a newly allocated list snapshot, including for empty maps. Keys/entries/values remain aligned; nested immutable values may share storage. Deleting a key leaves the original untouched and shares everything it can with it; deleting an absent key returns the same map. Empty map literals still require an expected map type before traversal.

The lists compose with existing operations, for example `m |> Map.entries() |> filter(predicate)` or `m |> Map.values() |> reduce(initial,callback)`. Function-containing values remain excluded from equality, even though such maps can be traversed and deleted. Builtin references such as `&Map.keys` are unsupported; wrap the call in a typed closure when a callback is needed.

The current backend sorts an O(n) key slice, so traversal is O(n log n) with O(n) extra storage, excluding key-comparison costs. Values/entries allocate an additional O(n) result. Deletion is O(log n). `Map.merge` costs O(m log n) for m updates. Traversal results are snapshots, not lazy iterators or mutable views. Key placement uses a hash seeded randomly per run, so traversal goes through the sorted snapshot rather than exposing internal order.

## Modules, process types and tooling

`import "relative.alc"` precedes function declarations and introduces the imported module's qualified calls/references. Build/check operate on an entry file or `main.alc` directory; [modules](modules.md) specifies resolution and error behavior.

`pid[T]` and `supervisor[T]` are local runtime capabilities with sendable message type `T`. Message data is immutable and is shared with the receiver rather than copied, which no program can observe; capabilities are explicitly shared, and function-containing messages are rejected. Only a PID's owning process may receive. These handles use identity through `Process.id` rather than structural equality. [Runtime](runtime.md) specifies all process APIs, monitors/links, restart policies/strategies, intensity and shutdown behavior.

Root failures now unwind through a recoverable runtime boundary and print Alchem source frames. Worker failures terminate that process and can be monitored, reported or supervised. Formatting, structured compile errors and target/deadline/trace/race options are specified in [tooling](tooling.md).

## Implicit returns and function clauses

The last expression of a function or closure body is its result. When the body ends in an `if` or `case`, the last expression of each branch is the result, so every branch must end in a value; an `if` without `else` cannot end a value-returning body. `return expression` remains available for early exits. Expressions that are not the last statement must be calls. `if` and `case` can also be used as values, described next.

A function may be written as several clauses with the same name and number of parameters. A parameter is a pattern, optionally followed by a type, and a clause may add a guard after the return type:

```elixir
def fact(0): integer do
  1
end
def fact(n: integer) when n > 0 do
  n * fact(n - 1)
end
def fact(_) do
  -1
end
```

Clauses are tried in source order and must be adjacent. Each parameter needs a type in at least one clause (a literal pattern supplies its own), the return type is written on at least one clause, and clauses that repeat a type must agree. The clauses together must cover every argument: a missing case is the compile error `non-exhaustive case`, and a clause that can never be reached is rejected. `main` and `extern` functions cannot have clauses. Clause parameters accept every pattern form, including lists, tuples, maps, structs and variants.

Exhaustiveness is checked structurally for booleans, lists, tuples, structs and sum types, including combinations such as a tuple of a boolean and a list. Integers, floats, strings and maps always need a catch-all.

## If and case as values

An `if` or `case` may stand wherever an expression is expected: on the right of a binding, as an argument, as an operand or inside interpolation. Its value is the last expression of the branch that runs.

```elixir
label = if count > 0 do "some" else "none" end
total = case items do
  [] -> 0
  [first | _] -> first * 2
end
```

Every branch must end in a value of the same type; the first branch fixes it unless the context expects one. A branch that only partly fixes it, such as `ok(n)` or `error("missing")` for a `result`, is completed by the others: `case parse(x) do ok(n) -> ok(n * 2); error(_) -> error("bad") end` is a `result[integer, string]` without an annotation. `if condition, do: value, else: value` is the same `if` on one line, and `unless` has the same form. An `if` used as a value needs an `else`, and a `case` must be exhaustive. Branches may contain bindings and other statements before their final expression; those bindings are not visible outside. `return` cannot be used inside an `if` or `case` that produces a value. At the start of a statement, `if` and `case` remain statements whose branches need not produce values.

## Floats

`float` literals need digits on both sides of the point and may carry an exponent: `1.5`, `0.25`, `1.0e21`, `1.5e-7`. `+`, `-`, `*`, `/` and unary minus work on two floats or two integers; there is no implicit conversion, so `1 + 1.5` is a type error. Float division by zero fails with `division by zero`. `%` is integer-only. Floats compare with `==` and the ordering operators, can be literal patterns, sort with `List.sort`, and cannot be map keys. Float arithmetic is not overflow-checked.

## Strings

`left <> right` concatenates two strings. A string literal may interpolate expressions with `#{expression}`; each must be a string, integer, float or boolean and is rendered as `Integer.to_string`, `Float.to_string` or `true`/`false` would render it; a float is its shortest text, in exponent form when that is strictly shorter or the value is at least 2**53, so `1000.0` is `1.0e3` and `1250.0` is `1250.0`, as in Elixir (`inspect` keeps plain digits up to `1.0e16`). Interpolated expressions may contain nested strings. Write `\#{` for a literal `#{`. Strings order lexicographically by bytes with `<`, `<=`, `>` and `>=`. The `String`, `Integer` and `Float` functions are listed in [standard library](stdlib.md).

## Atoms and keyword lists

`:name` is an atom: a name used as a value, of type `atom`. Atoms are compared with `==` and the ordering operators, match as literal patterns, may be map keys, interpolate as their name, and may be sent between processes. A colon is the start of an atom unless it directly follows a name, a number or a closing bracket, where it introduces a type annotation or a value, so `x: integer` and `[key: value]` are unaffected and an atom after a name is written with a space, `do: :ok`. Every atom has the one type `atom`: a `case` over atoms needs a catch-all, and a fixed set of alternatives that the compiler should check is a sum type.

`[name: value, other: value]` is a keyword list: the list `[{:name, value}, {:other, value}]`, of type `list[tuple[atom, T]]`, so its values share one type. It keeps its order and may repeat a key. The `Keyword` module reads and changes one, and `inspect` writes it back in the keyword form.

## Protocols

```elixir
defprotocol Describe do
  def describe(value): string
end

defimpl Describe, for: integer do
  def describe(n): string do
    "the number #{n}"
  end
end
```

`defprotocol` declares functions without bodies. `defimpl Protocol, for: Type` defines all of them for one type, which may be a builtin type, a struct or sum type from any module, or a generic type such as `list[a]`; the first parameter is the value of that type and needs no annotation. Both are written in a module, beside its functions. A protocol is known by its own name throughout the program, and an implementation may live in any module.

A call `Describe.describe(value)` is resolved when the program is compiled, to the implementation for the type of its first argument. Nothing is looked up while the program runs. The type must therefore be known where the call is written: calling a protocol function on a value of a type variable is a compile error, as is calling it on a type with no implementation. An implementation must define every function of the protocol with the declared number of arguments and result type.

## Macros

```elixir
defmacro unless_empty(items, do: body) do
  quote do
    if unquote(items) != [] do
      unquote(body)
    end
  end
end
```

A macro is a template. `defmacro name(parameters) do quote do ... end end` is written in a module, and its body is one `quote` block. A call `name(arguments)` is replaced by a copy of the quoted code in which each `unquote(parameter)` has become the argument given for it. A last parameter written `do: name` takes the `do ... end` block that follows the call. From another module a macro is called `Module.name(...)`.

Expansion happens before the program is typed and runs no code; the compiler has no way to run code while it compiles. The result is checked like any other code, and a problem in it is reported at the call. A macro whose template is a single expression, or a single `if` or `case`, may be used as a value; one with several statements is used as a statement.

The template is kept apart from the code around it. A name the template binds is a different name in each expansion, so it cannot clash with one at the call, and a function the template calls is the one in the macro's own module wherever the macro is used. An argument is evaluated wherever it is unquoted: unquoting it twice evaluates it twice.

A macro named `__using__` holds function definitions instead of statements. `use Module, option: value` adds them to the module that says so, with each option put where the template unquotes the parameter of that name.

Macros cannot inspect their arguments, compute at compile time, or define types.

## Structs

```elixir
struct Account do
  owner: string
  balance: integer
end
```

A struct is declared in a module, before or between its functions, and names a type. `%Account{owner: "ada", balance: 10}` builds a value and must give every field exactly once. `%Account{account | balance: 25}` copies `account` with the listed fields replaced. `account.balance` reads a field. The pattern `%Account{balance: amount}` matches any `Account` and binds or matches the listed fields; unlisted fields are ignored. Structs are immutable values compared structurally. A struct may not contain itself directly or through other structs and tuples; put the recursion behind a list, `option` or sum type.

## Sum types

```elixir
type Shape do
  circle(radius: float)
  rect(width: float, height: float)
  empty
end
```

A sum type lists its variants; each has zero or more typed fields. `Shape.circle(2.0)` and `Shape.empty` build values, and the same forms are patterns: `Shape.circle(r)`, `Shape.empty`. A `case` or set of function clauses over a sum type must cover every variant or include a catch-all. Sum types may be recursive.

Inside the declaring module a type is written `Shape`; other modules that import it write `Geometry.Shape`, `Geometry.Shape.circle(2.0)` and `%Geometry.Size{...}`.

## Option and result

`option[T]` is `none` or `some(value)`. `result[T,E]` is `ok(value)` or `error(reason)`. These constructors are written unqualified and are also patterns. `ok`, `error` and `some` are constructors only when applied; as bare names they remain ordinary bindings, and `none` is a constructor wherever no binding of that name is in scope. A constructor that does not determine every type argument, such as `none` or `ok(1)`, needs an expected type from a binding annotation, a parameter, a return type or the other side of a comparison.

```elixir
def halve(n: integer): result[integer, string] do
  if n % 2 == 0 do
    ok(n / 2)
  else
    error("#{n} is odd")
  end
end
```

## Generics

A lowercase name in a type that is not a builtin type is a type variable. A function is generic in the type variables of its parameters, and its return type may only use those:

```elixir
def fold([]: list[a], acc: b, _: fn[b, a, b]): b do
  acc
end
def fold([head | tail], acc, f) do
  fold(tail, f(acc, head), f)
end
```

Each call chooses the types from its arguments, and from the expected result type when the arguments leave one open. Inside the function a type variable is opaque: its values can be bound, passed, returned, stored and compared for equality, but not used as map keys, used in arithmetic or sent to a process. Comparing values of a type variable, whether with `==`, `!=`, a pin pattern or `List.contains`, makes equality a requirement of that variable: every call must then choose a type that supports equality, so passing a function where the variable is compared is the compile error `member needs equality for a, which fn[integer,integer] does not support`. The requirement carries through generic callers. A reference to a generic function (`&identity`) needs an expected function type. Structs and sum types take type parameters in brackets, `struct Pair[a, b]` and `type Tree[t]`, and are instantiated as `Pair[integer, string]`; literals and constructors infer the arguments. Because any unknown lowercase type name is a type variable, a misspelled builtin type in a parameter is reported where the value is first used.

## Anonymous functions with inferred types

`fn x, y -> body end` is a function whose parameter and result types come from where it is used: an argument position, an annotated binding, or a return. `fn -> body end` takes no parameters. A parameter may be a pattern, `fn {key, value} -> ... end`, which fails with `pattern match failed` if it does not match. The body's last expression is the result; a body that ends in a statement without a value, such as `IO.puts`, returns the empty tuple `{}`. Parameters may not shadow existing bindings.

A capture is the short form: `&(&1 + &2)`, `& &1.name` and `&String.length(&1)` are functions of as many parameters as the highest `&N` they mention. A capture extends to the end of the expression it starts, and captures cannot be nested. `&name` without arguments remains a reference to a named function.

Where no function type is expected, the types cannot be inferred; write the annotated form `fn(x: integer): integer do ... end`. The older builtins `map`, `filter` and `reduce` are such places: use `Enum.map` and friends with inferred functions.

## Ranges, membership and more operators

`first..last` is the integers from `first` to `last` inclusive, counting down when `first > last`; `first..last//step` uses the given step and is empty when the step points away from `last`. A zero step fails. A range is a lazy `stream[integer]`.

`value in enumerable` is true when the list, map, set, range or stream contains the value; the element type must support equality. For a map the elements are its `{key, value}` entries.

`left ++ right` concatenates two lists and `left -- right` removes, for each element of `right`, its first occurrence in `left`. `base ** exponent` raises integers (checked for overflow; a negative exponent fails) or floats. `&&`, `||` and a prefix `!` are spellings of `and`, `or` and `not`, with the same boolean-only operands. `..`, `++`, `--` and `<>` bind alike, below arithmetic and above comparison and `|>`; `**` binds tighter than `*` and associates to the right.

Function names may end in `?` or `!`: `def empty?(xs: list[a]): boolean`.

## Default arguments and function clauses in fn

```elixir
def greet(name: string, greeting: string \\ "hello"): string do
  "#{greeting}, #{name}"
end
```

`@name value` declares a module constant, and `@name` anywhere in the same module stands for the value: `@timeout 60 * 1000`. The value is built from literals, lists, tuples, maps, operators and earlier constants; it cannot call functions or read bindings. Each use is replaced by the value when the module is compiled, so a constant has no cost at run time. A name is defined once per module and is not visible from other modules. `@doc`, `@moduledoc`, `@typedoc`, `@tag`, `@describetag` and `@moduletag` keep their own meanings.

`name: type \\ value` gives a parameter a default value, which a call may leave out: `greet("ada")` is `greet("ada", "hello")`. Only trailing parameters may have one, and in a function with several clauses they are written in the first. The value is a constant: literals, lists, tuples and maps of them, `none`, `some(...)`, `ok(...)` or `error(...)`. A function still has one number of parameters; a reference `&greet` is to the function with all of them.

An anonymous function written with its clauses on the lines after `fn` takes one argument and tries the clauses in order, each `pattern -> body` with an optional guard:

```elixir
label = fn
  0 -> "zero"
  n when n < 0 -> "negative"
  _ -> "positive"
end
```

Its types are inferred from where it is used, like any `fn`; match a tuple to take several values.

## cond and raise

```elixir
label = cond do
  n < 0 -> "negative"
  n == 0 -> "zero"
  true -> "positive"
end
```

`unless condition do ... end` is an `if` on the opposite condition: its body runs when the condition is false, it may have an `else`, and it is a statement or a value.

`cond` runs the body of the first condition that is true, as a statement or as a value. Without a final `true ->` arm, a `cond` in which nothing matches fails with `no cond clause matched`.

`raise(message)` fails the current process with the message. It never returns, so it is accepted wherever any type is expected, including as the value of a branch.

## Streams and sets

`stream[T]` is a lazy sequence: building one runs nothing, and consuming it with an `Enum` function runs only as much as that function needs. Streams may be infinite. A stream holds the functions that produce it, so it cannot be compared or sent to another process.

`set[T]` is an immutable set of integers, strings or booleans, built with `MapSet.new`. Sets compare structurally and enumerate in ascending order.

`step[T]` is the answer a `Enum.reduce_while` callback gives: `cont(accumulator)` to go on or `halt(accumulator)` to stop.

## Comments

`#` starts a comment that runs to the end of the line. `alchem fmt` keeps comments: one on its own line stays where it is, and one written after code on the same line moves to the line below it. Inside a string, `#` is ordinary text and `#{` starts an interpolation.

## Documentation

```elixir
defmodule Temperature do
  @moduledoc """
  Temperature conversion.
  """

  @doc """
  Converts Celsius to Fahrenheit.

      alx> Temperature.to_fahrenheit(100.0)
      212.0
  """
  def to_fahrenheit(celsius: float): float do
    celsius * 9.0 / 5.0 + 32.0
  end
end
```

`@moduledoc` documents the module, `@doc` the function that follows and `@typedoc` the struct or type that follows. Each takes a string, usually a heredoc, or `false`. The clauses of a function share the documentation of the first documented one. Documentation is kept by `alchem fmt`, printed by `alchem doc file.alc`, and its `alx>` examples are run by `doctest Module` (see [testing Alchem programs](unit-testing.md)). Documentation with nothing declared after it is an error; `@doc false` is allowed anywhere.

A heredoc is a string that starts with `"""` at the end of a line and ends at the first later line that begins with `"""`. The expression it is part of may go on after the closing quotes, so a heredoc can be an argument: `String.trim("""` ... `""")`. The indentation of the closing quotes is removed from every line, and the text ends with a newline. As in a string, escapes apply and `#{...}` interpolates. `~S"""` starts a heredoc that is taken literally, as documentation whose examples contain backslashes is written; `~s"""` is the same as `"""`, and any other sigil letter applies that sigil to the heredoc's text. `alchem fmt` writes documentation as `~S"""` when its text holds a backslash or `#{`.

## try, rescue and after

```elixir
value = try do
  risky(input)
rescue
  "division by zero" -> 0
  message when String.contains?(message, "timeout") -> -1
after
  cleanup()
end
```

`try` runs its body. If the body fails, the failure is matched against the `rescue` arms in order, with optional guards; the first that matches supplies the value. A failure no arm matches continues to propagate, as does a request to stop the process, which cannot be rescued. The `after` block runs on every way out, after any arm, and its value is discarded. A `try` needs a `rescue`, a `catch`, an `after`, or a combination.

A rescue arm is one of:

- `e in NotFound`, which matches an exception of that type and binds it;
- a struct pattern of an exception type, such as `%NotFound{id: id}`;
- a string literal or a name, with an optional guard, which matches the message of any failure: of `raise("message")`, of an exception (its `message` field), or of a runtime failure such as `division by zero`.

An exception is declared with `defexception`, like a struct, and must have a `message: string` field:

```elixir
defexception NotFound do
  message: string
  id: integer
end
```

`raise(%NotFound{message: "no item", id: 7})` raises it, and `raise(e)` in a rescue arm raises it again.

`throw(value)` unwinds to the nearest enclosing `try` with a `catch` arm for the value's type, and is how a loop such as `Enum.each` is left early. The catch arms of one `try` take values of one type: the type of the values thrown in its body, or the type of the arm's pattern when it is a literal or struct, or a type written in the arm, as in `catch value: integer -> value`. A throw passes through `rescue` arms. One that no `catch` takes fails the process with `uncaught throw`.

`else` arms, after `rescue` and `catch`, match the body's value when nothing was raised or thrown, and their value is the value of the `try`. A failure inside an `else` arm is not rescued by the same `try`; a value that no `else` arm matches fails with `no else clause of this try matched`.

```elixir
count = try do
  Integer.parse(text)
rescue
  _ -> 0
else
  ok(n) -> n
  error(_) -> -1
end
```

As a value, the body (or, with `else`, every `else` arm) and every `rescue` and `catch` arm must end in a value of one type. As a statement, their values are ignored. `return` cannot be used inside a `try`.

## with

```elixir
with [name, age_text] <- String.split(text, ":"),
     ok(age) <- Integer.parse(age_text) do
  ok(%User{name: name, age: age})
else
  error(reason) -> error("bad age: #{reason}")
  parts -> error("expected name:age, got #{length(parts)} parts")
end
```

Each clause matches a pattern against an expression; bindings are visible to later clauses and the body. When every clause matches, the body runs. The first value that does not match its pattern ends the `with`:

- **With `else`**, that value is matched against the else arms. The clauses may produce different types; for each clause only the arms whose pattern fits its type apply, in order, and it is a compile error if none can. A value that no applicable arm matches fails at run time with `no case branch matched`.
- **Without `else`**, that value becomes the result, so it must fit the type of the body: either the same type, or an `error(reason)` of another `result` with the same reason type, or a `none` of another `option`. This is what lets `with ok(a) <- f(), ok(b) <- g(a) do ok(a + b) end` chain functions returning different `result` types.

`with` is a statement or a value, like `case`.

## for

```elixir
squares = for(n <- 1..5, do: n * n)

pairs = for x <- [1, 2, 3], y <- [1, 2, 3], x < y do
  {x, y}
end
```

A comprehension has generators, `pattern <- enumerable`, and filters, which are boolean expressions; the first item must be a generator. Later items see the bindings of earlier ones. The body runs for every combination that passes the filters, and the values it ends in are collected into a list. An element that does not match a generator's pattern is skipped, so `for some(n) <- maybe_numbers, do: n` keeps only the present values. The one-line form ends in `, do: expression` and may be parenthesized; the block form uses `do ... end`. As a statement, a `for` is run for its effects. 

One option may follow the generators and filters. `into: collectable` adds the values to a map (from `{key, value}` tuples), a set, a list or a string instead of building a list; an empty `%{}` or `[]` takes its type from the values. `uniq: true` drops values already produced. `reduce: initial` threads an accumulator: the block is then one or more `accumulator -> body` arms, the value of the body is the next accumulator, and the last accumulator is the value of the `for`. An empty initial value such as `%{}` needs a type, given by annotating what the `for` is bound to.

```elixir
squares = for n <- 1..3, into: %{}, do: {n, n * n}
total = for x <- [1, 2, 3], x != 2, reduce: 0 do
  acc -> acc + x
end
```

## Sigils and the match operator

| Sigil | Value |
| --- | --- |
| `~r/pattern/` | a `regex`, checked when the program is compiled; modifiers `i`, `m`, `s` and `u` may follow |
| `~w(one two three)` | `list[string]` of the whitespace-separated words |
| `~s(text)`, `~S(text)` | a `string` that may contain double quotes without escaping |
| `~h"<p>#{name}</p>"`, `~H(<br>)` | `Markup`: HTML whose interpolated values are escaped; see below |
| `~D[2026-01-05]` | a `Date` |
| `~T[13:04:05]` | a `Time` |
| `~N[2026-01-05 13:04:05]` | a `NaiveDateTime` |
| `~U[2026-01-05T13:04:05Z]` | a `DateTime` |

The delimiters may be `/ /`, `| |`, `" "`, `' '`, `( )`, `[ ]`, `{ }` or `< >`; a backslash escapes the closing one. `~s`, `~w`, `~r` and `~h` interpolate `#{expression}`, and `~S` and `~H` never do; an interpolation is an expression like any other, so strings in it may hold the delimiter, as in `~h"<a href=#{path("x")}>"`; a `~r` that interpolates is compiled when it runs instead of being checked when the program is compiled. A one-line sigil cannot span lines; a sigil heredoc (`~h"""`) can. Calendar sigils are checked when the program is compiled.

`~h` is an HTML template. Its own text is markup as written, and each interpolated value is converted by its type: a `string` is escaped (`&`, `<`, `>`, `"` and `'` become character references), `Markup` goes in unchanged, so templates nest, an `integer`, `float` or `atom` is written as text, and a `list[Markup]` is joined. Any other type is a compile error. The result is a `Markup` value, a struct whose `html` field holds the text; `Markup.to_string` returns it. Escaping makes a value safe inside an element or a quoted attribute value, so attribute values belong in quotes.

`~c(text)` is the code points of its text as a `list[integer]`; there are no charlists.

Any other sigil letter belongs to the program. `~x(text)mods` is the call `sigil_x("text", "mods")`: a function of two strings, the text and the modifier letters, defined in the module that uses the sigil or in one it imports. Its result may be of any type. `~x` interpolates, and `~X`, which calls `sigil_X`, does not.

`text =~ regex` is true when the regex matches somewhere in the string.
