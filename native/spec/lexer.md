# Alchem-written native expression lexer

This bounded ASCII lexer lives in implementations/alchem/lexer.alc and is
compiled by the bootstrap source command. It is a lexer for the native expression
profile, not the complete production Alchem language. It scans immutable bytes;
all positions are byte offsets. It does not parse or evaluate expressions.

Token kinds retain the classifier codes: identifier=2, decimal integer=3,
plus=4, minus=5, star=6, left parenthesis=7, right parenthesis=8, EOF=9.
Kind 0 indicates an invalid byte or invalid request. Whitespace (space/tab/LF/CR)
is skipped and never returned as a token. Identifiers begin with an ASCII letter
or underscore, then continue with letters, underscores or digits. Decimal tokens
are maximal digit runs; signs are separate tokens. Integer conversion, overflow
and keyword recognition are later parser/semantic tasks. NUL, non-ASCII, quotes,
comments and other unsupported punctuation are lexical errors.

The public token API accepts (values: list[integer], cursor: integer):

- token_start returns the first non-whitespace position at/after cursor.
- token_kind returns the category of that token.
- token_end returns its exclusive end; identifiers/digits use maximal matching.
- token_error returns 0 for a valid token/EOF, 1 for an invalid byte, 2 for an
  invalid cursor, or 3 for input longer than 128 bytes. Length failure takes
  precedence over cursor failure. Valid cursors are 0..length inclusive.
- token_count counts remaining tokens, excluding EOF, or returns -1 on any
  lexical/request error. It does not allocate a token collection.
- first_error returns the first invalid byte offset, -1 on success, -2 for an
  invalid cursor, or -3 for oversized input.

An invalid byte has a one-byte span, so callers can recover by advancing to
its end. An invalid request has start/end -1 and kind 0. At EOF, start/end equal
length and kind is 9; repeated EOF requests stay there. Tokenization is stateless:
the caller advances by passing token_end as the next cursor. No text is copied;
spans retain indices into the immutable source. Unknown-byte errors retain the
exact offending offset; no low-byte exit-status truncation is used to test it.

The 128-byte public input bound keeps these recursive helpers within the native
256-active-call budget, including token-stream recursion. Longer inputs fail
explicitly before scanning. Low-level byte_at, skip_spaces and scan_digits retain
their existing behavior and do not gain this public token limit. The host must
still meet V4/V5 stack assumptions. Writable token storage, larger-input iteration,
strings/file IO and a parser/compiler written in Alchem remain future work.
