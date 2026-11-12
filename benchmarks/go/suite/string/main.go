// Go ceiling for benchmarks/alchem/suite/string.alc, using strings, unicode/utf8
// and regexp directly.
package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

func line(i int) string {
	return fmt.Sprintf("2026-11-10 12:00:%d host%d GET /api/items/%d %d %dms", i%60, i%17, i, 200+i%7*50, i*31%997)
}

// slice returns count code points of text starting at code point start.
func slice(text string, start, count int) string {
	from, seen := len(text), 0
	for at := range text {
		if seen == start {
			from = at
		}
		if seen == start+count {
			return text[from:at]
		}
		seen++
	}
	return text[from:]
}

func main() {
	words := make([]string, 200000)
	padded := make([]string, len(words))
	for i := range words {
		words[i] = "w" + strconv.Itoa((i+1)*7919%100003)
		padded[i] = "  " + words[i] + "\t "
	}
	text := strings.Join(words, " ")
	accented := strings.Repeat("naïve café 日本語 Straße ", 10000)
	long := strings.Repeat("abcdefghij", 100)
	lines := make([]string, 100000)
	for i := range lines {
		lines[i] = line(i + 1)
	}
	few := lines[:10000]
	serverError := regexp.MustCompile(` 5\d\d `)
	request := regexp.MustCompile(`GET (\S+) (\d+)`)
	named := regexp.MustCompile(`host(?P<host>\d+) GET (?P<path>\S+)`)
	digits := regexp.MustCompile(`\d+`)
	separators := regexp.MustCompile(`[ /:]+`)

	bench.Run("string <> append 1 byte 20k times", func() int {
		var out strings.Builder
		for i := 0; i < 20000; i++ {
			out.WriteString("x")
		}
		return len(out.String())
	})
	bench.Run("string interpolation 200k", func() int {
		acc := 0
		for i := 1; i <= 200000; i++ {
			acc += len("item " + strconv.Itoa(i) + " of " + strconv.Itoa(acc))
		}
		return acc
	})
	bench.Run("string.split on space 1.4 MB", func() int { return len(strings.Split(text, " ")) })
	bench.Run("string.split whitespace 1.4 MB", func() int { return len(strings.Fields(text)) })
	bench.Run("string.replace 1.4 MB", func() int { return len(strings.ReplaceAll(text, "w1", "W-")) })
	bench.Run("string.contains? 200k words", func() int {
		count := 0
		for _, word := range words {
			if strings.Contains(word, "99") {
				count++
			}
		}
		return count
	})
	bench.Run("string.starts_with? 200k words", func() int {
		count := 0
		for _, word := range words {
			if strings.HasPrefix(word, "w12") {
				count++
			}
		}
		return count
	})
	bench.Run("string.upcase ASCII 1.4 MB", func() int { return len(strings.ToUpper(text)) })
	bench.Run("string.downcase ASCII 1.4 MB", func() int { return len(strings.ToLower(text)) })
	bench.Run("string.upcase non-ASCII 310 KB", func() int { return len(strings.ToUpper(accented)) })
	bench.Run("string.trim 200k words", func() int {
		total := 0
		for _, word := range padded {
			total += len(strings.TrimSpace(word))
		}
		return total
	})
	bench.Run("string.length ASCII 1.4 MB", func() int { return utf8.RuneCountInString(text) })
	bench.Run("string.length non-ASCII 310 KB", func() int { return utf8.RuneCountInString(accented) })
	bench.Run("string.slice 100k from the middle of 1,000 characters", func() int {
		total := 0
		for i := 1; i <= 100000; i++ {
			total += len(slice(long, 400+i%100, 20))
		}
		return total
	})
	codepoints := func() int {
		out := make([]string, 0, len(accented))
		for _, r := range accented {
			out = append(out, string(r))
		}
		return len(out)
	}
	// The Go standard library has no grapheme segmentation; this text has no
	// combining sequences, so code points give the same answer.
	bench.Run("string.graphemes non-ASCII 310 KB", codepoints)
	bench.Run("string.codepoints non-ASCII 310 KB", codepoints)
	bench.Run("string.reverse ASCII 1.4 MB", func() int {
		runes := []rune(text)
		for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
			runes[i], runes[j] = runes[j], runes[i]
		}
		return len(string(runes))
	})
	bench.Run("string.pad_leading 200k words", func() int {
		total := 0
		for _, word := range words {
			if missing := 12 - utf8.RuneCountInString(word); missing > 0 {
				word = strings.Repeat("0", missing) + word
			}
			total += len(word)
		}
		return total
	})
	bench.Run("string == and < compare 200k words", func() int {
		total := 0
		for i := 0; i+1 < len(words); i++ {
			if words[i] < words[i+1] {
				total++
			}
			if words[i] == words[i+1] {
				total++
			}
		}
		return total
	})
	bench.Run("regex.match? 100k lines", func() int {
		count := 0
		for _, entry := range lines {
			if serverError.MatchString(entry) {
				count++
			}
		}
		return count
	})
	bench.Run("regex.run with captures 100k lines", func() int {
		total := 0
		for _, entry := range lines {
			if found := request.FindStringSubmatch(entry); found != nil {
				status, _ := strconv.Atoi(found[2])
				total += status
			}
		}
		return total
	})
	bench.Run("regex.named_captures 100k lines", func() int {
		total := 0
		path := named.SubexpIndex("path")
		for _, entry := range lines {
			if found := named.FindStringSubmatch(entry); found != nil {
				total += len(found[path])
			}
		}
		return total
	})
	bench.Run("regex.scan 10k lines", func() int {
		total := 0
		for _, entry := range few {
			total += len(digits.FindAllString(entry, -1))
		}
		return total
	})
	bench.Run("regex.replace 10k lines", func() int {
		total := 0
		for _, entry := range few {
			total += len(digits.ReplaceAllString(entry, "N"))
		}
		return total
	})
	bench.Run("regex.split 10k lines", func() int {
		total := 0
		for _, entry := range few {
			total += len(separators.Split(entry, -1))
		}
		return total
	})
}
