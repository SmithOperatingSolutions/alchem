# Instruction reference only; native-strings.alc emits these bytes.
# Not a build input. Pop i64 and return a fresh decimal string record.
.intel_syntax noprefix
.text
 pop rax
 sub rsp,32
 lea r9,[rsp+32]
 mov rsi,r9
 xor r8d,r8d
 test rax,rax
 jns digits
 mov r8d,1
 neg rax
digits:
 mov r10d,10
more:
 xor edx,edx
 div r10
 add dl,48
 dec rsi
 mov [rsi],dl
 test rax,rax
 jnz more
 test r8d,r8d
 jz length
 dec rsi
 mov byte ptr [rsi],45
length:
 sub r9,rsi
 lea r11,[r9+15]
 and r11,-8
 add r11,r12
 cmp r11,r13
 ja error
fits:
 mov rax,r12
 mov r12,r11
 mov [rax],r9
 lea rdi,[rax+8]
 mov rcx,r9
 cld
 rep movsb
 add rsp,32
 jmp done
# No room: the allocation hook (alchem-memory.md), and back.
error:
 call qword ptr [0x400478]
 .byte 0xe9
 .long fits-.-4
done:
