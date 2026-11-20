# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# The TLS runtime: the arithmetic on large numbers and the two record
# ciphers that TLS needs, emitted once per program as an extra
# function-table entry. RDI is a block of 64-bit words; word 0 says what to
# do and the other words, at the byte offsets given, are its operands. The
# result is in RAX (0 where none is named). RBX, RBP and R12-R15 are kept,
# every other register and all of XMM is scratch, the stack need not be
# aligned, and nothing is allocated: scratch stands on the stack (under
# 24 KiB at the largest size). There are no relocations and no system calls.
#
# A large number is k limbs of 64 bits, the least significant first, k from
# 1 to 128. A Montgomery context for an odd modulus m > 1 is 16+24k bytes
# that the caller provides: 0 k, 8 n0 = -1/m mod 2**64, 16 m, 16+8k
# RR = R*R mod m, 16+16k R mod m (the Montgomery form of 1), R = 2**(64k).
#
#   0  features: RAX is 1 when the processor has AES-NI, PCLMULQDQ and
#      SSSE3, else 0
#   1  mont_setup: 8 ctx, 16 m, 24 k. Fills the context
#   2  mont_mul: 8 ctx, 16 r, 24 a, 32 b. r = a*b/R mod m, fully reduced,
#      for one of a and b under m and the other under R
#   3  mod_add: 8 ctx, 16 r, 24 a, 32 b. r = a+b mod m for a, b < m
#   4  mod_sub: 8 ctx, 16 r, 24 a, 32 b. r = a-b mod m for a, b < m
#   5  mod_exp: 8 ctx, 16 r, 24 base, 32 exponent, 40 bits. r = base**e
#      mod m, neither in Montgomery form, base < m, e the low `bits` bits
#      of the exponent's limbs (only the limbs holding them are read);
#      bits 0 gives 1 mod m
#   6  cswap: 8 a, 16 b, 24 k, 32 bit. Exchanges the k limbs when bit is
#      1, leaves them when it is 0
#   7  reduce: 8 ctx, 16 r, 24 a, 32 n. r = a mod m, a being n limbs,
#      n from 1 to 2k (limbs past 2k are ignored)
#   8  be2le: 8 limbs, 16 k, 24 bytes, 32 n. The k limbs of the big-endian
#      number of n bytes. Bytes that do not fit (the leading n-8k) are
#      dropped and RAX is 1 when any of them is not zero, else 0
#   9  le2be: 8 bytes, 16 n, 24 limbs, 32 k. The n big-endian bytes of the
#      number, zeros in front; what does not fit in n bytes is dropped
#   10 compare: 8 a, 16 b, 24 k. RAX is 0 when a = b, 1 when a > b and -1
#      when a < b
#   16 aes_setup: 8 ctx (512 bytes), 16 key, 24 its length (16 or 32),
#      32 force (1 takes the software cipher whatever the processor has).
#      RAX is 1, or 0 for another key length (nothing is written)
#   17 gcm_seal: 8 ctx, 16 nonce (12 bytes), 24 aad, 32 its length, 40 in,
#      48 its length, 56 out, 64 tag (16 bytes, written). RAX is 1
#   18 gcm_open: the same block, 64 the tag to check. RAX is 1 and the
#      plaintext is at out when the tag is right; else RAX is 0 and out
#      is untouched
#   20 chacha_seal: 8 key (32 bytes), 16 nonce (12 bytes), 24 aad, 32 its
#      length, 40 in, 48 its length, 56 out, 64 tag (16 bytes, written).
#      RAX is 1
#   21 chacha_open: the same block, 64 the tag to check; RAX as for 18
#   22 cbc_encrypt: 8 ctx (of 16), 16 iv (16 bytes, only read), 24 in,
#      32 its length (a multiple of 16), 40 out. AES-CBC with no padding.
#      RAX is 1, or 0 when the length is no multiple of 16 (nothing is
#      written)
#   23 cbc_decrypt: the same block
#
# Any other word 0 does nothing and gives 0.
#
# In 2 to 5 and 7 r may be the address of any operand; in 6 a and b are
# apart or the same; in 8 and 9 the two areas are apart. In 17 to 23 out
# is in or does not overlap it, and every length may be 0 (its address is
# then not read).
#
# 2 to 6 and 10 run in a time and touch addresses that depend on k alone,
# and 5 on k and `bits` alone: a Montgomery product is the word-by-word
# form with one masked subtraction, the power takes the exponent four bits
# at a time and reads all sixteen powers for every digit. 1, 7, 8 and 9
# depend on the sizes only as well.
#
# The AES context: 0 rounds (10 or 14), 8 which cipher (1 AES-NI and
# PCLMULQDQ, 0 software), 16 the round keys, 256 the GHASH key
# H = AES_K(0) with its sixteen bytes reversed. The software cipher looks
# nothing up by a secret: SubBytes is the inverse in GF(2**8) as x**254
# on all sixteen bytes at once in SSE2 and the affine map, ShiftRows and
# MixColumns are shuffles and shifts, and GHASH multiplies bit by bit
# under masks. The key schedule is that SubBytes for both ciphers. A tag
# is compared whole before the one branch on it. Deciphering (23) uses
# the same context: in software the inverse cipher with InvSubBytes as
# the inverse affine map and the same x**254, InvShiftRows and
# InvMixColumns as the forward ones three times over, so it too looks
# nothing up; with AES-NI AESDEC under round keys turned by AESIMC at
# each call, four blocks abreast. 22 and 23 run in a time that depends on
# the length and the cipher chosen alone.
#
# The frame, 304 bytes at R14, cleared on the way out of 16 to 23: 0 the
# counter block, 16 the GHASH state, 32 a block being padded, 48 the tag,
# 64 the ChaCha state, 128 key stream, 192 Poly1305's r, 208 its h,
# 232 r1*5/4, 240 its s, 256 opening, 264 what absorbs a block, 272 what
# makes the tag, 280 what makes key stream, 288 how much it makes. The
# scratch of 1 to 7 is not cleared, but for the powers of 5 and the
# halves of 7.
.intel_syntax noprefix
.text
.equ F_CTR,0
.equ F_Y,16
.equ F_TMP,32
.equ F_TAG,48
.equ F_ST,64
.equ F_KS,128
.equ F_R0,192
.equ F_R1,200
.equ F_H0,208
.equ F_H1,216
.equ F_H2,224
.equ F_S1,232
.equ F_PAD,240
.equ F_OPEN,256
.equ F_BLK,264
.equ F_FIN,272
.equ F_GEN,280
.equ F_BS,288
.equ F_SIZE,304
 push rbx
 push rbp
 push r12
 push r13
 push r14
 push r15
 mov r15,rdi
 mov rbp,rsp
 sub rsp,F_SIZE
 and rsp,-16
 mov r14,rsp
 xor eax,eax
 mov rcx,[r15]
 cmp rcx,23
 ja tq_out
 lea rdx,[rip+tq_table]
 movsx rcx,word ptr [rdx+rcx*2]
 add rcx,rdx
 call rcx
tq_out:
 cmp qword ptr [r15],16
 jb 1f
 # the frame held keys and key stream
 mov rdx,rax
 lea rdi,[rbp-F_SIZE]
 and rdi,-16
 mov ecx,F_SIZE/8
 xor eax,eax
 rep stosq
 mov rax,rdx
1:
 mov rsp,rbp
 pop r15
 pop r14
 pop r13
 pop r12
 pop rbp
 pop rbx
tq_nop:
 ret

# ---- large numbers ----
# R12 is the context and R13 k throughout.
tq_args:
 mov rdi,[r15+16]
 mov rsi,[r15+24]
 mov rdx,[r15+32]
tq_ctx:
 mov r12,[r15+8]
 mov r13,[r12]
 ret

tq_op_mul:
 call tq_args
 call tq_mmul
 jmp tq_zero
tq_op_add:
 call tq_args
 call tq_madd
tq_zero:
 xor eax,eax
 ret

# [RDI] = [RSI]*[RDX]/R mod m. RBX, RBP and R12-R15 are kept. t, k+2
# limbs on the stack, takes a*b[i] and then the multiple of m that clears
# its lowest limb, one limb of b at a time; it ends under 2m.
tq_mmul:
 push rbx
 push rbp
 mov rbp,rsp
 lea rax,[r13*8+16]
 sub rsp,rax
 mov r9,rdx
 mov r10,rdi
 lea rcx,[r13+2]
 xor eax,eax
1:
 mov [rsp+rcx*8-8],rax
 dec rcx
 jnz 1b
 xor r11d,r11d
1:
 mov r8,[r9+r11*8]
 xor ecx,ecx
 xor ebx,ebx
2:
 mov rax,[rsi+rbx*8]
 mul r8
 add rax,rcx
 adc rdx,0
 add [rsp+rbx*8],rax
 adc rdx,0
 mov rcx,rdx
 inc rbx
 cmp rbx,r13
 jb 2b
 add [rsp+r13*8],rcx
 adc qword ptr [rsp+r13*8+8],0
 mov r8,[rsp]
 imul r8,[r12+8]
 mov rax,[r12+16]
 mul r8
 add rax,[rsp]
 adc rdx,0
 mov rcx,rdx
 mov ebx,1
 jmp 4f
3:
 mov rax,[r12+rbx*8+16]
 mul r8
 add rax,rcx
 adc rdx,0
 add rax,[rsp+rbx*8]
 adc rdx,0
 mov [rsp+rbx*8-8],rax
 mov rcx,rdx
 inc rbx
4:
 cmp rbx,r13
 jb 3b
 xor eax,eax
 add rcx,[rsp+r13*8]
 adc rax,[rsp+r13*8+8]
 mov [rsp+r13*8-8],rcx
 mov [rsp+r13*8],rax
 mov qword ptr [rsp+r13*8+8],0
 inc r11
 cmp r11,r13
 jb 1b
# t, k+1 limbs at RSP and under 2m, less m when it is not under m, to
# [R10]: t-m is written and t put back under a mask.
tq_fin:
 xor ebx,ebx
 mov rcx,r13
1:
 mov rax,[rsp+rbx*8]
 sbb rax,[r12+rbx*8+16]
 mov [r10+rbx*8],rax
 lea rbx,[rbx+1]
 dec rcx
 jnz 1b
 mov rax,[rsp+r13*8]
 sbb rax,0
 sbb rax,rax
 xor ebx,ebx
2:
 mov rcx,[rsp+rbx*8]
 mov rdx,[r10+rbx*8]
 xor rcx,rdx
 and rcx,rax
 xor rdx,rcx
 mov [r10+rbx*8],rdx
 inc rbx
 cmp rbx,r13
 jb 2b
 mov rsp,rbp
 pop rbp
 pop rbx
 ret

# [RDI] = [RSI]+[RDX] mod m
tq_madd:
 push rbx
 push rbp
 mov rbp,rsp
 lea rax,[r13*8+16]
 sub rsp,rax
 mov r10,rdi
 xor ebx,ebx
 mov rcx,r13
1:
 mov rax,[rsi+rbx*8]
 adc rax,[rdx+rbx*8]
 mov [rsp+rbx*8],rax
 lea rbx,[rbx+1]
 dec rcx
 jnz 1b
 mov eax,0
 adc eax,eax
 mov [rsp+r13*8],rax
 jmp tq_fin

tq_op_sub:
 call tq_args
 xor ecx,ecx
 mov r8,r13
1:
 mov rax,[rsi+rcx*8]
 sbb rax,[rdx+rcx*8]
 mov [rdi+rcx*8],rax
 lea rcx,[rcx+1]
 dec r8
 jnz 1b
 # m comes back under a mask when that borrowed; R10 is the carry
 sbb r9,r9
 xor ecx,ecx
 xor r10d,r10d
2:
 mov rax,[r12+rcx*8+16]
 and rax,r9
 xor edx,edx
 add rax,r10
 adc edx,edx
 add [rdi+rcx*8],rax
 adc edx,0
 mov r10,rdx
 inc rcx
 cmp rcx,r13
 jb 2b
 jmp tq_zero

# [RDI] = 1
tq_one:
 mov rcx,r13
 xor eax,eax
 rep stosq
 mov rax,r13
 neg rax
 mov qword ptr [rdi+rax*8],1
 ret

tq_op_setup:
 mov r12,[r15+8]
 mov r13,[r15+24]
 mov [r12],r13
 lea rdi,[r12+16]
 mov rsi,[r15+16]
 mov rcx,r13
 rep movsq
 # 1/m mod 2**64: m is its own inverse mod 8, and each step doubles
 # the bits that are right
 mov rcx,[r12+16]
 mov rax,rcx
 mov edx,5
1:
 mov r8,rax
 imul r8,rcx
 neg r8
 add r8,2
 imul rax,r8
 dec edx
 jnz 1b
 neg rax
 mov [r12+8],rax
 # R mod m is 1 doubled 64k times; k doublings more is the Montgomery
 # form of 2**k, and six squarings of that the form of R, which is RR
 lea r14,[r13*8]
 lea rbx,[r12+r14*2+16]
 mov rdi,rbx
 call tq_one
 mov rax,r13
 shl rax,6
 call tq_double
 lea rsi,[r12+r14*2+16]
 lea rbx,[r12+r14+16]
 mov rdi,rbx
 mov rcx,r13
 rep movsq
 mov rax,r13
 call tq_double
 mov eax,6
1:
 push rax
 push rax
 mov rdi,rbx
 mov rsi,rbx
 mov rdx,rbx
 call tq_mmul
 pop rax
 pop rax
 dec eax
 jnz 1b
 ret
# [RBX] doubled RAX times mod m
tq_double:
 push rax
 mov rdi,rbx
 mov rsi,rbx
 mov rdx,rbx
 call tq_madd
 pop rax
 dec rax
 jnz tq_double
 ret

# The power. On the stack, each of k limbs: the running product at RBX,
# the chosen power after it, then the sixteen powers base**0..15 in
# Montgomery form. R14 is 8k.
tq_op_exp:
 call tq_ctx
 lea r14,[r13*8]
 imul rax,r14,18
 sub rsp,rax
 mov rbx,rsp
 lea rdi,[rbx+r14*2]
 lea rsi,[r12+r14*2+16]
 mov rcx,r13
 rep movsq
 mov rsi,[r15+24]
 lea rdx,[r12+r14+16]
 call tq_mmul
 lea rdi,[rbx+r14*2]
 add rdi,r14
 mov ecx,14
1:
 add rdi,r14
 push rcx
 push rdi
 mov rsi,rdi
 sub rsi,r14
 lea rdx,[rbx+r14*2]
 add rdx,r14
 call tq_mmul
 pop rdi
 pop rcx
 dec ecx
 jnz 1b
 mov rdi,rbx
 lea rsi,[rbx+r14*2]
 mov rcx,r13
 rep movsq
 mov rax,[r15+40]
 add rax,3
 shr rax,2
2:
 # RAX digits are left
 test rax,rax
 jz 8f
 dec rax
 push rax
 mov ecx,4
3:
 push rcx
 mov rdi,rbx
 mov rsi,rbx
 mov rdx,rbx
 call tq_mmul
 pop rcx
 dec ecx
 jnz 3b
 # the digit, without the bits at and past `bits` in the top one
 mov rax,[rsp]
 lea rcx,[rax*4]
 mov rdx,rcx
 shr rdx,6
 mov rsi,[r15+32]
 mov rdx,[rsi+rdx*8]
 shr rdx,cl
 and edx,15
 mov rax,[r15+40]
 sub rax,rcx
 cmp rax,4
 jae 4f
 mov ecx,eax
 mov eax,1
 shl eax,cl
 dec eax
 and edx,eax
4:
 lea rdi,[rbx+r14]
 mov rcx,r13
 xor eax,eax
 rep stosq
 lea rdi,[rbx+r14]
 lea rsi,[rbx+r14*2]
 xor r8d,r8d
5:
 mov rax,r8
 xor rax,rdx
 sub rax,1
 sbb rax,rax
 xor ecx,ecx
6:
 mov r9,[rsi+rcx*8]
 and r9,rax
 or [rdi+rcx*8],r9
 inc rcx
 cmp rcx,r13
 jb 6b
 add rsi,r14
 inc r8d
 cmp r8d,16
 jb 5b
 mov rdx,rdi
 mov rdi,rbx
 mov rsi,rbx
 call tq_mmul
 pop rax
 jmp 2b
8:
 lea rdi,[rbx+r14]
 call tq_one
 mov rdi,[r15+16]
 mov rsi,rbx
 lea rdx,[rbx+r14]
 call tq_mmul
 lea rcx,[r13+r13*8]
 add rcx,rcx
# RCX limbs at RBX are cleared and the operation is over
tq_wipe:
 mov rdi,rbx
 xor eax,eax
 rep stosq
 jmp tq_out

