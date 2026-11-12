// Command spawn is the Go baseline for benchmarks/alchem/spawn.alc: it keeps
// 100,000 goroutines alive at once, each blocked on a one-slot mailbox.
package main

import (
	"fmt"
	"os"
	"sync"
	"time"
)

const processes = 100000

func main() {
	started := time.Now()
	mailboxes := make([]chan int64, processes)
	var done sync.WaitGroup
	done.Add(processes)
	for i := range mailboxes {
		mailbox := make(chan int64, 1)
		mailboxes[i] = mailbox
		go func() {
			defer done.Done()
			<-mailbox
		}()
	}
	spawned := phase("spawn", started)
	for _, mailbox := range mailboxes {
		mailbox <- 1
	}
	done.Wait()
	phase("release and join", spawned)
	fmt.Println("spawned", processes)
}

// phase writes how long a phase took, in microseconds, to standard error.
func phase(name string, since time.Time) time.Time {
	now := time.Now()
	fmt.Fprintf(os.Stderr, "phase %s %d\n", name, now.Sub(since).Microseconds())
	return now
}
