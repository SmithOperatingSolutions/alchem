# Reference used only to generate checked Alchem byte literals, never at build/runtime.
# File.read(path): result[string,string] and File.write/append(path,content),
# File.remove(path): result[tuple[],string] subroutine, emitted once per program
# as an extra function-table entry. RDI path string record, ESI 0 read, 1 write,
# 2 append, 3 remove or 4 the text of the error number in RDI, RDX content record when writing; RAX returns ok(text),
# ok({}) or error(reason). Reasons match the pinned runtime's os.PathError text,
# "open|read|write|close|remove PATH: ERRNO TEXT", or "file is not valid UTF-8".
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
# UTF8_WIDTH
# Frame: [rsp] path, [rsp+8] fd, [rsp+16] stage (0 open, 1 read, 2 UTF-8,
# 3 write, 4 close, 5 remove), [rsp+24] errno (-1 unexpected EOF) or probe byte,
# [rsp+32] data end, content record or unlink errno, [rsp+40..63] digits.
# [rsp+8] holds the requested mode until a descriptor replaces it.
# [rsp+64..4167] is the path with the zero byte that ends it for the kernel
# (its first 4096 bytes: a longer one is ENAMETOOLONG there either way), so
# that nothing is written into the arena but what becomes a value.
 sub rsp,4168
# ESI 4: RDI is an error number; RAX returns its text alone (stage 9), for
# the library functions written in Alchem (Sys.errno).
 cmp esi,4
 jne fr_begin
 mov qword ptr [rsp+16],9
 mov [rsp+24],rdi
 gm_reserve r12+4096
 lea r11,[r12+8]
 cmp r11,r13
 ja fr_arena
 jmp fr_reason
fr_begin:
 mov [rsp],rdi
 mov [rsp+32],rdx
 mov [rsp+8],rsi
 mov qword ptr [rsp+16],0
 mov rcx,[rdi]
 lea rsi,[rdi+8]
# Room for the path (it is part of a failure's text) and 8192 bytes.
 gm_reserve r12+rcx+8192
 xor edx,edx
fr_copy:
 cmp rdx,rcx
 jae fr_copied
 movzx eax,byte ptr [rsi+rdx]
 test eax,eax
 jz fr_einval
 cmp rdx,4096
 jae fr_long
 mov [rsp+64+rdx],al
fr_long:
 inc rdx
 jmp fr_copy
fr_einval:
 mov qword ptr [rsp+24],22
 cmp qword ptr [rsp+8],3
 jne fr_error
 mov qword ptr [rsp+16],5
 jmp fr_error
fr_copied:
 cmp rdx,4096
 jbe fr_ended
 mov edx,4096
fr_ended:
 mov byte ptr [rsp+64+rdx],0
 cmp qword ptr [rsp+8],0
 jne fw_open
fr_open:
 lea rdi,[rsp+64]
 mov esi,524288
 xor edx,edx
 mov eax,2
 syscall
 cmp rax,-4
 je fr_open
 test rax,rax
 js fr_errno
 mov [rsp+8],rax
 mov qword ptr [rsp+16],1
 lea rsi,[r12+8]
# The room is filled up to 64 bytes before its end (the result's record
# and a failure's text come behind the bytes read), then made larger.
fr_read:
 mov rdx,r13
 sub rdx,rsi
 sub rdx,64
 ja fr_fill
 gm_grow r13+1
 add rsi,r11
 jmp fr_read
fr_fill:
 mov rdi,[rsp+8]
 xor eax,eax
 syscall
 cmp rax,-4
 je fr_read
 test rax,rax
 js fr_read_errno
 jz fr_eof
 add rsi,rax
 jmp fr_read
fr_eof:
 mov [rsp+32],rsi
 call fr_close
 lea rsi,[r12+8]
 mov rdx,[rsp+32]
fr_valid:
 cmp rsi,rdx
 jae fr_ok
 utf8_width fr_not_utf8
 add rsi,rcx
 jmp fr_valid
fr_not_utf8:
 mov qword ptr [rsp+16],2
 jmp fr_error
fr_ok:
 mov rax,r12
 mov rdx,[rsp+32]
 lea r10,[rdx+7]
 and r10,-8
 sub rdx,rax
 sub rdx,8
 mov [rax],rdx
 mov edx,1
 jmp fr_result
fr_read_errno:
 neg rax
 mov [rsp+24],rax
 cmp qword ptr [rsp+16],1
 jne fr_closing
 mov [rsp+32],rsi
fr_closing:
 call fr_close
 jmp fr_error
# os.WriteFile(path,content,0644): O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, write all,
# close. Append opens O_WRONLY|O_CREAT|O_APPEND|O_CLOEXEC instead.
fw_open:
 cmp qword ptr [rsp+8],3
 je fx_remove
 mov esi,524865
 cmp qword ptr [rsp+8],1
 je fw_flags
 mov esi,525377
fw_flags:
 lea rdi,[rsp+64]
 mov edx,420
 mov eax,2
 syscall
 cmp rax,-4
 je fw_open
 test rax,rax
 js fr_errno
 mov [rsp+8],rax
 mov qword ptr [rsp+16],3
 mov rsi,[rsp+32]
 mov rdx,[rsi]
 add rsi,8
fw_write:
 test rdx,rdx
 jz fw_close
 mov rdi,[rsp+8]
 mov eax,1
 syscall
 cmp rax,-4
 je fw_write
 test rax,rax
 js fr_read_errno
 jz fw_stalled
 add rsi,rax
 sub rdx,rax
 jmp fw_write
fw_stalled:
 mov qword ptr [rsp+24],-1
 call fr_close
 jmp fr_error
fw_close:
 mov qword ptr [rsp+16],4
 call fr_close
 test rax,rax
 js fr_errno
# ok({}): an empty tuple record, then the result record.
fw_ok:
 lea r10,[r12+8]
 cmp r10,r13
 ja fr_arena
 mov qword ptr [r12],0
 mov rax,r12
 mov edx,1
 jmp fr_result
# os.Remove: unlink, then rmdir; report rmdir's error unless it is ENOTDIR.
fx_remove:
 mov qword ptr [rsp+16],5
fx_unlink:
 lea rdi,[rsp+64]
 mov eax,87
 syscall
 cmp rax,-4
 je fx_unlink
 test rax,rax
 jz fw_ok
 neg rax
 mov [rsp+32],rax
fx_rmdir:
 lea rdi,[rsp+64]
 mov eax,84
 syscall
 cmp rax,-4
 je fx_rmdir
 test rax,rax
 jz fw_ok
 neg rax
 cmp rax,20
 jne fx_report
 mov rax,[rsp+32]
fx_report:
 mov [rsp+24],rax
 jmp fr_error
fr_errno:
 neg rax
 mov [rsp+24],rax
# What was read of a file that then failed is no value: it is zeroed, as
# free memory is (alchem-memory.md).
fr_error:
 mov rax,[rsp+16]
 dec rax
 cmp rax,1
 ja fr_text
 lea rdi,[r12+8]
 mov rcx,[rsp+32]
 sub rcx,rdi
 jbe fr_text
 xor eax,eax
 cld
 rep stosb
fr_text:
 lea r11,[r12+8]
 mov rax,[rsp+16]
 cmp rax,2
 je fr_message_utf8
 lea rsi,[rip+fr_open_text]
 mov ecx,5
 test rax,rax
 jz fr_prefix
 lea rsi,[rip+fr_read_text]
 cmp rax,1
 je fr_prefix
 lea rsi,[rip+fr_write_text]
 mov ecx,6
 cmp rax,3
 je fr_prefix
 lea rsi,[rip+fr_close_text]
 cmp rax,4
 je fr_prefix
 lea rsi,[rip+fr_remove_text]
 mov ecx,7
fr_prefix:
 call fr_append
 mov rsi,[rsp]
 mov rcx,[rsi]
 add rsi,8
 call fr_append
 lea rsi,[rip+fr_colon_text]
 mov ecx,2
 call fr_append
fr_reason:
 mov rax,[rsp+24]
 cmp rax,-1
 je fr_message_eof
.ifdef WINDOWS
# Windows' text for the error the layer gave this errno for, as Go's
# syscall.Errno.Error gives it (pseudo call 1000101, spec/windows.md); the
# text below when the errno was the layer's own.
 push r11
 mov rdi,rax
 mov eax,1000101
 syscall
 pop r11
 test rax,rax
 jle fr_reason_table
 mov rsi,rax
 xor ecx,ecx
fr_reason_length:
 cmp byte ptr [rsi+rcx],0
 je fr_reason_windows
 inc rcx
 jmp fr_reason_length
fr_reason_windows:
 call fr_append
 jmp fr_message_done
fr_reason_table:
 mov rax,[rsp+24]
.endif
 cmp rax,ERRNO_COUNT
 jae fr_errno_number
 lea rsi,[rip+fr_errnos]
fr_errno_skip:
 test rax,rax
 jz fr_errno_found
 movzx ecx,byte ptr [rsi]
 lea rsi,[rsi+rcx+1]
 dec rax
 jmp fr_errno_skip
fr_errno_found:
 movzx ecx,byte ptr [rsi]
 inc rsi
 call fr_append
 jmp fr_message_done
fr_errno_number:
 lea rsi,[rip+fr_errno_text]
 mov ecx,6
 call fr_append
 mov rax,[rsp+24]
 lea rsi,[rsp+64]
 mov r8d,10
fr_digit:
 xor edx,edx
 div r8
 add dl,48
 dec rsi
 mov [rsi],dl
 test rax,rax
 jnz fr_digit
 lea rcx,[rsp+64]
 sub rcx,rsi
 call fr_append
 jmp fr_message_done
fr_message_eof:
 lea rsi,[rip+fr_eof_text]
 mov ecx,14
 call fr_append
 jmp fr_message_done
fr_message_utf8:
 lea rsi,[rip+fr_utf8_text]
 mov ecx,23
 call fr_append
fr_message_done:
 mov rax,r12
 lea r10,[r11+7]
 and r10,-8
 mov rdx,r11
 sub rdx,rax
 sub rdx,8
 mov [rax],rdx
 cmp qword ptr [rsp+16],9
 jne fr_failed
 cmp r10,r13
 ja fr_arena
 mov r12,r10
 gm_release
 add rsp,4168
 ret
fr_failed:
 xor edx,edx
# RAX string record, R10 aligned end, RDX discriminant (1 ok, 0 error).
fr_result:
 lea r11,[r10+16]
 cmp r11,r13
 ja fr_arena
 mov [r10],rdx
 mov [r10+8],rax
 mov rax,r10
 mov r12,r11
 gm_release
 add rsp,4168
 ret
# Append RSI/RCX at R11 within the arena.
fr_append:
 lea rax,[r11+rcx]
 cmp rax,r13
 ja fr_arena
 mov rdi,r11
 cld
 rep movsb
 mov r11,rdi
 ret
# close(fd); like the pinned runtime's deferred Close, its result is ignored.
fr_close:
 mov rdi,[rsp+16]
 mov eax,3
 syscall
 ret
fr_arena:
 mov edi,71
 mov eax,60
 syscall
fr_open_text:
 .ascii "open "
fr_read_text:
 .ascii "read "
fr_write_text:
 .ascii "write "
fr_close_text:
 .ascii "close "
fr_remove_text:
 .ascii "remove "
fr_eof_text:
 .ascii "unexpected EOF"
fr_colon_text:
 .ascii ": "
fr_errno_text:
 .ascii "errno "
fr_utf8_text:
 .ascii "file is not valid UTF-8"
fr_errnos:
# ERRNO_DATA
