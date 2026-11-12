// Go ceiling for benchmarks/alchem/suite/enum.alc: the same results computed
// with slices and built-in maps, mutated in place.
package main

import (
	"cmp"
	"slices"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

type pair struct{ left, right int }

func main() {
	const n = 1000000
	numbers := make([]int, n)
	others := make([]int, n)
	for i := 1; i <= n; i++ {
		numbers[i-1] = (i*7919 + 13) % 1000003
		others[i-1] = (i*104729 + 7) % 1000003
	}
	small := numbers[:200000]
	words := make([]string, 200000)
	for i := 1; i <= 200000; i++ {
		words[i-1] = "w" + strconv.Itoa(i*7919%100003)
	}
	pairs := make([]pair, n)
	for i := range numbers {
		pairs[i] = pair{numbers[i], others[i]}
	}
	table := make(map[int]int, 100000)
	for i := 1; i <= 100000; i++ {
		table[i] = i * 7919 % 1009
	}

	bench.Run("enum.map list 1M", func() int {
		out := make([]int, len(numbers))
		for i, x := range numbers {
			out[i] = x*2 + 1
		}
		return out[0]
	})
	bench.Run("enum.filter list 1M", func() int {
		var out []int
		for _, x := range numbers {
			if x%3 == 0 {
				out = append(out, x)
			}
		}
		return out[0]
	})
	bench.Run("enum.reduce list 1M", func() int {
		acc := 0
		for _, x := range numbers {
			acc = (acc + x*3) % 1000000007
		}
		return acc
	})
	bench.Run("enum.sum list 1M", func() int {
		sum := 0
		for _, x := range numbers {
			sum += x
		}
		return sum
	})
	bench.Run("enum.count predicate list 1M", func() int {
		count := 0
		for _, x := range numbers {
			if x%7 == 0 {
				count++
			}
		}
		return count
	})
	bench.Run("enum.map range 1M", func() int {
		out := make([]int, n)
		for x := 1; x <= n; x++ {
			out[x-1] = x*2 + 1
		}
		return out[0]
	})
	bench.Run("enum.filter range 1M", func() int {
		var out []int
		for x := 1; x <= n; x++ {
			if x%3 == 0 {
				out = append(out, x)
			}
		}
		return out[0]
	})
	bench.Run("enum.reduce range 1M", func() int {
		acc := 0
		for x := 1; x <= n; x++ {
			acc = (acc + x*3) % 1000000007
		}
		return acc
	})
	bench.Run("enum.map map 100k", func() int {
		out := make([]int, 0, len(table))
		for key, value := range table {
			out = append(out, key+value)
		}
		sum := 0
		for _, x := range out {
			sum += x
		}
		return sum
	})
	bench.Run("enum.filter map 100k", func() int {
		var out []pair
		for key, value := range table {
			if value < 500 {
				out = append(out, pair{key, value})
			}
		}
		return len(out)
	})
	bench.Run("enum.reduce map 100k", func() int {
		acc := 0
		for key, value := range table {
			acc += key * value
		}
		return acc
	})
	bench.Run("enum.sort integers 1M", func() int {
		out := slices.Clone(numbers)
		slices.Sort(out)
		return out[0]
	})
	bench.Run("enum.sort strings 200k", func() int {
		out := slices.Clone(words)
		slices.Sort(out)
		return len(out[0])
	})
	bench.Run("enum.sort_by 200k", func() int {
		out := slices.Clone(small)
		slices.SortStableFunc(out, func(a, b int) int { return cmp.Compare(a%1000, b%1000) })
		return out[0]
	})
	bench.Run("enum.group_by 1M into 1000", func() int {
		groups := map[int][]int{}
		for _, x := range numbers {
			groups[x%1000] = append(groups[x%1000], x)
		}
		return len(groups)
	})
	bench.Run("enum.frequencies strings 200k", func() int {
		counts := map[string]int{}
		for _, word := range words {
			counts[word]++
		}
		return len(counts)
	})
	bench.Run("enum.chunk_every 1M by 100", func() int {
		chunks := make([][]int, 0, len(numbers)/100)
		for chunk := range slices.Chunk(numbers, 100) {
			chunks = append(chunks, slices.Clone(chunk))
		}
		return len(chunks)
	})
	bench.Run("enum.uniq 1M", func() int {
		seen := map[int]struct{}{}
		var out []int
		for _, x := range numbers {
			if _, ok := seen[x]; !ok {
				seen[x] = struct{}{}
				out = append(out, x)
			}
		}
		return len(out)
	})
	bench.Run("enum.zip 1M", func() int {
		out := make([]pair, len(numbers))
		for i := range numbers {
			out[i] = pair{numbers[i], others[i]}
		}
		return out[0].left + out[0].right
	})
	bench.Run("enum.unzip 1M", func() int {
		left := make([]int, len(pairs))
		right := make([]int, len(pairs))
		for i, p := range pairs {
			left[i], right[i] = p.left, p.right
		}
		return left[0] + right[0]
	})
	bench.Run("enum.with_index 1M", func() int {
		out := make([]pair, len(numbers))
		for i, x := range numbers {
			out[i] = pair{x, i}
		}
		return out[0].left + out[0].right
	})
	bench.Run("enum.flat_map 200k", func() int {
		out := make([]int, 0, 2*len(small))
		for _, x := range small {
			out = append(out, x, x+1)
		}
		return len(out)
	})
	bench.Run("enum.member? miss 1M", func() int {
		if slices.Contains(numbers, -1) {
			return 1
		}
		return 0
	})
	bench.Run("enum.join strings 200k", func() int {
		return len(strings.Join(words, ","))
	})
	bench.Run("enum.map_join integers 200k", func() int {
		var out strings.Builder
		for i, x := range small {
			if i > 0 {
				out.WriteByte(',')
			}
			out.WriteString(strconv.Itoa(x + 1))
		}
		return out.Len()
	})
	bench.Run("enum.min_max 1M", func() int {
		return slices.Min(numbers) + slices.Max(numbers)
	})
	bench.Run("enum.reverse 1M", func() int {
		out := slices.Clone(numbers)
		slices.Reverse(out)
		return out[0]
	})
	bench.Run("enum.slice middle 500k of 1M", func() int {
		return slices.Clone(numbers[250000:750000])[0]
	})
	bench.Run("enum.at last of 1M", func() int {
		return numbers[n-1]
	})
	bench.Run("enum.concat 1M + 1M", func() int {
		return slices.Concat(numbers, others)[0]
	})
}
