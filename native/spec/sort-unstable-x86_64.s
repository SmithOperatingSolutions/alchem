# The pinned unstable sort: Go's pdqsort_func as sort.Slice runs it.
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
sift_down:
	subq	$56, %rsp
	movq	%rsi, %rbx
	movq	%rdi, 8(%rsp)
	movq	%rdx, 24(%rsp)
	movq	%rcx, 16(%rsp)
.L16:
	leaq	(%rbx,%rbx), %rax
	movq	24(%rsp), %rdi
	leaq	1(%rax), %rcx
	cmpq	%rdi, %rcx
	jge	.L12
	addq	$2, %rax
	movq	%rax, (%rsp)
	cmpq	%rdi, %rax
	jge	.L14
	movq	16(%rsp), %rax
	movq	8(%rsp), %rdi
	movq	%rbx, 40(%rsp)
	movq	%rcx, 32(%rsp)
	leaq	(%rcx,%rax), %rsi
	leaq	1(%rsi), %rdx
	call	less
	movq	32(%rsp), %rcx
	movq	40(%rsp), %rbx
	testl	%eax, %eax
	jne	.L15
.L14:
	movq	%rcx, (%rsp)
.L15:
	movq	16(%rsp), %rcx
	movq	(%rsp), %rax
	movq	8(%rsp), %rdi
	leaq	(%rax,%rcx), %rdx
	leaq	(%rbx,%rcx), %rsi
	movq	%rdx, 40(%rsp)
	movq	%rsi, 32(%rsp)
	call	less
	testl	%eax, %eax
	je	.L12
	movq	8(%rsp), %rax
	movq	40(%rsp), %rdx
	movq	32(%rsp), %rsi
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	(%rsp), %rbx
	jmp	.L16
.L12:
	addq	$56, %rsp
	ret
heap_sort:
	subq	%rsi, %rdx
	subq	$56, %rsp
	movl	$2, %ecx
	movq	%rdx, %rax
	movq	%rdx, 32(%rsp)
	decq	%rax
	movq	%rdi, 24(%rsp)
	cqto
	movq	%rax, 8(%rsp)
	idivq	%rcx
	movq	%rsi, 16(%rsp)
.L22:
	testq	%rax, %rax
	js	.L24
	movq	16(%rsp), %rcx
	movq	32(%rsp), %rdx
	movq	%rax, %rsi
	movq	%rax, 40(%rsp)
	movq	24(%rsp), %rdi
	call	sift_down
	movq	40(%rsp), %rax
	decq	%rax
	jmp	.L22
.L24:
	cmpq	$0, 8(%rsp)
	js	.L27
	movq	16(%rsp), %rax
	movq	8(%rsp), %rbx
	movq	%rax, %rsi
	leaq	(%rax,%rbx), %rdx
	movq	24(%rsp), %rax
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	16(%rsp), %rcx
	movq	8(%rsp), %rdx
	xorl	%esi, %esi
	movq	24(%rsp), %rdi
	call	sift_down
	decq	8(%rsp)
	jmp	.L24
.L27:
	addq	$56, %rsp
	ret
bit_length:
	bsrq	%rdi, %rax
	xorl	%edx, %edx
	incl	%eax
	testq	%rdi, %rdi
	cmove	%edx, %eax
	ret
break_patterns:
	subq	$72, %rsp
	subq	%rsi, %rdx
	movq	%rdi, 32(%rsp)
	movq	%rdx, 8(%rsp)
	cmpq	$7, %rdx
	jle	.L29
	movq	%rdx, %rdi
	movq	%rdx, 16(%rsp)
	movq	%rsi, %r8
	call	bit_length
	orq	$-1, %rdx
	movq	%rdi, %rbx
	movl	%eax, %ecx
	sarq	$2, %rbx
	salq	%cl, %rdx
	addq	%rbx, %rbx
	notq	%rdx
	addq	%rsi, %rbx
	movq	%rdx, 24(%rsp)
	leaq	-1(%rbx), %rsi
.L31:
	leaq	1(%rbx), %rax
	cmpq	%rsi, %rax
	jl	.L29
	movq	16(%rsp), %rdx
	movq	16(%rsp), %rax
	salq	$13, %rdx
	xorq	%rax, %rdx
	movq	%rdx, %rax
	shrq	$7, %rax
	xorq	%rdx, %rax
	movq	%rax, %rdx
	salq	$17, %rdx
	xorq	%rax, %rdx
	movq	%rdx, 16(%rsp)
	andq	24(%rsp), %rdx
	cmpq	%rdx, 8(%rsp)
	jg	.L32
	movq	8(%rsp), %rax
	subq	%rax, %rdx
.L32:
	movq	32(%rsp), %rax
	addq	%r8, %rdx
	movq	%rbx, 56(%rsp)
	movq	%r8, 48(%rsp)
	movq	(%rax), %rdi
	movq	%rsi, 40(%rsp)
	call	swap.isra.0
	movq	40(%rsp), %rsi
	movq	56(%rsp), %rbx
	movq	48(%rsp), %r8
	incq	%rsi
	jmp	.L31
.L29:
	addq	$72, %rsp
	ret
median:
	subq	$40, %rsp
	movq	%rdx, (%rsp)
	movq	%rsi, %rdx
	movq	%rsi, 8(%rsp)
	movq	(%rsp), %rsi
	movq	%r8, 32(%rsp)
	movq	%rdi, 16(%rsp)
	movq	%rcx, 24(%rsp)
	call	less
	movq	32(%rsp), %r8
	testl	%eax, %eax
	je	.L37
	movq	8(%rsp), %rax
	movq	(%rsp), %rbx
	incq	(%r8)
	movq	%rbx, 8(%rsp)
	movq	%rax, (%rsp)
.L37:
	movq	(%rsp), %rdx
	movq	24(%rsp), %rsi
	movq	%r8, 32(%rsp)
	movq	16(%rsp), %rdi
	call	less
	movq	32(%rsp), %r8
	testl	%eax, %eax
	je	.L38
	movq	24(%rsp), %rax
	incq	(%r8)
	movq	%rax, (%rsp)
.L38:
	movq	8(%rsp), %rdx
	movq	(%rsp), %rsi
	movq	%r8, 24(%rsp)
	movq	16(%rsp), %rdi
	call	less
	testl	%eax, %eax
	je	.L39
	movq	24(%rsp), %r8
	movq	8(%rsp), %rax
	incq	(%r8)
	movq	%rax, (%rsp)
.L39:
	movq	(%rsp), %rax
	addq	$40, %rsp
	ret
choose_pivot:
	subq	%rsi, %rdx
	subq	$56, %rsp
	xorl	%eax, %eax
	movq	%rsi, %rbx
	movq	%rax, 48(%rsp)
	movq	%rdx, %rax
	movl	$4, %esi
	movq	%rcx, 8(%rsp)
	movq	%rdx, %rcx
	cqto
	idivq	%rsi
	movq	%rdi, (%rsp)
	leaq	(%rax,%rax), %r9
	addq	%r9, %rbx
	cmpq	$7, %rcx
	jle	.L51
	movq	%rbx, %r10
	subq	%rax, %r10
	addq	%r10, %r9
	cmpq	$49, %rcx
	jle	.L52
	leaq	1(%r10), %rcx
	leaq	-1(%r10), %rsi
	movq	%r10, %rdx
	movq	%r9, 32(%rsp)
	leaq	48(%rsp), %r8
	movq	%rbx, 16(%rsp)
	call	median
	movq	16(%rsp), %rbx
	movq	(%rsp), %rdi
	leaq	48(%rsp), %r8
	movq	%rax, 24(%rsp)
	leaq	1(%rbx), %rcx
	leaq	-1(%rbx), %rsi
	movq	%rbx, %rdx
	call	median
	movq	32(%rsp), %r9
	movq	(%rsp), %rdi
	leaq	48(%rsp), %r8
	movq	%rax, 16(%rsp)
	leaq	1(%r9), %rcx
	leaq	-1(%r9), %rsi
	movq	%r9, %rdx
	call	median
	movq	24(%rsp), %r10
	movq	16(%rsp), %rbx
	movq	%rax, %r9
.L52:
	movq	(%rsp), %rdi
	movq	%rbx, %rdx
	leaq	48(%rsp), %r8
	movq	%r9, %rcx
	movq	%r10, %rsi
	call	median
	movq	%rax, %rbx
.L51:
	movq	48(%rsp), %rdx
	movl	$1, %eax
	testq	%rdx, %rdx
	je	.L53
	xorl	%eax, %eax
	cmpq	$12, %rdx
	sete	%al
	addq	%rax, %rax
.L53:
	movq	8(%rsp), %rdi
	movq	%rax, (%rdi)
	movq	%rbx, %rax
	addq	$56, %rsp
	ret
partial_insertion:
	movq	%rsi, %rax
	subq	$72, %rsp
	incq	%rax
	movq	%rdi, 16(%rsp)
	movq	%rsi, 40(%rsp)
	movq	%rdx, 32(%rsp)
	movq	%rax, 8(%rsp)
	movq	$5, 48(%rsp)
.L72:
	movq	32(%rsp), %rbx
	cmpq	%rbx, 8(%rsp)
	jl	.L59
	jne	.L61
	jmp	.L83
.L59:
	movq	8(%rsp), %rax
	movq	16(%rsp), %rdi
	leaq	-1(%rax), %rdx
	movq	%rax, %rsi
	call	less
	testl	%eax, %eax
	jne	.L61
	incq	8(%rsp)
	jmp	.L72
.L61:
	movq	32(%rsp), %rax
	movq	40(%rsp), %rbx
	subq	%rbx, %rax
	cmpq	$49, %rax
	jg	.L63
.L69:
	xorl	%eax, %eax
	jmp	.L57
.L63:
	movq	8(%rsp), %rax
	leaq	-1(%rax), %rcx
	movq	%rax, %rsi
	movq	16(%rsp), %rax
	movq	%rcx, %rdx
	movq	%rcx, 24(%rsp)
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	8(%rsp), %rax
	movq	40(%rsp), %rbx
	movq	24(%rsp), %rcx
	subq	%rbx, %rax
	decq	%rax
	jg	.L64
.L67:
	movq	32(%rsp), %rax
	movq	8(%rsp), %rbx
	subq	%rbx, %rax
	decq	%rax
	jle	.L66
	jmp	.L84
.L68:
	leaq	-1(%rcx), %rax
	movq	16(%rsp), %rdi
	movq	%rcx, %rsi
	movq	%rcx, 56(%rsp)
	movq	%rax, %rdx
	movq	%rax, 24(%rsp)
	call	less
	testl	%eax, %eax
	je	.L67
	movq	16(%rsp), %rax
	movq	24(%rsp), %rdx
	movq	56(%rsp), %rsi
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	24(%rsp), %rcx
.L64:
	testq	%rcx, %rcx
	jg	.L68
	jmp	.L67
.L84:
	movq	8(%rsp), %rax
	incq	%rax
	movq	%rax, 24(%rsp)
.L70:
	movq	32(%rsp), %rbx
	cmpq	%rbx, 24(%rsp)
	jl	.L71
.L66:
	decq	48(%rsp)
	jne	.L72
	jmp	.L69
.L71:
	movq	24(%rsp), %rax
	movq	16(%rsp), %rdi
	leaq	-1(%rax), %rdx
	movq	%rax, %rsi
	movq	%rdx, 56(%rsp)
	call	less
	testl	%eax, %eax
	je	.L66
	movq	16(%rsp), %rax
	movq	56(%rsp), %rdx
	movq	24(%rsp), %rsi
	movq	(%rax), %rdi
	call	swap.isra.0
	incq	24(%rsp)
	jmp	.L70
.L83:
	movl	$1, %eax
.L57:
	addq	$72, %rsp
	ret
partition_equal:
	subq	$40, %rsp
	movq	%rdi, 8(%rsp)
	movq	(%rdi), %rdi
	movq	%rdx, (%rsp)
	movq	%rcx, %rdx
	movq	%rsi, 16(%rsp)
	call	swap.isra.0
	movq	16(%rsp), %rax
	movq	(%rsp), %rcx
	incq	%rax
	decq	%rcx
	movq	%rax, (%rsp)
.L86:
	cmpq	%rcx, (%rsp)
	jg	.L85
	movq	(%rsp), %rdx
	movq	16(%rsp), %rsi
	movq	%rcx, 24(%rsp)
	movq	8(%rsp), %rdi
	call	less
	movq	24(%rsp), %rcx
	testl	%eax, %eax
	jne	.L90
.L88:
	incq	(%rsp)
	jmp	.L86
.L97:
	movq	16(%rsp), %rsi
	movq	8(%rsp), %rdi
	movq	%rcx, %rdx
	movq	%rcx, 24(%rsp)
	call	less
	movq	24(%rsp), %rcx
	leaq	-1(%rcx), %rbx
	testl	%eax, %eax
	je	.L96
	movq	%rbx, %rcx
.L90:
	cmpq	%rcx, (%rsp)
	jle	.L97
	jmp	.L85
.L96:
	movq	8(%rsp), %rax
	movq	(%rsp), %rsi
	movq	%rcx, %rdx
	movq	%rbx, 24(%rsp)
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	24(%rsp), %rcx
	jmp	.L88
