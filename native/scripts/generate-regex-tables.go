//go:build ignore

// Regenerate spec/regex-tables.json from the pinned Go unicode package: what
// regexp/syntax takes from it for \p{...} and for (?i). Development step only:
// go run scripts/generate-regex-tables.go > spec/regex-tables.json
//
//	categories  the general categories no other is made of, each as ranges
//	            [first, last]; unions says which of them make up the others
//	scripts     the scripts, each as ranges
//	aliases     the other names of categories (unicode.CategoryAliases)
//	fold        unicode.SimpleFold as [first, last, stride, delta]: first,
//	            first+stride, ..., last each fold to themselves plus delta;
//	            in the order of their first, which two runs may share
//	unfolded    per category or script the characters that regexp/syntax
//	            does not add under (?i) although one they fold to is in it
//	            (unicode.FoldCategory and FoldScript against SimpleFold)
package main

import (
	"fmt"
	"runtime"
	"sort"
	"strings"
	"unicode"
)

func spans(t *unicode.RangeTable) [][2]int {
	var out [][2]int
	add := func(lo, hi, stride int) {
		for c := lo; c <= hi; c += stride {
			last := c
			if stride == 1 {
				last = hi
			}
			if n := len(out); n > 0 && out[n-1][1]+1 == c {
				out[n-1][1] = last
			} else {
				out = append(out, [2]int{c, last})
			}
			if stride == 1 {
				break
			}
		}
	}
	for _, r := range t.R16 {
		add(int(r.Lo), int(r.Hi), int(r.Stride))
	}
	for _, r := range t.R32 {
		add(int(r.Lo), int(r.Hi), int(r.Stride))
	}
	return out
}

func text(s [][2]int) string {
	parts := make([]string, len(s))
	for i, r := range s {
		parts[i] = fmt.Sprintf("[%d,%d]", r[0], r[1])
	}
	return "[" + strings.Join(parts, ",") + "]"
}

func keys[V any](m map[string]V) []string {
	var out []string
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// unfolded lists the characters outside tab that fold to one inside it and
// that fold does not hold.
func unfolded(tab, fold *unicode.RangeTable) []int {
	var out []int
	for r := rune(0); r <= unicode.MaxRune; r++ {
		if unicode.Is(tab, r) || fold != nil && unicode.Is(fold, r) {
			continue
		}
		for f := unicode.SimpleFold(r); f != r; f = unicode.SimpleFold(f) {
			if unicode.Is(tab, f) {
				out = append(out, int(r))
				break
			}
		}
	}
	// The other way round would be a character fold holds that folds to
	// none in tab; there is none, which this checks.
	if fold != nil {
		for r := rune(0); r <= unicode.MaxRune; r++ {
			if !unicode.Is(fold, r) || unicode.Is(tab, r) {
				continue
			}
			found := false
			for f := unicode.SimpleFold(r); f != r; f = unicode.SimpleFold(f) {
				found = found || unicode.Is(tab, f)
			}
			if !found {
				panic(fmt.Sprintf("fold table holds %x, which folds to nothing in its table", r))
			}
		}
	}
	return out
}

func main() {
	unions := map[string][]string{}
	var leaves []string
	for _, name := range keys(unicode.Categories) {
		if len(name) == 2 && name != "LC" {
			leaves = append(leaves, name)
		}
	}
	for _, name := range keys(unicode.Categories) {
		if len(name) == 2 && name != "LC" {
			continue
		}
		var parts []string
		for _, leaf := range leaves {
			if name == "LC" && (leaf == "Lu" || leaf == "Ll" || leaf == "Lt") || name != "LC" && leaf[:1] == name {
				parts = append(parts, leaf)
			}
		}
		for r := rune(0); r <= unicode.MaxRune; r++ {
			in := false
			for _, leaf := range parts {
				in = in || unicode.Is(unicode.Categories[leaf], r)
			}
			if in != unicode.Is(unicode.Categories[name], r) {
				panic("category " + name + " is not the union of its parts")
			}
		}
		unions[name] = parts
	}
	fmt.Printf("{\n \"go\": %q,\n \"unicode\": %q,\n \"categories\": {\n", runtime.Version(), unicode.Version)
	for i, name := range leaves {
		comma := ","
		if i == len(leaves)-1 {
			comma = ""
		}
		fmt.Printf("  %q: %s%s\n", name, text(spans(unicode.Categories[name])), comma)
	}
	fmt.Printf(" },\n \"unions\": {\n")
	for i, name := range keys(unions) {
		comma := ","
		if i == len(unions)-1 {
			comma = ""
		}
		fmt.Printf("  %q: [\"%s\"]%s\n", name, strings.Join(unions[name], "\",\""), comma)
	}
	fmt.Printf(" },\n \"scripts\": {\n")
	scripts := keys(unicode.Scripts)
	for i, name := range scripts {
		comma := ","
		if i == len(scripts)-1 {
			comma = ""
		}
		fmt.Printf("  %q: %s%s\n", name, text(spans(unicode.Scripts[name])), comma)
	}
	fmt.Printf(" },\n \"aliases\": {\n")
	aliases := keys(unicode.CategoryAliases)
	for i, name := range aliases {
		comma := ","
		if i == len(aliases)-1 {
			comma = ""
		}
		fmt.Printf("  %q: %q%s\n", name, unicode.CategoryAliases[name], comma)
	}
	fmt.Printf(" },\n \"fold\": [\n")
	type span struct{ start, end, stride, delta int }
	var folds []span
	for r := 0; r <= unicode.MaxRune; r++ {
		delta := int(unicode.SimpleFold(rune(r))) - r
		if delta == 0 {
			continue
		}
		// Upper and lower case letters often alternate, so the run a
		// character continues may be the one before the last.
		merged := false
		for back := 1; back <= 2 && back <= len(folds) && !merged; back++ {
			last := &folds[len(folds)-back]
			if last.delta != delta {
				continue
			}
			gap := r - last.end
			if last.start == last.end && gap <= 2 {
				last.stride, last.end, merged = gap, r, true
			} else if gap == last.stride {
				last.end, merged = r, true
			}
		}
		if merged {
			continue
		}
		folds = append(folds, span{r, r, 1, delta})
	}
	for i, f := range folds {
		comma := ","
		if i == len(folds)-1 {
			comma = ""
		}
		fmt.Printf("  [%d, %d, %d, %d]%s\n", f.start, f.end, f.stride, f.delta, comma)
	}
	fmt.Printf(" ],\n \"unfolded\": {")
	first := true
	for _, name := range keys(unicode.Categories) {
		if list := unfolded(unicode.Categories[name], unicode.FoldCategory[name]); len(list) > 0 {
			if !first {
				fmt.Printf(",")
			}
			first = false
			fmt.Printf("\n  %q: %s", name, strings.ReplaceAll(fmt.Sprint(list), " ", ","))
		}
	}
	for _, name := range scripts {
		if list := unfolded(unicode.Scripts[name], unicode.FoldScript[name]); len(list) > 0 {
			if !first {
				fmt.Printf(",")
			}
			first = false
			fmt.Printf("\n  %q: %s", name, strings.ReplaceAll(fmt.Sprint(list), " ", ","))
		}
	}
	fmt.Printf("\n }\n}\n")
}
