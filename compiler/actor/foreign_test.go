package actor

import (
	"strings"
	"sync"
	"sync/atomic"
	"testing"
)

// Calls from Go goroutines while a process waits in Go take turns in its
// context or run in processes of their own, so the context is never used by
// two at once; failures are reported and leave the context as it was.
func TestCallsFromGoShareTheLentContext(t *testing.T) {
	c := root(t)
	const callers = 64
	var inside, borrowed, apart atomic.Int64
	result := make(chan string, 1)
	Spawn(c, func(owner *Context, _ *PID[struct{}]) int64 {
		depth := owner.depth
		give := Lend(owner)
		var wg sync.WaitGroup
		var failures atomic.Int64
		for i := 0; i < callers; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				message, failed := CallIn(owner, func(ctx *Context) {
					if ctx == owner {
						if inside.Add(1) > 1 {
							t.Error("two calls ran in the owner's context at once")
						}
						defer inside.Add(-1)
						borrowed.Add(1)
					} else {
						apart.Add(1)
					}
					// Calls change what a function call would change.
					Enter(ctx, "test")
					ctx.handled++
					if i%4 == 0 {
						Fail(ctx, "test", "refused")
					}
					ctx.handled--
					Leave(ctx, 0)
				})
				if failed {
					if message != "refused" {
						t.Errorf("failure message %q", message)
					}
					failures.Add(1)
				}
			}()
		}
		wg.Wait()
		give()
		if owner.depth != depth || owner.handled != 0 {
			result <- "the context was left changed"
		} else if failures.Load() != callers/4 {
			result <- "wrong number of failures"
		} else {
			result <- ""
		}
		return 0
	}, 1, "test")
	if problem := <-result; problem != "" {
		t.Fatal(problem)
	}
	if borrowed.Load()+apart.Load() != callers {
		t.Fatalf("borrowed %d, apart %d", borrowed.Load(), apart.Load())
	}
}

// A call made while the process runs its own code, or after it has ended,
// does not touch its context.
func TestCallsFromGoOutsideALend(t *testing.T) {
	c := root(t)
	owners := make(chan *Context, 1)
	release := make(chan struct{})
	owner := Spawn(c, func(self *Context, _ *PID[struct{}]) int64 {
		owners <- self
		<-release
		return 0
	}, 1, "test")
	ctx := <-owners
	ran := make(chan *Context, 1)
	if _, failed := CallIn(ctx, func(c *Context) { ran <- c }); failed {
		t.Fatal("a call while the owner runs failed")
	}
	if <-ran == ctx {
		t.Fatal("a call ran in the context of a running process")
	}
	close(release)
	Await(c, owner, -1, "test")
	message, failed := CallIn(ctx, func(*Context) { t.Error("a call ran after its process ended") })
	if !failed || !strings.Contains(message, "has ended") {
		t.Fatalf("failed=%v message=%q", failed, message)
	}
}

// A failure of a call Go makes on the process's own goroutine, during the
// extern, fails the process as it would without Go in between.
func TestCallFromGoOnTheOwnGoroutineFailsTheProcess(t *testing.T) {
	c := root(t)
	p := Spawn(c, func(owner *Context, _ *PID[struct{}]) int64 {
		defer Lend(owner)()
		CallIn(owner, func(ctx *Context) { Fail(ctx, "test", "inside") })
		return 0
	}, 1, "test")
	if ended := Await(c, p, -1, "test"); ended.E1 != "inside" {
		t.Fatalf("ended with %q", ended.E1)
	}
}

// The cost of a callback Go makes during the extern that received it.
func BenchmarkCallInLent(b *testing.B) {
	c := root(b)
	done := make(chan struct{})
	Spawn(c, func(owner *Context, _ *PID[struct{}]) int64 {
		defer close(done)
		defer Lend(owner)()
		var n int64
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			CallIn(owner, func(*Context) { n++ })
		}
		return n & 0
	}, 1, "test")
	<-done
}
