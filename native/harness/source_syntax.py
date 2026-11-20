"""Explicit migration of pre-collection byte-profile fixtures; never runtime code."""
import re

_TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|\#[^\r\n]*|list\s*\[\s*integer\s*\]|[A-Za-z_][A-Za-z_0-9]*|\[|.',re.S)
_TYPE_WORDS={'list','option','tuple','result','map','fn'}


def native_bytes(source):
    """Rename legacy byte types/literals without changing strings or comments."""
    binary=isinstance(source,bytes)
    text=source.decode() if binary else source
    out=[];previous=''
    for m in _TOKEN.finditer(text):
        token=m[0]
        if token.startswith('"') or token.startswith('#'):
            out.append(token)
        elif re.fullmatch(r'list\s*\[\s*integer\s*\]',token):
            out.append('bytes');previous='bytes'
        elif token=='[':
            out.append('[' if previous in _TYPE_WORDS or previous=='b' else 'b[')
            previous='['
        else:
            out.append(token)
            if not token.isspace():previous=token
    result=''.join(out)
    return result.encode() if binary else result


if __name__=='__main__':
    cases=[('x: list[integer]', 'x: bytes'),('some([1,2])','some(b[1,2])'),('x: option[list[integer]]','x: option[bytes]'),('x=b[1]','x=b[1]'),('x: tuple[integer,string]','x: tuple[integer,string]'),('s="list[integer] [1]" # [2]\nx=[]','s="list[integer] [1]" # [2]\nx=b[]')]
    for before,after in cases:
        assert native_bytes(before)==after,(before,native_bytes(before))
        assert native_bytes(after)==after
    print('PASS byte fixture syntax migration')
