# Checked integer-literal conversion written in Alchem

The helpers in implementations/alchem/lexer.alc convert decimal byte spans to
signed i64 values. This is parser support, separate from the lexer's maximal
digit-span rule. No bootstrap IR or host-language conversion is added.

`decimal_error(values, start, stop, negative)` validates a nonempty half-open
span. negative is 0 for positive or 1 for negative; the sign is not in the span.
Leading zeroes are accepted. Error codes: 0 success, 1 nondigit, 2 invalid
span/sign flag, 3 input longer than 128 bytes, 4 signed-i64 overflow. Length has
precedence, then request validation, then the first left-to-right nondigit or
overflow. Valid spans satisfy 0 <= start < stop <= length.

`decimal_or(values, start, stop, negative, fallback)` returns the exact signed
value on success and fallback on any error. Call decimal_error when a diagnostic
is needed: fallback may itself equal a legitimate value. Positive magnitude is
limited to 9223372036854775807; negative magnitude to 9223372036854775808, so
minimum i64 is supported without first representing its positive magnitude.

`integer_error(values, cursor, negative)` validates the next lexer token as a
decimal integer. Token request/lexical errors are returned first; a non-integer
(including EOF or a sign token) returns 1. Otherwise decimal_error applies to
its digit span. `integer_or(values, cursor, negative, fallback)` combines this
check and conversion, returning fallback on error. Whitespace is skipped by the
lexer; trailing tokens are not part of the selected integer. The parser must
consume a unary sign separately and pass the appropriate flag.

Conversion accumulates a nonpositive value. Before each multiply/subtract it
checks against -922337203685477580 and the last allowed digit (7 or 8). The
validation pass proves all arithmetic in the value pass fits i64; there is no
silent wrap/truncation of invalid literals. Error paths do not expose partial
values. Internal recursive helpers assume validated arguments; callers should
use the public functions above. The same 128-byte input / native call budget
assumptions as the token API apply.