.L85:
	movq	(%rsp), %rax
	addq	$40, %rsp
	ret
partition:
	subq	$56, %rsp
	movq	%rdi, 8(%rsp)
	movq	(%rdi), %rdi
	movq	%rdx, (%rsp)
	movq	%rcx, %rdx
	movq	%rsi, 16(%rsp)
	movq	%r8, 32(%rsp)
	call	swap.isra.0
	movq	16(%rsp), %rax
	incq	%rax
	movq	%rax, 24(%rsp)
	movq	(%rsp), %rax
	decq	%rax
	movq	%rax, (%rsp)
.L99:
	movq	(%rsp), %rbx
	cmpq	%rbx, 24(%rsp)
	jg	.L114
	movq	16(%rsp), %rdx
	movq	24(%rsp), %rsi
	movq	8(%rsp), %rdi
	call	less
	testl	%eax, %eax
	je	.L101
	incq	24(%rsp)
	jmp	.L99
.L104:
	movq	16(%rsp), %rdx
	movq	(%rsp), %rsi
	movq	8(%rsp), %rdi
	call	less
	testl	%eax, %eax
	movq	(%rsp), %rax
	leaq	-1(%rax), %rax
	jne	.L117
	movq	%rax, (%rsp)
.L101:
	movq	(%rsp), %rbx
	cmpq	%rbx, 24(%rsp)
	jle	.L104
.L114:
	movq	8(%rsp), %rax
	movq	16(%rsp), %rdx
	movq	(%rsp), %rsi
	movq	(%rax), %rdi
	call	swap.isra.0
	movl	$1, %eax
	jmp	.L105
.L117:
	movq	(%rsp), %rdx
	movq	24(%rsp), %rsi
	movq	%rax, 40(%rsp)
	movq	8(%rsp), %rax
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	40(%rsp), %rax
	movq	%rax, (%rsp)
	movq	24(%rsp), %rax
	incq	%rax
	movq	%rax, 24(%rsp)
.L106:
	movq	(%rsp), %rbx
	cmpq	%rbx, 24(%rsp)
	jg	.L109
	movq	16(%rsp), %rdx
	movq	24(%rsp), %rsi
	movq	8(%rsp), %rdi
	call	less
	testl	%eax, %eax
	je	.L112
.L110:
	incq	24(%rsp)
	jmp	.L106
.L111:
	movq	16(%rsp), %rdx
	movq	(%rsp), %rsi
	movq	8(%rsp), %rdi
	call	less
	movq	(%rsp), %rcx
	decq	%rcx
	testl	%eax, %eax
	jne	.L118
	movq	%rcx, (%rsp)
.L112:
	movq	(%rsp), %rbx
	cmpq	%rbx, 24(%rsp)
	jle	.L111
.L109:
	movq	8(%rsp), %rax
	movq	16(%rsp), %rdx
	movq	(%rsp), %rsi
	movq	(%rax), %rdi
	call	swap.isra.0
	xorl	%eax, %eax
	jmp	.L105
.L118:
	movq	8(%rsp), %rax
	movq	(%rsp), %rdx
	movq	%rcx, 40(%rsp)
	movq	24(%rsp), %rsi
	movq	(%rax), %rdi
	call	swap.isra.0
	movq	40(%rsp), %rcx
	movq	%rcx, (%rsp)
	jmp	.L110
.L105:
	movq	32(%rsp), %rbx
	movq	%rax, (%rbx)
	movq	(%rsp), %rax
	addq	$56, %rsp
	ret
pdqsort:
	subq	$120, %rsp
	movq	%rdi, 24(%rsp)
	movq	%rsi, 8(%rsp)
	movq	%rdx, 16(%rsp)
	movq	%rcx, 48(%rsp)
	movq	$1, 56(%rsp)
	movq	$1, 40(%rsp)
.L120:
	movq	16(%rsp), %rax
	movq	8(%rsp), %rbx
	subq	%rbx, %rax
	movq	%rax, 64(%rsp)
	cmpq	$12, %rax
	jg	.L121
	movq	16(%rsp), %rdx
	movq	24(%rsp), %rdi
	movq	%rbx, %rsi
	addq	$120, %rsp
	jmp	insertion
.L121:
	cmpq	$0, 48(%rsp)
	jne	.L122
	movq	16(%rsp), %rdx
	movq	8(%rsp), %rsi
	movq	24(%rsp), %rdi
	addq	$120, %rsp
	jmp	heap_sort
