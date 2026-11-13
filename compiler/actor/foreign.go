package actor

import (
	"fmt"
	"runtime"
	"time"
)

// Go may call an Alchem function it was given, a callback or a method of an
// interface Alchem implements, at any time and from any goroutine. Alchem
// code runs in a process, so each such call needs one:
//
//   - While the process that gave Go the function waits in a Go call, it
//     lends its context out: one call at a time may take it and run there,
//     as the process. This is how a callback Go makes during the call runs,
//     at the cost of one atomic operation.
//   - Any other call, made while the context is taken, while the process
//     runs Alchem code, or after it has left the Go call, runs in a new
//     process spawned under it, as each request of HTTP.serve does.
//
// A failure in the process's own goroutine fails the process, as any
// failure there does; elsewhere it is returned to Go as a failure message.

const (
	leaseHeld int32 = iota // the process is using its context
	leaseFree              // the process waits in a Go call
	leaseLent              // a call from Go is running in the context
)

// Lend makes the process's context available to calls from Go while it waits
// in a Go call, and returns the function that takes it back, waiting for a
// call running in it to finish. Lends nest: a call from Go that itself calls
// Go lends the context again and gets it back afterwards.
func Lend(c *Context) func() {
	cold := c.cold()
	if cold.goroutine.Load() == 0 {
		cold.goroutine.Store(currentGoroutine())
	}
	previous := cold.lease.Swap(leaseFree)
	return func() {
		for wait := time.Microsecond; !cold.lease.CompareAndSwap(leaseFree, previous); {
			time.Sleep(wait)
			if wait < time.Millisecond {
				wait *= 2
			}
		}
	}
}

// CallIn runs body, a call from Go into an Alchem function of owner, in
// owner's context when it is lent out and in a new process otherwise. It
// reports the failure of a call that did not run in owner's goroutine; a
// failure there fails owner, as it would without Go in between.
func CallIn(owner *Context, body func(*Context)) (failure string, failed bool) {
	cold := owner.cold()
	if !cold.lease.CompareAndSwap(leaseFree, leaseLent) {
		return callApart(owner, body)
	}
	depth, handled := owner.depth, owner.handled
	defer func() {
		v := recover()
		if v == nil {
			cold.lease.Store(leaseFree)
			return
		}
		if currentGoroutine() == cold.goroutine.Load() {
			cold.lease.Store(leaseFree)
			panic(v)
		}
		// Another goroutine borrowed the context: undo what the failed call
		// left in it before handing it back.
		owner.depth, owner.handled = depth, handled
		cold.lease.Store(leaseFree)
		failure, _ = recovered(v)
		failed = true
	}()
	body(owner)
	return "", false
}

// callApart runs body in a new process and waits for it. The process is not
// linked to owner: its failure is reported to Go instead.
func callApart(owner *Context, body func(*Context)) (failure string, failed bool) {
	const ended = "the Alchem process that made this function has ended"
	r := owner.rt
	r.mu.Lock()
	if r.closing || owner.stopping || owner.ended {
		r.mu.Unlock()
		return ended, true
	}
	child := &Context{}
	r.register(child, nil)
	child.mailbox = &PID[struct{}]{task: child, capacity: 1}
	r.mu.Unlock()
	done := make(chan string, 1)
	go func() {
		reason := "normal"
		var f *Failure
		defer func() {
			if v := recover(); v != nil {
				reason, f = recovered(v)
				done <- reason
			}
			child.finish(reason, f)
		}()
		Check(child)
		body(child)
		done <- ""
	}()
	message := <-done
	return message, message != ""
}

// currentGoroutine is the goroutine's number, read from its stack header.
// It is slow, so it is used only to record a process's goroutine once and
// on the failure path.
func currentGoroutine() uint64 {
	var buf [32]byte
	n := runtime.Stack(buf[:], false)
	var id uint64
	for _, c := range buf[len("goroutine "):n] {
		if c < '0' || c > '9' {
			break
		}
		id = id*10 + uint64(c-'0')
	}
	return id
}

// GoFailure is the Go error a failed call from Go becomes.
func GoFailure(message string) error {
	return fmt.Errorf("alchem: %s", message)
}
