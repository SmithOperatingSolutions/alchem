// Command restart is the Go baseline for benchmarks/alchem/restart.alc: a
// hand-written supervisor restarts a worker 20,000 times. Each cycle crashes
// the worker, waits for its replacement and completes one round trip with it.
package main

import (
	"fmt"
	"os"
	"runtime"
	"sort"
	"sync/atomic"
	"time"
)

const restarts = 20000

type request struct {
	reply chan int64
	value int64
}

type worker struct {
	requests chan request
	done     chan struct{}
}

// supervise keeps one worker running, replacing it whenever it panics.
func supervise(current *atomic.Pointer[worker], stop chan struct{}) {
	for {
		w := &worker{make(chan request, 1), make(chan struct{})}
		current.Store(w)
		go func() {
			defer close(w.done)
			defer func() { _ = recover() }()
			for message := range w.requests {
				if message.value < 0 {
					panic("requested")
				}
				message.reply <- message.value
			}
		}()
		select {
		case <-w.done:
		case <-stop:
			close(w.requests)
			return
		}
	}
}

func main() {
	var current atomic.Pointer[worker]
	stop := make(chan struct{})
	go supervise(&current, stop)
	for current.Load() == nil {
		runtime.Gosched()
	}
	replies := make(chan int64, 1)
	started := time.Now()
	durations := make([]int64, 0, restarts)
	for done := int64(0); done < restarts; done++ {
		since := time.Now()
		doomed := current.Load()
		doomed.requests <- request{replies, -1}
		<-doomed.done
		for current.Load() == doomed {
			runtime.Gosched()
		}
		current.Load().requests <- request{replies, done}
		if reply := <-replies; reply != done {
			panic("unexpected reply")
		}
		durations = append(durations, time.Since(since).Microseconds())
	}
	phase("cycles", started)
	latency("restart (us)", durations)
	close(stop)
	fmt.Println("restarted", restarts)
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
