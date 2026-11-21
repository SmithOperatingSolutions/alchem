# The Windows layer of a native program (spec/windows.md).
#
# The image of a Windows program is the Linux image at 0x400000 with every
# `syscall` made `ud2` (nc_sc, nc_os), and this layer below it: the PE
# entry, which builds a Linux initial stack and jumps to 0x400080, and a
# vectored exception handler that makes each system call with kernel32
# and commits reserved memory as it is touched.
#
# scripts/generate-windows-runtime.py links it at IMAGE_BASE + 0x1000
# (code and the import tables, RX) and IMAGE_BASE + 0x10000 (data, RW), and
# lays out the PE headers before it (native-windows-data.alc).
#
# A system call keeps the Linux contract: the number in RAX, the arguments
# in RDI, RSI, RDX, R10, R8 and R9, the result or -errno in RAX, RCX the
# address after the call and R11 the flags, every other register kept.
        .intel_syntax noprefix
        .set IMAGE_BASE, 0x380000
        .set REGIONS, 1024      # the program's memory: reservations and allocations
        .set FDS, 1024          # descriptors

        .text
        .globl start
start:
        sub rsp, 40
        # The handler runs on this thread's own stack, which stops growing
        # once the TEB names the program's (windows-layer.c, Stacks): 512 KiB
        # of it are touched now, from the top down, while it still grows.
        mov rax, rsp
        mov ecx, 128
.Lprobe:
        sub rax, 4096
        cmp byte ptr [rax], 0
        dec ecx
        jnz .Lprobe
        # A band of 64 KiB of guard pages below each stack's committed part.
        mov dword ptr [rsp+32], 65536
        lea rcx, [rsp+32]
        call [rip+imp_SetThreadStackGuarantee]
        mov ecx, 1
        lea rdx, [rip+handler]
        call [rip+imp_AddVectoredExceptionHandler]
        # The TEB's stack of this thread, which the handler runs on: it is
        # put back there while the handler runs (Windows' functions probe
        # their frames against it, __chkstk).
        mov rax, gs:[0x8]
        mov [rip+thread_teb], rax
        mov rax, gs:[0x10]
        mov [rip+thread_teb+8], rax
        mov rax, gs:[0x1478]
        mov [rip+thread_teb+16], rax
        call linux_stack
        mov [rip+win_rsp], rsp
        mov rsp, rax
        mov eax, 0x400080
        jmp rax

# The Linux initial stack, in rax: argc, argv, NULL, the environment, NULL,
# an empty auxiliary vector. The command line and the environment are
# UTF-8, and the command line is split as Go's os package splits it
# (commandLineToArgv): an argument ends at a space or tab outside quotes,
# 2n backslashes and a quote are n backslashes and a quote that opens or
# closes, 2n+1 and a quote are n and a quote, "" within quotes is a quote.
linux_stack:
        push rbx
        push rsi
        push rdi
        push r12
        push r13
        push r14
        push r15
        sub rsp, 64
        call [rip+imp_GetCommandLineW]
        mov r12, rax
        xor r13d, r13d          # its length in UTF-16 units
.Lwl:
        cmp word ptr [r12+r13*2], 0
        je .Lwl_done
        inc r13
        jmp .Lwl
.Lwl_done:
        # An empty command line: the one argument is the program's path, as
        # Go's os.Args has it (os.Executable), quoted so it stays one.
        test r13, r13
        jnz .Lwl_given
        xor ecx, ecx
        lea rdx, [rip+wpath1+2]
        mov r8d, 32760
        call [rip+imp_GetModuleFileNameW]
        lea r12, [rip+wpath1]
        mov word ptr [r12], 0x22
        mov word ptr [r12+rax*2+2], 0x22
        mov word ptr [r12+rax*2+4], 0
        lea r13, [rax+2]
.Lwl_given:
        call [rip+imp_GetEnvironmentStringsW]
        mov r14, rax
        xor r15d, r15d          # the block's length, its last NUL excluded
        cmp word ptr [r14], 0
        je .Lel_done
.Lel:
        inc r15
        cmp word ptr [r14+r15*2], 0
        jne .Lel
        cmp word ptr [r14+r15*2+2], 0
        je .Lel_entry
        jmp .Lel
.Lel_entry:
        inc r15
.Lel_done:
        # Room: 64 KiB of stack below the pointers, for the exception
        # records Windows pushes there until the program has its own stack,
        # then the pointers, then the command line, the environment and the
        # arguments in UTF-8, at most three bytes for each unit.
        lea rbx, [r13+r15]
        imul rdx, rbx, 24
        add rdx, 65536+4096
        xor ecx, ecx
        mov r8d, 0x3000         # MEM_COMMIT | MEM_RESERVE
        mov r9d, 4
        call [rip+imp_VirtualAlloc]
        test rax, rax
        jz .Lls_fail
        # A region of the program's memory, as mmap's are: it writes words
        # below its first stack pointer (a copy, windows-layer.c, keeps them).
        mov ecx, [rip+region_count]
        shl ecx, 4
        lea rdx, [rip+regions]
        mov [rdx+rcx], rax
        imul r8, rbx, 24
        add r8, 65536+4096
        mov [rdx+rcx+8], r8
        inc dword ptr [rip+region_count]
        lea rsi, [rax+65536]
        lea rdi, [rsi+rbx*8+64] # the command line
        mov rcx, r12
        mov rdx, r13
        mov r8, rdi
        call to_utf8
        mov byte ptr [rdi+rax], 0
        lea r12, [rdi+rax+1]    # the environment
        mov rcx, r14
        mov rdx, r15
        mov r8, r12
        call to_utf8
        mov r13, rax
        mov byte ptr [r12+rax], 0
        lea r15, [r12+rax+1]    # the arguments
        mov rcx, r14
        call [rip+imp_FreeEnvironmentStringsW]
        xor ebx, ebx            # argc
.Lnext_arg:
        mov al, [rdi]
        cmp al, ' '
        je .Lskip
        cmp al, 9
        je .Lskip
        test al, al
        jz .Largs_done
        mov [rsi+8+rbx*8], r15
        inc rbx
        xor r8d, r8d            # within quotes
        xor r9d, r9d            # backslashes pending
.Lc:
        mov al, [rdi]
        test al, al
        jz .Lc_last
        cmp al, '"'
        je .Lc_quote
        cmp al, 92              # backslash
        je .Lc_slash
        test r8d, r8d
        jnz .Lc_plain
        cmp al, ' '
        je .Lc_end
        cmp al, 9
        je .Lc_end
.Lc_plain:
        call .Lslashes
        mov [r15], al
        inc r15
        inc rdi
        jmp .Lc
.Lc_slash:
        inc r9d
        inc rdi
        jmp .Lc
.Lc_quote:
        mov r10d, r9d
        shr r9d, 1
        call .Lslashes
        test r10d, 1
        jnz .Lc_literal
        test r8d, r8d
        jz .Lc_toggle
        cmp byte ptr [rdi+1], '"'
        jne .Lc_toggle
        mov byte ptr [r15], '"'
        inc r15
        inc rdi
.Lc_toggle:
        xor r8d, 1
        inc rdi
        jmp .Lc
.Lc_literal:
        mov byte ptr [r15], '"'
        inc r15
        inc rdi
        jmp .Lc
.Lc_end:
        inc rdi
.Lc_last:
        call .Lslashes
        mov byte ptr [r15], 0
        inc r15
        jmp .Lnext_arg
.Lskip:
        inc rdi
        jmp .Lnext_arg
# r9d backslashes to r15; r9d 0 after.
.Lslashes:
        test r9d, r9d
        jz .Lslashes_done
        mov byte ptr [r15], 92
        inc r15
        dec r9d
        jmp .Lslashes
.Lslashes_done:
        ret
.Largs_done:
        mov [rsi], rbx
        lea rdx, [rsi+8+rbx*8]
        mov qword ptr [rdx], 0
        add rdx, 8
        mov rcx, r12            # each NUL-terminated entry
        lea r8, [r12+r13]
.Lenv:
        cmp rcx, r8
        jae .Lenv_done
        cmp byte ptr [rcx], 0
        je .Lenv_done
        mov [rdx], rcx
        add rdx, 8
.Lenv_skip:
        inc rcx
        cmp byte ptr [rcx-1], 0
        jne .Lenv_skip
        jmp .Lenv
.Lenv_done:
        mov qword ptr [rdx], 0
        mov qword ptr [rdx+8], 0       # AT_NULL
        mov qword ptr [rdx+16], 0
        mov rax, rsi
        add rsp, 64
        pop r15
        pop r14
        pop r13
        pop r12
        pop rdi
        pop rsi
        pop rbx
        ret
.Lls_fail:
        mov ecx, 71
        call [rip+imp_ExitProcess]

# UTF-16 at rcx, rdx units, as UTF-8 at r8 (room for three bytes a unit);
# its length in rax.
to_utf8:
        sub rsp, 72
        xor eax, eax
        test rdx, rdx
        jz .Lu8_done
        mov [rsp+32], r8
        lea rax, [rdx+rdx*2+4]
        mov [rsp+40], rax
        mov qword ptr [rsp+48], 0
        mov qword ptr [rsp+56], 0
        mov r8, rcx
        mov r9, rdx
        mov ecx, 65001          # CP_UTF8
        xor edx, edx
        call [rip+imp_WideCharToMultiByte]
.Lu8_done:
        add rsp, 72
        ret

# LONG handler(EXCEPTION_POINTERS *rcx), called on the stack of the code
# that raised the exception. It runs kernel32 on Windows' own stack.
handler:
        push rbx
        push rbp
        push rsi
        push rdi
        push r12
        push r13
        mov rbp, rsp
        xor eax, eax
        cmp byte ptr [rip+busy], 0
        jne .Lout               # an exception inside the handler: Windows'
        mov byte ptr [rip+busy], 1
        # The program's stack in the TEB is kept, the thread's put there.
        mov rax, gs:[0x8]
        mov [rip+program_teb], rax
        mov rax, gs:[0x10]
        mov [rip+program_teb+8], rax
        mov rax, gs:[0x1478]
        mov [rip+program_teb+16], rax
        mov rax, [rip+thread_teb]
        mov gs:[0x8], rax
        mov rax, [rip+thread_teb+8]
        mov gs:[0x10], rax
        mov rax, [rip+thread_teb+16]
        mov gs:[0x1478], rax
        mov rbx, [rcx]          # EXCEPTION_RECORD
        mov r12, [rcx+8]        # CONTEXT
        mov rsp, [rip+win_rsp]
        sub rsp, 64
        mov eax, [rbx]
        cmp eax, 0xC000001D     # EXCEPTION_ILLEGAL_INSTRUCTION
        je .Lillegal
        cmp eax, 0xC0000005     # EXCEPTION_ACCESS_VIOLATION
        je .Laccess
.Lsearch:
        xor eax, eax            # EXCEPTION_CONTINUE_SEARCH
        jmp .Ldone
.Laccess:
        # A copy of the program (windows-layer.c, fork) first.
        mov rdi, rbx
        call copy_fault
        test eax, eax
        jnz .Lcontinue
        mov rcx, [rbx+0x28]     # the address
        call region_of
        test rax, rax
        jz .Lsignal
        # 64 KiB around the address, within the region [rax, rdx).
        mov rcx, [rbx+0x28]
        and rcx, -65536
        cmp rcx, rax
        cmovb rcx, rax
        lea r8, [rcx+65536]
        add rdx, 4095
        and rdx, -4096
        cmp r8, rdx
        cmova r8, rdx
        mov rdx, r8
        sub rdx, rcx
        mov r8d, 0x1000         # MEM_COMMIT
        mov r9d, 4              # PAGE_READWRITE
        call [rip+imp_VirtualAlloc]
        test rax, rax
        jz .Lsearch
        jmp .Lcontinue
.Lsignal:
        # The SIGSEGV handler rt_sigaction gave, called as Linux would with
        # the address in its siginfo and RIP in its ucontext; it may move RIP.
        mov rax, [rip+segv_handler]
        test rax, rax
        jz .Lsearch
        lea rsi, [rip+siginfo]
        mov rcx, [rbx+0x28]
        mov [rsi+16], rcx
        lea rdx, [rip+ucontext]
        mov rcx, [r12+0xF8]
        mov [rdx+168], rcx
        mov edi, 11
        call rax
        lea rdx, [rip+ucontext]
        mov rcx, [rdx+168]
        cmp rcx, [r12+0xF8]
        je .Lsearch
        mov [r12+0xF8], rcx
        jmp .Lcontinue
.Lillegal:
        mov rax, [r12+0xF8]     # Rip
        cmp word ptr [rax], 0x0B0F
        jne .Lsearch
        call emulate
        mov [r12+0x78], rax     # Rax
        mov rax, [r12+0xF8]
        add rax, 2
        mov [r12+0xF8], rax
        mov [r12+0x80], rax     # Rcx
        mov eax, [r12+0x44]     # EFlags
        mov [r12+0xD0], rax     # R11
.Lcontinue:
        mov eax, -1             # EXCEPTION_CONTINUE_EXECUTION
.Ldone:
        # The program's stack in the TEB again (the thread's limit kept, as
        # the kernel may have moved it).
        mov rcx, gs:[0x10]
        mov [rip+thread_teb+8], rcx
        mov rcx, [rip+program_teb]
        mov gs:[0x8], rcx
        mov rcx, [rip+program_teb+8]
        mov gs:[0x10], rcx
        mov rcx, [rip+program_teb+16]
        mov gs:[0x1478], rcx
        mov byte ptr [rip+busy], 0
.Lout:
        mov rsp, rbp
        pop r13
        pop r12
        pop rdi
        pop rsi
        pop rbp
        pop rbx
        ret

# The region mmap reserved that holds rcx: its start in rax and its end in
# rdx, or rax 0.
region_of:
        lea rdx, [rip+regions]
        mov r8d, [rip+region_count]
.Lr:
        test r8d, r8d
        jz .Lr0
        mov r9, [rdx]
        cmp rcx, r9
        jb .Lrn
        add r9, [rdx+8]
        cmp rcx, r9
        jb .Lr1
.Lrn:
        add rdx, 16
        dec r8d
        jmp .Lr
.Lr0:
        xor eax, eax
        ret
.Lr1:
        mov rax, [rdx]
        mov rdx, r9
        ret

# Commit the reserved memory in [rcx, rcx+rdx) within one region: Windows
# does not commit it when the kernel reads or writes it, as Linux does.
        .globl commit_range
commit_range:
        push rbx
        push rsi
        push rdi
        sub rsp, 32
        test rdx, rdx
        jz .Lcr
        mov rsi, rdx
        mov rbx, rcx
        # While a copy of the program runs, what is written here is kept
        # for the parent first (windows-layer.c, copy_write).
        cmp dword ptr [rip+copy_running], 0
        je .Lcr_plain
        mov rdi, rbx
        mov [rsp], rsi
        call copy_write
        mov rsi, [rsp]
.Lcr_plain:
        mov rcx, rbx
        call region_of
        test rax, rax
        jz .Lcr
        # [max(rbx, rax), min(rbx+rsi, rdx)), in whole pages.
        lea r8, [rbx+rsi]
        cmp r8, rdx
        cmova r8, rdx
        mov rcx, rbx
        cmp rcx, rax
        cmovb rcx, rax
        and rcx, -4096
        add r8, 4095
        and r8, -4096
        mov rdx, r8
        sub rdx, rcx
        jbe .Lcr
        mov r8d, 0x1000         # MEM_COMMIT
        mov r9d, 4
        call [rip+imp_VirtualAlloc]
.Lcr:
        add rsp, 32
        pop rdi
        pop rsi
        pop rbx
        ret

# Wait for the time in the timespec at rcx, on a high-resolution waitable
# timer, rounded up to 100 ns.
        .globl wait_for
wait_for:
        push rbx
        push rsi
        sub rsp, 72
        mov rsi, rcx
        mov rax, [rip+sleep_timer]
        test rax, rax
        jnz .Lwait_timer
        xor ecx, ecx
        xor edx, edx
        mov r8d, 2              # CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
        mov r9d, 0x1F0003       # TIMER_ALL_ACCESS
        call [rip+imp_CreateWaitableTimerExW]
        test rax, rax
        jnz .Lwait_made
        xor ecx, ecx            # no high resolution here: a plain timer
        xor edx, edx
        xor r8d, r8d
        mov r9d, 0x1F0003
        call [rip+imp_CreateWaitableTimerExW]
.Lwait_made:
        mov [rip+sleep_timer], rax
.Lwait_timer:
        mov rcx, rsi
        mov rax, [rcx]
        imul rax, rax, 10000000
        mov rbx, rax
        mov rax, [rcx+8]
        add rax, 99
        xor edx, edx
        mov ecx, 100
        div rcx
        add rax, rbx
        neg rax                 # negative: relative
        mov [rsp+48], rax
        mov rcx, [rip+sleep_timer]
        lea rdx, [rsp+48]
        xor r8d, r8d
        xor r9d, r9d
        mov qword ptr [rsp+32], 0
        mov qword ptr [rsp+40], 0
        call [rip+imp_SetWaitableTimer]
        mov rcx, [rip+sleep_timer]
        mov edx, -1             # INFINITE
        call [rip+imp_WaitForSingleObject]
        add rsp, 72
        pop rsi
        pop rbx
        ret

# The Windows handle of Linux descriptor rcx, in rax; 0 for none.
# Descriptors 0 to 2 are the standard handles until a handle is set there.
        .globl handle_of
handle_of:
        cmp rcx, FDS
        jae .Lho_none
        lea rax, [rip+handles]
        mov rax, [rax+rcx*8]
        test rax, rax
        jnz .Lho_done
        cmp ecx, 3
        jae .Lho_done
        neg ecx
        sub ecx, 10
        jmp [rip+imp_GetStdHandle]
.Lho_none:
        xor eax, eax
.Lho_done:
        ret

# A new descriptor, the lowest free from 3, for the handle in rcx; or
# -EMFILE, the handle closed.
        .globl new_fd
new_fd:
        lea rdx, [rip+handles]
        mov eax, 3
.Lnf:
        cmp qword ptr [rdx+rax*8], 0
        je .Lnf_found
        inc eax
        cmp eax, FDS
        jb .Lnf
        sub rsp, 40
        call [rip+imp_CloseHandle]
        add rsp, 40
        mov rax, -24
        ret
.Lnf_found:
        mov [rdx+rax*8], rcx
        ret

# -errno for the last Windows error, which is kept (last_error).
        .globl fail
fail:
        sub rsp, 40
        call [rip+imp_GetLastError]
        mov [rip+last_error], eax
        lea rdx, [rip+errno_map]
.Lem:
        movzx ecx, word ptr [rdx]
        test ecx, ecx
        jz .Lem_default
        cmp eax, ecx
        je .Lem_found
        add rdx, 4
        jmp .Lem
.Lem_found:
        movzx eax, word ptr [rdx+2]
        neg rax
        jmp .Lem_out
.Lem_default:
        mov rax, -5             # EIO
.Lem_out:
        add rsp, 40
        ret

# The UTF-8 path at rcx in UTF-16 at rdx (32768 units); eax 0 if it does
# not convert. /dev/null is NUL.
        .globl wide
wide:
        sub rsp, 56
        mov r8, rcx
        mov r9, rdx
        lea r10, [rip+dev_null]
        xor eax, eax
.Lwd:
        mov r11b, [r10+rax]
        cmp r11b, [r8+rax]
        jne .Lwd_convert
        inc eax
        test r11b, r11b
        jnz .Lwd
        mov dword ptr [r9], 0x0055004E      # "NU"
        mov dword ptr [r9+4], 0x0000004C    # "L"
        mov eax, 4
        jmp .Lwd_out
.Lwd_convert:
        mov [rsp+32], r9
        mov dword ptr [rsp+40], 32768
        mov ecx, 65001
        xor edx, edx
        mov r9, -1
        call [rip+imp_MultiByteToWideChar]
.Lwd_out:
        add rsp, 56
        ret

# A Linux stat at rcx from Windows attributes and times at rdx (attributes,
# then creation, access and write times as FILETIMEs), the size in r8.
fill_stat:
        push rdi
        mov rdi, rcx
        mov r10, rcx
        xor eax, eax
        mov ecx, 18
        rep stosq
        mov qword ptr [r10+16], 1           # st_nlink
        mov eax, [rdx]
        test eax, 0x10                      # FILE_ATTRIBUTE_DIRECTORY
        jz .Lfs_file
        mov dword ptr [r10+24], 040777
        jmp .Lfs_mode
.Lfs_file:
        mov ecx, 0100666
        test eax, 1                         # FILE_ATTRIBUTE_READONLY
        jz .Lfs_rw
        mov ecx, 0100444
.Lfs_rw:
        mov [r10+24], ecx
.Lfs_mode:
        mov [r10+48], r8                    # st_size
        mov qword ptr [r10+56], 4096        # st_blksize
        lea rax, [r8+511]
        shr rax, 9
        mov [r10+64], rax                   # st_blocks
        mov r8, [rdx+12]                    # access
        lea r9, [r10+72]
        call .Lfs_time
        mov r8, [rdx+20]                    # write
        lea r9, [r10+88]
        call .Lfs_time
        lea r9, [r10+104]                   # change: the write time
        call .Lfs_time
        pop rdi
        ret
.Lfs_time:
        mov rax, r8
        mov rcx, 116444736000000000
        sub rax, rcx
        push rdx
        cqo
        mov ecx, 10000000
        idiv rcx
        test rdx, rdx
        jns .Lfs_pos
        dec rax
        add rdx, rcx
.Lfs_pos:
        mov [r9], rax
        imul rdx, rdx, 100
        mov [r9+8], rdx
        pop rdx
        ret

# Where a copy of the program that exited goes on, on the layer's stack, to
# put the parent back (windows-layer.c, copy_resume_c, which does not
# return).
        .globl copy_resume
copy_resume:
        call copy_resume_c
        ud2

# The system call in the CONTEXT at r12; its result in rax.
emulate:
        push rbx
        sub rsp, 128
        # The calls written in C (spec/windows-layer.c) first.
        mov rdi, r12
        call layer_call
        movabs rcx, 0x7FFFFFFFFFFFFFFF
        cmp rax, rcx
        jne .Lret
        mov rax, [r12+0x78]
        cmp rax, 0
        je .Lread
        cmp rax, 1
        je .Lwrite
        cmp rax, 9
        je .Lmmap
        cmp rax, 11
        je .Lmunmap
        cmp rax, 28
        je .Lmadvise
        cmp rax, 13
        je .Lsigaction
        cmp rax, 14
        je .Lzero               # rt_sigprocmask
        cmp rax, 131
        je .Lzero               # sigaltstack
        cmp rax, 60
        je .Lexit
        cmp rax, 228
        je .Lclock
        cmp rax, 35
        je .Lsleep
        cmp rax, 318
        je .Lrandom
        cmp rax, 39
        je .Lpid
        cmp rax, 271
        je .Lppoll
        cmp rax, 231
        je .Lexit
        cmp rax, 2
        je .Lopen
        cmp rax, 257
        je .Lopenat
        cmp rax, 3
        je .Lclose
        cmp rax, 8
        je .Llseek
        cmp rax, 5
        je .Lfstat
        cmp rax, 4
        je .Lstat
        cmp rax, 6
        je .Lstat               # lstat
        cmp rax, 262
        je .Lfstatat
        cmp rax, 79
        je .Lgetcwd
        cmp rax, 80
        je .Lchdir
        cmp rax, 83
        je .Lmkdir
        cmp rax, 258
        je .Lmkdirat
        cmp rax, 84
        je .Lrmdir
        cmp rax, 87
        je .Lunlink
        cmp rax, 263
        je .Lunlinkat
        cmp rax, 82
        je .Lrename
        cmp rax, 264
        je .Lrenameat
        cmp rax, 316
        je .Lrenameat
        # Any other: its number on standard error, and -ENOSYS.
        mov rbx, rax
        mov ecx, -12
        call [rip+imp_GetStdHandle]
        mov rcx, rax
        lea rdx, [rip+unknown]
        mov eax, ebx
        mov r9d, 7
        lea r11, [rip+hexdigits]
.Lhex:
        mov r10d, eax
        and r10d, 15
        movzx r10d, byte ptr [r11+r10]
        mov [rdx+r9+UNKNOWN_DIGITS], r10b
        shr eax, 4
        dec r9d
        jns .Lhex
        mov r8d, OFFSET UNKNOWN_LENGTH
        lea r9, [rsp+48]
        mov qword ptr [rsp+32], 0
        call [rip+imp_WriteFile]
        mov rax, -38
        jmp .Lret
.Lzero:
        xor eax, eax
        jmp .Lret
.Lsigaction:
        cmp qword ptr [r12+0xB0], 11
        jne .Lzero
        mov rax, [r12+0xA8]     # the new action, or NULL
        test rax, rax
        jz .Lzero
        mov rax, [rax]
        mov [rip+segv_handler], rax
        jmp .Lzero
.Lexit:
        mov rcx, [r12+0xB0]
        call [rip+imp_ExitProcess]
.Lread:
        mov rcx, [r12+0xA8]
        mov rdx, [r12+0x88]
        call commit_range
        mov rcx, [r12+0xB0]
        call handle_of
        test rax, rax
        jz .Lebadf
        mov rcx, rax
        mov rdx, [r12+0xA8]
        mov r8, [r12+0x88]
        lea r9, [rsp+48]
        mov qword ptr [rsp+48], 0
        mov qword ptr [rsp+32], 0
        call [rip+imp_ReadFile]
        test eax, eax
        jnz .Lread_done
        call [rip+imp_GetLastError]
        cmp eax, 109            # ERROR_BROKEN_PIPE: the end
        je .Lread_done
        cmp eax, 38             # ERROR_HANDLE_EOF
        je .Lread_done
        call fail
        jmp .Lret
.Lread_done:
        mov rax, [rsp+48]
        jmp .Lret
.Lebadf:
        mov rax, -9
        jmp .Lret
.Lwrite:
        mov rcx, [r12+0xA8]
        mov rdx, [r12+0x88]
        call commit_range
        mov rcx, [r12+0xB0]
        call handle_of
        test rax, rax
        jz .Lebadf
        mov rcx, rax
        mov rdx, [r12+0xA8]
        mov r8, [r12+0x88]
        lea r9, [rsp+48]
        mov qword ptr [rsp+48], 0
        mov qword ptr [rsp+32], 0
        call [rip+imp_WriteFile]
        test eax, eax
        jz .Lwrite_failed
        mov rax, [rsp+48]
        jmp .Lret
.Lwrite_failed:
        call [rip+imp_GetLastError]
        cmp eax, 232            # ERROR_NO_DATA: the reader has gone
        je .Lepipe
        call fail
        jmp .Lret
.Lepipe:
        mov rax, -32
        jmp .Lret
.Lmmap:
        # Up to 4 GiB is committed at once; more is reserved and committed
        # 64 KiB at a time as it is touched (MAP_NORESERVE).
        mov rdx, [r12+0xA8]
        mov rbx, rdx
        mov r8d, 0x3000         # MEM_COMMIT | MEM_RESERVE
        mov rax, 0x100000000
        cmp rdx, rax
        jbe .Lmc
        mov r8d, 0x2000         # MEM_RESERVE
.Lmc:
        xor ecx, ecx
        mov r9d, 4
        call [rip+imp_VirtualAlloc]
        test rax, rax
        jz .Lenomem
        mov ecx, [rip+region_count]
        cmp ecx, REGIONS
        jae .Lret
        shl ecx, 4
        lea rdx, [rip+regions]
        mov [rdx+rcx], rax
        mov [rdx+rcx+8], rbx
        inc dword ptr [rip+region_count]
        jmp .Lret
.Lclock:
        # clock_gettime(id, timespec): REALTIME from the system time, the
        # process and thread CPU clocks from their times, any other from the
        # performance counter.
        mov rcx, [r12+0xA8]
        mov edx, 16
        call commit_range
        mov rax, [r12+0xB0]
        cmp rax, 0              # CLOCK_REALTIME
        je .Lrealtime
        cmp rax, 5              # CLOCK_REALTIME_COARSE
        je .Lrealtime
        cmp rax, 2              # CLOCK_PROCESS_CPUTIME_ID
        je .Lcpu
        cmp rax, 3              # CLOCK_THREAD_CPUTIME_ID
        je .Lcpu
        lea rcx, [rsp+48]
        call [rip+imp_QueryPerformanceCounter]
        lea rcx, [rsp+56]
        call [rip+imp_QueryPerformanceFrequency]
        mov rax, [rsp+48]
        xor edx, edx
        div qword ptr [rsp+56]
        mov rcx, [r12+0xA8]
        mov [rcx], rax
        mov rax, rdx
        mov ecx, 1000000000
        mul rcx
        div qword ptr [rsp+56]
        mov rcx, [r12+0xA8]
        mov [rcx+8], rax
        xor eax, eax
        jmp .Lret
.Lrealtime:
        lea rcx, [rsp+48]
        call [rip+imp_GetSystemTimePreciseAsFileTime]
        mov rax, [rsp+48]
        mov rcx, 116444736000000000     # 1601 to 1970 in 100 ns
        sub rax, rcx
        jmp .Lticks
.Lcpu:
        # GetProcessTimes or GetThreadTimes(handle, &creation, &exit,
        # &kernel, &user): kernel + user.
        cmp qword ptr [r12+0xB0], 2
        je .Lcpu_process
        call [rip+imp_GetCurrentThread]
        lea rbx, [rip+imp_GetThreadTimes]
        jmp .Lcpu_times
.Lcpu_process:
        call [rip+imp_GetCurrentProcess]
        lea rbx, [rip+imp_GetProcessTimes]
.Lcpu_times:
        mov rcx, rax
        lea rdx, [rsp+48]
        lea r8, [rsp+56]
        lea r9, [rsp+64]
        lea rax, [rsp+72]
        mov [rsp+32], rax
        call [rbx]
        mov rax, [rsp+64]
        add rax, [rsp+72]
.Lticks:
        # rax 100 ns ticks into the timespec.
        xor edx, edx
        mov ecx, 10000000
        div rcx
        mov rcx, [r12+0xA8]
        mov [rcx], rax
        imul rdx, rdx, 100
        mov [rcx+8], rdx
        xor eax, eax
        jmp .Lret
.Lsleep:
        # nanosleep(request, remaining) on a high-resolution waitable timer,
        # rounded up to 100 ns; nothing remains.
        mov rcx, [r12+0xB0]
        mov edx, 16
        call commit_range
        mov rcx, [r12+0xA8]
        mov edx, 16
        call commit_range
        mov rcx, [r12+0xB0]
        call wait_for
        mov rcx, [r12+0xA8]
        test rcx, rcx
        jz .Lzero
        mov qword ptr [rcx], 0
        mov qword ptr [rcx+8], 0
        jmp .Lzero
.Lrandom:
        # getrandom(buffer, length, flags): ProcessPrng, as Go does.
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
        call commit_range
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
        call [rip+imp_ProcessPrng]
        mov rax, [r12+0xA8]
        jmp .Lret
.Lppoll:
        # ppoll(fds, count, timeout, mask): with no descriptors, a sleep.
        # Each descriptor is taken as ready for what it waits for: a read or
        # write then blocks, as the whole program does on one thread.
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
        shl rdx, 3
        call commit_range
        mov rcx, [r12+0xA8]
        test rcx, rcx
        jnz .Lppoll_fds
        mov rcx, [r12+0x88]
        test rcx, rcx
        jz .Lzero
        mov edx, 16
        call commit_range
        mov rcx, [r12+0x88]
        call wait_for
        jmp .Lzero
.Lppoll_fds:
        mov rdx, [r12+0xB0]
        xor eax, eax
.Lppoll_next:
        mov word ptr [rdx+6], 0
        cmp dword ptr [rdx], 0
        jl .Lppoll_skip
        movzx r8d, word ptr [rdx+4]
        and r8d, 5              # POLLIN | POLLOUT
        mov [rdx+6], r8w
        jz .Lppoll_skip
        inc eax
.Lppoll_skip:
        add rdx, 8
        dec rcx
        jnz .Lppoll_next
        jmp .Lret
.Lpid:
        call [rip+imp_GetCurrentProcessId]
        jmp .Lret
.Lopen:
        mov rcx, [r12+0xB0]     # path, flags, mode
        mov rax, [r12+0xA8]
        mov [rsp+64], rax
        mov rax, [r12+0x88]
        mov [rsp+72], rax
        jmp .Lopen_path
.Lopenat:
        # The directory is taken to be the working directory (AT_FDCWD).
        mov rcx, [r12+0xA8]
        mov rax, [r12+0x88]
        mov [rsp+64], rax
        mov rax, [r12+0xC8]
        mov [rsp+72], rax
.Lopen_path:
        lea rdx, [rip+wpath1]
        call wide
        test eax, eax
        jz .Lfailed
        # Access: O_RDONLY, O_WRONLY, O_RDWR; O_APPEND writes at the end.
        mov rax, [rsp+64]
        mov edx, 0x80000000     # GENERIC_READ
        and eax, 3
        jz .Lop_access
        mov edx, 0x40000000     # GENERIC_WRITE
        cmp eax, 1
        je .Lop_access
        mov edx, 0xC0000000
.Lop_access:
        test qword ptr [rsp+64], 0x400      # O_APPEND
        jz .Lop_append
        and edx, 0x80000000
        or edx, 0x00100004      # FILE_APPEND_DATA | SYNCHRONIZE
.Lop_append:
        # Creation: O_CREAT, O_EXCL, O_TRUNC.
        mov rax, [rsp+64]
        mov r8d, 3              # OPEN_EXISTING
        test eax, 0x40          # O_CREAT
        jz .Lop_nocreat
        mov r8d, 4              # OPEN_ALWAYS
        test eax, 0x80          # O_EXCL
        jz .Lop_trunc_c
        mov r8d, 1              # CREATE_NEW
        jmp .Lop_created
.Lop_trunc_c:
        test eax, 0x200         # O_TRUNC
        jz .Lop_created
        mov r8d, 2              # CREATE_ALWAYS
        jmp .Lop_created
.Lop_nocreat:
        test eax, 0x200
        jz .Lop_created
        mov r8d, 5              # TRUNCATE_EXISTING
.Lop_created:
        mov [rsp+32], r8
        # Directories open only with FILE_FLAG_BACKUP_SEMANTICS; a file
        # made without write permission is read-only.
        mov eax, 0x02000080     # FILE_FLAG_BACKUP_SEMANTICS | NORMAL
        test qword ptr [rsp+72], 0200
        jnz .Lop_mode
        test qword ptr [rsp+64], 0x40
        jz .Lop_mode
        or eax, 1               # FILE_ATTRIBUTE_READONLY
.Lop_mode:
        mov [rsp+40], rax
        mov qword ptr [rsp+48], 0
        lea rcx, [rip+wpath1]
        mov r8d, 3              # FILE_SHARE_READ | WRITE, as Go's syscall.Open
        xor r9d, r9d
        call [rip+imp_CreateFileW]
        cmp rax, -1
        je .Lfailed
        mov rcx, rax
        call new_fd
        jmp .Lret
.Lfailed:
        call fail
        jmp .Lret
.Lclose:
        mov rcx, [r12+0xB0]
        cmp rcx, 3
        jb .Lzero
        call handle_of
        test rax, rax
        jz .Lebadf
        mov rcx, rax
        mov rdx, [r12+0xB0]
        lea rax, [rip+handles]
        mov qword ptr [rax+rdx*8], 0
        call [rip+imp_CloseHandle]
        jmp .Lzero
.Llseek:
        mov rcx, [r12+0xB0]
        call handle_of
        test rax, rax
        jz .Lebadf
        mov rcx, rax
        mov rdx, [r12+0xA8]
        lea r8, [rsp+64]
        mov r9, [r12+0x88]      # SEEK_SET, CUR, END are FILE_BEGIN, CURRENT, END
        call [rip+imp_SetFilePointerEx]
        test eax, eax
        jz .Lfailed
        mov rax, [rsp+64]
        jmp .Lret
.Lfstat:
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
.Lfstat_fd:
        # rcx the descriptor, rdx the stat.
        mov [rsp+120], rdx
        mov rcx, rdx
        mov edx, 144
        call commit_range
        mov rcx, [r12+0xB0]
        call handle_of
        test rax, rax
        jz .Lebadf
        mov rbx, rax
        mov rcx, rax
        call [rip+imp_GetFileType]
        cmp eax, 1              # FILE_TYPE_DISK
        jne .Lfstat_other
        mov rcx, rbx
        lea rdx, [rsp+64]
        call [rip+imp_GetFileInformationByHandle]
        test eax, eax
        jz .Lfailed
        mov r8d, [rsp+64+36]    # nFileSizeLow
        mov eax, [rsp+64+32]    # nFileSizeHigh
        shl rax, 32
        or r8, rax
        mov rcx, [rsp+120]
        lea rdx, [rsp+64]
        call fill_stat
        jmp .Lzero
.Lfstat_other:
        # A console is a character device, a pipe a FIFO.
        mov ebx, 020666
        cmp eax, 2              # FILE_TYPE_CHAR
        je .Lfstat_kind
        mov ebx, 010600
.Lfstat_kind:
        mov dword ptr [rsp+64], 0
        mov qword ptr [rsp+64+12], 0
        mov qword ptr [rsp+64+20], 0
        mov rcx, [rsp+120]
        lea rdx, [rsp+64]
        xor r8d, r8d
        call fill_stat
        mov rcx, [rsp+120]
        mov [rcx+24], ebx
        jmp .Lzero
.Lstat:
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
        jmp .Lstat_path
.Lfstatat:
        mov rcx, [r12+0xA8]
        mov rdx, [r12+0x88]
        test qword ptr [r12+0xC8], 0x1000   # AT_EMPTY_PATH
        jz .Lstat_path
        cmp byte ptr [rcx], 0
        jne .Lstat_path
        mov rcx, [r12+0xB0]
        jmp .Lfstat_fd
.Lstat_path:
        # rcx the path, rdx the stat.
        mov [rsp+120], rdx
        lea rdx, [rip+wpath1]
        call wide
        test eax, eax
        jz .Lfailed
        mov rcx, [rsp+120]
        mov edx, 144
        call commit_range
        lea rcx, [rip+wpath1]
        xor edx, edx            # GetFileExInfoStandard
        lea r8, [rsp+64]
        call [rip+imp_GetFileAttributesExW]
        test eax, eax
        jz .Lfailed
        mov r8d, [rsp+64+32]    # nFileSizeLow
        mov eax, [rsp+64+28]    # nFileSizeHigh
        shl rax, 32
        or r8, rax
        mov rcx, [rsp+120]
        lea rdx, [rsp+64]
        call fill_stat
        jmp .Lzero
.Lgetcwd:
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
        call commit_range
        mov ecx, 32768
        lea rdx, [rip+wpath1]
        call [rip+imp_GetCurrentDirectoryW]
        test eax, eax
        jz .Lfailed
        mov ecx, 65001
        xor edx, edx
        lea r8, [rip+wpath1]
        mov r9d, eax
        mov rax, [r12+0xB0]
        mov [rsp+32], rax
        mov rax, [r12+0xA8]
        dec rax
        mov [rsp+40], rax
        mov qword ptr [rsp+48], 0
        mov qword ptr [rsp+56], 0
        call [rip+imp_WideCharToMultiByte]
        test eax, eax
        jz .Lerange
        mov rcx, [r12+0xB0]
        mov byte ptr [rcx+rax], 0
        inc rax
        jmp .Lret
.Lerange:
        mov rax, -34
        jmp .Lret
.Lchdir:
        lea rbx, [rip+imp_SetCurrentDirectoryW]
        mov rcx, [r12+0xB0]
        jmp .Lpath_call
.Lmkdir:
        lea rbx, [rip+imp_CreateDirectoryW]
        mov rcx, [r12+0xB0]
        jmp .Lpath_call
.Lmkdirat:
        lea rbx, [rip+imp_CreateDirectoryW]
        mov rcx, [r12+0xA8]
        jmp .Lpath_call
.Lrmdir:
        lea rbx, [rip+imp_RemoveDirectoryW]
        mov rcx, [r12+0xB0]
        jmp .Lpath_call
.Lunlink:
        lea rbx, [rip+imp_DeleteFileW]
        mov rcx, [r12+0xB0]
        jmp .Lpath_call
.Lunlinkat:
        lea rbx, [rip+imp_DeleteFileW]
        test qword ptr [r12+0x88], 0x200    # AT_REMOVEDIR
        jz .Lunlinkat_file
        lea rbx, [rip+imp_RemoveDirectoryW]
.Lunlinkat_file:
        mov rcx, [r12+0xA8]
.Lpath_call:
        # The call at [rbx] with the path at rcx, and NULL.
        lea rdx, [rip+wpath1]
        call wide
        test eax, eax
        jz .Lfailed
        lea rcx, [rip+wpath1]
        xor edx, edx
        call [rbx]
        test eax, eax
        jz .Lfailed
        jmp .Lzero
.Lrename:
        mov rcx, [r12+0xB0]
        mov rax, [r12+0xA8]
        jmp .Lrename_paths
.Lrenameat:
        mov rcx, [r12+0xA8]
        mov rax, [r12+0xC8]
.Lrename_paths:
        mov [rsp+64], rax
        lea rdx, [rip+wpath1]
        call wide
        test eax, eax
        jz .Lfailed
        mov rcx, [rsp+64]
        lea rdx, [rip+wpath2]
        call wide
        test eax, eax
        jz .Lfailed
        lea rcx, [rip+wpath1]
        lea rdx, [rip+wpath2]
        mov r8d, 1              # MOVEFILE_REPLACE_EXISTING
        call [rip+imp_MoveFileExW]
        test eax, eax
        jz .Lfailed
        jmp .Lzero
.Lenomem:
        mov rax, -12
        jmp .Lret
.Lmadvise:
        # madvise(address, length, advice): MADV_DONTNEED (4) and MADV_FREE
        # (8) decommit the whole pages, which the handler commits again,
        # zeroed, when they are touched; any other advice is taken.
        mov rax, [r12+0x88]
        cmp rax, 4
        je .Lmadvise_free
        cmp rax, 8
        jne .Lzero
.Lmadvise_free:
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
        add rdx, rcx
        add rcx, 4095
        and rcx, -4096
        and rdx, -4096
        sub rdx, rcx
        jbe .Lzero
        mov r8d, 0x4000         # MEM_DECOMMIT
        call [rip+imp_VirtualFree]
        jmp .Lzero
.Lmunmap:
        mov rcx, [r12+0xB0]
        mov rdx, [r12+0xA8]
        mov r8d, 0x4000         # MEM_DECOMMIT
        call [rip+imp_VirtualFree]
        xor eax, eax
.Lret:
        # Arguments the C part changed for the assembly are the program's again.
        mov rbx, rax
        mov rdi, r12
        mov rsi, rax
        call layer_restore
        mov rax, rbx
        add rsp, 128
        pop rbx
        ret

hexdigits: .ascii "0123456789abcdef"
dev_null: .asciz "/dev/null"
# Windows errors and the Linux errno each stands for; any other is EIO.
        .balign 2
errno_map:
        .short 2, 2             # ERROR_FILE_NOT_FOUND: ENOENT
        .short 3, 2             # ERROR_PATH_NOT_FOUND
        .short 5, 13            # ERROR_ACCESS_DENIED: EACCES
        .short 6, 9             # ERROR_INVALID_HANDLE: EBADF
        .short 8, 12            # ERROR_NOT_ENOUGH_MEMORY: ENOMEM
        .short 14, 12           # ERROR_OUTOFMEMORY
        .short 15, 2            # ERROR_INVALID_DRIVE
        .short 19, 30           # ERROR_WRITE_PROTECT: EROFS
        .short 32, 16           # ERROR_SHARING_VIOLATION: EBUSY
        .short 33, 16           # ERROR_LOCK_VIOLATION
        .short 80, 17           # ERROR_FILE_EXISTS: EEXIST
        .short 87, 22           # ERROR_INVALID_PARAMETER: EINVAL
        .short 109, 32          # ERROR_BROKEN_PIPE: EPIPE
        .short 112, 28          # ERROR_DISK_FULL: ENOSPC
        .short 123, 2           # ERROR_INVALID_NAME
        .short 145, 39          # ERROR_DIR_NOT_EMPTY: ENOTEMPTY
        .short 161, 2           # ERROR_BAD_PATHNAME
        .short 183, 17          # ERROR_ALREADY_EXISTS
        .short 206, 36          # ERROR_FILENAME_EXCED_RANGE: ENAMETOOLONG
        .short 267, 20          # ERROR_DIRECTORY: ENOTDIR
        .short 0


        .data
# The message for a system call the layer does not make; its digits are
# filled in.
unknown: .ascii "E_RUNTIME_WINDOWS: unsupported system call 0x"
        .set UNKNOWN_DIGITS, . - unknown
        .ascii "00000000\n"
        .set UNKNOWN_LENGTH, . - unknown
win_rsp: .quad 0
segv_handler: .quad 0
sleep_timer: .quad 0
        .globl region_count
region_count: .long 0
        .globl last_error
last_error: .long 0
busy:   .byte 0
        .balign 8
thread_teb: .quad 0, 0, 0       # StackBase, StackLimit, DeallocationStack
program_teb: .quad 0, 0, 0

# The rest starts as zeros, which the file does not hold.
        .bss
        .balign 16
siginfo: .space 128
ucontext: .space 1024
        .globl regions
regions: .space REGIONS*16
        .globl handles
handles: .space FDS*8
        .balign 2
        .globl wpath1
wpath1: .space 65536
        .globl wpath2
wpath2: .space 65536

        .section .note.GNU-stack, "", @progbits
