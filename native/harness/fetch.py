#!/usr/bin/env python3
"""Packages fetched without Go (tools/alchem-fetch.alc, spec/alchem-modules.md):
alchem built by the compiler under test fetches a package from module
proxies served here (over HTTP and from files), checks it against a checksum
database served here (a tree of records signed with Ed25519, proved by its
tiles), keeps it in its own cache and builds with it. Offline: every server
is on this machine.

Checked: the archive's h1 hash as Go computes it; the lock; the cache read
again without the network; two builds that fetch at once; doc of a
package's file; GOPROXY lists, off and fall-through; a record the database
does not hold, a signature by another key, a tile that is not the tree's
and a hash that differs (nothing kept); the latest tree kept, and trees grown
from it, older than it and forked from it, larger and of its size; GONOSUMDB; private packages, fetched
with git from repositories made here (a module at the root, in a directory and
in a major version's directory, with the files go mod download leaves out),
with the hashes go mod download gave for them, the pattern set in the
environment or by go env -w, and nothing asked of any server; GOPROXY=direct;
archives with a file outside the module, a damaged file and two names that
differ only in case; the cache directory when ALCHEM_CACHE is not set."""
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from importlib.util import module_from_spec, spec_from_file_location
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[1]

# ---- Ed25519 signing (RFC 8032, section 6) ----
P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, P - 2, P) % P
GY = 4 * pow(5, P - 2, P) % P


def _x(y, sign):
    xx = (y * y - 1) * pow(D * y * y + 1, P - 2, P) % P
    x = pow(xx, (P + 3) // 8, P)
    if (x * x - xx) % P:
        x = x * pow(2, (P - 1) // 4, P) % P
    return P - x if x & 1 != sign else x


G = (_x(GY, 0), GY, 1, _x(GY, 0) * GY % P)


def _add(a, b):
    A = (a[1] - a[0]) * (b[1] - b[0]) % P
    B = (a[1] + a[0]) * (b[1] + b[0]) % P
    C = 2 * a[3] * b[3] * D % P
    E = 2 * a[2] * b[2] % P
    e, f, g, h = B - A, E - C, E + C, B + A
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _mul(s, point):
    q = (0, 1, 1, 0)
    while s:
        if s & 1:
            q = _add(q, point)
        point = _add(point, point)
        s >>= 1
    return q


def _encode(point):
    zi = pow(point[2], P - 2, P)
    x, y = point[0] * zi % P, point[1] * zi % P
    return int.to_bytes(y | ((x & 1) << 255), 32, 'little')


def _sha512(*parts):
    return int.from_bytes(hashlib.sha512(b''.join(parts)).digest(), 'little')


def keypair(seed):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], 'little')
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:], _encode(_mul(a, G))


def sign(key, message):
    a, prefix, public = key
    r = _sha512(prefix, message) % L
    R = _encode(_mul(r, G))
    s = (r + _sha512(R, public, message) * a) % L
    return R + int.to_bytes(s, 32, 'little')


# ---- A checksum database ----

def escaped(text):
    return ''.join('!' + c.lower() if 'A' <= c <= 'Z' else c for c in text)


def record_hash(data):
    return hashlib.sha256(b'\x00' + data).digest()


def node(left, right):
    return hashlib.sha256(b'\x01' + left + right).digest()


def tree_hash(leaves):
    if len(leaves) == 1:
        return leaves[0]
    k = 1
    while k * 2 < len(leaves):
        k *= 2
    return node(tree_hash(leaves[:k]), tree_hash(leaves[k:]))


def verifier(name, public):
    raw = b'\x01' + public
    keyhash = hashlib.sha256(name.encode() + b'\n' + raw).digest()[:4].hex()
    return f'{name}+{keyhash}+{base64.b64encode(raw).decode()}'


def tile_name(index):
    digits = str(index).rjust(3 * ((len(str(index)) + 2) // 3), '0')
    groups = [digits[i:i + 3] for i in range(0, len(digits), 3)]
    return '/'.join(['x' + g for g in groups[:-1]] + [groups[-1]])


def write_database(directory, name, key, records):
    """records: the data of each record, in order. Writes lookup/ for those
    naming a package and tile/ for the tree, signed as one note."""
    leaves = [record_hash(data) for data in records]
    size = len(leaves)
    text = f'go.sum database tree\n{size}\n{base64.b64encode(tree_hash(leaves)).decode()}\n'.encode()
    keyhash = hashlib.sha256(name.encode() + b'\n\x01' + key[2]).digest()[:4]
    note = text + b'\n\xe2\x80\x94 ' + name.encode() + b' ' + base64.b64encode(keyhash + sign(key, text)) + b'\n'
    # Tiles of height 8: level 0 holds the records' hashes, level 1 the
    # hashes of each 256 of them.
    level = leaves
    for tile_level in range(3):
        count = len(level)
        for index in range((count + 255) // 256):
            hashes = level[index * 256:(index + 1) * 256]
            path = directory / 'tile/8' / str(tile_level) / tile_name(index)
            if len(hashes) < 256:
                path = path.parent / (path.name + f'.p/{len(hashes)}')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b''.join(hashes))
        level = [tree_hash(level[i:i + 256]) for i in range(0, count - count % 256, 256)]
        if not level:
            break
    for id_, data in enumerate(records):
        module, version, _ = data.split(b'\n')[0].decode().split(' ')
        if version.endswith('/go.mod') or module.startswith('filler.test'):
            continue
        lookup = directory / 'lookup' / f'{escaped(module)}@{escaped(version)}'
        lookup.parent.mkdir(parents=True, exist_ok=True)
        lookup.write_bytes(f'{id_}\n'.encode() + data + b'\n' + note)


# ---- Packages ----

def archive(module, version, files, extra=()):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in list(files.items()) + list(extra):
            z.writestr(f'{module}@{version}/{name}' if not name.startswith('/') else name[1:], content)
    return out.getvalue()


def hash1(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(z.namelist())
        summary = ''.join(f'{hashlib.sha256(z.read(n)).hexdigest()}  {n}\n' for n in names)
    return 'h1:' + base64.b64encode(hashlib.sha256(summary.encode()).digest()).decode()


def publish(proxy, module, version, data):
    directory = proxy / escaped(module) / '@v'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f'{escaped(version)}.info').write_text(f'{{"Version":"{version}"}}')
    (directory / f'{escaped(version)}.mod').write_text(f'module {module}\n')
    (directory / f'{escaped(version)}.zip').write_bytes(data)


LIVE = {
    'lib/live.alc': 'defmodule Live do\n  @moduledoc """\n  Pages that stay connected.\n  """\n  import "wire.alc"\n\n  @doc "Greets a visitor."\n  def greet(name: string): string do\n    Wire.frame("hello " <> name)\n  end\nend\n',
    'lib/wire.alc': 'defmodule Wire do\n  def frame(text: string): string do\n    "wire: " <> text\n  end\nend\n',
    'go.mod': 'module example.test/lib\n',
}
MAIN = 'defmodule Main do\n  import "example.test/lib@v0.1.0/lib/live.alc"\n\n  def main() do\n    IO.puts(Live.greet("notes"))\n  end\nend\n'
HEADER = '# Generated by alchem. Records the content of remote packages and Go modules; commit this file.\n'


# Repositories of private packages, as git serves them to the go command
# (DIRECT holds what go mod download gave for them).
REPOSITORIES = {
    'private-repo': ({'go.mod': 'module github.com/owner/private-repo\n\ngo 1.24\n', **{k: v for k, v in LIVE.items() if k != 'go.mod'},
                      'nested/go.mod': 'module github.com/owner/private-repo/nested\n', 'nested/n.alc': 'defmodule N do\nend\n',
                      'vendor/x/y.go': 'package y\n', 'vendor/modules.txt': '# x\n', 'pkg/vendor/v.alc': 'defmodule V do\nend\n',
                      '.hg_archival.txt': 'repo: x\n', 'notes.txt': 'a\r\nb\r\n'},
                     {'link.alc': 'lib/live.alc'}, ['v0.1.0']),
    'mono': ({'LICENSE': 'licensed\n', 'tools/go.mod': 'module github.com/owner/mono/tools\n', 'tools/t.alc': 'defmodule T do\nend\n',
              'v2/go.mod': 'module github.com/owner/mono/v2\n', 'v2/m.alc': 'defmodule M2 do\nend\n'},
             {}, ['tools/v1.0.0', 'v2.0.0']),
}
DIRECT = {'github.com/owner/private-repo@v0.1.0': 'h1:npLpUmCmNnZVnpo/EoxNBt07AnYWj0sUR8l+LdS2spg=', 'github.com/owner/mono/tools@v1.0.0': 'h1:B8rMANRF8ALv2LBwBf0SGRuXrLQvpAvYjyu8rq/NCbs=',
          'github.com/owner/mono/v2@v2.0.0': 'h1:ivdAeK7SJ3cZ4vZ4TGpceFpnJdNXlOhxDf5xYz6KtR8='}


def repositories(top, git):
    """The repositories under top/github.com/owner, and a git configuration
    that fetches https://github.com/ from them."""
    quiet = {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'HOME': str(top), 'PATH': os.path.dirname(git),
             'GIT_AUTHOR_NAME': 'A', 'GIT_AUTHOR_EMAIL': 'a@example.test', 'GIT_COMMITTER_NAME': 'A', 'GIT_COMMITTER_EMAIL': 'a@example.test',
             'GIT_AUTHOR_DATE': '2026-01-01T00:00:00Z', 'GIT_COMMITTER_DATE': '2026-01-01T00:00:00Z'}
    for name, (files, links, tags) in REPOSITORIES.items():
        repo = top / 'github.com/owner' / name
        repo.mkdir(parents=True)
        for path, text in files.items():
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_bytes(text.encode())
        for path, target in links.items():
            os.symlink(target, repo / path)
        for command in (['init', '-q'], ['-c', 'core.autocrlf=false', 'add', '-A'], ['commit', '-q', '-m', 'x']) + tuple(['tag', tag] for tag in tags):
            subprocess.run([git] + command, cwd=repo, env=quiet, check=True, capture_output=True)
    config = top / 'gitconfig'
    config.write_text(f'[url "file://{top}/github.com/"]\n\tinsteadOf = https://github.com/\n')
    return config


class Served(SimpleHTTPRequestHandler):
    asked = []

    def log_message(self, *arguments):
        pass

    def do_GET(self):
        Served.asked.append(self.path)
        return super().do_GET()


def verify(compiler):
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-fetch-') as top:
        base = Path(top).resolve()
        alchem = base / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        system = builder.platform_of(compiler).split('/')[0]
        web = base / 'web'
        proxy = web / 'proxy'
        lib = archive('example.test/lib', 'v0.1.0', LIVE)
        publish(proxy, 'example.test/lib', 'v0.1.0', lib)
        bad = archive('example.test/bad', 'v1.0.0', {'bad.alc': 'defmodule Bad do\nend\n'})
        publish(proxy, 'example.test/bad', 'v1.0.0', bad)
        for name, extra, message in [('outside', [('/elsewhere/x.alc', 'x')], 'is not inside example.test/outside@v1.0.0/'),
                                     ('cased', [('A.alc', 'a'), ('a.alc', 'b')], 'case-insensitive file name collision')]:
            publish(proxy, f'example.test/{name}', 'v1.0.0', archive(f'example.test/{name}', 'v1.0.0', {}, extra))
        damaged = bytearray(archive('example.test/damaged', 'v1.0.0', {'d.alc': 'defmodule D do\nend\n' * 50}))
        damaged[damaged.index(b'PK\x01\x02') + 16] ^= 1
        publish(proxy, 'example.test/damaged', 'v1.0.0', bytes(damaged))
        # The database: fillers around the packages' records, so that the
        # proofs go through full and partial tiles of both levels.
        key = keypair(b'test sumdb seed'.ljust(32, b'.'))
        records = [f'filler.test/m{i} v1.0.0 h1:{base64.b64encode(hashlib.sha256(str(i).encode()).digest()).decode()}\n'.encode() for i in range(300)]
        records[5] = f'example.test/lib v0.1.0 {hash1(lib)}\nexample.test/lib v0.1.0/go.mod h1:x=\n'.encode()
        records[290] = b'example.test/bad v1.0.0 h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n'
        records[250] = f'github.com/owner/private-repo v0.1.0 {DIRECT["github.com/owner/private-repo@v0.1.0"]}\n'.encode()
        for i, name in enumerate(['outside', 'cased', 'damaged']):
            records[280 + i] = f'example.test/{name} v1.0.0 h1:x=\n'.encode()
        write_database(web / 'sumdb', 'test.sumdb', key, records)
        os.chdir(web)
        server = ThreadingHTTPServer(('127.0.0.1', 0), lambda *a, **k: Served(*a, directory=str(web), **k))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        address = f'http://127.0.0.1:{server.server_address[1]}'
        database = verifier('test.sumdb', key[2]) + ' ' + address + '/sumdb'
        try:
            cache = base / 'cache'
            plain = {'PATH': '', 'HOME': str(base / 'home'), 'ALCHEM_CACHE': str(cache), 'GOMODCACHE': str(base / 'nogo'),
                     'GOPROXY': address + '/proxy', 'GOSUMDB': database, 'GOENV': str(base / 'goenv')}

            def run(directory, arguments, **settings):
                environment = {**plain, **settings}
                environment = {k: v for k, v in environment.items() if v is not None}
                done = subprocess.run([str(alchem)] + arguments, cwd=directory, capture_output=True, env=environment, timeout=300)
                return done.returncode, done.stdout.decode(errors='replace'), done.stderr.decode(errors='replace')

            project = base / 'project'
            project.mkdir()
            (project / 'main.alc').write_text(MAIN)
            # Fetched from the proxy and proved in the database's tree.
            Served.asked.clear()
            assert run(project, ['run', 'main.alc']) == (0, 'wire: hello notes\n', ''), run(project, ['run', 'main.alc'])
            assert (project / 'alchem.lock').read_text() == HEADER + f'package example.test/lib v0.1.0 {hash1(lib)}\n', (project / 'alchem.lock').read_text()
            kept = cache / 'packages/example.test/lib@v0.1.0'
            assert (kept / 'h1').read_text() == hash1(lib) + '\n' and (kept / 'files/lib/live.alc').read_text() == LIVE['lib/live.alc']
            assert '/sumdb/lookup/example.test/lib@v0.1.0' in Served.asked and '/sumdb/tile/8/0/000' in Served.asked and '/sumdb/tile/8/0/001.p/44' in Served.asked, Served.asked
            assert not [p for p in (cache / 'packages').iterdir() if p.name.startswith('.')]
            # Read again from the cache: nothing is asked.
            Served.asked.clear()
            assert run(project, ['run', 'main.alc'], GOPROXY='off')[0] == 0 and Served.asked == [], Served.asked
            # doc of a package's file, kept already.
            status, out, _ = run(project, ['doc', 'example.test/lib@v0.1.0/lib/live.alc'])
            assert status == 0 and 'Pages that stay connected.' in out, out
            # Two builds that fetch at once, into an empty cache.
            shutil.rmtree(cache)
            with ThreadPoolExecutor(2) as pool:
                both = list(pool.map(lambda _: run(project, ['run', 'main.alc']), range(2)))
            assert both == [(0, 'wire: hello notes\n', '')] * 2, both
            assert sorted(p.name for p in (cache / 'packages/example.test').iterdir()) == ['lib@v0.1.0'], list((cache / 'packages/example.test').iterdir())
            assert not [p for p in (cache / 'packages').iterdir() if p.name.startswith('.')]
            # A lock that records another hash.
            (project / 'alchem.lock').write_text(HEADER + 'package example.test/lib v0.1.0 h1:AAAA\n')
            status, _, err = run(project, ['run', 'main.alc'])
            assert status == 1 and f'example.test/lib@v0.1.0 does not match alchem.lock: locked h1:AAAA, fetched {hash1(lib)}' in err, err
            (project / 'alchem.lock').unlink()

            def refused(target, want, **settings):
                directory = base / ('p' + hashlib.sha256((target + repr(settings)).encode()).hexdigest()[:8])
                directory.mkdir(exist_ok=True)
                (directory / 'main.alc').write_text(f'defmodule Main do\n  import "{target}"\n\n  def main() do\n    IO.puts("x")\n  end\nend\n')
                fresh = base / ('cache-' + directory.name)
                status, out, err = run(directory, ['run', 'main.alc'], ALCHEM_CACHE=str(fresh), **settings)
                assert status == 1 and all(w in err for w in want), (target, settings, status, out, err)
                assert not (fresh / 'packages').exists() or not [p for p in (fresh / 'packages').rglob('h1')], (target, list((fresh / 'packages').rglob('*')))
                return err

            # The database's hash differs: nothing is kept. Its record is
            # proved with a hash of the second level of tiles.
            Served.asked.clear()
            refused('example.test/bad@v1.0.0/bad.alc', ['fetch example.test/bad@v1.0.0: verifying example.test/bad@v1.0.0: checksum mismatch', f'downloaded: {hash1(bad)}', 'SECURITY ERROR'])
            assert '/sumdb/tile/8/1/000.p/1' in Served.asked, Served.asked
            # A database whose key is not the one that signed the tree.
            other = keypair(b'another seed'.ljust(32, b'.'))
            refused('example.test/lib@v0.1.0/lib/live.alc', ['verifying example.test/lib@v0.1.0: verifying tree: invalid signature'], GOSUMDB=verifier('test.sumdb', other[2]) + ' ' + address + '/sumdb')
            # A package the database does not record.
            publish(proxy, 'example.test/unrecorded', 'v1.0.0', archive('example.test/unrecorded', 'v1.0.0', {'u.alc': 'defmodule U do\nend\n'}))
            refused('example.test/unrecorded@v1.0.0/u.alc', ['verifying example.test/unrecorded@v1.0.0: reading ' + address + '/sumdb/lookup/example.test/unrecorded@v1.0.0: 404 Not Found'])
            # GONOSUMDB: not asked of the database, from a proxy of files.
            Served.asked.clear()
            status, out, _ = run(project, ['run', 'main.alc'], ALCHEM_CACHE=str(base / 'cache-nosum'), GONOSUMDB='example.test', GOPROXY='file://' + str(proxy))
            assert (status, out) == (0, 'wire: hello notes\n') and Served.asked == [], (status, out, Served.asked)
            # The proxies: off, none that has it, fall-through after , and |.
            refused('example.test/lib@v0.1.0/lib/live.alc', ['example.test/lib@v0.1.0: module lookup disabled by GOPROXY=off'], GOPROXY='off')
            refused('example.test/lib@v9.9.9/lib/live.alc', [f'fetch example.test/lib@v9.9.9: example.test/lib@v9.9.9: reading {address}/proxy/example.test/lib/@v/v9.9.9.info: 404 Not Found'])
            for proxies, works in [(address + '/nothing,' + address + '/proxy', True), ('http://127.0.0.1:1|' + address + '/proxy', True), ('http://127.0.0.1:1,' + address + '/proxy', False)]:
                status, _, err = run(project, ['run', 'main.alc'], ALCHEM_CACHE=str(base / ('cache-' + hashlib.sha256(proxies.encode()).hexdigest()[:8])), GOPROXY=proxies)
                assert (status == 0) == works, (proxies, status, err)
            # Private packages, fetched with git from their repositories (here
            # on this machine, by git's insteadOf), with the hashes go mod
            # download gives them; nothing about them is asked of a server.
            git = shutil.which('git')
            assert git, 'the fetch gate needs git'
            config = repositories(base / 'repositories', git)
            with_git = {'PATH': os.path.dirname(git), 'GIT_CONFIG_GLOBAL': str(config), 'GIT_CONFIG_NOSYSTEM': '1'}
            Served.asked.clear()
            made = {}
            for package, sum_ in DIRECT.items():
                module, version = package.split('@')
                inside = {'github.com/owner/private-repo': 'lib/live.alc', 'github.com/owner/mono/tools': 't.alc', 'github.com/owner/mono/v2': 'm.alc'}[module]
                for setting in ({'ALCHEM_PRIVATE': 'github.com/owner/*'}, {'goenv': 'GOPRIVATE=github.com/owner\n'}):
                    directory = base / ('git-' + hashlib.sha256((package + repr(setting)).encode()).hexdigest()[:8])
                    directory.mkdir()
                    (directory / 'main.alc').write_text(f'defmodule Main do\n  import "{package}/{inside}"\n\n  def main() do\n    IO.puts("ok")\n  end\nend\n')
                    if 'goenv' in setting:
                        (base / 'goenv').write_text(setting['goenv'])
                    done = run(directory, ['run', 'main.alc'], ALCHEM_CACHE=str(directory / 'cache'), **with_git, **{k: v for k, v in setting.items() if k != 'goenv'})
                    (base / 'goenv').unlink(missing_ok=True)
                    assert done == (0, 'ok\n', ''), (package, setting, done)
                    assert (directory / 'alchem.lock').read_text() == HEADER + f'package {module} {version} {sum_}\n', (package, (directory / 'alchem.lock').read_text())
                    made.setdefault(package, directory)
            assert Served.asked == [], Served.asked
            private = made['github.com/owner/private-repo@v0.1.0']
            kept = private / 'cache/packages/github.com/owner/private-repo@v0.1.0/files'
            files = sorted(str(f.relative_to(kept)) for f in kept.rglob('*') if f.is_file())
            assert files == ['go.mod', 'lib/live.alc', 'lib/wire.alc', 'notes.txt', 'pkg/vendor/v.alc'], files
            refused('github.com/owner/private-repo@v9.9.9/lib/live.alc', ['fetch github.com/owner/private-repo@v9.9.9: github.com/owner/private-repo@v9.9.9: invalid version: unknown revision v9.9.9'], ALCHEM_PRIVATE='github.com/owner/*', **with_git)
            refused('github.com/owner/absent@v1.0.0/x.alc', ['github.com/owner/absent@v1.0.0: invalid version: git ls-remote -q --end-of-options https://github.com/owner/absent in ', 'exit status 128'], ALCHEM_PRIVATE='github.com/owner/*', **with_git)
            refused('github.com/owner/private-repo@v0.1.0/lib/live.alc', ['github.com/owner/private-repo@v0.1.0: git is not installed'], ALCHEM_PRIVATE='github.com/owner/*', PATH='')
            assert Served.asked == [], Served.asked
            # GOPROXY=direct for a package that is not private: from git, and
            # checked against the database.
            status, out, err = run(private, ['run', 'main.alc'], ALCHEM_CACHE=str(base / 'cache-direct'), GOPROXY='direct', **with_git)
            assert (status, out) == (0, 'ok\n') and Served.asked == ['/sumdb/lookup/github.com/owner/private-repo@v0.1.0'] + [a for a in Served.asked[1:] if a.startswith('/sumdb/tile/')], (status, err, Served.asked)
            # Archives that are not a module's.
            for name, message in [('outside', 'is not inside example.test/outside@v1.0.0/'), ('cased', 'case-insensitive file name collision'), ('damaged', 'zip: checksum error')]:
                refused(f'example.test/{name}@v1.0.0/x.alc', [message])
            # The cache when ALCHEM_CACHE is not set: in the user's cache directory.
            home = base / 'home'
            assert run(project, ['run', 'main.alc'], ALCHEM_CACHE=None)[0] == 0
            where = home / ('Library/Caches' if system == 'darwin' else '.cache') / 'alchem/packages/example.test/lib@v0.1.0/h1'
            assert where.exists(), list(home.rglob('h1'))
            # The tree the database showed last is kept, and each tree is
            # checked against it (Client.checkTrees): one grown from it and an
            # older one are on its timeline; a fork, larger or of the same
            # size, is the database showing different trees.
            trees = {'grown': records + records[:10], 'fork': records[:100] + [b'filler.test/forked v1.0.0 h1:x=\n'] + records[101:] + records[:20],
                     'same': records[:100] + [b'filler.test/forked v1.0.0 h1:x=\n'] + records[101:] + records[:10]}
            for name, held in trees.items():
                write_database(web / ('sumdb-' + name), 'test.sumdb', key, held)
            # The tree of 300 again, with the tiles of the tree of 310 the
            # check reads.
            shutil.copytree(web / 'sumdb-grown', web / 'sumdb-back')
            shutil.copytree(web / 'sumdb', web / 'sumdb-back', dirs_exist_ok=True)
            seen = base / 'cache-trees'
            latest = seen / 'sumdb/test.sumdb/latest'
            for served, works, size in [('sumdb', True, 300), ('sumdb-grown', True, 310), ('sumdb-back', True, 310), ('sumdb-fork', False, 310), ('sumdb-same', False, 310)]:
                shutil.rmtree(seen / 'packages', ignore_errors=True)
                status, _, err = run(project, ['run', 'main.alc'], ALCHEM_CACHE=str(seen), GOSUMDB=verifier('test.sumdb', key[2]) + ' ' + address + '/' + served)
                assert (status == 0) == works, (served, status, err)
                assert works or ('go.sum database server misbehavior detected!' in err and not (seen / 'packages/example.test/lib@v0.1.0').exists()), (served, err)
                assert latest.read_text().split('\n')[1] == str(size), (served, latest.read_text())
            # A tile that is not the tree's: the record is not proved.
            tile = web / 'sumdb/tile/8/0/001.p/44'
            tile.write_bytes(bytes([tile.read_bytes()[0] ^ 1]) + tile.read_bytes()[1:])
            refused('example.test/lib@v0.1.0/lib/live.alc', ['verifying example.test/lib@v0.1.0: verifying tree: the record is not in the signed tree'])
        finally:
            server.shutdown()
            os.chdir(ROOT)
    print('PASS fetch: a package fetched from a module proxy over HTTP and from files, proved in a signed checksum database by its tiles, kept in alchem\'s cache and read from it offline; two fetches at once; doc of a package file; GOPROXY lists, off and fall-through; a differing hash, another key, trees grown, older and forked against the latest one seen, a tile not the tree\'s, an unrecorded package, GONOSUMDB, private packages fetched with git as Go fetches them (asked of no server), GOPROXY=direct, three bad archives and the default cache directory')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
