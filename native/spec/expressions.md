# Alchem-written arithmetic expression frontend

The helpers in implementations/alchem/lexer.alc now parse/evaluate this grammar:

```
expression = term (('+' | '-') term)*
term       = unary ('*' unary)*
unary      = ('+' | '-') unary | primary
primary    = decimal-integer | '(' expression ')'
```

Whitespace follows the lexer contract. Operators are left associative; * binds
more tightly than +/-. Identifiers are lexically valid but not expressions in
this initial grammar. Comments, strings and other operators remain unsupported.

`expression_error(values)` returns 0 success, 1 lexical error, 2 syntax error,
3 input over 128 bytes, 4 integer-literal overflow, or 5 over 16 nested unary
signs/parentheses. Input size and lexical validation precede parsing. The parser
then reports the first grammar/literal/depth failure it encounters. A complete
expression must consume all tokens; EOF cannot serve as an operand.

`expression_or(values, fallback)` returns the full i64 result or fallback on any
error. Arithmetic operations wrap modulo 2^64, matching native IR arithmetic.
Literals use checked decimal conversion. A minus immediately preceding a digit
token permits magnitude 9223372036854775808 (minimum i64); a plus or no sign does
not. Further unary operators apply ordinary wrapping arithmetic, so
`--9223372036854775808` is valid and evaluates to minimum i64. Parenthesized
positive overflow remains invalid: `-(9223372036854775808)` is rejected.

Parsing returns cursor offsets internally; a separate value pass reuses these
bounds and the checked literals, without constructing an AST or token array.
This deliberately small, repeated traversal is a correctness milestone, not an
optimized or self-hosted compiler. Internal parse/eval helpers assume validated
arguments; use the public functions. Parenthesis/sign depth and input bounds
keep recursive execution within native limits. Source lowering emits their
actual computations without executing these helpers during compilation.

No source file reader, declarations/bindings, semantic name resolution, machine-
code generation in Alchem, output writer or self-rebuild is implemented here.

Executable source now uses V6's native process-status guard instead of a
compile-time main/halt proof. All expression oracles, including value/deep-boundary
cases, compile through ordinary source main. The former proof-budget/library-
probe workaround is removed. This resolves status validation for expensive or
future dynamic computations; IO/storage primitives are still separate work.
