# A program around the collector alone (harness/memory_reclaim.py, UNMAPPED, which
# holds these instructions assembled; as --64, objcopy -O binary -j .text):
# a block of three pages is mapped through the collector's system-call entry,
# its middle page is unmapped, and the only address of a value is kept in its
# last page. A collection must keep the value. The collector follows at "blob".
.intel_syntax noprefix
.text
start:
 mov r14,rsp
 sub rsp,8192
 lea rax,[rsp-4194304]
 mov [r14-8],rax
 mov eax,9
 xor edi,edi
 mov esi,67108864
 mov edx,3
 mov r10d,0x4022
 mov r8,-1
 xor r9d,r9d
 syscall
 mov r12,rax
 lea r13,[rax+67108864]
 call blob+15                      # gm_init
 mov eax,9
 xor edi,edi
 mov esi,12288
 mov edx,3
 mov r10d,0x22
 mov r8,-1
 xor r9d,r9d
 call blob+10                      # Sys.call: mmap
 mov r15,rax
 lea r11,[r12+4096]                # the value: 4096 bytes of a pattern
 cmp r11,r13
 jbe 1f
 call blob
1:
 mov rdi,r12
 mov r12,r11
 mov [r15+8192],rdi
 mov ecx,512
 mov rax,0x1122334455667788
 rep stosq
 lea r11,[r12+64]                  # a second one, so that no register is left just behind the first
 cmp r11,r13
 jbe 2f
 call blob
2:
 mov r12,r11
 mov eax,11
 lea rdi,[r15+4096]
 mov esi,4096
 call blob+10                      # Sys.call: munmap of the middle page
 xor edi,edi
 xor esi,esi
 xor ecx,ecx
 xor edx,edx
 xor r11d,r11d
 mov eax,1000001
 call blob+10                      # a collection
 mov ebx,2000                      # 8 MB of other values, zero where they are made
3:
 lea r11,[r12+4096]
 cmp r11,r13
 jbe 4f
 call blob
4:
 mov rdi,r12
 mov r12,r11
 mov ecx,512
 mov rax,-1
 rep stosq
 dec ebx
 jnz 3b
 mov eax,1000001
 call blob+10
 mov rsi,[r15+8192]
 mov ecx,512
 mov rax,0x1122334455667788
 xor edi,edi
5:
 cmp [rsi],rax
 jne 6f
 add rsi,8
 dec ecx
 jnz 5b
 jmp 7f
6:
 mov edi,1
7:
 mov eax,60
 syscall
blob:
