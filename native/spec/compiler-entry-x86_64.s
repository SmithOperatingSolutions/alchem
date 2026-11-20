.intel_syntax noprefix
.text
.global _start,call_slot,after_call
_start:
mov r9,r12
add r12,16776200
lea rsi,[r9+8]
xor r8d,r8d
mov edx,16776192
xor edi,edi
read_loop:
xor eax,eax
syscall
cmp rax,-4
je read_loop
test rax,rax
js read_error
jz read_done
add r8,rax
cmp r8,16776191
ja input_error
add rsi,rax
sub rdx,rax
jmp read_loop
read_done:
mov [r9],r8
mov rdi,r9
call_slot:
.fill 9,1,0x90
after_call:
mov rdx,[rax]
test rdx,rdx
jz compile_error
lea rsi,[rax+8]
mov edi,1
write_loop:
mov eax,1
syscall
cmp rax,-4
je write_loop
test rax,rax
jle write_error
add rsi,rax
sub rdx,rax
jnz write_loop
xor edi,edi
mov eax,60
syscall
input_error:
lea rsi,[rip+input_message]
mov edx,input_message_end-input_message
mov edi,65
jmp diagnostic
compile_error:
lea rsi,[rip+compile_message]
mov edx,compile_message_end-compile_message
mov edi,65
jmp diagnostic
read_error:
lea rsi,[rip+read_message]
mov edx,read_message_end-read_message
mov edi,74
jmp diagnostic
write_error:
lea rsi,[rip+write_message]
mov edx,write_message_end-write_message
mov edi,74
diagnostic:
mov r10d,edi
mov edi,2
mov eax,1
syscall
mov edi,r10d
mov eax,60
syscall
input_message:
.ascii "E_RUNTIME_INPUT: input exceeds byte limit\n"
input_message_end:
compile_message:
.ascii "E_COMPILE: invalid or unsupported Alchem function program\n"
compile_message_end:
read_message:
.ascii "E_RUNTIME_IO: input read failed\n"
read_message_end:
write_message:
.ascii "E_RUNTIME_IO: output write failed\n"
write_message_end:
