# Instruction reference only; native-strings.alc emits these bytes.
# Not a build input. RAX contains the immutable string record pointer.
.intel_syntax noprefix
.text
 mov rdx,[rax]
 lea rsi,[rax+8]
 test rdx,rdx
 jz newline
write:
 mov edi,1
 mov eax,1
 syscall
 cmp rax,-4
 je write
 test rax,rax
 jle error
 add rsi,rax
 sub rdx,rax
 jnz write
newline:
 push 10
 mov rsi,rsp
 mov edx,1
retry:
 mov edi,1
 mov eax,1
 syscall
 cmp rax,-4
 je retry
 cmp rax,1
 jne error
 pop rax
 jmp done
error:
 mov edi,74
 mov eax,60
 syscall
done:
