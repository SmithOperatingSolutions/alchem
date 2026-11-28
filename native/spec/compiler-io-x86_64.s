# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# The input and output of a compiler entry (a program whose entry is
# native_compile(source: bytes): bytes; nc_entry_compiler): all of standard
# input as one bytes value, read into room the collector reserves and grows
# (spec/alchem-memory.md), given to the entry in RDI; the bytes it returns
# written to standard output; status 0, or 65 or 74 and a message. The
# x86-64 compiler emits nc_io_prefix, the call and nc_io_suffix
# (native-runtime.alc), whose bytes are these; the ARM64 compiler the same
# assembled with markers before the messages' addresses
# (scripts/generate-marked-fragments.py, spec/arm64.md).
.intel_syntax noprefix
.text
 lea r11,[r12+65536]
 call qword ptr [0x400470]
 lea rsi,[r12+8]
1:
 mov rdx,r13
 sub rdx,rsi
 sub rdx,16
 ja 5f
 lea r11,[r13+1]
 call qword ptr [0x400458]
 add rsi,r11
 jmp 1b
5:
 xor edi,edi
 xor eax,eax
 syscall
 cmp rax,-4
 je 1b
 test rax,rax
 js io_read_failed
 jz 2f
 add rsi,rax
 mov rax,rsi
 sub rax,r12
 cmp rax,0x3ffffc07
 ja io_limit
 jmp 1b
2:
 mov rax,rsi
 sub rax,r12
 sub rax,8
 mov [r12],rax
 mov rdi,r12
 add rsi,7
 and rsi,-8
 mov r12,rsi
 mov r13,[r14-1536+216]
# The call of native_compile (nc_call: 9 bytes) stands here.
io_call:
 .skip 9
io_after:
 mov rdx,[rax]
 test rdx,rdx
 je io_empty
 lea rsi,[rax+8]
 mov edi,1
3:
 mov eax,1
 syscall
 cmp rax,-4
 je 3b
 test rax,rax
 jle io_write_failed
 add rsi,rax
 sub rdx,rax
 jne 3b
 xor edi,edi
 mov eax,60
 syscall
io_limit:
 lea rsi,[rip+io_m_limit]
 mov edx,42
 mov edi,65
 jmp 4f
io_empty:
 lea rsi,[rip+io_m_empty]
 mov edx,58
 mov edi,65
 jmp 4f
io_read_failed:
 lea rsi,[rip+io_m_read]
 mov edx,32
 mov edi,74
 jmp 4f
io_write_failed:
 lea rsi,[rip+io_m_write]
 mov edx,34
 mov edi,74
4:
 mov r10d,edi
 mov edi,2
 mov eax,1
 syscall
 mov edi,r10d
 mov eax,60
 syscall
io_m_limit:
 .ascii "E_RUNTIME_INPUT: input exceeds byte limit\n"
io_m_empty:
 .ascii "E_COMPILE: invalid or unsupported Alchem function program\n"
io_m_read:
 .ascii "E_RUNTIME_IO: input read failed\n"
io_m_write:
 .ascii "E_RUNTIME_IO: output write failed\n"
