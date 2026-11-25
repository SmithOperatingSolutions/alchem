"""The source of the pinned Go compiler, in the module cache: the version
adapters/alchem/go.mod names, whatever other versions the cache holds."""
from pathlib import Path
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def version():
    return re.search(r'SmithOperatingSolutions/alchem (\S+)', (ROOT / 'adapters/alchem/go.mod').read_text()).group(1)


def tree():
    return ROOT / '.cache/gomod/github.com/!smith!operating!solutions' / f'alchem@{version()}'


def command(out):
    """The pinned command line, built at out from its module: again when
    what stands there was built from another version (out.version says which),
    so a build kept from before the reference moved is never compared with."""
    out = Path(out)
    stamp = out.with_name(out.name + '.version')
    if not out.exists() or not stamp.exists() or stamp.read_text() != version():
        out.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off', GOTOOLCHAIN='local', GOMODCACHE=str(ROOT / '.cache/gomod'))
        subprocess.run(['go', 'build', '-o', str(out), './cmd/alchem'], cwd=tree(), env=env, check=True)
        stamp.write_text(version())
    return out
