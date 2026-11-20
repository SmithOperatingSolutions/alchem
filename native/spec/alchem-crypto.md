# Crypto

`Crypto.hash`, `hmac`, `pbkdf2`, `strong_rand_bytes`, `secure_compare`,
`hash_password/1,2` and `verify_password`, with the pinned runtime's results
and failures. `harness/crypto.py` holds 28 programs with the pinned
compiler's status, output and trace frozen in, 10 programs it rejects, and
138 digest, HMAC and PBKDF2 triples of random data (every length around a
block boundary, and 3 MB read from a file) checked against Python's
`hashlib`.

## The runtime

The digests are machine code: `spec/crypto-x86_64.s` (4,020 bytes with its
tables; `scripts/generate-crypto-runtime.py` writes
`implementations/alchem/native-crypto-data.alc`). It is emitted once, in
function-table slot `functions+6` (after the float runtime's), for a
program that holds `Sys.hash`, which is to say one that got a `Crypto`
function appended. `Sys.hash(block)` is a library-only primitive
(`native-system.alc`, operation 15): the address of nine words — what to
do (0 a digest, 1 an HMAC, 2 PBKDF2), the algorithm (0 md5, 1 sha1, 2
sha224, 3 sha256, 4 sha384, 5 sha512), where the result goes, the key and
its length, the data and its length, the iterations and the bytes wanted.

MD5, SHA-1, SHA-256 and SHA-512 are one compression each, driven by a
table of block size, digest length and first state, so SHA-224 and SHA-384
cost a row. Nothing is allocated: three contexts of 224 bytes, the key's
block and the working digests are 1,024 bytes of stack, whatever the
length of the data. PBKDF2 keeps the two contexts that have taken the
key's pads and copies them for each round, which leaves two compressions
to a round: 600,000 rounds of SHA-256 (the default of `hash_password`)
take 0.3 s.

`library/Crypto.alc` checks the arguments in the pinned order and with the
pinned messages, writes the result straight into a fresh string, reads
random bytes with `getrandom` (again after a short read or EINTR), and
writes and reads the stored form `$pbkdf2-sha256$i=N$salt$key` with
base 64 as Go's `RawStdEncoding` has it: line breaks are passed over, a
last group of two or three characters gives one or two bytes whatever its
spare bits, `=` is refused. `secure_compare` looks at every byte.

The same runtime holds two operations that are no cryptography, because
they too need arithmetic no Alchem integer has (128 bits): 3 is the next
64 bits of Go's `math/rand/v2` PCG and 4 a number below a bound as
`Rand.Uint64N` draws it, for `library/Gen.alc` (`alchem-testing-gen.md`).
Both were checked against Go itself.

## Limits

- A digest costs its own bytes and 88 for the block. The data itself is a
  string in the program's arena (16 GiB reserved, paid for as it is
  touched): a string of 200,000,000 bytes was hashed with SHA-256 and MD5
  here and by the pinned compiler, with the same digests.
- `getrandom` failing with anything but EINTR ends the program with status
  74; Go's `crypto/rand` aborts the process there.
