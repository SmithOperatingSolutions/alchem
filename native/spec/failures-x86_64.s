# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# String.slice(text, start, count) before the grapheme runtime is called:
# RDI the string, RSI start, RDX count (native-failures.alc, zf_slice_check).
# Negative bounds fail (status 87). The pinned runtime slices a string of
# plain bytes (none from 0x80 up and no carriage return) as s[start:min(size,
# start+count)]; when start+count overflows and start is inside the string
# that is a Go panic, "slice bounds out of range [:N]" with the wrapped sum,
# which is built here and raised with status 97 (RSI the message).
.intel_syntax noprefix
.text
 mov rax,rsi
 or rax,rdx
 jns 1f
 mov edi,87
 mov eax,60
 syscall
1:
 mov rax,rsi
 add rax,rdx
 jno 9f
 cmp rsi,[rdi]
 jae 9f
 mov rcx,[rdi]
 lea r8,[rdi+8]
2:
 test rcx,rcx
 jz 3f
 cmp byte ptr [r8],0x80
 jae 9f
 cmp byte ptr [r8],13
 je 9f
 inc r8
 dec rcx
 jmp 2b
3:
 mov r9,rax
 lea r11,[r12+96]
 cmp r11,r13
 jbe 4f
# No room: the allocation hook (alchem-memory.md), in the twelve bytes an exit took.
 call qword ptr [0x400478]
 .byte 0x0f,0x1f,0x44,0x00,0x00
4:
 lea rdi,[r12+8]
 lea rsi,[rip+8f]
 mov ecx,51
 cld
 rep movsb
 neg r9
 mov rax,r9
 sub rsp,32
 lea r8,[rsp+32]
 mov ecx,10
5:
 xor edx,edx
 div rcx
 add dl,48
 dec r8
 mov [r8],dl
 test rax,rax
 jnz 5b
 lea rcx,[rsp+32]
 sub rcx,r8
 mov rsi,r8
 rep movsb
 add rsp,32
 mov byte ptr [rdi],93
 inc rdi
 lea rax,[r12+8]
 sub rdi,rax
 mov [r12],rdi
 mov rsi,r12
 mov r12,r11
 mov edi,97
 mov eax,60
 syscall
8: .ascii "panic: runtime error: slice bounds out of range [:-"
9:
