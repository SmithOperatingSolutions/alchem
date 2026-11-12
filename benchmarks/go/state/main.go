// Command state is the Go baseline for benchmarks/alchem/state.alc: build a
// 50,000-entry map one key at a time, sum it in key order, then update 1,000
// counters 50,000 times. Go's idiomatic map is mutable, so it updates in place.
package main

import (
	"fmt"
	"os"
	"sort"
	"time"
)

func main() {
	started := time.Now()
	counts := map[int64]int64{}
	for n := int64(1); n <= 50000; n++ {
		counts[n] += n
	}
	if len(counts) != 50000 || counts[50000] != 50000 {
		panic("build")
	}
	built := phase("build", started)
	keys := make([]int64, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool { return keys[i] < keys[j] })
	var total int64
	for _, key := range keys {
		total += counts[key]
	}
	if total != 1250025000 {
		panic("sum")
	}
	summed := phase("sum", built)
	buckets := map[int64]int64{}
	for n := int64(1); n <= 50000; n++ {
		buckets[n%1000]++
	}
	if len(buckets) != 1000 || buckets[0] != 50 {
		panic("buckets")
	}
	phase("update", summed)
	fmt.Println("state kept")
}

// phase writes how long a phase took, in microseconds, to standard error.
func phase(name string, since time.Time) time.Time {
	now := time.Now()
	fmt.Fprintf(os.Stderr, "phase %s %d\n", name, now.Sub(since).Microseconds())
	return now
}
