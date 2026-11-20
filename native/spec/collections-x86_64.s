# Immutable word collections. Inputs are native expression pushes, output RAX.
# R12/R13 are the checked arena cursor/end; a site without room calls the
# allocation hook (alchem-memory.md). All sections are position independent.
.macro arena_count
  lea 8(%r12,%rcx,8), %r11
  cmp %r13,%r11
  jbe 991f
  call *0x400478
991:
  mov %r12,%rax
  mov %r11,%r12
  mov %rcx,(%rax)
.endm
# A list (alchem-lists.md) is the address of a count word followed by the
# first element, the count of the rest, the second element and so on down
# to a count of 0: its tail is the address 16 above it. The word 16 below a
# list is 0 where the block it lies in has an unclaimed pair there.
# arena_list reserves a block for exactly RCX elements: the word -2, a word
# of padding, RCX pairs and the 0 that ends them. RAX is the first pair; the
# counts and elements are the caller's to write. Clobbers R11.
.macro arena_list
  mov %rcx,%r11
  shl $4,%r11
  lea 24(%r12,%r11),%r11
  cmp %r13,%r11
  jbe 993f
  call *0x400478
993:
  movq $-2,(%r12)
  lea 16(%r12),%rax
  movq $0,-8(%r11)
  mov %r11,%r12
.endm
.macro box_value
  lea 16(%r12),%r11
  cmp %r13,%r11
  jbe 992f
  call *0x400478
992:
  movq $1,(%r12)
  mov %rax,8(%r12)
  mov %r12,%rax
  mov %r11,%r12
.endm
.section .text.nl_pack,"ax"
  arena_list
  mov %rcx,%rdx
  lea -24(%r12),%r11
  mov $1,%r8d
  test %rdx,%rdx
  jz 2f
1:
  pop 8(%r11)
  mov %r8,(%r11)
  inc %r8
  sub $16,%r11
  dec %rdx
  jnz 1b
2:
.section .text.nl_at,"ax"
  pop %rax
  pop %rsi
  pop %rdi
  mov (%rdi),%rcx
  test %rsi,%rsi
  jns 1f
  add %rcx,%rsi
1:
  cmp %rcx,%rsi
  jae 2f
  shl $4,%rsi
  mov 8(%rdi,%rsi),%rax
  test %r10d,%r10d
  jz 3f
  box_value
  jmp 3f
2:
  test %r10d,%r10d
  jz 3f
  xor %eax,%eax
3:
.section .text.nl_concat,"ax"
  pop %r10
  pop %rsi
  mov (%rsi),%r8
  mov (%r10),%rcx
  add %r8,%rcx
  arena_list
  mov %rax,%rdi
  mov %rcx,%rdx
1:
  test %r8,%r8
  jz 2f
  mov %rdx,(%rdi)
  mov 8(%rsi),%r11
  mov %r11,8(%rdi)
  add $16,%rsi
  add $16,%rdi
  dec %rdx
  dec %r8
  jmp 1b
2:
  mov %r10,%rsi
  lea (%rdx,%rdx),%rcx
  cld
  rep movsq
# A slice that ends where the list ends is the list from its first element
# on, and an empty one the list's end: neither is copied.
.section .text.nl_slice,"ax"
  pop %rdx
  pop %rsi
  pop %rdi
  mov (%rdi),%rcx
  test %rsi,%rsi
  jns 1f
  add %rcx,%rsi
1:
  test %rdx,%rdx
  jns 4f
  mov $80,%edi
  mov $60,%eax
  syscall
4:
  mov %rcx,%r8
  test %rdx,%rdx
  jz 2f
  cmp %rcx,%rsi
  jae 2f
  sub %rsi,%rcx
  cmp %rcx,%rdx
  jae 5f
  mov %rdx,%rcx
  shl $4,%rsi
  lea (%rdi,%rsi),%r10
  arena_list
  mov %rax,%rdi
  mov %rcx,%rdx
6:
  mov %rdx,(%rdi)
  mov 8(%r10),%r11
  mov %r11,8(%rdi)
  add $16,%r10
  add $16,%rdi
  dec %rdx
  jnz 6b
  jmp 3f
2:
  mov %r8,%rsi
5:
  shl $4,%rsi
  lea (%rdi,%rsi),%rax
3:
.section .text.nl_reverse,"ax"
  pop %rsi
  mov (%rsi),%rcx
  arena_list
  lea -24(%r12),%r11
  mov $1,%edx
1:
  cmp %rcx,%rdx
  ja 2f
  mov 8(%rsi),%r8
  mov %r8,8(%r11)
  mov %rdx,(%r11)
  add $16,%rsi
  sub $16,%r11
  inc %rdx
  jmp 1b
2:
.section .text.nl_sum,"ax"
  pop %rdi
  mov (%rdi),%rcx
  xor %eax,%eax
1:
  test %rcx,%rcx
  jz 2f
  add 8(%rdi),%rax
  jo 3f
  add $16,%rdi
  dec %rcx
  jmp 1b
3:
  stc
  jmp 4f
2:
  clc
4:
# The carry flag is set when the sum left 64 bits; the caller reports it.
.section .text.nl_map,"ax"
  pop %r10
  pop %rsi
  mov (%rsi),%rcx
  arena_list
  push %rax
  mov %rax,%r8
1:
  test %rcx,%rcx
  jz 2f
  push %r10
  push %rsi
  push %r8
  push %rcx
  mov 8(%rsi),%rdi
  call *(%r10)
  pop %rcx
  pop %r8
  pop %rsi
  pop %r10
  mov %rcx,(%r8)
  mov %rax,8(%r8)
  add $16,%rsi
  add $16,%r8
  dec %rcx
  jmp 1b
2:
  pop %rax
.section .text.nl_reduce,"ax"
  pop %r10
  pop %rax
  pop %r8
  mov (%r8),%rcx
1:
  test %rcx,%rcx
  jz 2f
  push %r10
  push %r8
  push %rcx
  mov 8(%r8),%rdi
  mov %rax,%rsi
  call *(%r10)
  pop %rcx
  pop %r8
  pop %r10
  add $16,%r8
  dec %rcx
  jmp 1b
2:
# [h1, ..., hk | rest]: the heads lie on the stack in order with the rest
# above them, and ECX is k. Each head, the last first, is put before the
# list: into the pair below it when the block has that pair unclaimed (the
# word there is 0, as the arena is before it is written), which claims it,
# and otherwise into a new block of 2n+4 pairs that holds the head, the n
# elements copied after it and n+3 unclaimed pairs below, as the pinned
# runtime's listPrepend.
.section .text.nl_cons,"ax"
  pop %rax
1:
  test %rcx,%rcx
  jz 9f
  pop %rdx
  cmpq $0,-16(%rax)
  jne 2f
  mov (%rax),%r8
  inc %r8
  mov %r8,-16(%rax)
  mov %rdx,-8(%rax)
  sub $16,%rax
  dec %rcx
  jmp 1b
2:
  mov (%rax),%r8
  lea 4(%r8,%r8),%r11
  shl $4,%r11
  lea 24(%r12,%r11),%r11
  cmp %r13,%r11
  jbe 3f
  call *0x400478
3:
  movq $-2,(%r12)
  lea 3(%r8),%rdi
  shl $4,%rdi
  lea 16(%r12,%rdi),%rdi
  mov %r11,%r12
  lea 1(%r8),%r10
  mov %r10,(%rdi)
  mov %rdx,8(%rdi)
  push %rdi
  add $16,%rdi
  mov %rax,%rsi
  mov %rcx,%r10
  lea 1(%r8,%r8),%rcx
  cld
  rep movsq
  mov %r10,%rcx
  pop %rax
  dec %rcx
  jmp 1b
