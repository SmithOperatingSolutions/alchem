// Command build is the Go baseline for benchmarks/alchem/build.alc: grow a
// 50,000-element sequence one element at a time, then walk and sum it. Go's
// idiomatic growth is append, so the sequence is stored newest-last.
package main

import (
	"fmt"
	"os"
	"time"
)

func count(xs []int64, seen int64) int64 {
	if len(xs) == 0 {
		return seen
	}
	return count(xs[:len(xs)-1], seen+1)
}

func main() {
	started := time.Now()
	var items []int64
	for n := int64(1); n <= 50000; n++ {
		items = append(items, n)
	}
	grown := phase("grow", started)
	if items[len(items)-1] != 50000 || count(items, 0) != 50000 {
		panic("build")
	}
	var total int64
	for _, n := range items {
		total += n
	}
	if total != 1250025000 {
		panic("sum")
	}
	phase("walk", grown)
	fmt.Println("built")
}

// phase writes how long a phase took, in microseconds, to standard error.
func phase(name string, since time.Time) time.Time {
	now := time.Now()
	fmt.Fprintf(os.Stderr, "phase %s %d\n", name, now.Sub(since).Microseconds())
	return now
}
