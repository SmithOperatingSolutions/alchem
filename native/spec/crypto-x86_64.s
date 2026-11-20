# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# The crypto runtime, emitted once per program as an extra function-table
# entry when the library's Crypto functions are appended (Sys.hash). RDI is
# a block of nine words:
#
#   0  what: 0 a digest of the data, 1 its HMAC under the key, 2 PBKDF2 of
#      the key (the password) and the data (the salt)
#   8  the algorithm: 0 md5, 1 sha1, 2 sha224, 3 sha256, 4 sha384, 5 sha512
#   16 where the result goes
#   24, 32 the key and its length; 40, 48 the data and its length
#   56 the iterations and 64 the bytes wanted of PBKDF2
#
# Two more things it does are no cryptography: they are the random numbers
# of Gen, which the pinned runtime draws from Go's math/rand/v2 PCG, kept
# here because they need arithmetic on 128 bits. For them word 16 is where
# the generator's two words stand (the high one first):
#
#   0  3 the next 64 bits (PCG.Uint64); 4 a number below word 56
#      (Rand.Uint64N: a mask for a power of two, else the high half of a
#      product, drawn again while the low half is under 2**64 mod n)
#
# RAX is the digest's length. A digest is fed through a context of 224
# bytes: 0 the state, 64 a block being filled, 192 how full it is, 200 the
# bytes fed so far. Nothing is allocated: three contexts, the key's block
# and the working digests stand in 1024 bytes of stack. PBKDF2 keeps the
# contexts that have taken the key's two pads and copies them for each
# round, which leaves two compressions to a round.
.intel_syntax noprefix
.text
 push rbx
 push rbp
 push r12
 push r13
 push r14
 push r15
 mov r15,rdi
 sub rsp,1024
 mov rbp,rsp
 # frame: 0 inner context, 224 outer, 448 working, 672 the key's block,
 # 800 U, 864 T, 928 the block counter, 936 the inner digest, 1000 the
 # counter's bytes, 1008 rounds left
 mov rax,[r15+8]
 shl rax,5
 lea r14,[rip+kr_algs]
 add r14,rax
 cmp qword ptr [r15],3
 jae kr_random
 cmp qword ptr [r15],0
 jne kr_keyed
 lea rbx,[rbp+448]
 call kr_init
 mov rsi,[r15+40]
 mov rdx,[r15+48]
 call kr_update
 mov rdi,[r15+16]
 call kr_final
kr_done:
 mov eax,[r14+8]
kr_out:
 add rsp,1024
 pop r15
 pop r14
 pop r13
 pop r12
 pop rbp
 pop rbx
 ret
kr_keyed:
 lea rdi,[rbp+672]
 xor eax,eax
 mov ecx,16
 rep stosq
 mov rdx,[r15+32]
 mov ecx,[r14+4]
 cmp rdx,rcx
 jbe 1f
 # a key longer than a block is its digest
 lea rbx,[rbp+448]
 call kr_init
 mov rsi,[r15+24]
 mov rdx,[r15+32]
 call kr_update
 lea rdi,[rbp+672]
 call kr_final
 jmp 2f
1:
 lea rdi,[rbp+672]
 mov rsi,[r15+24]
 mov rcx,rdx
 rep movsb
2:
 mov al,0x36
 call kr_pad
 mov rbx,rbp
 call kr_init
 lea rsi,[rbp+672]
 mov edx,[r14+4]
 call kr_update
 mov al,0x6a
 call kr_pad
 lea rbx,[rbp+224]
 call kr_init
 lea rsi,[rbp+672]
 mov edx,[r14+4]
 call kr_update
 cmp qword ptr [r15],1
 jne kr_pbkdf
 call kr_inner
 mov rsi,[r15+40]
 mov rdx,[r15+48]
 call kr_update
 mov rdi,[r15+16]
 call kr_outer
 jmp kr_done
kr_pbkdf:
 mov r13,[r15+16]
 mov r12,[r15+64]
 mov qword ptr [rbp+928],1
1:
 call kr_inner
 mov rsi,[r15+40]
 mov rdx,[r15+48]
 call kr_update
 mov eax,[rbp+928]
 bswap eax
 mov [rbp+1000],eax
 lea rsi,[rbp+1000]
 mov edx,4
 call kr_update
 lea rdi,[rbp+800]
 call kr_outer
 lea rsi,[rbp+800]
 lea rdi,[rbp+864]
 mov ecx,8
 rep movsq
 mov rax,[r15+56]
 dec rax
 mov [rbp+1008],rax
2:
 cmp qword ptr [rbp+1008],0
 je 4f
 call kr_inner
 lea rsi,[rbp+800]
 mov edx,[r14+8]
 call kr_update
 lea rdi,[rbp+800]
 call kr_outer
 xor ecx,ecx
3:
 mov rax,[rbp+800+rcx*8]
 xor [rbp+864+rcx*8],rax
 inc ecx
 cmp ecx,8
 jb 3b
 dec qword ptr [rbp+1008]
 jmp 2b
4:
 mov ecx,[r14+8]
 cmp rcx,r12
 cmova rcx,r12
 sub r12,rcx
 lea rsi,[rbp+864]
 mov rdi,r13
 rep movsb
 mov r13,rdi
 inc qword ptr [rbp+928]
 test r12,r12
 jnz 1b
 jmp kr_done

kr_random:
 mov rbx,[r15+16]
 cmp qword ptr [r15],3
 jne 1f
 call kr_pcg
 jmp kr_out
1:
 mov rcx,[r15+56]
 lea rax,[rcx-1]
 test rax,rcx
 jnz 2f
 push rax
 call kr_pcg
 pop rdx
 and rax,rdx
 jmp kr_out
2:
 call kr_pcg
 mul qword ptr [r15+56]
 cmp rax,[r15+56]
 jae 4f
 push rdx
 push rax
 mov rax,[r15+56]
 neg rax
 xor edx,edx
 div qword ptr [r15+56]
 mov r12,rdx
 pop rax
 pop rdx
3:
 cmp rax,r12
 jae 4f
 call kr_pcg
 mul qword ptr [r15+56]
 jmp 3b
4:
 mov rax,rdx
 jmp kr_out
# The state at RBX times 0x2360ed051fc65da44385df649fccf645 plus
# 0x5851f42d4c957f2d14057b7ef767814f, and its 64 bits by DXSM.
kr_pcg:
 mov rax,[rbx+8]
 mov rsi,4865540595714422341
 mul rsi
 mov rdi,[rbx]
 imul rdi,rsi
 add rdx,rdi
 mov rdi,[rbx+8]
 mov rcx,2549297995355413924
 imul rdi,rcx
 add rdx,rdi
 mov rcx,1442695040888963407
 add rax,rcx
 mov rcx,6364136223846793005
 adc rdx,rcx
 mov [rbx+8],rax
 mov [rbx],rdx
 mov rcx,rdx
 shr rcx,32
 xor rdx,rcx
 mov rcx,0xda942042e4dd58b5
 imul rdx,rcx
 mov rcx,rdx
 shr rcx,48
 xor rdx,rcx
 or rax,1
 imul rdx,rax
 mov rax,rdx
 ret

# The key's block xor AL, byte by byte.
kr_pad:
 xor ecx,ecx
1:
 xor [rbp+672+rcx],al
 inc ecx
 cmp ecx,128
 jb 1b
 ret
# The working context becomes the one that has taken the inner pad.
kr_inner:
 mov rsi,rbp
 lea rdi,[rbp+448]
 mov ecx,28
 rep movsq
 lea rbx,[rbp+448]
 ret
# The working context's digest, fed to the context that has taken the outer
# pad; that one's digest to RDI.
kr_outer:
 push rdi
 lea rdi,[rbp+936]
 call kr_final
 lea rsi,[rbp+224]
 lea rdi,[rbp+448]
 mov ecx,28
 rep movsq
 lea rsi,[rbp+936]
 mov edx,[r14+8]
 call kr_update
 pop rdi
 jmp kr_final

# RBX a context, R14 the algorithm's record.
kr_init:
 movsxd rsi,dword ptr [r14+16]
 lea rax,[rip+kr_algs]
 add rsi,rax
 mov rdi,rbx
 mov ecx,8
 rep movsq
 xor eax,eax
 mov [rbx+192],rax
 mov [rbx+200],rax
 ret
# RDX bytes at RSI into the context RBX.
kr_update:
 push r12
 push r13
 mov r12,rsi
 mov r13,rdx
 add [rbx+200],rdx
 mov rax,[rbx+192]
 test rax,rax
 jz 2f
 mov ecx,[r14+4]
 sub rcx,rax
 cmp rcx,r13
 cmova rcx,r13
 lea rdi,[rbx+64+rax]
 mov rsi,r12
 add r12,rcx
 sub r13,rcx
 add rax,rcx
 mov [rbx+192],rax
 rep movsb
 mov ecx,[r14+4]
 cmp rax,rcx
 jb 4f
 lea rsi,[rbx+64]
 call kr_block
 mov qword ptr [rbx+192],0
2:
 mov ecx,[r14+4]
 cmp r13,rcx
 jb 3f
 mov rsi,r12
 call kr_block
 mov ecx,[r14+4]
 add r12,rcx
 sub r13,rcx
 jmp 2b
3:
 lea rdi,[rbx+64]
 mov rsi,r12
 mov rcx,r13
 mov [rbx+192],r13
 rep movsb
4:
 pop r13
 pop r12
 ret
# The block at RSI into the state at RBX. The compressions keep RBX, RBP
# and R12 to R15.
kr_block:
 movsxd rax,dword ptr [r14]
 lea rcx,[rip+kr_algs]
 add rax,rcx
 mov rdi,rbx
 jmp rax
# The digest of the context RBX to RDI; its length in EAX.
kr_final:
 push rdi
 mov rax,[rbx+192]
 mov byte ptr [rbx+64+rax],0x80
 inc rax
 mov ecx,[r14+4]
 sub rcx,rax
 lea rdi,[rbx+64+rax]
 mov rdx,rax
 xor eax,eax
 rep stosb
 mov ecx,[r14+4]
 mov eax,ecx
 shr eax,3
 sub rcx,rax
 cmp rdx,rcx
 jbe 1f
 lea rsi,[rbx+64]
 call kr_block
 lea rdi,[rbx+64]
 xor eax,eax
 mov ecx,16
 rep stosq
1:
 mov rax,[rbx+200]
 shl rax,3
 mov ecx,[r14+4]
 test byte ptr [r14+20],1
 jnz 2f
 bswap rax
2:
 mov [rbx+56+rcx],rax
 lea rsi,[rbx+64]
 call kr_block
 pop rdi
 test byte ptr [r14+20],1
 jnz 5f
 xor ecx,ecx
 test byte ptr [r14+20],2
 jnz 4f
3:
 mov eax,[rbx+rcx*4]
 bswap eax
 mov [rbx+rcx*4],eax
 inc ecx
 cmp ecx,8
 jb 3b
 jmp 5f
4:
 mov rax,[rbx+rcx*8]
 bswap rax
 mov [rbx+rcx*8],rax
 inc ecx
 cmp ecx,8
 jb 4b
5:
 mov rsi,rbx
 mov ecx,[r14+8]
 mov eax,ecx
 rep movsb
 ret

# ---- the compressions: RDI the state, RSI a block ----
kr_md5:
 push rbx
 push rbp
 mov r8d,[rdi]
 mov r9d,[rdi+4]
 mov r10d,[rdi+8]
 mov r11d,[rdi+12]
 lea rbp,[rip+kr_md5_t]
 xor ecx,ecx
1:
 cmp ecx,16
 jae 2f
 mov eax,r10d
 xor eax,r11d
 and eax,r9d
 xor eax,r11d
 jmp 5f
2:
 cmp ecx,32
 jae 3f
 mov eax,r9d
 xor eax,r10d
 and eax,r11d
 xor eax,r10d
 jmp 5f
3:
 cmp ecx,48
 jae 4f
 mov eax,r9d
 xor eax,r10d
 xor eax,r11d
 jmp 5f
4:
 mov eax,r11d
 not eax
 or eax,r9d
 xor eax,r10d
5:
 add eax,r8d
 add eax,[rbp+rcx*4]
 movzx edx,byte ptr [rbp+320+rcx]
 add eax,[rsi+rdx*4]
 mov ebx,ecx
 movzx ecx,byte ptr [rbp+256+rbx]
 rol eax,cl
 mov ecx,ebx
 add eax,r9d
 mov r8d,r11d
 mov r11d,r10d
 mov r10d,r9d
 mov r9d,eax
 inc ecx
 cmp ecx,64
 jb 1b
 add [rdi],r8d
 add [rdi+4],r9d
 add [rdi+8],r10d
 add [rdi+12],r11d
 pop rbp
 pop rbx
 ret

kr_sha1:
 push rbx
 push rbp
 sub rsp,320
 xor ecx,ecx
1:
 mov eax,[rsi+rcx*4]
 bswap eax
 mov [rsp+rcx*4],eax
 inc ecx
 cmp ecx,16
 jb 1b
2:
 mov eax,[rsp+rcx*4-12]
 xor eax,[rsp+rcx*4-32]
 xor eax,[rsp+rcx*4-56]
 xor eax,[rsp+rcx*4-64]
 rol eax,1
 mov [rsp+rcx*4],eax
 inc ecx
 cmp ecx,80
 jb 2b
 mov r8d,[rdi]
 mov r9d,[rdi+4]
 mov r10d,[rdi+8]
 mov r11d,[rdi+12]
 mov ebp,[rdi+16]
 xor ecx,ecx
3:
 cmp ecx,20
 jae 4f
 mov eax,r10d
 xor eax,r11d
 and eax,r9d
 xor eax,r11d
 add eax,0x5a827999
 jmp 7f
4:
 cmp ecx,40
 jae 5f
 mov eax,r9d
 xor eax,r10d
 xor eax,r11d
 add eax,0x6ed9eba1
 jmp 7f
5:
 cmp ecx,60
 jae 6f
 mov eax,r9d
 or eax,r10d
 and eax,r11d
 mov edx,r9d
 and edx,r10d
 or eax,edx
 add eax,0x8f1bbcdc
 jmp 7f
6:
 mov eax,r9d
 xor eax,r10d
 xor eax,r11d
 add eax,0xca62c1d6
7:
 mov edx,r8d
 rol edx,5
 add eax,edx
 add eax,ebp
 add eax,[rsp+rcx*4]
 mov ebp,r11d
 mov r11d,r10d
 mov r10d,r9d
 rol r10d,30
 mov r9d,r8d
 mov r8d,eax
 inc ecx
 cmp ecx,80
 jb 3b
 add [rdi],r8d
 add [rdi+4],r9d
 add [rdi+8],r10d
 add [rdi+12],r11d
 add [rdi+16],ebp
 add rsp,320
 pop rbp
 pop rbx
 ret

kr_sha256:
 push rbx
 push rbp
 push r12
 push r13
 push r14
 push r15
 sub rsp,256
 xor ecx,ecx
1:
 mov eax,[rsi+rcx*4]
 bswap eax
 mov [rsp+rcx*4],eax
 inc ecx
 cmp ecx,16
 jb 1b
