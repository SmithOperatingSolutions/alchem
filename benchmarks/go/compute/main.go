// Command compute is the Go baseline for benchmarks/alchem/compute.alc:
// recursive fib(32), then the sum of squares of 1..1,000,000 through an
// intermediate list.
package main

import (
	"fmt"
	"os"
	"time"
)

func fib(n int64) int64 {
	if n < 2 {
		return n
	}
	return fib(n-1) + fib(n-2)
}

func main() {
	started := time.Now()
	if fib(32) != 2178309 {
		panic("fib")
	}
	recursed := phase("fib", started)
	numbers := make([]int64, 1000000)
	for i := range numbers {
		numbers[i] = int64(i + 1)
	}
	squares := make([]int64, len(numbers))
	for i, n := range numbers {
		squares[i] = n * n
	}
	var total int64
	for _, n := range squares {
		total += n
	}
	if total != 333333833333500000 {
		panic("sum")
	}
	phase("squares", recursed)
	fmt.Println("computed")
}

// phase writes how long a phase took, in microseconds, to standard error.
func phase(name string, since time.Time) time.Time {
	now := time.Now()
	fmt.Fprintf(os.Stderr, "phase %s %d\n", name, now.Sub(since).Microseconds())
	return now
}