.L122:
	cmpq	$0, 40(%rsp)
	jne	.L123
	movq	16(%rsp), %rdx
	movq	8(%rsp), %rsi
	movq	24(%rsp), %rdi
	call	break_patterns
	decq	48(%rsp)
.L123:
	movq	16(%rsp), %rdx
	movq	8(%rsp), %rsi
	leaq	96(%rsp), %rcx
	movq	24(%rsp), %rdi
	call	choose_pivot
	cmpq	$2, 96(%rsp)
	movq	%rax, 32(%rsp)
	jne	.L124
	movq	16(%rsp), %rax
	movq	8(%rsp), %rcx
	leaq	-1(%rax), %rbx
	movq	%rbx, %rax
.L125:
	cmpq	%rax, %rcx
	jge	.L141
	movq	%rax, 80(%rsp)
	movq	%rax, %rdx
	movq	24(%rsp), %rax
	movq	%rcx, %rsi
	movq	%rbx, 88(%rsp)
	movq	(%rax), %rdi
	movq	%rcx, 72(%rsp)
	call	swap.isra.0
	movq	72(%rsp), %rcx
	movq	80(%rsp), %rax
	movq	88(%rsp), %rbx
	incq	%rcx
	decq	%rax
	jmp	.L125
.L141:
	movq	32(%rsp), %rax
	movq	8(%rsp), %rdi
	movq	$1, 96(%rsp)
	subq	%rdi, %rax
	subq	%rax, %rbx
	movq	%rbx, 32(%rsp)
.L124:
	cmpq	$0, 56(%rsp)
	je	.L131
	cmpq	$0, 40(%rsp)
	jne	.L127
.L131:
	cmpq	$0, 8(%rsp)
	jg	.L129
	jmp	.L130
.L127:
	cmpq	$1, 96(%rsp)
	jne	.L131
	movq	16(%rsp), %rdx
	movq	8(%rsp), %rsi
	movq	24(%rsp), %rdi
	call	partial_insertion
	testl	%eax, %eax
	je	.L131
	addq	$120, %rsp
	ret
.L129:
	movq	8(%rsp), %rax
	movq	32(%rsp), %rdx
	movq	24(%rsp), %rdi
	leaq	-1(%rax), %rsi
	call	less
	testl	%eax, %eax
	jne	.L130
	movq	32(%rsp), %rcx
	movq	16(%rsp), %rdx
	movq	8(%rsp), %rsi
	movq	24(%rsp), %rdi
	call	partition_equal
	jmp	.L140
.L130:
	movq	32(%rsp), %rcx
	movq	16(%rsp), %rdx
	leaq	104(%rsp), %r8
	movq	24(%rsp), %rdi
	movq	8(%rsp), %rsi
	call	partition
	movq	104(%rsp), %rbx
	movq	8(%rsp), %rdi
	movq	16(%rsp), %rcx
	movq	64(%rsp), %rdx
	movq	%rbx, 56(%rsp)
	movq	%rax, %rbx
	subq	%rdi, %rbx
	subq	%rax, %rcx
	sarq	$3, %rdx
	cmpq	%rcx, %rbx
	jge	.L134
	cmpq	%rdx, %rbx
	movq	%rdi, %rsi
	movq	48(%rsp), %rcx
	movq	24(%rsp), %rdi
	setge	%bl
	movq	%rax, %rdx
	movq	%rax, 32(%rsp)
	movzbl	%bl, %ebx
	movq	%rbx, 40(%rsp)
	call	pdqsort
	movq	32(%rsp), %rax
	incq	%rax
.L140:
	movq	%rax, 8(%rsp)
	jmp	.L120
.L134:
	xorl	%esi, %esi
	cmpq	%rdx, %rcx
	movq	24(%rsp), %rdi
	movq	48(%rsp), %rcx
	setge	%sil
	movq	16(%rsp), %rdx
	movq	%rax, 32(%rsp)
	movq	%rsi, 40(%rsp)
	leaq	1(%rax), %rsi
	call	pdqsort
	movq	32(%rsp), %rax
	movq	%rax, 16(%rsp)
	jmp	.L120
sort_entry:
	subq	$24, %rsp
	movq	%rdi, (%rsp)
	movq	%rsi, %rdi
	movq	%rdx, 8(%rsp)
	call	bit_length
	movq	%rsi, %rdx
	movq	%rsp, %rdi
	xorl	%esi, %esi
	movslq	%eax, %rcx
	call	pdqsort
	addq	$24, %rsp
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
