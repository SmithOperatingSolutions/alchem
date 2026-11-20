# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# Coverage of a test program (alchem-testing-gen.md): a statement of a file
# under test starts with a call of this routine and, behind the call, its
# position in 32 bits, which the routine returns past. Each call has a count
# of its own: the 32-bit word 4*D of a region mapped at the first call, D
# being how far before the routine the call returns (the low 24 bits),
# and kept in word 80 of the library's block of working memory (Sys.state:
# the word that ends argv, mapped here when it is not yet). Every register
# is kept. The compiler puts after the routine the trace table's slot, the
# length of the trace routine, how many statements are counted and their
# positions (zf_cover_blob); the word at 4 is where that starts.
#
# The ARM64 compiler uses this translated (scripts/generate-arm64-runtimes.py,
# assembled with ARM defined): a call there is ARM64 code whose return address
# is the word behind it (zf_cover_call), and the calls are found where they
# stand in the ARM64 code (zf_cover_arm_points).
.intel_syntax noprefix
.text
cover_start:
 jmp 1f
# x86-64's jump is 2 bytes and ARM64's 4: the length is the word at 4 in both.
.ifndef ARM
 .byte 0,0
.endif
 .long cover_end
1:
 push rax
 push rdi
 mov rdi,[rsp+16]
 add qword ptr [rsp+16],4
 lea rax,[rip+cover_start]
 sub rax,rdi
 mov edi,eax
 and edi,0xFFFFFF
2:
 mov rax,[r14]
 mov rax,[r14+rax*8+8]
 test rax,rax
 jz 3f
 mov rax,[rax+80]
 test rax,rax
 jz 3f
 lock inc dword ptr [rax+rdi*4]
 pop rdi
 pop rax
 ret
3:
 push rcx
 push rdx
 push rsi
 push r8
 push r9
 push r10
 push r11
 push rdi
 mov rax,[r14]
 cmp qword ptr [r14+rax*8+8],0
 jne 4f
 xor edi,edi
 mov esi,16384
 mov edx,3
 mov r10d,34
 mov r8,-1
 xor r9d,r9d
 mov eax,9
 syscall
 cmp rax,-4096
 ja 9f
 mov rcx,[r14]
 mov [r14+rcx*8+8],rax
4:
 xor edi,edi
 mov esi,67108872
 mov edx,3
 mov r10d,0x4021
 mov r8,-1
 xor r9d,r9d
 mov eax,9
 syscall
 cmp rax,-4096
 ja 9f
 mov rcx,[r14]
 mov rcx,[r14+rcx*8+8]
 mov [rcx+80],rax
 pop rdi
 pop r11
 pop r10
 pop r9
 pop r8
 pop rsi
 pop rdx
 pop rcx
 jmp 2b
9:
 mov edi,71
 mov eax,60
 syscall
cover_end:
