// Go ceiling for benchmarks/alchem/suite/map_set.alc, using built-in maps
// mutated in place. Cases that start from an existing map clone it first,
// because the Alchem and Elixir versions leave their input untouched.
package main

import (
	"maps"
	"strconv"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

type set = map[int]struct{}

func key(i int) int { return (i*7919 + 13) % 1000003 }

func build(n int) map[int]int {
	out := map[int]int{}
	for i := 1; i <= n; i++ {
		out[key(i)] = i
	}
	return out
}

func buildText(n int) map[string]int {
	out := map[string]int{}
	for i := 1; i <= n; i++ {
		out["k"+strconv.Itoa(i)] = i
	}
	return out
}

func main() {
	const n = 100000
	table := build(n)
	text := buildText(n)
	shifted := map[int]int{}
	for i := 50001; i <= 150000; i++ {
		shifted[key(i)] = i * 2
	}
	type entry struct{ key, value int }
	entries := make([]entry, n)
	for i := 1; i <= n; i++ {
		entries[i-1] = entry{key(i), i}
	}
	numbers := make([]int, 1000000)
	for i := range numbers {
		numbers[i] = ((i+1)*7919 + 13) % 250007
	}
	evens, threes := set{}, set{}
	for i := 1; i <= n; i++ {
		evens[i*2] = struct{}{}
		threes[i*3] = struct{}{}
	}

	bench.Run("map.put build integer keys 1k", func() int { return len(build(1000)) })
	bench.Run("map.put build integer keys 100k", func() int { return len(build(n)) })
	bench.Run("map.put build integer keys 1M", func() int { return len(build(1000000)) })
	bench.Run("map.put build string keys 100k", func() int { return len(buildText(n)) })
	bench.Run("map.new from 100k pairs", func() int {
		out := make(map[int]int, len(entries))
		for _, e := range entries {
			out[e.key] = e.value
		}
		return len(out)
	})
	bench.Run("map.get hit integer keys 100k", func() int {
		sum := 0
		for i := 1; i <= n; i++ {
			sum += table[key(i)]
		}
		return sum
	})
	bench.Run("map.get miss integer keys 100k", func() int {
		sum := 0
		for i := 1; i <= n; i++ {
			if value, ok := table[-i]; ok {
				sum += value
			} else {
				sum++
			}
		}
		return sum
	})
	bench.Run("map.fetch! string keys 100k", func() int {
		sum := 0
		for i := 1; i <= n; i++ {
			sum += text["k"+strconv.Itoa(i)]
		}
		return sum
	})
	bench.Run("map.has_key? 100k", func() int {
		sum := 0
		for i := 1; i <= n; i++ {
			if _, ok := table[i]; ok {
				sum++
			}
		}
		return sum
	})
	bench.Run("map.update 1M counters over 1000 keys", func() int {
		counts := map[int]int{}
		for i := 1; i <= 1000000; i++ {
			counts[i%1000]++
		}
		return counts[7]
	})
	bench.Run("map.update existing 100k keys", func() int {
		out := maps.Clone(table)
		for i := 1; i <= n; i++ {
			out[key(i)]++
		}
		return len(out)
	})
	bench.Run("map.merge 100k with 100k", func() int {
		out := maps.Clone(table)
		maps.Copy(out, shifted)
		return len(out)
	})
	bench.Run("map.delete 100k keys", func() int {
		out := maps.Clone(table)
		for i := 1; i <= n; i++ {
			delete(out, key(i))
		}
		return len(out)
	})
	bench.Run("map.to_list 100k", func() int {
		out := make([]entry, 0, len(table))
		for k, v := range table {
			out = append(out, entry{k, v})
		}
		return len(out)
	})
	bench.Run("map.keys 100k", func() int {
		sum := 0
		for k := range table {
			sum += k
		}
		return sum
	})
	bench.Run("map.values 100k", func() int {
		sum := 0
		for _, v := range table {
			sum += v
		}
		return sum
	})
	bench.Run("map.filter 100k", func() int {
		out := map[int]int{}
		for k, v := range table {
			if v%2 == 0 {
				out[k] = v
			}
		}
		return len(out)
	})
	bench.Run("mapset.new from 1M integers", func() int {
		out := set{}
		for _, x := range numbers {
			out[x] = struct{}{}
		}
		return len(out)
	})
	bench.Run("mapset.put 100k", func() int {
		out := set{}
		for i := 1; i <= n; i++ {
			out[key(i)] = struct{}{}
		}
		return len(out)
	})
	bench.Run("mapset.member? 200k", func() int {
		sum := 0
		for i := 1; i <= 200000; i++ {
			if _, ok := evens[i]; ok {
				sum++
			}
		}
		return sum
	})
	bench.Run("mapset.union 100k with 100k", func() int {
		out := maps.Clone(evens)
		maps.Copy(out, threes)
		return len(out)
	})
	bench.Run("mapset.intersection 100k with 100k", func() int {
		out := set{}
		for x := range evens {
			if _, ok := threes[x]; ok {
				out[x] = struct{}{}
			}
		}
		return len(out)
	})
	bench.Run("mapset.difference 100k with 100k", func() int {
		out := set{}
		for x := range evens {
			if _, ok := threes[x]; !ok {
				out[x] = struct{}{}
			}
		}
		return len(out)
	})
}
