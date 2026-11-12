package actor

import (
	"sync/atomic"
	"time"
)

// This file is what a package built on the runtime needs in order to reach
// processes from outside it, as the node package does for other programs.
// Nothing here opens a connection, so a program that stays on its own does
// not carry any of that.

// Remote is how a handle reaches a process of another program. Send copies a
// message to it; Monitor and Demonitor ask to be told of its exit; Alive
// reports whether it can be reached at all.
type Remote[T any] struct {
	Node      string
	ID        int64
	Send      func(T) bool
	Monitor   func(*Context) int64
	Demonitor func(ref int64) bool
	Alive     func() bool
	// Exit tells the process that one linked to it ended for a reason.
	Exit func(reason string) bool
}

// ExitLinked passes on to a process of this program the exit of a process
// of another that was linked to it: an abnormal one ends it, unless it traps
// exits, when it is told instead.
func ExitLinked[T any](p *PID[T], from int64, reason string) {
	r := p.task.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	if p.task.ended {
		return
	}
	if p.task.trap {
		p.task.enqueue(Event{0, from, reason})
	} else if abnormal(reason) {
		p.task.cancel("linked: "+reason, nil)
	}
}

// linkRemote links a process to one of another program: each is told of
// the other's exit. The other's is learned through a monitor, kept by a
// helper process that ends with the link.
func linkRemote[T any](c *Context, p *PID[T]) bool {
	remote := p.remote
	if remote.Exit == nil || remote.Monitor == nil {
		return false
	}
	var active atomic.Bool
	active.Store(true)
	c.rt.mu.Lock()
	if c.remoteLinks == nil {
		c.remoteLinks = map[*Remote[T]]*atomic.Bool{}
	}
	c.remoteLinks.(map[*Remote[T]]*atomic.Bool)[remote] = &active
	c.distant = append(c.distant, func(reason string) {
		if active.Load() && abnormal(reason) {
			remote.Exit(reason)
		}
	})
	c.rt.mu.Unlock()
	self := c
	Spawn(c, func(w *Context, _ *PID[struct{}]) int64 {
		remote.Monitor(w)
		for {
			event := NextEvent(w, -1)
			if !event.E0 {
				continue
			}
			if active.Load() {
				r := self.rt
				r.mu.Lock()
				if !self.ended {
					if self.trap {
						self.enqueue(Event{0, remote.ID, event.E3})
					} else if abnormal(event.E3) {
						self.cancel("linked: "+event.E3, nil)
					}
				}
				r.mu.Unlock()
			}
			return 0
		}
	}, 1, "link")
	return true
}

// unlinkRemote ends a link to a process of another program.
func unlinkRemote[T any](c *Context, p *PID[T]) bool {
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	links, _ := c.remoteLinks.(map[*Remote[T]]*atomic.Bool)
	active, ok := links[p.remote]
	if ok {
		active.Store(false)
		delete(links, p.remote)
	}
	return ok
}

// RemotePID makes the handle for a process of another program.
func RemotePID[T any](r *Remote[T]) *PID[T] { return &PID[T]{remote: r} }

// RemoteOf returns what a handle holds about a process of another program,
// or nil for a process of this one.
func RemoteOf[T any](p *PID[T]) *Remote[T] { return p.remote }

// LocalID is the number of a process of this program.
func LocalID[T any](p *PID[T]) int64 { return p.task.id }

// Deliver puts a message in a mailbox on behalf of a sender outside the
// runtime. A full mailbox is waited on for up to patience, then given up on.
func Deliver[T any](p *PID[T], value T, patience time.Duration) bool {
	until := time.Now().Add(patience)
	for {
		p.mu.Lock()
		if p.task.stopped.Load() {
			p.mu.Unlock()
			return false
		}
		if p.count < p.capacity {
			p.push(value)
			p.mu.Unlock()
			p.task.signal()
			return true
		}
		p.mu.Unlock()
		if time.Now().After(until) {
			return false
		}
		time.Sleep(time.Millisecond)
	}
}

// NextReference returns a number no monitor of this program has used.
func NextReference(c *Context) int64 {
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	c.rt.next++
	return c.rt.next
}

// Notify queues an event for a process, unless it has ended.
func Notify(c *Context, e Event) {
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	if !c.ended {
		c.enqueue(e)
	}
}

// WatchExit arranges for tell to be called with a process's exit reason. If
// the process has already ended it reports so, with the reason, instead.
func WatchExit[T any](p *PID[T], tell func(reason string)) (bool, string) {
	r := p.task.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	if p.task.ended {
		return true, p.task.reason
	}
	p.task.distant = append(p.task.distant, tell)
	return false, ""
}

// After returns a channel that fires in ms milliseconds, and its release.
func After(ms int64) (<-chan time.Time, func()) { return deadline(ms) }

// Extension returns the state a package keeps for this program under a key,
// making it on first use.
func Extension(c *Context, key string, make func() any) any {
	r := c.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.extensions == nil {
		r.extensions = map[string]any{}
	}
	if r.extensions[key] == nil && make != nil {
		r.extensions[key] = make()
	}
	return r.extensions[key]
}

// AtClose runs a function when the program ends, before its processes are
// stopped.
func AtClose(c *Context, f func()) {
	c.rt.mu.Lock()
	c.rt.atClose = append(c.rt.atClose, f)
	c.rt.mu.Unlock()
}

// Registered is a process that has been given a name. Kind names its
// message type, and Extra is whatever the registering package needs to
// reach it from outside.
type Registered struct {
	ID    int64
	PID   any
	Kind  string
	Extra any
	task  *Context
}

// RegisterName gives a process of this program a name. A name belongs to
// one living process at a time.
func RegisterName[T any](c *Context, p *PID[T], name, kind string, extra any) bool {
	Check(c)
	if p == nil || p.remote != nil || name == "" {
		return false
	}
	r := c.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	if existing, taken := r.registered[name]; taken && !existing.task.ended {
		return false
	}
	if r.registered == nil {
		r.registered = map[string]Registered{}
	}
	r.registered[name] = Registered{ID: p.task.id, PID: p, Kind: kind, Extra: extra, task: p.task}
	return true
}

// UnregisterName frees a name.
func UnregisterName(c *Context, name string) bool {
	r := c.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	_, known := r.registered[name]
	delete(r.registered, name)
	return known
}

// LookupName finds the living process registered under a name.
func LookupName(c *Context, name string) (Registered, bool) {
	r := c.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	entry, ok := r.registered[name]
	return entry, ok && !entry.task.ended
}

// MailboxOf is a process's mailbox when its messages are of type T.
func MailboxOf[T any](c *Context) (*PID[T], bool) {
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	p, ok := c.mailbox.(*PID[T])
	return p, ok
}

// Ended returns a channel closed when a process of this program has ended.
func Ended[T any](p *PID[T]) <-chan struct{} { return p.task.doneSignal() }

// OnEnd runs a function, in a goroutine of its own, once a process has
// ended; at once if it already has.
func OnEnd(c *Context, f func()) {
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	if c.ended {
		go f()
		return
	}
	c.distant = append(c.distant, func(string) { f() })
}

// ContextOf is the process behind a handle of this program, or nil.
func ContextOf[T any](p *PID[T]) *Context {
	if p == nil || p.remote != nil {
		return nil
	}
	return p.task
}
