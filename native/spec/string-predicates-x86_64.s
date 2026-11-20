# Auditable reference only; native-booleans.alc emits these bytes.
# Not a compiler build input.
.intel_syntax noprefix
.text
# EDI operation: 1 contains, 2 prefix, 3 suffix; stack holds hay then needle.
 pop rdx
 pop rsi
 mov r8,[rsi]
 mov r9,[rdx]
 cmp r9,r8
 ja fail
 add rsi,8
 add rdx,8
 mov r10,r8
 sub r10,r9
 xor r11d,r11d
 cmp edi,3
 jne outer
 mov r11,r10
outer:
 xor ecx,ecx
 lea r8,[rsi+r11]
 test r9,r9
 jz success
compare:
 mov al,[r8+rcx]
 cmp al,[rdx+rcx]
 jne advance
 inc rcx
 cmp rcx,r9
 jb compare
success:
 mov eax,1
 jmp done
advance:
 cmp edi,1
 jne fail
 cmp r11,r10
 jae fail
 inc r11
 jmp outer
fail:
 xor eax,eax
done:
