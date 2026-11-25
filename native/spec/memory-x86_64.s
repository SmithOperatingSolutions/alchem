# The collector of a native program (spec/alchem-memory.md). Assembled by
# scripts/generate-memory-runtime.py into
# implementations/alchem/native-memory-data.alc; position independent, and
# appended to a program's code. Its first bytes are five jumps, which the
# words at 0x400458..0x400478 of the entry address:
#   +0  gm_alloc    the allocation hook   (call [0x400478])
#   +5  gm_reserve  the reserve hook      (call [0x400470])
#   +10 gm_syscall  Sys.call              (call [0x400468])
#   +15 gm_init     once, from the entry  (call [0x400460])
#   +20 gm_grow     the grow hook         (call [0x400458])
#   +25 gm_off      in place of gm_init for a program that does not collect (no entry starts it now: compilers collect too)
#   +30 gm_map_get, +35 gm_map_put, +40 gm_map_delete, +45 gm_map_entries,
#   +50 gm_map_new, +55 gm_map_flat: maps of more than 32 entries
#       (call [0x400428] to call [0x400450])
#
# R12 is where the next value starts and R14 the initial stack pointer. The
# collector's words are the 1536 bytes below R14 (G). R13 is 0 while a
# program collects, so that every allocation site calls gm_alloc; after
# gm_reserve it is the end of the room reserved.
.intel_syntax noprefix
.text
.set G,1536
.set LIM,0            # end of the window allocation runs in; 0: none
.set SBIAS,8          # S less the arena's start in bits
.set BASE,16
.set END,24
.set FRONT,32         # everything from here up was never used, or is free and zero
.set WSTART,40
.set WFRONT,48        # the window is fresh arena at the frontier
.set USED,56          # bytes of windows closed since the last collection
.set THRESH,64
.set LIVE,72          # bytes found live by the last collection
.set SMAP,80
.set MMAP,88
.set FMAP,96
.set SSMAP,104
.set MSBASE,112
.set MSEND,120
.set MAPS,128         # the table of mapped blocks: start, end (bit 0: a stack)
.set NMAPS,136
.set MAPCAP,144
.set MAINLO,152
.set MAINHI,160
.set COUNT,168        # collections
.set MODE,176         # 1: collecting
.set OVER,184         # the mark stack was full
.set MSP,192
.set TOTAL,200        # bytes of windows closed since the start
.set FREEB,208        # bytes in the lists of free ranges
# What R13 is while nothing is reserved: 0, or the arena's end in a program
# that does not collect. Sites read it (gm_release).
.set REST,216
.set GROW,224         # where the text inspect is writing starts
.set OLD,232          # gm_grow: where the room was,
.set HELD,240         # how many bytes of it to keep
.set NEED,248         # and how many it has to hold
.set BINS,256         # 48 lists of free ranges, by the highest bit of their size
.set TAILS,640        # their last ranges, while a sweep builds them
.set GSIZE,1024
.set MINHOLE,128
.set CHUNK,1048576
# Assembled with STRESS defined (scripts/generate-memory-runtime.py --stress,
# for testing only) a program collects after every 64 KiB, and every value
# is made 64 bytes further on than its site meant to make it: a site that
# kept an address from before the hook's call writes into those 64 bytes,
# which the next call finds changed and stops at (an invalid instruction).
.set MAINSP,1032      # the main stack's pointer where Process.__switch left it (R14-504)
.set OWNED,1056       # 1 once a bit of M says that a value is owned (gm_own): M is cleared before marks
.set DTOP,1064        # what lies from DLOW up to here was in use and is not zero;
.set DLOW,1072        # from the frontier up to DLOW, and from DTOP on, the arena is zero
.ifdef STRESS
.set FLOOR,65536
.set GAP,1024
.else
.set FLOOR,8388608
.endif
.macro jump5 target
 .byte 0xe9
 .long \target-.-4
.endm
 jump5 gm_alloc
 jump5 gm_reserve
 jump5 gm_syscall
 jump5 gm_init
 jump5 gm_grow
 jump5 gm_off
 jump5 gm_map_get
 jump5 gm_map_put
 jump5 gm_map_delete
 jump5 gm_map_entries
 jump5 gm_map_new
 jump5 gm_map_flat

# R12 start, R11 end of a value about to be made. Keeps every register but
# R11, R12 (moved together when the value goes elsewhere), R13 and the flags.
gm_alloc:
.ifdef STRESS
 jmp gm_alloc_slow
.endif
 cmp r11,[r14-G+LIM]
 ja gm_alloc_slow
 test r12b,7
 jnz gm_alloc_slow
 xor r13d,r13d
 push rax
 push rcx
 mov rax,r12
 shr rax,3
 mov rcx,[r14-G+SBIAS]
 bts [rcx],rax
 pop rcx
 pop rax
 ret
gm_alloc_slow:
 push r15
 push r14
 push r13
 push r12
 push r11
 push r10
 push r9
 push r8
 push rdi
 push rsi
 push rbp
 push rbx
 push rdx
 push rcx
 push rax
 lea rbx,[r14-G]
 cmp qword ptr [rbx+MODE],0
 je gm_full
 xor edx,edx
 call gm_refill
 mov qword ptr [rsp+96],0
gm_resume:
 pop rax
 pop rcx
 pop rdx
 pop rbx
 pop rbp
 pop rsi
 pop rdi
 pop r8
 pop r9
 pop r10
 pop r11
 pop r12
 pop r13
 pop r14
 pop r15
 ret
gm_full:
 mov edi,71
 mov eax,60
 syscall

# R12 start, R11 the end a site may fill up to. Gives R12 with that much
# room (or what there is) and R13 = R11 = its end.
gm_reserve:
 cmp qword ptr [r14-G+MODE],0
 je 9f
.ifdef STRESS
 jmp 1f
.endif
 cmp r11,[r14-G+LIM]
 ja 1f
 test r12b,7
 jnz 1f
 mov r13,r11
 push rax
 push rcx
 mov rax,r12
 shr rax,3
 mov rcx,[r14-G+SBIAS]
 bts [rcx],rax
 pop rcx
 pop rax
9:
 ret
1:
 push r15
 push r14
 push r13
 push r12
 push r11
 push r10
 push r9
 push r8
 push rdi
 push rsi
 push rbp
 push rbx
 push rdx
 push rcx
 push rax
 lea rbx,[r14-G]
 mov edx,1
 call gm_refill
 mov rax,[rsp+80]
 mov [rsp+96],rax
 jmp gm_resume

# A program that does not collect: the hooks find the collector off, and
# R13 stays the arena's end.
gm_off:
 lea rdi,[r14-G]
 mov ecx,GSIZE/8+7
 xor eax,eax
 rep stosq
 mov [r14-G+REST],r13
 ret

# The room from R12 to R13 has to reach R11. It is made longer where it is,
# or the bytes move to room twice as large; R11 is then by how much.
gm_grow:
 cmp qword ptr [r14-G+MODE],0
 je gm_full
 push r15
 push r14
 push r13
 push r12
 push r11
 push r10
 push r9
 push r8
 push rdi
 push rsi
 push rbp
 push rbx
 push rdx
 push rcx
 push rax
 lea rbx,[r14-G]
 mov rsi,[rsp+88]
 mov [rbx+OLD],rsi
 mov r15,[rsp+80]
 sub r15,rsi
 mov [rbx+NEED],r15
 mov r13,[rsp+96]
 sub r13,rsi
 mov [rbx+HELD],r13
 lea r12,[r13+r13]
 cmp r12,r15
 jae 1f
 mov r12,r15
1:
 add r12,7
 and r12,-8                        # what is asked for: twice as much
 mov rcx,[rbx+LIM]
 test rcx,rcx
 jz 5f
 lea rdx,[rsi+r12]
 cmp rdx,rcx
 jbe 4f
 cmp qword ptr [rbx+WFRONT],0
 je 3f
 mov rax,[rbx+END]                 # fresh arena behind it: the window grows
 cmp rdx,rax
 jbe 2f
 mov rdx,rax
2:
 lea rax,[rsi+r15]
 cmp rdx,rax
 jb 5f
 mov [rbx+LIM],rdx
 mov rdi,rcx
 mov rax,rdx
 call gm_clean
 jmp 4f
3:
 lea rdx,[rsi+r15]
 cmp rdx,rcx
 ja 5f
 mov rdx,rcx
4:
 mov [rsp+96],rdx
 mov qword ptr [rsp+80],0
 jmp gm_resume
5:
 mov rsi,[rsp+96]                  # it moves: what was there stays a value
 add rsi,7
 and rsi,-8
 test rcx,rcx
 jz 6f
 cmp rsi,rcx
 jbe 6f
 mov rsi,rcx
6:
 call gm_close
 mov rax,[rsp+88]
 add rax,r12
 mov [rsp+80],rax
 mov edx,1
 call gm_refill
 mov rax,[rsp+80]
 mov rdi,[rsp+88]
 mov [rsp+96],rax
 sub rax,rdi
 cmp rax,[rbx+NEED]
 jb gm_full
 mov rsi,[rbx+OLD]
 mov rax,rdi
 sub rax,rsi
 mov [rsp+80],rax
 mov rcx,[rbx+HELD]
 cld
 rep movsb
 jmp gm_resume

# The registers of the site are on the stack above the return address:
# [rsp+88] R11 and [rsp+96] R12 here. EDX is 1 for a reservation. Sets both
# to a place with room for the value, in a window, and its S bit.
gm_refill:
 mov r13,rdx
 mov rsi,[rsp+96]
 mov r15,[rsp+88]
 sub r15,rsi                       # the size
 add rsi,7
 and rsi,-8                        # where it would start
 mov rax,[rbx+LIM]
.ifdef STRESS
 mov rcx,[rbx+GAP]
 test rcx,rcx
 jz 12f
 mov qword ptr [rbx+GAP],0
 mov edx,8
11:
 cmp qword ptr [rcx+rdx*8-8],0
 je 13f
 ud2
13:
 dec edx
 jnz 11b
12:
 test rax,rax
 jz 2f
 lea rcx,[rsi+r15+64]
 cmp rcx,rax
 ja 2f
 mov rdx,rsi
 sub rdx,[rbx+BASE]
 shr rdx,3
 mov rcx,[rbx+SMAP]
 bts [rcx],rdx
 mov [rbx+GAP],rsi
 lea rax,[rsi+64]
 jmp gm_placed
.endif
 test rax,rax
 jz 2f
 cmp rsi,rax
 jbe 1f
 mov rsi,rax
1:
 lea rcx,[rsi+r15]
 cmp rcx,rax
 ja 2f
 mov rax,rsi                       # it fits where it is once aligned
 jmp gm_placed
2:
 call gm_close
 xor r12d,r12d                     # 1 once this call has collected
gm_again:
 mov rax,[rbx+USED]
 cmp rax,[rbx+THRESH]
 jb 1f
 test r12d,r12d
 jnz 1f
 call gm_collect
 mov r12d,1
1:
 mov ecx,7
 cmp r15,MINHOLE
 jbe 2f
 lea rax,[r15-1]
 bsr rcx,rax
 inc ecx
2:
 cmp ecx,48
 jae 4f
 mov rax,[rbx+BINS+rcx*8]
 test rax,rax
 jnz gm_take
 inc ecx
 jmp 2b
4:
 mov rax,[rbx+FRONT]
 mov rcx,[rbx+END]
 sub rcx,rax                       # fresh arena left
 cmp rcx,r15
 jb 6f
 lea rdx,[r15+7]
 and rdx,-8
 cmp rdx,CHUNK
 jae 5f
 mov edx,CHUNK
5:
 cmp rdx,rcx
 jbe gm_fresh
 mov rdx,rcx
 jmp gm_fresh
6:
 test r12d,r12d
 jnz 7f
 call gm_collect
 mov r12d,1
 jmp gm_again
7:
 test r13d,r13d
 jz gm_full
# A reservation takes what there is: fresh arena, or the largest free range.
 cmp rcx,4096
 jae 8f
 mov edx,47
71:
 mov rax,[rbx+BINS+rdx*8]
 test rax,rax
 jnz 72f
 dec edx
 cmp edx,7
 jae 71b
 test rcx,rcx
 jz gm_full
 jmp 8f
72:
 mov ecx,edx
 jmp gm_take
8:
 mov rax,[rbx+FRONT]
 mov rdx,rcx
gm_fresh:
 mov [rbx+WSTART],rax
 add rdx,rax
 mov [rbx+LIM],rdx
 mov qword ptr [rbx+WFRONT],1
 mov rdi,rax
 push rax
 mov rax,rdx
 call gm_clean
 pop rax
 jmp gm_placed
# The free range RAX of list RCX becomes the window. What a collection
# freed is as it was left: it is made zero here, when it is taken. Of a
# range much larger than what is asked for only the first part is taken
# (at least CHUNK), so that no more is made zero than is likely to be used;
# the rest stays a free range.
gm_take:
 mov rdx,[rax]
 mov [rbx+BINS+rcx*8],rdx
 mov rdx,[rax+8]
 sub [rbx+FREEB],rdx
 lea rdi,[r15+7]
 and rdi,-8
 cmp rdi,CHUNK
 jae 1f
 mov edi,CHUNK
1:
 mov rcx,rdx
 sub rcx,rdi
 jbe 2f
 cmp rcx,MINHOLE*2
 jb 2f
 lea rsi,[rax+rdi]                 # the rest: RCX bytes at RSI
 mov [rsi+8],rcx
 add [rbx+FREEB],rcx
 bsr rdx,rcx
 mov rcx,[rbx+BINS+rdx*8]
 mov [rsi],rcx
 mov [rbx+BINS+rdx*8],rsi
 sub rsi,[rbx+BASE]
 shr rsi,3
 mov rcx,[rbx+SMAP]
 bts [rcx],rsi
 mov rcx,[rbx+FMAP]
 bts [rcx],rsi
 mov rdx,rdi
2:
 mov [rbx+WSTART],rax
 mov rdi,rax
 mov rcx,rdx
 shr rcx,3
 mov rsi,rax
 xor eax,eax
 cld
 rep stosq
 mov rax,rsi
 add rdx,rax
 mov [rbx+LIM],rdx
 mov qword ptr [rbx+WFRONT],0
 mov rdx,rax
 sub rdx,[rbx+BASE]
 shr rdx,3
 mov rcx,[rbx+FMAP]
 btr [rcx],rdx
gm_placed:
 mov [rsp+96],rax
 mov rdx,rax
 sub rdx,[rbx+BASE]
 shr rdx,3
 mov rcx,[rbx+SMAP]
 bts [rcx],rdx
 add rax,r15
 mov rcx,[rbx+LIM]
 cmp rax,rcx
 jbe 1f
 mov rax,rcx                       # a reservation that got less
1:
 mov [rsp+88],rax
 ret

# Fresh arena from RDI to RAX is about to be used: what of it was in use
# before (from DLOW up to DTOP) is made zero, once. Keeps every register
# but RAX, RCX, RDI.
gm_clean:
 mov rcx,[rbx+DLOW]
 cmp rdi,rcx
 jae 1f
 mov rdi,rcx
1:
 mov rcx,[rbx+DTOP]
 cmp rax,rcx
 jbe 2f
 mov rax,rcx
2:
 cmp rdi,rax
 jae 9f
 mov [rbx+DLOW],rax
 mov rcx,rax
 sub rcx,rdi
 add rcx,7
 shr rcx,3
 xor eax,eax
 cld
 rep stosq
9:
 ret
# The window ends at RSI: what is left of it is a free range.
gm_close:
 mov rax,[rbx+LIM]
 test rax,rax
 jz 9f
 mov rcx,rsi
 sub rcx,[rbx+WSTART]
 add [rbx+USED],rcx
 add [rbx+TOTAL],rcx
 mov qword ptr [rbx+LIM],0
 cmp qword ptr [rbx+WFRONT],0
 je 1f
 mov [rbx+FRONT],rsi
 ret
1:
 sub rax,rsi                       # bytes left
 cmp rax,8
 jb 9f
 mov rdx,rsi
 sub rdx,[rbx+BASE]
 shr rdx,3
 mov rcx,[rbx+SMAP]
 bts [rcx],rdx
 mov rcx,[rbx+FMAP]
 bts [rcx],rdx
 cmp rax,MINHOLE
 jb 9f
 bsr rcx,rax
 mov rdx,[rbx+BINS+rcx*8]
 mov [rsi],rdx
 mov [rsi+8],rax
 mov [rbx+BINS+rcx*8],rsi
 add [rbx+FREEB],rax
9:
 ret

# Sys.call: the system call, with the mappings it makes and ends noted.
# As the instruction it stands for, it changes RAX, RCX and R11 only.
gm_syscall:
 cmp eax,1000000
 ja gm_more
 cmp eax,9
 je gm_map
 cmp eax,11
 je gm_unmap
 cmp eax,25
 je gm_remap
 syscall
 ret
# Numbers the kernel does not have: a collection, and the owned values
# (below, "Owned values").
gm_more:
 cmp eax,1000004
 je gm_str_append
 cmp eax,1000002
 je gm_map_oput
 cmp eax,1000005
 je gm_str_done
 cmp eax,1000003
 je gm_map_done
 cmp eax,1000006
 je gm_map_owned
 cmp eax,1000007
 je gm_map_own
 cmp eax,1000001
 je gm_force
 syscall
 ret
gm_map:
 push rsi
 push r10
 syscall
 pop r10
 pop rsi
 cmp rax,-4096
 ja 9f
 test r10d,32
 jz 9f
 cmp qword ptr [r14-G+MODE],0
 je 9f
 push rdx
 push rsi
 mov rcx,[r14-G+NMAPS]
 cmp rcx,[r14-G+MAPCAP]
 jae gm_full
 shl rcx,4
 add rcx,[r14-G+MAPS]
 mov [rcx],rax
 add rsi,4095
 and rsi,-4096
 add rsi,rax
 mov edx,r10d
 shr edx,14
 and edx,1
 or rsi,rdx
 mov [rcx+8],rsi
 inc qword ptr [r14-G+NMAPS]
 pop rsi
 pop rdx
9:
 ret
# The blocks of [RDI, RDI+RSI) leave the table: a block wholly inside goes,
# one that starts or ends inside is cut, one around it becomes two.
gm_unmap:
 syscall
 test rax,rax
 jnz 9f
 cmp qword ptr [r14-G+MODE],0
 je 9f
 push rdx
 push rsi
 push r8
 push r9
 add rsi,4095
 and rsi,-4096
 add rsi,rdi                       # the end
 mov rcx,[r14-G+MAPS]
 mov r11,[r14-G+NMAPS]
 shl r11,4
 add r11,rcx
1:
 cmp rcx,r11
 jae 8f
 mov r8,[rcx]
 mov r9,[rcx+8]
 mov rdx,r9
 and edx,1
 and r9,-2
 cmp r8,rsi
 jae 7f
 cmp r9,rdi
 jbe 7f
 cmp r8,rdi
 jb 3f
 cmp r9,rsi
 ja 2f
 sub r11,16                        # wholly inside: the last entry takes its place
 mov r8,[r11]
 mov [rcx],r8
 mov r8,[r11+8]
 mov [rcx+8],r8
 dec qword ptr [r14-G+NMAPS]
 jmp 1b
2:
 mov [rcx],rsi                     # its start is inside
 jmp 7f
3:
 mov [rcx+8],rdi                   # its end is inside: what stays is scanned whole (a stack without its top is none)
 cmp r9,rsi
 jbe 7f
 mov r8,[r14-G+NMAPS]              # the range is in its middle: what lies behind it is a block of its own
 cmp r8,[r14-G+MAPCAP]
 jae gm_full
 shl r8,4
 add r8,[r14-G+MAPS]
 mov [r8],rsi
 or r9,rdx
 mov [r8+8],r9
 inc qword ptr [r14-G+NMAPS]
 jmp 8f
7:
 add rcx,16
 jmp 1b
8:
 pop r9
 pop r8
 pop rsi
 pop rdx
9:
 ret
gm_remap:
 push rdi
 push rdx
 syscall
 pop rdx
 pop rdi
 cmp rax,-4096
 ja 9f
 cmp qword ptr [r14-G+MODE],0
 je 9f
 push rsi
 mov rcx,[r14-G+MAPS]
 mov r11,[r14-G+NMAPS]
 shl r11,4
 add r11,rcx
1:
 cmp rcx,r11
 jae 8f
 cmp [rcx],rdi
 je 2f
 add rcx,16
 jmp 1b
2:
 mov [rcx],rax
 mov rsi,[rcx+8]
 and esi,1
 lea r11,[rdx+4095]
 and r11,-4096
 add r11,rax
 or r11,rsi
 mov [rcx+8],r11
8:
 pop rsi
9:
 ret
# System.collect_garbage.
gm_force:
 push r15
 push r14
 push r13
 push r12
 push r11
 push r10
 push r9
 push r8
 push rdi
 push rsi
 push rbp
 push rbx
 push rdx
 push rcx
 push rax
 lea rbx,[r14-G]
 cmp qword ptr [rbx+MODE],0
 je 1f
 mov rsi,[rsp+88]
 add rsi,7
 and rsi,-8
 mov rax,[rbx+LIM]
 test rax,rax
 jz 2f
 cmp rsi,rax
 jbe 2f
 mov rsi,rax
2:
 call gm_close
 call gm_collect
 mov qword ptr [rsp+96],0
1:
 mov qword ptr [rsp],0
 jmp gm_resume

# From the entry: R12 and R13 are the arena's start and end, RSP the top of
# the main stack less this call. Without room for the tables the program
# runs as it did, without collecting.
gm_init:
 lea rbx,[r14-G]
 mov rdi,rbx
 mov ecx,GSIZE/8+7
 xor eax,eax
 rep stosq
 mov r8,r13
 sub r8,r12                        # the arena's size
 mov rsi,r8
 shr rsi,6
 lea rsi,[rsi+rsi*4]               # S, M, F, the mark stack's first part, the table
 mov rax,r8
 shr rax,12
 add rsi,rax                       # the summary
 mov rax,r8
 shr rax,4
 add rsi,rax                       # the mark stack
 add rsi,24575                     # a page behind each of S, M and F: the bit of the arena's end
 and rsi,-4096
 xor edi,edi
 mov edx,3
 mov r10d,0x4022
 push r8
 mov r8,-1
 xor r9d,r9d
 mov eax,9
 syscall
 pop r8
 cmp rax,-4096
 ja 9f
 mov rcx,r8
 shr rcx,6
 mov [rbx+SMAP],rax
 lea rax,[rax+rcx+4096]
 mov [rbx+MMAP],rax
 lea rax,[rax+rcx+4096]
 mov [rbx+FMAP],rax
 lea rax,[rax+rcx+4096]
 mov [rbx+MAPS],rax
 add rax,rcx
 mov rdx,rcx
 shr rdx,4
 mov [rbx+MAPCAP],rdx
 mov [rbx+SSMAP],rax
 mov rdx,r8
 shr rdx,12
 lea rax,[rax+rdx+8]
 mov [rbx+MSBASE],rax
 mov [rbx+MSP],rax
 add rax,rcx
 mov rdx,r8
 shr rdx,4
 add rax,rdx
 mov [rbx+MSEND],rax
 mov [rbx+BASE],r12
 mov [rbx+END],r13
 mov [rbx+FRONT],r12
 mov rax,r12
 shr rax,9
 shl rax,3
 mov rdx,[rbx+SMAP]
 sub rdx,rax
 mov [rbx+SBIAS],rdx
 mov qword ptr [rbx+THRESH],FLOOR
 lea rax,[rsp+8]
 mov [rbx+MAINHI],rax
 mov rax,[r14-8]
 sub rax,65536
 mov [rbx+MAINLO],rax
 mov qword ptr [rbx+MODE],1
 xor r13d,r13d
9:
 mov [rbx+REST],r13
 xor ebx,ebx
 ret

# A possible address in RDI: the value it lies in is marked and pushed.
# R15 is the arena's start and RBP the bytes below the frontier. Changes
# RAX, RCX, RDX, RSI, RDI, R8 and R9.
gm_mark:
 sub rdi,r15
 cmp rdi,rbp
 jae 9f
 shr rdi,3
 mov rsi,[rbx+SMAP]
 mov rdx,rdi
 shr rdx,6
 mov ecx,edi
 and ecx,63
 mov eax,2
 shl rax,cl
 dec rax
 and rax,[rsi+rdx*8]
 jnz 4f
 test rdx,rdx
 jz 9f
 lea r8,[rdx-1]
 mov r9,[rbx+SSMAP]
 mov ecx,r8d
 and ecx,63
 shr r8,6
 mov eax,2
 shl rax,cl
 dec rax
 and rax,[r9+r8*8]
1:
 test rax,rax
 jnz 2f
 test r8,r8
 jz 9f
 dec r8
 mov rax,[r9+r8*8]
 jmp 1b
2:
 bsr rax,rax
 shl r8,6
 lea rdx,[r8+rax]
 mov rax,[rsi+rdx*8]
 test rax,rax
 jz 9f
4:
 bsr rax,rax
 shl rdx,6
 add rdx,rax
 mov rsi,[rbx+FMAP]
 bt [rsi],rdx
 jc 9f
 mov rsi,[rbx+MMAP]
 bts [rsi],rdx
 jc 9f
 mov rax,[rbx+MSP]
 cmp rax,[rbx+MSEND]
 jae 8f
 mov [rax],rdx
 add rax,8
 mov [rbx+MSP],rax
 ret
8:
 mov qword ptr [rbx+OVER],1
9:
 ret

# Every word of [RDI, RSI) is a possible address. Changes R12 and R13 too.
gm_scan:
 mov r12,rdi
 mov r13,rsi
1:
 cmp r12,r13
 jae 9f
 mov rdi,[r12]
 add r12,8
 mov rax,rdi
 sub rax,r15
 cmp rax,rbp
 jae 1b
 call gm_mark
 jmp 1b
9:
 ret
# The same for [R12, R13) of a stack: a word also keeps the value just
# before the one it points at the start of, and the one a word further.
gm_scan_wide:
 cmp r12,r13
 jae 9f
 mov rdi,[r12]
 add r12,8
 lea rax,[rdi+8]
 sub rax,r15
 lea rcx,[rbp+16]
 cmp rax,rcx
 jae gm_scan_wide
 push rdi
 call gm_mark
 mov rdi,[rsp]
 dec rdi
 call gm_mark
 pop rdi
 add rdi,8
 call gm_mark
 jmp gm_scan_wide
9:
 ret
# The stack mapped at [RDI, RSI): from the stack pointer when it is the
# running one, else from where Process.__switch left it (RAX: the word
# below its top, which is the next free stack's top while it is free, or for
# the main stack the collector's word), else its top 64 bytes.
gm_stack:
 mov r13,rsi
 cmp rsp,rdi
 jb 1f
 cmp rsp,rsi
 jae 1f
 mov r12,rsp
 jmp gm_scan_wide
1:
 cmp rax,rdi
 jbe 2f
 cmp rax,rsi
 jae 2f
 test al,7
 jnz 2f
 mov r12,rax
 jmp gm_scan_wide
2:
 lea r12,[rsi-64]
 jmp gm_scan_wide
# The value that starts at bit RDI of S: its words up to the next value.
gm_object:
 mov rsi,[rbx+SMAP]
 lea rax,[rdi+1]
 mov rdx,rax
 shr rdx,6
 mov ecx,eax
 and ecx,63
 mov r8,-1
 shl r8,cl
 mov r9,rbp
 shr r9,3
 cmp rax,r9
 jae 3f
 and r8,[rsi+rdx*8]
1:
 test r8,r8
 jnz 2f
 inc rdx
 mov rax,rdx
 shl rax,6
 cmp rax,r9
 jae 3f
 mov r8,[rsi+rdx*8]
 jmp 1b
2:
 bsf r8,r8
 shl rdx,6
 add rdx,r8
 cmp rdx,r9
 jbe 4f
3:
 mov rdx,r9
4:
 lea rdi,[r15+rdi*8]
 lea rsi,[r15+rdx*8]
 jmp gm_scan
gm_drain:
 mov rax,[rbx+MSP]
 cmp rax,[rbx+MSBASE]
 jbe 9f
 sub rax,8
 mov [rbx+MSP],rax
 mov rdi,[rax]
 call gm_object
 jmp gm_drain
9:
 ret

# A collection. The window is closed and every register of the program is
# on the running stack.
gm_collect:
 push r12
 push r13
 push r15
 push rbp
 inc qword ptr [rbx+COUNT]
 mov r15,[rbx+BASE]
 mov rbp,[rbx+FRONT]
 sub rbp,r15
# The bits of M that said a value was owned (gm_own) go: nothing is owned
# after a collection.
 cmp qword ptr [rbx+OWNED],0
 je 1f
 mov qword ptr [rbx+OWNED],0
 mov rdi,[rbx+MMAP]
 mov rcx,rbp
 shr rcx,9
 inc rcx
 xor eax,eax
 rep stosq
1:
# The summary of S.
 mov rdi,[rbx+SSMAP]
 mov rcx,rbp
 shr rcx,15
 add rcx,2
 xor eax,eax
 rep stosq
 mov rsi,[rbx+SMAP]
 mov r8,[rbx+SSMAP]
 mov rcx,rbp
 shr rcx,9
 inc rcx
 xor edx,edx
1:
 cmp qword ptr [rsi+rdx*8],0
 je 2f
 bts [r8],rdx
2:
 inc rdx
 cmp rdx,rcx
 jb 1b
 mov rax,[rbx+MSBASE]
 mov [rbx+MSP],rax
 mov qword ptr [rbx+OVER],0
# Roots.
 mov rdi,[rbx+MAINLO]
 mov rsi,[rbx+MAINHI]
 mov rax,[rbx+MAINSP]
 call gm_stack
 mov r10,[rbx+MAPS]
 mov r11,[rbx+NMAPS]
 shl r11,4
 add r11,r10
3:
 cmp r10,r11
 jae 5f
 mov rdi,[r10]
 mov rsi,[r10+8]
 add r10,16
 test sil,1
 jz 4f
 and rsi,-2
 mov rax,[rsi-8]
 call gm_stack
 jmp 3b
4:
 call gm_scan
 jmp 3b
5:
 lea rdi,[r14-64]
 mov rsi,r14
 call gm_scan
# The library's block of working memory (the word that ends argv: Sys.state),
# which the coverage routine may have mapped itself.
 mov rdi,[r14]
 mov rdi,[r14+rdi*8+8]
 test rdi,rdi
 jz 51f
 lea rsi,[rdi+16384]
 call gm_scan
51:
 call gm_drain
# Values that were marked while the stack was full are gone through again.
6:
 cmp qword ptr [rbx+OVER],0
 je gm_sweep
 mov qword ptr [rbx+OVER],0
 xor r10d,r10d
7:
 mov rax,r10
 shl rax,9
 cmp rax,rbp
 jae 6b
 mov rax,[rbx+MMAP]
 mov r11,[rax+r10*8]
8:
 test r11,r11
 jz 81f
 bsf rdi,r11
 btr r11,rdi
 mov rax,r10
 shl rax,6
 add rdi,rax
 push r10
 push r11
 call gm_object
 call gm_drain
 pop r11
 pop r10
 jmp 8b
81:
 inc r10
 jmp 7b

# RSI S, R8 F, R9 M, R10 the bits below the frontier, R11 the word of S,
# RDI its bits still to see, RDX the value before (-1: none) and RBP its
# kind (0 live, 1 dead, 2 free already), R12 the first bit of the free
# range being gathered (-1: none). No byte of the arena is read or written
# but the two words a free range of MINHOLE or more waits with: what died
# stays as it is until its range is taken (gm_take) or the frontier passes
# it again (gm_clean).
gm_sweep:
 lea rdi,[rbx+BINS]
 mov ecx,96
 xor eax,eax
 rep stosq
 mov [rbx+FREEB],rax
 mov [rbx+LIVE],rax
 mov rsi,[rbx+SMAP]
 mov r8,[rbx+FMAP]
 mov r9,[rbx+MMAP]
 mov r10,rbp
 shr r10,3
 xor r11d,r11d
 mov r12,-1
 mov rdx,-1
 xor ebp,ebp
1:
 mov rax,r11
 shl rax,6
 cmp rax,r10
 jae gm_swept
 mov rdi,[rsi+r11*8]
# Inside a free range that is being gathered, a word of S with no mark holds
# only more of it (dead values, and ranges that were free): it joins at once.
 test r12,r12
 js 2f
 test ebp,ebp
 jz 2f
 cmp qword ptr [r9+r11*8],0
 jne 2f
 add rax,64
 cmp rax,r10
 ja 2f
 mov qword ptr [rsi+r11*8],0
 mov qword ptr [r8+r11*8],0
 inc r11
 jmp 1b
2:
 test rdi,rdi
 jnz 3f
 inc r11
 jmp 1b
3:
 bsf rcx,rdi
 btr rdi,rcx
 mov rax,r11
 shl rax,6
 add rcx,rax                       # the bit of this value
 cmp rcx,r10
 jae gm_swept
 call gm_done
 mov rdx,rcx
 btr [r9],rcx
 jc 6f
 mov ebp,1                         # dead, or free already
 test r12,r12
 jns 41f
 mov r12,rcx
 bts [r8],rcx
 jmp 2b
41:
 btr [rsi],rcx
 btr [r8],rcx
 jmp 2b
6:
 xor ebp,ebp                       # live
 test r12,r12
 js 2b
 call gm_range
 mov r12,-1
 jmp 2b
gm_swept:
 mov rcx,r10
 call gm_done
 btr [rsi],r10                     # a value of no bytes may have started at the frontier
 test r12,r12
 js 1f
 btr [rsi],r12                     # free up to the frontier: the frontier comes down
 btr [r8],r12
 lea rax,[r15+r12*8]
 mov rdi,[rbx+FRONT]
 mov [rbx+FRONT],rax
 mov [rbx+DLOW],rax
 cmp rdi,[rbx+DTOP]
 jbe 11f
 mov [rbx+DTOP],rdi
11:
# Pages given back when at least 4 MiB of them became free there.
 add rax,4095
 and rax,-4096
 mov rcx,rdi
 sub rdi,rax
 jbe 1f
 cmp rdi,4194304
 jb 1f
 mov rsi,rdi
 mov rdi,rax
 push rcx
 push rax
 mov edx,4
 mov eax,28
 syscall
 pop rdi
 pop rcx
# They come back zero, where the system took them: a system that does not
# leaves them as they were, and they are made zero when they are taken.
 test rax,rax
 jnz 1f
 cmp rcx,[rbx+DTOP]
 jne 1f
 mov [rbx+DTOP],rdi
1:
 mov rax,[rbx+LIVE]
 cmp rax,FLOOR
 jae 2f
 mov eax,FLOOR
2:
 mov [rbx+THRESH],rax
 mov qword ptr [rbx+USED],0
 pop rbp
 pop r15
 pop r13
 pop r12
 ret
# The value before, from bit RDX to bit RCX, is over: what is live is counted.
gm_done:
 test rdx,rdx
 js 9f
 test ebp,ebp
 jnz 9f
 mov rax,rcx
 sub rax,rdx
 shl rax,3
 add [rbx+LIVE],rax
9:
 ret
# The free range from bit R12 to bit RCX goes to the end of its list.
gm_range:
 mov rax,rcx
 sub rax,r12
 shl rax,3
 cmp rax,MINHOLE
 jb 9f
 push rcx
 push rdx
 lea rdx,[r15+r12*8]
 mov qword ptr [rdx],0
 mov [rdx+8],rax
 add [rbx+FREEB],rax
 bsr rcx,rax
 mov rax,[rbx+TAILS+rcx*8]
 test rax,rax
 jz 1f
 mov [rax],rdx
 jmp 2f
1:
 mov [rbx+BINS+rcx*8],rdx
2:
 mov [rbx+TAILS+rcx*8],rdx
 pop rdx
 pop rcx
9:
 ret

# ---- Maps of many entries (spec/alchem-memory.md, "Maps") ----
#
# A map is the address of a node. A leaf is what a map always was: the
# count of its entries and its keys and values side by side, in the order
# of the keys. A branch has bit 62 set in its first word beside the count
# of all entries below it; then the number of its children and, for each,
# a key no entry of that child is below (its least when the child was put
# there) and the child. The compiler's own code serves a leaf of up to 32
# entries (spec/collections-x86_64.s); these routines serve the rest. A
# map is never changed: putting and deleting copy the nodes on the way to
# the entry, at most 32 pairs each.
#
# R8 says how keys compare, as everywhere in the map code: 0 words, 2
# strings, 24 floats, above 48 twice the comparator of a compound type.
# A float that is a NaN, and a key of a compound type that holds one, is
# equal to nothing, itself included: it is never found, every put of one
# adds an entry, and it has no place in the order. Such keys stand after
# all others, in a leaf and in a tree, in the order they were put.
.set MTAG,62
.set LMAX,32
.set BMAX,32
.set INSN,1040        # entries inspect has written of the map it is in (R14-496)
# R11 bytes: RAX their address. They are zero.
.macro mk_alloc
 add r11,r12
 cmp r11,r13
 jbe 771f
 call gm_alloc
771:
 mov rax,r12
 mov r12,r11
.endm
# The first key of the node \node.
.macro mk_first node,out
 mov \out,[\node]
 bt \out,MTAG
 mov \out,[\node+8]
 jnc 772f
 mov \out,[\node+16]
772:
.endm
# RDI against RSI: EAX -1, 0 or 1. RDI holds no NaN (a key that does is
# never looked for: it equals nothing, mk_nan). A key that does, RSI, comes
# after every key that does not: such keys stand last in a leaf and in a
# tree, in the order they were put. Keeps every other register.
mk_cmp:
 cmp r8,48
 ja 3f
 cmp r8d,2
 je 1f
 cmp r8d,24
 je 2f
 cmp rdi,rsi
 mov eax,0
 setg al
 jge 9f
 mov eax,-1
9:
 ret
1:
 push rcx
 push rdx
 push rsi
 push rdi
 mov rax,[rdi]
 mov rdx,[rsi]
 mov rcx,rax
 cmp rcx,rdx
 cmova rcx,rdx
 add rdi,8
 add rsi,8
 test rcx,rcx
 jz 11f
 cld
 repe cmpsb
 je 11f
 pop rdi                           # the bytes differ: the flags are of RSI's less RDI's
 pop rsi
 pop rdx
 pop rcx
 mov eax,1
 jb 9b
 mov eax,-1
 ret
11:
 cmp rax,rdx                       # one starts the other: the shorter is first
 pop rdi
 pop rsi
 pop rdx
 pop rcx
 mov eax,0
 seta al
 jae 9b
 mov eax,-1
 ret
2:
 movq xmm0,rdi
 movq xmm1,rsi
 ucomisd xmm0,xmm1
 jp 21f
 mov eax,0
 seta al
 jae 9b
21:
 mov eax,-1
 ret
3:
 xchg rdi,rsi
 call mk_nan
 xchg rdi,rsi
 test eax,eax
 jz mk_ord
 mov eax,-1
 ret
# The order of two keys of a compound type that hold no NaN: EAX -1, 0
# (they are equal) or 1.
mk_ord:
 push rdx
 mov edx,1
 call mk_ask
 pop rdx
 ret
# EAX 1 when the key RDI holds a NaN: it is not equal to itself.
mk_nan:
 xor eax,eax
 cmp r8,48
 ja 1f
 cmp r8d,24
 jne 9f
 movq xmm0,rdi
 ucomisd xmm0,xmm0
 setp al
9:
 ret
1:
 push rsi
 push rdx
 mov rsi,rdi
 xor edx,edx
 call mk_ask
 pop rdx
 pop rsi
 test al,al
 mov eax,0
 setz al
 ret
# The comparator of a compound type (R8 twice its address, or twice that of
# a function value) asked about RDI and RSI: EDX 0 whether they are equal
# (AL), 1 their order (EAX). Keeps every other register.
mk_ask:
 push rbx
 push rcx
 push rdx
 push rsi
 push rdi
 push r8
 push r9
 push r10
 push r11
 mov r10,r8
 shr r10,1
.ifdef PIC
# Code is what stands less than 1 GiB and the head below the copy of the
# entry's words (spec/darwin-arm64.md); anything else a function value.
 lea rax,[0x400420]
 sub rax,r10
 cmp rax,0x40001000
 jae 6f
.else
 mov rax,r10
 shr rax,32
 jnz 6f
.endif
 call r10
 jmp 7f
6:
 call [r10]
7:
 pop r11
 pop r10
 pop r9
 pop r8
 pop rdi
 pop rsi
 pop rdx
 pop rcx
 pop rbx
 ret
# Among the RCX keys at RDI, 16 bytes apart and in order, the first that
# is not before RSI: its index in RAX (RCX when all are), and EDX 1 when
# it is RSI. Keeps RDI, RSI and R8. Keys of a compound type are compared
# by their order alone when the last of them holds no NaN (then none does).
mk_search:
 xor r9d,r9d
 mov r10,rcx
 test r8,r8
 jnz 7f
5:
 cmp r9,r10                        # keys that are words
 jae 6f
 lea r11,[r9+r10]
 shr r11,1
 mov rax,r11
 shl rax,4
 mov rax,[rdi+rax]
 lea rdx,[r11+1]
 cmp rax,rsi
 je 61f
 cmovl r9,rdx
 cmovg r10,r11
 jmp 5b
61:
 mov rax,r11
 mov edx,1
 ret
6:
 mov rax,r9
 xor edx,edx
 ret
7:
 push rbx
 lea rbx,[rip+mk_cmp]
 cmp r8,48
 jbe 1f
 test rcx,rcx
 jz 1f
 push rdi
 mov rax,rcx
 shl rax,4
 mov rdi,[rdi+rax-16]
 call mk_nan
 pop rdi
 test eax,eax
 jnz 1f
 lea rbx,[rip+mk_ord]
1:
 cmp r9,r10
 jae 3f
 lea r11,[r9+r10]
 shr r11,1
 push rdi
 push rsi
 mov rax,r11
 shl rax,4
 mov rax,[rdi+rax]
 mov rdi,rsi
 mov rsi,rax
 call rbx
 pop rsi
 pop rdi
 test eax,eax
 jz 2f
 js 4f
 lea r9,[r11+1]
 jmp 1b
4:
 mov r10,r11
 jmp 1b
2:
 mov rax,r11
 mov edx,1
 pop rbx
 ret
3:
 mov rax,r9
 xor edx,edx
 pop rbx
 ret
# The child of the branch RBX to look in for the key RSI: its index in RAX.
mk_child:
 lea rdi,[rbx+16]
 mov rcx,[rbx+8]
 call mk_search
 test edx,edx
 jnz 1f
 test rax,rax
 jz 1f
 dec rax
1:
 ret

# Map.get, Map.fetch and Map.has_key?: RDI the map, RSI the key, RDX what
# stands for a key that is not there, R9D 0 for the value or RDX, 1 for
# some(value) or none, 2 for true or false.
gm_map_get:
 push rbx
 push rdx
 push r9
 mov rbx,rdi
 xor edx,edx
 mov rdi,rsi
 call mk_nan
 test eax,eax
 jnz 21f
1:
 mov rax,[rbx]
 bt rax,MTAG
 jnc 2f
 call mk_child
 shl rax,4
 mov rbx,[rbx+rax+24]
 jmp 1b
2:
 lea rdi,[rbx+8]
 mov rcx,rax
 call mk_search
21:
 pop r9
 pop rcx
 test edx,edx
 jz 5f
 cmp r9d,2
 je 4f
 shl rax,4
 mov rax,[rbx+rax+16]
 test r9d,r9d
 jz 9f
 mov rdx,rax
 mov r11d,16
 mk_alloc
 mov qword ptr [rax],1
 mov [rax+8],rdx
 jmp 9f
4:
 mov eax,1
 jmp 9f
5:
 mov rax,rcx
 test r9d,r9d
 jz 9f
 xor eax,eax
9:
 pop rbx
 ret

# Map.put: RDI the map, RSI the key, RDX the value. While it runs RBX is
# its words on the stack: the key, the value, how keys compare, 1 once an
# entry was added, and the second of the two nodes a full one became.
gm_map_put:
 push rbx
 sub rsp,56
 mov rbx,rsp
 call mk_begin
 call mk_put
 mov rdx,[rbx+32]
 test rdx,rdx
 jz 9f
 push rax
 push rdx
 mov r11d,48
 mk_alloc
gm_map_root:
 pop rdx
 pop rcx
 mov rsi,[rcx]
 btr rsi,MTAG
 mov rdi,[rdx]
 btr rdi,MTAG
 add rsi,rdi
 bts rsi,MTAG
 mov [rax],rsi
 mov qword ptr [rax+8],2
 mk_first rcx,rsi
 mov [rax+16],rsi
 mov [rax+24],rcx
 mk_first rdx,rsi
 mov [rax+32],rsi
 mov [rax+40],rdx
9:
 add rsp,56
 pop rbx
 ret
# The words of a put at RBX from RSI the key, RDX the value and R8; RDI,
# the map, comes back as a node to put into: a leaf of more than LMAX
# entries as a tree, and one the compiler's own code made (up to LMAX
# entries) with the keys that hold a NaN last.
mk_begin:
 mov [rbx],rsi
 mov [rbx+8],rdx
 mov [rbx+16],r8
 mov qword ptr [rbx+24],0
 mov qword ptr [rbx+32],0
 push rdi
 mov rdi,rsi
 call mk_nan
 pop rdi
 mov [rbx+40],rax
 mov rax,[rdi]
 bt rax,MTAG
 jc 9f
 cmp rax,LMAX
 ja 1f
 call mk_canon
 mov rdi,rax
 ret
1:
 call mk_build
 mov rdi,rax
9:
 ret
# Where the key of the walk at RBX is, or goes, among the RCX entries of
# the leaf RDI: its index in RAX, and EDX 1 when it is there. A key that
# holds a NaN goes last.
mk_find:
 cmp qword ptr [rbx+40],0
 je 1f
 mov rax,rcx
 xor edx,edx
 ret
1:
 lea rdi,[rdi+8]
 mov rsi,[rbx]
 mov r8,[rbx+16]
 jmp mk_search
# The child of the branch RDI to go to for that key: its index in RAX.
mk_down:
 cmp qword ptr [rbx+40],0
 je 1f
 mov rax,[rdi+8]
 dec rax
 ret
1:
 push rbx
 mov rsi,[rbx]
 mov r8,[rbx+16]
 mov rbx,rdi
 call mk_child
 pop rbx
 ret
# The leaf RDI of up to LMAX entries, as the compiler's own code keeps one
# (a key that holds a NaN stays where it was put and stops the keys put
# after it from going past): RAX the same entries with the keys that hold
# no NaN in order and the others after them; RDI itself when no key holds
# one. Keeps RSI, RDX and R8.
mk_canon:
 mov rax,rdi
 test r8,-3
 jz 9f
 mov rcx,[rdi]
 test rcx,rcx
 jz 9f
 push rsi
 push rdi
 lea rsi,[rdi+8]
1:
 mov rdi,[rsi]
 call mk_nan
 test eax,eax
 jnz 2f
 add rsi,16
 dec rcx
 jnz 1b
 pop rax
 pop rsi
9:
 ret
2:
 pop rdi
 push rdx
 push rbp
 mov rbp,rsp
 sub rsp,32
 mov [rbp-8],rdi
 mov r11,[rdi]
 shl r11,4
 add r11,8
 mk_alloc
 mov [rbp-16],rax
 mov qword ptr [rbp-24],0          # entries written
 mov qword ptr [rbp-32],0          # 0: the keys without a NaN, 1: the others
3:
 mov rsi,[rbp-8]
 mov rcx,[rsi]
 add rsi,8
4:
 mov rdi,[rsi]
 call mk_nan
 cmp rax,[rbp-32]
 jne 7f
 mov r10,[rbp-16]
 mov r9,[rbp-24]
 test eax,eax
 jnz 6f
5:
 test r9,r9                        # down from the last one written while the key is before it
 jz 6f
 push rsi
 mov rax,r9
 shl rax,4
 mov rsi,[r10+rax-8]
 call mk_cmp
 pop rsi
 test eax,eax
 jns 6f
 mov rax,r9
 shl rax,4
 mov rdx,[r10+rax-8]
 mov [r10+rax+8],rdx
 mov rdx,[r10+rax]
 mov [r10+rax+16],rdx
 dec r9
 jmp 5b
6:
 mov rax,r9
 shl rax,4
 mov rdx,[rsi]
 mov [r10+rax+8],rdx
 mov rdx,[rsi+8]
 mov [r10+rax+16],rdx
 inc qword ptr [rbp-24]
7:
 add rsi,16
 dec rcx
 jnz 4b
 inc qword ptr [rbp-32]
 cmp qword ptr [rbp-32],1
 je 3b
 mov rax,[rbp-16]
 mov rcx,[rbp-24]
 mov [rax],rcx
 leave
 pop rdx
 pop rsi
 ret
# The node RDI with the entry put: RAX, and a second node in the word at
# RBX+32 when it no longer fitted in one.
mk_put:
 push rbp
 mov rbp,rsp
 sub rsp,48
 mov [rbp-8],rdi
 mov rax,[rdi]
 bt rax,MTAG
 jc mk_put_branch
 mov [rbp-32],rax
 mov rcx,rax
 call mk_find
 mov [rbp-16],rax
 test edx,edx
 jz 2f
 mov r11,[rbp-32]                  # the key is there: the leaf with the new value
 shl r11,4
 add r11,8
 mk_alloc
 mov rdi,rax
 mov rsi,[rbp-8]
 mov rcx,[rbp-32]
 lea rcx,[rcx*2+1]
 cld
 rep movsq
 mov rcx,[rbp-16]
 shl rcx,4
 mov rdx,[rbx+8]
 mov [rax+rcx+16],rdx
 mov rdx,[rbx]                     # and the key as it was given (0.0 for -0.0)
 mov [rax+rcx+8],rdx
 mov qword ptr [rbx+32],0
 leave
 ret
2:
 mov qword ptr [rbx+24],1          # the leaf with one entry more
 mov r11,[rbp-32]
 inc r11
 shl r11,4
 add r11,8
 mk_alloc
 mov rdx,[rbp-32]
 inc rdx
 mov [rax],rdx
 lea rdi,[rax+8]
 mov rsi,[rbp-8]
 add rsi,8
 mov rcx,[rbp-16]
 shl rcx,1
 cld
 rep movsq
 mov rdx,[rbx]
 mov [rdi],rdx
 mov rdx,[rbx+8]
 mov [rdi+8],rdx
 add rdi,16
 mov rcx,[rbp-32]
 sub rcx,[rbp-16]
 shl rcx,1
 rep movsq
 mov qword ptr [rbx+32],0
 cmp qword ptr [rax],LMAX
 jbe 9f
 mov rdi,rax
 call mk_halves
9:
 leave
 ret
mk_put_branch:
 btr rax,MTAG
 mov [rbp-40],rax
 mov rcx,[rdi+8]
 mov [rbp-32],rcx
 call mk_down
 mov [rbp-16],rax
 mov rdi,[rbp-8]
 shl rax,4
 mov rdi,[rdi+rax+24]
 call mk_put
 mov [rbp-24],rax
 mov rcx,[rbp-32]
 cmp qword ptr [rbx+32],0
 je 2f
 inc rcx
2:
 mov [rbp-48],rcx
 mov r11,rcx
 shl r11,4
 add r11,16
 mk_alloc
 mov rdx,[rbp-40]
 add rdx,[rbx+24]
 bts rdx,MTAG
 mov [rax],rdx
 mov rcx,[rbp-48]
 mov [rax+8],rcx
 lea rdi,[rax+16]
 mov rsi,[rbp-8]
 add rsi,16
 mov rcx,[rbp-16]
 inc rcx
 shl rcx,1
 cld
 rep movsq
 mov rdx,[rbp-24]
 mov [rdi-8],rdx
 push rax
 cmp qword ptr [rbx+40],0
 jne 3f
 push rdi
 push rsi
 mov rsi,[rdi-16]
 mov rdi,[rbx]
 mov r8,[rbx+16]
 call mk_cmp
 pop rsi
 pop rdi
 test eax,eax
 jns 3f
 mov rdx,[rbx]                     # a key below all that were there
 mov [rdi-16],rdx
3:
 pop rax
 mov rdx,[rbx+32]
 test rdx,rdx
 jz 4f
 mk_first rdx,rcx
 mov [rdi],rcx
 mov [rdi+8],rdx
 add rdi,16
4:
 mov rcx,[rbp-32]
 sub rcx,[rbp-16]
 dec rcx
 shl rcx,1
 rep movsq
 mov qword ptr [rbx+32],0
 cmp qword ptr [rax+8],BMAX
 jbe 9f
 mov rdi,rax
 call mk_halves
9:
 leave
 ret
# The node RDI, which holds one pair too many, as two: RAX the first half
# and the word at RBX+32 the second.
mk_halves:
 push rbp
 mov rbp,rsp
 sub rsp,48
 mov [rbp-8],rdi
 xor edx,edx
 mov rax,[rdi]
 bt rax,MTAG
 jnc 1f
 mov edx,8
 mov rax,[rdi+8]
1:
 mov [rbp-16],rdx                  # 8 for a branch: where its pairs start
 mov [rbp-24],rax                  # pairs
 shr rax,1
 mov [rbp-32],rax                  # pairs of the first half
 mov r11,rax
 shl r11,4
 add r11,8
 add r11,rdx
 mk_alloc
 mov [rbp-40],rax
 mov rcx,[rbp-32]
 mov rdx,[rbp-16]
 mov [rax+rdx],rcx
 lea rdi,[rax+rdx+8]
 mov rsi,[rbp-8]
 lea rsi,[rsi+rdx+8]
 shl rcx,1
 cld
 rep movsq
 mov [rbp-48],rsi
 mov r11,[rbp-24]
 sub r11,[rbp-32]
 shl r11,4
 add r11,8
 add r11,[rbp-16]
 mk_alloc
 mov rcx,[rbp-24]
 sub rcx,[rbp-32]
 mov rdx,[rbp-16]
 mov [rax+rdx],rcx
 lea rdi,[rax+rdx+8]
 mov rsi,[rbp-48]
 shl rcx,1
 cld
 rep movsq
 mov [rbx+32],rax
 cmp qword ptr [rbp-16],0
 je 2f
 mov rdi,rax
 call mk_total
 mov rdi,[rbp-40]
 call mk_total
2:
 mov rax,[rbp-40]
 leave
 ret
# The first word of the branch RDI from the counts of its children. Keeps
# RAX and RDI.
mk_total:
 mov rcx,[rdi+8]
 xor edx,edx
 lea rsi,[rdi+16]
1:
 test rcx,rcx
 jz 2f
 mov r9,[rsi+8]
 mov r9,[r9]
 btr r9,MTAG
 add rdx,r9
 add rsi,16
 dec rcx
 jmp 1b
2:
 bts rdx,MTAG
 mov [rdi],rdx
 ret
# The leaf RDI of more than 32 entries (one made at once: Map.new of keys
# in order, a map read from JSON or another node) as branches over leaves
# of 24: RAX.
mk_build:
 push rbp
 mov rbp,rsp
 sub rsp,64
 mov [rbp-56],rdi
 lea rax,[rdi+8]
 mov [rbp-8],rax
 mov rax,[rdi]
 mov [rbp-16],rax
 mov qword ptr [rbp-48],1          # 1 while the nodes made are leaves
1:
 mov rax,[rbp-16]
 add rax,23
 xor edx,edx
 mov ecx,24
 div rcx
 mov [rbp-64],rax                  # nodes of this level
 mov r11,rax
 shl r11,4
 mk_alloc
 mov [rbp-24],rax                  # their keys and addresses
 mov qword ptr [rbp-32],0
 mov rax,[rbp-16]
 mov [rbp-40],rax
2:
 cmp qword ptr [rbp-40],0
 je 5f
 mov rcx,[rbp-40]
 cmp rcx,24
 jbe 3f
 mov ecx,24
3:
 push rcx
 mov r11,rcx
 shl r11,4
 add r11,8
 cmp qword ptr [rbp-48],0
 jne 31f
 add r11,8
31:
 mk_alloc
 pop rcx
 cmp qword ptr [rbp-48],0
 je 32f
 mov [rax],rcx
 lea rdi,[rax+8]
 jmp 33f
32:
 mov [rax+8],rcx
 lea rdi,[rax+16]
33:
 mov rsi,[rbp-8]
 mov rdx,[rsi]
 push rcx
 shl rcx,1
 cld
 rep movsq
 mov [rbp-8],rsi
 pop rcx
 sub [rbp-40],rcx
 cmp qword ptr [rbp-48],0
 jne 34f
 push rdx
 mov rdi,rax
 call mk_total
 pop rdx
34:
 mov rcx,[rbp-32]
 shl rcx,4
 add rcx,[rbp-24]
 mov [rcx],rdx
 mov [rcx+8],rax
 inc qword ptr [rbp-32]
 jmp 2b
5:
 mov rax,[rbp-24]
 mov [rbp-8],rax
 mov [rbp-56],rax
 mov rax,[rbp-64]
 mov [rbp-16],rax
 mov qword ptr [rbp-48],0
 cmp rax,BMAX
 ja 1b
 mov r11,rax
 shl r11,4
 add r11,16
 mk_alloc
 mov rcx,[rbp-16]
 mov [rax+8],rcx
 lea rdi,[rax+16]
 mov rsi,[rbp-8]
 shl rcx,1
 cld
 rep movsq
 mov rdi,rax
 call mk_total
 leave
 ret

# Map.delete: RDI the map, RSI the key. A map without the key is given as
# it is.
gm_map_delete:
 push rbx
 sub rsp,56
 mov rbx,rsp
 mov [rbx],rsi
 mov [rbx+16],r8
 mov qword ptr [rbx+24],0
 mov qword ptr [rbx+40],0
 push rdi
 mov rdi,rsi
 call mk_nan
 pop rdi
 test eax,eax
 jz 11f
 mov rax,rdi                       # a key that holds a NaN is not there
 jmp 9f
11:
 mov rax,[rdi]
 bt rax,MTAG
 jc 1f
 cmp rax,LMAX
 jbe 1f
 call mk_build
 mov rdi,rax
1:
 push rdi
 call mk_del
 pop rdi
 cmp qword ptr [rbx+24],0
 jne 2f
 mov rax,rdi
 jmp 9f
2:
 test rax,rax
 jnz 3f
 mov r11d,8
 mk_alloc
 jmp 9f
3:
 mov rcx,[rax]
 bt rcx,MTAG
 jnc 9f
 btr rcx,MTAG
 cmp rcx,LMAX
 ja 9f
 mov rdi,rax                       # few are left: one leaf again
 call gm_map_flat
9:
 add rsp,56
 pop rbx
 ret
# The node RDI without the entry: RAX, 0 when nothing is left of it. The
# word at RBX+24 is 1 once the entry was found.
mk_del:
 push rbp
 mov rbp,rsp
 sub rsp,48
 mov [rbp-8],rdi
 mov rax,[rdi]
 bt rax,MTAG
 jc mk_del_branch
 mov [rbp-32],rax
 mov rcx,rax
 call mk_find
 test edx,edx
 jnz 1f
 mov rax,[rbp-8]
 leave
 ret
1:
 mov [rbp-16],rax
 mov qword ptr [rbx+24],1
 mov rcx,[rbp-32]
 dec rcx
 jnz 2f
 xor eax,eax
 leave
 ret
2:
 mov r11,rcx
 shl r11,4
 add r11,8
 mk_alloc
 mov rcx,[rbp-32]
 dec rcx
 mov [rax],rcx
 lea rdi,[rax+8]
 mov rsi,[rbp-8]
 add rsi,8
 mov rcx,[rbp-16]
 shl rcx,1
 cld
 rep movsq
 add rsi,16
 mov rcx,[rbp-32]
 sub rcx,[rbp-16]
 dec rcx
 shl rcx,1
 rep movsq
 leave
 ret
mk_del_branch:
 btr rax,MTAG
 mov [rbp-40],rax
 mov rcx,[rdi+8]
 mov [rbp-32],rcx
 call mk_down
 mov [rbp-16],rax
 mov rdi,[rbp-8]
 shl rax,4
 mov rdi,[rdi+rax+24]
 call mk_del
 cmp qword ptr [rbx+24],0
 jne 2f
 mov rax,[rbp-8]
 leave
 ret
2:
 mov [rbp-24],rax
 test rax,rax
 jnz 5f
 mov rcx,[rbp-32]                  # the child is gone
 dec rcx
 jnz 3f
 xor eax,eax
 leave
 ret
3:
 cmp rcx,1
 jne 4f
 mov rax,[rbp-8]                   # one child is left: it stands for the branch
 mov ecx,1
 sub rcx,[rbp-16]
 shl rcx,4
 mov rax,[rax+rcx+24]
 leave
 ret
4:
 mov [rbp-48],rcx
 mov r11,rcx
 shl r11,4
 add r11,16
 mk_alloc
 mov rcx,[rbp-48]
 mov [rax+8],rcx
 mov rdx,[rbp-40]
 dec rdx
 bts rdx,MTAG
 mov [rax],rdx
 lea rdi,[rax+16]
 mov rsi,[rbp-8]
 add rsi,16
 mov rcx,[rbp-16]
 shl rcx,1
 cld
 rep movsq
 add rsi,16
 mov rcx,[rbp-32]
 sub rcx,[rbp-16]
 dec rcx
 shl rcx,1
 rep movsq
 leave
 ret
5:
 mov r11,[rbp-32]                  # the child changed
 shl r11,4
 add r11,16
 mk_alloc
 mov rdi,rax
 mov rsi,[rbp-8]
 mov rcx,[rbp-32]
 lea rcx,[rcx*2+2]
 cld
 rep movsq
 mov rdx,[rbp-40]
 dec rdx
 bts rdx,MTAG
 mov [rax],rdx
 mov rcx,[rbp-16]
 shl rcx,4
 mov rdx,[rbp-24]
 mov [rax+rcx+24],rdx
 leave
 ret

# The entries of the node RDI in the order of their keys. RBX is the words
# of the walk: where the next goes, what goes there (0 the key, 1 the
# value, 2 a tuple of both as a list's element; 3 key and value side by
# side, as a leaf holds them) and, for a list, how many are still to come.
mk_walk:
 mov rax,[rdi]
 bt rax,MTAG
 jc 5f
 lea rsi,[rdi+8]
 mov rcx,rax
 test rcx,rcx
 jz 9f
1:
 mov rdx,[rbx+8]
 cmp edx,3
 jne 2f
 mov rdi,[rbx]
 mov rax,[rsi]
 mov [rdi],rax
 mov rax,[rsi+8]
 mov [rdi+8],rax
 add qword ptr [rbx],16
 jmp 4f
2:
 cmp edx,1
 ja 3f
 mov rax,[rsi+rdx*8]
 jmp 35f
3:
 push rsi
 push rcx
 mov r11d,24
 mk_alloc
 pop rcx
 pop rsi
 mov qword ptr [rax],2
 mov rdx,[rsi]
 mov [rax+8],rdx
 mov rdx,[rsi+8]
 mov [rax+16],rdx
35:
 mov rdi,[rbx]
 mov rdx,[rbx+16]
 mov [rdi],rdx
 mov [rdi+8],rax
 add qword ptr [rbx],16
 dec qword ptr [rbx+16]
4:
 add rsi,16
 dec rcx
 jnz 1b
9:
 ret
5:
 mov rcx,[rdi+8]
 lea rsi,[rdi+16]
6:
 push rsi
 push rcx
 mov rdi,[rsi+8]
 call mk_walk
 pop rcx
 pop rsi
 add rsi,16
 dec rcx
 jnz 6b
 ret
# Map.keys, Map.values and Map.to_list of a branch: RDI the map, R10D 0, 1
# or 2 for which.
gm_map_entries:
 push rbx
 sub rsp,40
 mov rbx,rsp
 mov rcx,[rdi]
 btr rcx,MTAG
 mov [rbx+16],rcx
 mov eax,r10d
 mov [rbx+8],rax
 mov qword ptr [rbx],0
 push rdi
 mov r11,rcx
 shl r11,4
 add r11,24
 mk_alloc
 pop rdi
 mov qword ptr [rax],-2
 add rax,16
 mov [rbx],rax
 push rax
 call mk_walk
 pop rax
 add rsp,40
 pop rbx
 ret
# The map RDI as one leaf: itself when it is one. Keeps every register but
# RAX.
gm_map_flat:
 mov rax,[rdi]
 bt rax,MTAG
 jc 1f
 mov rax,rdi
 ret
1:
 push rbx
 push rcx
 push rdx
 push rsi
 push rdi
 push r8
 push r9
 push r10
 push r11
 sub rsp,40
 mov rbx,rsp
 btr rax,MTAG
 mov qword ptr [rbx],0
 mov qword ptr [rbx+8],3
 push rdi
 push rax
 mov r11,rax
 shl r11,4
 add r11,8
 mk_alloc
 pop rcx
 pop rdi
 mov [rax],rcx
 lea rdx,[rax+8]
 mov [rbx],rdx
 push rax
 call mk_walk
 pop rax
 add rsp,40
 pop r11
 pop r10
 pop r9
 pop r8
 pop rdi
 pop rsi
 pop rdx
 pop rcx
 pop rbx
 ret
# Map.new of a list of more than 32 tuples, RDI. Keys that come in order,
# each after the one before, make one leaf at once; others are put one by
# one, so that a key that comes again keeps its last value.
gm_map_new:
 push rbx
 push rbp
 mov rbp,rsp
 sub rsp,32
 mov [rbp-8],rdi
 mov [rbp-16],r8
 mov rcx,[rdi]
 mov [rbp-24],rcx
 lea rsi,[rdi+8]
 dec rcx
 test r8,-3                        # a key of another kind may hold a NaN
 jnz 5f
1:
 test rcx,rcx
 jz 3f
 push rcx
 push rsi
 mov rdi,[rsi]
 mov rdi,[rdi+8]
 mov rsi,[rsi+16]
 mov rsi,[rsi+8]
 call mk_cmp
 pop rsi
 pop rcx
 cmp eax,-1
 jne 5f
 add rsi,16
 dec rcx
 jmp 1b
3:
 mov r11,[rbp-24]
 shl r11,4
 add r11,8
 mk_alloc
 mov rcx,[rbp-24]
 mov [rax],rcx
 lea rdi,[rax+8]
 mov rsi,[rbp-8]
 add rsi,8
4:
 mov rdx,[rsi]
 mov r9,[rdx+8]
 mov [rdi],r9
 mov r9,[rdx+16]
 mov [rdi+8],r9
 add rsi,16
 add rdi,16
 dec rcx
 jnz 4b
 jmp 9f
5:
 mov r11d,8
 mk_alloc
 mov [rbp-32],rax                  # the map so far
 add qword ptr [rbp-8],8
6:
 cmp qword ptr [rbp-24],0
 je 7f
 mov rdi,[rbp-32]
 mov rdx,[rbp-8]
 mov rdx,[rdx]
 mov rsi,[rdx+8]
 mov rdx,[rdx+16]
 mov r8,[rbp-16]
 call gm_map_oput                  # the map so far is nobody else's: it is changed where it is
 mov [rbp-32],rax
 add qword ptr [rbp-8],16
 dec qword ptr [rbp-24]
 jmp 6b
7:
 mov rdi,[rbp-32]
 call gm_map_done
9:
 leave
 pop rbx
 ret

# ---- Owned values ----
#
# A value is never changed once it is made, with two exceptions that no
# program can observe. A fold that puts into a map (Enum.reduce whose
# function gives back its accumulator with one entry put) and a loop that
# appends to a string (acc <> piece, handed on to the next turn) would copy
# for every turn what the turn before made and nothing else can reach. The
# compiler finds these (native-memory.alc, ow_) and asks for an owned put
# or an owned append instead. Such a value has its bit in M set, the marks
# of a collection, which are all zero between collections: the bit says
# that the value was made by an owned operation, has room, and has been
# given to nobody but the operation's result. An owned operation on a value
# with the bit changes it where it is; on one without it copies it into a
# value with room and sets the bit. gm_map_done and gm_str_done take the
# bits away again, where the result leaves the loop: from then on the value
# is as any other. A collection clears M before it marks, so nothing is
# owned after one (the next owned operation copies once more), and a bit
# that was left on a value nothing refers to any more (a fold ended by a
# raise) is gone before the memory is used again. A program that does not
# collect owns nothing: its owned operations are the plain ones.

# CF set when the value that starts at RDI is owned. Changes RAX and RCX.
mk_owned:
 mov rax,rdi
 sub rax,[r14-G+BASE]
 mov rcx,[r14-G+END]
 sub rcx,[r14-G+BASE]
 cmp rax,rcx
 jae 9f
 shr rax,3
 mov rcx,[r14-G+MMAP]
 bt [rcx],rax
9:
 ret
# The value that starts at RDI, in the arena, is owned from now on.
mk_mark:
 cmp qword ptr [r14-G+MODE],0
 je 9f
 mov rax,rdi
 sub rax,[r14-G+BASE]
 shr rax,3
 mov rcx,[r14-G+MMAP]
 bts [rcx],rax
 mov qword ptr [r14-G+OWNED],1
9:
 ret
# The node RDI as one that may be changed: itself when it is owned, else
# a copy with room for LMAX entries or BMAX children.
mk_own:
 call mk_owned
 jnc 1f
 mov rax,rdi
 ret
1:
 push rdi
 mov r11d,16+16*LMAX
 mk_alloc
 mov rdi,rax
 call mk_mark
 pop rsi
 mov rcx,[rsi]
 bt rcx,MTAG
 lea rcx,[rcx*2+1]
 jnc 2f
 mov rcx,[rsi+8]
 lea rcx,[rcx*2+2]
2:
 mov rax,rdi
 cld
 rep movsq
 ret

# Map.put where the map is the fold's own: RDI the map, RSI the key, RDX
# the value, R8 how keys compare. The nodes on the way to the entry are
# changed where they are once they are the fold's; a node that is full
# gives its upper half to a new one.
gm_map_oput:
 cmp qword ptr [r14-G+MODE],0
 je gm_map_put
 push rbx
 sub rsp,56
 mov rbx,rsp
 call mk_begin
 call mk_oput
 mov rdx,[rbx+32]
 test rdx,rdx
 jz 9f
 push rax
 push rdx
 mov r11d,16+16*BMAX
 mk_alloc
 mov rdi,rax
 call mk_mark
 mov rax,rdi
 jmp gm_map_root
9:
 add rsp,56
 pop rbx
 ret
mk_oput:
 push rbp
 mov rbp,rsp
 sub rsp,48
 call mk_own
 mov [rbp-8],rax
 mov rdi,rax
 mov rax,[rdi]
 bt rax,MTAG
 jc mk_oput_branch
 mov [rbp-32],rax
 mov rcx,rax
 call mk_find
 mov [rbp-16],rax
 mov qword ptr [rbx+32],0
 mov rdi,[rbp-8]
 test edx,edx
 jz 2f
 shl rax,4                         # the key is there: its value changes
 mov rdx,[rbx+8]
 mov [rdi+rax+16],rdx
 mov rax,rdi
 leave
 ret
2:
 mov qword ptr [rbx+24],1
 mov [rbp-24],rdi
 cmp qword ptr [rbp-32],LMAX
 jb 4f
 mov r11d,16+16*LMAX               # full: the upper half goes to a new leaf
 mk_alloc
 mov rdi,rax
 call mk_mark
 mov [rbx+32],rdi
 mov qword ptr [rdi],LMAX/2
 mov rsi,[rbp-8]
 mov qword ptr [rsi],LMAX/2
 lea rsi,[rsi+8+8*LMAX]
 add rdi,8
 mov ecx,LMAX
 cld
 rep movsq
 mov rdi,[rbp-8]
 lea rdi,[rdi+8+8*LMAX]
 mov ecx,LMAX
 xor eax,eax
 rep stosq
 mov qword ptr [rbp-32],LMAX/2
 mov rax,[rbp-16]
 cmp rax,LMAX/2
 jbe 4f
 sub rax,LMAX/2
 mov [rbp-16],rax
 mov rax,[rbx+32]
 mov [rbp-24],rax
4:
 mov rdi,[rbp-24]                  # the entries from the index on move up by one
 mov rcx,[rbp-32]
 mov rax,rcx
 shl rax,4
 lea rsi,[rdi+rax]
 lea rdi,[rsi+16]
 sub rcx,[rbp-16]
 shl rcx,1
 std
 rep movsq
 cld
 mov rdi,[rbp-24]
 mov rax,[rbp-16]
 shl rax,4
 mov rdx,[rbx]
 mov [rdi+rax+8],rdx
 mov rdx,[rbx+8]
 mov [rdi+rax+16],rdx
 inc qword ptr [rdi]
 mov rax,[rbp-8]
 leave
 ret
mk_oput_branch:
 mov rcx,[rdi+8]
 mov [rbp-32],rcx
 call mk_down
 mov [rbp-16],rax
 mov rdi,[rbp-8]
 shl rax,4
 mov rdi,[rdi+rax+24]
 call mk_oput
 mov rdi,[rbp-8]
 mov rcx,[rbp-16]
 shl rcx,4
 mov [rdi+rcx+24],rax
 cmp qword ptr [rbx+40],0
 jne 3f
 push rdi
 push rcx
 mov rsi,[rdi+rcx+16]
 mov rdi,[rbx]
 mov r8,[rbx+16]
 call mk_cmp
 pop rcx
 pop rdi
 test eax,eax
 jns 3f
 mov rdx,[rbx]                     # a key below all that were there
 mov [rdi+rcx+16],rdx
3:
 mov rax,[rbx+24]
 add [rdi],rax
 mov rdx,[rbx+32]
 test rdx,rdx
 jnz 4f
 mov rax,rdi
 leave
 ret
4:
 mov qword ptr [rbx+32],0          # the child became two: the second goes in after it
 mov [rbp-24],rdx
 inc qword ptr [rbp-16]
 mov qword ptr [rbp-40],0
 cmp qword ptr [rbp-32],BMAX
 jb 6f
 mov r11d,16+16*BMAX               # full: the upper half goes to a new branch
 mk_alloc
 mov rdi,rax
 call mk_mark
 mov [rbp-40],rdi
 mov qword ptr [rdi+8],BMAX/2
 mov rsi,[rbp-8]
 mov qword ptr [rsi+8],BMAX/2
 lea rsi,[rsi+16+8*BMAX]
 add rdi,16
 mov ecx,BMAX
 cld
 rep movsq
 mov rdi,[rbp-8]
 lea rdi,[rdi+16+8*BMAX]
 mov ecx,BMAX
 xor eax,eax
 rep stosq
 mov qword ptr [rbp-32],BMAX/2
 mov rdi,[rbp-8]
 mov rax,[rbp-16]
 cmp rax,BMAX/2
 jbe 6f
 sub rax,BMAX/2
 mov [rbp-16],rax
 mov rdi,[rbp-40]
6:
 mov r9,rdi                        # the branch the child goes into, at the index
 mov rcx,[rbp-32]
 mov rax,rcx
 shl rax,4
 lea rsi,[rdi+rax+8]
 lea rdi,[rsi+16]
 sub rcx,[rbp-16]
 shl rcx,1
 std
 rep movsq
 cld
 mov rax,[rbp-16]
 shl rax,4
 mov rdx,[rbp-24]
 mk_first rdx,rcx
 mov [r9+rax+16],rcx
 mov [r9+rax+24],rdx
 inc qword ptr [r9+8]
 mov rdi,[rbp-40]
 test rdi,rdi
 jz 7f
 call mk_total
 mov [rbx+32],rdi
 mov rdi,[rbp-8]
 call mk_total
7:
 mov rax,[rbp-8]
 leave
 ret
# RAX 1 when the map RDI is a fold's own (its first node is owned), else 0.
# Changes RCX.
gm_map_owned:
 call mk_owned
 mov eax,0
 setc al
 ret
# The map RDI as a fold's own: RAX, itself when it is one already, else its
# first node copied with room. Every other register is kept. The library's
# functions that put into the map they are given (Map.update, MapSet.put)
# then change it where it is (Map.o_keep).
gm_map_own:
 cmp qword ptr [r14-G+MODE],0
 jne 1f
 mov rax,rdi
 ret
1:
 push rcx
 push rsi
 push rdi
 push r11
 mov rax,[rdi]
 bt rax,MTAG
 jc 2f
 cmp rax,LMAX
 jbe 2f
 push rdx
 push r8
 push r9
 call mk_build
 pop r9
 pop r8
 pop rdx
 mov rdi,rax
2:
 call mk_own
 pop r11
 pop rdi
 pop rsi
 pop rcx
 ret
# The map RDI leaves the fold: its nodes are owned no longer. RAX the map;
# every other register is kept.
gm_map_done:
 push rcx
 push rsi
 push rdi
 call mk_free
 pop rax
 mov rdi,rax
 pop rsi
 pop rcx
 ret
mk_free:
 call mk_owned
 jnc 9f
 mov rax,rdi
 sub rax,[r14-G+BASE]
 shr rax,3
 mov rcx,[r14-G+MMAP]
 btr [rcx],rax
 mov rax,[rdi]
 bt rax,MTAG
 jnc 9f
 mov rcx,[rdi+8]
 lea rsi,[rdi+16]
1:
 push rsi
 push rcx
 mov rdi,[rsi+8]
 call mk_free
 pop rcx
 pop rsi
 add rsi,16
 dec rcx
 jnz 1b
9:
 ret

# left <> right where left is the loop's own: RDI and RSI the strings. An
# owned string is [room][length][bytes]: its address is that of its length,
# as of any string, and the value starts a word before, with the bytes it
# has room for. With room the bytes of the right string are written behind
# those of the left and the length grows; else both go into a new string
# with twice the room. Changes RAX, RCX, RDX, RSI, RDI, R8 and R11.
gm_str_append:
 mov rdx,[rsi]
 mov r8,[rdi]
 sub rdi,8
 call mk_owned
 lea rdi,[rdi+8]
 jnc 2f
 lea rax,[r8+rdx]
 cmp rax,[rdi-8]
 ja 2f
 mov [rdi],rax
 mov rax,rdi
 lea rdi,[rdi+r8+8]
 add rsi,8
 mov rcx,rdx
 jmp mk_bytes
2:
 lea r11,[r8+rdx]
 cmp qword ptr [r14-G+MODE],0
 je 3f
 add r11,r11
 cmp r11,64
 jae 3f
 mov r11d,64
3:
 add r11,7
 and r11,-8
 push r11
 add r11,16
 mk_alloc
 pop qword ptr [rax]
 lea rcx,[r8+rdx]
 mov [rax+8],rcx
 push rdi
 mov rdi,rax
 call mk_mark
 mov rax,rdi
 pop rdi
 push rax
 push rsi
 lea rsi,[rdi+8]
 lea rdi,[rax+16]
 mov rcx,r8
 call mk_bytes
 pop rsi
 add rsi,8
 mov rcx,rdx
 call mk_bytes
 pop rax
 add rax,8
 ret
# RCX bytes from RSI to RDI; RDI ends behind them. Keeps RAX and RDX.
mk_bytes:
 cmp rcx,16
 jae 2f
 test rcx,rcx
 jz 9f
1:
 mov r11b,[rsi]
 mov [rdi],r11b
 inc rsi
 inc rdi
 dec rcx
 jnz 1b
9:
 ret
2:
 cld
 rep movsb
 ret
# The string RDI leaves the loop: it is owned no longer. RAX the string;
# every other register is kept.
gm_str_done:
 push rcx
 push rdi
 sub rdi,8
 call mk_owned
 jnc 1f
 mov rax,rdi
 sub rax,[r14-G+BASE]
 shr rax,3
 mov rcx,[r14-G+MMAP]
 btr [rcx],rax
1:
 pop rax
 mov rdi,rax
 pop rcx
 ret