2:
 mov eax,[rsp+rcx*4-8]
 mov edx,eax
 mov ebx,eax
 ror eax,17
 ror edx,19
 shr ebx,10
 xor eax,edx
 xor eax,ebx
 add eax,[rsp+rcx*4-28]
 mov edx,[rsp+rcx*4-60]
 mov ebx,edx
 mov ebp,edx
 ror edx,7
 ror ebx,18
 shr ebp,3
 xor edx,ebx
 xor edx,ebp
 add eax,edx
 add eax,[rsp+rcx*4-64]
 mov [rsp+rcx*4],eax
 inc ecx
 cmp ecx,64
 jb 2b
 mov r8d,[rdi]
 mov r9d,[rdi+4]
 mov r10d,[rdi+8]
 mov r11d,[rdi+12]
 mov r12d,[rdi+16]
 mov r13d,[rdi+20]
 mov r14d,[rdi+24]
 mov r15d,[rdi+28]
 lea rbp,[rip+kr_k256]
 xor ecx,ecx
3:
 mov eax,r12d
 ror eax,6
 mov edx,r12d
 ror edx,11
 xor eax,edx
 mov edx,r12d
 ror edx,25
 xor eax,edx
 add eax,r15d
 mov edx,r14d
 xor edx,r13d
 and edx,r12d
 xor edx,r14d
 add eax,edx
 add eax,[rbp+rcx*4]
 add eax,[rsp+rcx*4]
 mov edx,r8d
 ror edx,2
 mov ebx,r8d
 ror ebx,13
 xor edx,ebx
 mov ebx,r8d
 ror ebx,22
 xor edx,ebx
 mov ebx,r8d
 or ebx,r9d
 and ebx,r10d
 mov esi,r8d
 and esi,r9d
 or ebx,esi
 add edx,ebx
 mov r15d,r14d
 mov r14d,r13d
 mov r13d,r12d
 lea r12d,[r11d+eax]
 mov r11d,r10d
 mov r10d,r9d
 mov r9d,r8d
 lea r8d,[eax+edx]
 inc ecx
 cmp ecx,64
 jb 3b
 add [rdi],r8d
 add [rdi+4],r9d
 add [rdi+8],r10d
 add [rdi+12],r11d
 add [rdi+16],r12d
 add [rdi+20],r13d
 add [rdi+24],r14d
 add [rdi+28],r15d
 add rsp,256
 pop r15
 pop r14
 pop r13
 pop r12
 pop rbp
 pop rbx
 ret

kr_sha512:
 push rbx
 push rbp
 push r12
 push r13
 push r14
 push r15
 sub rsp,640
 xor ecx,ecx
1:
 mov rax,[rsi+rcx*8]
 bswap rax
 mov [rsp+rcx*8],rax
 inc ecx
 cmp ecx,16
 jb 1b
2:
 mov rax,[rsp+rcx*8-16]
 mov rdx,rax
 mov rbx,rax
 ror rax,19
 ror rdx,61
 shr rbx,6
 xor rax,rdx
 xor rax,rbx
 add rax,[rsp+rcx*8-56]
 mov rdx,[rsp+rcx*8-120]
 mov rbx,rdx
 mov rbp,rdx
 ror rdx,1
 ror rbx,8
 shr rbp,7
 xor rdx,rbx
 xor rdx,rbp
 add rax,rdx
 add rax,[rsp+rcx*8-128]
 mov [rsp+rcx*8],rax
 inc ecx
 cmp ecx,80
 jb 2b
 mov r8,[rdi]
 mov r9,[rdi+8]
 mov r10,[rdi+16]
 mov r11,[rdi+24]
 mov r12,[rdi+32]
 mov r13,[rdi+40]
 mov r14,[rdi+48]
 mov r15,[rdi+56]
 lea rbp,[rip+kr_k512]
 xor ecx,ecx
