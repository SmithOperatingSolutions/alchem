"""Where a runtime assembled from spec/*-x86_64.s makes a system call, for
the Windows compiler (spec/windows.md).

Each runtime is assembled a second time with `syscall` defined as a macro
for `ud2`, which has the same length. The two outputs differ only where a
system call stands, and those offsets go into the generated literal as
nc_os(code, sites): the code as it is for Linux, and with each `syscall`
turned into `ud2` in the Windows compiler.
"""
from pathlib import Path
import subprocess
import tempfile

MACRO = '.macro syscall\n ud2\n.endm\n'


def sites(linux, windows):
    """The offsets of the system calls: where linux has 0F 05 and windows 0F 0B."""
    if len(linux) != len(windows):
        raise ValueError('the Windows assembly differs in length')
    found = []
    for i, (a, b) in enumerate(zip(linux, windows)):
        if a == b:
            continue
        if not (a == 0x05 and b == 0x0B and i > 0 and linux[i - 1] == 0x0F):
            raise ValueError(f'the Windows assembly differs at {i} other than at a system call')
        found.append(i - 1)
    return found


def assemble(command):
    """Run an `as` command list (ending in its sources) for Windows: the
    macro first, the output object with '.win' added to its name."""
    out = command.index('-o') + 1
    with tempfile.TemporaryDirectory(prefix='alchem-windows-sites-') as d:
        macro = Path(d) / 'windows.s'
        macro.write_text(MACRO)
        windows = list(command)
        windows[out] = str(command[out]) + '.win'
        sources = [i for i, part in enumerate(windows) if str(part).endswith('.s')]
        windows.insert(sources[0], str(macro))
        subprocess.run(windows, check=True)
    return Path(windows[out])


def literal(found):
    """The sites as an Alchem byte literal, four bytes each."""
    return 'b[' + ','.join(str(x) for site in found for x in site.to_bytes(4, 'little')) + ']'


def wrap(expression, found):
    """expression, which gives the code, with its system calls for Windows."""
    return f'nc_os({expression},{literal(found)})' if found else expression