# a = L + H*R, each half under R: L*RR/R is L*R, that times 1 over R is
# L mod m, and H*RR/R is H*R mod m. The stack has L, H and a 1.
tq_op_reduce:
 call tq_ctx
 lea r14,[r13*8]
 lea rax,[r14+r14*2]
 sub rsp,rax
 mov rbx,rsp
 mov rdi,rbx
 lea rcx,[r13+r13*2]
 xor eax,eax
 rep stosq
 mov qword ptr [rbx+r14*2],1
 mov rsi,[r15+24]
 mov rdi,rbx
 mov rcx,[r15+32]
 lea rax,[r13+r13]
 cmp rcx,rax
 cmova rcx,rax
 rep movsq
 mov rdi,rbx
 mov rsi,rbx
 lea rdx,[r12+r14+16]
 call tq_mmul
 mov rdi,rbx
 mov rsi,rbx
 lea rdx,[rbx+r14*2]
 call tq_mmul
 lea rdi,[rbx+r14]
 mov rsi,rdi
 lea rdx,[r12+r14+16]
 call tq_mmul
 mov rdi,[r15+16]
 mov rsi,rbx
 lea rdx,[rbx+r14]
 call tq_madd
 lea rcx,[r13+r13*2]
 jmp tq_wipe

tq_op_cswap:
 mov rdi,[r15+8]
 mov rsi,[r15+16]
 mov rcx,[r15+24]
 mov rdx,[r15+32]
 neg rdx
1:
 mov rax,[rdi+rcx*8-8]
 mov r8,[rsi+rcx*8-8]
 mov r9,rax
 xor r9,r8
 and r9,rdx
 xor rax,r9
 xor r8,r9
 mov [rdi+rcx*8-8],rax
 mov [rsi+rcx*8-8],r8
 dec rcx
 jnz 1b
 jmp tq_zero

tq_op_compare:
 mov rdi,[r15+8]
 mov rsi,[r15+16]
 mov rcx,[r15+24]
 xor eax,eax
 mov r9d,1
 mov r10,-1
 xor edx,edx
1:
 mov r8,[rdi+rdx*8]
 cmp r8,[rsi+rdx*8]
 cmova rax,r9
 cmovb rax,r10
 inc rdx
 cmp rdx,rcx
 jb 1b
 ret

tq_op_be2le:
 mov rdi,[r15+8]
 mov rcx,[r15+16]
 shl rcx,3
 mov rsi,[r15+24]
 mov rdx,[r15+32]
 xor r8d,r8d
 xor eax,eax
1:
 cmp r8,rcx
 jae 3f
 xor r9d,r9d
 cmp r8,rdx
 jae 2f
 mov r10,rdx
 sub r10,r8
 movzx r9d,byte ptr [rsi+r10-1]
2:
 mov [rdi+r8],r9b
 inc r8
 jmp 1b
3:
 sub rdx,rcx
 jbe 5f
4:
 or al,[rsi+rdx-1]
 dec rdx
 jnz 4b
5:
 neg al
 sbb eax,eax
 neg eax
 ret

tq_op_le2be:
 mov rdi,[r15+8]
 mov rdx,[r15+16]
 mov rsi,[r15+24]
 mov rcx,[r15+32]
 shl rcx,3
 xor r8d,r8d
1:
 cmp r8,rdx
 jae tq_zero
 xor eax,eax
 cmp r8,rcx
 jae 2f
 mov al,[rsi+r8]
2:
 mov r10,rdx
 sub r10,r8
 mov [rdi+r10-1],al
 inc r8
 jmp 1b

# ---- AES ----
tq_op_feat:
 mov eax,1
 cpuid
 and ecx,0x02000202
 xor eax,eax
 cmp ecx,0x02000202
 sete al
 ret

# The product of the bytes of XMM1 and XMM3 in GF(2**8) to XMM1; XMM6 is
# sixteen 0x1b. XMM3-XMM5 and EAX are spent.
tq_gmul:
 movdqa xmm4,xmm1
 pxor xmm1,xmm1
 mov eax,8
1:
 pxor xmm5,xmm5
 pcmpgtb xmm5,xmm1
 paddb xmm1,xmm1
 pand xmm5,xmm6
 pxor xmm1,xmm5
 pxor xmm5,xmm5
 pcmpgtb xmm5,xmm3
 paddb xmm3,xmm3
 pand xmm5,xmm4
 pxor xmm1,xmm5
 dec eax
 jnz 1b
 ret

# The inverse in GF(2**8) of the bytes of XMM0 to XMM1: x**254 by six
# times squaring and multiplying by x and one squaring more. XMM2-XMM6,
# EAX and ECX are spent; XMM6 is left sixteen 0x1b.
tq_inv:
 movdqu xmm6,[rip+tq_k1b]
 movdqa xmm2,xmm0
 movdqa xmm1,xmm0
 mov ecx,6
1:
 movdqa xmm3,xmm1
 call tq_gmul
 movdqa xmm3,xmm2
 call tq_gmul
 dec ecx
 jnz 1b
 movdqa xmm3,xmm1
 jmp tq_gmul

# The bytes of XMM1 turned left one bit; XMM5 is spent
.macro TQ_ROL1
 pxor xmm5,xmm5
 pcmpgtb xmm5,xmm1
 paddb xmm1,xmm1
 psubb xmm1,xmm5
.endm

# SubBytes of XMM0: the inverse, then the sum of the byte, its four
# rotations and 0x63. XMM1-XMM6, EAX and ECX are spent.
tq_sbox:
 call tq_inv
 movdqu xmm0,[rip+tq_k63]
 pxor xmm0,xmm1
 mov eax,4
1:
 TQ_ROL1
 pxor xmm0,xmm1
 dec eax
 jnz 1b
 ret

# InvSubBytes of XMM0: the sum of the byte turned left by 1, 3 and 6 and
# 0x05, then the inverse. EAX counts the six turns, a set bit for each one
# that is taken.
tq_isbox:
 movdqa xmm1,xmm0
 mov eax,0x05050505
 movd xmm0,eax
 pshufd xmm0,xmm0,0
 mov eax,0x25
1:
 TQ_ROL1
 shr eax,1
 jnc 2f
 pxor xmm0,xmm1
2:
 jnz 1b
 call tq_inv
 movdqa xmm0,xmm1
 ret

tq_subw:
 movd xmm0,eax
 call tq_sbox
 movd eax,xmm0
 ret

# ShiftRows of XMM0: row r of each column comes from r columns on. XMM1,
# XMM2 and XMM7 are spent.
tq_rows:
 movdqu xmm7,[rip+tq_krow]
 movdqa xmm1,xmm0
 pand xmm1,xmm7
 .irp s,0x39,0x4e,0x93
 pshufd xmm2,xmm0,\s
 pslld xmm7,8
 pand xmm2,xmm7
 por xmm1,xmm2
 .endr
 movdqa xmm0,xmm1
 ret

.macro TQ_ROT8
 movdqa xmm2,xmm1
 psrld xmm1,8
 pslld xmm2,24
 por xmm1,xmm2
.endm
# MixColumns of XMM0: with x' the column turned by one row,
# 2(x+x') + x' + x'' + x'''. XMM6 is sixteen 0x1b; XMM1, XMM2 and XMM5
# are spent.
tq_mix:
 movdqa xmm1,xmm0
 TQ_ROT8
 pxor xmm0,xmm1
 pxor xmm5,xmm5
 pcmpgtb xmm5,xmm0
 paddb xmm0,xmm0
 pand xmm5,xmm6
 pxor xmm0,xmm5
 pxor xmm0,xmm1
 TQ_ROT8
 pxor xmm0,xmm1
 TQ_ROT8
 pxor xmm0,xmm1
 ret

# XMM0 enciphered under the context at R12. RAX, RCX, RDX, R8 and
# XMM1-XMM7 are spent, nothing else.
tq_aes:
 cmp qword ptr [r12+8],0
 jne tq_ni4
 lea rdx,[r12+16]
 mov r8d,[r12]
 movdqu xmm7,[rdx]
 pxor xmm0,xmm7
1:
 add rdx,16
 call tq_sbox
 call tq_rows
 dec r8d
 jz 2f
 call tq_mix
2:
 movdqu xmm7,[rdx]
 pxor xmm0,xmm7
 test r8d,r8d
 jnz 1b
 ret

# XMM0 deciphered, the same registers spent. ShiftRows three times over
# is its inverse and so is MixColumns, each being the identity when done
# four times.
tq_aesd:
 cmp qword ptr [r12+8],0
 jne tq_ni4d
 mov r8d,[r12]
 mov rdx,r8
 shl rdx,4
 lea rdx,[r12+rdx+16]
 movdqu xmm7,[rdx]
 pxor xmm0,xmm7
1:
 call tq_rows
 call tq_rows
 call tq_rows
 call tq_isbox
 sub rdx,16
 movdqu xmm7,[rdx]
 pxor xmm0,xmm7
 dec r8d
 jz 2f
 call tq_mix
 call tq_mix
 call tq_mix
 jmp 1b
2:
 ret

# XMM0-XMM3 deciphered with AES-NI, the round keys taken from the last
# and turned by AESIMC as they come; RDX, ECX and XMM4 are spent
tq_ni4d:
 mov ecx,[r12]
 mov rdx,rcx
 shl rdx,4
 lea rdx,[r12+rdx+16]
 movdqu xmm4,[rdx]
 .irp i,0,1,2,3
 pxor xmm\i,xmm4
 .endr
1:
 sub rdx,16
 movdqu xmm4,[rdx]
 dec ecx
 jz 2f
 aesimc xmm4,xmm4
 .irp i,0,1,2,3
 aesdec xmm\i,xmm4
 .endr
 jmp 1b
2:
 .irp i,0,1,2,3
 aesdeclast xmm\i,xmm4
 .endr
 ret

# ---- CBC ----
# The frame has the block before at 32 and, deciphering, the ciphertext
# at 128, so that out may be in.
tq_op_cbc:
 mov r12,[r15+8]
 mov rbx,[r15+32]
 xor eax,eax
 test bl,15
 jnz 9f
 mov rsi,[r15+16]
 movdqu xmm0,[rsi]
 movdqa [r14+F_TMP],xmm0
 mov rsi,[r15+24]
 mov rdi,[r15+40]
 cmp qword ptr [r15],22
 jne 3f
1:
 test rbx,rbx
 jz 8f
 movdqu xmm0,[rsi]
 pxor xmm0,[r14+F_TMP]
 call tq_aes
 movdqa [r14+F_TMP],xmm0
 movdqu [rdi],xmm0
 add rsi,16
 add rdi,16
 sub rbx,16
 jmp 1b
3:
 # four blocks at a time while AES-NI has them
 cmp qword ptr [r12+8],0
 je 5f
4:
 cmp rbx,64
 jb 5f
 .irp i,0,1,2,3
 movdqu xmm\i,[rsi+16*\i]
 movdqa [r14+F_KS+16*\i],xmm\i
 .endr
 call tq_ni4d
 pxor xmm0,[r14+F_TMP]
 pxor xmm1,[r14+F_KS]
 pxor xmm2,[r14+F_KS+16]
 pxor xmm3,[r14+F_KS+32]
 movdqa xmm4,[r14+F_KS+48]
 movdqa [r14+F_TMP],xmm4
 .irp i,0,1,2,3
 movdqu [rdi+16*\i],xmm\i
 .endr
 add rsi,64
 add rdi,64
 sub rbx,64
 jmp 4b
5:
 test rbx,rbx
 jz 8f
 movdqu xmm0,[rsi]
 movdqa [r14+F_KS],xmm0
 call tq_aesd
 pxor xmm0,[r14+F_TMP]
 movdqa xmm4,[r14+F_KS]
 movdqa [r14+F_TMP],xmm4
 movdqu [rdi],xmm0
 add rsi,16
 add rdi,16
 sub rbx,16
 jmp 5b
