#!/usr/bin/env python3
"""Build the pinned compiler's loader as a program that writes the loaded
program as JSON: what its checker (syntax.Analyze) is given.

    pinned-loaded.py OUTPUT

The loader (compiler.loadProjectAs) is not exported, and it runs the checker
before it returns. So the pinned module is copied from the Go module cache
(GOMODCACHE) to a directory of its own, and two things are added to the copy
and nothing else changed: a file that exports the loader, and a test of an
environment variable before the checker, which the program sets. The program
takes FILE..., and writes for each one line: the path and the loaded program,
or the path, "error" and the loader's message. Statements and the fields kept
for the literal-only parser API are left out, as scripts/pinned-module leaves
them out. Not used by normal builds."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE = 'github.com/SmithOperatingSolutions/alchem'

EXPORT = '''package compiler

import (
	"context"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// LoadProjectAs is loadProjectAs, for scripts/pinned-loaded.py.
func LoadProjectAs(ctx context.Context, entry string, library bool) (ast.Program, error) {
	return loadProjectAs(ctx, entry, library)
}
'''

MAIN = '''package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

func main() {
	os.Setenv("ALCHEM_PINNED_LOADED", "1")
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	for _, path := range os.Args[1:] {
		program, err := compiler.LoadProjectAs(context.Background(), path, true)
		var line []byte
		if err != nil {
			line, _ = json.Marshal([]any{path, "error", err.Error()})
		} else {
			program.Statements, program.Output, program.Comparison, program.Assertion = nil, "", nil, nil
			line, _ = json.Marshal([]any{path, program})
		}
		fmt.Fprintln(out, string(line))
	}
}
'''

ANALYZE = '\tif err := syntax.Analyze(&out); err != nil {\n'
GUARDED = '\tif os.Getenv("ALCHEM_PINNED_LOADED") != "" {\n\t\treturn out, nil\n\t}\n' + ANALYZE


def main(arguments):
    if len(arguments) != 1:
        raise SystemExit(__doc__)
    output = Path(arguments[0]).resolve()
    pinned = (ROOT / 'scripts/pinned-parser/go.mod').read_text().split(MODULE + ' ')[1].split()[0]
    cache = Path(os.environ.get('GOMODCACHE') or subprocess.run(['go', 'env', 'GOMODCACHE'], capture_output=True, text=True, check=True).stdout.strip())
    source = cache / 'github.com/!smith!operating!solutions' / f'alchem@{pinned}'
    with tempfile.TemporaryDirectory() as d:
        copy = Path(d) / 'alchem'
        shutil.copytree(source, copy)
        for path in copy.rglob('*'):
            path.chmod(0o755 if path.is_dir() else 0o644)
        project = copy / 'compiler/project.go'
        text = project.read_text()
        if text.count(ANALYZE) != 1:
            raise SystemExit('compiler/project.go does not call syntax.Analyze once as expected')
        project.write_text(text.replace(ANALYZE, GUARDED))
        (copy / 'compiler/export_loader.go').write_text(EXPORT)
        tool = Path(d) / 'tool'
        tool.mkdir()
        (tool / 'go.mod').write_text(f'module pinnedloaded\n\ngo 1.27\n\nrequire {MODULE} v0.0.0\n\nreplace {MODULE} => ../alchem\n')
        (tool / 'main.go').write_text(MAIN)
        environment = dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off')
        subprocess.run(['go', 'build', '-o', str(output), '.'], cwd=tool, check=True, env=environment)
    print(f'built {output}')


if __name__ == '__main__':
    main(sys.argv[1:])
