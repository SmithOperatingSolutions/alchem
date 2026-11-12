// Package actor implements Alchem's local, cooperatively cancellable process runtime.
package actor

import (
	"fmt"
	"io"
	"os"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type Event struct {
	Ref, PID int64
	Reason   string
}

// Failure records where a process failed. The call stack is captured as raw
// program counters, which is cheap; turning them into source frames is left
// until something asks to see them, because a supervised worker that crashes
// and is restarted usually never has its frames read.
type Failure struct {
	Where, Message string
	// Raised is the exception value of a failure raised with one.
	Raised  any
	Frames  []string
	pcs     []uintptr
	names   map[string]string
	resolve sync.Once
}

// frames resolves the captured stack into Alchem source frames once.
func (f *Failure) frames() []string {
	f.resolve.Do(func() {
		if len(f.pcs) == 0 {
			return
		}
		frames := runtime.CallersFrames(f.pcs)
		for {
			frame, more := frames.Next()
			if strings.HasSuffix(frame.File, ".alc") {
				// Go reports an instantiated generic function as "name[...]".
				function := strings.ReplaceAll(frame.Function, "[...]", "")
				name, best := function, ""
				for generated, source := range f.names {
					if (function == generated || strings.HasPrefix(function, generated+".")) && len(generated) > len(best) {
						best = generated
						name = source
					}
				}
				if best != "" && best != function {
					name += " <closure>"
				}
				f.Frames = append(f.Frames, fmt.Sprintf("%s (%s:%d)", name, frame.File, frame.Line))
			}
			if !more {
				break
			}
		}
		f.pcs = nil
	})
	return f.Frames
}

func (f *Failure) Error() string { return f.Where + ": " + f.Message }

type exit struct {
	reason  string
	failure *Failure
}
type Runtime struct {
	mu   sync.Mutex
	next int64
	// root is the main process, and exitCode the status System.stop asked
	// the program to end with, or -1.
	root     *Context
	exitCode atomic.Int64
	// live is an intrusive list of every process that has not ended, so
	// registering and removing one is a few pointer writes with no hashing.
	live    *Context
	changed chan struct{}
	closing bool
	names   map[string]string
	// maxDepth is fixed before any process starts and read without the lock.
	maxDepth int64
	// observers counts supervisors waiting on changed; with none, wake is a
	// no-op and ordinary processes pay nothing for it.
	observers int
	// registered holds the processes that have been given names.
	registered map[string]Registered
	// extensions are per-program state kept by packages built on this one,
	// and atClose are run when the program ends.
	extensions map[string]any
	atClose    []func()
}
type Context struct {
	// untyped marks a process started without a message type, such as a
	// task, whose first Process.self may still choose one.
	untyped bool
	// serving is the server this process runs, for Server.self.
	serving any
	// continued holds the requests a handler asked to handle next, with
	// Server.continue, ahead of any waiting in the mailbox.
	continued []any
	// remoteLinks are the links to processes of other programs, by their
	// handles, so that Unlink can end one.
	remoteLinks           any
	rt                    *Runtime
	id                    int64
	stop, done            chan struct{}
	stopping, ended, trap bool
	finishing             bool
	reason, stopReason    string
	failure, stopFailure  *Failure
	mailbox               any
	watchers              map[int64]*Context
	// distant are told the exit reason on behalf of processes of other
	// nodes that monitor this one.
	distant  []func(reason string)
	monitors map[int64]*Context
	links    map[int64]*Context
	owned    map[int64]*Context
	parent   *Context
	events   []Event
	notify   chan struct{}
	// depth counts active Alchem calls; only the owning goroutine touches it.
	depth int64
	// handled counts the enclosing try blocks that rescue every failure.
	handled int64
	// joined is the string this process last built with <>.
	joined joined
	// limit is the deepest call allowed. Cancellation lowers it below zero,
	// so one comparison on entry covers both the depth limit and a stop.
	limit atomic.Int64
	// previous and following link the runtime's list of live processes.
	previous, following *Context
	// stopped mirrors stopping so the per-statement cancellation check is one
	// atomic load instead of a trip through the runtime lock.
	stopped atomic.Bool
	// finished is set after reason and failure are final, so a joiner that
	// sees it can read them without the lock or a channel.
	finished atomic.Bool
	// wake holds at most one token meaning "re-check what you are waiting
	// for". Senders, receivers freeing space and cancellation all post to it;
	// only the owning goroutine takes from it, and always re-checks after.
	wake chan struct{}
}

func (c *Context) signal() {
	select {
	case c.wake <- struct{}{}:
	default:
	}
}

var closedSignal = func() chan struct{} { ch := make(chan struct{}); close(ch); return ch }()

// stopSignal and doneSignal return channels for the less frequent waits that
// still select. They are created on first use; most processes are never
// joined through a channel or caught blocking in a select.
func (c *Context) stopSignal() <-chan struct{} {
	if c.stopped.Load() {
		return closedSignal
	}
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	return c.stopLocked()
}
func (c *Context) stopLocked() <-chan struct{} {
	if c.stopping {
		return closedSignal
	}
	if c.stop == nil {
		c.stop = make(chan struct{})
	}
	return c.stop
}
func (c *Context) doneSignal() <-chan struct{} {
	if c.finished.Load() {
		return closedSignal
	}
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	if c.ended {
		return closedSignal
	}
	if c.done == nil {
		c.done = make(chan struct{})
	}
	return c.done
}

// PID is a process capability and its bounded FIFO mailbox. The mailbox is a
// ring buffer under its own small lock rather than a Go channel, so a receive
// with no deadline parks on a single channel instead of a multi-way select,
// and the buffer grows on demand up to the declared capacity.
type PID[T any] struct {
	// remote is set on a handle to a process of another node, which has no
	// mailbox here: sending to it goes over the connection.
	remote   *Remote[T]
	task     *Context
	mu       sync.Mutex
	buf      []T
	head     int
	count    int
	capacity int
	// waiters are senders parked until the mailbox has room or its owner stops.
	waiters []*Context
}

func (*PID[T]) capability() {}

// push appends a message; the caller holds p.mu and has checked for room.
func (p *PID[T]) push(value T) {
	if p.count == len(p.buf) {
		size := 2 * len(p.buf)
		if size == 0 {
			size = 1
		}
		if size > p.capacity {
			size = p.capacity
		}
		grown := make([]T, size)
		for i := 0; i < p.count; i++ {
			grown[i] = p.buf[(p.head+i)%len(p.buf)]
		}
		p.buf, p.head = grown, 0
	}
	p.buf[(p.head+p.count)%len(p.buf)] = value
	p.count++
}

// pop removes the oldest message; the caller holds p.mu and has checked count.
func (p *PID[T]) pop() T {
	var zero T
	value := p.buf[p.head]
	p.buf[p.head] = zero
	p.head = (p.head + 1) % len(p.buf)
	p.count--
	return value
}

// takeWaiters detaches the parked senders; the caller holds p.mu.
func (p *PID[T]) takeWaiters() []*Context {
	waiters := p.waiters
	p.waiters = nil
	return waiters
}
func (p *PID[T]) forget(c *Context) {
	kept := p.waiters[:0]
	for _, waiter := range p.waiters {
		if waiter != c {
			kept = append(kept, waiter)
		}
	}
	p.waiters = kept
}

// release wakes every parked sender once the owner has been told to stop.
func (p *PID[T]) release() {
	p.mu.Lock()
	waiters := p.takeWaiters()
	p.mu.Unlock()
	for _, waiter := range waiters {
		waiter.signal()
	}
}
func (p *PID[T]) discard() {
	p.mu.Lock()
	p.buf, p.head, p.count = nil, 0, 0
	waiters := p.takeWaiters()
	p.mu.Unlock()
	for _, waiter := range waiters {
		waiter.signal()
	}
}
func NewRoot() *Context {
	r := &Runtime{changed: make(chan struct{}), names: map[string]string{}, maxDepth: DefaultMaxCallDepth}
	r.exitCode.Store(-1)
	r.mu.Lock()
	c := r.newTask(nil)
	r.root = c
	r.mu.Unlock()
	return c
}

// StopProgram ends the program with a status, as System.stop does: the main
// process is stopped, as if it had returned, and the runtime then shuts the
// other processes down in the usual way before the program exits.
func StopProgram(c *Context, status int64) {
	r := c.rt
	r.exitCode.CompareAndSwap(-1, status)
	r.mu.Lock()
	r.root.cancel("shutdown", nil)
	r.mu.Unlock()
	Check(c)
}
func (r *Runtime) newTask(parent *Context) *Context {
	c := &Context{}
	r.register(c, parent)
	return c
}

// register initializes a zero Context in place and adds it to the live list.
// The relationship tables and the event channel are created on first use:
// most processes never monitor, link, own or wait for events.
func (r *Runtime) register(c, parent *Context) {
	r.next++
	c.rt, c.id, c.parent = r, r.next, parent
	c.limit.Store(r.maxDepth)
	c.wake = make(chan struct{}, 1)
	c.following = r.live
	if r.live != nil {
		r.live.previous = c
	}
	r.live = c
	if parent != nil {
		relate(&parent.owned, c.id, c)
	}
}
func (r *Runtime) unregister(c *Context) {
	if c.previous != nil {
		c.previous.following = c.following
	} else if r.live == c {
		r.live = c.following
	}
	if c.following != nil {
		c.following.previous = c.previous
	}
	c.previous, c.following = nil, nil
}

// relate records an entry in a lazily created relationship table.
func relate(table *map[int64]*Context, id int64, c *Context) {
	if *table == nil {
		*table = map[int64]*Context{}
	}
	(*table)[id] = c
}
func (r *Runtime) wake() {
	if r.observers == 0 {
		return
	}
	close(r.changed)
	r.changed = make(chan struct{})
}
func (c *Context) enqueue(e Event) {
	c.events = append(c.events, e)
	select {
	case c.notify <- struct{}{}:
	default:
	}
}
func (c *Context) cancel(reason string, f *Failure) {
	if !c.stopping && !c.ended {
		c.stopping = true
		c.stopReason = reason
		c.stopFailure = f
		c.stopped.Store(true)
		c.limit.Store(-1)
		if c.stop != nil {
			close(c.stop)
		}
		// Unblock the process itself and anyone parked on its mailbox.
		c.signal()
		if box, ok := c.mailbox.(interface{ release() }); ok {
			box.release()
		}
		c.rt.wake()
	}
}
func abnormal(reason string) bool { return reason != "normal" && reason != "shutdown" }
func (c *Context) finish(reason string, f *Failure) {
	r := c.rt
	r.mu.Lock()

	if c.ended || c.finishing {
		r.mu.Unlock()
		return
	}
	c.finishing = true
	if c.stopping && reason == "normal" {
		reason = c.stopReason
		f = c.stopFailure
	}
	c.cancel(reason, f)
	owned := []*Context{}
	for _, child := range c.owned {
		child.cancel("shutdown", nil)
		owned = append(owned, child)
	}
	// Only a process that owns supervisors has anything to join; the common
	// case finishes inside one critical section.
	if len(owned) > 0 {
		r.mu.Unlock()
		for _, child := range owned {
			<-child.doneSignal()
		}
		r.mu.Lock()
	}
	defer r.mu.Unlock()
	c.ended = true
	c.reason = reason
	c.failure = f
	c.finished.Store(true)
	if c.done != nil {
		close(c.done)
	}
	r.unregister(c)
	for ref, observer := range c.watchers {
		delete(observer.monitors, ref)
		if !observer.ended {
			observer.enqueue(Event{ref, c.id, reason})
		}
	}
	for ref, target := range c.monitors {
		delete(target.watchers, ref)
	}
	for _, tell := range c.distant {
		// Writing to a connection must not hold up the runtime's lock.
		go tell(reason)
	}
	c.distant = nil
	c.watchers = nil
	c.monitors = nil
	c.events = nil
	if box, ok := c.mailbox.(interface{ discard() }); ok {
		box.discard()
	}
	c.mailbox = nil
	for id, other := range c.links {
		delete(other.links, c.id)
		if !other.ended {
			if other.trap {
				other.enqueue(Event{0, c.id, reason})
			} else if abnormal(reason) {
				other.cancel("linked: "+reason, f)
			}
		}
		delete(c.links, id)
	}
	for _, child := range c.owned {
		child.cancel("shutdown", nil)
	}
	if c.parent != nil {
		delete(c.parent.owned, c.id)
		c.parent = nil
	}
	r.wake()
}

// DefaultMaxCallDepth keeps runaway recursion a recoverable process failure
// instead of a fatal Go stack overflow that no supervisor can observe.
const DefaultMaxCallDepth = 100000

// Enter records one Alchem function activation.
//
// Enter, Leave and Check run on every call and statement, so each is small
// enough to inline and keeps its failure path in a separate function.
//
// Enter is also the cancellation point for function bodies. Alchem has no
// loop construct: repetition is a call or a runtime operation, and both check
// here or in the runtime, so the straight-line statements in between are
// bounded by the program text and need no check of their own.
func Enter(c *Context, where string) {
	c.depth++
	if c.depth > c.limit.Load() {
		enterSlow(c, where)
	}
}

//go:noinline
func enterSlow(c *Context, where string) {
	Check(c)
	Fail(c, where, "call depth exceeded")
}

// Leave ends an activation and passes the function's result through, so
// generated code writes "return actor.Leave(ctx, value)" instead of deferring.
// A failure unwinds without restoring depth, which is safe because a failure
// always ends the process.
func Leave[T any](c *Context, value T) T {
	c.depth--
	return value
}
func Check(c *Context) {
	if c.stopped.Load() {
		c.exitNow()
	}
}

//go:noinline
func (c *Context) exitNow() {
	c.rt.mu.Lock()
	reason, f := c.stopReason, c.stopFailure
	c.rt.mu.Unlock()
	panic(exit{reason, f})
}
func Fail(c *Context, where, message string) {
	// names is fixed before the entry function runs, so it is read unlocked.
	f := &Failure{Where: where, Message: message, names: c.rt.names}
	if c.handled == 0 {
		var pcs [64]uintptr
		f.pcs = append(f.pcs, pcs[:runtime.Callers(2, pcs[:])]...)
	}
	panic(f)
}
func foreign[T any](c *Context, p *PID[T], where string) {
	if p != nil && p.remote != nil {
		Fail(c, where, "this needs a process of this node; a process of another node can only be sent to")
	}
	if p == nil || p.task.rt != c.rt {
		Fail(c, where, "invalid or foreign PID")
	}
}
func Self[T any](c *Context, capacity int64, where string) *PID[T] {
	Check(c)
	if capacity < 1 || capacity > 1000000 {
		Fail(c, where, "mailbox capacity must be 1..1000000")
	}
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	if c.mailbox != nil {
		if p, ok := c.mailbox.(*PID[T]); ok {
			return p
		}
		if c.untyped {
			// A task or test has no mailbox of its own yet: its first
			// Process.self chooses the message type.
			c.untyped = false
			p := &PID[T]{task: c, capacity: int(capacity)}
			c.mailbox = p
			return p
		}
		panic(&Failure{Where: where, Message: "process mailbox type already fixed"})
	}
	p := &PID[T]{task: c, capacity: int(capacity)}
	c.mailbox = p
	return p
}
func Spawn[T any](c *Context, fn func(*Context, *PID[T]) int64, capacity int64, where string) *PID[T] {
	Check(c)
	if capacity < 1 || capacity > 1000000 {
		Fail(c, where, "mailbox capacity must be 1..1000000")
	}
	r := c.rt
	r.mu.Lock()
	if r.closing || c.stopping {
		r.mu.Unlock()
		Check(c)
		Fail(c, where, "runtime shutting down")
	}
	// The process record and its mailbox share one allocation.
	cell := &struct {
		task Context
		pid  PID[T]
	}{}
	child, p := &cell.task, &cell.pid
	r.register(child, nil)
	p.task, p.capacity = child, int(capacity)
	child.mailbox = p
	r.mu.Unlock()
	go func() {
		reason := "normal"
		var failure *Failure
		defer func() {
			if v := recover(); v != nil {
				reason, failure = recovered(v)
			}
			child.finish(reason, failure)
		}()
		Check(child)
		if code := fn(child, p); code != 0 {
			reason = fmt.Sprintf("exit:%d", code)
		}
	}()
	return p
}
func recovered(v any) (string, *Failure) {
	switch e := v.(type) {
	case *Failure:
		reason := e.Message
		if reason == "normal" || reason == "shutdown" {
			reason = "error: " + reason
		}
		return reason, e
	case exit:
		return e.reason, e.failure
	case Thrown:
		f := &Failure{Where: e.Where, Message: "uncaught throw"}
		return f.Message, f
	default:
		f := &Failure{Where: "<runtime>", Message: fmt.Sprintf("panic: %v", v)}
		return f.Message, f
	}
}
func deadline(ms int64) (<-chan time.Time, func()) {
	if ms < 0 {
		return nil, func() {}
	}
	if ms > int64((1<<63-1)/int64(time.Millisecond)) {
		ms = int64((1<<63 - 1) / int64(time.Millisecond))
	}
	t := time.NewTimer(time.Duration(ms) * time.Millisecond)
	return t.C, func() { t.Stop() }
}

// park blocks the calling process until its wake token arrives or the timer
// fires, and reports whether the timer fired. A nil timer means no deadline,
// which makes this a plain channel receive.
func (c *Context) park(timer <-chan time.Time) bool {
	if timer == nil {
		<-c.wake
		return false
	}
	select {
	case <-c.wake:
		return false
	case <-timer:
		return true
	}
}

// ReceiveMatching takes the oldest message that match accepts, leaving the
// others in the mailbox in their order, and waits up to ms milliseconds for
// one to arrive. Only the owner removes messages, so the position of a
// message it has looked at does not change while match runs outside the lock.
func ReceiveMatching[T any](c *Context, p *PID[T], ms int64, match func(*Context, T) bool, where string) Received[T] {
	Check(c)
	foreign(c, p, where)
	if p.task != c {
		Fail(c, where, "only the mailbox owner may receive")
	}
	var timer <-chan time.Time
	var stop func()
	seen := 0
	for {
		p.mu.Lock()
		if seen < p.count {
			value := p.buf[(p.head+seen)%len(p.buf)]
			p.mu.Unlock()
			if !match(c, value) {
				seen++
				continue
			}
			p.mu.Lock()
			var zero T
			for i := seen; i < p.count-1; i++ {
				p.buf[(p.head+i)%len(p.buf)] = p.buf[(p.head+i+1)%len(p.buf)]
			}
			p.buf[(p.head+p.count-1)%len(p.buf)] = zero
			p.count--
			waiters := p.takeWaiters()
			p.mu.Unlock()
			for _, waiter := range waiters {
				waiter.signal()
			}
			return Received[T]{true, value}
		}
		p.mu.Unlock()
		if ms == 0 {
			return Received[T]{}
		}
		if timer == nil && ms > 0 {
			timer, stop = deadline(ms)
			defer stop()
		}
		if c.park(timer) {
			return Received[T]{}
		}
		Check(c)
	}
}

// Stopping is closed when the process has been asked to stop, for work
// outside the runtime that must be abandoned then.
func Stopping(c *Context) <-chan struct{} { return c.stopSignal() }

// Pending returns the messages waiting in a mailbox, oldest first, without
// removing them.
func Pending[T any](p *PID[T]) []T {
	p.mu.Lock()
	defer p.mu.Unlock()
	out := make([]T, p.count)
	for i := range out {
		out[i] = p.buf[(p.head+i)%len(p.buf)]
	}
	return out
}

// Send delivers value to p's mailbox. Alchem values are immutable (every
// collection operation builds a new value), so the message is shared rather
// than copied; neither side can observe the difference.
func Send[T any](c *Context, p *PID[T], value T, ms int64, where string) bool {
	Check(c)
	if p != nil && p.remote != nil {
		return p.remote.Send(value)
	}
	foreign(c, p, where)
	target := p.task
	var timer <-chan time.Time
	var stop func()
	for {
		p.mu.Lock()
		// stopped is set before the mailbox is released or discarded, so
		// checking it under the mailbox lock can never strand a sender.
		if target.stopped.Load() {
			p.forget(c)
			p.mu.Unlock()
			return false
		}
		if p.count < p.capacity {
			p.push(value)
			p.forget(c)
			p.mu.Unlock()
			target.signal()
			return true
		}
		if ms == 0 {
			p.mu.Unlock()
			return false
		}
		p.forget(c)
		p.waiters = append(p.waiters, c)
		p.mu.Unlock()
		if timer == nil && ms > 0 {
			timer, stop = deadline(ms)
			defer stop()
		}
		expired := c.park(timer)
		if expired || c.stopped.Load() {
			p.mu.Lock()
			p.forget(c)
			p.mu.Unlock()
			Check(c)
			return false
		}
	}
}

type Received[T any] struct {
	E0 bool
	E1 T
}

func Receive[T any](c *Context, p *PID[T], ms int64, where string) Received[T] {
	Check(c)
	foreign(c, p, where)
	if p.task != c {
		Fail(c, where, "only the mailbox owner may receive")
	}
	var timer <-chan time.Time
	var stop func()
	for {
		p.mu.Lock()
		if p.count > 0 {
			value := p.pop()
			waiters := p.takeWaiters()
			p.mu.Unlock()
			for _, waiter := range waiters {
				waiter.signal()
			}
			return Received[T]{true, value}
		}
		p.mu.Unlock()
		if ms == 0 {
			return Received[T]{}
		}
		if timer == nil && ms > 0 {
			timer, stop = deadline(ms)
			defer stop()
		}
		if c.park(timer) {
			return Received[T]{}
		}
		Check(c)
	}
}

type Result struct {
	E0 bool
	E1 string
}

func Await[T any](c *Context, p *PID[T], ms int64, where string) Result {
	Check(c)
	foreign(c, p, where)
	if p.task == c {
		Fail(c, where, "cannot await self")
	}
	return wait(c, p.task, ms)
}
func wait(c, target *Context, ms int64) Result {
	// reason is written once, before done is closed, so observing the close
	// is enough to read it without the runtime lock.
	if target.finished.Load() {
		return Result{true, target.reason}
	}
	timer, stop := deadline(ms)
	defer stop()
	select {
	case <-target.doneSignal():
		return Result{true, target.reason}
	case <-c.stopSignal():
		Check(c)
	case <-timer:
	}
	return Result{}
}
func Stop[T any](c *Context, p *PID[T], where string) bool {
	Check(c)
	foreign(c, p, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	ok := !p.task.ended && !p.task.stopping
	p.task.cancel("shutdown", nil)
	return ok
}
func Alive[T any](c *Context, p *PID[T], where string) bool {
	Check(c)
	if p != nil && p.remote != nil {
		// All that can be known from here is whether its node is reachable.
		return p.remote.Alive()
	}
	foreign(c, p, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	return !p.task.ended && !p.task.stopping
}
func ID[T any](c *Context, p *PID[T], where string) int64 {
	if p != nil && p.remote != nil {
		return p.remote.ID
	}
	foreign(c, p, where)
	return p.task.id
}
func Sleep(c *Context, ms int64, where string) int64 {
	Check(c)
	if ms < 0 {
		Fail(c, where, "sleep duration must be nonnegative")
	}
	if ms == 0 {
		// A zero-length sleep yields the processor to other processes, which
		// is what a polling loop needs between attempts.
		runtime.Gosched()
		Check(c)
		return 0
	}
	timer, stop := deadline(ms)
	defer stop()
	select {
	case <-timer:
	case <-c.stopSignal():
		Check(c)
	}
	return 0
}
func Crash(c *Context, reason, where string) int64 { Fail(c, where, reason); return 0 }
func Monitor[T any](c *Context, p *PID[T], where string) int64 {
	Check(c)
	if p != nil && p.remote != nil {
		return p.remote.Monitor(c)
	}
	foreign(c, p, where)
	r := c.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	r.next++
	ref := r.next
	if p.task.ended {
		c.enqueue(Event{ref, p.task.id, p.task.reason})
	} else {
		relate(&p.task.watchers, ref, c)
		relate(&c.monitors, ref, p.task)
	}
	return ref
}
func Demonitor[T any](c *Context, p *PID[T], ref int64, where string) bool {
	Check(c)
	removed := false
	id := int64(0)
	if p != nil && p.remote != nil {
		// The other node may still report the exit; without an entry here
		// the report is ignored.
		id = p.remote.ID
		removed = p.remote.Demonitor(ref)
	} else {
		foreign(c, p, where)
		id = p.task.id
	}
	r := c.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	if p.remote == nil && c.monitors[ref] == p.task {
		delete(c.monitors, ref)
		delete(p.task.watchers, ref)
		removed = true
	}
	events := c.events[:0]
	for _, e := range c.events {
		if e.Ref == ref && e.PID == id {
			removed = true
		} else {
			events = append(events, e)
		}
	}
	c.events = events
	return removed
}
func Trap(c *Context, value bool) bool {
	Check(c)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	old := c.trap
	c.trap = value
	return old
}
func Link[T any](c *Context, p *PID[T], where string) bool {
	Check(c)
	if p != nil && p.remote != nil {
		return linkRemote(c, p)
	}
	foreign(c, p, where)
	r := c.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	if p.task == c {
		return false
	}
	if p.task.ended {
		if c.trap {
			c.enqueue(Event{0, p.task.id, p.task.reason})
		} else if abnormal(p.task.reason) {
			c.cancel("linked: "+p.task.reason, p.task.failure)
		}
		return false
	}
	relate(&c.links, p.task.id, p.task)
	relate(&p.task.links, c.id, c)
	return true
}
func Unlink[T any](c *Context, p *PID[T], where string) bool {
	Check(c)
	if p != nil && p.remote != nil {
		return unlinkRemote(c, p)
	}
	foreign(c, p, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	_, ok := c.links[p.task.id]
	delete(c.links, p.task.id)
	delete(p.task.links, c.id)
	return ok
}

type Notification struct {
	E0     bool
	E1, E2 int64
	E3     string
}

func NextEvent(c *Context, ms int64) Notification {
	Check(c)
	timer, stop := deadline(ms)
	defer stop()
	for {
		c.rt.mu.Lock()
		if c.notify == nil {
			// Created under the lock that guards enqueue, before the check
			// below, so no event can slip between the two.
			c.notify = make(chan struct{}, 1)
		}
		notify := c.notify
		if len(c.events) > 0 {
			e := c.events[0]
			c.events = c.events[1:]
			c.rt.mu.Unlock()
			return Notification{true, e.Ref, e.PID, e.Reason}
		}
		c.rt.mu.Unlock()
		if ms == 0 {
			return Notification{}
		}
		select {
		case <-notify:
		case <-c.stopSignal():
			Check(c)
		case <-timer:
			return Notification{}
		}
	}
}
func Report[T any](c *Context, p *PID[T], where string) string {
	foreign(c, p, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	if p.task.failure != nil {
		return render(p.task.failure, true)
	}
	return p.task.reason
}
func render(f *Failure, trace bool) string {
	out := f.Error()
	if trace {
		for _, frame := range f.frames() {
			out += "\n  at " + frame
		}
	}
	return out
}
func Close(c *Context, ms int64) bool {
	r := c.rt
	r.mu.Lock()
	r.closing = true
	atClose := r.atClose
	r.atClose = nil
	r.mu.Unlock()
	for _, each := range atClose {
		each()
	}
	r.mu.Lock()
	var tasks []*Context
	for t := r.live; t != nil; t = t.following {
		if t != c {
			t.cancel("shutdown", nil)
			tasks = append(tasks, t)
		}
	}
	r.mu.Unlock()
	timer, stop := deadline(ms)
	defer stop()
	for _, t := range tasks {
		select {
		case <-t.doneSignal():
		case <-timer:
			return false
		}
	}
	return true
}
func Run(fn func(*Context), names map[string]string, trace bool, shutdownMS, maxDepth int64) (code int) {
	c := NewRoot()
	c.rt.names = names
	if maxDepth > 0 {
		c.rt.maxDepth = maxDepth
		c.limit.Store(maxDepth)
	}
	var failure *Failure
	defer func() {
		if v := recover(); v != nil {
			reason, f := recovered(v)
			failure = f
			if abnormal(reason) {
				code = 2
				if failure == nil {
					failure = &Failure{Where: "<runtime>", Message: reason}
				}
			}
		}
		closed := Close(c, shutdownMS)
		if !closed {
			code = 2
			fmt.Fprintln(os.Stderr, "<runtime>: shutdown deadline exceeded")
		}
		if failure != nil {
			fmt.Fprintln(os.Stderr, render(failure, trace))
		}
		// finish joins owned supervisors without a deadline. After a missed
		// deadline that join could block forever, so the caller exits instead.
		if closed {
			c.finish("normal", nil)
		}
		if stopped := c.rt.exitCode.Load(); stopped >= 0 && code == 0 {
			code = int(stopped)
		}
	}()
	fn(c)
	return 0
}

// WriteFailure renders a structured failure without exposing generated Go paths.
func WriteFailure(w io.Writer, f *Failure, trace bool) { fmt.Fprintln(w, render(f, trace)) }

// Loop threads immutable state through fresh callback activations without
// retaining an actor's message history on the Go call stack.
func Loop[S any](c *Context, state S, fn func(*Context, S) struct {
	E0 bool
	E1 S
}, where string) S {
	Check(c)
	for {
		Check(c)
		next := fn(c, state)
		state = next.E1
		if !next.E0 {
			return state
		}
	}
}
