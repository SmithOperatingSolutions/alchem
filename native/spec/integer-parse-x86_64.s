# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# Integer.parse(string[,base]) subroutine, emitted once per program as an extra
# function-table entry. RSI base, RDI string record, RDX 1 when the base was
# given (the error then names it) or 2 for String.to_integer (failure exits73);
# RAX returns ok(i64) or error(string).
# Semantics follow Go strconv.ParseInt; the error quotes like strconv.Quote.
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
.macro put byte
 test rdi,rdi
 jz 1f
 mov byte ptr [r11],\byte
1:
 inc r11
.endm
 cmp rdx,4
 je ins_entry
 sub rsp,32
 mov [rsp],rsi
 mov [rsp+8],rdi
 mov [rsp+24],rdx
 cmp rsi,2
 jl ip_base_error
 cmp rsi,36
 jg ip_base_error
 mov r8,rsi
 mov rcx,[rdi]
 lea r9,[rdi+8]
 xor r10d,r10d
 xor r11d,r11d
 test rcx,rcx
 jz ip_fail
 movzx eax,byte ptr [r9]
 cmp eax,43
 je ip_sign
 cmp eax,45
 jne ip_digits
 mov r11d,1
ip_sign:
 inc r10
 cmp r10,rcx
 je ip_fail
ip_digits:
 xor eax,eax
ip_digit:
 cmp r10,rcx
 jae ip_range
 movzx esi,byte ptr [r9+r10]
 lea edx,[rsi-48]
 cmp edx,9
 jbe ip_value
 or esi,32
 lea edx,[rsi-97]
 cmp edx,25
 ja ip_fail
 add edx,10
ip_value:
 cmp rdx,r8
 jae ip_fail
 mov rsi,rdx
 mul r8
 jc ip_fail
 add rax,rsi
 jc ip_fail
 inc r10
 jmp ip_digit
ip_range:
 test r11,r11
 jz ip_positive
 neg rax
 test rax,rax
 jg ip_fail
 jmp ip_ok
ip_positive:
 test rax,rax
 js ip_fail
ip_ok:
 lea r11,[r12+16]
 gm_fit r11
 mov rsi,rax
 mov rax,r12
 mov r12,r11
 mov qword ptr [rax],1
 mov [rax+8],rsi
 add rsp,32
 ret
# Error text is counted (RDI=0) and then written (RDI=1) into one exact allocation.
ip_fail:
 cmp qword ptr [rsp+24],2
 je ip_base_error
 xor edi,edi
 xor r11d,r11d
ip_pass:
 mov rsi,[rsp+8]
 mov rcx,[rsi]
 add rsi,8
 call ip_quote
 lea rsi,[rip+ip_suffix]
 mov ecx,18
 call ip_copy
 cmp qword ptr [rsp+24],0
 je ip_suffix_done
 lea rsi,[rip+ip_base_text]
 mov ecx,9
 call ip_copy
 mov rax,[rsp]
 cmp eax,10
 jb ip_base_one
 xor edx,edx
 mov ecx,10
 div ecx
 add eax,48
 put al
 mov eax,edx
ip_base_one:
 add eax,48
 put al
ip_suffix_done:
 test rdi,rdi
 jnz ip_written
 lea rdx,[r11+15]
 and rdx,-8
 add rdx,r12
 gm_fit rdx
 mov rax,r12
 mov r12,rdx
 mov [rax],r11
 mov [rsp+16],rax
 lea r11,[rax+8]
 mov edi,1
 jmp ip_pass
ip_written:
 lea r11,[r12+16]
 gm_fit r11
 mov rax,r12
 mov r12,r11
 mov qword ptr [rax],0
 mov rsi,[rsp+16]
 mov [rax+8],rsi
 add rsp,32
 ret
ip_base_error:
 mov edi,73
 mov eax,60
 syscall
ip_arena_error:
 mov edi,71
 mov eax,60
 syscall
# inspect (RDX 4): the value in RDI as text in source form, by the description
# of its type at RSI. A description is a node: its length (16 bits), a tag
# and what the tag needs:
#   0 integer, 2 string, 3 boolean, 10 function, 22 atom, 23 range: nothing;
#   24 float: the address of the float runtime's table entry (32 bits);
#   4 option, 7 list, 25 set: the node of the element;
#   6 result: the nodes of the ok and the error value; 8 map: of key and value;
#   5 tuple: the count, then a node per position;
#   (a count, and the length of a name, is one byte, or the byte 255 and 32
#   bits: ins_count)
#   13 struct: the length of its name and the name, the field count, then per
#      field the length of its name, the name and its node;
#   14 sum type: the length of its name and the name, the variant count, then
#      per variant its length (16 bits), the length of its name, the name, the
#      field count and a node per field;
#   20 a node met before, by its offset from the first node (a type that
#      refers to itself).
#   34 an option, as 4 (JSON.decode_as tells the two apart);
#   35 five bytes of zero and the address (64 bits) of the first node of
#      another description, which a 20 inside it counts from: the type a
#      type variable stands for;
#   36 one node, for inspect alone (the JSON library has no form for it).
#   29 a regular expression: nothing;
#   30 Date, 31 Time, 32 NaiveDateTime, 33 DateTime of the library: nothing.
# The text is written at the arena's cursor, R12, behind a length filled in
# at the end; RBX holds the first node.
# The text grows in room reserved for it (alchem-memory.md): the word at
# R14-1536+224 is where it starts, since the room may move when it is made
# larger (ins_more). 8 bytes always stay free behind the text.
ins_entry:
 push rbx
 gm_reserve r12+4096
 lea rax,[r12+16]
 cmp rax,r13
 ja ip_arena_error
 mov [r14-1536+224],r12
 add r12,8
 mov rbx,rsi
 call ins
 mov rax,[r14-1536+224]
 mov rdx,r12
 sub rdx,rax
 sub rdx,8
 mov [rax],rdx
 add r12,7
 and r12,-8
 gm_release
 pop rbx
 ret
# RAX is where the text has to reach, with its 8 bytes: more room. Keeps
# every register but RAX and R11.
ins_more:
 mov r11,rax
 push r12
 mov r12,[r14-1536+224]
 call qword ptr [0x400458]
 mov [r14-1536+224],r12
 pop r12
 add r12,r11
 ret
ins:
 cmp rsp,[r14-8]
 jb ins_deep
 movzx eax,byte ptr [rsi+2]
 cmp eax,20
 jne 1f
 movzx eax,word ptr [rsi+3]
 lea rsi,[rbx+rax]
 jmp ins
1:
 cmp eax,35
 jne 1f
 push rbx
 mov rsi,[rsi+8]
 mov rbx,rsi
 call ins
 pop rbx
 ret
1:
 cmp eax,36
 jne 1f
 add rsi,3
 jmp ins
1:
 cmp eax,34
 jne 1f
 mov eax,4
1:
 lea rdx,[rsi+3]
 cmp eax,30
 jb ins_plain
 cmp eax,33
 jbe ins_calendar
ins_plain:
 test eax,eax
 jz ins_int
 cmp eax,2
 je ins_string
 cmp eax,3
 je ins_bool
 cmp eax,4
 je ins_option
 cmp eax,5
 je ins_tuple
 cmp eax,6
 je ins_result
 cmp eax,7
 je ins_list
 cmp eax,8
 je ins_map
 cmp eax,13
 je ins_struct
 cmp eax,14
 je ins_sum
 cmp eax,22
 je ins_atom
 cmp eax,23
 je ins_range
 cmp eax,24
 je ins_float
 cmp eax,25
 je ins_set
 lea rsi,[rip+ins_function]
 mov ecx,11
 cmp eax,29
 jne ins_text
 lea rsi,[rip+ins_regexp]
 mov ecx,9
# Append ECX bytes from RSI, which is left after them.
ins_text:
 test ecx,ecx
 jz 2f
 mov eax,ecx
 lea rax,[rax+r12+8]
 cmp rax,r13
 jbe 1f
 call ins_more
