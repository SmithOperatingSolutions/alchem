# Audit reference only; native-options.alc emits these bytes. Not a build input.
.intel_syntax noprefix
.text
 lea r11,[r12+16]
 cmp r11,r13
 ja error
fits:
 mov qword ptr [r12],1
 mov [r12+8],rax
 mov rax,r12
 mov r12,r11
 jmp done
# No room: the allocation hook (alchem-memory.md), and back.
error:
 call qword ptr [0x400478]
 .byte 0xe9
 .long fits-.-4
done:
