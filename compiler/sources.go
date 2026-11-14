package compiler

import (
	"context"
	"io/fs"
	"path/filepath"
	"sort"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// ProjectSource is one module a project holds or imports: its name, its
// file, and the path a person would write to name it, which for a file of a
// package is the path an import gives.
type ProjectSource struct {
	Module, File, Shown string
}

// maxProjectSources bounds how many files ProjectSources reads.
const maxProjectSources = 2000

// maxProjectEntries bounds how many files and directories it walks past.
const maxProjectEntries = 50000

// ProjectSources lists the modules of the source files under a directory
// and of every package file they import, following imports inside those
// packages. Packages are read from the module cache only: one that has not
// been fetched yet is left out, so listing never contacts the network.
// Files that do not parse are left out too.
func ProjectSources(ctx context.Context, dir string) []ProjectSource {
	var out []ProjectSource
	seen := map[string]bool{}
	roots := map[string]string{}
	var visit func(file, shown, root, prefix string)
	visit = func(file, shown, root, prefix string) {
		if seen[file] || len(seen) >= maxProjectSources || ctx.Err() != nil {
			return
		}
		seen[file] = true
		data, err := ReadSource(file)
		if err != nil {
			return
		}
		module, err := syntax.ParseSyntax(string(data))
		if err != nil {
			return
		}
		out = append(out, ProjectSource{Module: module.Module, File: file, Shown: shown})
		for _, imp := range module.Imports {
			if RemoteSource(imp) {
				parts := remoteImport.FindStringSubmatch(imp)
				key := parts[1] + "@" + parts[2]
				fetched, known := roots[key]
				if !known {
					fetched, _, _ = fetchPackageFrom(ctx, key, true)
					roots[key] = fetched
				}
				if fetched != "" {
					visit(filepath.Join(fetched, filepath.FromSlash(parts[3])), imp, fetched, key+"/")
				}
				continue
			}
			// Only the files of a package are followed here: those of the
			// project itself are found by walking its directory.
			if root == "" || strings.Contains(imp, "@") || filepath.IsAbs(imp) {
				continue
			}
			target := filepath.Join(filepath.Dir(file), filepath.FromSlash(imp))
			if !within(root, target) {
				continue
			}
			relative, err := filepath.Rel(root, target)
			if err != nil {
				continue
			}
			visit(target, prefix+filepath.ToSlash(relative), root, prefix)
		}
	}
	var local []string
	walked := 0
	_ = filepath.WalkDir(dir, func(path string, entry fs.DirEntry, err error) error {
		// A directory that is not a project, a home directory say, is not
		// read to its end.
		if walked++; walked > maxProjectEntries || ctx.Err() != nil {
			return filepath.SkipAll
		}
		if err != nil {
			return nil
		}
		name := entry.Name()
		if entry.IsDir() {
			if path != dir && (strings.HasPrefix(name, ".") || name == "node_modules" || name == "vendor") {
				return filepath.SkipDir
			}
			return nil
		}
		if filepath.Ext(name) == ".alc" && len(local) < maxProjectSources {
			local = append(local, path)
		}
		return nil
	})
	sort.Strings(local)
	for _, path := range local {
		shown, err := filepath.Rel(dir, path)
		if err != nil {
			shown = path
		}
		if absolute, err := filepath.Abs(path); err == nil {
			path = absolute
		}
		visit(path, filepath.ToSlash(shown), "", "")
	}
	return out
}
