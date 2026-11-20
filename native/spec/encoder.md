# Alchem-written ELF emitter — small Linux exit target

implementations/alchem/encoder.alc now constructs a complete executable image,
not just an instruction fragment. emit_exit(value) builds MOV EDI imm32 followed
by MOV EAX,60; syscall (12 bytes). emit_elf_exit(value) builds the ELF64 header,
program header, padding and code as immutable byte buffers in Alchem, returning
all 140 bytes. There is no host ELF-header builder or field patching in export.

The target is Linux x86-64 ET_EXEC, one RX PT_LOAD segment at 0x400000, entry
0x400080, phoff 64, one 56-byte program header, no section table, 8 bytes padding,
file/memory size 140 and alignment 4096. All 0..255 exit immediates are supported;
other i64 values fail checked packing. The private header helper currently uses
one checked byte for file size; the public factory always has 12 bytes of code.
This is a small fixed target, not an arbitrary-size ELF writer or source compiler.

## Produce an executable now

After scripts/build-native.sh has built the bootstrap tools:

```sh
python3 scripts/emit-alchem-executable.py --status 42 --output /tmp/exit42 --save-emitter /tmp/alchem-emitter42
/tmp/exit42
echo "$?"  # 42
/tmp/alchem-emitter42 > /tmp/exit42-again
chmod 700 /tmp/exit42-again
/tmp/exit42-again
```

The saved Alchem emitter reproduces its configured image using native writes;
it runs with an empty PATH and does not invoke Python, the frontend/backend,
Go, Rust, Cargo or an external compiler/linker. It is configured during bootstrap,
not yet a general compiler accepting a new program at runtime.

The helper is an explicit bootstrap/export bridge: it compiles the Alchem emitter
with the prebuilt frontend/backend, adds an existing IR bytes.write observation
of its result, runs it and saves stdout unchanged. It does not construct/patch
ELF bytes. Source-level binary IO is still absent. Successful files use 0700 and
atomic replacement; construction failure preserves existing output. Saving an
optional emitter is a separate atomic file replacement, not a two-file transaction.
The helper rejects overwriting its source or bootstrap tools.

The encoder oracle independently parses every header/segment field, checks exact
machine code, saves returned bytes unchanged and executes all 256 valid images
through both backends. Four invalid immediates fail; export/preservation/source
protection and empty-PATH saved-emitter reuse are tested. No Python-generated ELF
envelope remains. readelf confirms the demonstrated layout.

Wide integer encoding/relocations, general instruction selection, binary source
output, runtime input/file semantics and compiling Alchem source in Alchem remain
future work. This emitter is an Alchem-written executable-producing component;
it is not self-hosted and does not satisfy compiler self-rebuild benchmark gates.
