// Go ceiling for benchmarks/alchem/suite/otp.alc. The server is a goroutine
// that owns a counter and answers over channels; the agent is a value behind
// a mutex, which is how Go shares state; a task is a goroutine with a result
// channel.
package main

import (
	"sync"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

type request struct {
	reply  chan int
	amount int
}

// serve owns a total and adds every request to it, replying when asked to.
func serve(requests chan request) {
	total := 0
	for r := range requests {
		total += r.amount
		if r.reply != nil {
			r.reply <- total
		}
	}
}

func fib(n int) int {
	if n < 2 {
		return n
	}
	return fib(n-1) + fib(n-2)
}

// heavy computes 1,000 results with at most limit goroutines at a time and
// adds them in input order.
func heavy(limit int) int {
	results := make([]int, 1000)
	slots := make(chan struct{}, limit)
	var group sync.WaitGroup
	for i := range results {
		slots <- struct{}{}
		group.Go(func() {
			results[i] = fib(22) + i + 1
			<-slots
		})
	}
	group.Wait()
	total := 0
	for _, value := range results {
		total += value
	}
	return total
}

func main() {
	bench.Run("server.call 200k", func() int {
		requests, reply := make(chan request, 1024), make(chan int, 1)
		go serve(requests)
		total := 0
		for i := 0; i < 200000; i++ {
			requests <- request{reply, 1}
			total += <-reply
		}
		close(requests)
		return total
	})
	bench.Run("server.call 8 clients, 25k calls each", func() int {
		requests := make(chan request, 1024)
		go serve(requests)
		best := make([]int, 8)
		var group sync.WaitGroup
		for client := range best {
			group.Go(func() {
				reply := make(chan int, 1)
				for i := 0; i < 25000; i++ {
					requests <- request{reply, 1}
					best[client] = max(best[client], <-reply)
				}
			})
		}
		group.Wait()
		close(requests)
		total := 0
		for _, value := range best {
			total = max(total, value)
		}
		return total
	})
	bench.Run("server.cast 200k then one call", func() int {
		requests, reply := make(chan request, 1024), make(chan int, 1)
		go serve(requests)
		for i := 0; i < 200000; i++ {
			requests <- request{nil, 1}
		}
		requests <- request{reply, 0}
		total := <-reply
		close(requests)
		return total + 200000
	})
	bench.Run("agent.get 200k", func() int {
		var lock sync.Mutex
		state, total := 7, 0
		for i := 0; i < 200000; i++ {
			lock.Lock()
			total += state
			lock.Unlock()
		}
		return total
	})
	bench.Run("agent.update 200k then get", func() int {
		var lock sync.Mutex
		state := 0
		for i := 0; i < 200000; i++ {
			lock.Lock()
			state++
			lock.Unlock()
		}
		return state
	})
	bench.Run("agent.get_and_update 200k", func() int {
		var lock sync.Mutex
		state, total := 0, 0
		for i := 0; i < 200000; i++ {
			lock.Lock()
			total += state
			state++
			lock.Unlock()
		}
		return total
	})
	bench.Run("task.async and await 100k, one at a time", func() int {
		total := 0
		for i := 1; i <= 100000; i++ {
			result := make(chan int, 1)
			go func() { result <- i * 2 }()
			total += <-result
		}
		return total
	})
	bench.Run("task.async 10k at once, await_many", func() int {
		results := make([]chan int, 10000)
		for i := range results {
			result := make(chan int, 1)
			results[i] = result
			go func() { result <- fib(15) + i + 1 }()
		}
		total := 0
		for _, result := range results {
			total += <-result
		}
		return total
	})
	bench.Run("task.async_stream 100k trivial items", func() int {
		results := make([]int, 100000)
		slots := make(chan struct{}, 14)
		var group sync.WaitGroup
		for i := range results {
			slots <- struct{}{}
			group.Go(func() {
				results[i] = (i + 1) * 2
				<-slots
			})
		}
		group.Wait()
		total := 0
		for _, value := range results {
			total += value
		}
		return total
	})
	bench.Run("serial 1,000 x fib(22)", func() int {
		total := 0
		for i := 1; i <= 1000; i++ {
			total += fib(22) + i
		}
		return total
	})
	bench.Run("task.async_stream 1,000 x fib(22), limit 1", func() int { return heavy(1) })
	bench.Run("task.async_stream 1,000 x fib(22), limit 2", func() int { return heavy(2) })
	bench.Run("task.async_stream 1,000 x fib(22), limit 4", func() int { return heavy(4) })
	bench.Run("task.async_stream 1,000 x fib(22), limit 8", func() int { return heavy(8) })
	bench.Run("task.async_stream 1,000 x fib(22), limit 14", func() int { return heavy(14) })
}
