# Architecture

## Compiler pipeline

1. Lexer tokenizes UTF-8 Alchem source and reports source positions.
2. Parser builds a typed abstract syntax tree.
3. Semantic analysis resolves names, validates supported constructs and reports deterministic diagnostics.
4. Go backend emits Go source into an isolated temporary build directory.
5. Build driver invokes the Go toolchain with explicit target configuration and captures diagnostics.

The compiler must not execute arbitrary user-provided source during parsing or analysis. Build output paths and generated identifiers must be validated.

## Runtime direction

Alchem processes are planned as goroutines with separate logical mailboxes and managed lifecycle state. Define message copying/ownership before implementing send. Supervision will distinguish recoverable actor panics from unrecoverable runtime failures. No BEAM-equivalent isolation guarantee is implied.

## Initial boundaries

Keep compiler packages independent of runtime packages. The first milestone needs no actor runtime. Prefer deterministic builds and explicit dependency versions.


## Collection and pattern lowering

Collection types use canonical recursive names in the AST (`list[T]`, `tuple[T1,T2]`). Semantic analysis checks element types, contextual empty-list construction, access, pattern captures and conservative case coverage before generation. Lists lower to read-only Go slices and tuples to fixed anonymous structs. Equality is structural; the current backend uses Go deep equality.

Destructuring and case subjects are stored once. Length/literal guards short-circuit before generated field/index accesses, and captures are emitted only inside a successful match. Branch scopes map source names to fresh generated identifiers. Pipes lower to ordinary typed calls with the source value inserted once as the first argument.

The build driver passes the original Alchem source path to generation. Checked arithmetic, bounds, assertions and matches carry quoted file/line/column locations into small runtime helpers. Known failures write one diagnostic and exit 2; fatal Go runtime errors and full Alchem stack traces are outside this mapping.

## Callbacks, maps and guarded matching

Canonical types include `fn[parameters...,result]` and `map[key,value]`. Builtin signature checking instantiates callback/list contracts without executing source. Named function references lower to generated Go function values. Function-containing values are excluded from equality.

List operations use allocating generic helpers; map updates clone the outer map. Map literals lower to sequential key/value temporaries so dynamic collisions deterministically retain the later value. Maps have primitive keys, preventing invalid Go map-key types. Pattern guards use checked capture access paths behind a short-circuiting full-pattern condition; branch bindings are emitted only after both pattern and guard succeed. Exhaustiveness/subsumption proofs exclude guarded arms.

## Lexical closure lowering

Anonymous function expressions carry typed parameters, return types and statement bodies in the AST. Semantic analysis clones the lexical type scope at the expression, rejects shadowing/forward captures, and reuses return-path/type analysis. Function values remain excluded from structural equality.

The backend emits Go function literals referring only to generated immutable binding identifiers. Go retains captured storage for escaping closures; the language exposes no assignment that can mutate a captured slot or shared collection. Each enclosing invocation has independent parameter/local slots. Postfix calls lower to a parenthesized callee followed by ordered arguments, retaining single evaluation and source-tagged runtime operations.

## Sorted map snapshots

The checker derives traversal output types from the map signature. Code generation supplies a compiler-owned comparator for the primitive key type to generic helpers. Helpers collect/sort keys once, then read values/entries in that order; they never execute payload callbacks. Deletion copies all remaining entries into a new map. This avoids exposing Go map iteration order while preserving immutable aliases and single evaluation of source arguments.

## Integrated project/runtime architecture

The project loader resolves a deterministic import DAG and retains each function's module/file while qualifying callable names. Type analysis runs after linking and before any output is published. Generated projects contain a small `alchem.local` module and embedded actor sources, without remote dependency resolution or ambient Go workspace/VCS discovery.

Lists are a generated generic type wrapping a Go slice that stores the head last, so a tail is a reslice and `prepend` is an append. Each backing array created by `prepend` has a small claim counter: a prepend extends the array in place only if an atomic compare-and-swap wins the next slot, and otherwise copies. Two prepends onto the same list, including from different processes, therefore never overwrite each other. Runtime calls that take Go slices convert at the boundary.

Maps are a generic hash array mapped trie in the runtime package (`compiler/actor/hamt.go`): 32-way nodes addressed by five hash bits per level, path copying on update, and a linear bucket for keys whose full 64-bit hashes collide. String keys hash with a per-run random seed and integer keys with a seeded mixer, so a crafted key set cannot force collisions. Equality is never reflective: the generator emits a comparison function for each compared type.

Generated functions and function values carry a hidden process context. Callback helpers forward the invoking context, and cancellation is checked on entry to every function and closure, before each statement of the entry body, and inside every blocking or repeating runtime operation. Alchem has no loop construct, so the statements between two such points are bounded by the program text. Runtime PID capabilities and bounded ring-buffer mailboxes with their own small locks carry immutable, shared messages; each process parks on a single wake channel, and one runtime lock protects the lifecycle graph. A process context is used only by its own goroutine; no goroutine ID or OS thread-local lookup is used. Monitors/links and owned supervisor scopes are removed during completion. Restart managers stop/join affected subtrees before replacing PIDs.

Source-mapped Go directives and registered function names produce Alchem frames. Runtime failures panic through the current process boundary; the root renders them, while spawned/supervised boundaries retain failure metadata. The formatter consumes syntax-only ASTs, preserving imports and canonical pipes without requiring project resolution. All command and library build paths share staged publication and context/deadline options.

## Clauses, declared types and generics

Function clauses are merged right after parsing into one function whose body is a `case` over its parameters, so clauses reuse pattern checking, guards and code generation; the formatter works from the unmerged tree. A final expression statement is rewritten into a return before type checking. Exhaustiveness uses a pattern-matrix check that splits on a column's constructors only when a row names one, which keeps it terminating on recursive types.

Types remain canonical strings. A module's own type and constructor names are rewritten to `Module.Name` when it is parsed. Structs lower to Go structs and sum types to a Go interface with one struct per variant; `option` and `result` are ordinary sum types declared by the compiler. Type variables become Go type parameters, and every call and reference to a generic function carries the types the checker chose, so nothing depends on Go's own inference. Inference is one-directional unification of parameter types against argument types, seeded by the expected result type.

## Go bindings and packages

`check` and `build` write the same temporary Go module: `go.mod` with the required modules, the runtime, project-local Go packages under `ext/`, and a placeholder main package importing every bound package. `go list -export` then yields compiler export data, which the standard `go/importer` turns into `go/types` information without any dependency outside the standard library. Each `extern` is matched against its Go function or method and a wrapper is generated with exact conversions: checked integer narrowing, slice/map copies, struct field mapping, callback adapters and error or comma-ok results. Because the Go signature is known, mismatches are diagnostics at the declaration rather than Go compile errors, and the same code path serves `check`. Opaque Go types become Go type aliases; the checker treats them as neither comparable nor sendable.

Remote Alchem packages are fetched with `go mod download` and read from the module cache; their relative imports and local Go packages are confined to the package directory. The hash Go reports for each package, and the `go.sum` lines of the prepared module, are what `alchem.lock` records; locked `go.sum` lines are written into the temporary module before dependencies are resolved so that Go enforces them.

## Values from if and case, and equality requirements

An `if` or `case` in expression position is an expression holding that one statement. Its final expressions are marked as yields, checked against a per-expression result type, and generated as an immediately called Go function so that each branch can return its value. Equality on a type variable is recorded per function; after all functions are checked the requirements are propagated through the recorded instantiations to a fixed point and then tested against the concrete types each caller chose.