3:
 mov rax,r12
 ror rax,14
 mov rdx,r12
 ror rdx,18
 xor rax,rdx
 mov rdx,r12
 ror rdx,41
 xor rax,rdx
 add rax,r15
 mov rdx,r14
 xor rdx,r13
 and rdx,r12
 xor rdx,r14
 add rax,rdx
 add rax,[rbp+rcx*8]
 add rax,[rsp+rcx*8]
 mov rdx,r8
 ror rdx,28
 mov rbx,r8
 ror rbx,34
 xor rdx,rbx
 mov rbx,r8
 ror rbx,39
 xor rdx,rbx
 mov rbx,r8
 or rbx,r9
 and rbx,r10
 mov rsi,r8
 and rsi,r9
 or rbx,rsi
 add rdx,rbx
 mov r15,r14
 mov r14,r13
 mov r13,r12
 lea r12,[r11+rax]
 mov r11,r10
 mov r10,r9
 mov r9,r8
 lea r8,[rax+rdx]
 inc ecx
 cmp ecx,80
 jb 3b
 add [rdi],r8
 add [rdi+8],r9
 add [rdi+16],r10
 add [rdi+24],r11
 add [rdi+32],r12
 add [rdi+40],r13
 add [rdi+48],r14
 add [rdi+56],r15
 add rsp,640
 pop r15
 pop r14
 pop r13
 pop r12
 pop rbp
 pop rbx
 ret

# An algorithm: its compression and the block's size, the digest's length,
# its first state, and 1 for words stored low byte first, 2 for words of 64 bits.
 .balign 8
kr_algs:
 .long kr_md5-kr_algs,64,16,0,kr_iv_md5-kr_algs,1,0,0
 .long kr_sha1-kr_algs,64,20,0,kr_iv_sha1-kr_algs,0,0,0
 .long kr_sha256-kr_algs,64,28,0,kr_iv_sha224-kr_algs,0,0,0
 .long kr_sha256-kr_algs,64,32,0,kr_iv_sha256-kr_algs,0,0,0
 .long kr_sha512-kr_algs,128,48,0,kr_iv_sha384-kr_algs,2,0,0
 .long kr_sha512-kr_algs,128,64,0,kr_iv_sha512-kr_algs,2,0,0
kr_iv_md5:
 .long 0x67452301,0xefcdab89,0x98badcfe,0x10325476
kr_iv_sha1:
 .long 0x67452301,0xefcdab89,0x98badcfe,0x10325476,0xc3d2e1f0
kr_iv_sha224:
 .long 0xc1059ed8,0x367cd507,0x3070dd17,0xf70e5939,0xffc00b31,0x68581511,0x64f98fa7,0xbefa4fa4
kr_iv_sha256:
 .long 0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
kr_iv_sha384:
 .quad 0xcbbb9d5dc1059ed8,0x629a292a367cd507,0x9159015a3070dd17,0x152fecd8f70e5939
 .quad 0x67332667ffc00b31,0x8eb44a8768581511,0xdb0c2e0d64f98fa7,0x47b5481dbefa4fa4
kr_iv_sha512:
 .quad 0x6a09e667f3bcc908,0xbb67ae8584caa73b,0x3c6ef372fe94f82b,0xa54ff53a5f1d36f1
 .quad 0x510e527fade682d1,0x9b05688c2b3e6c1f,0x1f83d9abfb41bd6b,0x5be0cd19137e2179
kr_k256:
 .long 0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5
 .long 0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174
 .long 0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da
 .long 0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967
 .long 0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85
 .long 0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070
 .long 0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3
 .long 0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
kr_k512:
 .quad 0x428a2f98d728ae22,0x7137449123ef65cd,0xb5c0fbcfec4d3b2f,0xe9b5dba58189dbbc
 .quad 0x3956c25bf348b538,0x59f111f1b605d019,0x923f82a4af194f9b,0xab1c5ed5da6d8118
 .quad 0xd807aa98a3030242,0x12835b0145706fbe,0x243185be4ee4b28c,0x550c7dc3d5ffb4e2
 .quad 0x72be5d74f27b896f,0x80deb1fe3b1696b1,0x9bdc06a725c71235,0xc19bf174cf692694
 .quad 0xe49b69c19ef14ad2,0xefbe4786384f25e3,0x0fc19dc68b8cd5b5,0x240ca1cc77ac9c65
 .quad 0x2de92c6f592b0275,0x4a7484aa6ea6e483,0x5cb0a9dcbd41fbd4,0x76f988da831153b5
 .quad 0x983e5152ee66dfab,0xa831c66d2db43210,0xb00327c898fb213f,0xbf597fc7beef0ee4
 .quad 0xc6e00bf33da88fc2,0xd5a79147930aa725,0x06ca6351e003826f,0x142929670a0e6e70
 .quad 0x27b70a8546d22ffc,0x2e1b21385c26c926,0x4d2c6dfc5ac42aed,0x53380d139d95b3df
 .quad 0x650a73548baf63de,0x766a0abb3c77b2a8,0x81c2c92e47edaee6,0x92722c851482353b
 .quad 0xa2bfe8a14cf10364,0xa81a664bbc423001,0xc24b8b70d0f89791,0xc76c51a30654be30
 .quad 0xd192e819d6ef5218,0xd69906245565a910,0xf40e35855771202a,0x106aa07032bbd1b8
 .quad 0x19a4c116b8d2d0c8,0x1e376c085141ab53,0x2748774cdf8eeb99,0x34b0bcb5e19b48a8
 .quad 0x391c0cb3c5c95a63,0x4ed8aa4ae3418acb,0x5b9cca4f7763e373,0x682e6ff3d6b2b8a3
 .quad 0x748f82ee5defb2fc,0x78a5636f43172f60,0x84c87814a1f0ab72,0x8cc702081a6439ec
 .quad 0x90befffa23631e28,0xa4506cebde82bde9,0xbef9a3f7b2c67915,0xc67178f2e372532b
 .quad 0xca273eceea26619c,0xd186b8c721c0c207,0xeada7dd6cde0eb1e,0xf57d4f7fee6ed178
 .quad 0x06f067aa72176fba,0x0a637dc5a2c898a6,0x113f9804bef90dae,0x1b710b35131c471b
 .quad 0x28db77f523047d84,0x32caab7b40c72493,0x3c9ebe0a15c9bebc,0x431d67c49c100d4c
 .quad 0x4cc5d4becb3e42b6,0x597f299cfc657e2a,0x5fcb6fab3ad6faec,0x6c44198c4a475817
kr_md5_t:
 .long 0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,0xf57c0faf,0x4787c62a,0xa8304613,0xfd469501
 .long 0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,0x6b901122,0xfd987193,0xa679438e,0x49b40821
 .long 0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,0xd62f105d,0x02441453,0xd8a1e681,0xe7d3fbc8
 .long 0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a
 .long 0xfffa3942,0x8771f681,0x6d9d6122,0xfde5380c,0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70
 .long 0x289b7ec6,0xeaa127fa,0xd4ef3085,0x04881d05,0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665
 .long 0xf4292244,0x432aff97,0xab9423a7,0xfc93a039,0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1
 .long 0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,0xf7537e82,0xbd3af235,0x2ad7d2bb,0xeb86d391
kr_md5_s:
 .byte 7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22
 .byte 5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20
 .byte 4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23
 .byte 6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21
kr_md5_g:
 .byte 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
 .byte 1,6,11,0,5,10,15,4,9,14,3,8,13,2,7,12
 .byte 5,8,11,14,1,4,7,10,13,0,3,6,9,12,15,2
 .byte 0,7,14,5,12,3,10,1,8,15,6,13,4,11,2,9
