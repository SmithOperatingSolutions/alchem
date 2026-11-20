//go:build ignore

// Regenerate spec/print-ranges.json from the pinned Go strconv.IsPrint, which the
// pinned Alchem runtime's strconv.Quote uses. Development step only:
// go run scripts/generate-print-ranges.go > spec/print-ranges.json
package main

import (
	"fmt"
	"runtime"
	"strconv"
	"unicode"
)

func main() {
	var ranges [][2]int
	start := -1
	for r := 0x80; r <= 0x110000; r++ {
		printable := r <= unicode.MaxRune && strconv.IsPrint(rune(r))
		if printable && start < 0 {
			start = r
		}
		if !printable && start >= 0 {
			ranges = append(ranges, [2]int{start, r - 1})
			start = -1
		}
	}
	// Inclusive printable ranges above ASCII, one per line.
	fmt.Printf("{\n \"go\": %q,\n \"unicode\": %q,\n \"ranges\": [\n", runtime.Version(), unicode.Version)
	for i, r := range ranges {
		separator := ","
		if i == len(ranges)-1 {
			separator = ""
		}
		fmt.Printf("  [%d, %d]%s\n", r[0], r[1], separator)
	}
	fmt.Println(" ]\n}")
}
