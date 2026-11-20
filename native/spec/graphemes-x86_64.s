# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# Subroutine emitted once per program as an extra function-table entry.
# EAX op 1=count,2=slice,3=first,4=last,5=reverse,6=first cluster byte length;
# RDI record, RSI start, RDX count.
.intel_syntax noprefix
.text
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
# gm_reserve: room from R12 up to \end for a value whose size is not known
# yet; R13 is its end until gm_release.
.macro gm_reserve end
 lea r11,[\end]
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
 push rbp
 mov rbp,rsp
 push rbx
 push r14
 sub rsp,112
 mov [rbp-24],rdi
 mov [rbp-48],rax
 mov [rbp-56],rsi
 mov [rbp-64],rdx
 mov rcx,[rdi]
 mov [rbp-40],rcx
 add rdi,8
 mov [rbp-32],rdi
 mov [rbp-88],rcx
 mov [rbp-96],rcx
 mov qword ptr [rbp-72],0
 mov qword ptr [rbp-80],0
 cmp eax,2
 jne gr_start
 test rsi,rsi
 js gr_bounds
 test rdx,rdx
 js gr_bounds
gr_start:
 cmp eax,5
 je gr_reverse
 cmp eax,6
 je gr_first_length
 cmp eax,1
 jne gr_loop
 xor edx,edx
gr_ascii:
 cmp rdx,rcx
 jae gr_ascii_done
 movzx r8d,byte ptr [rdi+rdx]
 cmp r8d,128
 jae gr_loop
 cmp r8d,13
 je gr_loop
 inc rdx
 jmp gr_ascii
gr_ascii_done:
 mov rax,rcx
 jmp gr_finish
gr_loop:
 cmp qword ptr [rbp-48],2
 jne gr_advance
 mov rax,[rbp-72]
 cmp rax,[rbp-56]
 jne gr_slice_stop
 mov rcx,[rbp-80]
 mov [rbp-88],rcx
gr_slice_stop:
 cmp rax,[rbp-56]
 jb gr_advance
 sub rax,[rbp-56]
 cmp rax,[rbp-64]
 jne gr_advance
 mov rax,[rbp-80]
 mov [rbp-96],rax
 jmp gr_result
gr_advance:
 mov rax,[rbp-80]
 cmp rax,[rbp-40]
 jae gr_result
 cmp qword ptr [rbp-48],4
 jne gr_call_next
 mov [rbp-88],rax
gr_call_next:
 mov rsi,[rbp-32]
 add rsi,rax
 mov rdx,[rbp-40]
 sub rdx,rax
# An ASCII byte other than a carriage return, before another ASCII byte or
# at the end, is a cluster by itself.
 movzx ecx,byte ptr [rsi]
 cmp cl,13
 je 2f
 test cl,cl
 js 2f
 mov eax,1
 cmp rdx,1
 je 3f
 cmp byte ptr [rsi+1],0
 jns 3f
2:
 call gr_next
3:
 add [rbp-80],rax
 inc qword ptr [rbp-72]
 cmp qword ptr [rbp-48],3
 jne gr_loop
 mov qword ptr [rbp-88],0
 mov rax,[rbp-80]
 mov [rbp-96],rax
gr_result:
 mov rax,[rbp-72]
 cmp qword ptr [rbp-48],1
 je gr_finish
 cmp qword ptr [rbp-48],2
 je gr_copy
 cmp qword ptr [rbp-40],0
 jne gr_copy
 xor eax,eax
 jmp gr_finish
gr_copy:
 mov rsi,[rbp-32]
 add rsi,[rbp-88]
 mov rcx,[rbp-96]
 sub rcx,[rbp-88]
 lea r11,[rcx+15]
 and r11,-8
 add r11,r12
 gm_fit r11
 mov rax,r12
 mov r12,r11
 mov [rax],rcx
 lea rdi,[rax+8]
 cld
 rep movsb
 cmp qword ptr [rbp-48],2
 je gr_finish
 lea r11,[r12+16]
 gm_fit r11
 mov qword ptr [r12],1
 mov [r12+8],rax
 mov rax,r12
 mov r12,r11
gr_finish:
 lea rsp,[rbp-16]
 pop r14
 pop rbx
 pop rbp
 ret
# Reverse: each cluster is copied to its mirrored position in a fresh record.
gr_reverse:
 mov rcx,[rbp-40]
 lea r11,[rcx+15]
 and r11,-8
 add r11,r12
 gm_fit r11
 mov rax,r12
 mov r12,r11
 mov [rax],rcx
 mov [rbp-88],rax
gr_reverse_loop:
 mov rax,[rbp-80]
 cmp rax,[rbp-40]
 jae gr_reverse_done
 mov rsi,[rbp-32]
 add rsi,rax
 mov rdx,[rbp-40]
 sub rdx,rax
 movzx ecx,byte ptr [rsi]
 cmp cl,13
 je 2f
 test cl,cl
 js 2f
 cmp rdx,1
 je 1f
 cmp byte ptr [rsi+1],0
 js 2f
1:
 inc rax
 mov [rbp-80],rax
 mov rdi,[rbp-88]
 add rdi,[rbp-40]
 sub rdi,rax
 mov [rdi+8],cl
 jmp gr_reverse_loop
2:
 call gr_next
 mov rcx,rax
 mov rsi,[rbp-32]
 add rsi,[rbp-80]
 add [rbp-80],rax
 mov rdi,[rbp-88]
 add rdi,8
 add rdi,[rbp-40]
 sub rdi,[rbp-80]
 cld
 rep movsb
 jmp gr_reverse_loop
gr_reverse_done:
 mov rax,[rbp-88]
 jmp gr_finish
gr_first_length:
 xor eax,eax
 cmp qword ptr [rbp-40],0
 je gr_finish
 mov rsi,[rbp-32]
 mov rdx,[rbp-40]
 call gr_next
 jmp gr_finish
gr_bounds:
 mov edi,73
 jmp gr_exit
gr_arena:
 mov edi,71
gr_exit:
 mov eax,60
 syscall
# First cluster byte length. Input RSI, RDX; no heap allocation.
gr_next:
 sub rsp,64
 mov [rsp],rsi
 mov [rsp+8],rdx
 call gr_decode
 mov [rsp+16],rcx
 call gr_class
 mov [rsp+24],eax
 xor edx,edx
 cmp eax,6
 sete dl
 mov [rsp+32],edx
 xor edx,edx
 cmp eax,14
 sete dl
 mov [rsp+40],edx
 mov dword ptr [rsp+48],0
gr_next_loop:
 mov rax,[rsp+16]
 cmp rax,[rsp+8]
 jae gr_next_done
 mov rsi,[rsp]
 add rsi,rax
 mov rdx,[rsp+8]
 sub rdx,rax
 call gr_decode
 mov [rsp+56],ecx
 call gr_class
 mov ebx,eax
 mov ecx,[rsp+24]
 cmp ecx,1
 jne gr_controls
 cmp ebx,2
 je gr_join
gr_controls:
 cmp ecx,1
 jb gr_next_controls
 cmp ecx,3
 jbe gr_next_done
gr_next_controls:
 cmp ebx,1
 jb gr_hangul
 cmp ebx,3
 jbe gr_next_done
gr_hangul:
 cmp ecx,9
 jne gr_hangul_v
 cmp ebx,9
 je gr_join
 cmp ebx,10
 je gr_join
 cmp ebx,12
 je gr_join
 cmp ebx,13
 je gr_join
gr_hangul_v:
 cmp ecx,12
 je gr_v_next
 cmp ecx,10
 jne gr_hangul_t
gr_v_next:
 cmp ebx,10
 je gr_join
 cmp ebx,11
 je gr_join
gr_hangul_t:
 cmp ecx,13
 je gr_t_next
 cmp ecx,11
 jne gr_extends
gr_t_next:
 cmp ebx,11
 je gr_join
gr_extends:
 cmp ebx,4
 je gr_join
 cmp ebx,5
 je gr_join
 cmp ebx,8
 je gr_join
 cmp ecx,7
 je gr_join
 cmp dword ptr [rsp+48],0
 je gr_regionals
 cmp ebx,14
 je gr_join
gr_regionals:
 cmp ecx,6
 jne gr_next_done
 cmp ebx,6
 jne gr_next_done
 test dword ptr [rsp+32],1
 jz gr_next_done
gr_join:
 cmp ebx,6
 jne gr_emoji
 inc dword ptr [rsp+32]
 jmp gr_joined
gr_emoji:
 cmp ebx,14
 jne gr_zwj
 mov dword ptr [rsp+40],1
 mov dword ptr [rsp+48],0
 jmp gr_joined