8:
 mov eax,1
9:
 ret

# XMM0-XMM3 enciphered with AES-NI; RDX, ECX and XMM4 are spent
tq_ni4:
 lea rdx,[r12+16]
 mov ecx,[r12]
 movdqu xmm4,[rdx]
 .irp i,0,1,2,3
 pxor xmm\i,xmm4
 .endr
1:
 add rdx,16
 movdqu xmm4,[rdx]
 dec ecx
 jz 2f
 .irp i,0,1,2,3
 aesenc xmm\i,xmm4
 .endr
 jmp 1b
2:
 .irp i,0,1,2,3
 aesenclast xmm\i,xmm4
 .endr
 ret

tq_op_aes:
 mov r12,[r15+8]
 mov rsi,[r15+16]
 mov rdx,[r15+24]
 xor eax,eax
 cmp rdx,16
 je 1f
 cmp rdx,32
 jne tq_nop
1:
 # RBX words of key, R13 words in all, R9 the word being made and R10
 # the round constant
 mov ebx,edx
 shr ebx,2
 lea eax,[rbx+6]
 mov [r12],rax
 lea rdi,[r12+16]
 mov ecx,edx
 rep movsb
 lea r13d,[rbx*4+28]
 mov r9d,ebx
 mov r10d,1
1:
 mov eax,[r12+r9*4+12]
 lea edx,[rbx-1]
 and edx,r9d
 jnz 2f
 ror eax,8
 call tq_subw
 xor eax,r10d
 add r10d,r10d
 cmp r10d,0x100
 jb 3f
 xor r10d,0x11b
 jmp 3f
2:
 cmp edx,4
 jne 3f
 call tq_subw
3:
 mov rcx,r9
 sub rcx,rbx
 xor eax,[r12+rcx*4+16]
 mov [r12+r9*4+16],eax
 inc r9d
 cmp r9d,r13d
 jb 1b
 xor eax,eax
 cmp qword ptr [r15+32],0
 jne 4f
 call tq_op_feat
4:
 mov [r12+8],rax
 pxor xmm0,xmm0
 call tq_aes
 movdqa [r14],xmm0
 mov rax,[r14]
 bswap rax
 mov [r12+264],rax
 mov rax,[r14+8]
 bswap rax
 mov [r12+256],rax
 mov eax,1
 ret

# ---- GCM ----
tq_op_gcm:
 mov r12,[r15+8]
 mov rsi,[r15+16]
 mov rax,[rsi]
 mov [r14],rax
 mov eax,[rsi+8]
 mov [r14+8],eax
 mov dword ptr [r14+12],0x01000000
 pxor xmm0,xmm0
 movdqa [r14+F_Y],xmm0
 lea rax,[rip+tq_ghash_sw]
 lea rdx,[rip+tq_gen_sw]
 mov ecx,16
 cmp qword ptr [r12+8],0
 je 1f
 lea rax,[rip+tq_ghash_ni]
 lea rdx,[rip+tq_gen_ni]
 mov ecx,64
1:
 lea rsi,[rip+tq_gcm_fin]
 mov rdi,18
# RAX absorbs a block, RDX makes RCX bytes of key stream, RSI makes the
# tag and RDI is the opening operation.
tq_aead:
 mov [r14+F_BLK],rax
 mov [r14+F_GEN],rdx
 mov [r14+F_BS],rcx
 mov [r14+F_FIN],rsi
 xor eax,eax
 cmp rdi,[r15]
 sete al
 mov [r14+F_OPEN],rax
 mov rsi,[r15+24]
 mov rdx,[r15+32]
 call tq_absorb
 cmp qword ptr [r14+F_OPEN],0
 je 2f
 # the tag is over the ciphertext, so it is known before any of it is
 # deciphered
 mov rsi,[r15+40]
 mov rdx,[r15+48]
 call tq_absorb
 call qword ptr [r14+F_FIN]
 mov rsi,[r15+64]
 mov rax,[rsi]
 xor rax,[r14+F_TAG]
 mov rdx,[rsi+8]
 xor rdx,[r14+F_TAG+8]
 or rax,rdx
 mov eax,0
 jnz 4f
 call tq_crypt
 jmp 3f
2:
 call tq_crypt
 mov rsi,[r15+56]
 mov rdx,[r15+48]
 call tq_absorb
 call qword ptr [r14+F_FIN]
 mov rdi,[r15+64]
 movdqa xmm0,[r14+F_TAG]
 movdqu [rdi],xmm0
3:
 mov eax,1
4:
 ret

# RDX bytes at RSI absorbed in blocks of sixteen, the last one filled
# with zeros
tq_absorb:
 push rbx
 push r13
 mov r13,rsi
 mov rbx,rdx
1:
 cmp rbx,16
 jb 2f
 mov rsi,r13
 call qword ptr [r14+F_BLK]
 add r13,16
 sub rbx,16
 jmp 1b
2:
 test rbx,rbx
 jz 3f
 pxor xmm0,xmm0
 movdqa [r14+F_TMP],xmm0
 lea rdi,[r14+F_TMP]
 mov rsi,r13
 mov rcx,rbx
 rep movsb
 lea rsi,[r14+F_TMP]
 call qword ptr [r14+F_BLK]
3:
 pop r13
 pop rbx
 ret

# in to out under the key stream. What makes key stream keeps RSI, RDI
# and RBX.
tq_crypt:
 push rbx
 mov rsi,[r15+40]
 mov rdi,[r15+56]
 mov rbx,[r15+48]
1:
 test rbx,rbx
 jz 5f
 call qword ptr [r14+F_GEN]
 mov rcx,[r14+F_BS]
 cmp rbx,rcx
 cmovb rcx,rbx
 sub rbx,rcx
 lea rdx,[r14+F_KS]
2:
 cmp rcx,16
 jb 4f
 movdqu xmm0,[rsi]
 pxor xmm0,[rdx]
 movdqu [rdi],xmm0
 add rsi,16
 add rdi,16
 add rdx,16
 sub rcx,16
 jmp 2b
3:
 mov al,[rsi]
 xor al,[rdx]
 mov [rdi],al
 inc rsi
 inc rdi
 inc rdx
 dec rcx
4:
 test rcx,rcx
 jnz 3b
 jmp 1b
5:
 pop rbx
 ret

# One block of key stream from the next counter, software
tq_gen_sw:
 mov eax,[r14+12]
 bswap eax
 inc eax
 bswap eax
 mov [r14+12],eax
 movdqa xmm0,[r14]
 call tq_aes
 movdqa [r14+F_KS],xmm0
 ret
# Four blocks from the next four counters, AES-NI
tq_gen_ni:
 mov eax,[r14+12]
 bswap eax
 movdqa xmm6,[r14]
 pslldq xmm6,4
 psrldq xmm6,4
 .irp i,0,1,2,3
 inc eax
 mov ecx,eax
 bswap ecx
 movd xmm5,ecx
 pslldq xmm5,12
 movdqa xmm\i,xmm6
 por xmm\i,xmm5
 .endr
 bswap eax
 mov [r14+12],eax
 call tq_ni4
 .irp i,0,1,2,3
 movdqa [r14+F_KS+16*\i],xmm\i
 .endr
 ret

# The lengths in bits, then the tag: the GHASH state under E(J0)
tq_gcm_fin:
 mov rax,[r15+32]
 shl rax,3
 bswap rax
 mov [r14+F_TMP],rax
 mov rax,[r15+48]
 shl rax,3
 bswap rax
 mov [r14+F_TMP+8],rax
 lea rsi,[r14+F_TMP]
 call qword ptr [r14+F_BLK]
 mov dword ptr [r14+12],0x01000000
 movdqa xmm0,[r14]
 call tq_aes
 movdqa [r14+F_TAG],xmm0
 mov rax,[r14+F_Y+8]
 bswap rax
 xor [r14+F_TAG],rax
 mov rax,[r14+F_Y]
 bswap rax
 xor [r14+F_TAG+8],rax
 ret

# Y = (Y + the block at RSI)*H. The state and H are the blocks with their
# bytes reversed, so the first bit of a block is the top bit. Z takes V
# for every set bit of Y from the top while V goes down a bit at a time,
# 0xe1 coming in at the top for a bit that falls off.
tq_ghash_sw:
 push rbx
 mov r8,[rsi]
 bswap r8
 xor r8,[r14+F_Y+8]
 mov r9,[rsi+8]
 bswap r9
 xor r9,[r14+F_Y]
 mov r10,[r12+264]
 mov r11,[r12+256]
 xor esi,esi
 xor edi,edi
 mov rdx,0xe100000000000000
 mov ecx,128
1:
 add r9,r9
 adc r8,r8
 sbb rax,rax
 mov rbx,r10
 and rbx,rax
 xor rsi,rbx
 and rax,r11
 xor rdi,rax
 shr r10,1
 rcr r11,1
 sbb rax,rax
 and rax,rdx
 xor r10,rax
 dec ecx
 jnz 1b
 mov [r14+F_Y+8],rsi
 mov [r14+F_Y],rdi
 pop rbx
 ret

# The same by carry-less multiplication: the four partial products, the
# 255-bit product moved up one bit for the reversed order, and the
# reduction by x**128+x**7+x**2+x+1 in two halves.
tq_ghash_ni:
 movdqu xmm0,[rsi]
 movdqu xmm2,[rip+tq_kswap]
 pshufb xmm0,xmm2
 pxor xmm0,[r14+F_Y]
 movdqu xmm1,[r12+256]
 movdqa xmm3,xmm0
 pclmulqdq xmm3,xmm1,0x00
 movdqa xmm4,xmm0
 pclmulqdq xmm4,xmm1,0x10
 movdqa xmm5,xmm0
 pclmulqdq xmm5,xmm1,0x01
 movdqa xmm6,xmm0
 pclmulqdq xmm6,xmm1,0x11
 pxor xmm4,xmm5
 movdqa xmm5,xmm4
 psrldq xmm4,8
 pslldq xmm5,8
 pxor xmm3,xmm5
 pxor xmm6,xmm4
 movdqa xmm7,xmm3
 movdqa xmm8,xmm6
 pslld xmm3,1
 pslld xmm6,1
 psrld xmm7,31
 psrld xmm8,31
 movdqa xmm9,xmm7
 pslldq xmm8,4
 pslldq xmm7,4
 psrldq xmm9,12
 por xmm3,xmm7
 por xmm6,xmm8
 por xmm6,xmm9
 movdqa xmm7,xmm3
 movdqa xmm8,xmm3
 movdqa xmm9,xmm3
 pslld xmm7,31
 pslld xmm8,30
 pslld xmm9,25
 pxor xmm7,xmm8
 pxor xmm7,xmm9
 movdqa xmm8,xmm7
 pslldq xmm7,12
 psrldq xmm8,4
 pxor xmm3,xmm7
 movdqa xmm2,xmm3
 movdqa xmm4,xmm3
 movdqa xmm5,xmm3
 psrld xmm2,1
 psrld xmm4,2
 psrld xmm5,7
 pxor xmm2,xmm4
 pxor xmm2,xmm5
 pxor xmm2,xmm8
 pxor xmm3,xmm2
 pxor xmm6,xmm3
 movdqa [r14+F_Y],xmm6
 ret

# ---- ChaCha20-Poly1305 ----
.macro TQ_QSTEP a,b,c,n
 paddd \a,\b
 pxor \c,\a
 movdqa xmm4,\c
 pslld \c,\n
 psrld xmm4,32-\n
 por \c,xmm4
