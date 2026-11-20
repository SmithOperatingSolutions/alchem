# The pinned stable sort: Go's stable_func (insertion sort over blocks of 20, SymMerge).
# Compiled from spec/sort-runtime.c (gcc 13.3 -Os with RBP and R12 to R15
# fixed, RBX call-clobbered, no red zone, general registers only) and kept
# as the checked reference: scripts/generate-sort-runtime.py assembles this
# file. Entry at offset 0: RDI the words, RSI their number, RDX the function
# value asked "is the first less than the second" (called with its address
# in R10 and the two words in RDI and RSI). Sorts in place; keeps RBP and R12
# to R15 and uses no frame of its own, so a failure inside the function is
# traced from the caller's frame.
	.text
	jmp	sort_entry
less:
	movq	(%rdi), %rax
	movq	8(%rdi), %r10
	movq	(%rax,%rsi,8), %rdi
	movq	(%rax,%rdx,8), %rsi
#APP
# 15 "sort.c" 1
	call *(%r10)
# 0 "" 2
#NO_APP
	testb	%al, %al
	setne	%al
	movzbl	%al, %eax
	ret
insertion:
	movq	%rsi, %rax
	subq	$56, %rsp
	incq	%rax
	movq	%rdi, 16(%rsp)
	movq	%rsi, 24(%rsp)
	movq	%rdx, 32(%rsp)
	movq	%rax, (%rsp)
.L3:
	movq	32(%rsp), %rcx
	cmpq	%rcx, (%rsp)
	jge	.L11
	movq	(%rsp), %rsi
.L7:
	movq	24(%rsp), %rax
	cmpq	%rax, %rsi
	jg	.L4
.L6:
	incq	(%rsp)
	jmp	.L3
.L4:
	leaq	-1(%rsi), %rax
	movq	16(%rsp), %rdi
	movq	%rsi, 40(%rsp)
	movq	%rax, %rdx
	movq	%rax, 8(%rsp)
	call	less
	movq	40(%rsp), %rsi
	testl	%eax, %eax
	je	.L6
	movq	16(%rsp), %rax
	movq	8(%rsp), %rdx
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	8(%rsp), %rsi
	jmp	.L7
.L11:
	addq	$56, %rsp
	ret
swap_range:
	xorl	%eax, %eax
	movq	%rdi, %rbx
	movq	%rsi, %r8
	movq	%rdx, %r9
	cmpq	%rcx, %rax
	jl	.L17
	ret
.L17:
	subq	$56, %rsp
.L14:
	movq	(%rbx), %rdi
	leaq	(%r9,%rax), %rdx
	leaq	(%r8,%rax), %rsi
	movq	%rcx, 40(%rsp)
	movq	%r9, 32(%rsp)
	movq	%rax, 24(%rsp)
	movq	%r8, 16(%rsp)
	movq	%rbx, 8(%rsp)
	call	swap.isra.0
	movq	24(%rsp), %rax
	movq	40(%rsp), %rcx
	movq	32(%rsp), %r9
	movq	16(%rsp), %r8
	incq	%rax
	movq	8(%rsp), %rbx
	cmpq	%rcx, %rax
	jl	.L14
	addq	$56, %rsp
	ret
rotate:
	subq	$40, %rsp
	movq	%rdx, %rbx
	subq	%rdx, %rcx
	movq	%rdx, %rax
	movq	%rdi, (%rsp)
	subq	%rsi, %rbx
	movq	%rcx, %r8
.L19:
	movq	%rax, %rsi
	subq	%rbx, %rsi
	cmpq	%r8, %rbx
	je	.L24
	jle	.L20
	movq	(%rsp), %rdi
	movq	%r8, %rcx
	movq	%rax, %rdx
	movq	%rbx, 24(%rsp)
	movq	%r8, 16(%rsp)
	movq	%rax, 8(%rsp)
	call	swap_range
	movq	16(%rsp), %r8
	movq	24(%rsp), %rbx
	movq	8(%rsp), %rax
	subq	%r8, %rbx
	jmp	.L19
.L20:
	leaq	(%r8,%rax), %rdx
	movq	(%rsp), %rdi
	movq	%rbx, %rcx
	movq	%rax, 24(%rsp)
	subq	%rbx, %rdx
	movq	%r8, 16(%rsp)
	movq	%rbx, 8(%rsp)
	call	swap_range
	movq	8(%rsp), %rbx
	movq	16(%rsp), %r8
	movq	24(%rsp), %rax
	subq	%rbx, %r8
	jmp	.L19
.L24:
	movq	(%rsp), %rdi
	movq	%rbx, %rcx
	movq	%rax, %rdx
	addq	$40, %rsp
	jmp	swap_range
sym_merge:
	subq	$88, %rsp
	movq	%rsi, %r8
	movq	%rdx, %rbx
	movq	%rdi, 16(%rsp)
	movq	%rcx, (%rsp)
.L45:
	movq	%rbx, %rax
	subq	%r8, %rax
	decq	%rax
	jne	.L70
.L26:
	movq	(%rsp), %rax
	cmpq	%rax, %rbx
	jge	.L30
	movq	(%rsp), %rax
	movq	16(%rsp), %rdi
	movq	%r8, %rdx
	movq	%rbx, 32(%rsp)
	movq	%r8, 24(%rsp)
	leaq	(%rbx,%rax), %rcx
	shrq	%rcx
	movq	%rcx, %rsi
	movq	%rcx, 8(%rsp)
	call	less
	movq	8(%rsp), %rcx
	movq	24(%rsp), %r8
	testl	%eax, %eax
	movq	32(%rsp), %rbx
	je	.L28
	leaq	1(%rcx), %rbx
	movq	(%rsp), %rcx
.L28:
	movq	%rcx, (%rsp)
	jmp	.L26
.L30:
	leaq	-1(%rbx), %rax
	cmpq	%r8, %rax
	jle	.L25
	leaq	1(%r8), %rax
	movq	%r8, %rsi
	movq	%rbx, 8(%rsp)
	movq	%rax, (%rsp)
	movq	%rax, %rdx
	movq	16(%rsp), %rax
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	(%rsp), %r8
	movq	8(%rsp), %rbx
	jmp	.L30
.L70:
	movq	(%rsp), %rax
	subq	%rbx, %rax
	decq	%rax
	jne	.L71
	movq	%rbx, %rcx
.L33:
	cmpq	%rcx, %r8
	jge	.L37
	leaq	(%r8,%rcx), %rdx
	movq	16(%rsp), %rdi
	movq	%rbx, %rsi
	movq	%rbx, (%rsp)
	shrq	%rdx
	movq	%r8, 24(%rsp)
	movq	%rdx, 8(%rsp)
	movq	%rcx, 32(%rsp)
	call	less
	movq	(%rsp), %rbx
	movq	8(%rsp), %rdx
	testl	%eax, %eax
	movq	24(%rsp), %r8
	jne	.L35
	leaq	1(%rdx), %r8
	movq	32(%rsp), %rdx
.L35:
	movq	%rdx, %rcx
	jmp	.L33
.L37:
	cmpq	%rbx, %r8
	jge	.L25
	leaq	-1(%rbx), %rax
	movq	%rbx, %rsi
	movq	%r8, 8(%rsp)
	movq	%rax, (%rsp)
	movq	%rax, %rdx
	movq	16(%rsp), %rax
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	(%rsp), %rbx
	movq	8(%rsp), %r8
	jmp	.L37
.L71:
	movq	(%rsp), %rax
	addq	%r8, %rax
	shrq	%rax
	movq	%rax, 8(%rsp)
	leaq	(%rbx,%rax), %rcx
	cmpq	%rax, %rbx
	jle	.L48
	movq	(%rsp), %rax
	movq	%rcx, %r9
	movq	8(%rsp), %r10
	subq	%rax, %r9
	jmp	.L39
.L48:
	movq	%rbx, %r10
	movq	%r8, %r9
.L39:
	leaq	-1(%rcx), %rax
	movq	%rax, 24(%rsp)
.L40:
	cmpq	%r10, %r9
	jge	.L73
	leaq	(%r9,%r10), %rdx
	movq	24(%rsp), %rsi
	movq	16(%rsp), %rdi
	movq	%rbx, 72(%rsp)
	shrq	%rdx
	movq	%r8, 64(%rsp)
	subq	%rdx, %rsi
	movq	%rcx, 56(%rsp)
	movq	%r9, 40(%rsp)
	movq	%rdx, 32(%rsp)
	movq	%r10, 48(%rsp)
	call	less
	movq	32(%rsp), %rdx
	movq	40(%rsp), %r9
	testl	%eax, %eax
	movq	56(%rsp), %rcx
	movq	64(%rsp), %r8
	movq	72(%rsp), %rbx
	jne	.L41
	leaq	1(%rdx), %r9
	movq	48(%rsp), %rdx
.L41:
	movq	%rdx, %r10
	jmp	.L40
.L73:
	movq	%rcx, %rax
	subq	%r9, %rax
	cmpq	%rbx, %r9
	jge	.L43
	cmpq	%rax, %rbx
	jge	.L43
	movq	16(%rsp), %rdi
	movq	%rax, %rcx
	movq	%r9, %rsi
	movq	%rbx, %rdx
	movq	%r8, 40(%rsp)
	movq	%rax, 32(%rsp)
	movq	%r9, 24(%rsp)
	call	rotate
	movq	40(%rsp), %r8
	movq	32(%rsp), %rax
	movq	24(%rsp), %r9
.L43:
	cmpq	%r8, %r9
	jle	.L44
	movq	8(%rsp), %rdi
	cmpq	%rdi, %r9
	jge	.L44
	movq	%rdi, %rcx
	movq	16(%rsp), %rdi
	movq	%r9, %rdx
	movq	%r8, %rsi
	movq	%rax, 24(%rsp)
	call	sym_merge
	movq	24(%rsp), %rax
.L44:
	cmpq	%rax, 8(%rsp)
	jge	.L25
	cmpq	%rax, (%rsp)
	jle	.L25
	movq	8(%rsp), %r8
	movq	%rax, %rbx
	jmp	.L45
.L25:
	addq	$88, %rsp
	ret
sort_entry:
	subq	$56, %rsp
	movl	$20, %eax
	movq	%rsi, (%rsp)
	movq	%rdi, 32(%rsp)
	movq	%rdx, 40(%rsp)
.L75:
	movq	(%rsp), %rbx
	leaq	-20(%rax), %rsi
	cmpq	%rbx, %rax
	jg	.L83
	movq	%rax, %rdx
	leaq	32(%rsp), %rdi
	movq	%rax, 8(%rsp)
	call	insertion
	movq	8(%rsp), %rax
	addq	$20, %rax
	jmp	.L75
.L83:
	movq	%rbx, %rdx
	leaq	32(%rsp), %rdi
	call	insertion
	movl	$20, %eax
.L77:
	movq	(%rsp), %rdi
	cmpq	%rdi, %rax
	jge	.L84
	leaq	(%rax,%rax), %rbx
	xorl	%esi, %esi
	movq	%rbx, 8(%rsp)
.L78:
	movq	8(%rsp), %rbx
	leaq	(%rsi,%rbx), %rcx
	movq	(%rsp), %rbx
	movq	%rcx, %rdx
	subq	%rax, %rdx
	cmpq	%rbx, %rcx
	jg	.L85
	leaq	32(%rsp), %rdi
	movq	%rax, 24(%rsp)
	movq	%rcx, 16(%rsp)
	call	sym_merge
	movq	16(%rsp), %rsi
	movq	24(%rsp), %rax
	jmp	.L78
.L85:
	cmpq	%rdx, %rbx
	jle	.L80
	movq	%rbx, %rcx
	leaq	32(%rsp), %rdi
	call	sym_merge
.L80:
	movq	8(%rsp), %rax
	jmp	.L77
.L84:
	addq	$56, %rsp
	ret
swap.isra.0:
	movq	%rdx, %rax
	leaq	(%rdi,%rsi,8), %rdx
	leaq	(%rdi,%rax,8), %rax
	movq	(%rdx), %rcx
	movq	(%rax), %rbx
	movq	%rbx, (%rdx)
	movq	%rcx, (%rax)
	ret