gr_zwj:
 cmp ebx,5
 jne gr_reset
 mov eax,[rsp+40]
 mov [rsp+48],eax
 jmp gr_joined
gr_reset:
 cmp ebx,4
 je gr_joined
 mov dword ptr [rsp+40],0
 mov dword ptr [rsp+48],0
gr_joined:
 mov [rsp+24],ebx
 mov eax,[rsp+56]
 add [rsp+16],rax
 jmp gr_next_loop
gr_next_done:
 mov rax,[rsp+16]
 add rsp,64
 ret
# Exact Go UTF-8 decoding: invalid/truncated sequences consume one byte.
gr_decode:
 movzx r8d,byte ptr [rsi]
 mov eax,r8d
 mov ecx,1
 cmp r8d,128
 jb gr_dec_ret
 cmp r8d,194
 jb gr_invalid
 cmp r8d,244
 ja gr_invalid
 mov ecx,2
 cmp r8d,224
 jb gr_dec_width
 inc ecx
 cmp r8d,240
 jb gr_dec_width
 inc ecx
gr_dec_width:
 cmp rdx,rcx
 jb gr_invalid
 movzx r9d,byte ptr [rsi+1]
 cmp r9d,128
 jb gr_invalid
 cmp r9d,191
 ja gr_invalid
 cmp r8d,224
 jne gr_dec_ed
 cmp r9d,160
 jb gr_invalid
gr_dec_ed:
 cmp r8d,237
 jne gr_dec_f0
 cmp r9d,160
 jae gr_invalid
gr_dec_f0:
 cmp r8d,240
 jne gr_dec_f4
 cmp r9d,144
 jb gr_invalid
gr_dec_f4:
 cmp r8d,244
 jne gr_dec_rest
 cmp r9d,144
 jae gr_invalid
gr_dec_rest:
 and r9d,63
 cmp ecx,2
 jne gr_dec_three
 and eax,31
 shl eax,6
 or eax,r9d
 ret
gr_dec_three:
 movzx r10d,byte ptr [rsi+2]
 cmp r10d,128
 jb gr_invalid
 cmp r10d,191
 ja gr_invalid
 and r10d,63
 cmp ecx,3
 jne gr_dec_four
 and eax,15
 shl eax,12
 shl r9d,6
 or eax,r9d
 or eax,r10d
 ret
gr_dec_four:
 movzx r11d,byte ptr [rsi+3]
 cmp r11d,128
 jb gr_invalid
 cmp r11d,191
 ja gr_invalid
 and r11d,63
 and eax,7
 shl eax,18
 shl r9d,12
 shl r10d,6
 or eax,r9d
 or eax,r10d
 or eax,r11d
gr_dec_ret:
 ret
gr_invalid:
 mov eax,65533
 mov ecx,1
 ret
# Packed range lookup: start21 | class4 | lengthMinusOne11 in five bytes.
gr_class:
 cmp eax,127
 jae gr_class_hangul
 cmp eax,13
 je gr_class_cr
 cmp eax,10
 je gr_class_lf
 cmp eax,32
 jb gr_class_control
 xor eax,eax
 ret
gr_class_cr:
 mov eax,1
 ret
gr_class_lf:
 mov eax,2
 ret
gr_class_control:
 mov eax,3
 ret
gr_class_hangul:
 cmp eax,44032
 jb gr_lookup
 cmp eax,55203
 ja gr_lookup
 sub eax,44032
 xor edx,edx
 mov ecx,28
 div ecx
 mov eax,12
 test edx,edx
 jz gr_class_ret
 inc eax
gr_class_ret:
 ret
gr_lookup:
 mov esi,eax
 lea rdi,[rip+gr_table]
 xor r8d,r8d
 mov r9d,613
gr_search:
 cmp r8d,r9d
 jae gr_other
 lea r10d,[r8+r9]
 shr r10d,1
 lea r11,[r10+r10*4]
 mov rax,[rdi+r11]
 mov ecx,eax
 and ecx,2097151
 cmp esi,ecx
 jb gr_smaller
 shr rax,21
 mov edx,eax
 and edx,15
 shr rax,4
 and eax,2047
 add eax,ecx
 cmp esi,eax
 ja gr_bigger
 mov eax,edx
 ret
gr_smaller:
 mov r9d,r10d
 jmp gr_search
gr_bigger:
 lea r8d,[r10+1]
 jmp gr_search
gr_other:
 xor eax,eax
 ret
gr_table:
# GRAPHEME_DATA