.endm
# A quarter round on the four columns at once
tq_cc_quarter:
 TQ_QSTEP xmm0,xmm1,xmm3,16
 TQ_QSTEP xmm2,xmm3,xmm1,12
 TQ_QSTEP xmm0,xmm1,xmm3,8
 TQ_QSTEP xmm2,xmm3,xmm1,7
 ret
# The block of the state to the key stream, and the counter goes up. ECX
# and XMM0-XMM4 are spent.
tq_cc_block:
 .irp i,0,1,2,3
 movdqa xmm\i,[r14+F_ST+16*\i]
 .endr
 mov ecx,10
1:
 call tq_cc_quarter
 pshufd xmm1,xmm1,0x39
 pshufd xmm2,xmm2,0x4e
 pshufd xmm3,xmm3,0x93
 call tq_cc_quarter
 pshufd xmm1,xmm1,0x93
 pshufd xmm2,xmm2,0x4e
 pshufd xmm3,xmm3,0x39
 dec ecx
 jnz 1b
 .irp i,0,1,2,3
 paddd xmm\i,[r14+F_ST+16*\i]
 movdqa [r14+F_KS+16*\i],xmm\i
 .endr
 inc dword ptr [r14+F_ST+48]
 ret

tq_op_chacha:
 lea rdi,[r14+F_ST]
 lea rsi,[rip+tq_sigma]
 movsq
 movsq
 mov rsi,[r15+8]
 mov ecx,4
 rep movsq
 xor eax,eax
 stosd
 mov rsi,[r15+16]
 movsq
 mov eax,[rsi]
 stosd
 # block 0 is the Poly1305 key: r with its bits cleared, and s
 call tq_cc_block
 mov rax,0x0ffffffc0fffffff
 and rax,[r14+F_KS]
 mov [r14+F_R0],rax
 mov rax,0x0ffffffc0ffffffc
 and rax,[r14+F_KS+8]
 mov [r14+F_R1],rax
 mov rcx,rax
 shr rcx,2
 add rax,rcx
 mov [r14+F_S1],rax
 movdqa xmm0,[r14+F_KS+16]
 movdqa [r14+F_PAD],xmm0
 pxor xmm0,xmm0
 movdqa [r14+F_H0],xmm0
 movq [r14+F_H2],xmm0
 lea rax,[rip+tq_poly_block]
 lea rdx,[rip+tq_cc_block]
 mov ecx,64
 lea rsi,[rip+tq_poly_fin]
 mov edi,21
 jmp tq_aead

# h = (h + the block at RSI + 2**128)*r mod 2**130-5, h being three
# limbs and r two. 2**128 is 5/4 there and r1 is a multiple of 4, so the
# limbs past the second fold back through r1*5/4.
tq_poly_block:
 push rbx
 mov r8,[r14+F_H0]
 mov r9,[r14+F_H1]
 mov r10,[r14+F_H2]
 add r8,[rsi]
 adc r9,[rsi+8]
 adc r10,1
 mov rax,r8
 mul qword ptr [r14+F_R0]
 mov rbx,rax
 mov rcx,rdx
 mov rax,r9
 mul qword ptr [r14+F_S1]
 add rbx,rax
 adc rcx,rdx
 mov rax,r8
 mul qword ptr [r14+F_R1]
 mov r11,rax
 mov rdi,rdx
 mov rax,r9
 mul qword ptr [r14+F_R0]
 add r11,rax
 adc rdi,rdx
 mov rax,r10
 imul rax,[r14+F_S1]
 add r11,rax
 adc rdi,0
 imul r10,[r14+F_R0]
 add r11,rcx
 adc r10,rdi
 mov rax,r10
 shr rax,2
 and r10d,3
 lea rax,[rax+rax*4]
 add rbx,rax
 adc r11,0
 adc r10,0
 mov [r14+F_H0],rbx
 mov [r14+F_H1],r11
 mov [r14+F_H2],r10
 pop rbx
 ret

# The two lengths, then h fully reduced (h+5 when that reaches 2**130)
# plus s
tq_poly_fin:
 mov rax,[r15+32]
 mov [r14+F_TMP],rax
 mov rax,[r15+48]
 mov [r14+F_TMP+8],rax
 lea rsi,[r14+F_TMP]
 call tq_poly_block
 mov r8,[r14+F_H0]
 mov r9,[r14+F_H1]
 mov rdx,[r14+F_H2]
 mov rax,r8
 mov rcx,r9
 add rax,5
 adc rcx,0
 adc rdx,0
 shr rdx,2
 cmovnz r8,rax
 cmovnz r9,rcx
 add r8,[r14+F_PAD]
 adc r9,[r14+F_PAD+8]
 mov [r14+F_TAG],r8
 mov [r14+F_TAG+8],r9
 ret

tq_table:
 .word tq_op_feat-tq_table,tq_op_setup-tq_table,tq_op_mul-tq_table,tq_op_add-tq_table
 .word tq_op_sub-tq_table,tq_op_exp-tq_table,tq_op_cswap-tq_table,tq_op_reduce-tq_table
 .word tq_op_be2le-tq_table,tq_op_le2be-tq_table,tq_op_compare-tq_table,tq_nop-tq_table
 .word tq_nop-tq_table,tq_nop-tq_table,tq_nop-tq_table,tq_nop-tq_table
 .word tq_op_aes-tq_table,tq_op_gcm-tq_table,tq_op_gcm-tq_table,tq_nop-tq_table
 .word tq_op_chacha-tq_table,tq_op_chacha-tq_table,tq_op_cbc-tq_table,tq_op_cbc-tq_table
tq_k1b:
 .fill 16,1,0x1b
tq_k63:
 .fill 16,1,0x63
tq_krow:
 .long 0xff,0xff,0xff,0xff
tq_kswap:
 .byte 15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0
tq_sigma:
 .ascii "expand 32-byte k"
