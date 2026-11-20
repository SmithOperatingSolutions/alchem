# Additional native library operations; independent fixed-size scratch space.
.macro library_error status
 mov $\status,%edi
 mov $60,%eax
 syscall
.endm
.macro byte_arena
 lea 15(%rdx),%r11
 and $-8,%r11
 add %r12,%r11
 cmp %r13,%r11
 jbe 991f
 call *0x400478
991:
 mov %r12,%rax
 mov %r11,%r12
 mov %rdx,(%rax)
.endm
# A block for a list of RCX elements (alchem-lists.md): RAX is its first
# pair; the counts and elements are the caller's to write.
.macro list_arena
 mov %rcx,%r11
 shl $4,%r11
 lea 24(%r12,%r11),%r11
 cmp %r13,%r11
 jbe 992f
 call *0x400478
992:
 movq $-2,(%r12)
 lea 16(%r12),%rax
 movq $0,-8(%r11)
 mov %r11,%r12
.endm
.section .text.na_base,"ax"
 pop %rsi
 pop %rax
 cmp $2,%rsi
 jl 9f
 cmp $36,%rsi
 jg 9f
 sub $80,%rsp
 lea 80(%rsp),%r10
 xor %r8d,%r8d
 test %rax,%rax
 jns 1f
 mov $1,%r8d
 jmp 2f
1:
 neg %rax
2:
 xor %r9d,%r9d
3:
 cqto
 idiv %rsi
 neg %edx
 cmp $10,%edx
 jb 4f
 add $7,%edx
4:
 add $48,%edx
 dec %r10
 mov %dl,(%r10)
 inc %r9
 test %rax,%rax
 jnz 3b
 test %r8d,%r8d
 jz 5f
 dec %r10
 movb $45,(%r10)
 inc %r9
5:
 mov %r9,%rdx
 byte_arena
 lea 8(%rax),%rdi
 mov %r10,%rsi
 mov %r9,%rcx
 cld
 rep movsb
 add $80,%rsp
 jmp 10f
9:
 library_error 82
10:
.section .text.na_digits,"ax"
 pop %rsi
 pop %rax
 cmp $2,%rsi
 jl 9f
 sub $512,%rsp
 lea 512(%rsp),%r10
 xor %ecx,%ecx
1:
 cqto
 idiv %rsi
 sub $8,%r10
 mov %rdx,(%r10)
 inc %rcx
 test %rax,%rax
 jnz 1b
 list_arena
 mov %rax,%rdi
 mov %rcx,%rdx
2:
 mov %rdx,(%rdi)
 mov (%r10),%r11
 mov %r11,8(%rdi)
 add $8,%r10
 add $16,%rdi
 dec %rdx
 jnz 2b
 add $512,%rsp
 jmp 10f
9:
 library_error 83
10:
.section .text.na_undigits,"ax"
 pop %rsi
 pop %rdi
 cmp $2,%rsi
 jl 9f
 mov (%rdi),%rcx
 xor %eax,%eax
1:
 test %rcx,%rcx
 jz 10f
 mov 8(%rdi),%rdx
 test %rdx,%rdx
 js 7f
 cmp %rsi,%rdx
 jae 7f
 imul %rsi,%rax
 jo 8f
 add %rdx,%rax
 jo 8f
 add $16,%rdi
 dec %rcx
 jmp 1b
8:
 library_error 85
7:
 library_error 84
9:
 library_error 83
10:
.section .text.na_duplicate,"ax"
 pop %r9
 pop %r8
 test %r9,%r9
 js 9f
 mov (%r8),%rax
 mul %r9
 cmp $1073741824,%rax
 jg 9f
 test %rdx,%rdx
 jnz 7f
 test %rax,%rax
 js 7f
 mov %rax,%rdx
 # The size is bounded before rounded allocation can overflow: by what is
 # left of the arena, or in a program that collects (R13 is 0 there,
 # alchem-memory.md) by all of it.
 mov %r13,%r11
 sub %r12,%r11
 test %r13,%r13
 jnz 77f
 mov -1512(%r14),%r11
 sub -1520(%r14),%r11
77:
 cmp %r11,%rdx
 jae 8f
 byte_arena
 mov %rax,%rdx
 lea 8(%rax),%rdi
 test %r9,%r9
 jz 10f
 cmpq $0,(%r8)
 je 10f
1:
 lea 8(%r8),%rsi
 mov (%r8),%rcx
 cld
 rep movsb
 dec %r9
 jnz 1b
 mov %rdx,%rax
 jmp 10f
8:
 library_error 71
7:
 library_error 96
9:
 library_error 81
10:
.section .text.na_join,"ax"
 pop %r10
 pop %r8
 xor %r9d,%r9d
 test %r10,%r10
 jz 1f
 mov (%r10),%r9
1:
 xor %edx,%edx
 mov %r8,%rsi
2:
 cmpq $0,(%rsi)
 je 4f
 mov 8(%rsi),%rax
 add (%rax),%rdx
 cmp %r8,%rsi
 je 3f
 add %r9,%rdx
3:
 add $16,%rsi
 jmp 2b
4:
 byte_arena
 mov %rax,%rdx
 lea 8(%rax),%rdi
 mov %r8,%r11
5:
 cmpq $0,(%r11)
 je 8f
 cmp %r8,%r11
 je 6f
 lea 8(%r10),%rsi
 mov %r9,%rcx
 cld
 rep movsb
6:
 mov 8(%r11),%rsi
 mov (%rsi),%rcx
 add $8,%rsi
 cld
 rep movsb
 add $16,%r11
 jmp 5b
8:
 mov %rdx,%rax
.section .text.na_clock,"ax"
 sub $16,%rsp
 xor %edi,%edi
 mov %rsp,%rsi
 mov $228,%eax
 syscall
 test %rax,%rax
 js 9f
 mov (%rsp),%rax
 imul $1000000000,%rax
 add 8(%rsp),%rax
 add $16,%rsp
 jmp 10f
9:
 library_error 74
10:
.section .text.na_pid,"ax"
 mov $39,%eax
 syscall
.section .text.na_filter,"ax"
 pop %r10
 pop %rsi
 mov (%rsi),%rcx
 list_arena
 mov %rax,%r8
 xor %r9d,%r9d
1:
 test %rcx,%rcx
 jz 3f
 push %r10
 push %rsi
 push %r8
 push %rcx
 push %r9
 mov 8(%rsi),%rdi
 call *(%r10)
 pop %r9
 pop %rcx
 pop %r8
 pop %rsi
 pop %r10
 test %rax,%rax
 jz 2f
 mov %r9,%rdx
 shl $4,%rdx
 mov 8(%rsi),%rax
 mov %rax,8(%r8,%rdx)
 inc %r9
2:
 add $16,%rsi
 dec %rcx
 jmp 1b
3:
 mov %r8,%rax
 mov %r8,%rdx
# The elements kept lie in the first pairs: their counts, down to the 0
# that ends the list.
4:
 mov %r9,(%rdx)
 add $16,%rdx
 sub $1,%r9
 jns 4b
.section .note.GNU-stack,"",@progbits
.section .text.na_write,"ax"
 mov (%rax),%rdx
 lea 8(%rax),%rsi
 test %rdx,%rdx
 jz 3f
1:
 mov $1,%edi
 mov $1,%eax
 syscall
 cmp $-4,%rax
 je 1b
 test %rax,%rax
 jle 2f
 add %rax,%rsi
 sub %rax,%rdx
 jnz 1b
 jmp 3f
2:
 library_error 74
3:
# Standard input readers, Intel syntax. Go utf8.Valid acceptance: invalid UTF-8
# ends the program at the call (status 89 here, which the compiler turns
# into the failure: native-failures.alc), as does a line too long (88) and a
# read_all that cannot read (90); read_line takes a read failure as the end of input; input beyond the arena exits71.
.intel_syntax noprefix
# The hooks of the collector (alchem-memory.md, spec/memory-x86_64.s).
# gm_fit: a value from R12 to \reg is about to be made.
.macro gm_fit reg
 cmp \reg,r13
 jbe 771f
 .ifnc \reg,r11
 xchg \reg,r11
 .endif
 call qword ptr [0x400478]
 .ifnc \reg,r11
 xchg \reg,r11
 .endif
771:
.endm
# gm_reserve: room from R12 for \size bytes of a value whose size is not
# known yet; R13 is its end until gm_release.
.macro gm_reserve size
 lea r11,[r12+\size]
 call qword ptr [0x400470]
.endm
# gm_grow: the room from R12 to R13 is full and has to reach \end: it may
# move, and R11 is by how much.
.macro gm_grow end
 lea r11,[\end]
 call qword ptr [0x400458]
.endm
.macro gm_release
 mov r13,[r14-1536+216]
.endm
# RSI<RDX: ECX width of the valid UTF-8 sequence at RSI, else jump to \invalid.
# Go utf8 acceptance; clobbers RAX,R8,R9.
.macro utf8_width invalid
 movzx eax,byte ptr [rsi]
 mov ecx,1
 cmp eax,128
 jb 87f
 cmp eax,194
 jb \invalid
 cmp eax,244
 ja \invalid
 inc ecx
 cmp eax,224
 jb 83f
 inc ecx
 cmp eax,240
 jb 83f
 inc ecx
83:
 mov r8,rdx
 sub r8,rsi
 cmp r8,rcx
 jb \invalid
 movzx r9d,byte ptr [rsi+1]
 mov r8d,128
 cmp eax,224
 jne 84f
 mov r8d,160
84:
 cmp eax,240
 jne 85f
 mov r8d,144
85:
 cmp r9d,r8d
 jb \invalid
 mov r8d,191
 cmp eax,237
 jne 86f
 mov r8d,159
86:
 cmp eax,244
 jne 82f
 mov r8d,143
82:
 cmp r9d,r8d
 ja \invalid
 cmp ecx,3
 jb 87f
 movzx r9d,byte ptr [rsi+2]
 and r9d,192
 cmp r9d,128
 jne \invalid
 cmp ecx,4
 jb 87f
 movzx r9d,byte ptr [rsi+3]
 and r9d,192
 cmp r9d,128
 jne \invalid
87:
.endm
# RSI..RDX must be valid UTF-8 or the process exits73; clobbers RAX,RCX,R8,R9.
.macro utf8_valid
81:
 cmp rsi,rdx
 jae 89f
 utf8_width 88f
 add rsi,rcx
 jmp 81b
88:
 mov edi,89
 mov eax,60
 syscall
89:
.endm
.section .text.na_read_all,"ax"
 gm_reserve 65536
 lea rsi,[r12+8]
 cmp rsi,r13
 ja 9f
# Bytes the library read ahead of a character that turned out to be none
# (Sys.next: the state block's words 40 and 48) come first.
 mov rax,[r14]
 mov rax,[r14+rax*8+8]
 test rax,rax
 jz 1f
 mov rcx,[rax+48]
 test rcx,rcx
 jz 1f
 lea rdx,[rsi+8]
 cmp rdx,r13
 ja 9f
 mov rdx,[rax+40]
 mov [rsi],rdx
 add rsi,rcx
 mov qword ptr [rax+48],0
# The room is filled up to 16 bytes before its end, then made larger.
1:
 mov rdx,r13
 sub rdx,rsi
 sub rdx,16
 ja 5f
 gm_grow r13+1
 add rsi,r11
 jmp 1b
5:
 xor edi,edi
 xor eax,eax
 syscall
# A standard input that is closed reads as empty (the pinned runtime opens
# /dev/null in its place).
 cmp rax,-4
 je 1b
 cmp rax,-9
 je 2f
 test rax,rax
 js 7f
 jz 2f
 add rsi,rax
 jmp 1b
2:
 mov r10,rsi
 lea rsi,[r12+8]
 mov rdx,r10
 utf8_valid
 mov rax,r12
 lea rdx,[r10-8]
 sub rdx,rax
 mov [rax],rdx
 add r10,7
 and r10,-8
 mov r12,r10
 jmp 10f
7:
 mov edi,90
 mov eax,60
 syscall
9:
 mov edi,71
 mov eax,60
 syscall
10:
 gm_release
# One byte per read so no input past the newline is consumed.
.section .text.na_read_line,"ax"
 gm_reserve 4096
 lea rsi,[r12+8]
# 32 bytes stay free behind the line for its end and the option's record.
1:
 lea rax,[rsi+32]
 cmp rax,r13
 jb 11f
 gm_grow r13+1
 add rsi,r11
 jmp 1b
11:
# A byte the library read ahead (Sys.next) comes before the input's next.
 mov rax,[r14]
 mov rax,[r14+rax*8+8]
 test rax,rax
 jz 20f
 mov rcx,[rax+48]
 test rcx,rcx
 jz 20f
 dec rcx
 mov [rax+48],rcx
 mov rdx,[rax+40]
 mov [rsi],dl
 shr rdx,8
 mov [rax+40],rdx
 jmp 21f
20:
 mov edx,1
 xor edi,edi
 xor eax,eax
 syscall
 cmp rax,-4
 je 1b
 test rax,rax
 js 2f
 jz 2f
21:
 cmp byte ptr [rsi],10
 je 3f
 inc rsi
 mov rax,rsi
 sub rax,r12
 cmp rax,1048585
 ja 8f
 jmp 1b
2:
 lea rax,[r12+8]
 cmp rsi,rax
 jne 3f
 xor eax,eax
 jmp 10f
3:
 lea rax,[r12+8]
 cmp rsi,rax
 je 4f
 cmp byte ptr [rsi-1],13
 jne 4f
 dec rsi
4:
 mov rax,rsi
 sub rax,r12
 cmp rax,1048584
 ja 8f
 mov r10,rsi
 lea rsi,[r12+8]
 mov rdx,r10
 utf8_valid
 lea rdx,[r10-8]
 sub rdx,r12
 mov [r12],rdx
 add r10,7
 and r10,-8
 lea r11,[r10+16]
 gm_fit r11
 mov qword ptr [r10],1
 mov [r10+8],r12
 mov rax,r10
 mov r12,r11
 jmp 10f
8:
 mov edi,88
 mov eax,60
 syscall
9:
 mov edi,71
 mov eax,60
 syscall
10:
 gm_release
# The entry stub keeps the initial stack pointer in R14: argc, argv..., 0, envp..., 0.
.macro string_record
 lea rdx,[r11+15]
 and rdx,-8
 add rdx,r12
 gm_fit rdx
 mov rax,r12
 mov r12,rdx
 mov [rax],r11
.endm
# System.argv(): os.Args[1:], each run of invalid UTF-8 replaced by one U+FFFD.
.section .text.na_argv,"ax"
 mov rcx,[r14]
 dec rcx
 jns 1f
 xor ecx,ecx
1:
 mov r11,rcx
 shl r11,4
 lea r11,[r12+r11+24]
 gm_fit r11
 mov qword ptr [r12],-2
 lea rax,[r12+16]
 mov r12,r11
 mov rdx,rax
7:
 mov [rdx],rcx
 add rdx,16
 sub rcx,1
 jns 7b
# Stack slots: [rsp] index, [rsp+8] current string record, [rsp+16] list.
 push rax
 push 0
 push 0
2:
 mov r10,[rsp]
 mov rax,[rsp+16]
 cmp r10,[rax]
 jae 8f
 xor edi,edi
 xor r11d,r11d
3:
 mov rsi,[r14+r10*8+16]
 mov rdx,rsi
4:
 cmp byte ptr [rdx],0
 je 5f
 inc rdx
 jmp 4b
5:
 call 20f
 test rdi,rdi
 jnz 6f
 string_record
 mov [rsp+8],rax
 lea r11,[rax+8]
 mov edi,1
 mov r10,[rsp]
 jmp 3b
6:
 mov r10,[rsp]
 mov rax,[rsp+16]
 mov rdx,[rsp+8]
 mov rcx,r10
 shl rcx,4
 mov [rax+rcx+8],rdx
 inc qword ptr [rsp]
 jmp 2b
8:
 pop rax
 pop rax
 pop rax
 jmp 10f
9:
 mov edi,71
 mov eax,60
 syscall
# Copy RSI..RDX as strings.ToValidUTF8: RDI write flag, R11 cursor; R10 run flag.
20:
 xor r10d,r10d
21:
 cmp rsi,rdx
 jae 25f
 utf8_width 23f
 xor r10d,r10d
22:
 test rdi,rdi
 jz 26f
 movzx eax,byte ptr [rsi]
 mov [r11],al
26:
 inc r11
 inc rsi
 dec ecx
 jnz 22b
 jmp 21b
23:
 inc rsi
 test r10,r10
 jnz 21b
 mov r10d,1
 test rdi,rdi
 jz 24f
 mov byte ptr [r11],239
 mov byte ptr [r11+1],191
 mov byte ptr [r11+2],189
24:
 add r11,3
 jmp 21b
25:
 ret
10:
# System.get_env(name[,default]): first envp entry whose key equals name exactly.
# Stack: name record (and default above it when RAX=1 on entry). Returns
# option[string], or the value/default string for the two-argument form.
.section .text.na_get_env,"ax"
 mov r10,rax
 xor r8d,r8d
 test r10,r10
 jz 1f
 pop r8
1:
 pop rsi
 mov rcx,[rsi]
 add rsi,8
 mov rax,[r14]
 lea r9,[r14+rax*8+16]
# The word that ends argv holds the library's state block once it is in
# use; its first word is the environment System.put_env has changed.
 mov rdi,[r9-8]
 test rdi,rdi
 jz 0f
 mov rdi,[rdi]
 test rdi,rdi
 cmovnz r9,rdi
0:
 test rcx,rcx
 jz 7f
2:
 mov rdi,[r9]
 test rdi,rdi
 jz 7f
 add r9,8
 xor edx,edx
3:
 cmp rdx,rcx
 jae 4f
 movzx eax,byte ptr [rdi+rdx]
 test eax,eax
 jz 2b
 cmp eax,61
 je 2b
 cmp al,[rsi+rdx]
 jne 2b
 inc rdx
 jmp 3b
4:
 cmp byte ptr [rdi+rdx],61
 jne 2b
 lea rsi,[rdi+rdx+1]
 mov rdx,rsi
5:
 cmp byte ptr [rdx],0
 je 6f
 inc rdx
 jmp 5b
6:
 mov r11,rdx
 sub r11,rsi
 mov r9,r11
 string_record
 lea rdi,[rax+8]
 mov rcx,r9
 cld
 rep movsb
 test r10,r10
 jnz 10f
 lea r11,[r12+16]
 gm_fit r11
 mov qword ptr [r12],1
 mov [r12+8],rax
 mov rax,r12
 mov r12,r11
 jmp 10f
7:
 mov rax,r8
 jmp 10f
9:
 mov edi,71
 mov eax,60
 syscall
10:
# String equality: RCX left, RAX right string records; RAX 1 when the bytes match.
.section .text.na_str_eq,"ax"
 mov rdx,[rcx]
 cmp rdx,[rax]
 jne 1f
 lea rsi,[rcx+8]
 lea rdi,[rax+8]
 mov rcx,rdx
 cld
 repe cmpsb
 jne 1f
 mov eax,1
 jmp 10f
1:
 xor eax,eax
10:
# String.count(s,pattern): non-overlapping matches, 0 for an empty pattern.
.section .text.na_count,"ax"
 pop rsi
 pop rdi
 mov r8,[rsi]
 lea r9,[rsi+8]
 lea r10,[rdi+8]
 mov r11,[rdi]
 add r11,r10
 xor eax,eax
 test r8,r8
 jz 10f
1:
 mov rdx,r11
 sub rdx,r10
 cmp rdx,r8
 jb 10f
 mov rsi,r10
 mov rdi,r9
 mov rcx,r8
 cld
 repe cmpsb
 jne 2f
 inc rax
 add r10,r8
 jmp 1b
2:
 inc r10
 jmp 1b
10:
# String.split(s,separator): Go strings.Split; an empty separator fails (86).
.section .text.na_split,"ax"
 pop rsi
 pop rdi
 mov r8,[rsi]
 test r8,r8
 jz 8f
 lea r9,[rsi+8]
 lea r10,[rdi+8]
 mov r11,[rdi]
 add r11,r10
# Stack slots: [rsp] list, [rsp+8] index, [rsp+16] piece start.
# A place is compared in full only where its first byte is the separator's
# (BL); RBP, kept on the stack meanwhile, is the last place one can start.
 sub rsp,24
 mov [rsp+16],r10
 xor eax,eax
 movzx ebx,byte ptr [r9]
 push rbp
 mov rbp,r11
 sub rbp,r8
1:
 cmp r10,rbp
 ja 3f
 cmp bl,[r10]
 je 2f
 inc r10
 jmp 1b
2:
 mov rsi,r10
 mov rdi,r9
 mov rcx,r8
 cld
 repe cmpsb
 je 21f
 inc r10
 jmp 1b
21:
 inc rax
 add r10,r8
 jmp 1b
3:
 pop rbp
 lea rcx,[rax+1]
 mov rdx,rcx
 shl rdx,4
 lea rdx,[r12+rdx+24]
 gm_fit rdx
 mov qword ptr [r12],-2
 lea rax,[r12+16]
 mov r12,rdx
 mov rdx,rax
7:
 mov [rdx],rcx
 add rdx,16
 sub rcx,1
 jns 7b
 mov [rsp],rax
 mov qword ptr [rsp+8],0
 mov r10,[rsp+16]
4:
 mov rdx,r11
 sub rdx,r8
 cmp r10,rdx
 ja 6f
 cmp bl,[r10]
 je 41f
 inc r10
 jmp 4b
41:
 mov rsi,r10
 mov rdi,r9
 mov rcx,r8
 cld
 repe cmpsb
 jne 5f
 mov rdx,r10
 call 20f
 add r10,r8
 mov [rsp+16],r10
 jmp 4b
5:
 inc r10
 jmp 4b
6:
 mov rdx,r11
 call 20f
 mov rax,[rsp]
 add rsp,24
 jmp 10f
8:
 mov edi,86
 mov eax,60
 syscall
9:
 mov edi,71
 mov eax,60
 syscall
# Piece [rsp+24] (caller's start)..RDX becomes list element [rsp+16].
20:
 mov rsi,[rsp+24]
 mov rcx,rdx
 sub rcx,rsi
 lea rdx,[rcx+15]
 and rdx,-8
 add rdx,r12
 gm_fit rdx
 mov rax,r12
 mov r12,rdx
 mov [rax],rcx
 lea rdi,[rax+8]
 cmp rcx,32
 jae 22f
 test rcx,rcx
 jz 23f
21:
 mov dl,[rsi]
 mov [rdi],dl
 inc rsi
 inc rdi
 dec rcx
 jnz 21b
 jmp 23f
22:
 cld
 rep movsb
23:
 mov rdx,[rsp+8]
 mov rcx,[rsp+16]
 shl rcx,4
 mov [rdx+rcx+8],rax
 inc qword ptr [rsp+16]
 ret
10:
# String.replace(s,old,new): Go strings.ReplaceAll. An empty old inserts new
# before every UTF-8 sequence (invalid bytes count singly) and at the end.
# Counted (flag 0) and then written (flag 1) into one exact allocation.
.section .text.na_replace,"ax"
 pop rax
 pop rsi
 pop rdi
# Stack slots: [rsp] new, [rsp+8] s, [rsp+16] old, [rsp+24] flag, [rsp+32] result.
 sub rsp,40
 mov [rsp],rax
 mov [rsp+8],rdi
 mov [rsp+16],rsi
 mov qword ptr [rsp+24],0
 xor r11d,r11d
1:
 mov rdi,[rsp+8]
 lea r10,[rdi+8]
 mov r9,[rdi]
 add r9,r10
 mov rsi,[rsp+16]
 mov r8,[rsi]
 test r8,r8
 jz 6f
# A place is compared in full only where its first byte is old's (BL); the
# bytes passed over since RAX are appended together. RDX is the last place
# old can start.
 movzx ebx,byte ptr [rsi+8]
 mov rdx,r9
 sub rdx,r8
2:
 mov rax,r10
22:
 cmp r10,rdx
 ja 4f
 cmp bl,[r10]
 je 23f
 inc r10
 jmp 22b
23:
 mov rsi,r10
 mov rdi,[rsp+16]
 add rdi,8
 mov rcx,r8
 cld
 repe cmpsb
 je 3f
 inc r10
 jmp 22b
3:
 mov rsi,rax
 mov rcx,r10
 sub rcx,rax
 call 20f
 mov rsi,[rsp]
 mov rcx,[rsi]
 add rsi,8
 call 20f
 add r10,r8
 jmp 2b
4:
 mov rsi,rax
 mov rcx,r9
 sub rcx,rax
 call 20f
 jmp 7f
6:
 mov rdx,r9
 mov rsi,[rsp]
 mov rcx,[rsi]
 add rsi,8
 call 20f
61:
 cmp r10,rdx
 jae 7f
 mov rsi,r10
 utf8_width 62f
 jmp 63f
62:
 mov ecx,1
63:
 mov rsi,r10
 add r10,rcx
 call 20f
 mov rsi,[rsp]
 mov rcx,[rsi]
 add rsi,8
 call 20f
 jmp 61b
7:
 cmp qword ptr [rsp+24],0
 jne 8f
 lea rdx,[r11+15]
 and rdx,-8
 add rdx,r12
 gm_fit rdx
 mov rax,r12
 mov r12,rdx
 mov [rax],r11
 mov [rsp+32],rax
 lea r11,[rax+8]
 mov qword ptr [rsp+24],1
 jmp 1b
8:
 mov rax,[rsp+32]
 add rsp,40
 jmp 10f
9:
 mov edi,71
 mov eax,60
 syscall
# Append RSI/RCX at R11 when writing; always advance R11.
20:
 cmp qword ptr [rsp+32],0
 je 21f
 mov rdi,r11
 cld
 cmp rcx,32
 jae 23f
 test rcx,rcx
 jz 24f
22:
 movsb
 dec rcx
 jnz 22b
 jmp 24f
23:
 rep movsb
24:
 mov r11,rdi
 ret
21:
 add r11,rcx
 ret
10:
# String.valid?(s): Go utf8.ValidString.
.section .text.na_valid,"ax"
 pop rsi
 mov rdx,[rsi]
 add rsi,8
 add rdx,rsi
1:
 cmp rsi,rdx
 jae 2f
 utf8_width 3f
 add rsi,rcx
 jmp 1b
2:
 mov eax,1
 jmp 10f
3:
 xor eax,eax
10:
# Whitespace trimming of RSI..RDX with unicode.IsSpace, as Go strings.TrimSpace,
# TrimLeftFunc and TrimRightFunc do. Each section pops the string and copies the rest.
.macro trim_leading
1:
 cmp rsi,rdx
 jae 5f
 movzx eax,byte ptr [rsi]
 mov ecx,1
 cmp eax,32
 je 2f
 lea r8d,[rax-9]
 cmp r8d,4
 jbe 2f
 mov r8,rdx
 sub r8,rsi
 mov ecx,2
 cmp eax,194
 jne 11f
 cmp r8,2
 jb 5f
 movzx r9d,byte ptr [rsi+1]
 cmp r9d,133
 je 2f
 cmp r9d,160
 je 2f
 jmp 5f
11:
 mov ecx,3
 cmp r8,3
 jb 5f
 movzx r9d,byte ptr [rsi+1]
 movzx r10d,byte ptr [rsi+2]
 call 30f
 test r11d,r11d
 jz 5f
2:
 add rsi,rcx
 jmp 1b
.endm
.macro trim_trailing
 cmp rdx,rsi
 jbe 8f
 movzx eax,byte ptr [rdx-1]
 cmp eax,32
 je 6f
 lea r8d,[rax-9]
 cmp r8d,4
 jbe 6f
 mov r8,rdx
 sub r8,rsi
 cmp r8,2
 jb 8f
 movzx r9d,byte ptr [rdx-2]
 cmp r9d,194
 jne 7f
 cmp eax,133
 je 61f
 cmp eax,160
 je 61f
 jmp 8f
61:
 sub rdx,2
 jmp 5b
6:
 dec rdx
 jmp 5b
7:
 cmp r8,3
 jb 8f
 mov r10d,eax
 movzx eax,byte ptr [rdx-3]
 call 30f
 test r11d,r11d
 jz 8f
 sub rdx,3
 jmp 5b
.endm
.macro trim_finish
8:
 mov rcx,rdx
 sub rcx,rsi
 lea rdx,[rcx+15]
 and rdx,-8
 add rdx,r12
 gm_fit rdx
 mov rax,r12
 mov r12,rdx
 mov [rax],rcx
 lea rdi,[rax+8]
 cld
 rep movsb
 jmp 10f
9:
 mov edi,71
 mov eax,60
 syscall
# Three-byte spaces: EAX, R9D, R10D bytes; R11D 1 for U+1680, U+2000-200A,
# U+2028/2029, U+202F, U+205F or U+3000.
30:
 xor r11d,r11d
 cmp eax,225
 jne 31f
 cmp r9d,154
 jne 39f
 cmp r10d,128
 je 38f
 ret
31:
 cmp eax,227
 jne 32f
 cmp r9d,128
 jne 39f
 cmp r10d,128
 je 38f
 ret
32:
 cmp eax,226
 jne 39f
 cmp r9d,129
 jne 33f
 cmp r10d,159
 je 38f
 ret
33:
 cmp r9d,128
 jne 39f
 cmp r10d,138
 jbe 34f
 cmp r10d,168
 je 38f
 cmp r10d,169
 je 38f
 cmp r10d,175
 je 38f
 ret
34:
 cmp r10d,128
 jb 39f
38:
 mov r11d,1
39:
 ret
10:
.endm
.macro trim_range
 pop rsi
 mov rdx,[rsi]
 add rsi,8
 add rdx,rsi
.endm
# String.trim(s): both ends.
.section .text.na_trim,"ax"
 trim_range
 trim_leading
5:
 trim_trailing
 trim_finish
# String.trim_leading(s).
.section .text.na_trim_leading,"ax"
 trim_range
 trim_leading
5:
 trim_finish
# String.trim_trailing(s).
.section .text.na_trim_trailing,"ax"
 trim_range
5:
 trim_trailing
 trim_finish
# String ordering: RCX left, RAX right; RAX -1, 0 or 1 by unsigned byte order,
# a proper prefix sorting first, like Go string comparison.
.section .text.na_str_cmp,"ax"
 mov rdx,[rcx]
 mov r8,[rax]
 lea rsi,[rcx+8]
 lea rdi,[rax+8]
 mov rcx,rdx
 cmp rcx,r8
 jbe 1f
 mov rcx,r8
1:
 test rcx,rcx
 jz 3f
 cld
 repe cmpsb
 jne 2f
3:
 cmp rdx,r8
2:
 mov eax,0
 ja 4f
 jb 5f
 jmp 10f
4:
 mov eax,1
 jmp 10f
5:
 mov rax,-1
10:
# String.pad_leading/pad_trailing(s,width[,with]): RAX holds the grapheme count
# of s and R8D the side (0 leading, 1 trailing); the stack holds with (0 for the
# default space), width and s. The fill is the first width-count runes of with
# repeated, each invalid byte counting as one rune written as U+FFFD, as Go's
# []rune conversion does. Counted (flag 0), then written (flag 1).
.section .text.na_pad,"ax"
 pop r9
 pop rcx
 pop rdi
# What is missing is width less the count in 64 bits that wrap around, and
# the fill is made of missing/runes+1 copies of with, as in the pinned
# runtime: a count that wraps is its panic "negative Repeat count" (status
# 98), a length past 64 bits "Repeat output length overflow" (96) and one
# past 2^48 bytes "makeslice: len out of range" (99; native-failures.alc).
 sub rcx,rax
 test rcx,rcx
 jle 7f
 mov r10d,1
 mov esi,1
 test r9,r9
 jz 42f
 mov r10,[r9]
 test r10,r10
 jz 45f
 xor esi,esi
 xor edx,edx
