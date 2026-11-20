# Executable format — draft

Initial output: Linux x86-64 ELF executable. Begin with a minimal static executable and deterministic layout. Validate ELF headers, program headers, entrypoint, section/segment permissions and exit status. Do not enable writable-and-executable memory segments.
