# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# The float runtime, emitted once per program as an extra function-table entry
# when the source mentions floats. EAX selects the operation; a float is its
# IEEE-754 bits in a 64-bit register. R12/R13 are the arena cursor and end.
#
#   0  to_string: RDI float -> RAX string (shortest text, exponent form when
#      strictly shorter or the value is at least 2**53)
#   1  inspect: RDI float, its text appended at R12 (plain digits from 1 up
#      to 1.0e16, else as 0); called by the inspect routine
#   2  Float.parse and String.to_float: RDI string -> RAX float, RDX 0, or
#      RDX 1 when the text is no finite float (Go strconv.ParseFloat, then no
#      infinity and no NaN, so "inf" and "nan" are refused with the rest)
#   4  Float.round, 5 Float.floor, 6 Float.ceil: RDI float, RSI decimal
#      places -> RAX float, RDX 0, or RDX 1 for places outside 0..15
#   7  pow: RDI base, RSI exponent -> RAX (Go math.Pow)
#   8  Float.ratio: RDI float -> RAX numerator, RDX denominator, RCX 0; RCX 1
#      for infinity or NaN, 2 when the fraction leaves 64 bits
#   9  floor, 10 ceil, 11 trunc, 12 round (halves away from zero): RDI float
#      -> RAX float
#   13..16  the same four -> RAX integer, RDX 0, or RDX 1 when the result
#      leaves 64 bits
#
# Decimal conversion is Go 1.27's (internal/strconv/uscale.go, "unrounded
# scaling"): text is shortFloat and parsing parseFloat64 on the first 19
# digits, both one or two 64-bit products with a 128-bit power of ten of
# fl_pow10 (Go's pow10Tab). Text with more digits whose 19 and 19 plus one
# give different floats goes the exact way: up to 800 digits, the value as a
# ratio of integers of 4096 bits, divided bit by bit.
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
 cmp eax,1
 jb fl_to_string
 je fl_inspect
 cmp eax,2
 je fl_parse
 cmp eax,6
 jbe fl_round_to
 cmp eax,7
 je fl_pow
 cmp eax,8
 je fl_ratio
 cmp eax,12
 jbe fl_whole
 jmp fl_whole_int
fl_arena:
 mov edi,71
 mov eax,60
 syscall

# ---- integers of RCX words at RDI (and RSI); RDI, RSI and RCX are kept ----
# x *= RSI; the carry out in RDX.
bn_mul:
 xor r8d,r8d
 xor r9d,r9d
1:
 mov rax,[rdi+r8*8]
 mul rsi
 add rax,r9
 adc rdx,0
 mov [rdi+r8*8],rax
 mov r9,rdx
 inc r8
 cmp r8,rcx
 jb 1b
 mov rdx,r9
 ret
bn_add:
 xor r8d,r8d
 mov r9,rcx
 clc
1:
 mov rax,[rsi+r8*8]
 adc [rdi+r8*8],rax
 inc r8
 dec r9
 jnz 1b
 ret
bn_sub:
 xor r8d,r8d
 mov r9,rcx
 clc
1:
 mov rax,[rsi+r8*8]
 sbb [rdi+r8*8],rax
 inc r8
 dec r9
 jnz 1b
 ret
# Flags as an unsigned comparison of x with y.
bn_cmp:
 mov r8,rcx
1:
 dec r8
 mov rax,[rdi+r8*8]
 cmp rax,[rsi+r8*8]
 jne 2f
 test r8,r8
 jnz 1b
2:
 ret
bn_shl1:
 xor r8d,r8d
 mov r9,rcx
 clc
1:
 rcl qword ptr [rdi+r8*8],1
 inc r8
 dec r9
 jnz 1b
 ret
bn_copy:
 xor r8d,r8d
1:
 mov rax,[rsi+r8*8]
 mov [rdi+r8*8],rax
 inc r8
 cmp r8,rcx
 jb 1b
 ret
bn_zero:
 xor eax,eax
 xor r8d,r8d
1:
 mov [rdi+r8*8],rax
 inc r8
 cmp r8,rcx
 jb 1b
 ret
# x <<= RDX bits.
bn_shl:
 push rbx
 push rcx
 mov r10,rcx
 mov r8,rdx
 shr r8,6
 mov ecx,edx
 and ecx,63
 mov r9,r10
1:
 dec r9
 js 9f
 mov rax,r9
 sub rax,r8
 jl 3f
 mov rbx,[rdi+rax*8]
 xor r11d,r11d
 test rax,rax
 jz 2f
 mov r11,[rdi+rax*8-8]
2:
 shld rbx,r11,cl
 mov [rdi+r9*8],rbx
 jmp 1b
3:
 mov qword ptr [rdi+r9*8],0
 jmp 1b
9:
 pop rcx
 pop rbx
 ret
# The number of bits of x in RAX, 0 for zero.
bn_bitlen:
 mov r8,rcx
1:
 dec r8
 js 2f
 mov rax,[rdi+r8*8]
 test rax,rax
 jz 1b
 bsr rax,rax
 shl r8,6
 lea rax,[rax+r8+1]
 ret
2:
 xor eax,eax
 ret
# x = RAX << RDX.
bn_set:
 push rax
 push rdx
 call bn_zero
 pop rdx
 pop rax
 mov [rdi],rax
 jmp bn_shl
# x *= 10**RDX. RSI is not kept.
bn_pow10:
 push rbx
 mov rbx,rdx
1:
 cmp rbx,19
 jb 2f
 mov rsi,10000000000000000000
 call bn_mul
 sub rbx,19
 jmp 1b
2:
 test rbx,rbx
 jz 4f
 mov esi,1
3:
 lea rsi,[rsi+rsi*4]
 add rsi,rsi
 dec rbx
 jnz 3b
 call bn_mul
4:
 pop rbx
 ret

# ---- text ----
# The text of the float RDI at R8, its length in RAX. ESI 0 for to_string,
# 1 for inspect. Frame: R at RBP-144, S -288, M+ -432, M- -576, T -720 (18
# words each), the digits at -744, then the words named below.
fl_text:
 push rbp
 mov rbp,rsp
 sub rsp,880
 push rbx
 mov [rbp-752],r8              # cursor
 mov [rbp-872],r8              # start
 mov [rbp-760],rsi             # mode
 mov rax,rdi
 btr rax,63
 mov [rbp-800],rax             # magnitude bits
 mov rdx,0x7ff0000000000000
 cmp rax,rdx
 jb ft_finite
 ja ft_nan
 mov dword ptr [r8],0x666e492b # +Inf
 test rdi,rdi
 jns 1f
 mov byte ptr [r8],45
1:
 mov eax,4
 jmp ft_leave
ft_nan:
 mov dword ptr [r8],0x004e614e # NaN
 mov eax,3
 test esi,esi
 jz ft_leave
 mov word ptr [r8+3],0x302e    # inspect adds ".0", having found no point
 mov eax,5
 jmp ft_leave
ft_finite:
 test rdi,rdi
 jns 1f
 mov byte ptr [r8],45
 inc qword ptr [rbp-752]
1:
 test rax,rax
 jnz ft_digits
 mov byte ptr [rbp-744],48
 mov qword ptr [rbp-776],1     # digit count
 mov qword ptr [rbp-784],0     # decimal exponent
 jmp ft_layout
ft_digits:
# Go's shortFloat (internal/strconv/uscale.go): the shortest digits that
# read back as the value, by unrounded scaling with the 128-bit powers of
# ten of fl_pow10. RAX holds the bits of a finite value that is not zero.
 mov rdx,rax
 shr rdx,52
 mov r9,0xfffffffffffff
 and rax,r9
 test rdx,rdx
 jnz 1f
 mov edx,1
 jmp 2f
1:
 bts rax,52
2:
 bsr rcx,rax
 xor ecx,63
 shl rax,cl
 sub rdx,1075
 sub rdx,rcx
 mov r8,rax                    # m, its highest bit set
 mov r9,rdx                    # e: the value is m * 2**e
 mov ecx,11                    # z
 cmp r9,-1085
 jge 1f
 mov rcx,-1074
 sub rcx,r9
1:
 mov esi,1
 shl rsi,cl
 shr rsi,1                     # half the gap to a neighbour
 mov rdi,r8
 shr rdi,cl
 and edi,1                     # odd
 lea rax,[r9+rcx]
 mov r10,rsi
 mov rdx,0x8000000000000000
 cmp r8,rdx
 jne 2f
 cmp r9,-1085
 jle 2f
 shr r10,1                     # a power of two: the gap below is half the gap above
 imul rax,rax,631305
 sub rax,261663
 sar rax,21
 jmp 3f
2:
 imul rax,rax,78913
 sar rax,18
3:
 neg rax                       # p
 mov [rbp-808],rax
 mov [rbp-832],r8
 mov rdx,r8
 sub rdx,r10
 mov [rbp-816],rdx             # min
 add rsi,r8
 mov [rbp-824],rsi             # max
 imul rdx,rax,108853
 sar rdx,15
 add rdx,r9
 add rdx,3
 neg rdx
 mov rcx,rdx                   # s
 lea r11,[rip+fl_pow10]
 add rax,348
 shl rax,4
 mov rbx,[r11+rax]
 mov r11,[r11+rax+8]
 mov rax,[rbp-816]
 call fl_uscale
 lea r8,[rax+rdi+3]
 shr r8,2                      # dmin
 mov rax,[rbp-824]
 call fl_uscale
 sub rax,rdi
 shr rax,2                     # dmax
 mov rsi,rax
 mov r9,0xcccccccccccccccd
 mul r9
 shr rdx,3                     # dmax/10
 lea rax,[rdx+rdx*4]
 add rax,rax
 cmp rax,r8
 jb 4f
 mov rax,rdx
 mov r8d,1
 sub r8,[rbp-808]
 jmp 6f
4:
 mov rax,r8
 cmp r8,rsi
 jae 5f
 mov rax,[rbp-832]
 call fl_uscale
 mov rdx,rax
 shr rdx,2
 and edx,1
 lea rax,[rax+rdx+1]
 shr rax,2
5:
 mov r8,[rbp-808]
 neg r8
6:
# RAX is the digits as an integer and R8 the power of ten it is times.
 lea rsi,[rbp-721]
 xor ecx,ecx
 mov r9,0xcccccccccccccccd
1:
 mov r10,rax
 mul r9
 shr rdx,3
 lea rax,[rdx+rdx*4]
 add rax,rax
 sub r10,rax
 add r10b,48
 mov [rsi],r10b
 dec rsi
 inc rcx
 mov rax,rdx
 test rax,rax
 jnz 1b
 inc rsi
 lea rax,[r8+rcx-1]
 mov [rbp-784],rax
 lea rdi,[rbp-744]
 mov rdx,rcx
2:
 mov al,[rsi]
 mov [rdi],al
 inc rsi
 inc rdi
 dec rdx
 jnz 2b
3:
 cmp byte ptr [rbp-745+rcx],48
 jne 4f
 dec rcx
 jmp 3b
4:
 mov [rbp-776],rcx
 jmp ft_layout
# Go's uscale: RAX times 2**e times 10**p, unrounded: RBX and R11 are the
# power of ten's two words and CL the shift. Keeps RDI, R8 and RCX.
fl_uscale:
 mov rsi,rax
 mul rbx
 mov r9,rdx
 shr r9,cl
 mov r10,r9
 shl r10,cl
 cmp r10,rdx
 je 1f
 mov rax,r9
 or rax,1
 ret
1:
 mov r9,rdx
 mov r10,rax
 mov rax,rsi
 mul r11
 xor eax,eax
 cmp r10,rdx
 adc rax,0
 sub r9,rax
 sub r10,rdx
 shr r9,cl
 xor eax,eax
 cmp r10,1
 seta al
 or rax,r9
 ret
# Go's parseFloat64: the bits of the float nearest RDI * 10**RSI, for RDI
# not zero and RSI from -348 to 347; those of infinity when it is too large.
fl_scale:
 push rbx
 bsr rcx,rdi
 inc rcx                       # b
 imul r8,rsi,108853
 sar r8,15                     # lp
 mov r9d,53
 sub r9,rcx
 sub r9,r8
 mov eax,1074
 cmp r9,rax
 cmovg r9,rax                  # e
 mov r10d,61
 sub r10,r9
 sub r10,rcx
 sub r10,r8                    # s
 xor eax,eax
 cmp r10,64
 jge 3f
 mov rax,rdi
 neg ecx
 add ecx,64
 shl rax,cl
 mov rcx,r10
 lea rdx,[rip+fl_pow10]
 lea r8,[rsi+348]
 shl r8,4
 mov rbx,[rdx+r8]
 mov r11,[rdx+r8+8]
 mov rdi,r9
 call fl_uscale
 mov rdx,0x7ffffffffffffe
 xor ecx,ecx
 cmp rax,rdx
 setae cl
 mov rdx,rax
 and edx,1
 shr rax,cl
 or rax,rdx
 sub rdi,rcx
 mov rdx,rax
 shr rdx,2
 and edx,1
 lea rax,[rax+rdx+1]
 shr rax,2
 bt rax,52
 jnc 3f
 neg rdi
 cmp rdi,972
 jge 2f
 btr rax,52
 add rdi,1075
 shl rdi,52
 or rax,rdi
 jmp 3f
2:
 mov rax,0x7ff0000000000000
3:
 pop rbx
 ret
ft_layout:
 mov rbx,[rbp-752]
 mov rcx,[rbp-776]
 mov rdx,[rbp-784]
 lea rsi,[rbp-744]
 mov rax,[rbp-800]
 cmp qword ptr [rbp-760],1
 jne ft_rule
 test rax,rax
 jz ft_plain
 mov r8,0x3ff0000000000000
 cmp rax,r8
 jb ft_rule
 mov r8,0x4341c37937e08000     # 1.0e16
 cmp rax,r8
 jb ft_plain
ft_rule:
 lea r8,[rcx+1]                # the length in exponent form
 cmp rcx,1
 jne 1f
 mov r8d,3
1:
 mov r9,rdx
 test r9,r9
 jns 2f
 neg r9
 inc r8
2:
 add r8,2
 cmp r9,10
 jb 3f
 inc r8
 cmp r9,100
 jb 3f
 inc r8
3:
 test rdx,rdx                  # the length in plain form
 jns 4f
 mov r10,rcx
 sub r10,rdx
 inc r10
 jmp 6f
4:
 lea r10,[rdx+1]
 cmp rcx,r10
 ja 5f
 lea r10,[rdx+3]
 jmp 6f
5:
 lea r10,[rcx+1]
6:
 cmp r8,r10
 jb ft_exponent
 mov r8,0x4340000000000000     # 2**53
 cmp rax,r8
 jae ft_exponent
ft_plain:
 test rdx,rdx
 jns 3f
 mov word ptr [rbx],0x2e30
 add rbx,2
 not rdx
1:
 test rdx,rdx
 jz 2f
 mov byte ptr [rbx],48
 inc rbx
 dec rdx
 jmp 1b
2:
 mov r9,rcx
 call ft_copy
 jmp ft_end
3:
 lea r10,[rdx+1]
 cmp rcx,r10
 ja 6f
 mov r9,rcx
 call ft_copy
 sub r10,rcx
4:
 test r10,r10
 jz 5f
 mov byte ptr [rbx],48
 inc rbx
 dec r10
 jmp 4b
5:
 mov word ptr [rbx],0x302e
 add rbx,2
 jmp ft_end
6:
 mov r9,r10
 call ft_copy
 mov byte ptr [rbx],46
 inc rbx
 mov r9,rcx
 sub r9,r10
 call ft_copy
 jmp ft_end
ft_exponent:
 mov al,[rsi]
 mov [rbx],al
 mov byte ptr [rbx+1],46
 add rbx,2
 inc rsi
 mov r9,rcx
 dec r9
 jnz 1f
 mov byte ptr [rbx],48
 inc rbx
 jmp 2f
1:
 call ft_copy
2:
 mov byte ptr [rbx],101
 inc rbx
 mov rax,rdx
 test rax,rax
 jns 3f
 neg rax
 mov byte ptr [rbx],45
 inc rbx
3:
 cmp rax,100
 jb 4f
 xor edx,edx
 mov ecx,100
 div rcx
 add al,48
 mov [rbx],al
 inc rbx
 mov rax,rdx
 jmp 5f
4:
 cmp rax,10
 jb 6f
5:
 xor edx,edx
 mov ecx,10
 div rcx
 add al,48
 mov [rbx],al
 inc rbx
 mov rax,rdx
6:
 add al,48
 mov [rbx],al
 inc rbx
ft_end:
 mov rax,rbx
 sub rax,[rbp-872]
ft_leave:
 pop rbx
 mov rsp,rbp
 pop rbp
 ret
# R9 bytes from RSI to RBX, both left after them.
ft_copy:
 test r9,r9
 jz 2f
1:
 mov al,[rsi]
 mov [rbx],al
 inc rsi
 inc rbx
 dec r9
 jnz 1b
2:
 ret
fl_to_string:
 sub rsp,56
 mov r8,rsp
 xor esi,esi
 call fl_text
 lea rdx,[rax+15]
 and rdx,-8
 add rdx,r12
 gm_fit rdx
 mov rdi,r12
 mov r12,rdx
 mov [rdi],rax
 xor ecx,ecx
1:
 cmp rcx,rax
 jae 2f
 mov dl,[rsp+rcx]
 mov [rdi+rcx+8],dl
 inc rcx
 jmp 1b
2:
 mov rax,rdi
 add rsp,56
 ret
fl_inspect:
 sub rsp,56
 mov r8,rsp
 mov esi,1
 call fl_text
# The text inspect writes has to reach here, with the 8 bytes it keeps free:
# more room, as ins_more of spec/integer-parse-x86_64.s.
 lea rdx,[r12+rax+8]
 cmp rdx,r13
 jbe 3f
 push rax
 mov r11,rdx
 push r12
 mov r12,[r14-1536+224]
 call qword ptr [0x400458]
 mov [r14-1536+224],r12
 pop r12
 add r12,r11
 pop rax
3:
 xor ecx,ecx
1:
 cmp rcx,rax
 jae 2f
 mov dl,[rsp+rcx]
 mov [r12+rcx],dl
 inc rcx
 jmp 1b
2:
 add r12,rax
 add rsp,56
 ret

# ---- parsing ----
# Go's readFloat. Frame: the digits as an integer U at RBP-512 and the power
# of ten V at RBP-1024 (64 words each), then the words named below.
fl_parse:
 push rbp
 mov rbp,rsp
 sub rsp,1152
 push rbx
 mov rax,[rdi]
 mov [rbp-1104],rax            # length
 add rdi,8
 mov [rbp-1096],rdi            # text
 xor eax,eax
 mov [rbp-1040],rax            # 1 for a minus sign
 mov [rbp-1048],rax            # dp: where the point stands
 mov [rbp-1056],rax            # nd: digits after leading zeros
 mov [rbp-1064],rax            # 1 when a dropped digit was not zero
 mov [rbp-1072],rax            # saw a point
 mov [rbp-1080],rax            # saw a digit
 mov [rbp-1088],rax            # saw an underscore
 mov [rbp-1112],rax            # hexadecimal mantissa
 mov [rbp-1120],rax            # digits kept
 mov [rbp-1128],rax            # 1 for hexadecimal
 mov [rbp-1136],rax            # digits in the mantissa word, at most 19
 mov [rbp-1144],rax            # 1 when a digit past them was not zero
 cmp qword ptr [rbp-1104],0
 je fp_fail
fp_read:
 xor ebx,ebx                   # i
 mov r10,[rbp-1096]
 mov r11,[rbp-1104]
 movzx eax,byte ptr [r10]
 cmp al,43
 je 1f
 cmp al,45
 jne 2f
 mov qword ptr [rbp-1040],1
1:
 inc rbx
2:
 lea rax,[rbx+2]
 cmp rax,r11
 jae 3f
 cmp byte ptr [r10+rbx],48
 jne 3f
 movzx eax,byte ptr [r10+rbx+1]
 or al,32
 cmp al,120
 jne 3f
 mov qword ptr [rbp-1128],1
 add rbx,2
3:
 mov ecx,64
 lea rdi,[rbp-512]
 call bn_zero
fp_loop:
 mov r10,[rbp-1096]
 cmp rbx,[rbp-1104]
 jae fp_scanned
 movzx eax,byte ptr [r10+rbx]
 cmp al,95
 jne 1f
 mov qword ptr [rbp-1088],1
 jmp fp_continue
1:
 cmp al,46
 jne 2f
 cmp qword ptr [rbp-1072],0
 jne fp_scanned
 mov qword ptr [rbp-1072],1
 mov rdx,[rbp-1056]
 mov [rbp-1048],rdx
 jmp fp_continue
2:
 lea edx,[rax-48]
 cmp edx,9
 ja 5f
 mov qword ptr [rbp-1080],1
 test edx,edx
 jnz 3f
 cmp qword ptr [rbp-1056],0
 jne 3f
 dec qword ptr [rbp-1048]      # a leading zero
 jmp fp_continue
3:
 inc qword ptr [rbp-1056]
 cmp qword ptr [rbp-1128],0
 jne fp_hex_digit
 cmp qword ptr [rbp-1136],19
 jae 4f
 inc qword ptr [rbp-1136]
 mov rax,[rbp-1112]
 lea rax,[rax+rax*4]
 lea rax,[rdx+rax*2]
 mov [rbp-1112],rax
 jmp fp_continue
4:
 test edx,edx
 jz fp_continue
 mov qword ptr [rbp-1144],1
 jmp fp_continue
5:
 cmp qword ptr [rbp-1128],0
 je fp_scanned
 or al,32
 lea edx,[rax-97]
 cmp edx,5
 ja fp_scanned
 add edx,10
 mov qword ptr [rbp-1080],1
 inc qword ptr [rbp-1056]
fp_hex_digit:
 cmp qword ptr [rbp-1120],16
 jae 6f
 inc qword ptr [rbp-1120]
 mov rax,[rbp-1112]
 shl rax,4
 or rax,rdx
 mov [rbp-1112],rax
 jmp fp_continue
6:
 test edx,edx
 jz fp_continue
 mov qword ptr [rbp-1064],1
fp_continue:
 inc rbx
 jmp fp_loop
fp_scanned:
 cmp qword ptr [rbp-1080],0
 je fp_fail
 cmp qword ptr [rbp-1072],0
 jne 1f
 mov rax,[rbp-1056]
 mov [rbp-1048],rax
1:
 cmp qword ptr [rbp-1128],0
 je 2f
 shl qword ptr [rbp-1048],2
 shl qword ptr [rbp-1120],2
2:
 mov r10,[rbp-1096]
 mov r11,[rbp-1104]
 cmp rbx,r11
 jae fp_no_exponent
 movzx eax,byte ptr [r10+rbx]
 or al,32
 mov edx,101
 cmp qword ptr [rbp-1128],0
 je 3f
 mov edx,112
3:
 cmp al,dl
 jne fp_no_exponent
 inc rbx
 cmp rbx,r11
 jae fp_fail
 mov r8d,1
 movzx eax,byte ptr [r10+rbx]
 cmp al,43
 je 4f
 cmp al,45
 jne 5f
 mov r8,-1
4:
 inc rbx
5:
 cmp rbx,r11
 jae fp_fail
 movzx eax,byte ptr [r10+rbx]
 sub eax,48
 cmp eax,9
 ja fp_fail
 xor r9d,r9d
6:
 cmp rbx,r11
 jae 8f
 movzx eax,byte ptr [r10+rbx]
 cmp al,95
 jne 7f
 mov qword ptr [rbp-1088],1
 inc rbx
 jmp 6b
7:
 sub eax,48
 cmp eax,9
 ja 8f
 inc rbx
 cmp r9,10000
 jge 6b
 lea r9,[r9+r9*4]
 lea r9,[rax+r9*2]
 jmp 6b
8:
 imul r9,r8
 add [rbp-1048],r9
 jmp fp_whole_text
fp_no_exponent:
 cmp qword ptr [rbp-1128],0
 jne fp_fail
fp_whole_text:
 cmp rbx,r11
 jne fp_fail
 cmp qword ptr [rbp-1088],0
 je 1f
 call fl_underscores
 test eax,eax
 jz fp_fail
1:
 cmp qword ptr [rbp-1128],0
 je fp_decimal
 mov rdi,[rbp-1112]
 test rdi,rdi
 jz fp_zero
 mov rsi,[rbp-1048]
 sub rsi,[rbp-1120]
 mov rdx,[rbp-1064]
 call fl_pack
 jmp fp_have
fp_decimal:
 cmp qword ptr [rbp-1136],0
 je fp_zero
 mov rax,[rbp-1048]
 cmp rax,310
 jg fp_fail
 cmp rax,-330
 jl fp_zero
# As Go's atof64: the first 19 digits and the power of ten by unrounded
# scaling; when digits were dropped, the result stands if the digits plus
# one give the same float. Otherwise the exact way below.
 sub rax,[rbp-1136]
 cmp rax,-345
 jl fp_zero
 mov rsi,rax
 mov rdi,[rbp-1112]
 call fl_scale
 cmp qword ptr [rbp-1144],0
 je fp_have
 push rax
 mov rsi,[rbp-1048]
 sub rsi,[rbp-1136]
 mov rdi,[rbp-1112]
 inc rdi
 call fl_scale
 pop rdx
 cmp rax,rdx
 je fp_have
# The digits again, up to 800 of them, as the integer U.
 mov r10,[rbp-1096]
 xor ebx,ebx
 movzx eax,byte ptr [r10]
 cmp al,43
 je 1f
 cmp al,45
 jne 2f
1:
 inc rbx
2:
 mov r10,[rbp-1096]
 cmp rbx,[rbp-1104]
 jae 9f
 movzx eax,byte ptr [r10+rbx]
 inc rbx
 cmp al,95
 je 2b
 cmp al,46
 je 2b
 lea edx,[rax-48]
 cmp edx,9
 ja 9f
 test edx,edx
 jnz 3f
 cmp qword ptr [rbp-1120],0
 je 2b
3:
 cmp qword ptr [rbp-1120],800
 jae 4f
 inc qword ptr [rbp-1120]
 push rdx
 mov ecx,64
 lea rdi,[rbp-512]
 mov esi,10
 call bn_mul
 pop rdx
 add [rbp-512],rdx
 jnc 2b
 lea rdi,[rbp-504]
8:
 add qword ptr [rdi],1
 lea rdi,[rdi+8]
 jc 8b
 jmp 2b
4:
 test edx,edx
 jz 2b
 mov qword ptr [rbp-1064],1
 jmp 2b
9:
 mov rax,[rbp-1048]
 sub rax,[rbp-1120]
 mov [rbp-1048],rax            # the value is U * 10**this
 mov ecx,64
 lea rdi,[rbp-1024]
 mov eax,1
 xor edx,edx
 call bn_set
 mov rdx,[rbp-1048]
 test rdx,rdx
 jz 2f
 js 1f
 lea rdi,[rbp-512]
 call bn_pow10
 jmp 2f
1:
 neg rdx
 lea rdi,[rbp-1024]
 call bn_pow10
2:
 lea rdi,[rbp-512]
 lea rsi,[rbp-1024]
 mov rdx,[rbp-1064]
 call fl_div
fp_have:
 mov rdx,0x7ff0000000000000
 cmp rax,rdx
 je fp_fail
 jmp 1f
fp_zero:
 xor eax,eax
1:
 mov rdx,[rbp-1040]
 shl rdx,63
 or rax,rdx
 xor edx,edx
 jmp fp_leave
fp_fail:
 xor eax,eax
 mov edx,1
fp_leave:
 pop rbx
 mov rsp,rbp
 pop rbp
 ret
# Go's underscoreOK for the R11 bytes at R10: EAX 1 when every underscore
# stands between digits, or between a base prefix and a digit.
fl_underscores:
 mov rsi,r10
 mov rcx,r11
 mov r8d,94
 xor r9d,r9d
 xor edx,edx
 test rcx,rcx
 jz 7f
 movzx eax,byte ptr [rsi]
 cmp al,43
 je 1f
 cmp al,45
 jne 2f
1:
 inc rsi
 dec rcx
2:
 cmp rcx,2
 jb 4f
 cmp byte ptr [rsi],48
 jne 4f
 movzx eax,byte ptr [rsi+1]
 or al,32
 cmp al,98
 je 3f
 cmp al,111
 je 3f
 cmp al,120
 jne 4f
 mov r9d,1
3:
 mov edx,2
 mov r8d,48
4:
 cmp rdx,rcx
 jae 7f
 movzx eax,byte ptr [rsi+rdx]
 inc rdx
 lea r10d,[rax-48]
 cmp r10d,9
 jbe 6f
 test r9d,r9d
 jz 5f
 mov r10d,eax
 or r10d,32
 sub r10d,97
 cmp r10d,5
 jbe 6f
5:
 cmp al,95
 jne 8f
 cmp r8d,48
 jne 9f
 mov r8d,95
 jmp 4b
8:
 cmp r8d,95
 je 9f
 mov r8d,33
 jmp 4b
6:
 mov r8d,48
 jmp 4b
7:
 cmp r8d,95
 je 9f
 mov eax,1
 ret
9:
 xor eax,eax
 ret
# The float nearest U/V (integers of RCX words at RDI and RSI, neither zero),
# RDX 1 when U stands for a little more; its bits in RAX, those of infinity
# when it is too large. U and V are not kept.
fl_div:
 push rbp
 mov rbp,rsp
 sub rsp,48
 push rbx
 mov [rbp-8],rdi
 mov [rbp-16],rsi
 mov [rbp-24],rdx
 call bn_bitlen
 mov [rbp-32],rax
 mov rdi,[rbp-16]
 call bn_bitlen
 mov rdx,[rbp-32]
 sub rdx,rax
 mov [rbp-40],rdx              # the binary exponent of the quotient
 jl 1f
 call bn_shl
 jmp 2f
1:
 neg rdx
 mov rdi,[rbp-8]
 call bn_shl
2:
 mov rdi,[rbp-8]
 mov rsi,[rbp-16]
 call bn_cmp
 jae 3f
 call bn_shl1
 dec qword ptr [rbp-40]
3:
 xor ebx,ebx
 mov qword ptr [rbp-48],64
4:
 add rbx,rbx
 call bn_cmp
 jb 5f
 call bn_sub
 or rbx,1
5:
 call bn_shl1
 dec qword ptr [rbp-48]
 jnz 4b
 call bn_bitlen
 test rax,rax
 setnz al
 movzx edx,al
 or rdx,[rbp-24]
 mov rdi,rbx
 mov rsi,[rbp-40]
 sub rsi,63
 pop rbx
 mov rsp,rbp
 pop rbp
# The float nearest RDI * 2**RSI (RDI not zero), RDX 1 when RDI stands for a
# little more: halves go to the even neighbour.
fl_pack:
 bsr rcx,rdi
 xor rcx,63
 shl rdi,cl
 sub rsi,rcx
 add rsi,63                    # the value is 1.x * 2**this
 cmp rsi,1023
 jg 9f
 mov ecx,11
 cmp rsi,-1022
 jge 1f
 mov rcx,-1011
 sub rcx,rsi                   # a subnormal keeps fewer bits
 mov rsi,-1022
 cmp rcx,64
 jb 1f
 ja 8f
 xor r8d,r8d
 mov r10d,1
 mov r11,rdi
 add r11,r11
 jmp 2f
1:
 mov r8,rdi
 shr r8,cl
 dec ecx
 mov r10,rdi
 shr r10,cl
 and r10d,1
 mov r11d,1
 shl r11,cl
 dec r11
 and r11,rdi
2:
 test r10d,r10d
 jz 4f
 test r11,r11
 jnz 3f
 test rdx,rdx
 jnz 3f
 test r8b,1
 jz 4f
3:
 inc r8
4:
 lea rax,[rsi+1022]
 shl rax,52
 add rax,r8
 mov rdx,0x7ff0000000000000
 cmp rax,rdx
 jae 9f
 ret
8:
 xor eax,eax
 ret
9:
 mov rax,0x7ff0000000000000
 ret

# ---- whole numbers ----
# XMM0 to a whole number: ECX 0 down, 1 up, 2 toward zero, 3 to the nearest
# with halves away from zero. A zero result keeps the sign.
fl_fint:
 movq rax,xmm0
 mov rdx,rax
 btr rax,63
 mov r11,0x4330000000000000
 cmp rax,r11
 jae 9f
 cvttsd2si rax,xmm0
 cvtsi2sd xmm15,rax
 cmp ecx,1
 jb 1f
 je 2f
 cmp ecx,3
 jne 8f
 movapd xmm14,xmm0
 subsd xmm14,xmm15
 movq rax,xmm14
 btr rax,63
 mov r11,0x3fe0000000000000
 cmp rax,r11
 jb 8f
 mov rax,0x3ff0000000000000
 mov r11,rdx
 shr r11,63
 shl r11,63
 or rax,r11
 movq xmm14,rax
 addsd xmm15,xmm14
 jmp 8f
1:
 ucomisd xmm15,xmm0
 jbe 8f
 subsd xmm15,[rip+fl_one]
 jmp 8f
2:
 ucomisd xmm0,xmm15
 jbe 8f
 addsd xmm15,[rip+fl_one]
8:
 movq rax,xmm15
 btr rax,63
 shr rdx,63
 shl rdx,63
 or rax,rdx
 movq xmm0,rax
9:
 ret
fl_whole:
 lea ecx,[rax-9]
 movq xmm0,rdi
 call fl_fint
 movq rax,xmm0
 ret
fl_whole_int:
 lea ecx,[rax-13]
 movq xmm0,rdi
 call fl_fint
 ucomisd xmm0,[rip+fl_low]
 jb 1f
 ucomisd xmm0,[rip+fl_two63]
 jae 1f
 cvttsd2si rax,xmm0
 xor edx,edx
 ret
1:
 xor eax,eax
 mov edx,1
 ret

# ---- rounding at decimal places ----
fl_round_to:
 cmp rsi,15
 ja fr_bad
 mov r8d,1
 test rsi,rsi
 jz 2f
1:
 lea r8,[r8+r8*4]
 add r8,r8
 dec rsi
 jnz 1b
2:
 mov rcx,rdi
 btr rcx,63
 mov rdx,0x7ff0000000000000
 cmp rcx,rdx
 jae fr_same
 mov esi,eax                   # 4 nearest, 5 down, 6 up
 movq xmm0,rdi
 cvtsi2sd xmm1,r8
 movapd xmm2,xmm0
 mulsd xmm2,xmm1               # the product, rounded
 movq r9,xmm2
 btr r9,63
 mov rdx,0x4330000000000000
 cmp r9,rdx
 jae fr_exact
 # XMM7: the exact product less the rounded one (Dekker).
 movsd xmm9,[rip+fl_split]
 movapd xmm3,xmm0
 mulsd xmm3,xmm9
 movapd xmm4,xmm3
 subsd xmm4,xmm0
 subsd xmm3,xmm4
 movapd xmm4,xmm0
 subsd xmm4,xmm3
 movapd xmm5,xmm1
 mulsd xmm5,xmm9
 movapd xmm6,xmm5
 subsd xmm6,xmm1
 subsd xmm5,xmm6
 movapd xmm6,xmm1
 subsd xmm6,xmm5
 movapd xmm7,xmm3
 mulsd xmm7,xmm5
 subsd xmm7,xmm2
 movapd xmm8,xmm3
 mulsd xmm8,xmm6
 addsd xmm7,xmm8
 movapd xmm8,xmm4
 mulsd xmm8,xmm5
 addsd xmm7,xmm8
 mulsd xmm4,xmm6
 addsd xmm7,xmm4
 xorpd xmm10,xmm10
 movapd xmm0,xmm2
 cmp esi,5
 je fr_down
 ja fr_up
 mov ecx,2
 call fl_fint
 movapd xmm3,xmm2
 subsd xmm3,xmm0
 ucomisd xmm3,[rip+fl_half]
 ja 1f
 jne 2f
 ucomisd xmm7,xmm10
 jae 1f
 jmp fr_divide
1:
 addsd xmm0,[rip+fl_one]
 jmp fr_divide
2:
 ucomisd xmm3,[rip+fl_minus_half]
 jb 3f
 jne fr_divide
 ucomisd xmm7,xmm10
 ja fr_divide
3:
 subsd xmm0,[rip+fl_one]
 jmp fr_divide
fr_down:
 xor ecx,ecx
 call fl_fint
 ucomisd xmm0,xmm2
 jne fr_divide
 ucomisd xmm7,xmm10
 jae fr_divide
 subsd xmm0,[rip+fl_one]
 jmp fr_divide
fr_up:
 mov ecx,1
 call fl_fint
 ucomisd xmm0,xmm2
 jne fr_divide
 ucomisd xmm7,xmm10
 jbe fr_divide
 addsd xmm0,[rip+fl_one]
fr_divide:
 divsd xmm0,xmm1
 movq rax,xmm0
 xor edx,edx
 ret
fr_same:
 mov rax,rdi
 xor edx,edx
 ret
fr_bad:
 xor eax,eax
 mov edx,1
 ret
# The product is too large to be exact as a float: the same with integers.
fr_exact:
 mov rcx,rdi
 btr rcx,63
 mov r10,rcx
 shr r10,52
 mov r9,0xfffffffffffff
 and rcx,r9
 bts rcx,52
 sub r10,1075
 jge fr_same                   # a whole number already
 neg r10
 mov rax,rcx
 mul r8
 mov r9,rax
 mov ecx,r10d
 shrd rax,rdx,cl
 shr rdx,cl
 mov r11d,1
 shl r11,cl
 dec r11
 and r11,r9                    # what the shift dropped
 cmp esi,5
 je 1f
 ja 2f
 dec ecx
 bt r11,rcx
 jc 4f
 jmp 5f
1:
 test rdi,rdi
 jns 5f
 jmp 3f
2:
 test rdi,rdi
 js 5f
3:
 test r11,r11
 jz 5f
4:
 add rax,1
 adc rdx,0
5:
 sub rsp,64
 mov [rsp],rax
 mov [rsp+8],rdx
 xor eax,eax
 mov [rsp+16],rax
 mov [rsp+24],rax
 mov [rsp+32],r8
 mov [rsp+40],rax
 mov [rsp+48],rax
 mov [rsp+56],rax
 push rdi
 lea rdi,[rsp+8]
 lea rsi,[rsp+40]
 mov ecx,4
 xor edx,edx
 call fl_div
 pop rdi
 add rsp,64
 shr rdi,63
 shl rdi,63
 or rax,rdi
 xor edx,edx
 ret

# ---- Float.ratio ----
fl_ratio:
 mov rax,rdi
 btr rax,63
 mov r8,0x7ff0000000000000
 cmp rax,r8
 jae 7f
 test rax,rax
 jnz 1f
 mov edx,1
 xor ecx,ecx
 ret
1:
 mov rcx,rax
 shr rcx,52
 mov r9,0xfffffffffffff
 and rax,r9
 test rcx,rcx
 jnz 2f
 mov ecx,1
 jmp 3f
2:
 bts rax,52
3:
 sub rcx,1075
 bsf r9,rax
 xchg rcx,r9
 shr rax,cl
 add rcx,r9                    # the value is RAX * 2**RCX, RAX odd
 test rcx,rcx
 jl 5f
 bsr r9,rax
 add r9,rcx
 cmp r9,63
 ja 8f
 jb 4f
 test rdi,rdi
 jns 8f
 cmp rax,1
 jne 8f
4:
 shl rax,cl
 mov edx,1
 jmp 6f
5:
 neg rcx
 cmp rcx,62
 ja 8f
 mov edx,1
 shl rdx,cl
6:
 test rdi,rdi
 jns 9f
 neg rax
9:
 xor ecx,ecx
 ret
7:
 mov ecx,1
 ret
8:
 mov ecx,2
 ret

# ---- power: Go's math.Pow, with its Exp and Log for amd64 ----
fl_pow:
 movq xmm0,rdi
 movq xmm1,rsi
fp_again:
 xorpd xmm7,xmm7
 movsd xmm6,[rip+fl_one]
 ucomisd xmm1,xmm7
 jne 1f
 jnp fp_one
1:
 ucomisd xmm0,xmm6
 jne 2f
 jnp fp_one
2:
 ucomisd xmm1,xmm6
 jne 3f
 jnp fp_x
3:
 ucomisd xmm0,xmm0
 jp fp_nan
 ucomisd xmm1,xmm1
 jp fp_nan
 ucomisd xmm0,xmm7
 jne fp_y_infinite
 movq rax,xmm0                 # a zero to a power
 ucomisd xmm1,xmm7
 ja 4f
 test rax,rax
 jns fp_inf
 call fp_odd
 jz fp_inf
 mov rax,0xfff0000000000000
 ret
4:
 test rax,rax
 jns fp_zero_result
 call fp_odd
 jz fp_zero_result
 jmp fp_x
fp_y_infinite:
 movq rax,xmm1
 mov rdx,rax
 btr rdx,63
 mov rcx,0x7ff0000000000000
 cmp rdx,rcx
 jne fp_x_infinite
 ucomisd xmm0,[rip+fl_minus_one]
 je fp_one
 movq rdx,xmm0
 btr rdx,63
 mov r8,0x3ff0000000000000
 cmp rdx,r8
 setb dl
 test rax,rax
 setns cl
 cmp dl,cl
 je fp_zero_result
 jmp fp_inf
fp_x_infinite:
 movq rax,xmm0
 mov rdx,rax
 btr rdx,63
 cmp rdx,rcx
 jne fp_half
 test rax,rax
 jns 1f
 mov rax,0x8000000000000000    # minus infinity: the power of -0 to -y
 movq xmm0,rax
 movq rdx,xmm1
 btc rdx,63
 movq xmm1,rdx
 jmp fp_again
1:
 ucomisd xmm1,xmm7
 jb fp_zero_result
 jmp fp_inf
fp_half:
 ucomisd xmm1,[rip+fl_half]
 jne 1f
 sqrtsd xmm0,xmm0
 jmp fp_x
1:
 ucomisd xmm1,[rip+fl_minus_half]
 jne fp_general
 sqrtsd xmm0,xmm0
 movapd xmm2,xmm6
 divsd xmm2,xmm0
 movq rax,xmm2
 ret
fp_one:
 mov rax,0x3ff0000000000000
 ret
fp_x:
 movq rax,xmm0
 ret
fp_nan:
 mov rax,0x7ff8000000000001
 ret
fp_inf:
 mov rax,0x7ff0000000000000
 ret
fp_zero_result:
 xor eax,eax
 ret
# ZF clear when XMM1 is an odd whole number.
fp_odd:
 movq rdx,xmm1
 btr rdx,63
 mov rcx,0x4340000000000000
 cmp rdx,rcx
 jae 1f
 cvttsd2si rdx,xmm1
 cvtsi2sd xmm2,rdx
 ucomisd xmm2,xmm1
 jne 1f
 test dl,1
 ret
1:
 xor edx,edx
 ret
# The stack holds x, y, the whole part of |y| and its fraction.
fp_general:
 sub rsp,40
 movsd [rsp],xmm0
 movsd [rsp+8],xmm1
 movq rax,xmm1
 btr rax,63
 movq xmm0,rax
 movapd xmm2,xmm0
 mov ecx,2
 call fl_fint
 subsd xmm2,xmm0
 movsd [rsp+16],xmm0
 movsd [rsp+24],xmm2
 xorpd xmm7,xmm7
 movsd xmm3,[rsp]
 ucomisd xmm2,xmm7
 je 1f
 ucomisd xmm7,xmm3
 jbe 1f
 add rsp,40
 jmp fp_nan
1:
 ucomisd xmm0,[rip+fl_two63]
 jb 3f
 add rsp,40                    # a whole exponent too large to count
 ucomisd xmm3,[rip+fl_minus_one]
 je fp_one
 movq rdx,xmm3
 btr rdx,63
 mov r8,0x3ff0000000000000
 cmp rdx,r8
 setb dl
 ucomisd xmm1,xmm7
 seta cl
 cmp dl,cl
 je fp_zero_result
 jmp fp_inf
3:
 movsd xmm4,[rip+fl_one]       # the answer is XMM4 * 2**R8
 ucomisd xmm2,xmm7
 je 5f
 ucomisd xmm2,[rip+fl_half]
 jbe 4f
 subsd xmm2,[rip+fl_one]
 addsd xmm0,[rip+fl_one]
 movsd [rsp+16],xmm0
 movsd [rsp+24],xmm2
4:
 movsd xmm0,[rsp]
 call fl_log
 mulsd xmm0,[rsp+24]
 call fl_exp
 movapd xmm4,xmm0
5:
 xor r8d,r8d
 mov rax,[rsp]                 # frexp: x is XMM5 * 2**R9
 xor r9d,r9d
 mov rdx,rax
 btr rdx,63
 mov rcx,0x0010000000000000
 cmp rdx,rcx
 jae 6f
 movq xmm5,rax
 mulsd xmm5,[rip+fl_two52]
 movq rax,xmm5
 mov r9,-52
6:
 mov rdx,rax
 shr rdx,52
 and edx,0x7ff
 lea r9,[r9+rdx-1022]
 mov rcx,0x800fffffffffffff
 and rax,rcx
 mov rcx,0x3fe0000000000000
 or rax,rcx
 movq xmm5,rax
 cvttsd2si r10,[rsp+16]
7:
 test r10,r10
 jz 11f
 cmp r9,-4096
 jl 10f
 cmp r9,4096
 jg 10f
 test r10b,1
 jz 8f
 mulsd xmm4,xmm5
 add r8,r9
8:
.ifdef ARM
 movapd xmm6,xmm5
.endif
 mulsd xmm5,xmm5
 shl r9,1
 ucomisd xmm5,[rip+fl_half]
 jae 9f
.ifdef ARM
# Go's compiler on ARM64 makes x1 *= x1; x1 += x1 one fused step.
 vfmadd231sd xmm5,xmm6,xmm6
.else
 addsd xmm5,xmm5
.endif
 dec r9
9:
 sar r10,1
 jmp 7b
10:
 add r8,r9
11:
 xorpd xmm7,xmm7
 ucomisd xmm7,[rsp+8]
 jbe 12f
 movsd xmm0,[rip+fl_one]
 divsd xmm0,xmm4
 movapd xmm4,xmm0
 neg r8
12:
 add rsp,40
 movq rax,xmm4                 # ldexp
 mov rdx,rax
 btr rdx,63
 test rdx,rdx
 jz 16f
 mov rcx,0x7ff0000000000000
 cmp rdx,rcx
 jae 16f
 mov rcx,0x0010000000000000
 cmp rdx,rcx
 jae 13f
 mulsd xmm4,[rip+fl_two52]
 movq rax,xmm4
 sub r8,52
13:
 mov rdx,rax
 shr rdx,52
 and edx,0x7ff
 lea r8,[r8+rdx-1023]
 cmp r8,-1075
 jge 14f
 shr rax,63
 shl rax,63
 ret
14:
 cmp r8,1023
 jle 15f
 shr rax,63
 shl rax,63
 mov rcx,0x7ff0000000000000
 or rax,rcx
 ret
15:
 xor r11d,r11d
 cmp r8,-1022
 jge 17f
 add r8,53
 mov r11d,1
17:
 mov rcx,0x800fffffffffffff
 and rax,rcx
 add r8,1023
 shl r8,52
 or rax,r8
 test r11d,r11d
 jz 16f
 movq xmm4,rax
 mulsd xmm4,[rip+fl_two_m53]
 movq rax,xmm4
16:
 ret
# Go's archLog (math/log_amd64.s): XMM0 to its natural logarithm.
fl_log:
.ifdef ARM
# Go's math.log on ARM64 (log.go as Go's compiler makes it there: frexp,
# then the polynomial with its fused multiply-adds, read from the pinned
# toolchain's code): NaN and +Inf are themselves, a negative x NaN, zero
# -Inf.
 movq rcx,xmm0
 mov rax,rcx
 btr rax,63
 mov rdx,0x7ff0000000000000
 cmp rax,rdx
 ja 9f                         # NaN
 test rcx,rcx
 js 7f
 je 8f
 cmp rax,rdx
 je 9f                         # +Inf
 xor edx,edx                   # frexp: x is XMM1 * 2**EDX, XMM1 in [0.5, 1)
 mov rax,0x0010000000000000
 cmp rcx,rax
 jae 1f
 mulsd xmm0,[rip+fl_two52]
 movq rcx,xmm0
 mov edx,-52
1:
 mov rax,rcx
 shr rax,52
 and eax,0x7ff
 lea edx,[rdx+rax-1022]
 mov rax,0x800fffffffffffff
 and rcx,rax
 mov rax,0x3fe0000000000000
 or rcx,rax
 movq xmm1,rcx
 ucomisd xmm1,[rip+fl_hsqrt2]
 jae 2f
 addsd xmm1,xmm1
 dec edx
2:
 subsd xmm1,[rip+fl_one]       # f
 cvtsi2sd xmm2,edx             # k
 movsd xmm3,[rip+fl_two]
 addsd xmm3,xmm1
 movapd xmm4,xmm1
 divsd xmm4,xmm3               # s
 movapd xmm5,xmm4
 mulsd xmm5,xmm4               # s2
 movapd xmm6,xmm5
 mulsd xmm6,xmm5               # s4
 movsd xmm7,[rip+fl_l5]
 movsd xmm8,[rip+fl_l7]
 vfmadd231sd xmm7,xmm6,xmm8    # L5 + s4*L7
 movsd xmm8,[rip+fl_l3]
 vfmadd231sd xmm8,xmm6,xmm7
 movsd xmm7,[rip+fl_l1]
 vfmadd231sd xmm7,xmm6,xmm8    # L1 + s4*(L3 + s4*(L5 + s4*L7))
 movsd xmm8,[rip+fl_l4]
 movsd xmm9,[rip+fl_l6]
 vfmadd231sd xmm8,xmm6,xmm9    # L4 + s4*L6
 movsd xmm9,[rip+fl_l2]
 vfmadd231sd xmm9,xmm6,xmm8
 mulsd xmm9,xmm6               # t2
 vfmadd231sd xmm9,xmm5,xmm7    # R = s2*(...) + t2
 movsd xmm10,[rip+fl_half]
 mulsd xmm10,xmm1              # 0.5*f
 vfmadd231sd xmm9,xmm10,xmm1   # hfsq + R
 movsd xmm11,[rip+fl_ln2lo]
 mulsd xmm11,xmm2              # k*Ln2Lo
 vfmadd231sd xmm11,xmm4,xmm9   # s*(hfsq+R) + k*Ln2Lo
 vfmsub231sd xmm11,xmm10,xmm1  # hfsq - (...)
 subsd xmm11,xmm1              # (...) - f
 movsd xmm12,[rip+fl_ln2hi]
 vfmsub231sd xmm11,xmm2,xmm12  # k*Ln2Hi - (...)
 movapd xmm0,xmm11
 ret
7:
 mov rax,0x7ff8000000000001
 movq xmm0,rax
 ret
8:
 mov rax,0xfff0000000000000
 movq xmm0,rax
9:
 ret
.else
 movq rcx,xmm0
 mov rax,rcx
 btr rax,63
 test rax,rax
 jnz 2f
 mov rax,0xfff0000000000000
 movq xmm0,rax
 ret
2:
 test rcx,rcx
 jns 3f
 mov rax,0x7ff8000000000001
 movq xmm0,rax
 ret
3:
 mov rax,0x7ff0000000000000
 cmp rax,rcx
 jg 4f
 ret
4:
 mov rax,0x000fffffffffffff
 movq xmm2,rax
 andpd xmm2,xmm0
 movsd xmm0,[rip+fl_half]
 orpd xmm2,xmm0
 shr rcx,52
 and ecx,0x7ff
 sub ecx,0x3fe
 xorps xmm1,xmm1
 cvtsi2sd xmm1,ecx
 movsd xmm0,[rip+fl_hsqrt2]
 cmpnltsd xmm0,xmm2
 movsd xmm3,[rip+fl_one]
 andpd xmm3,xmm0
 subsd xmm1,xmm3
 movsd xmm0,[rip+fl_one]
 addsd xmm3,xmm0
 mulsd xmm2,xmm3
 subsd xmm2,xmm0
 movsd xmm0,[rip+fl_two]
 addsd xmm0,xmm2
 movapd xmm3,xmm2
 divsd xmm3,xmm0
 movapd xmm4,xmm3
 mulsd xmm4,xmm4
 movapd xmm5,xmm4
 mulsd xmm5,xmm5
 movsd xmm6,[rip+fl_l7]
 mulsd xmm6,xmm5
 addsd xmm6,[rip+fl_l5]
 mulsd xmm6,xmm5
 addsd xmm6,[rip+fl_l3]
 mulsd xmm6,xmm5
 addsd xmm6,[rip+fl_l1]
 mulsd xmm4,xmm6
 movsd xmm6,[rip+fl_l6]
 mulsd xmm6,xmm5
 addsd xmm6,[rip+fl_l4]
 mulsd xmm6,xmm5
 addsd xmm6,[rip+fl_l2]
 mulsd xmm5,xmm6
 addsd xmm4,xmm5
 movsd xmm0,[rip+fl_half]
 mulsd xmm0,xmm2
 mulsd xmm0,xmm2
 addsd xmm4,xmm0
 mulsd xmm3,xmm4
 movsd xmm4,[rip+fl_ln2lo]
 mulsd xmm4,xmm1
 addsd xmm3,xmm4
 subsd xmm0,xmm3
 subsd xmm0,xmm2
 mulsd xmm1,[rip+fl_ln2hi]
 subsd xmm1,xmm0
 movapd xmm0,xmm1
 ret
.endif
# Go's archExp (math/exp_amd64.s): XMM0 to e to its power, with fused
# multiply-add where the processor and the system have it, as Go chooses.
fl_exp:
.ifdef ARM
# Go's archExp on ARM64 (math/exp_arm64.s), instruction for instruction.
 ucomisd xmm0,xmm0
 jp 9f                         # NaN
 ucomisd xmm0,[rip+fl_exp_overflow]
 ja 7f
 ucomisd xmm0,[rip+fa_underflow]
 jb 8f
 movq rax,xmm0
 btr rax,63
 mov rdx,0x3e30000000000000    # 2**-28
 cmp rax,rdx
 jae 1f
 addsd xmm0,[rip+fl_one]       # 1 + x
 ret
1:
 movsd xmm2,[rip+fl_log2e]
 movsd xmm4,[rip+fl_half]
 vfmsub231sd xmm4,xmm2,xmm0    # Log2e*x - 0.5
 movsd xmm3,[rip+fl_half]
 vfmadd231sd xmm3,xmm2,xmm0    # Log2e*x + 0.5
 xorpd xmm5,xmm5
 ucomisd xmm0,xmm5
 jae 2f
 movapd xmm3,xmm4
2:
 cvttsd2si rcx,xmm3
 cvtsi2sd xmm3,rcx             # k
 movsd xmm4,[rip+fl_ln2hi]
 movapd xmm6,xmm0
 vfnmadd231sd xmm6,xmm3,xmm4   # hi = x - k*Ln2Hi
 movsd xmm5,[rip+fl_ln2lo]
 mulsd xmm5,xmm3               # lo = k*Ln2Lo
 movapd xmm7,xmm6
 subsd xmm7,xmm5               # r = hi - lo
 movapd xmm8,xmm7
 mulsd xmm8,xmm7               # t = r*r
 movsd xmm9,[rip+fa_p4]
 movsd xmm10,[rip+fa_p5]
 vfmadd231sd xmm9,xmm8,xmm10   # P4 + t*P5
 movsd xmm10,[rip+fa_p3]
 vfmadd231sd xmm10,xmm8,xmm9
 movsd xmm9,[rip+fa_p2]
 vfmadd231sd xmm9,xmm8,xmm10
 movsd xmm10,[rip+fa_p1]
 vfmadd231sd xmm10,xmm8,xmm9   # P1 + t*(...)
 movapd xmm11,xmm7
 vfnmadd231sd xmm11,xmm8,xmm10 # c = r - t*(...)
 movsd xmm12,[rip+fl_two]
 subsd xmm12,xmm11             # 2 - c
 movapd xmm13,xmm11
 mulsd xmm13,xmm7              # r*c
 divsd xmm13,xmm12
 movapd xmm14,xmm5
 subsd xmm14,xmm13             # lo - (r*c)/(2-c)
 subsd xmm14,xmm6              # ... - hi
 movsd xmm0,[rip+fl_one]
 subsd xmm0,xmm14              # y
 movq rax,xmm0                 # ldexp(y, k) as Go inlines it
 mov rdx,0x000fffffffffffff
 and rdx,rax
 shr rax,52
 add rax,rcx
 movsd xmm1,[rip+fl_one]
 cmp rax,1
 jge 3f
 add rax,52
 movsd xmm1,[rip+fa_m52]
3:
 shl rax,52
 or rax,rdx
 movq xmm0,rax
 mulsd xmm0,xmm1
 ret
7:
 mov rax,0x7ff0000000000000
 movq xmm0,rax
 ret
8:
 xorpd xmm0,xmm0
9:
 ret
.else
 push rbx
 movq r8,xmm0
 mov rdx,r8
 btr rdx,63
 mov rax,0x7ff0000000000000
 cmp rax,rdx
 jle fe_not_finite
 movsd xmm1,[rip+fl_exp_overflow]
 comisd xmm0,xmm1
 ja fe_overflow
 movsd xmm1,[rip+fl_log2e]
 mulsd xmm1,xmm0
 cvtsd2si r9d,xmm1
 cvtsi2sd xmm1,r9d
 mov eax,1
 cpuid
 and ecx,0x18001000            # AVX, OSXSAVE and FMA
 cmp ecx,0x18001000
 jne 1f
 xor ecx,ecx
 xgetbv
 and eax,6
 cmp eax,6
 je fe_fused
1:
 movsd xmm2,[rip+fl_ln2u]
 mulsd xmm2,xmm1
 subsd xmm0,xmm2
 movsd xmm2,[rip+fl_ln2l]
 mulsd xmm2,xmm1
 subsd xmm0,xmm2
 mulsd xmm0,[rip+fl_sixteenth]
 movsd xmm1,[rip+fl_e8]
 mulsd xmm1,xmm0
 addsd xmm1,[rip+fl_e7]
 mulsd xmm1,xmm0
 addsd xmm1,[rip+fl_e6]
 mulsd xmm1,xmm0
 addsd xmm1,[rip+fl_e5]
 mulsd xmm1,xmm0
 addsd xmm1,[rip+fl_e4]
 mulsd xmm1,xmm0
 addsd xmm1,[rip+fl_e3]
 mulsd xmm1,xmm0
 addsd xmm1,[rip+fl_half]
 mulsd xmm1,xmm0
 addsd xmm1,[rip+fl_one]
 mulsd xmm0,xmm1
 movsd xmm1,[rip+fl_two]
 addsd xmm1,xmm0
 mulsd xmm0,xmm1
 movsd xmm1,[rip+fl_two]
 addsd xmm1,xmm0
 mulsd xmm0,xmm1
 movsd xmm1,[rip+fl_two]
 addsd xmm1,xmm0
 mulsd xmm0,xmm1
 movsd xmm1,[rip+fl_two]
 addsd xmm1,xmm0
 mulsd xmm0,xmm1
 addsd xmm0,[rip+fl_one]
fe_ldexp:
 add r9d,0x3ff
 jle fe_denormal
 cmp r9d,0x7ff
 jge fe_overflow
fe_last:
 shl r9,52
 movq xmm1,r9
 mulsd xmm0,xmm1
 pop rbx
 ret
fe_not_finite:
 mov rax,0xfff0000000000000
 cmp rax,r8
 jne fe_given
fe_underflow:
 xorpd xmm0,xmm0
 pop rbx
 ret
fe_overflow:
 mov r8,0x7ff0000000000000
fe_given:
 movq xmm0,r8
 pop rbx
 ret
fe_denormal:
 cmp r9d,-52
 jl fe_underflow
 add r9d,0x3fe
 shl r9,52
 movq xmm1,r9
 mulsd xmm0,xmm1
 mov r9d,1
 jmp fe_last
fe_fused:
 movsd xmm2,[rip+fl_ln2u]
 vfnmadd231sd xmm0,xmm1,xmm2
 movsd xmm2,[rip+fl_ln2l]
 vfnmadd231sd xmm0,xmm1,xmm2
 mulsd xmm0,[rip+fl_sixteenth]
 movsd xmm1,[rip+fl_e8]
 vfmadd213sd xmm1,xmm0,[rip+fl_e7]
 vfmadd213sd xmm1,xmm0,[rip+fl_e6]
 vfmadd213sd xmm1,xmm0,[rip+fl_e5]
 vfmadd213sd xmm1,xmm0,[rip+fl_e4]
 vfmadd213sd xmm1,xmm0,[rip+fl_e3]
 vfmadd213sd xmm1,xmm0,[rip+fl_half]
 vfmadd213sd xmm1,xmm0,[rip+fl_one]
 mulsd xmm0,xmm1
 vaddsd xmm1,xmm0,[rip+fl_two]
 mulsd xmm0,xmm1
 vaddsd xmm1,xmm0,[rip+fl_two]
 mulsd xmm0,xmm1
 vaddsd xmm1,xmm0,[rip+fl_two]
 mulsd xmm0,xmm1
 vaddsd xmm1,xmm0,[rip+fl_two]
 vfmadd213sd xmm0,xmm1,[rip+fl_one]
 jmp fe_ldexp
.endif

 .balign 8
fl_one: .quad 0x3ff0000000000000
fl_minus_one: .quad 0xbff0000000000000
fl_two: .quad 0x4000000000000000
fl_half: .quad 0x3fe0000000000000
fl_minus_half: .quad 0xbfe0000000000000
fl_low: .quad 0xc3e0000000000000
fl_two63: .quad 0x43e0000000000000
fl_two52: .quad 0x4330000000000000
fl_two_m53: .quad 0x3ca0000000000000
fl_split: .quad 0x41a0000002000000
fl_sixteenth: .quad 0x3fb0000000000000
fl_hsqrt2: .quad 0x3fe6a09e667f3bcd
fl_ln2hi: .quad 0x3fe62e42fee00000
fl_ln2lo: .quad 0x3dea39ef35793c76
fl_l1: .quad 0x3fe5555555555593
fl_l2: .quad 0x3fd999999997fa04
fl_l3: .quad 0x3fd2492494229359
fl_l4: .quad 0x3fcc71c51d8e78af
fl_l5: .quad 0x3fc7466496cb03de
fl_l6: .quad 0x3fc39a09d078c69f
fl_l7: .quad 0x3fc2f112df3e5244
fl_log2e: .quad 0x3ff71547652b82fe
fl_ln2u: .quad 0x3fe62e42fefa3000
fl_ln2l: .quad 0x3d53de6af278ece6
fl_exp_overflow: .quad 0x40862e42fefa39ef
.ifdef ARM
fa_underflow: .quad 0xc0874910d52d3051
fa_p1: .quad 0x3fc5555555555555
fa_p2: .quad 0xbf66c16c16bebd93
fa_p3: .quad 0x3f11566aaf25de2c
fa_p4: .quad 0xbebbbd41c5d26bf1
fa_p5: .quad 0x3e66376972bea4d0
fa_m52: .quad 0x3cb0000000000000
.endif
fl_e3: .quad 0x3fc5555555555555
fl_e4: .quad 0x3fa5555555555555
fl_e5: .quad 0x3f81111111111111
fl_e6: .quad 0x3f56c16c16c16c17
fl_e7: .quad 0x3f2a01a01a01a01a
fl_e8: .quad 0x3efa01a01a01a01a
# Go 1.27.4 internal/strconv pow10Tab: 10**p from -348 to 347 as two words, the high one first, scaled so that its highest bit is set.
 .balign 8