1:
 mov al,[rsi]
 mov [r12],al
 inc rsi
 inc r12
 dec ecx
 jnz 1b
2:
 ret
ins_char:
 push rax
 lea rax,[r12+9]
 cmp rax,r13
 jbe 1f
 call ins_more
1:
 pop rax
 mov [r12],al
 inc r12
 ret
ins_deep:
 mov edi,70
 mov eax,60
 syscall
ins_int:
 mov rax,rdi
 sub rsp,32
 lea rsi,[rsp+32]
 mov ecx,10
 test rax,rax
 jns 1f
 neg rax
1:
 xor edx,edx
 div rcx
 add dl,48
 dec rsi
 mov [rsi],dl
 test rax,rax
 jnz 1b
 test rdi,rdi
 jns 2f
 dec rsi
 mov byte ptr [rsi],45
2:
 lea rcx,[rsp+32]
 sub rcx,rsi
 call ins_text
 add rsp,32
 ret
ins_string:
 push rdi
 mov rsi,rdi
 mov rcx,[rsi]
 add rsi,8
 xor edi,edi
 xor r11d,r11d
 call ip_quote
 lea rax,[r12+r11+8]
 cmp rax,r13
 jbe 1f
 call ins_more
1:
 pop rsi
 mov rcx,[rsi]
 add rsi,8
 mov edi,1
 mov r11,r12
 call ip_quote
 mov r12,r11
 ret
ins_bool:
 lea rsi,[rip+ins_true]
 mov ecx,4
 test rdi,rdi
 jnz ins_text
 lea rsi,[rip+ins_false]
 mov ecx,5
 jmp ins_text
ins_option:
# 0x400000 is the nil of an option and discriminant -1 that of a result
# (zf_zero).
 cmp rdi,0x400000
 je ins_absent
 test rdi,rdi
 jnz 1f
 lea rsi,[rip+ins_none]
 mov ecx,4
 jmp ins_text
1:
 push rdi
 push rdx
 lea rsi,[rip+ins_some]
 mov ecx,5
 call ins_text
 pop rsi
 pop rdi
 mov rdi,[rdi+8]
 call ins
ins_close:
 mov al,41
 jmp ins_char
ins_result:
 cmp qword ptr [rdi],-1
 je ins_absent
 push rdi
 push rdx
 cmp qword ptr [rdi],0
 je 1f
 lea rsi,[rip+ins_ok]
 mov ecx,3
 call ins_text
 pop rsi
 pop rdi
 jmp 2f
1:
 lea rsi,[rip+ins_error]
 mov ecx,6
 call ins_text
 pop rsi
 pop rdi
 movzx eax,word ptr [rsi]
 add rsi,rax
2:
 mov rdi,[rdi+8]
 call ins
 jmp ins_close
# RCX values from RDI on, separated by ", ": each by the node at RSI, or
# when R8 is set by the next node in turn. ins_pairs reads the elements of
# a list, which lie 16 bytes apart (alchem-lists.md).
ins_pairs:
 mov r9d,16
 jmp ins_step
ins_seq:
 mov r9d,8
ins_step:
 test rcx,rcx
 jz 9f
 push r9
 push rdi
 push rcx
 push rsi
 push r8
1:
 mov rdi,[rsp+24]
 mov rdi,[rdi]
 mov rsi,[rsp+8]
 call ins
 mov rax,[rsp+32]
 add [rsp+24],rax
 dec qword ptr [rsp+16]
 jz 8f
 cmp qword ptr [rsp],0
 je 2f
 mov rsi,[rsp+8]
 movzx eax,word ptr [rsi]
 add [rsp+8],rax
2:
 lea rsi,[rip+ins_comma]
 mov ecx,2
 call ins_text
 jmp 1b
8:
 add rsp,40
9:
 ret
# A range: its list, then first, last and step. The step is written unless
# it is 1, or -1 on a range that counts down.
ins_range:
 mov rcx,[rdi]
 shl rcx,4
 lea rdx,[rdi+rcx+8]
 push rdx
 mov rdi,[rdx]
 call ins_int
 lea rsi,[rip+ins_dots]
 mov ecx,2
 call ins_text
 mov rdx,[rsp]
 mov rdi,[rdx+8]
 call ins_int
 pop rdx
 mov rax,[rdx+16]
 cmp rax,1
 je 9f
 cmp rax,-1
 jne 1f
 mov rcx,[rdx]
 cmp rcx,[rdx+8]
 jg 9f
1:
 push rdx
 lea rsi,[rip+ins_slashes]
 mov ecx,2
 call ins_text
 pop rdx
 mov rdi,[rdx+16]
 jmp ins_int
9:
 ret
# A float: the float runtime, whose table entry the node names, appends it.
ins_float:
 mov ecx,[rsi+3]
 mov eax,1
.ifdef PIC
# The entry's address in the table's copy (spec/darwin-arm64.md).
 sub ecx,0x400420
 jmp [rcx*1+0x400420]
.else
 jmp [rcx]
.endif
# A date or time of the library is written as its sigil, the fields after
# the struct's count: 30 Date (year, month, day), 31 Time (hour, minute,
# second, microsecond), 32 NaiveDateTime (both), 33 DateTime (both, then the
# time zone and the offset in seconds). A DateTime outside Etc/UTC is
# written #DateTime<day clock+hh:mm zone>.
ins_calendar:
 push rdi
 push rax
 cmp eax,33
 jne 1f
 mov rsi,[rdi+64]
 cmp qword ptr [rsi],7
 jne ins_zoned
 add rsi,8
 lea rdi,[rip+ins_utc]
 mov ecx,7
 repe cmpsb
 jne ins_zoned
1:
 mov al,126
 call ins_char
 mov rax,[rsp]
 lea rsi,[rip+ins_letters]
 mov al,[rsi+rax-30]
 call ins_char
 mov al,91
 call ins_char
 mov rdi,[rsp+8]
 cmp qword ptr [rsp],31
 je 2f
 call ins_day
 cmp qword ptr [rsp],30
 je 3f
 mov al,32
 cmp qword ptr [rsp],33
 jne 4f
 mov al,84
4:
 call ins_char
 mov rdi,[rsp+8]
 add rdi,24
2:
 call ins_clock
 cmp qword ptr [rsp],33
 jne 3f
 mov al,90
 call ins_char
3:
 add rsp,16
 mov al,93
 jmp ins_char
ins_zoned:
 lea rsi,[rip+ins_datetime]
 mov ecx,10
 call ins_text
 mov rdi,[rsp+8]
 call ins_day
 mov al,32
 call ins_char
 mov rdi,[rsp+8]
 add rdi,24
 call ins_clock
 mov rdi,[rsp+8]
 mov rax,[rdi+72]
 mov cl,43
 test rax,rax
 jns 1f
 neg rax
 mov cl,45
1:
 push rax
 mov al,cl
 call ins_char
 mov rax,[rsp]
 xor edx,edx
 mov ecx,3600
 div rcx
 mov [rsp],rdx
 mov rdi,rax
 mov edx,2
 call ins_padded
 mov al,58
 call ins_char
 pop rax
 xor edx,edx
 mov ecx,60
 div rcx
 mov rdi,rax
 mov edx,2
 call ins_padded
 mov al,32
 call ins_char
 mov rsi,[rsp+8]
 mov rsi,[rsi+64]
 mov rcx,[rsi]
 add rsi,8
 call ins_text
 add rsp,16
 mov al,62
 jmp ins_char
# year-month-day and hour:minute:second with the microseconds unless they
# are 0, from the three or four fields after RDI+8.
ins_day:
 push rdi
 mov rdi,[rdi+8]
 mov edx,4
 call ins_padded
 mov al,45
 call ins_char
 mov rdi,[rsp]
 mov rdi,[rdi+16]
 mov edx,2
 call ins_padded
 mov al,45
 call ins_char
 pop rdi
 mov rdi,[rdi+24]
 mov edx,2
 jmp ins_padded
ins_clock:
 push rdi
 mov rdi,[rdi+8]
 mov edx,2
 call ins_padded
 mov al,58
 call ins_char
 mov rdi,[rsp]
 mov rdi,[rdi+16]
 mov edx,2
 call ins_padded
 mov al,58
 call ins_char
 mov rdi,[rsp]
 mov rdi,[rdi+24]
 mov edx,2
 call ins_padded
 pop rdi
 mov rdi,[rdi+32]
 test rdi,rdi
 jz 9f
 push rdi
 mov al,46
 call ins_char
 pop rdi
 mov edx,6
 jmp ins_padded
9:
 ret
# The integer in RDI in at least EDX characters: zeros after its sign, as
# Go's %0Nd writes it.
ins_padded:
 mov rax,rdi
 sub rsp,40
 lea rsi,[rsp+40]
 mov ecx,10
 mov r8d,edx
 test rax,rax
 jns 1f
 neg rax
 dec r8d
1:
 xor edx,edx
 div rcx
 add dl,48
 dec rsi
 mov [rsi],dl
 dec r8d
 test rax,rax
 jnz 1b
2:
 test r8d,r8d
 jle 3f
 dec rsi
 mov byte ptr [rsi],48
 dec r8d
 jmp 2b
3:
 test rdi,rdi
 jns 4f
 dec rsi
 mov byte ptr [rsi],45
4:
 lea rcx,[rsp+40]
 sub rcx,rsi
 call ins_text
 add rsp,40
 ret
ins_atom:
 push rdi
 mov al,58
 call ins_char
 pop rsi
 mov rcx,[rsi]
 add rsi,8
 jmp ins_text
# A list of {atom, value} tuples is written as a keyword list.
ins_list:
 push rdi
 push rdx
 mov al,91
 call ins_char
 pop rsi
 pop rdi
 mov rcx,[rdi]
 add rdi,8
 cmp byte ptr [rsi+2],35
 jne 4f
 push rbx
 mov rsi,[rsi+8]
 mov rbx,rsi
 cmp byte ptr [rsi+2],36
 jne 3f
 add rsi,3
3:
 call ins_items
 pop rbx
 jmp 8f
4:
 call ins_items
8:
 mov al,93
 jmp ins_char
ins_items:
 cmp byte ptr [rsi+2],5
 jne 5f
 cmp byte ptr [rsi+3],2
 jne 5f
 cmp byte ptr [rsi+6],22
 je 3f
 cmp byte ptr [rsi+6],35
 jne 5f
 mov rax,[rsi+12]
 cmp byte ptr [rax+2],22
 jne 5f
3:
 test rcx,rcx
 jz 5f
 movzx eax,word ptr [rsi+4]
 lea rsi,[rsi+rax+4]
 push rdi
 push rcx
 push rsi
6:
 mov rsi,[rsp+16]
 mov rsi,[rsi]
 mov rsi,[rsi+8]
 mov rcx,[rsi]
 add rsi,8
 call ins_text
 lea rsi,[rip+ins_colon]
 mov ecx,2
 call ins_text
 mov rdi,[rsp+16]
 mov rdi,[rdi]
 mov rdi,[rdi+16]
 mov rsi,[rsp]
 call ins
 add qword ptr [rsp+16],16
 dec qword ptr [rsp+8]
 jz 7f
 lea rsi,[rip+ins_comma]
 mov ecx,2
 call ins_text
 jmp 6b
7:
 add rsp,24
 ret
5:
 xor r8d,r8d
 jmp ins_pairs
ins_tuple:
 push rdi
 push rdx
 mov al,123
 call ins_char
 pop rsi
 pop rdi
 call ins_count
 mov rcx,[rdi]
 add rdi,8
 mov r8d,1
 call ins_seq
 mov al,125
 jmp ins_char
ins_map:
 push rdi
 push rdx
 mov al,37
 call ins_char
 mov al,123
 call ins_char
 pop rsi
 pop rdi
 push qword ptr [r14-496]
 mov qword ptr [r14-496],0
 mov edx,1
 call ins_tree
 pop qword ptr [r14-496]
 mov al,125
 jmp ins_char
# A set: MapSet.new([...]) around the keys of its map, by the node at RDX.
ins_set:
 push rdi
 push rdx
 lea rsi,[rip+ins_mapset]
 mov ecx,12
 call ins_text
 pop rsi
 pop rdi
 push qword ptr [r14-496]
 mov qword ptr [r14-496],0
 xor edx,edx
 call ins_tree
 pop qword ptr [r14-496]
 mov al,93
 call ins_char
 jmp ins_close
# The entries of the map at RDI in the order of their keys, by the node at
# RSI (the value's follows it): key => value with EDX 1, the key alone
# with 0. A map is a leaf, its count and its keys and values, or with bit
# 62 of its first word a branch: the count of its children at +8 and, 16
# bytes each from +16, a key and a child (spec/memory-x86_64.s). The word
# at R14-496 counts the entries written, for the commas between them.
ins_tree:
 mov rax,[rdi]
 bt rax,62
 jc 5f
 test rax,rax
 jz 9f
 add rdi,8
 push rdi
 push rax
 push rsi
 push rdx
1:
 cmp qword ptr [r14-496],0
 je 2f
 lea rsi,[rip+ins_comma]
 mov ecx,2
 call ins_text
2:
 inc qword ptr [r14-496]
 mov rdi,[rsp+24]
 mov rdi,[rdi]
 mov rsi,[rsp+8]
 call ins
 cmp qword ptr [rsp],0
 je 3f
 lea rsi,[rip+ins_arrow]
 mov ecx,4
 call ins_text
 mov rdi,[rsp+24]
 mov rdi,[rdi+8]
 mov rsi,[rsp+8]
 movzx eax,word ptr [rsi]
 add rsi,rax
 call ins
3:
 add qword ptr [rsp+24],16
 dec qword ptr [rsp+16]
 jnz 1b
 add rsp,32
9:
 ret
5:
 mov rcx,[rdi+8]
 add rdi,16
 push rdi
 push rcx
 push rsi
 push rdx
6:
 mov rdi,[rsp+24]
 mov rdi,[rdi+8]
 mov rsi,[rsp+8]
 mov rdx,[rsp]
 call ins_tree
 add qword ptr [rsp+24],16
 dec qword ptr [rsp+16]
 jnz 6b
 add rsp,32
 ret
ins_struct:
# A name that starts with # is the whole text: #fileHandle<>.
 cmp byte ptr [rdx+1],35
 jne 0f
 mov rsi,rdx
 call ins_count
 jmp ins_text
0:
 push rdi
 push rdx
 mov al,37
 call ins_char
 mov rsi,[rsp]
 call ins_count
 call ins_text
 mov [rsp],rsi
 mov al,123
 call ins_char
 pop rsi
 pop rdi
 call ins_count
 add rdi,8
 test ecx,ecx
 jz 9f
 push rdi
 push rcx
 push rsi
1:
 mov rsi,[rsp]
 call ins_count
 call ins_text
 mov [rsp],rsi
 lea rsi,[rip+ins_colon]
 mov ecx,2
 call ins_text
 mov rdi,[rsp+16]
 mov rdi,[rdi]
 mov rsi,[rsp]
 call ins
 mov rsi,[rsp]
 movzx eax,word ptr [rsi]
 add [rsp],rax
 add qword ptr [rsp+16],8
 dec qword ptr [rsp+8]
 jz 8f
 lea rsi,[rip+ins_comma]
 mov ecx,2
 call ins_text
 jmp 1b
8:
 add rsp,24
9:
 mov al,125
 jmp ins_char
ins_sum:
# A sum value whose variant is -1 is the one a receive that ran out of time
# leaves (the pinned runtime's nil; zf_zero).
 cmp qword ptr [rdi+8],-1
 jne 1f
ins_absent:
 lea rsi,[rip+ins_nil]
 mov ecx,3
 jmp ins_text
1:
 push rdi
 push rdx
 mov rsi,rdx
 call ins_count
 call ins_text
 mov al,46
 call ins_char
 mov rsi,[rsp]
 call ins_count
 add rsi,rcx
 call ins_count
 mov rdi,[rsp+8]
 mov rcx,[rdi+8]
1:
 test rcx,rcx
 jz 2f
 movzx eax,word ptr [rsi]
 add rsi,rax
 dec rcx
 jmp 1b
2:
 add rsi,2
 call ins_count
 call ins_text
 pop rdx
 pop rdi
 call ins_count
 test ecx,ecx
 jz 9f
 push rdi
 push rsi
 push rcx
 mov al,40
 call ins_char
 pop rcx
 pop rsi
 pop rdi
 add rdi,16
 mov r8d,1
 call ins_seq
 jmp ins_close
9:
 ret
# A count or the length of a name at RSI, into ECX: one byte, or the byte
# 255 and 32 bits. RSI moves past it.
ins_count:
 movzx ecx,byte ptr [rsi]
 inc rsi
 cmp ecx,255
 jne 1f
 mov ecx,[rsi]
 add rsi,4
1:
 ret
ins_function: .ascii "#Function<>"
ins_mapset: .ascii "MapSet.new(["
ins_regexp: .ascii "#Regexp<>"
ins_true: .ascii "true"
ins_false: .ascii "false"
ins_none: .ascii "none"
ins_nil: .ascii "nil"
ins_some: .ascii "some("
ins_ok: .ascii "ok("
ins_error: .ascii "error("
ins_comma: .ascii ", "
ins_arrow: .ascii " => "
ins_colon: .ascii ": "
ins_utc: .ascii "Etc/UTC"
ins_letters: .ascii "DTNU"
ins_datetime: .ascii "#DateTime<"
ins_dots: .ascii ".."
ins_slashes: .ascii "//"
# RSI bytes, RCX count; RDI write flag, R11 output cursor.
ip_copy:
 movzx edx,byte ptr [rsi]
 put dl
 inc rsi
 dec ecx
 jnz ip_copy
 ret
# strconv.Quote of RSI/RCX bytes, including both quote marks.
ip_quote:
 put 34
ip_quote_loop:
 test rcx,rcx
 jz ip_quote_done
 call ip_decode
 cmp r8d,1
 jne ip_quote_valid
 cmp eax,65533
 jne ip_quote_valid
 movzx r10d,byte ptr [rsi]
 put 92
 put 120
 shl r10d,24
 mov r9d,2
 call ip_hex
 jmp ip_quote_next
ip_quote_valid:
 cmp eax,34
 je ip_quote_backslash
 cmp eax,92
 je ip_quote_backslash
 cmp eax,128
 jae ip_quote_unicode
 cmp eax,32
 jb ip_quote_control
 cmp eax,127
 je ip_quote_control
 put al
 jmp ip_quote_next
ip_quote_backslash:
 put 92
 put al
 jmp ip_quote_next
ip_quote_control:
 lea edx,[rax-7]
 cmp edx,6
 ja ip_quote_hex
 lea r9,[rip+ip_escapes]
 movzx edx,byte ptr [r9+rdx]
 put 92
 put dl
 jmp ip_quote_next
ip_quote_hex:
 mov r10d,eax
 put 92
 put 120
 shl r10d,24
 mov r9d,2
 call ip_hex
 jmp ip_quote_next
ip_quote_unicode:
 call ip_print
 test edx,edx
 jz ip_quote_escape
 xor r9d,r9d
ip_quote_raw:
 movzx edx,byte ptr [rsi+r9]
 put dl
 inc r9d
 cmp r9d,r8d
 jb ip_quote_raw
 jmp ip_quote_next