41:
 cmp rdx,r10
 jae 42f
 movzx r11d,byte ptr [r9+rdx+8]
 and r11d,0xC0
 cmp r11d,0x80
 je 43f
 inc rsi
43:
 inc rdx
 jmp 41b
42:
 test rsi,rsi
 jnz 44f
 mov esi,1
44:
 mov r11,rax
 mov rax,rcx
 xor edx,edx
 div rsi
 inc rax
 js 46f
 mov rsi,rax
 movabs rax,0x7FFFFFFFFFFFFFFF
 xor edx,edx
 div rsi
 cmp r10,rax
 ja 47f
 mov rax,rsi
 imul rax,r10
 movabs rdx,0x1000000000000
 cmp rax,rdx
 ja 48f
 mov rax,r11
45:
# Every fill rune is at least one byte, so a fill beyond the arena cannot
# fit: beyond what is left of it, or in a program that collects (R13 is 0
# there, alchem-memory.md) beyond all of it.
 mov rdx,r13
 sub rdx,r12
 test r13,r13
 jnz 49f
 mov rdx,[r14-1536+24]
 sub rdx,[r14-1536+16]
49:
 cmp rcx,rdx
 ja 9f
 lea rsi,[rip+30f]
 lea rdx,[rsi+1]
 test r9,r9
 jz 1f
 lea rsi,[r9+8]
 mov rdx,[r9]
 add rdx,rsi
 cmp rsi,rdx
 je 7f
1:
# Stack slots: [rsp] s, [rsp+8] with start, [rsp+16] with end, [rsp+24] missing,
# [rsp+32] flag, [rsp+40] result, [rsp+48] side.
 sub rsp,56
 mov [rsp],rdi
 mov [rsp+8],rsi
 mov [rsp+16],rdx
 mov [rsp+24],rcx
 mov qword ptr [rsp+32],0
 mov [rsp+48],r8
 xor r11d,r11d
2:
 cmp qword ptr [rsp+48],0
 jne 3f
 call 20f
 call 25f
 jmp 4f
3:
 call 25f
 call 20f
4:
 cmp qword ptr [rsp+32],0
 jne 5f
 lea rdx,[r11+15]
 and rdx,-8
 add rdx,r12
 gm_fit rdx
 mov rax,r12
 mov r12,rdx
 mov [rax],r11
 mov [rsp+40],rax
 lea r11,[rax+8]
 mov qword ptr [rsp+32],1
 jmp 2b
5:
 mov rax,[rsp+40]
 add rsp,56
 jmp 10f
7:
 mov rax,rdi
 jmp 10f
9:
 mov edi,71
 mov eax,60
 syscall
# Fill: [rsp+32] missing runes cycling through with.
20:
 mov r10,[rsp+32]
 mov rsi,[rsp+16]
 mov rdx,[rsp+24]
21:
 test r10,r10
 jz 24f
 cmp rsi,rdx
 jb 22f
 mov rsi,[rsp+16]
22:
 utf8_width 23f
 cmp qword ptr [rsp+40],0
 je 26f
 mov rdi,r11
 mov r8,rcx
 cld
 rep movsb
 mov rcx,r8
 sub rsi,rcx
26:
 add r11,rcx
 add rsi,rcx
 dec r10
 jmp 21b
23:
 cmp qword ptr [rsp+40],0
 je 27f
 mov byte ptr [r11],239
 mov byte ptr [r11+1],191
 mov byte ptr [r11+2],189
27:
 add r11,3
 inc rsi
 dec r10
 jmp 21b
24:
 ret
# The string itself.
25:
 mov rsi,[rsp+8]
 mov rcx,[rsi]
 add rsi,8
 cmp qword ptr [rsp+40],0
 je 28f
 mov rdi,r11
 cld
 rep movsb
 mov r11,rdi
 ret
28:
 add r11,rcx
 ret
30:
 .byte 32
10:
# System.cwd!(): the working directory as the kernel names it. The pinned
# runtime raises when it cannot be read; here that exits 71.
 jmp 49f
46:
 mov edi,98
 mov eax,60
 syscall
47:
 mov edi,96
 mov eax,60
 syscall
48:
 mov edi,99
 mov eax,60
 syscall
49:
.section .text.na_cwd,"ax"
 sub rsp,4096
 mov rdi,rsp
 mov esi,4096
 mov eax,79
 syscall
 test rax,rax
 jle 9f
 lea r11,[rax-1]
 mov r9,r11
 string_record
 lea rdi,[rax+8]
 mov rsi,rsp
 mov rcx,r9
 cld
 rep movsb
 add rsp,4096
 jmp 8f
9:
 mov edi,71
 mov eax,60
 syscall
8:
.att_syntax