9:
.section .note.GNU-stack,"",@progbits
# Two keys of a compound type: RDI and RSI the keys, R8 twice the type's
# comparator, as a generic function holds it and the map routines get it
# (native-ordering.alc): code below 4 GiB, called directly, or a function
# value, called with its address in R10. EDX asks the question: 0 whether the
# keys are equal (AL 1 or 0, so that a NaN inside a key equals nothing), 1
# their order (EAX -1, 0 or 1). The comparator keeps only RBP, RSP and R12 to
# R15; every other register the map routines use is kept here.
.macro map_key name
\name:
  push %rbx
  push %rcx
  push %rsi
  push %rdi
  push %r8
  push %r9
  push %r10
  push %r11
  mov %r8,%r10
  shr $1,%r10
  mov %r10,%rax
  shr $32,%rax
  jnz .Lkey_value\@
  call *%r10
  jmp .Lkey_done\@
.Lkey_value\@:
  call *(%r10)
.Lkey_done\@:
  pop %r11
  pop %r10
  pop %r9
  pop %r8
  pop %rdi
  pop %rsi
  pop %rcx
  pop %rbx
  ret
.endm
# Map find: RDI map, RSI key, R8 key type (0 a word, 2 a string, 24 a float,
# above 48 twice the comparator of a compound type, for the routine key),
# RAX index/-1.
# Preserves RDI/RSI/RDX/R8. Comparison examines string contents, including NUL.
.macro map_find name key
\name:
  xor %ecx,%ecx
.Lfind_loop\@:
  cmp (%rdi),%rcx
  jae .Lfind_missing\@
  mov %rcx,%rax
  shl $4,%rax
  mov 8(%rdi,%rax),%r11
  cmp $48,%r8
  jbe .Lfind_plain\@
  push %rcx
  push %rdx
  push %rdi
  push %rsi
  mov %r11,%rdi
  xor %edx,%edx
  call \key
  pop %rsi
  pop %rdi
  pop %rdx
  pop %rcx
  test %al,%al
  jnz .Lfind_found\@
  jmp .Lfind_next\@
.Lfind_plain\@:
  cmp $2,%r8d
  jne .Lfind_scalar\@
  mov (%rsi),%r9
  cmp (%r11),%r9
  jne .Lfind_next\@
  xor %eax,%eax
.Lfind_bytes\@:
  cmp %r9,%rax
  jae .Lfind_found\@
  movzbl 8(%rsi,%rax),%r10d
  cmp 8(%r11,%rax),%r10b
  jne .Lfind_next\@
  inc %rax
  jmp .Lfind_bytes\@
.Lfind_next\@:
  inc %rcx
  jmp .Lfind_loop\@
.Lfind_scalar\@:
  cmp $24,%r8d
  je .Lfind_float\@
  cmp %rsi,%r11
  je .Lfind_found\@
  jmp .Lfind_next\@
.Lfind_float\@:
  movq %rsi,%xmm0
  movq %r11,%xmm1
  ucomisd %xmm1,%xmm0
  jne .Lfind_next\@
  jp .Lfind_next\@
  jmp .Lfind_found\@
.Lfind_missing\@:
  mov $-1,%rax
  ret
.Lfind_found\@:
  mov %rcx,%rax
  ret
.endm
# Sort fresh map records by signed scalar / byte-string / float key order,
# or by the routine key for a compound type.
.macro map_sort name key
\name:
  mov $1,%rcx
.Lsort_outer\@:
  cmp (%rdi),%rcx
  jae .Lsort_done\@
  mov %rcx,%rdx
.Lsort_inner\@:
  mov %rdx,%rax
  shl $4,%rax
  mov -8(%rdi,%rax),%r9
  mov 8(%rdi,%rax),%r10
  cmp $48,%r8
  jbe .Lsort_plain\@
  push %rcx
  push %rdx
  push %rdi
  push %r9
  push %r10
  mov %r9,%rdi
  mov %r10,%rsi
  mov $1,%edx
  call \key
  pop %r10
  pop %r9
  pop %rdi
  pop %rdx
  pop %rcx
  test %eax,%eax
  jg .Lsort_swap\@
  jmp .Lsort_next\@