ip_quote_escape:
 mov r10d,eax
 put 92
 cmp eax,65536
 jae ip_quote_long
 put 117
 shl r10d,16
 mov r9d,4
 call ip_hex
 jmp ip_quote_next
ip_quote_long:
 put 85
 mov r9d,8
 call ip_hex
ip_quote_next:
 add rsi,r8
 sub rcx,r8
 jmp ip_quote_loop
ip_quote_done:
 put 34
 ret
# Lowercase hexadecimal: R9D digits from the top of R10D.
ip_hex:
 rol r10d,4
 mov edx,r10d
 and edx,15
 add edx,48
 cmp edx,58
 jb ip_hex_digit
 add edx,39
ip_hex_digit:
 put dl
 dec r9d
 jnz ip_hex
 ret
# Exact Go UTF-8 decoding of RSI/RCX: EAX rune, R8D width; invalid consumes one byte.
ip_decode:
 movzx edx,byte ptr [rsi]
 mov eax,edx
 mov r8d,1
 cmp edx,128
 jb ip_decode_done
 cmp edx,194
 jb ip_invalid
 cmp edx,244
 ja ip_invalid
 mov r8d,2
 cmp edx,224
 jb ip_decode_width
 inc r8d
 cmp edx,240
 jb ip_decode_width
 inc r8d
ip_decode_width:
 cmp rcx,r8
 jb ip_invalid
 movzx r9d,byte ptr [rsi+1]
 cmp r9d,128
 jb ip_invalid
 cmp r9d,191
 ja ip_invalid
 cmp edx,224
 jne ip_decode_ed
 cmp r9d,160
 jb ip_invalid
ip_decode_ed:
 cmp edx,237
 jne ip_decode_f0
 cmp r9d,160
 jae ip_invalid
ip_decode_f0:
 cmp edx,240
 jne ip_decode_f4
 cmp r9d,144
 jb ip_invalid
ip_decode_f4:
 cmp edx,244
 jne ip_decode_rest
 cmp r9d,144
 jae ip_invalid
ip_decode_rest:
 and r9d,63
 cmp r8d,2
 jne ip_decode_three
 and eax,31
 shl eax,6
 or eax,r9d
 ret
ip_decode_three:
 movzx r10d,byte ptr [rsi+2]
 cmp r10d,128
 jb ip_invalid
 cmp r10d,191
 ja ip_invalid
 and r10d,63
 cmp r8d,3
 jne ip_decode_four
 and eax,15
 shl eax,12
 shl r9d,6
 or eax,r9d
 or eax,r10d
 ret
ip_decode_four:
 movzx edx,byte ptr [rsi+3]
 cmp edx,128
 jb ip_invalid
 cmp edx,191
 ja ip_invalid
 and edx,63
 and eax,7
 shl eax,18
 shl r9d,12
 shl r10d,6
 or eax,r9d
 or eax,r10d
 or eax,edx
ip_decode_done:
 ret
ip_invalid:
 mov eax,65533
 mov r8d,1
 ret
# strconv.IsPrint for EAX>=128: EDX=1 inside a packed printable range.
# Each five-byte entry is start21 | (end-start)17 << 21, sorted by start.
ip_print:
 push rcx
 lea r9,[rip+ip_ranges]
 mov r10d,PRINT_RANGE_COUNT
ip_print_loop:
 mov rdx,[r9]
 mov ecx,edx
 and ecx,2097151
 cmp eax,ecx
 jb ip_print_no
 shr rdx,21
 and edx,131071
 add ecx,edx
 cmp eax,ecx
 jbe ip_print_yes
 add r9,5
 dec r10d
 jnz ip_print_loop
ip_print_no:
 xor edx,edx
 pop rcx
 ret
ip_print_yes:
 mov edx,1
 pop rcx
 ret
ip_escapes:
 .byte 97,98,116,110,118,102,114
ip_suffix:
 .ascii " is not an integer"
ip_base_text:
 .ascii " in base "
ip_ranges:
# PRINT_DATA
