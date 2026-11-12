// Command echo is the Go baseline for benchmarks/alchem/echo.alc: 200,000
// request/reply round trips between two goroutines over one-slot channels.
package main

import (
	"fmt"
	"os"
	"sort"
	"time"
)

const roundTrips = 200000

type request struct {
	reply chan int64
	value int64
}

func main() {
	requests := make(chan request, 1)
	replies := make(chan int64, 1)
	go func() {
		for message := range requests {
			message.reply <- message.value
		}
	}()
	started := time.Now()
	durations := make([]int64, 0, roundTrips)
	since := started
	for sent := int64(0); sent < roundTrips; sent++ {
		requests <- request{replies, sent}
		if reply := <-replies; reply != sent {
			panic("unexpected reply")
		}
		now := time.Now()
		durations = append(durations, now.Sub(since).Nanoseconds())
		since = now
	}
	phase("round trips", started)
	latency("round trip (ns)", durations)
	close(requests)
	fmt.Println("round trips", roundTrips)
}

// phase writes how long a phase took, in microseconds, to standard error.
func phase(name string, since time.Time) time.Time {
	now := time.Now()
	fmt.Fprintf(os.Stderr, "phase %s %d\n", name, now.Sub(since).Microseconds())
	return now
}

// latency writes the fastest, median and 99th percentile of durations to
// standard error.
func latency(name string, durations []int64) {
	sort.Slice(durations, func(i, j int) bool { return durations[i] < durations[j] })
	n := len(durations)
	fmt.Fprintf(os.Stderr, "latency %s %d %d %d\n", name, durations[0], durations[n/2], durations[n*99/100])
}