fl_pow10:
 .quad 0xfa8fd5a0081c0289,0xe8cd3796329f1bac
 .quad 0x9c99e58405118196,0xf18042bddfa3714b
 .quad 0xc3c05ee50655e1fb,0xade0536d578c4d9e
 .quad 0xf4b0769e47eb5a79,0x19586848ad6f6106
 .quad 0x98ee4a22ecf3188c,0x6fd7412d6c659ca3
 .quad 0xbf29dcaba82fdeaf,0x8bcd1178c77f03cc
 .quad 0xeef453d6923bd65b,0xeec055d6f95ec4c0
 .quad 0x9558b4661b6565f9,0xb53835a65bdb3af8
 .quad 0xbaaee17fa23ebf77,0xa286430ff2d209b6
 .quad 0xe95a99df8ace6f54,0x0b27d3d3ef868c23
 .quad 0x91d8a02bb6c10595,0x86f8e46475b41796
 .quad 0xb64ec836a47146fa,0x68b71d7d93211d7b
 .quad 0xe3e27a444d8d98b8,0x02e4e4dcf7e964da
 .quad 0x8e6d8c6ab0787f73,0x01cf0f0a1af1df08
 .quad 0xb208ef855c969f50,0x4242d2cca1ae56ca
 .quad 0xde8b2b66b3bc4724,0x52d3877fca19ec7d
 .quad 0x8b16fb203055ac77,0xb3c434afde5033ce
 .quad 0xaddcb9e83c6b1794,0x20b541dbd5e440c2
 .quad 0xd953e8624b85dd79,0x28e29252cb5d50f2
 .quad 0x87d4713d6f33aa6c,0x798d9b73bf1a5297
 .quad 0xa9c98d8ccb009507,0x97f10250aee0e73d
 .quad 0xd43bf0effdc0ba49,0xfded42e4da99210d
 .quad 0x84a57695fe98746e,0xfeb449cf089fb4a8
 .quad 0xa5ced43b7e3e9189,0xbe615c42cac7a1d2
 .quad 0xcf42894a5dce35eb,0xadf9b3537d798a46
 .quad 0x818995ce7aa0e1b3,0x8cbc10142e6bf66c
 .quad 0xa1ebfb4219491a20,0xefeb14193a06f407
 .quad 0xca66fa129f9b60a7,0x2be5d91f8888b109
 .quad 0xfd00b897478238d1,0x76df4f676aaadd4b
 .quad 0x9e20735e8cb16383,0xaa4b91a0a2aaca4f
 .quad 0xc5a890362fddbc63,0x14de7608cb557ce2
 .quad 0xf712b443bbd52b7c,0x5a16138afe2adc1b
 .quad 0x9a6bb0aa55653b2e,0xb84dcc36dedac991
 .quad 0xc1069cd4eabe89f9,0x66613f4496917bf5
 .quad 0xf148440a256e2c77,0x3ff98f15bc35daf2
 .quad 0x96cd2a865764dbcb,0xc7fbf96d95a1a8d7
 .quad 0xbc807527ed3e12bd,0x39faf7c8fb0a130d
 .quad 0xeba09271e88d976c,0x0879b5bb39cc97d1
 .quad 0x93445b8731587ea4,0x854c1195041fdee2
 .quad 0xb8157268fdae9e4d,0xa69f15fa4527d69b
 .quad 0xe61acf033d1a45e0,0x9046db78d671cc42
 .quad 0x8fd0c16206306bac,0x5a2c492b86071fa9
 .quad 0xb3c4f1ba87bc8697,0x70b75b766788e793
 .quad 0xe0b62e2929aba83d,0xcce53254016b2178
 .quad 0x8c71dcd9ba0b4926,0x600f3f7480e2f4eb
 .quad 0xaf8e5410288e1b70,0xf8130f51a11bb226
 .quad 0xdb71e91432b1a24b,0x3617d32609629eaf
 .quad 0x892731ac9faf056f,0x41cee3f7c5dda32d
 .quad 0xab70fe17c79ac6cb,0x92429cf5b7550bf9
 .quad 0xd64d3d9db981787e,0xf6d34433252a4ef7
 .quad 0x85f0468293f0eb4f,0xda440a9ff73a715a
 .quad 0xa76c582338ed2622,0x50d50d47f5090db1
 .quad 0xd1476e2c07286fab,0xe50a5099f24b511e
 .quad 0x82cca4db847945cb,0xaf267260376f12b2
 .quad 0xa37fce126597973d,0x1af00ef8454ad75f
 .quad 0xcc5fc196fefd7d0d,0xe1ac12b6569d8d37
 .quad 0xff77b1fcbebcdc50,0xda171763ec44f085
 .quad 0x9faacf3df73609b2,0x884e6e9e73ab1653
 .quad 0xc795830d75038c1e,0x2a620a461095dbe8
 .quad 0xf97ae3d0d2446f26,0xb4fa8cd794bb52e2
 .quad 0x9becce62836ac578,0xb11c9806bcf513cd
 .quad 0xc2e801fb244576d6,0xdd63be086c3258c0
 .quad 0xf3a20279ed56d48b,0x94bcad8a873eeef0
 .quad 0x9845418c345644d7,0x7cf5ec7694875556
 .quad 0xbe5691ef416bd60d,0xdc33679439a92aac
 .quad 0xedec366b11c6cb90,0xd340417948137557
 .quad 0x94b3a202eb1c3f3a,0x840828ebcd0c2956
 .quad 0xb9e08a83a5e34f08,0x250a3326c04f33ac
 .quad 0xe858ad248f5c22ca,0x2e4cbff070630097
 .quad 0x91376c36d99995bf,0xdceff7f6463de05e
 .quad 0xb58547448ffffb2e,0x542bf5f3d7cd5875
 .quad 0xe2e69915b3fff9fa,0xe936f370cdc0ae93
 .quad 0x8dd01fad907ffc3c,0x51c2582680986d1c
 .quad 0xb1442798f49ffb4b,0x6632ee3020be8863
 .quad 0xdd95317f31c7fa1e,0xbfbfa9bc28ee2a7c
 .quad 0x8a7d3eef7f1cfc53,0xb7d7ca159994da8d
 .quad 0xad1c8eab5ee43b67,0x25cdbc9afffa1130
 .quad 0xd863b256369d4a41,0x6f412bc1bff8957d
 .quad 0x873e4f75e2224e69,0xa588bb5917fb5d6e
 .quad 0xa90de3535aaae203,0x8eeaea2f5dfa34c9
 .quad 0xd3515c2831559a84,0xf2a5a4bb3578c1fc
 .quad 0x8412d9991ed58092,0x17a786f5016b793d
 .quad 0xa5178fff668ae0b7,0x9d9168b241c6578d
 .quad 0xce5d73ff402d98e4,0x04f5c2ded237ed70
 .quad 0x80fa687f881c7f8f,0x831999cb4362f466
 .quad 0xa139029f6a239f73,0xe3e0003e143bb17f
 .quad 0xc987434744ac874f,0x5cd8004d994a9ddf
 .quad 0xfbe9141915d7a923,0xb40e0060ff9d4557
 .quad 0x9d71ac8fada6c9b6,0x9088c03c9fc24b56
 .quad 0xc4ce17b399107c23,0x34aaf04bc7b2de2c
 .quad 0xf6019da07f549b2c,0x81d5ac5eb99f95b7
 .quad 0x99c102844f94e0fc,0xd1258bbb3403bd92
 .quad 0xc0314325637a193a,0x056eeeaa0104acf7
 .quad 0xf03d93eebc589f89,0x86caaa548145d835
 .quad 0x96267c7535b763b6,0xb43eaa74d0cba721
 .quad 0xbbb01b9283253ca3,0x614e551204fe90e9
 .quad 0xea9c227723ee8bcc,0xb9a1ea56863e3523
 .quad 0x92a1958a76751760,0xf405327613e6e136
 .quad 0xb749faed14125d37,0x31067f1398e09984
 .quad 0xe51c79a85916f485,0x7d481ed87f18bfe5
 .quad 0x8f31cc0937ae58d3,0x2e4d13474f6f77ef
 .quad 0xb2fe3f0b8599ef08,0x79e05819234b55ea
 .quad 0xdfbdcece67006aca,0x98586e1f6c1e2b65
 .quad 0x8bd6a141006042be,0x1f3744d3a392db1f
 .quad 0xaecc49914078536e,0xa70516088c7791e7
 .quad 0xda7f5bf590966849,0x50c65b8aaf957661
 .quad 0x888f99797a5e012e,0x927bf936adbd69fc
 .quad 0xaab37fd7d8f58179,0x371af784592cc47c
 .quad 0xd5605fcdcf32e1d7,0x04e1b5656f77f59b
 .quad 0x855c3be0a17fcd27,0xa30d115f65aaf980
 .quad 0xa6b34ad8c9dfc070,0x0bd055b73f15b7e1
 .quad 0xd0601d8efc57b08c,0x0ec46b250edb25d9
 .quad 0x823c12795db6ce58,0x893ac2f72948f7a7
 .quad 0xa2cb1717b52481ee,0xab8973b4f39b3591
 .quad 0xcb7ddcdda26da269,0x566bd0a2308202f6
 .quad 0xfe5d54150b090b03,0x2c06c4cabca283b3
 .quad 0x9efa548d26e5a6e2,0x3b843afeb5e59250
 .quad 0xc6b8e9b0709f109b,0xca6549be635ef6e4
 .quad 0xf867241c8cc6d4c1,0x3cfe9c2dfc36b49d
 .quad 0x9b407691d7fc44f9,0x861f219cbda230e2
 .quad 0xc21094364dfb5637,0x67a6ea03ed0abd1b
 .quad 0xf294b943e17a2bc5,0xc190a484e84d6c62
 .quad 0x979cf3ca6cec5b5b,0x58fa66d3113063bd
 .quad 0xbd8430bd08277232,0xaf390087d57c7cac
 .quad 0xece53cec4a314ebe,0x5b0740a9cadb9bd7
 .quad 0x940f4613ae5ed137,0x78e4886a1ec94166
 .quad 0xb913179899f68585,0xd71daa84a67b91c0
 .quad 0xe757dd7ec07426e6,0xcce51525d01a7630
 .quad 0x9096ea6f38489850,0xc00f2d37a21089de
 .quad 0xb4bca50b065abe64,0xf012f8858a94ac56
 .quad 0xe1ebce4dc7f16dfc,0x2c17b6a6ed39d76b
 .quad 0x8d3360f09cf6e4be,0x9b8ed228544426a3
 .quad 0xb080392cc4349ded,0x427286b26955304c
 .quad 0xdca04777f541c568,0x130f285f03aa7c5f
 .quad 0x89e42caaf9491b61,0x0be9793b624a8dbb
 .quad 0xac5d37d5b79b623a,0xcee3d78a3add312a
 .quad 0xd77485cb25823ac8,0x829ccd6cc9947d74
 .quad 0x86a8d39ef77164bd,0x51a20063fdfcce68
 .quad 0xa8530886b54dbdec,0x260a807cfd7c0203
 .quad 0xd267caa862a12d67,0x2f8d209c3cdb0284
 .quad 0x8380dea93da4bc61,0xbdb83461a608e192
 .quad 0xa46116538d0deb79,0xad26417a0f8b19f7
 .quad 0xcd795be870516657,0x986fd1d8936de074
 .quad 0x806bd9714632dff7,0xff45e3275c24ac49
 .quad 0xa086cfcd97bf97f4,0x7f175bf1332dd75b
 .quad 0xc8a883c0fdaf7df1,0x9edd32ed7ff94d32
 .quad 0xfad2a4b13d1b5d6d,0x86947fa8dff7a07e
 .quad 0x9cc3a6eec6311a64,0x341ccfc98bfac44f
 .quad 0xc3f490aa77bd60fd,0x412403bbeef97563
 .quad 0xf4f1b4d515acb93c,0x116d04aaeab7d2bb
 .quad 0x991711052d8bf3c6,0x8ae422ead2b2e3b5
 .quad 0xbf5cd54678eef0b7,0x2d9d2ba5875f9ca2
 .quad 0xef340a98172aace5,0x7904768ee93783cb
 .quad 0x9580869f0e7aac0f,0x2ba2ca1951c2b25f
 .quad 0xbae0a846d2195713,0x768b7c9fa6335ef6
 .quad 0xe998d258869facd8,0xd42e5bc78fc036b4
 .quad 0x91ff83775423cc07,0x849cf95cb9d82230
 .quad 0xb67f6455292cbf09,0xe5c437b3e84e2abd
 .quad 0xe41f3d6a7377eecb,0xdf3545a0e261b56c
 .quad 0x8e938662882af53f,0xab814b848d7d1163
 .quad 0xb23867fb2a35b28e,0x16619e65b0dc55bc
 .quad 0xdec681f9f4c31f32,0x9bfa05ff1d136b2b
 .quad 0x8b3c113c38f9f37f,0x217c43bf722c22fb
 .quad 0xae0b158b4738705f,0x69db54af4eb72bba
 .quad 0xd98ddaee19068c77,0xc45229db2264f6a8
 .quad 0x87f8a8d4cfa417ca,0x1ab35a28f57f1a29
 .quad 0xa9f6d30a038d1dbd,0xa16030b332dee0b3
 .quad 0xd47487cc8470652c,0x89b83cdfff9698e0
 .quad 0x84c8d4dfd2c63f3c,0xd613260bffbe1f8c
 .quad 0xa5fb0a17c777cf0a,0x0b97ef8effada76f
 .quad 0xcf79cc9db955c2cd,0x8e7deb72bf99114b
 .quad 0x81ac1fe293d599c0,0x390eb327b7bfaacf
 .quad 0xa21727db38cb0030,0x47525ff1a5af9583
 .quad 0xca9cf1d206fdc03c,0x5926f7ee0f1b7ae3
 .quad 0xfd442e4688bd304b,0x6f70b5e992e2599c
 .quad 0x9e4a9cec15763e2f,0x65a671b1fbcd7801
 .quad 0xc5dd44271ad3cdbb,0xbf100e1e7ac0d602
 .quad 0xf7549530e188c129,0x2ed411a619710b83
 .quad 0x9a94dd3e8cf578ba,0x7d448b07cfe6a731
 .quad 0xc13a148e3032d6e8,0x1c95adc9c3e050fe
 .quad 0xf18899b1bc3f8ca2,0x23bb193c34d8653e
 .quad 0x96f5600f15a7b7e6,0xd654efc5a1073f46
 .quad 0xbcb2b812db11a5df,0x8bea2bb709490f18
 .quad 0xebdf661791d60f57,0xeee4b6a4cb9b52de
 .quad 0x936b9fcebb25c996,0x354ef226ff4113cb
 .quad 0xb84687c269ef3bfc,0xc2a2aeb0bf1158bd
 .quad 0xe65829b3046b0afb,0xf34b5a5ceed5aeed
 .quad 0x8ff71a0fe2c2e6dd,0xb80f187a15458d54
 .quad 0xb3f4e093db73a094,0xa612de989a96f0a9
 .quad 0xe0f218b8d25088b9,0xcf97963ec13cacd3
 .quad 0x8c974f7383725574,0xe1bebde738c5ec04
 .quad 0xafbd2350644eead0,0x1a2e6d6106f76705
 .quad 0xdbac6c247d62a584,0x20ba08b948b540c6
 .quad 0x894bc396ce5da773,0x94744573cd71487c
 .quad 0xab9eb47c81f51150,0xf99156d0c0cd9a9b
 .quad 0xd686619ba27255a3,0x37f5ac84f1010142
 .quad 0x8613fd0145877586,0x42f98bd316a0a0c9
 .quad 0xa798fc4196e952e8,0xd3b7eec7dc48c8fb
 .quad 0xd17f3b51fca3a7a1,0x08a5ea79d35afb3a
 .quad 0x82ef85133de648c5,0x6567b28c2418dd04
 .quad 0xa3ab66580d5fdaf6,0x3ec19f2f2d1f1445
 .quad 0xcc963fee10b7d1b4,0xce7206faf866d957
 .quad 0xffbbcfe994e5c620,0x020e88b9b6808fad
 .quad 0x9fd561f1fd0f9bd4,0x01491574121059cc
 .quad 0xc7caba6e7c5382c9,0x019b5ad11694703f
 .quad 0xf9bd690a1b68637c,0xc20231855c398c4f
 .quad 0x9c1661a651213e2e,0xf9415ef359a3f7b1
 .quad 0xc31bfa0fe5698db9,0xb791b6b0300cf59d
 .quad 0xf3e2f893dec3f127,0xa576245c3c103305
 .quad 0x986ddb5c6b3a76b8,0x0769d6b9a58a1fe3
 .quad 0xbe89523386091466,0x09444c680eeca7dc
 .quad 0xee2ba6c0678b5980,0x8b955f8212a7d1d3
 .quad 0x94db483840b717f0,0x573d5bb14ba8e323
 .quad 0xba121a4650e4ddec,0x6d0cb29d9e931bec
 .quad 0xe896a0d7e51e1567,0x884fdf450637e2e8
 .quad 0x915e2486ef32cd61,0xf531eb8b23e2edd1
 .quad 0xb5b5ada8aaff80b9,0xf27e666decdba945
 .quad 0xe3231912d5bf60e7,0xef1e000968129396
 .quad 0x8df5efabc5979c90,0x3572c005e10b9c3e
 .quad 0xb1736b96b6fd83b4,0x42cf7007594e834d
 .quad 0xddd0467c64bce4a1,0x53834c092fa22421
 .quad 0x8aa22c0dbef60ee5,0x94320f85bdc55694
 .quad 0xad4ab7112eb3929e,0x793e93672d36ac39
 .quad 0xd89d64d57a607745,0x178e3840f8845748
 .quad 0x87625f056c7c4a8c,0xeeb8e3289b52b68d
 .quad 0xa93af6c6c79b5d2e,0x2a671bf2c2276430
 .quad 0xd389b4787982347a,0xb500e2ef72b13d3c
 .quad 0x843610cb4bf160cc,0x31208dd5a7aec645
 .quad 0xa54394fe1eedb8ff,0x3d68b14b119a77d7
 .quad 0xce947a3da6a9273f,0x8cc2dd9dd60115cd
 .quad 0x811ccc668829b888,0xf7f9ca82a5c0ada0
 .quad 0xa163ff802a3426a9,0x35f83d234f30d908
 .quad 0xc9bcff6034c13053,0x03764c6c22fd0f4a
 .quad 0xfc2c3f3841f17c68,0x4453df872bbc531d
 .quad 0x9d9ba7832936edc1,0x2ab46bb47b55b3f2
 .quad 0xc5029163f384a932,0xf56186a19a2b20ee
 .quad 0xf64335bcf065d37e,0xb2b9e84a00b5e92a
 .quad 0x99ea0196163fa42f,0xafb4312e4071b1ba
 .quad 0xc06481fb9bcf8d3a,0x1ba13d79d08e1e29
 .quad 0xf07da27a82c37089,0xa2898cd844b1a5b3
 .quad 0x964e858c91ba2656,0xc595f8072aef0790
 .quad 0xbbe226efb628afeb,0x76fb7608f5aac974
 .quad 0xeadab0aba3b2dbe6,0xd4ba538b33157bd1
 .quad 0x92c8ae6b464fc970,0xc4f47436ffed6d62
 .quad 0xb77ada0617e3bbcc,0xf6319144bfe8c8bb
 .quad 0xe55990879ddcaabe,0x33bdf595efe2faea
 .quad 0x8f57fa54c2a9eab7,0x6056b97db5eddcd2
 .quad 0xb32df8e9f3546565,0xb86c67dd23695406
 .quad 0xdff9772470297ebe,0xa68781d46c43a908
 .quad 0x8bfbea76c619ef37,0xa814b124c3aa49a5
 .quad 0xaefae51477a06b04,0x1219dd6df494dc0e
 .quad 0xdab99e59958885c5,0x16a054c971ba1312
 .quad 0x88b402f7fd75539c,0xee2434fde7144beb
 .quad 0xaae103b5fcd2a882,0x29ad423d60d95ee6
 .quad 0xd59944a37c0752a3,0xb41892ccb90fb6a0
 .quad 0x857fcae62d8493a6,0x908f5bbff3a9d224
 .quad 0xa6dfbd9fb8e5b88f,0x34b332aff09446ad
 .quad 0xd097ad07a71f26b3,0x81dfff5becb95858
 .quad 0x825ecc24c8737830,0x712bff9973f3d737
 .quad 0xa2f67f2dfa90563c,0x8d76ff7fd0f0cd05
 .quad 0xcbb41ef979346bcb,0xb0d4bf5fc52d0046
 .quad 0xfea126b7d78186bd,0x1d09ef37b6784057
 .quad 0x9f24b832e6b0f437,0xf2263582d20b2836
 .quad 0xc6ede63fa05d3144,0x6eafc2e3868df244
 .quad 0xf8a95fcf88747d95,0x8a5bb39c68316ed5
 .quad 0x9b69dbe1b548ce7d,0x36795041c11ee545
 .quad 0xc24452da229b021c,0x0417a45231669e97
 .quad 0xf2d56790ab41c2a3,0x051d8d66bdc0463c
 .quad 0x97c560ba6b0919a6,0x2332786036982be5
 .quad 0xbdb6b8e905cb6010,0xabff1678443e36df
 .quad 0xed246723473e3814,0xd6fedc16554dc497
 .quad 0x9436c0760c86e30c,0x065f498df5509ade
 .quad 0xb94470938fa89bcf,0x07f71bf172a4c196
 .quad 0xe7958cb87392c2c3,0x49f4e2edcf4df1fb
 .quad 0x90bd77f3483bb9ba,0x4e390dd4a190b73d
 .quad 0xb4ecd5f01a4aa829,0xe1c75149c9f4e50c
 .quad 0xe2280b6c20dd5233,0xda39259c3c721e4f
 .quad 0x8d590723948a5360,0xa863b781a5c752f1
 .quad 0xb0af48ec79ace838,0xd27ca5620f3927ae
 .quad 0xdcdb1b2798182245,0x071bceba9307719a
 .quad 0x8a08f0f8bf0f156c,0xe47161349be4a700
 .quad 0xac8b2d36eed2dac6,0x1d8db981c2ddd0c0
 .quad 0xd7adf884aa879178,0xa4f127e2339544f0
 .quad 0x86ccbb52ea94baeb,0x6716b8ed603d4b16
 .quad 0xa87fea27a539e9a6,0xc0dc6728b84c9ddb
 .quad 0xd29fe4b18e88640f,0x711380f2e65fc552
 .quad 0x83a3eeeef9153e8a,0xe6ac3097cffbdb53
 .quad 0xa48ceaaab75a8e2c,0xa0573cbdc3fad228
 .quad 0xcdb02555653131b7,0xc86d0bed34f986b2
 .quad 0x808e17555f3ebf12,0x1d442774411bf42f
 .quad 0xa0b19d2ab70e6ed7,0xa49531515162f13b
 .quad 0xc8de047564d20a8c,0x0dba7da5a5bbad8a
 .quad 0xfb158592be068d2f,0x11291d0f0f2a98ed
 .quad 0x9ced737bb6c4183e,0xaab9b229697a9f94
 .quad 0xc428d05aa4751e4d,0x55681eb3c3d94779
 .quad 0xf53304714d9265e0,0x2ac22660b4cf9957
 .quad 0x993fe2c6d07b7fac,0x1ab957fc7101bfd6
 .quad 0xbf8fdb78849a5f97,0x2167adfb8d422fcc
 .quad 0xef73d256a5c0f77d,0x69c1997a7092bbbf
 .quad 0x95a8637627989aae,0x2218ffec865bb557
 .quad 0xbb127c53b17ec15a,0xaa9f3fe7a7f2a2ad
 .quad 0xe9d71b689dde71b0,0x55470fe191ef4b59
 .quad 0x9226712162ab070e,0x354c69ecfb358f17
 .quad 0xb6b00d69bb55c8d2,0xc29f84683a02f2dd
 .quad 0xe45c10c42a2b3b06,0x734765824883af95
 .quad 0x8eb98a7a9a5b04e4,0x880c9f716d524dbd
 .quad 0xb267ed1940f1c61d,0xaa0fc74dc8a6e12c
 .quad 0xdf01e85f912e37a4,0x9493b9213ad09977
 .quad 0x8b61313bbabce2c7,0xdcdc53b4c4c25fea
 .quad 0xae397d8aa96c1b78,0x541368a1f5f2f7e5
 .quad 0xd9c7dced53c72256,0x691842ca736fb5de
 .quad 0x881cea14545c7576,0x81af29be8825d1ab
 .quad 0xaa242499697392d3,0x221af42e2a2f4616
 .quad 0xd4ad2dbfc3d07788,0x6aa1b139b4bb179b
 .quad 0x84ec3c97da624ab5,0x42a50ec410f4eec1
 .quad 0xa6274bbdd0fadd62,0x134e527515322a71
 .quad 0xcfb11ead453994bb,0x9821e7125a7eb50d
 .quad 0x81ceb32c4b43fcf5,0x7f15306b788f3128
 .quad 0xa2425ff75e14fc32,0x5eda7c8656b2fd72
 .quad 0xcad2f7f5359a3b3f,0xf6911ba7ec5fbccf
 .quad 0xfd87b5f28300ca0e,0x74356291e777ac03
 .quad 0x9e74d1b791e07e49,0x88a15d9b30aacb82
 .quad 0xc612062576589ddb,0x6ac9b501fcd57e62
 .quad 0xf79687aed3eec552,0xc57c22427c0addfb
 .quad 0x9abe14cd44753b53,0x3b6d95698d86cabd
 .quad 0xc16d9a0095928a28,0x8a48fac3f0e87d6c
 .quad 0xf1c90080baf72cb2,0xacdb3974ed229cc7
 .quad 0x971da05074da7bef,0x2c0903e91435a1fc
 .quad 0xbce5086492111aeb,0x770b44e359430a7b
 .quad 0xec1e4a7db69561a6,0xd4ce161c2f93cd1a
 .quad 0x9392ee8e921d5d08,0xc500cdd19dbc6030
 .quad 0xb877aa3236a4b44a,0xf6410146052b783d
 .quad 0xe69594bec44de15c,0xb3d141978676564c
 .quad 0x901d7cf73ab0acda,0xf062c8feb409f5ef
 .quad 0xb424dc35095cd810,0xac7b7b3e610c736b
 .quad 0xe12e13424bb40e14,0xd79a5a0df94f9046
 .quad 0x8cbccc096f5088cc,0x06c07848bbd1ba2c
 .quad 0xafebff0bcb24aaff,0x0870965aeac628b7
 .quad 0xdbe6fecebdedd5bf,0x4a8cbbf1a577b2e4
 .quad 0x89705f4136b4a598,0xce97f577076acfcf
 .quad 0xabcc77118461cefd,0x023df2d4c94583c2
 .quad 0xd6bf94d5e57a42bd,0xc2cd6f89fb96e4b3
 .quad 0x8637bd05af6c69b6,0x59c065b63d3e4ef0
 .quad 0xa7c5ac471b478424,0xf0307f23cc8de2ac
 .quad 0xd1b71758e219652c,0x2c3c9eecbfb15b57
 .quad 0x83126e978d4fdf3c,0x9ba5e353f7ced916
 .quad 0xa3d70a3d70a3d70b,0xc28f5c28f5c28f5c
 .quad 0xcccccccccccccccd,0x3333333333333333
 .quad 0x8000000000000000,0x0000000000000000
 .quad 0xa000000000000000,0x0000000000000000
 .quad 0xc800000000000000,0x0000000000000000
 .quad 0xfa00000000000000,0x0000000000000000
 .quad 0x9c40000000000000,0x0000000000000000
 .quad 0xc350000000000000,0x0000000000000000
 .quad 0xf424000000000000,0x0000000000000000
 .quad 0x9896800000000000,0x0000000000000000
 .quad 0xbebc200000000000,0x0000000000000000
 .quad 0xee6b280000000000,0x0000000000000000
 .quad 0x9502f90000000000,0x0000000000000000
 .quad 0xba43b74000000000,0x0000000000000000
 .quad 0xe8d4a51000000000,0x0000000000000000
 .quad 0x9184e72a00000000,0x0000000000000000
 .quad 0xb5e620f480000000,0x0000000000000000
 .quad 0xe35fa931a0000000,0x0000000000000000
 .quad 0x8e1bc9bf04000000,0x0000000000000000
 .quad 0xb1a2bc2ec5000000,0x0000000000000000
 .quad 0xde0b6b3a76400000,0x0000000000000000
 .quad 0x8ac7230489e80000,0x0000000000000000
 .quad 0xad78ebc5ac620000,0x0000000000000000
 .quad 0xd8d726b7177a8000,0x0000000000000000
 .quad 0x878678326eac9000,0x0000000000000000
 .quad 0xa968163f0a57b400,0x0000000000000000
 .quad 0xd3c21bcecceda100,0x0000000000000000
 .quad 0x84595161401484a0,0x0000000000000000
 .quad 0xa56fa5b99019a5c8,0x0000000000000000
 .quad 0xcecb8f27f4200f3a,0x0000000000000000
 .quad 0x813f3978f8940985,0xc000000000000000
 .quad 0xa18f07d736b90be6,0xb000000000000000
 .quad 0xc9f2c9cd04674edf,0x5c00000000000000
 .quad 0xfc6f7c4045812297,0xb300000000000000
 .quad 0x9dc5ada82b70b59e,0x0fe0000000000000
 .quad 0xc5371912364ce306,0x93d8000000000000
 .quad 0xf684df56c3e01bc7,0x38ce000000000000
 .quad 0x9a130b963a6c115d,0xc380c00000000000
 .quad 0xc097ce7bc90715b4,0xb460f00000000000
 .quad 0xf0bdc21abb48db21,0xe1792c0000000000
 .quad 0x96769950b50d88f5,0xecebbb8000000000
 .quad 0xbc143fa4e250eb32,0xe826aa6000000000
 .quad 0xeb194f8e1ae525fe,0xa23054f800000000
 .quad 0x92efd1b8d0cf37bf,0xa55e351b00000000
 .quad 0xb7abc627050305ae,0x0eb5c261c0000000
 .quad 0xe596b7b0c643c71a,0x926332fa30000000
 .quad 0x8f7e32ce7bea5c70,0x1b7dffdc5e000000
 .quad 0xb35dbf821ae4f38c,0x225d7fd375800000
 .quad 0xe0352f62a19e306f,0x2af4dfc852e00000
 .quad 0x8c213d9da502de46,0xbad90bdd33cc0000
 .quad 0xaf298d050e4395d7,0x698f4ed480bf0000
 .quad 0xdaf3f04651d47b4d,0xc3f32289a0eec000
 .quad 0x88d8762bf324cd10,0x5a77f59604953800
 .quad 0xab0e93b6efee0054,0x7115f2fb85ba8600
 .quad 0xd5d238a4abe98069,0x8d5b6fba67292780
 .quad 0x85a36366eb71f042,0xb85925d48079b8b0
 .quad 0xa70c3c40a64e6c52,0x666f6f49a09826dc
 .quad 0xd0cf4b50cfe20766,0x000b4b1c08be3093
 .quad 0x82818f1281ed44a0,0x40070ef18576de5b
 .quad 0xa321f2d7226895c8,0x5008d2ade6d495f2
 .quad 0xcbea6f8ceb02bb3a,0x640b07596089bb6f
 .quad 0xfee50b7025c36a09,0xfd0dc92fb8ac2a4b
 .quad 0x9f4f2726179a2246,0xfe289dbdd36b9a6f
 .quad 0xc722f0ef9d80aad7,0xbdb2c52d4846810a
 .quad 0xf8ebad2b84e0d58c,0x2d1f76789a58214d
 .quad 0x9b934c3b330c8578,0x9c33aa0b607714d0
 .quad 0xc2781f49ffcfa6d6,0xc340948e3894da04
 .quad 0xf316271c7fc3908b,0x7410b9b1c6ba1085
 .quad 0x97edd871cfda3a57,0x688a740f1c344a53
 .quad 0xbde94e8e43d0c8ed,0xc2ad1112e3415ce8
 .quad 0xed63a231d4c4fb28,0xb35855579c11b422
 .quad 0x945e455f24fb1cf9,0x70173556c18b1095
 .quad 0xb975d6b6ee39e437,0x4c1d02ac71edd4bb
 .quad 0xe7d34c64a9c85d45,0x9f2443578e6949e9
 .quad 0x90e40fbeea1d3a4b,0x4376aa16b901ce32
 .quad 0xb51d13aea4a488de,0x9454549c674241be
 .quad 0xe264589a4dcdab15,0x396969c38112d22e
 .quad 0x8d7eb76070a08aed,0x03e1e21a30abc35d
 .quad 0xb0de65388cc8ada9,0xc4da5aa0bcd6b434
 .quad 0xdd15fe86affad913,0xb610f148ec0c6141
 .quad 0x8a2dbf142dfcc7ac,0x91ca96cd9387bcc8
 .quad 0xacb92ed9397bf997,0xb63d3c80f869abfb
 .quad 0xd7e77a8f87daf7fc,0x23cc8ba1368416f9
 .quad 0x86f0ac99b4e8dafe,0x965fd744c2128e5c
 .quad 0xa8acd7c0222311bd,0x3bf7cd15f29731f3
 .quad 0xd2d80db02aabd62c,0x0af5c05b6f3cfe6f
 .quad 0x83c7088e1aab65dc,0x86d9983925861f05
 .quad 0xa4b8cab1a1563f53,0xa88ffe476ee7a6c7
 .quad 0xcde6fd5e09abcf27,0x12b3fdd94aa19079
 .quad 0x80b05e5ac60b6179,0xabb07ea7cea4fa4b
 .quad 0xa0dc75f1778e39d7,0x969c9e51c24e38de
 .quad 0xc913936dd571c84d,0xfc43c5e632e1c716
 .quad 0xfb5878494ace3a60,0xfb54b75fbf9a38dc
 .quad 0x9d174b2dcec0e47c,0x9d14f29bd7c06389
 .quad 0xc45d1df942711d9b,0xc45a2f42cdb07c6b
 .quad 0xf5746577930d6501,0x3570bb13811c9b86
 .quad 0x9968bf6abbe85f21,0x816674ec30b1e134
 .quad 0xbfc2ef456ae276e9,0x61c012273cde5981
 .quad 0xefb3ab16c59b14a3,0x3a3016b10c15efe1
 .quad 0x95d04aee3b80ece6,0x445e0e2ea78db5ed
 .quad 0xbb445da9ca612820,0xd57591ba51712368
 .quad 0xea1575143cf97227,0x0ad2f628e5cd6c42
 .quad 0x924d692ca61be759,0xa6c3d9d98fa063a9
 .quad 0xb6e0c377cfa2e12f,0x9074d04ff3887c93
 .quad 0xe498f455c38b997b,0xf4920463f06a9bb8
 .quad 0x8edf98b59a373fed,0xb8db42be7642a153
 .quad 0xb2977ee300c50fe8,0xa712136e13d349a8
 .quad 0xdf3d5e9bc0f653e2,0xd0d6984998c81c12
 .quad 0x8b865b215899f46d,0x42861f2dff7d118b
 .quad 0xae67f1e9aec07188,0x1327a6f97f5c55ee
 .quad 0xda01ee641a708dea,0x17f190b7df336b6a
 .quad 0x884134fe908658b3,0xcef6fa72eb802322
 .quad 0xaa51823e34a7eedf,0x42b4b90fa6602bea
 .quad 0xd4e5e2cdc1d1ea97,0x9361e7538ff836e5
 .quad 0x850fadc09923329f,0xfc1d309439fb224f
 .quad 0xa6539930bf6bff46,0x7b247cb94879eae3
 .quad 0xcfe87f7cef46ff17,0x19ed9be79a98659c
 .quad 0x81f14fae158c5f6f,0xb0348170c09f3f81
 .quad 0xa26da3999aef774a,0x1c41a1ccf0c70f62
 .quad 0xcb090c8001ab551d,0xa3520a402cf8d33a
 .quad 0xfdcb4fa002162a64,0x8c268cd038370809
 .quad 0x9e9f11c4014dda7f,0xd798180223226505
 .quad 0xc646d63501a1511e,0x4d7e1e02abeafe47
 .quad 0xf7d88bc24209a566,0xe0dda58356e5bdd9
 .quad 0x9ae7575969460760,0xcc8a8772164f96a7
 .quad 0xc1a12d2fc3978938,0xffad294e9be37c51
 .quad 0xf209787bb47d6b85,0x3f9873a242dc5b65
 .quad 0x9745eb4d50ce6333,0x07bf484569c9b91f
 .quad 0xbd176620a501fc00,0x49af1a56c43c2767
 .quad 0xec5d3fa8ce427b00,0x5c1ae0ec754b3141
 .quad 0x93ba47c980e98ce0,0x3990cc93c94efec8
 .quad 0xb8a8d9bbe123f018,0x47f4ffb8bba2be7b
 .quad 0xe6d3102ad96cec1e,0x59f23fa6ea8b6e1a
 .quad 0x9043ea1ac7e41393,0x783767c8529724d0
 .quad 0xb454e4a179dd1878,0xd64541ba673cee04
 .quad 0xe16a1dc9d8545e95,0x0bd69229010c2985
 .quad 0x8ce2529e2734bb1e,0xe7661b59a0a799f3
 .quad 0xb01ae745b101e9e5,0xa13fa23008d18070
 .quad 0xdc21a1171d42645e,0x898f8abc0b05e08c
 .quad 0x899504ae72497ebb,0x95f9b6b586e3ac57
 .quad 0xabfa45da0edbde6a,0xfb782462e89c976d
 .quad 0xd6f8d7509292d604,0xba562d7ba2c3bd49
 .quad 0x865b86925b9bc5c3,0xf475dc6d45ba564d
 .quad 0xa7f26836f282b733,0x719353889728ebe1
 .quad 0xd1ef0244af236500,0xcdf8286abcf326d9
 .quad 0x8335616aed761f20,0x80bb1942b617f847
 .quad 0xa402b9c5a8d3a6e8,0xa0e9df93639df659
 .quad 0xcd036837130890a2,0xc92457783c8573f0
 .quad 0x802221226be55a65,0x3db6b6ab25d36876
 .quad 0xa02aa96b06deb0fe,0x0d246455ef484293
 .quad 0xc83553c5c8965d3e,0x906d7d6b6b1a5338
 .quad 0xfa42a8b73abbf48d,0x3488dcc645e0e806
 .quad 0x9c69a97284b578d8,0x00d589fbebac9104
 .quad 0xc38413cf25e2d70e,0x010aec7ae697b545
 .quad 0xf46518c2ef5b8cd2,0x814da799a03da296
 .quad 0x98bf2f79d5993803,0x10d088c00426859e
 .quad 0xbeeefb584aff8604,0x5504aaf005302705
 .quad 0xeeaaba2e5dbf6785,0x6a45d5ac067c30c7
 .quad 0x952ab45cfa97a0b3,0x226ba58b840d9e7c
 .quad 0xba756174393d88e0,0x6b068eee6511061b
 .quad 0xe912b9d1478ceb18,0x85c832a9fe5547a2
 .quad 0x91abb422ccb812ef,0x539d1faa3ef54cc5
 .quad 0xb616a12b7fe617ab,0xa8846794ceb29ff6
 .quad 0xe39c49765fdf9d95,0x12a5817a025f47f4
 .quad 0x8e41ade9fbebc27e,0xeba770ec417b8cf8
 .quad 0xb1d219647ae6b31d,0xa6914d2751da7037
 .quad 0xde469fbd99a05fe4,0x9035a07126510c44
 .quad 0x8aec23d680043bef,0xda218446b7f2a7ab
 .quad 0xada72ccc20054aea,0x50a9e55865ef5195
 .quad 0xd910f7ff28069da5,0xe4d45eae7f6b25fb
 .quad 0x87aa9aff79042287,0x6f04bb2d0fa2f7bd
 .quad 0xa99541bf57452b29,0xcac5e9f8538bb5ac
 .quad 0xd3fa922f2d1675f3,0xbd776476686ea317
 .quad 0x847c9b5d7c2e09b8,0x966a9eca014525ee
 .quad 0xa59bc234db398c26,0xbc05467c81966f6a
 .quad 0xcf02b2c21207ef2f,0x6b06981ba1fc0b44
 .quad 0x8161afb94b44f57e,0xe2e41f11453d870a
 .quad 0xa1ba1ba79e1632dd,0x9b9d26d5968ce8cd
 .quad 0xca28a291859bbf94,0x8284708afc302301
 .quad 0xfcb2cb35e702af79,0xa3258cadbb3c2bc1
 .quad 0x9defbf01b061adac,0xc5f777ec95059b58
 .quad 0xc56baec21c7a1917,0xf77555e7ba47022f
 .quad 0xf6c69a72a3989f5c,0x7552ab61a8d8c2ba
 .quad 0x9a3c2087a63f639a,0xc953ab1d098779b4
 .quad 0xc0cb28a98fcf3c80,0x7ba895e44be95822
 .quad 0xf0fdf2d3f3c30ba0,0x9a92bb5d5ee3ae2a
 .quad 0x969eb7c47859e744,0x609bb51a5b4e4cda
 .quad 0xbc4665b596706115,0x78c2a260f221e011
 .quad 0xeb57ff22fc0c795a,0x56f34af92eaa5815
 .quad 0x9316ff75dd87cbd9,0xf6580edbbd2a770d
 .quad 0xb7dcbf5354e9becf,0xf3ee1292ac7514d0
 .quad 0xe5d3ef282a242e82,0x70e9973757925a05
 .quad 0x8fa475791a569d11,0x0691fe8296bb7843
 .quad 0xb38d92d760ec4456,0xc8367e233c6a5653
 .quad 0xe070f78d3927556b,0x7a441dac0b84ebe8
 .quad 0x8c469ab843b89563,0x6c6a928b87331371
 .quad 0xaf58416654a6babc,0xc785372e68ffd84d
 .quad 0xdb2e51bfe9d0696b,0xf96684fa033fce61
 .quad 0x88fcf317f22241e3,0xbbe0131c4207e0fc
 .quad 0xab3c2fddeeaad25b,0x2ad817e35289d93c
 .quad 0xd60b3bd56a5586f2,0x758e1ddc272c4f8b
 .quad 0x85c7056562757457,0x0978d2a9987bb1b6
 .quad 0xa738c6bebb12d16d,0x4bd70753fe9a9e24
 .quad 0xd106f86e69d785c8,0x1eccc928fe4145ad
 .quad 0x82a45b450226b39d,0x133ffdb99ee8cb8c
 .quad 0xa34d721642b06085,0xd80ffd2806a2fe6f
 .quad 0xcc20ce9bd35c78a6,0xce13fc72084bbe0b
 .quad 0xff290242c83396cf,0x8198fb8e8a5ead8e
 .quad 0x9f79a169bd203e42,0xf0ff9d39167b2c79
 .quad 0xc75809c42c684dd2,0xad3f84875c19f797
 .quad 0xf92e0c3537826146,0x588f65a93320757d
 .quad 0x9bbcc7a142b17ccc,0x77599f89bff4496e
 .quad 0xc2abf989935ddbff,0x9530076c2ff15bca
 .quad 0xf356f7ebf83552ff,0xfa7c09473bedb2bc
 .quad 0x98165af37b2153df,0x3c8d85cc85748fb5
 .quad 0xbe1bf1b059e9a8d7,0x8bb0e73fa6d1b3a3
 .quad 0xeda2ee1c7064130d,0xee9d210f9086208c
 .quad 0x9485d4d1c63e8be8,0x752234a9ba53d457
 .quad 0xb9a74a0637ce2ee2,0x926ac1d428e8c96d
 .quad 0xe8111c87c5c1ba9a,0x370572493322fbc8
 .quad 0x910ab1d4db9914a1,0xe263676dbff5dd5d
 .quad 0xb54d5e4a127f59c9,0xdafc41492ff354b4
 .quad 0xe2a0b5dc971f303b,0xd1bb519b7bf029e2
 .quad 0x8da471a9de737e25,0xa31513012d761a2d
 .quad 0xb10d8e1456105dae,0x8bda57c178d3a0b8
 .quad 0xdd50f1996b947519,0x2ed0edb1d70888e6
 .quad 0x8a5296ffe33cc930,0x7d42948f26655590
 .quad 0xace73cbfdc0bfb7c,0x9c9339b2effeaaf4
 .quad 0xd8210befd30efa5b,0xc3b8081fabfe55b1
 .quad 0x8714a775e3e95c79,0x9a530513cb7ef58e
 .quad 0xa8d9d1535ce3b397,0x80e7c658be5eb2f2
 .quad 0xd31045a8341ca07d,0xe121b7eeedf65faf
 .quad 0x83ea2b892091e44e,0x6cb512f554b9fbcd
 .quad 0xa4e4b66b68b65d61,0x07e257b2a9e87ac0
 .quad 0xce1de40642e3f4ba,0xc9daed9f54629971
 .quad 0x80d2ae83e9ce78f4,0x3e28d48394bd9fe6
 .quad 0xa1075a24e4421731,0x4db309a479ed07e0
 .quad 0xc94930ae1d529cfd,0x211fcc0d986849d8
 .quad 0xfb9b7cd9a4a7443d,0xe967bf10fe825c4e
 .quad 0x9d412e0806e88aa6,0x71e0d76a9f1179b1
 .quad 0xc491798a08a2ad4f,0x0e590d4546d5d81d
 .quad 0xf5b5d7ec8acb58a3,0x51ef5096988b4e24
 .quad 0x9991a6f3d6bf1766,0x5335925e1f5710d6
 .quad 0xbff610b0cc6edd40,0xe802f6f5a72cd50c
 .quad 0xeff394dcff8a948f,0x2203b4b310f80a4f
 .quad 0x95f83d0a1fb69cda,0xb54250efea9b0671
 .quad 0xbb764c4ca7a44410,0x6292e52be541c80e
 .quad 0xea53df5fd18d5514,0x7b379e76de923a12
 .quad 0x92746b9be2f8552d,0xcd02c30a4b1b644b
 .quad 0xb7118682dbb66a78,0xc04373ccdde23d5e
 .quad 0xe4d5e82392a40516,0xf05450c0155accb5
 .quad 0x8f05b1163ba6832e,0xd634b2780d58bff1
 .quad 0xb2c71d5bca9023f9,0x8bc1df1610aeefed
 .quad 0xdf78e4b2bd342cf7,0x6eb256db94daabe9
 .quad 0x8bab8eefb6409c1b,0xe52f76493d08ab71
 .quad 0xae9672aba3d0c321,0x5e7b53db8c4ad64e
 .quad 0xda3c0f568cc4f3e9,0x361a28d26f5d8be1
 .quad 0x8865899617fb1872,0x81d05983859a776d
 .quad 0xaa7eebfb9df9de8e,0x22446fe467011548
 .quad 0xd51ea6fa85785632,0xaad58bdd80c15a9a
 .quad 0x8533285c936b35df,0x2ac5776a7078d8a0
 .quad 0xa67ff273b8460357,0x7576d5450c970ec8
 .quad 0xd01fef10a657842d,0xd2d48a964fbcd27a
 .quad 0x8213f56a67f6b29c,0x63c4d69df1d6038c
 .quad 0xa298f2c501f45f43,0x7cb60c456e4b8470
 .quad 0xcb3f2f7642717714,0xdbe38f56c9de658c
 .quad 0xfe0efb53d30dd4d8,0x12dc732c7c55feef
 .quad 0x9ec95d1463e8a507,0x0bc9c7fbcdb5bf55
 .quad 0xc67bb4597ce2ce49,0x4ebc39fac1232f2a
 .quad 0xf81aa16fdc1b81db,0x226b4879716bfaf5
 .quad 0x9b10a4e5e9913129,0x35830d4be6e37cd9
 .quad 0xc1d4ce1f63f57d73,0x02e3d09ee09c5c0f
 .quad 0xf24a01a73cf2dcd0,0x439cc4c698c37313
 .quad 0x976e41088617ca02,0x2a41fafc1f7a27ec
 .quad 0xbd49d14aa79dbc83,0xb4d279bb2758b1e7
 .quad 0xec9c459d51852ba3,0x22071829f12ede61
 .quad 0x93e1ab8252f33b46,0x35446f1a36bd4afc
 .quad 0xb8da1662e7b00a18,0xc2958ae0c46c9dbc
 .quad 0xe7109bfba19c0c9e,0xf33aed98f587c52b
 .quad 0x906a617d450187e3,0xd804d47f9974db3a
 .quad 0xb484f9dc9641e9db,0x4e06099f7fd21209
 .quad 0xe1a63853bbd26452,0xa1878c075fc6968c
 .quad 0x8d07e33455637eb3,0x24f4b7849bdc1e17
 .quad 0xb049dc016abc5e60,0x6e31e565c2d3259d
 .quad 0xdc5c5301c56b75f8,0x89be5ebf3387ef04
 .quad 0x89b9b3e11b6329bb,0x5616fb378034f562
 .quad 0xac2820d9623bf42a,0xab9cba05604232bb
 .quad 0xd732290fbacaf134,0x5683e886b852bf6a
 .quad 0x867f59a9d4bed6c1,0xb61271543333b7a2
 .quad 0xa81f301449ee8c71,0xa3970da94000a58b
 .quad 0xd226fc195c6a2f8d,0x8c7cd1139000ceee
 .quad 0x83585d8fd9c25db8,0x37ce02ac3a008154
 .quad 0xa42e74f3d032f526,0x45c183574880a1aa
 .quad 0xcd3a1230c43fb270,0xd731e42d1aa0ca14
 .quad 0x80444b5e7aa7cf86,0x867f2e9c30a47e4c
 .quad 0xa0555e361951c367,0x281efa433ccd9de0
 .quad 0xc86ab5c39fa63441,0x7226b8d40c010558
 .quad 0xfa856334878fc151,0x4eb067090f0146ae
 .quad 0x9c935e00d4b9d8d3,0x912e4065a960cc2c
 .quad 0xc3b8358109e84f08,0xf579d07f13b8ff37
 .quad 0xf4a642e14c6262c9,0x32d8449ed8a73f05
 .quad 0x98e7e9cccfbd7dbe,0x7fc72ae347688763
 .quad 0xbf21e44003acdd2d,0x1fb8f59c1942a93c
 .quad 0xeeea5d5004981479,0xe7a733031f93538b
 .quad 0x95527a5202df0ccc,0xf0c87fe1f3bc1437
 .quad 0xbaa718e68396cffe,0x2cfa9fda70ab1945
 .quad 0xe950df20247c83fe,0xb83947d10cd5df96
 .quad 0x91d28b7416cdd27f,0xb323cce2a805abbe
 .quad 0xb6472e511c81471e,0x1fecc01b520716ad
 .quad 0xe3d8f9e563a198e6,0xa7e7f0222688dc59
 .quad 0x8e679c2f5e44ff90,0xa8f0f615581589b7
 .quad 0xb201833b35d63f74,0xd32d339aae1aec25
 .quad 0xde81e40a034bcf50,0x07f8808159a1a72e
 .quad 0x8b112e86420f6192,0x04fb5050d805087d
 .quad 0xadd57a27d29339f7,0x863a24650e064a9c
 .quad 0xd94ad8b1c7380875,0xe7c8ad7e5187dd43
 .quad 0x87cec76f1c830549,0x70dd6c6ef2f4ea4a
 .quad 0xa9c2794ae3a3c69b,0x4d14c78aafb224dd
 .quad 0xd433179d9c8cb842,0xa059f96d5b9eae14
 .quad 0x849feec281d7f329,0x24383be459432ccc
 .quad 0xa5c7ea73224deff4,0xed464add6f93f7ff
 .quad 0xcf39e50feae16bf0,0x2897dd94cb78f5ff
 .quad 0x81842f29f2cce376,0x195eea7cff2b99bf
 .quad 0xa1e53af46f801c54,0x9fb6a51c3ef6802f
 .quad 0xca5e89b18b602369,0xc7a44e634eb4203b
 .quad 0xfcf62c1dee382c43,0xb98d61fc2261284a
 .quad 0x9e19db92b4e31baa,0x93f85d3d957cb92e
 .quad 0xc5a05277621be294,0x38f6748cfadbe77a
 .quad 0xf70867153aa2db39,0x473411b03992e158
 .quad 0x9a65406d44a5c904,0x8c808b0e23fbccd7
 .quad 0xc0fe908895cf3b45,0xafa0add1acfac00d
 .quad 0xf13e34aabb430a16,0x9b88d94618397010
 .quad 0x96c6e0eab509e64e,0xa13587cbcf23e60a
 .quad 0xbc789925624c5fe1,0x4982e9bec2ecdf8d
 .quad 0xeb96bf6ebadf77d9,0x1be3a42e73a81770
 .quad 0x933e37a534cbaae8,0x716e469d08490ea6
 .quad 0xb80dc58e81fe95a2,0x8dc9d8444a5b524f
 .quad 0xe61136f2227e3b0a,0x313c4e555cf226e3
 .quad 0x8fcac257558ee4e7,0xdec5b0f55a17584e
 .quad 0xb3bd72ed2af29e20,0x56771d32b09d2e62
 .quad 0xe0accfa875af45a8,0x6c14e47f5cc479fa
 .quad 0x8c6c01c9498d8b89,0x438d0ecf99facc3c
 .quad 0xaf87023b9bf0ee6b,0x1470528380797f4b
 .quad 0xdb68c2ca82ed2a06,0x598c67246097df1e
 .quad 0x892179be91d43a44,0x77f7c076bc5eeb73
 .quad 0xab69d82e364948d5,0x95f5b0946b76a64f
 .quad 0xd6444e39c3db9b0a,0x7b731cb986544fe3
 .quad 0x85eab0e41a6940e6,0x0d27f1f3f3f4b1ee
 .quad 0xa7655d1d21039120,0x9071ee70f0f1de6a
 .quad 0xd13eb46469447568,0xb48e6a0d2d2e5604
