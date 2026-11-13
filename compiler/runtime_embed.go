package compiler

import (
	"embed"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// Runtime source is bundled so generated projects never fetch an Alchem module.
//
//go:embed actor/process.go actor/supervisor.go actor/server.go actor/hamt.go actor/task.go actor/rescue.go actor/concat.go actor/remote.go actor/services.go actor/node/node.go
var runtimeSources embed.FS

// librarySource is the standard library runtime: Go that joins the generated
// program's main package, where the list and option types it uses live. It
// is written in sections, each introduced by a "// ---- Name ----" line.
//
//go:embed library.go.txt
var librarySource string

// Coverage of the runtime: when ALCHEM_GO_COVERAGE names a directory, programs
// are built with Go's coverage counters in the runtime and the library and
// write their counts there when they exit; and each line of
// library.go.txt is placed at that line plus LibraryLineOffset in the
// program's library.go, so that counts from different programs refer to the
// same lines. tools/coverage merges the counts with the compiler's.
const LibraryLineOffset = 100

var mapLibraryLines = os.Getenv("ALCHEM_GO_COVERAGE") != ""

var (
	identifier  = regexp.MustCompile(`[A-Za-z_][A-Za-z0-9_]*`)
	declaration = regexp.MustCompile(`(?m)^(?:func|type|var|const) ([A-Za-z_][A-Za-z0-9_]*)`)
)

// libraryImports are the packages the runtime sections may use, by the name
// they are referred to with.
var libraryImports = map[string]string{
	"atomic": "sync/atomic", "bufio": "bufio", "bytes": "bytes", "reflect": "reflect", "context": "context", "crand": "crypto/rand", "hmac": "crypto/hmac", "md5": "crypto/md5", "sha1": "crypto/sha1", "sha256": "crypto/sha256", "sha512": "crypto/sha512", "subtle": "crypto/subtle", "binary": "encoding/binary", "net": "net", "http": "net/http", "big": "math/big", "cmp": "cmp", "slices": "slices", "base32": "encoding/base32", "base64": "encoding/base64", "hex": "encoding/hex", "hash": "hash", "html": "html", "json": "encoding/json",
	"errors": "errors", "fmt": "fmt", "io": "io", "iter": "iter", "math": "math", "node": "alchem.local/actor/node", "rand": "math/rand/v2", "os": "os", "exec": "os/exec",
	"filepath": "path/filepath", "regexp": "regexp", "runtime": "runtime", "sort": "sort", "strconv": "strconv", "strings": "strings",
	"sync": "sync", "time": "time", "tls": "crypto/tls", "x509": "crypto/x509", "log": "log", "unicode": "unicode", "url": "net/url", "utf8": "unicode/utf8", "actor": "alchem.local/actor",
}

// selectLibrary returns the runtime sections a generated program needs: those
// declaring a name the program mentions, and whatever those sections use in
// turn. A program that calls no library function gets an empty file, so the
// library costs nothing to programs that do not use it.
func selectLibrary(generated string) string {
	sections := strings.Split("\n"+librarySource, "\n// ---- ")
	used := map[string]bool{}
	for _, name := range identifier.FindAllString(generated, -1) {
		used[name] = true
	}
	included := make([]bool, len(sections))
	for changed := true; changed; {
		changed = false
		for i, section := range sections {
			if included[i] {
				continue
			}
			for _, match := range declaration.FindAllStringSubmatch(section, -1) {
				if used[match[1]] {
					included[i], changed = true, true
					for _, name := range identifier.FindAllString(section, -1) {
						used[name] = true
					}
					break
				}
			}
		}
	}
	var body strings.Builder
	for i, section := range sections {
		switch {
		case mapLibraryLines && i == 0:
			// The pieces joined by newlines give back library.go.txt, with
			// the sections left out as blank lines.
			body.WriteString(blankUnless(included[i], section[1:]))
		case mapLibraryLines:
			body.WriteString("\n" + blankUnless(included[i], "// ---- "+section))
		case included[i]:
			body.WriteString("\n// ---- " + section + "\n")
		}
	}
	var out strings.Builder
	out.WriteString("package main\n\nimport (\n")
	names := []string{}
	for name := range libraryImports {
		names = append(names, name)
	}
	sort.Strings(names)
	// Comments mention packages too; only code decides what is imported.
	code := regexp.MustCompile(`(?m)(^|\s)//.*$`).ReplaceAllString(body.String(), "")
	for _, name := range names {
		if regexp.MustCompile(`\b` + name + `\.`).MatchString(code) {
			out.WriteString("\t" + name + " " + strconv.Quote(libraryImports[name]) + "\n")
		}
	}
	// Time zones come from the database built into the program, so that it
	// behaves the same on a system that has none installed.
	if strings.Contains(code, "time.LoadLocation(") {
		out.WriteString("\t_ \"time/tzdata\"\n")
	}
	out.WriteString(")\n")
	if mapLibraryLines {
		lines := strings.Count(out.String(), "\n")
		if lines > LibraryLineOffset {
			panic("the library's imports take more than LibraryLineOffset lines")
		}
		out.WriteString(strings.Repeat("\n", LibraryLineOffset-lines))
	}
	out.WriteString(body.String())
	return out.String()
}

// blankUnless returns text, or as many empty lines as it has when it is not
// kept.
func blankUnless(keep bool, text string) string {
	if keep {
		return text
	}
	return strings.Repeat("\n", strings.Count(text, "\n"))
}
