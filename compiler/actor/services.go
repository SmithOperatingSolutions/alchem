package actor

import (
	"hash/maphash"
	"sync"
	"sync/atomic"
	"time"
)

// This file holds what long-running services are built from besides servers
// themselves: timers, a server's own handle and name, exits that arrive as
// requests, a registry of processes by key, and a supervisor whose children
// are started while it runs.

// timers are the pending Process.send_after and Server.send_after calls of
// one program, by reference.
type timers struct {
	mu      sync.Mutex
	pending map[int64]chan struct{}
}

func timersOf(c *Context) *timers {
	return Extension(c, "timers", func() any { return &timers{pending: map[int64]chan struct{}{}} }).(*timers)
}

// later runs deliver after ms milliseconds unless the timer is cancelled or
// gone, the target ends first, or the program closes.
func later(c *Context, ms int64, gone <-chan struct{}, deliver func()) int64 {
	if ms < 0 {
		ms = 0
	}
	t := timersOf(c)
	ref := NextReference(c)
	cancel := make(chan struct{})
	t.mu.Lock()
	t.pending[ref] = cancel
	t.mu.Unlock()
	go func() {
		timer := time.NewTimer(time.Duration(ms) * time.Millisecond)
		defer timer.Stop()
		select {
		case <-timer.C:
		case <-cancel:
			return
		case <-gone:
		}
		t.mu.Lock()
		_, live := t.pending[ref]
		delete(t.pending, ref)
		t.mu.Unlock()
		if live {
			select {
			case <-gone:
			default:
				deliver()
			}
		}
	}()
	return ref
}

// SendAfter sends a message to a process after ms milliseconds and returns a
// reference that CancelTimer takes. A message to a full mailbox waits up to a
// second for space, then is dropped, as a message to an ended process is.
func SendAfter[T any](c *Context, p *PID[T], value T, ms int64, where string) int64 {
	Check(c)
	if p == nil {
		Fail(c, where, "invalid PID")
	}
	if p.remote != nil {
		remote := p.remote
		return later(c, ms, nil, func() { remote.Send(value) })
	}
	foreign(c, p, where)
	return later(c, ms, p.task.doneSignal(), func() { Deliver(p, value, time.Second) })
}

// SendAfterName sends a message after ms milliseconds to whatever is
// registered under a name then: a process whose messages are of the
// message's type, or a server whose requests are, as a cast. The message is
// dropped when nothing fitting holds the name by then, as Elixir drops a
// message sent to a name nobody has.
func SendAfterName[T any](c *Context, name string, value T, ms int64) int64 {
	Check(c)
	return later(c, ms, nil, func() {
		entry, alive := LookupName(c, name)
		if !alive {
			return
		}
		switch target := entry.PID.(type) {
		case *PID[T]:
			Deliver(target, value, time.Second)
		case interface{ deliverAny(any) }:
			target.deliverAny(value)
		}
	})
}

// deliverAny casts a request given as any, when it is of the server's type.
func (s *Server[Q, R]) deliverAny(value any) {
	if q, ok := value.(Q); ok {
		s.deliver(request[Q, R]{value: q})
	}
}

// CancelTimer stops a timer that has not fired and reports whether it had
// not.
func CancelTimer(c *Context, ref int64) bool {
	t := timersOf(c)
	t.mu.Lock()
	cancel, live := t.pending[ref]
	delete(t.pending, ref)
	t.mu.Unlock()
	if live {
		close(cancel)
	}
	return live
}

// current is the process serving now, or nil between restarts. It takes the
// runtime lock, so it must not be called while holding it.
func (s *Server[Q, R]) current() *PID[request[Q, R]] {
	if s.group == nil {
		return s.pid
	}
	r := s.group.task.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	return s.group.children[0].pid
}

// deliver queues a request from outside the server's callers, as a timer or
// a monitor does. It is dropped when the server is down.
func (s *Server[Q, R]) deliver(message request[Q, R]) {
	if pid := s.current(); pid != nil {
		Deliver(pid, message, time.Second)
	}
}

