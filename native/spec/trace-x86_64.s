# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# A program that cannot go on ends as the pinned runtime ends it: the place and
# the reason, then one line per active call, on standard error, with status 2.
#
# Emitted once per program as an extra function-table entry and entered by a
# call that does not return: EDI is the source position the message names and
# RSI the reason: its number in tr_reasons, or from 4096 up the address of a
# string holding it. The return address says which
# function failed and RBP is its frame.
#
# Every frame holds at RBP-136 the position of the statement it is running
# and at RBP-144 its closures: 0 for a function, 1 for a lambda, or the
# address of a record on the stack for an if or case used as a value (the
# pinned compiler makes each a closure): the outer chain, then the position of
# the statement around it.
#
# The compiler appends the tables: ten 32-bit words (offset from tr_data
# and count of the newline positions, of the files, of the names, of the
# bytes that continue a character, which a column does not count, and of
# the moved records of a rewritten program), then
#   lines: the position of every newline, 32 bits each, ascending;
#   files: where each file starts (32 bits), the length of its path (16 bits)
#          and the path, ascending;
#   names: one per function-table slot, a length byte and Module.function;
#   continuations: the position of every byte 0x80..0xBF, 32 bits each;
#   moved: where a piece of the rewritten text starts and its place in the
#          program as written, the place whose file it is shown in and a
#          number of columns, 32 bits each, ascending.
.intel_syntax noprefix
.text
# try (alchem-try.md). The word at R14-16 is the innermost handler record: on
# the stack, the record before it, the handler's address, and the RBP and R15
# of the try. A failure with a handler does not end the program: a failure
# record is pushed where it happened and the handler runs below it, in the
# frame of its try, so that nothing of the failing calls is lost before an arm
# takes the failure. The record, from its lowest word: the closure records and
# the position of the try's frame as they were, that frame, the handler
# record, the failure record this one passes on (0 for none), the type of a
# raised or thrown value (0 for none), that value, the message as a string,
# the reason, the position, and the RBP and return address of what failed.
# Reason 9 is a throw (RDX the value, RCX its type) and 10 an exception (the
# same, R8 its message). 11 raises the record in RDX again from where the
# handler stands, and 12 passes it on as it was once an after block is over.
 xor eax,eax
 xor r9d,r9d
 cmp rsi,9
 jb 30f
 cmp rsi,12
 ja 30f
 cmp rsi,10
 ja tr_again
 mov rax,rcx
 mov r9,rdx
 jne 30f
 mov rsi,r8
30:
 xor r10d,r10d
 mov r11,rbp
tr_raise:
 mov rcx,[r14-16]
 test rcx,rcx
 jz tr_unhandled
 push r11
 push rdi
 push rsi
 mov rdx,rsi
 cmp rsi,4096
 jae 32f
 lea rdx,[rip+tr_reasons]
 mov r8,rsi
31:
 test r8,r8
 jz 32f
 mov r11,[rdx]
 lea rdx,[rdx+r11+8]
 dec r8
 jmp 31b
32:
 push rdx
 push r9
 push rax
 push r10
 push rcx
 mov rdx,[rcx+16]
 push rdx
 mov rax,[rdx-136]
 push rax
 push qword ptr [rdx-144]
 mov rax,[rcx]
 mov [r14-16],rax
 mov rbp,rdx
 jmp [rcx+8]
tr_again:
 mov r10,rdx
 mov rax,[rdx+40]
 mov r9,[rdx+48]
 mov edi,[rdx+72]
 mov r11,rbp
 cmp rsi,12
 mov rsi,[rdx+64]
 jne tr_raise
 mov rcx,[rdx+16]                # passed on: the try's frame is as it was
 mov r8,[rdx]
 mov [rcx-144],r8
 mov r8,[rdx+8]
 mov [rcx-136],r8
 mov r11,[rdx+88]
 mov [rsp],r11
 mov r11,[rdx+80]
 jmp tr_raise
# No handler is left. What is shown is the failure where it first happened:
# every try it passed has its frame put back as it was.
tr_unhandled:
 test r10,r10
 jz tr_print
33:
 mov rcx,[r10+16]
 mov r8,[r10]
 mov [rcx-144],r8
 mov r8,[r10+8]
 mov [rcx-136],r8
 mov rax,[r10+32]
 test rax,rax
 jz 34f
 mov r10,rax
 jmp 33b
34:
 mov edi,[r10+72]
 mov rsi,[r10+64]
 mov rbp,[r10+80]
 lea rsp,[r10+88]
tr_print:
 mov r12d,edi
 mov r13,rsi
 mov rbx,[rsp]
 mov r15,rbp
 lea r14,[rip+tr_data]
# Position 0x7FFFFFFE: a failure of the runtime itself, which the pinned
# runtime shows as "<runtime>: " and the reason (a string), without calls.
 cmp r12d,0x7FFFFFFE
 jne 29f
 lea rsi,[rip+tr_runtime]
 mov edx,11
 call tr_write
 mov rdx,[r13]
 lea rsi,[r13+8]
 call tr_write
 lea rsi,[rip+tr_close+1]
 mov edx,1
 call tr_write
 jmp tr_exit
29:
# A failure inside a function of the library (its module's name starts with
# Alchem) is shown as the pinned runtime shows it: at the call that entered
# the library, whose position the calling frame holds at RBP-132, and
# without the library's own calls. A position passed with bit 31 set is the
# place to name whoever fails (Stream.__fail: a stream that fails when it is
# read names where it was made).
# One passed with bit 30 set shows no calls, as the pinned runtime shows
# none for a failure it raises without a trace (Process.self).
 xor eax,eax
 btr r12d,30
 adc eax,0
 push rax
 xor edi,edi
 btr r12d,31
 adc edi,0
 xor ebp,ebp
30:
 call tr_library
 jne 31f
 mov rax,[r15]
 test rax,rax
 jz 31f
 mov rbx,[r15+8]
 mov r15,rax
 inc ebp
 jmp 30b
31:
 test ebp,ebp
 jz 32f
 test edi,edi
 jnz 32f
 mov eax,[r15-152]
 test eax,eax
 jz 32f
 mov r12,rax
32:
 mov rax,r12
 call tr_place
 push rcx
 call tr_colon
 pop rax
 call tr_number
 lea rsi,[rip+tr_sep]
 mov edx,2
 call tr_write
 cmp r13,4096                  # a reason past the table is a string record
 jb 20f
 mov rdx,[r13]
 lea rsi,[r13+8]
 jmp 22f
20:
 lea rsi,[rip+tr_reasons]
 mov rax,r13
21:
 mov rdx,[rsi]
 add rsi,8
 test rax,rax
 jz 22f
 add rsi,rdx
 dec rax
 jmp 21b
22:
 call tr_write
 lea rsi,[rip+tr_close+1]
 mov edx,1
 call tr_write
 pop rax
 test eax,eax
 jnz tr_exit
 cmp r13,9                     # a throw nothing caught shows no calls
 je tr_exit
 push 0                        # no frame a handler stands in is being shown
 push 0
 mov ebp,63                    # the pinned runtime shows 63 calls, or 61
 cmp r13,1                     # when it stopped for depth
 jne tr_frame
 sub ebp,2                     # and not the call that went too deep
 mov rbx,[r15+8]
 mov r15,[r15]
 test r15,r15
 jz tr_exit
tr_frame:
 call tr_library
 je 3f
 cmp r15,[rsp]                 # back in the frame of the try whose handler
 jne 35f                       # was shown: it stands where it failed
 pop rax
 pop rax
 mov r12,[rax+8]
 mov r13,[rax]
 jmp tr_line
35:
 mov r12,[r15-136]
 mov r13,[r15-144]
tr_line:
 test ebp,ebp
 jz tr_exit
 dec ebp
 lea rsi,[rip+tr_at]
 mov edx,5
 call tr_write
 call tr_name
 test r13,r13
 jz 2f
 lea rsi,[rip+tr_closure]
 mov edx,10
 call tr_write
2:
 lea rsi,[rip+tr_open]
 mov edx,2
 call tr_write
 mov rax,r12
 call tr_place
 lea rsi,[rip+tr_close]
 mov edx,2
 call tr_write
 cmp r13,1
 jbe 3f
 test r13b,1                   # an odd record is a failure record: the calls
 jnz 36f                       # that failed come next, up to this frame
 mov r12,[r13+8]
 mov r13,[r13]
 jmp tr_line
36:
 lea rax,[r13-1]
 push rax
 push r15
 mov rbx,[rax+88]
 mov r15,[rax+80]
 jmp tr_frame
3:
 mov rbx,[r15+8]
 mov r15,[r15]
 test r15,r15
 jnz tr_frame
tr_exit:
 mov edi,2
 mov eax,60
 syscall
# The name of the function whose code holds RBX: the last slot that starts at
# or before it.
tr_name:
 call tr_find
 movzx edx,byte ptr [rsi]
 inc rsi
 jmp tr_write
# ZF when RBX is in a function of the library.
tr_library:
 call tr_find
 cmp byte ptr [rsi],6
 jb 9f
 cmp dword ptr [rsi+1],0x68636C41
 jne 9f
 cmp word ptr [rsi+5],0x6D65
9:
 ret
# RSI: the name record (a length byte, then the name) of the function whose
# code holds RBX.
tr_find:
 mov ecx,[r14+20]
 xor edx,edx
 xor eax,eax
4:
 cmp rdx,rcx
 jae 5f
 cmp [0x400480+rdx*8],rbx
 ja 5f
 mov rax,rdx
 inc rdx
 jmp 4b
5:
 mov esi,[r14+16]
 add rsi,r14
6:
 test rax,rax
 jz 7f
 movzx edx,byte ptr [rsi]
 lea rsi,[rsi+rdx+1]
 dec rax
 jmp 6b
7:
 ret
# Write path:line for the position in EAX and leave its column, in
# characters from 1, in RCX. The position is the low 24 bits of the 64-bit word; the bits above
# them count lines past its own, which is how a frame says the line the
# pinned compiler's generated code stands on inside a for.
tr_place:
 mov r8d,eax
 and r8d,0xFFFFFF
 shr rax,24
 push rax
# A program the compiler rewrote before compiling it (macros, protocols and
# templates, alchem-macros.md) names places in the rewritten text. Each
# moved record is where a piece of that text starts and where the piece
# stands in the program as written: the same bytes from there on, or with
# bit 31 the one place all of it stands for. The third word, unless it is
# all ones, is a place whose file is named instead of the piece's own: a
# function that use adds to a module is shown in that module's file. With
# bit 30 the place is an anchor: the piece is shown on the anchor's line, at
# its column plus the fourth word and, without bit 31, plus how far into the
# piece the position is (the code of a value in an HTML template, which the
# pinned compiler counts from the sigil).
 mov esi,[r14+32]
 add rsi,r14
 mov ecx,[r14+36]
 xor r9d,r9d
40:
 test ecx,ecx
 jz 41f
 cmp [rsi],r8d
 ja 41f
 mov r9,rsi
 add rsi,16
 dec ecx
 jmp 40b
41:
 mov edx,-1
 xor ecx,ecx
 test r9,r9
 jz 43f
 mov edx,[r9+8]
 mov eax,[r9+4]
 mov r10d,r8d
 sub r10d,[r9]
 btr eax,30
 jnc 46f
 mov ecx,[r9+12]
 btr eax,31
 jc 42f
 add ecx,r10d
 jmp 42f
46:
 btr eax,31
 jc 42f
 add eax,r10d
42:
 mov r8d,eax
43:
 push rdx
 push rcx
 mov esi,[r14+8]
 add rsi,r14
 mov ecx,[r14+12]
 mov r9,rsi
8:
 test ecx,ecx
 jz 9f
 cmp [rsi],r8d
 ja 9f
 mov r9,rsi
 movzx edx,word ptr [rsi+4]
 lea rsi,[rsi+rdx+6]
 dec ecx
 jmp 8b
9:
 mov r10d,[r9]
 mov r11d,1
 mov esi,[r14]
 add rsi,r14
 mov ecx,[r14+4]
10:
 test ecx,ecx
 jz 12f
 mov eax,[rsi]
 cmp eax,r8d
 jae 12f
 cmp eax,r10d
 jb 11f
 inc r11d
 lea r10d,[rax+1]
11:
 add rsi,4
 dec ecx
 jmp 10b
12:
 mov edi,r8d
 sub edi,r10d
 inc edi
 mov esi,[r14+24]
 add rsi,r14
 mov ecx,[r14+28]
16:
 test ecx,ecx
 jz 18f
 mov eax,[rsi]
 cmp eax,r8d
 jae 18f
 cmp eax,r10d
 jb 17f
 dec edi
17:
 add rsi,4
 dec ecx
 jmp 16b
18:
 pop rcx
 pop r10
 pop rax
 add r11d,eax
 add edi,ecx
 push rdi
 push r11
 cmp r10d,-1
 je 45f
 mov esi,[r14+8]
 add rsi,r14
 mov ecx,[r14+12]
 mov r9,rsi
44:
 test ecx,ecx
 jz 45f
 cmp [rsi],r10d
 ja 45f
 mov r9,rsi
 movzx edx,word ptr [rsi+4]
 lea rsi,[rsi+rdx+6]
 dec ecx
 jmp 44b
45:
 movzx edx,word ptr [r9+4]
 lea rsi,[r9+6]
 call tr_write
 call tr_colon
 pop rax
 call tr_number
 pop rcx
 ret
tr_colon:
 lea rsi,[rip+tr_sep]
 mov edx,1
 jmp tr_write
tr_number:
 sub rsp,24
 lea rsi,[rsp+24]
 mov ecx,10
13:
 xor edx,edx
 div ecx
 add dl,48
 dec rsi
 mov [rsi],dl
 test eax,eax
 jnz 13b
 lea rdx,[rsp+24]
 sub rdx,rsi
 call tr_write
 add rsp,24
 ret
tr_write:
 test rdx,rdx
 jz 15f
 mov edi,2
 mov eax,1
 push rsi
 push rdx
 syscall
 pop rdx
 pop rsi
 cmp rax,-4
 je tr_write
 test rax,rax
 jle 15f
 add rsi,rax
 sub rdx,rax
 jnz tr_write
15:
 ret
tr_sep: .ascii ": "
tr_runtime: .ascii "<runtime>: "
# The reasons by number, each a string: its length in eight bytes, then its bytes.
tr_reasons:
 .quad 20
 .ascii "pattern match failed"
 .quad 19
 .ascii "call depth exceeded"
 .quad 37
 .ascii "exit status must be between 0 and 255"
 .quad 16
 .ascii "integer overflow"
 .quad 16
 .ascii "division by zero"
 .quad 42
 .ascii "integer power needs a nonnegative exponent"
 .quad 16
 .ascii "assertion failed"
 .quad 17
 .ascii "the list is empty"
 .quad 22
 .ascii "no cond clause matched"
 .quad 14
 .ascii "uncaught throw"
tr_at: .ascii "  at "
tr_closure: .ascii " <closure>"
tr_open: .ascii " ("
tr_close: .ascii ")\n"
tr_data:
