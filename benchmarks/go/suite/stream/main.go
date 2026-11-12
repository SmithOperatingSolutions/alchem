// Go ceiling for benchmarks/alchem/suite/stream.alc. Lazy pipelines become
// single loops, and files are read through bufio.
package main

import (
	"bufio"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

// field returns the comma-separated field at index without splitting the
// whole line.
func field(line string, index int) string {
	for ; index > 0; index-- {
		_, line, _ = strings.Cut(line, ",")
	}
	found, _, _ := strings.Cut(line, ",")
	return found
}

func value(line string) int {
	n, _ := strconv.Atoi(field(line, 2))
	return n
}

// eachLine calls visit with every line of the file, without its line ending.
func eachLine(path string, visit func(string)) {
	file, err := os.Open(path)
	if err != nil {
		panic(err)
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		visit(scanner.Text())
	}
}

func main() {
	inputs := os.Args[1]
	lines := filepath.Join(inputs, "lines.txt")
	head := filepath.Join(inputs, "head.txt")
	const n = 1000000
	numbers := make([]int, n)
	for i := range numbers {
		numbers[i] = ((i+1)*7919 + 13) % 1000003
	}

	mapFilterSum := func() int {
		sum := 0
		for _, x := range numbers {
			if y := x * 3; y%2 == 0 {
				sum += y
			}
		}
		return sum
	}
	bench.Run("stream map filter sum 1M", mapFilterSum)
	bench.Run("eager map filter sum 1M", mapFilterSum)
	take := func() int {
		sum, taken := 0, 0
		for _, x := range numbers {
			if y := x * 3; y%2 == 0 {
				sum += y
				if taken++; taken == 1000 {
					break
				}
			}
		}
		return sum
	}
	bench.Run("stream map filter take 1,000 of 1M", take)
	bench.Run("eager map filter take 1,000 of 1M", take)
	chunks := func() int {
		best := 0
		for at := 0; at < len(numbers); at += 100 {
			sum := 0
			for _, x := range numbers[at:min(at+100, len(numbers))] {
				sum += x
			}
			best = max(best, sum)
		}
		return best
	}
	bench.Run("stream chunk_every 100 then sum 1M", chunks)
	bench.Run("eager chunk_every 100 then sum 1M", chunks)
	bench.Run("stream range map filter sum 1M", func() int {
		sum := 0
		for x := 1; x <= n; x++ {
			if y := x * 3; y%2 == 0 {
				sum += y
			}
		}
		return sum
	})
	bench.Run("stream.iterate take 1M", func() int {
		sum, x := 0, 1
		for i := 0; i < n; i++ {
			sum += x
			x = (x*31 + 7) % 1000003
		}
		return sum
	})
	bench.Run("stream.unfold 1M", func() int {
		sum := 0
		for x := 1; x <= n; x++ {
			sum += x * 2
		}
		return sum
	})
	bench.Run("stream.with_index 1M", func() int {
		sum := 0
		for index, x := range numbers {
			sum += x + index
		}
		return sum
	})
	bench.Run("stream.flat_map 200k", func() int {
		sum := 0
		for x := 1; x <= 200000; x++ {
			sum += x + x + 1
		}
		return sum
	})
	bench.Run("stream.scan 1M", func() int {
		acc, best := 0, 0
		for _, x := range numbers {
			acc = (acc + x) % 1000003
			best = max(best, acc)
		}
		return best
	})
	bench.Run("stream.zip 1M", func() int {
		best := 0
		for i, x := range numbers {
			best = max(best, x*(i+1))
		}
		return best
	})
	bench.Run("file.stream! count lines 1M (64 MiB)", func() int {
		count := 0
		eachLine(lines, func(string) { count++ })
		return count
	})
	bench.Run("file.stream! parse and sum a column 1M", func() int {
		sum := 0
		eachLine(lines, func(line string) { sum += value(line) })
		return sum
	})
	bench.Run("file.stream! word frequencies 1M", func() int {
		counts := map[string]int{}
		eachLine(lines, func(line string) { counts[field(line, 1)]++ })
		return len(counts)
	})
	bench.Run("file.stream! filter then chunk_every 1,000", func() int {
		total := 0
		var chunk []string
		eachLine(lines, func(line string) {
			if strings.Contains(line, ",w12") {
				if chunk = append(chunk, line); len(chunk) == 1000 {
					total += len(chunk)
					chunk = chunk[:0]
				}
			}
		})
		return total + len(chunk)
	})
	bench.Run("file.stream! 64 KiB chunks (64 MiB)", func() int {
		file, err := os.Open(lines)
		if err != nil {
			panic(err)
		}
		defer file.Close()
		total := 0
		buffer := make([]byte, 65536)
		for {
			read, err := io.ReadFull(file, buffer)
			total += read
			if err != nil {
				return total
			}
		}
	})
	bench.Run("file.stream! sum a column 120k (8 MiB)", func() int {
		sum := 0
		eachLine(head, func(line string) { sum += value(line) })
		return sum
	})
	bench.Run("file.read! split sum a column 120k (8 MiB)", func() int {
		data, err := os.ReadFile(head)
		if err != nil {
			panic(err)
		}
		sum := 0
		for _, line := range strings.Split(string(data), "\n") {
			if line != "" {
				sum += value(line)
			}
		}
		return sum
	})
}