// ServerSendAfter casts a request to a server after ms milliseconds.
func ServerSendAfter[Q, R any](c *Context, s *Server[Q, R], value Q, ms int64, where string) int64 {
	Check(c)
	s.target(c, where)
	return later(c, ms, s.lifetime().doneSignal(), func() { s.deliver(request[Q, R]{value: value}) })
}

// ServerSelf is the server whose handler is running.
func ServerSelf[Q, R any](c *Context, where string) *Server[Q, R] {
	Check(c)
	s, ok := c.serving.(*Server[Q, R])
	if !ok {
		if c.serving == nil {
			Fail(c, where, "Server.self is called from a process that is not a server")
		}
		Fail(c, where, "Server.self is called by a server of other request and reply types")
	}
	return s
}

// RegisterServer gives a server a name that Process.whereis does not find
// and ServerWhereis does. A supervised server keeps its name across restarts.
func RegisterServer[Q, R any](c *Context, s *Server[Q, R], name, where string) bool {
	Check(c)
	s.target(c, where)
	if name == "" {
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
	task := s.lifetime()
	r.registered[name] = Registered{ID: task.id, PID: s, task: task}
	return true
}

// ServerWhereis finds the living server registered under a name, when its
// request and reply types are the ones asked for.
func ServerWhereis[Q, R any](c *Context, name string) (*Server[Q, R], bool) {
	entry, alive := LookupName(c, name)
	if !alive {
		return nil, false
	}
	s, fits := entry.PID.(*Server[Q, R])
	return s, fits
}

// ServerMonitor arranges for a request to reach a server when a process ends.
// The request is made inside the server, from the exit reason, so the
// conversion runs there and not in the process that ended.
func ServerMonitor[Q, R, T any](c *Context, s *Server[Q, R], p *PID[T], convert func(*Context, string) Q, where string) bool {
	Check(c)
	s.target(c, where)
	if p == nil {
		Fail(c, where, "invalid PID")
	}
	tell := func(reason string) {
		s.deliver(request[Q, R]{later: func(c *Context) Q { return convert(c, reason) }})
	}
	if p.remote != nil {
		// A process of another node is watched through a monitor of a
		// helper process that forwards the down event.
		Spawn(c, func(w *Context, _ *PID[struct{}]) int64 {
			p.remote.Monitor(w)
			for {
				event := NextEvent(w, -1)
				if event.E0 {
					tell(event.E3)
					return 0
				}
			}
		}, 1, where)
		return true
	}
	foreign(c, p, where)
	if ended, reason := WatchExit(p, tell); ended {
		go tell(reason)
	}
	return true
}

// ServerMailbox gives a server a mailbox that any process can send to: each
// message becomes one of the server's own requests, made inside the server by
// convert. It is how messages from ports, sockets and other processes reach a
// handler, as handle_info does in Elixir. The mailbox lasts as long as the
// server, across restarts of a supervised one.
func ServerMailbox[Q, R, M any](c *Context, s *Server[Q, R], convert func(*Context, M) Q, where string) *PID[M] {
	Check(c)
	s.target(c, where)
	life := s.lifetime()
	pid := Spawn(c, func(w *Context, self *PID[M]) int64 {
		for {
			message := Receive(w, self, -1, where).E1
			made := request[Q, R]{later: func(c *Context) Q { return convert(c, message) }}
			// A supervised server between restarts gets the message once
			// its replacement runs.
			for {
				if pid := s.current(); pid != nil && Deliver(pid, made, time.Second) {
					break
				}
				if life.stopped.Load() {
					break
				}
				Sleep(w, 1, where)
			}
		}
	}, serverCapacity, where)
	go func() {
		select {
		case <-life.doneSignal():
			r := c.rt
			r.mu.Lock()
			pid.task.cancel("shutdown", nil)
			r.mu.Unlock()
		case <-pid.task.doneSignal():
		}
	}()
	return pid
}

// Registry maps keys to the processes that registered under them, each with
// a value. An entry belongs to the process that made it and goes away when
// that process ends. A unique registry holds one entry per key. Keys are
// spread over partitions, each with a lock of its own, so that processes
// registering under different keys seldom wait for each other.
type Registry[K comparable, V any] struct {
	unique bool
	seed   maphash.Seed
	parts  []registryPart[K, V]
	serial atomic.Uint64
	// meta holds values put with Registry.put_meta.
	metaLock sync.Mutex
	meta     map[string]any
}

type registryPart[K comparable, V any] struct {
	mu      sync.Mutex
	entries map[K][]registryEntry[V]
}

type registryEntry[V any] struct {
	owner *Context
	value V
	// serial tells entries apart when a process holds a key more than once.
	serial uint64
}

// RegistryEntry is a key with the process id and value of one entry.
type RegistryEntry[K, V any] struct {
	Key   K
	ID    int64
	Value V
}

func (*Registry[K, V]) capability() {}

func NewRegistry[K comparable, V any](unique bool) *Registry[K, V] {
	return NewPartitionedRegistry[K, V](unique, 1)
}

// NewPartitionedRegistry spreads the keys over the given number of partitions.
func NewPartitionedRegistry[K comparable, V any](unique bool, partitions int) *Registry[K, V] {
	g := &Registry[K, V]{unique: unique, seed: maphash.MakeSeed(), parts: make([]registryPart[K, V], max(partitions, 1)), meta: map[string]any{}}
	for i := range g.parts {
		g.parts[i].entries = map[K][]registryEntry[V]{}
	}
	return g
}

// Partitions is the number of partitions.
func (g *Registry[K, V]) Partitions() int { return len(g.parts) }

func (g *Registry[K, V]) part(key K) *registryPart[K, V] {
	if len(g.parts) == 1 {
		return &g.parts[0]
	}
	return &g.parts[maphash.Comparable(g.seed, key)%uint64(len(g.parts))]
}

func living(owner *Context) bool { return !owner.stopped.Load() && !owner.finished.Load() }

// Register adds an entry for the calling process. It reports false when the
// registry is unique and a living process holds the key. In a duplicate
// registry a process may hold a key more than once.
func (g *Registry[K, V]) Register(c *Context, key K, value V) bool {
	Check(c)
	part := g.part(key)
	part.mu.Lock()
	defer part.mu.Unlock()
	var kept []registryEntry[V]
	for _, entry := range part.entries[key] {
		if !living(entry.owner) {
			continue
		}
		if g.unique {
			return false
		}
		kept = append(kept, entry)
	}
	part.entries[key] = append(kept, registryEntry[V]{c, value, g.serial.Add(1)})
	c.rt.mu.Lock()
	c.distant = append(c.distant, func(string) { g.forget(c) })
	c.rt.mu.Unlock()
	return true
}

// forget removes the entries of a process that has ended.
func (g *Registry[K, V]) forget(owner *Context) {
	for i := range g.parts {
		part := &g.parts[i]
		part.mu.Lock()
		for key, list := range part.entries {
			kept := list[:0]
			for _, entry := range list {
				if entry.owner != owner {
					kept = append(kept, entry)
				}
			}
			if len(kept) == 0 {
				delete(part.entries, key)
			} else {
				part.entries[key] = kept
			}
		}
		part.mu.Unlock()
	}
}

// Unregister removes the calling process's entries under a key.
func (g *Registry[K, V]) Unregister(c *Context, key K) bool {
	return g.UnregisterMatch(c, key, func(V) bool { return true }) > 0
}

// UnregisterMatch removes the calling process's entries under a key whose
// values satisfy keep, and returns how many it removed.
func (g *Registry[K, V]) UnregisterMatch(c *Context, key K, match func(V) bool) int64 {
	part := g.part(key)
	part.mu.Lock()
	list := append([]registryEntry[V](nil), part.entries[key]...)
	part.mu.Unlock()
	// The test runs without the lock, since it may be Alchem code that uses
	// the registry; entries are then removed by serial.
	remove := map[uint64]bool{}
	for _, entry := range list {
		if entry.owner == c && match(entry.value) {
			remove[entry.serial] = true
		}
	}
	if len(remove) == 0 {
		return 0
	}
	part.mu.Lock()
	defer part.mu.Unlock()
	removed := int64(0)
	var kept []registryEntry[V]
	for _, entry := range part.entries[key] {
		if remove[entry.serial] {
			removed++
		} else {
			kept = append(kept, entry)
		}
	}
	if len(kept) == 0 {
		delete(part.entries, key)
	} else {
		part.entries[key] = kept
	}
	return removed
}

// Entries lists the process ids and values registered under a key by living
// processes, in the order they registered.
func (g *Registry[K, V]) Entries(key K) []RegistryEntry[K, V] {
	part := g.part(key)
	part.mu.Lock()
	defer part.mu.Unlock()
	out := []RegistryEntry[K, V]{}
	for _, entry := range part.entries[key] {
		if living(entry.owner) {
			out = append(out, RegistryEntry[K, V]{key, entry.owner.id, entry.value})
		}
	}
	return out
}

// Lookup lists the values registered under a key by living processes, in
// the order they registered.
func (g *Registry[K, V]) Lookup(key K) []V {
	out := []V{}
	for _, entry := range g.Entries(key) {
		out = append(out, entry.Value)
	}
	return out
}

// Values lists the values one process registered under a key.
func (g *Registry[K, V]) Values(key K, owner *Context) []V {
	part := g.part(key)
	part.mu.Lock()
	defer part.mu.Unlock()
	out := []V{}
	for _, entry := range part.entries[key] {
		if entry.owner == owner && living(owner) {
			out = append(out, entry.value)
		}
	}
	return out
}

// UpdateValue replaces the value of the calling process's entry under a key
// of a unique registry, and returns the new and old values.
func (g *Registry[K, V]) UpdateValue(c *Context, key K, update func(V) V) (V, V, bool) {
	var zero V
	part := g.part(key)
	part.mu.Lock()
	var old V
	found := -1
	for i, entry := range part.entries[key] {
		if entry.owner == c {
			old, found = entry.value, i
			break
		}
	}
	part.mu.Unlock()
	if found < 0 {
		return zero, zero, false
	}
	// The update runs without the lock: it may be Alchem code.
	value := update(old)
	part.mu.Lock()
	defer part.mu.Unlock()
	for i, entry := range part.entries[key] {
		if entry.owner == c {
			part.entries[key][i].value = value
			return value, old, true
		}
	}
	return zero, zero, false
}

// All lists every living entry, by key and then in registration order.
func (g *Registry[K, V]) All() []RegistryEntry[K, V] {
	out := []RegistryEntry[K, V]{}
	for i := range g.parts {
		part := &g.parts[i]
		part.mu.Lock()
		for key, list := range part.entries {
			for _, entry := range list {
				if living(entry.owner) {
					out = append(out, RegistryEntry[K, V]{key, entry.owner.id, entry.value})
				}
			}
		}
		part.mu.Unlock()
	}
	return out
}

// Keys lists the keys a process holds.
func (g *Registry[K, V]) Keys(owner *Context) []K {
	out := []K{}
	for i := range g.parts {
		part := &g.parts[i]
		part.mu.Lock()
		for key, list := range part.entries {
			for _, entry := range list {
				if entry.owner == owner {
					out = append(out, key)
					break
				}
			}
		}
		part.mu.Unlock()
	}
	return out
}

// Count is the number of live entries.
func (g *Registry[K, V]) Count() int64 {
	n := int64(0)
	for i := range g.parts {
		part := &g.parts[i]
		part.mu.Lock()
		for _, list := range part.entries {
			for _, entry := range list {
				if living(entry.owner) {
					n++
				}
			}
		}
		part.mu.Unlock()
	}
	return n
}

// PutMeta stores a value under a name for the whole registry.
func (g *Registry[K, V]) PutMeta(name string, value any) {
	g.metaLock.Lock()
	defer g.metaLock.Unlock()
	g.meta[name] = value
}

// Meta finds a value stored with PutMeta.
func (g *Registry[K, V]) Meta(name string) (any, bool) {
	g.metaLock.Lock()
	defer g.metaLock.Unlock()
	value, ok := g.meta[name]
	return value, ok
}

// OwnerOf is the process context behind a handle, for Registry.keys.
func OwnerOf[T any](c *Context, p *PID[T], where string) *Context {
	foreign(c, p, where)
	return p.task
}

// DynamicSupervisor starts children while it runs, of any message type, and
// restarts the permanent ones that fail, within a restart intensity like a
// Supervisor's.
type DynamicSupervisor struct {
	task     *Context
	limit    int64
	window   time.Duration
	children []*dynamicChild
	restarts int64
	where    string
	// most is the largest number of children at once; zero is no limit.
	most int64
}

type dynamicChild struct {
	// start runs the child and returns its process.
	start   func() *Context
	current *Context
	// policy is permanent, transient or temporary, as for a Supervisor.
	policy  string
	handled bool
	removed bool
}

func (*DynamicSupervisor) capability() {}

// StartDynamicSupervisor starts an empty supervisor that gives up after more
// than limit restarts within window milliseconds.
func StartDynamicSupervisor(c *Context, limit, window int64, where string) *DynamicSupervisor {
	Check(c)
	if limit < 0 || window <= 0 || window > 86400000 {
		Fail(c, where, "invalid supervision limits")
	}
	r := c.rt
	r.mu.Lock()
	if r.closing || c.stopping {
		r.mu.Unlock()
		Check(c)
		Fail(c, where, "runtime shutting down")
	}
	task := r.newTask(c)
	r.observers++
	s := &DynamicSupervisor{task: task, limit: limit, window: time.Duration(window) * time.Millisecond, where: where}
	r.mu.Unlock()
	go s.run()
	return s
}

func (s *DynamicSupervisor) run() {
	reason := "normal"
	var failure *Failure
	defer func() {
		if v := recover(); v != nil {
			reason, failure = recovered(v)
		}
		r := s.task.rt
		r.mu.Lock()
		r.observers--
		var tasks []*Context
		for _, child := range s.children {
			if child.current != nil {
				child.current.cancel("shutdown", nil)
				tasks = append(tasks, child.current)
			}
		}
		r.mu.Unlock()
		for _, task := range tasks {
			<-task.doneSignal()
		}
		s.task.finish(reason, failure)
	}()
	history := []time.Time{}
	for {
		Check(s.task)
		r := s.task.rt
		r.mu.Lock()
		changed := r.changed
		var failed *dynamicChild
		why := ""
		for _, child := range s.children {
			if !child.removed && child.current != nil && child.current.ended && !child.handled {
				child.handled = true
				failed, why = child, child.current.reason
				break
			}
		}
		r.mu.Unlock()
		if failed == nil {
			select {
			case <-changed:
			case <-s.task.stopSignal():
				Check(s.task)
			}
			continue
		}
		if failed.policy == "temporary" || (failed.policy == "transient" && !abnormal(why)) {
			s.drop(failed)
			continue
		}
		now := time.Now()
		kept := history[:0]
		for _, stamp := range history {
			if now.Sub(stamp) < s.window {
				kept = append(kept, stamp)
			}
		}
		history = kept
		if int64(len(history)) >= s.limit {
			reason = "restart_intensity"
			failure = &Failure{Where: s.where, Message: reason}
			return
		}
		history = append(history, now)
		task := failed.start()
		r.mu.Lock()
		s.restarts++
		failed.current, failed.handled = task, false
		r.wake()
		r.mu.Unlock()
	}
}

// drop forgets a child that will not be restarted.
func (s *DynamicSupervisor) drop(child *dynamicChild) {
	r := s.task.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	child.removed = true
	kept := s.children[:0]
	for _, other := range s.children {
		if other != child {
			kept = append(kept, other)
		}
	}
	s.children = kept
}

func validDynamic(c *Context, s *DynamicSupervisor, where string) {
	if s == nil || s.task.rt != c.rt {
		Fail(c, where, "invalid or foreign supervisor")
	}
}

// LimitChildren sets the largest number of children the supervisor runs at
// once; zero is no limit.
func (s *DynamicSupervisor) LimitChildren(most int64) { s.most = most }

// full reports whether the supervisor runs as many children as it may. The
// runtime lock must be held.
func (s *DynamicSupervisor) full() bool {
	if s.most <= 0 {
		return false
	}
	n := int64(0)
	for _, child := range s.children {
		if !child.removed {
			n++
		}
	}
	return n >= s.most
}

// Reasons a child is not started.
const (
	NotRunning  = "supervisor is not running"
	MaxChildren = "max_children"
)

// add starts a child and records it, or returns why it did not.
func (s *DynamicSupervisor) add(c *Context, start func() *Context, policy string, where string) string {
	Check(c)
	validDynamic(c, s, where)
	if policy != "permanent" && policy != "transient" && policy != "temporary" {
		Fail(c, where, "a child's restart is permanent, transient or temporary")
	}
	if s.task.stopped.Load() {
		return NotRunning
	}
	r := s.task.rt
	child := &dynamicChild{policy: policy}
	r.mu.Lock()
	if s.full() {
		r.mu.Unlock()
		return MaxChildren
	}
	// The place is held while the child starts, and given up if starting
	// it fails.
	s.children = append(s.children, child)
	r.mu.Unlock()
	started := false
	defer func() {
		if !started {
			s.drop(child)
		}
	}()
	task := start()
	started = true
	r.mu.Lock()
	defer r.mu.Unlock()
	if s.task.stopping || s.task.ended {
		task.cancel("shutdown", nil)
		child.removed = true
		return NotRunning
	}
	child.start, child.current = start, task
	r.wake()
	return ""
}

// StartDynamicChild starts a process under the supervisor. A permanent child
// is restarted whenever it ends, a transient one when it fails, and a
// temporary one never. The handle returned is the first process; a restarted
// child is a new process.
func StartDynamicChild[T any](c *Context, s *DynamicSupervisor, body func(*Context, *PID[T]) int64, policy string, where string) (*PID[T], string) {
	var first *PID[T]
	problem := s.add(c, func() *Context {
		p := Spawn(s.task, body, 1024, where)
		if first == nil {
			first = p
		}
		return p.task
	}, policy, where)
	return first, problem
}

// StartDynamicServer starts a supervised server under the supervisor, which
// stops it when the supervisor stops. The server restarts itself, within the
// supervisor's own limits, so its handle stays good across restarts.
func StartDynamicServer[S, Q, R any](c *Context, s *DynamicSupervisor, state S, handle func(*Context, S, Q) struct {
	E0 S
	E1 R
}, where string) (*Server[Q, R], string) {
	Check(c)
	validDynamic(c, s, where)
	var server *Server[Q, R]
	// The server's own supervisor is owned by this one, so it is stopped
	// with it; it is a child that is never restarted from here.
	problem := s.add(c, func() *Context {
		server = StartSupervisedServer(s.task, state, handle, s.limit, s.window.Milliseconds(), where)
		return server.group.task
	}, "temporary", where)
	return server, problem
}

// TerminateDynamicChild stops a child that has this process id.
func TerminateDynamicChild(c *Context, s *DynamicSupervisor, id int64, where string) bool {
	Check(c)
	validDynamic(c, s, where)
	r := s.task.rt
	r.mu.Lock()
	var target *dynamicChild
	for _, child := range s.children {
		if child.current != nil && child.current.id == id && !child.removed {
			target = child
			break
		}
	}
	if target == nil {
		r.mu.Unlock()
		return false
	}
	target.removed = true
	task := target.current
	task.cancel("shutdown", nil)
	r.mu.Unlock()
	<-task.doneSignal()
	s.drop(target)
	return true
}

// DynamicChildren lists the process ids of the running children.
func DynamicChildren(c *Context, s *DynamicSupervisor, where string) []int64 {
	Check(c)
	validDynamic(c, s, where)
	r := s.task.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	out := []int64{}
	for _, child := range s.children {
		if !child.removed && child.current != nil && !child.current.ended {
			out = append(out, child.current.id)
		}
	}
	return out
}

func DynamicRestarts(c *Context, s *DynamicSupervisor, where string) int64 {
	validDynamic(c, s, where)
	r := s.task.rt
	r.mu.Lock()
	defer r.mu.Unlock()
	return s.restarts
}

func StopDynamicSupervisor(c *Context, s *DynamicSupervisor, ms int64, where string) bool {
	Check(c)
	validDynamic(c, s, where)
	c.rt.mu.Lock()
	s.task.cancel("shutdown", nil)
	c.rt.mu.Unlock()
	return wait(c, s.task, ms).E0
}

func DynamicSupervisorAlive(c *Context, s *DynamicSupervisor, where string) bool {
	Check(c)
	validDynamic(c, s, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	return !s.task.ended && !s.task.stopping
}
