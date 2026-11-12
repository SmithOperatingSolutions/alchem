// Go ceiling for benchmarks/alchem/suite/processes.alc: bare goroutines and
// channels, with none of the identity, mailbox or lifecycle bookkeeping an
// Alchem or Erlang process carries.
package main

import (
	"sync"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

type request struct {
	reply chan int
	value int
}

type listRequest struct {
	reply chan int
	items []int
}

func main() {
	payload := make([]int, 10000)
	for i := range payload {
		payload[i] = i + 1
	}

	bench.Run("process spawn and await 100k, one at a time", func() int {
		count := 0
		for i := 0; i < 100000; i++ {
			done := make(chan struct{})
			go func() { close(done) }()
			<-done
			count++
		}
		return count
	})
	bench.Run("process spawn 100k alive at once, release, await", func() int {
		var group sync.WaitGroup
		inboxes := make([]chan int, 100000)
		for i := range inboxes {
			inbox := make(chan int, 1)
			inboxes[i] = inbox
			group.Go(func() { <-inbox })
		}
		for _, inbox := range inboxes {
			inbox <- 1
		}
		group.Wait()
		return len(inboxes)
	})
	bench.Run("process ping-pong 500k round trips", func() int {
		requests, reply, done := make(chan request, 1), make(chan int, 1), make(chan struct{})
		go func() {
			defer close(done)
			for r := range requests {
				r.reply <- r.value
				if r.value < 0 {
					return
				}
			}
		}()
		total := 0
		for i := 1; i <= 500000; i++ {
			requests <- request{reply, i}
			total += <-reply
		}
		requests <- request{reply, -1}
		total += <-reply
		<-done
		return total + 1
	})
	bench.Run("process fan-in 8 senders, 1M messages", func() int {
		inbox := make(chan int, 1024)
		var group sync.WaitGroup
		for s := 0; s < 8; s++ {
			group.Go(func() {
				for i := 1; i <= 125000; i++ {
					inbox <- i
				}
			})
		}
		total := 0
		for i := 0; i < 1000000; i++ {
			total += <-inbox
		}
		group.Wait()
		return total + 8
	})
	bench.Run("process ring 1,000 processes, 1,000 laps", func() int {
		home := make(chan int, 1)
		first := home
		for i := 0; i < 1000; i++ {
			inbox, next := make(chan int, 1), first
			go func() {
				for token := range inbox {
					next <- token
					if token < 0 {
						return
					}
				}
			}()
			first = inbox
		}
		laps := 0
		for lap := 1; lap <= 1000; lap++ {
			first <- lap
			laps += <-home
		}
		first <- -1
		return laps + <-home
	})
	bench.Run("process send a 10k-element list, 10k round trips", func() int {
		requests, reply := make(chan listRequest, 1), make(chan int, 1)
		go func() {
			for r := range requests {
				r.reply <- r.items[0]
				if r.items[0] < 0 {
					return
				}
			}
		}()
		total := 0
		for i := 0; i < 10000; i++ {
			requests <- listRequest{reply, payload}
			total += <-reply
		}
		requests <- listRequest{reply, []int{-1}}
		return total + <-reply
	})
	bench.Run("process mailbox fill 500k then drain", func() int {
		inbox, done := make(chan int, 500000), make(chan struct{})
		go func() {
			for i := 1; i <= 500000; i++ {
				inbox <- i
			}
			close(done)
		}()
		<-done
		total := 1
		for i := 0; i < 500000; i++ {
			total += <-inbox
		}
		return total
	})
}
