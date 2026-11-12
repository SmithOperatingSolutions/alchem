// Go ceiling for benchmarks/alchem/suite/list.alc, using slices. Cases that
// change an existing list clone it once first, because the Alchem and Elixir
// versions leave their input untouched, and then edit the copy in place.
package main

import (
	"slices"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

func at(i int) int { return i * 37 % 10000 }

func sum(xs []int) int {
	total := 0
	for _, x := range xs {
		total += x
	}
	return total
}

func main() {
	items := make([]int, 10000)
	for i := range items {
		items[i] = ((i+1)*7919 + 13) % 1000003
	}
	big := make([]int, 100000)
	for i := range big {
		big[i] = ((i+1)*7919 + 13) % 1000003
	}
	short := items[:5000]
	chunk := make([]int, 1000)
	for i := range chunk {
		chunk[i] = i + 1
	}
	nested := make([][]int, 1000)
	for i := range nested {
		nested[i] = make([]int, 100)
		for j := range nested[i] {
			nested[i][j] = i + 1 + j
		}
	}
	var removed []int
	for i := 0; i < len(items); i += 10 {
		removed = append(removed, items[i])
	}

	bench.Run("list.at 2,000 reads of 10k", func() int {
		total := 0
		for i := 1; i <= 2000; i++ {
			total += items[at(i)]
		}
		return total
	})
	bench.Run("list.replace_at 1,000 of 10k", func() int {
		out := slices.Clone(items)
		for i := 1; i <= 1000; i++ {
			out[at(i)] = i
		}
		return sum(out)
	})
	bench.Run("list.update_at 1,000 of 10k", func() int {
		out := slices.Clone(items)
		for i := 1; i <= 1000; i++ {
			out[at(i)]++
		}
		return sum(out)
	})
	bench.Run("list.insert_at 1,000 into 10k", func() int {
		out := slices.Clone(items)
		for i := 1; i <= 1000; i++ {
			out = slices.Insert(out, at(i), i)
		}
		return sum(out)
	})
	bench.Run("list.delete_at 1,000 of 10k", func() int {
		out := slices.Clone(items)
		for i := 1; i <= 1000; i++ {
			at := i * 37 % 9000
			out = slices.Delete(out, at, at+1)
		}
		return sum(out)
	})
	bench.Run("list.delete value 1,000 of 10k", func() int {
		out := slices.Clone(items)
		for _, x := range removed {
			if at := slices.Index(out, x); at >= 0 {
				out = slices.Delete(out, at, at+1)
			}
		}
		return len(out)
	})
	bench.Run("list.last 1,000 times of 100k", func() int {
		total := 0
		for i := 0; i < 1000; i++ {
			total += big[len(big)-1]
		}
		return total
	})
	bench.Run("list.length 1,000 times of 100k", func() int {
		total := 0
		for i := 0; i < 1000; i++ {
			total += len(big)
		}
		return total
	})
	bench.Run("list ++ append 1k to growing list 200 times", func() int {
		var out []int
		for i := 0; i < 200; i++ {
			out = append(out, chunk...)
		}
		return len(out)
	})
	bench.Run("list ++ prepend 1k to growing list 200 times", func() int {
		var out []int
		for i := 0; i < 200; i++ {
			out = slices.Concat(chunk, out)
		}
		return len(out)
	})
	bench.Run("list -- 1,000 from 10k", func() int {
		out := slices.Clone(items)
		for _, x := range removed {
			if at := slices.Index(out, x); at >= 0 {
				out = slices.Delete(out, at, at+1)
			}
		}
		return len(out)
	})
	bench.Run("list.flatten 1,000 lists of 100", func() int {
		return len(slices.Concat(nested...))
	})
	bench.Run("list prepend build 1M", func() int {
		// Appending and reading from the end is how Go builds a stack.
		var out []int
		for i := 1; i <= 1000000; i++ {
			out = append(out, i)
		}
		return out[len(out)-1]
	})
	bench.Run("list head/tail recursive walk 5k, 20 times", func() int {
		total := 0
		for i := 0; i < 20; i++ {
			total += sum(short)
		}
		return total
	})
	bench.Run("list.foldr 100k", func() int {
		acc := 0
		for i := len(big) - 1; i >= 0; i-- {
			acc = (acc*31 + big[i]) % 1000000007
		}
		return acc
	})
	bench.Run("list.duplicate 1M", func() int {
		return slices.Repeat([]int{7}, 1000000)[0]
	})
	bench.Run("list in (membership) 1,000 misses of 10k", func() int {
		count := 0
		for i := 1; i <= 1000; i++ {
			if slices.Contains(items, -i) {
				count++
			}
		}
		return count
	})
}
