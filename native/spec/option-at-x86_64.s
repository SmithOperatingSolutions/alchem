# Audit reference only; native-options.alc emits these bytes. Not a build input.
.intel_syntax noprefix
.text
 pop rsi
 pop rdi
 mov rcx,[rdi]
 test rsi,rsi
 jns normalized
 add rsi,rcx
normalized:
 cmp rsi,rcx
 jae absent
 movzx eax,byte ptr [rdi+rsi+8]
 lea r11,[r12+16]
 cmp r11,r13
 ja box_error
fits:
 mov qword ptr [r12],1
 mov [r12+8],rax
 mov rax,r12
 mov r12,r11
 jmp box_done
# No room: the allocation hook (alchem-memory.md), and back.
box_error:
 call qword ptr [0x400478]
 .byte 0xe9
 .long fits-.-4
box_done:

 jmp done
absent:
 xor eax,eax
done:
