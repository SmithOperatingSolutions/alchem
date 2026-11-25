"""The source of the pinned Go compiler, in the module cache: the version
adapters/alchem/go.mod names, whatever other versions the cache holds."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def version():
    return re.search(r'SmithOperatingSolutions/alchem (\S+)', (ROOT / 'adapters/alchem/go.mod').read_text()).group(1)


def tree():
    return ROOT / '.cache/gomod/github.com/!smith!operating!solutions' / f'alchem@{version()}'
