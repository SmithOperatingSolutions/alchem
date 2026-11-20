# Auditable instruction reference; never a compiler build input.
# Emitted by native-runtime.alc. take/drop prefixes append nc_slice_emit.
.intel_syntax noprefix
.text
.global sum_start,sum_end,reverse_start,reverse_end,take_start,take_end,drop_start,drop_end
sum_start:
 pop rsi
 mov rcx,[rsi]
 xor eax,eax
 test rcx,rcx
 jz 2f
1: movzx edx,byte ptr [rsi+rcx+7]
 add rax,rdx
 loop 1b
2:
sum_end:
reverse_start:
 pop rsi
 mov rcx,[rsi]
 lea r11,[rcx+15]
 and r11,-8
 add r11,r12
 cmp r11,r13
 ja 3f
5:
 mov rax,r12
 mov r12,r11
 mov [rax],rcx
 lea rdi,[rax+8]
 test rcx,rcx
 jz 4f
1: mov dl,[rsi+rcx+7]
 mov [rdi],dl
 inc rdi
 loop 1b
 jmp 4f
# No room: the allocation hook (alchem-memory.md), and back.
3: call qword ptr [0x400478]
 .byte 0xe9
 .long 5b-.-4
4:
reverse_end:
take_start:
 pop rdx
 pop rdi
 mov rcx,[rdi]
 xor esi,esi
 test rdx,rdx
 jns 2f
 add rdx,rcx
 jns 1f
 xor edx,edx
1: mov rsi,rdx
 mov rdx,rcx
 sub rdx,rsi
2: push rdi
 push rsi
 push rdx
take_end:
drop_start:
 pop rsi
 pop rdi
 mov rcx,[rdi]
 mov rdx,rcx
 test rsi,rsi
 jns 2f
 add rsi,rcx
 jns 1f
 xor esi,esi
1: mov rdx,rsi
 xor esi,esi
2: push rdi
 push rsi
 push rdx
drop_end:
