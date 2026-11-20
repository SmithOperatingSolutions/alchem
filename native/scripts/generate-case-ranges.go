//go:build ignore

// Regenerate spec/case-ranges.json from the pinned Go unicode.ToUpper/ToLower/
// ToTitle simple mappings, which strings.ToUpper/ToLower/ToTitle
// (String.upcase/downcase/capitalize) use.
// Each range [start, end, stride, delta] maps start, start+stride, ..., end to
// rune+delta. Development step only:
// go run scripts/generate-case-ranges.go > spec/case-ranges.json
package main

import (
	"fmt"
	"runtime"
	"unicode"
)

type span struct{ start, end, stride, delta int }

func ranges(mapping func(rune) rune) []span {
	var out []span
	for r := 0x80; r <= unicode.MaxRune; r++ {
		delta := int(mapping(rune(r))) - r
		if delta == 0 {
			continue
		}
		if n := len(out); n > 0 && out[n-1].delta == delta {
			last := &out[n-1]
			gap := r - last.end
			if last.start == last.end && gap <= 2 {
				last.stride, last.end = gap, r
				continue
			}
			if gap == last.stride {
				last.end = r
				continue
			}
		}
		out = append(out, span{r, r, 1, delta})
	}
	return out
}

func main() {
	fmt.Printf("{\n \"go\": %q,\n \"unicode\": %q", runtime.Version(), unicode.Version)
	for _, table := range []struct {
		name    string
		mapping func(rune) rune
	}{{"upper", unicode.ToUpper}, {"lower", unicode.ToLower}, {"title", unicode.ToTitle}} {
		fmt.Printf(",\n %q: [\n", table.name)
		spans := ranges(table.mapping)
		for i, s := range spans {
			separator := ","
			if i == len(spans)-1 {
				separator = ""
			}
			fmt.Printf("  [%d, %d, %d, %d]%s\n", s.start, s.end, s.stride, s.delta, separator)
		}
		fmt.Print(" ]")
	}
	fmt.Println("\n}")
}