.Lsort_plain\@:
  cmp $2,%r8d
  jne .Lsort_scalar\@
  xor %eax,%eax
.Lsort_bytes\@:
  cmp (%r9),%rax
  jae .Lsort_next\@
  cmp (%r10),%rax
  jae .Lsort_swap\@
  movzbl 8(%r9,%rax),%r11d
  cmp 8(%r10,%rax),%r11b
  ja .Lsort_swap\@
  jb .Lsort_next\@
  inc %rax
  jmp .Lsort_bytes\@
.Lsort_scalar\@:
  cmp $24,%r8d
  je .Lsort_float\@
  cmp %r10,%r9
  jle .Lsort_next\@
  jmp .Lsort_swap\@
.Lsort_float\@:
  movq %r9,%xmm0
  movq %r10,%xmm1
  ucomisd %xmm1,%xmm0
  jbe .Lsort_next\@
.Lsort_swap\@:
  mov %rdx,%rax
  shl $4,%rax
  mov (%rdi,%rax),%r11
  mov %r10,-8(%rdi,%rax)
  mov 16(%rdi,%rax),%r10
  mov %r10,(%rdi,%rax)
  mov %r9,8(%rdi,%rax)
  mov %r11,16(%rdi,%rax)
  dec %rdx
  jnz .Lsort_inner\@
.Lsort_next\@:
  inc %rcx
  jmp .Lsort_outer\@
.Lsort_done\@:
  ret
.endm

# A map of more than 32 entries, or one whose first word has bit 62 set (a
# branch over other nodes), is the collector's to serve (spec/memory-x86_64.s,
# "Maps"; alchem-memory.md): the calls through 0x400428 to 0x400450, for
# every kind of key.
.section .text.nm_get,"ax"
  pop %rdx
  pop %rsi
  pop %rdi
  cmpq $32,(%rdi)
  jbe 0f
  call *0x400428
  jmp 4f
0:
  push %rdx
  push %r9
  call .Lget_find
  pop %r9
  pop %rdx
  test %rax,%rax
  js 2f
  cmp $2,%r9d
  je 3f
  shl $4,%rax
  mov 16(%rdi,%rax),%rax
  test %r9d,%r9d
  jz 4f
  box_value
  jmp 4f
2:
  mov %rdx,%rax
  test %r9d,%r9d
  jz 4f
  xor %eax,%eax
  jmp 4f
3:
  mov $1,%eax
  jmp 4f
  map_find .Lget_find .Lget_key
  map_key .Lget_key
4:
.section .text.nm_put,"ax"
  pop %rdx
  pop %rsi
  pop %rdi
  cmpq $32,(%rdi)
  jb 0f
  call *0x400430
  jmp 3f
0:
  push %r8
  call .Lput_find
  push %rdx
  push %rsi
  push %rax
  push %rdi
  mov (%rdi),%rcx
  test %rax,%rax
  jns 1f
  inc %rcx
1:
  mov %rcx,%r9
  shl $1,%rcx
  arena_count
  mov %r9,(%rax)
  mov %rax,%r8
  pop %rsi
  mov (%rsi),%rcx
  shl $1,%rcx
  add $8,%rsi
  lea 8(%rax),%rdi
  cld
  rep movsq
  pop %rax
  pop %rsi
  pop %rdx
  test %rax,%rax
  jns 2f
  lea -1(%r9),%rax
2:
  shl $4,%rax
  mov %rsi,8(%r8,%rax)
  mov %rdx,16(%r8,%rax)
  mov %r8,%rdi
  pop %r8
  call .Lput_sort
  mov %rdi,%rax
  jmp 3f
  map_find .Lput_find .Lput_key
  map_sort .Lput_sort .Lput_key
  map_key .Lput_key
3:
.section .text.nm_delete,"ax"
  pop %rsi
  pop %rdi
  cmpq $32,(%rdi)
  jbe 0f
  call *0x400438
  jmp 5f
0:
  call .Ldelete_find
  mov %rax,%r9
  mov %rdi,%rsi
  mov (%rdi),%rcx
  test %rax,%rax
  js 1f
  dec %rcx
1:
  mov %rcx,%r10
  shl $1,%rcx
  arena_count
  mov %r10,(%rax)
  mov %rax,%r8
  lea 8(%rax),%rdi
  mov (%rsi),%rcx
  xor %edx,%edx
2:
  cmp %rcx,%rdx
  jae 4f
  cmp %r9,%rdx
  je 3f
  mov %rdx,%rax
  shl $4,%rax
  mov 8(%rsi,%rax),%r10
  mov 16(%rsi,%rax),%r11
  mov %r10,(%rdi)
  mov %r11,8(%rdi)
  add $16,%rdi
3:
  inc %rdx
  jmp 2b
  map_find .Ldelete_find .Ldelete_key
  map_key .Ldelete_key
4:
  mov %r8,%rax
5:
.section .text.nm_entries,"ax"
  pop %rsi
  mov (%rsi),%rcx
  bt $62,%rcx
  jnc 0f
  mov %rsi,%rdi
  call *0x400440
  jmp 7f
0:
  arena_list
  mov %rax,%r8
  xor %r9d,%r9d
1:
  cmp %rcx,%r9
  jae 6f
  mov %r9,%rdx
  shl $4,%rdx
  cmp $1,%r10d
  je 2f
  cmp $2,%r10d
  je 3f
  mov 8(%rsi,%rdx),%rax
  jmp 5f
2:
  mov 16(%rsi,%rdx),%rax
  jmp 5f
3:
  lea 24(%r12),%r11
  cmp %r13,%r11
  jbe 4f
  call *0x400478
4:
  movq $2,(%r12)
  mov 8(%rsi,%rdx),%rdi
  mov 16(%rsi,%rdx),%rax
  mov %rdi,8(%r12)
  mov %rax,16(%r12)
  mov %r12,%rax
  mov %r11,%r12
5:
  mov %r9,%rdx
  shl $4,%rdx
  mov %rax,8(%r8,%rdx)
  mov %rcx,%rax
  sub %r9,%rax
  mov %rax,(%r8,%rdx)
  inc %r9
  jmp 1b
6:
  mov %r8,%rax
7:
.section .text.nm_new,"ax"
  pop %rsi
  mov (%rsi),%rcx
  cmp $32,%rcx
  jbe 0f
  mov %rsi,%rdi
  call *0x400448
  jmp 6f
0:
  mov %rcx,%r9
  shl $1,%rcx
  arena_count
  mov %rax,%rdi
  movq $0,(%rdi)
  mov %r9,%rcx
  xor %edx,%edx
1:
  cmp %rcx,%rdx
  jae 5f
  mov %rdx,%rax
  shl $4,%rax
  mov 8(%rsi,%rax),%rax
  push %rsi
  push %rdx
  push %rcx
  mov 8(%rax),%rsi
  mov 16(%rax),%rdx
  push %rdx
  push %rsi
  call .Lnew_find
  pop %rsi
  pop %rdx
  test %rax,%rax
  jns 2f
  mov (%rdi),%rax
  incq (%rdi)
2:
  shl $4,%rax
  mov %rsi,8(%rdi,%rax)
  mov %rdx,16(%rdi,%rax)
  pop %rcx
  pop %rdx
  pop %rsi
  inc %rdx
  jmp 1b
  map_find .Lnew_find .Lnew_key
  map_sort .Lnew_sort .Lnew_key
  map_key .Lnew_key
5:
  call .Lnew_sort
  mov %rdi,%rax
6:
