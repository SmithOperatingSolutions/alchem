# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# String.upcase/downcase/capitalize subroutine, emitted once per program as an
# extra function-table entry. RDI string record, ESI 0 for upper, 1 for lower or
# 2 for capitalize with RDX the byte length of the first grapheme; RAX returns a
# fresh string. Go strings.ToUpper/ToLower/ToTitle: every rune goes through the
# simple unicode mapping and each invalid byte becomes U+FFFD. Capitalize is
# ToTitle of the first grapheme followed by ToLower of the rest.
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
# UTF8_WIDTH
# Frame: [rsp] string, [rsp+8] table, [rsp+16] range count, [rsp+24] write flag,
# [rsp+32] result, [rsp+40] ASCII mode (0 upper, 1 lower), [rsp+48] requested
# mode, [rsp+56] capitalize split pointer. Counted (flag 0), then written (flag 1).
 sub rsp,64
 mov [rsp],rdi
 mov [rsp+48],rsi
 lea rax,[rdi+rdx+8]
 mov [rsp+56],rax
 mov qword ptr [rsp+24],0
 xor r11d,r11d
cm_pass:
 lea rax,[rip+cm_upper]
 mov ecx,UPPER_COUNT
 xor r8d,r8d
 cmp qword ptr [rsp+48],1
 jb cm_table
 je cm_lower_table
 lea rax,[rip+cm_title]
 mov ecx,TITLE_COUNT
 jmp cm_table
cm_lower_table:
 lea rax,[rip+cm_lower]
 mov ecx,LOWER_COUNT
 mov r8d,1
cm_table:
 mov [rsp+8],rax
 mov [rsp+16],rcx
 mov [rsp+40],r8
 mov rsi,[rsp]
 mov rdx,[rsi]
 add rsi,8
 add rdx,rsi
cm_loop:
 cmp rsi,rdx
 jae cm_pass_done
 cmp qword ptr [rsp+48],2
 jne cm_rune
 cmp rsi,[rsp+56]
 jb cm_rune
# Past the first grapheme: the rest is lower-cased.
 lea rax,[rip+cm_lower]
 mov [rsp+8],rax
 mov qword ptr [rsp+16],LOWER_COUNT
 mov qword ptr [rsp+40],1
cm_rune:
 movzx eax,byte ptr [rsi]
 cmp eax,128
 jae cm_multi
 inc rsi
 cmp qword ptr [rsp+40],0
 jne cm_ascii_lower
 lea r8d,[rax-97]
 cmp r8d,25
 ja cm_encode
 sub eax,32
 jmp cm_encode
cm_ascii_lower:
 lea r8d,[rax-65]
 cmp r8d,25
 ja cm_encode
 add eax,32
 jmp cm_encode
cm_multi:
 utf8_width cm_invalid
 movzx eax,byte ptr [rsi]
 movzx r8d,byte ptr [rsi+1]
 and r8d,63
 cmp ecx,2
 jne cm_three
 and eax,31
 shl eax,6
 or eax,r8d
 jmp cm_decoded
cm_three:
 movzx r9d,byte ptr [rsi+2]
 and r9d,63
 cmp ecx,3
 jne cm_four
 and eax,15
 shl eax,12
 shl r8d,6
 or eax,r8d
 or eax,r9d
 jmp cm_decoded
cm_four:
 movzx r10d,byte ptr [rsi+3]
 and r10d,63
 and eax,7
 shl eax,18
 shl r8d,12
 shl r9d,6
 or eax,r8d
 or eax,r9d
 or eax,r10d
cm_decoded:
 add rsi,rcx
 call cm_map
 jmp cm_encode
cm_invalid:
 inc rsi
 mov eax,65533
# Append rune EAX as UTF-8 at R11 when writing; always advance R11.
cm_encode:
 mov rcx,[rsp+24]
 cmp eax,128
 jae cm_encode_two
 test rcx,rcx
 jz cm_one_counted
 mov [r11],al
cm_one_counted:
 inc r11
 jmp cm_loop
cm_encode_two:
 cmp eax,2048
 jae cm_encode_three
 test rcx,rcx
 jz cm_two_counted
 mov r8d,eax
 shr r8d,6
 or r8d,192
 mov [r11],r8b
 mov r8d,eax
 and r8d,63
 or r8d,128
 mov [r11+1],r8b
cm_two_counted:
 add r11,2
 jmp cm_loop
cm_encode_three:
 cmp eax,65536
 jae cm_encode_four
 test rcx,rcx
 jz cm_three_counted
 mov r8d,eax
 shr r8d,12
 or r8d,224
 mov [r11],r8b
 mov r8d,eax
 shr r8d,6
 and r8d,63
 or r8d,128
 mov [r11+1],r8b
 mov r8d,eax
 and r8d,63
 or r8d,128
 mov [r11+2],r8b
cm_three_counted:
 add r11,3
 jmp cm_loop
cm_encode_four:
 test rcx,rcx
 jz cm_four_counted
 mov r8d,eax
 shr r8d,18
 or r8d,240
 mov [r11],r8b
 mov r8d,eax
 shr r8d,12
 and r8d,63
 or r8d,128
 mov [r11+1],r8b
 mov r8d,eax
 shr r8d,6
 and r8d,63
 or r8d,128
 mov [r11+2],r8b
 mov r8d,eax
 and r8d,63
 or r8d,128
 mov [r11+3],r8b
cm_four_counted:
 add r11,4
 jmp cm_loop
cm_pass_done:
 cmp qword ptr [rsp+24],0
 jne cm_written
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
 jmp cm_pass
cm_written:
 mov rax,[rsp+32]
 add rsp,64
 ret
cm_arena:
 mov edi,71
 mov eax,60
 syscall
# EAX rune >= 128 -> mapped rune. Six-byte entries sorted by start:
# start21 | span8 << 21 | (stride-1) << 29 | (delta+65536) << 30.
cm_map:
 push rdx
 mov r9,[rsp+24]
 mov r10,[rsp+32]
cm_map_loop:
 test r10,r10
 jz cm_map_done
 mov r8,[r9]
 mov ecx,r8d
 and ecx,2097151
 cmp eax,ecx
 jb cm_map_done
 mov rdx,r8
 shr rdx,21
 and edx,255
 add edx,ecx
 cmp eax,edx
 ja cm_map_next
 mov rdx,r8
 shr rdx,29
 and edx,1
 mov edi,eax
 sub edi,ecx
 test edi,edx
 jnz cm_map_next
 shr r8,30
 and r8d,131071
 sub r8d,65536
 add eax,r8d
 jmp cm_map_done
cm_map_next:
 add r9,6
 dec r10
 jmp cm_map_loop
cm_map_done:
 pop rdx
 ret
cm_upper:
# UPPER_DATA
cm_lower:
# LOWER_DATA
cm_title:
# TITLE_DATA
