// Command provenance reports passages of Alchem's documentation that match
// Elixir's word for word: runs of at least -words consecutive words that
// also appear, in the same order, in an Elixir source tree.
//
//	go run ./tools/provenance -elixir path/to/elixir [-words 10]
//
// Words are compared case-insensitively with punctuation removed, so a
// match survives reformatting. The generated reference pages are skipped:
// they repeat the library documentation that is checked at its source.
package main

import (
	"flag"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var word = regexp.MustCompile(`[A-Za-z0-9_]+[?!]?`)

// generated pages are written by alchem docs from the checked sources.
var generated = map[string]bool{
	"docs/library-reference.md": true,
	"docs/syntax-reference.md":  true,
	"docs/agent-guide.md":       true,
	"docs/cli-reference.md":     true,
}

type match struct {
	file  string
	line  int
	words int
	text  string
}

func main() {
	elixir := flag.String("elixir", "", "Elixir source tree to compare against")
	n := flag.Int("words", 10, "shortest run of shared words reported")
	flag.Parse()
	if *elixir == "" || *n < 2 {
		fmt.Fprintln(os.Stderr, "usage: go run ./tools/provenance -elixir path [-words 10]")
		os.Exit(2)
	}
	reference, err := shingles(*elixir, *n)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if len(reference) == 0 {
		fmt.Fprintln(os.Stderr, "no Elixir sources found under", *elixir)
		os.Exit(1)
	}
	matches, err := compare(reference, *n)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	for _, m := range matches {
		fmt.Printf("%s:%d: %d words: %s\n", m.file, m.line, m.words, m.text)
	}
	fmt.Printf("%d passages of %d or more words shared with %s\n", len(matches), *n, *elixir)
	if len(matches) > 0 {
		os.Exit(1)
	}
}

func words(text string) []string {
	found := word.FindAllString(text, -1)
	for i := range found {
		found[i] = strings.ToLower(found[i])
	}
	return found
}

// shingles collects every run of n words in Elixir's sources and guides.
func shingles(root string, n int) (map[string]bool, error) {
	set := map[string]bool{}
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		switch filepath.Ext(path) {
		case ".ex", ".exs", ".md", ".cheatmd":
		default:
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		w := words(string(data))
		for i := 0; i+n <= len(w); i++ {
			set[strings.Join(w[i:i+n], " ")] = true
		}
		return nil
	})
	return set, err
}

// compare finds the runs of Alchem's documentation found in reference:
// the library and syntax documentation, the guide, the docs and the README.
func compare(reference map[string]bool, n int) ([]match, error) {
	var files []string
	for _, pattern := range []string{"compiler/syntax/*.go", "guide/*.go", "guide/*.md", "docs/*.md", "README.md"} {
		found, err := filepath.Glob(pattern)
		if err != nil {
			return nil, err
		}
		for _, f := range found {
			if !strings.HasSuffix(f, "_test.go") && !generated[filepath.ToSlash(f)] {
				files = append(files, f)
			}
		}
	}
	sort.Strings(files)
	var out []match
	for _, f := range files {
		data, err := os.ReadFile(f)
		if err != nil {
			return nil, err
		}
		text := string(data)
		spans := word.FindAllStringIndex(text, -1)
		w := make([]string, len(spans))
		for i, s := range spans {
			w[i] = strings.ToLower(text[s[0]:s[1]])
		}
		for i := 0; i+n <= len(w); {
			if !reference[strings.Join(w[i:i+n], " ")] {
				i++
				continue
			}
			j := i
			for j+1+n <= len(w) && reference[strings.Join(w[j+1:j+1+n], " ")] {
				j++
			}
			out = append(out, match{f, strings.Count(text[:spans[i][0]], "\n") + 1, j - i + n, strings.Join(w[i:j+n], " ")})
			i = j + n
		}
	}
	return out, nil
}
