# Reference used only to check the byte literals of
# implementations/alchem/native-processes.alc, never at build or run time
# (scripts/generate-process-runtime.py assembles each part and looks for its
# bytes there). Processes are coroutines of the one thread a native program
# has; everything else about them is written in Alchem (library/Process.alc
# and the modules built on it, spec/alchem-processes.md). A part starts at a
# line "# == name".
#
# R14 is the initial stack pointer. The word at R14-8 is the stack limit of
# the running process and the word at R14-16 its innermost handler of a try
# (spec/alchem-try.md); R15 counts its active calls and RBP is its frame.
# R12 and R13, the arena, belong to the program and are never switched.
.intel_syntax noprefix
.text
# == switch
# Process.__switch(a, b): the arguments are on the stack, b on top. The
# running process leaves its stack pointer, frame, call count, handler and
# stack limit in the five words at a and goes on as the process that left
# its own at b. A process is gone on with at the label, with 0 in RAX.
# The stack pointer it leaves is also kept where the collector finds it
# (alchem-memory.md): in the word below the top of its stack (the word at
# a+256 is that top, Process._start), or, for the main process, whose
# record has no stack of its own there, in the collector's word at R14-504.
 pop rsi
 pop rdi
 lea rax,[rip+1f]
 push rax
 mov [rdi],rsp
 mov [rdi+8],rbp
 mov [rdi+16],r15
 mov rax,[r14-16]
 mov [rdi+24],rax
 mov rax,[r14-8]
 mov [rdi+32],rax
 mov rax,[rdi+256]
 test rax,rax
 jz 2f
 mov [rax-8],rsp
 jmp 3f
2:
 mov [r14-504],rsp
3:
 mov rsp,[rsi]
 mov rbp,[rsi+8]
 mov r15,[rsi+16]
 mov rax,[rsi+24]
 mov [r14-16],rax
 mov rax,[rsi+32]
 mov [r14-8],rax
 ret
1:
 xor eax,eax
# == stub
# Process.__stub(): the address a new stack "returns" to. The stack of a
# new process holds, from its top down, two words of its own (the next free
# stack and its size), the function value to run and this address; the
# function is called with nothing and never returns.
 jmp 2f
1:
 pop r10
 call [r10]
 ud2
2:
 lea rax,[rip+1b]
# == until
# Process.__until(f, word): f(word) again and again until it is not 0.
1:
 mov r10,[rsp+8]
 mov rdi,[rsp]
 call [r10]
 test rax,rax
 jz 1b
 add rsp,16
# == depth
# Process.__depth(count): the count of active calls.
 pop r15
 xor eax,eax
# == statement
# Before a statement of main in a program with processes: Process._stopped
# is called (nine bytes follow) when the main process was asked to stop.
 cmp qword ptr [r14-56],0
 je .+11
# == untyped
# Before a call that takes a type from the program's annotations and finds
# none settled: no type.
 mov qword ptr [r14-48],0
# == typed
# The same with a type: the string of its bytes stands in the code behind a
# jump, "lea rax,[rip-(its size+7)]" takes its address, and then:
 mov [r14-48],rax
# == entry
# The entry of a program with processes, after the arena and the stack are
# made: main runs under a handler whose frame is 160 bytes of the stack.
# The calls of main and of Process._close stand where the nops are, nine
# bytes each, and the exit of every program follows the first part.
 sub rsp,160
 lea rax,[rsp+160]
 push r15
 push rax
 lea rax,[rip+76]
 push rax
 push qword ptr [r14-16]
 mov [r14-16],rsp
# == returned
# main returned: the handler goes, Process._close(0) runs, and the status
# is main's unless that is 0.
 pop qword ptr [r14-16]
 add rsp,24
 push rax
 xor edi,edi
# == status
 pop rcx
 test rax,rax
 cmovz rax,rcx
# == failed
# main failed: the failure record is at RSP. Process._close(1) runs.
 mov rax,rsp
 push rax
 mov edi,1
# == passed
# The failure then passes on as from an after block (reason 12).
 pop rdx
 mov esi,12
