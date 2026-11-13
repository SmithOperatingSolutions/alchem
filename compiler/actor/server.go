package actor

import "time"

// request is one message to a server; reply is nil when no answer is wanted.
type request[Q, R any] struct {
	value Q
	reply chan R
	// later, when set, makes the request inside the server: it is how an
	// exit the server monitors arrives as one of its own requests.
	later func(*Context) Q
}

// Server is a process that owns a state and answers typed requests one at a
// time, in the order they arrive. A supervised server runs as the only child
// of its own supervisor, which replaces it, with the initial state, when its
// handler fails.
type Server[Q, R any] struct {
	pid   *PID[request[Q, R]]
	group *Supervisor[request[Q, R]]
	// ready is closed once pid or group is set, so a handler that reaches
	// its own server never reads a handle still being filled in.
	ready chan struct{}
}

func (*Server[Q, R]) capability() {}

// serverCapacity bounds the requests queued for one server.
const serverCapacity = 1024

// serve returns the process body of a server starting from the given state.
func serve[S, Q, R any](s *Server[Q, R], state S, handle func(*Context, S, Q) struct {
	E0 S
	E1 R
}, where string) func(*Context, *PID[request[Q, R]]) int64 {
	return func(c *Context, self *PID[request[Q, R]]) int64 {
		select {
		case <-s.ready:
		case <-c.stopSignal():
			Check(c)
		}
		cold := c.cold()
		cold.serving = s
		state := state
		for {
			message := Receive(c, self, -1, where).E1
			if message.later != nil {
				message.value = message.later(c)
			}
			next := handle(c, state, message.value)
			state = next.E0
			if message.reply != nil {
				// The channel holds one reply, so an abandoned call never blocks.
				message.reply <- next.E1
			}
			// Work a handler continues runs before the next request, and
			// its replies go nowhere.
			for len(cold.continued) > 0 {
				value := cold.continued[0].(Q)
				cold.continued = cold.continued[1:]
				state = handle(c, state, value).E0
			}
		}
	}
}

// ServerContinue asks the running server to handle a request of its own as
// soon as the current one is answered, before any request waiting in its
// mailbox: the work a handler defers past its reply. Requests continued from
// one handler are handled in order.
func ServerContinue[Q any](c *Context, value Q, where string) bool {
	Check(c)
	cold := c.more.Load()
	if cold == nil || cold.serving == nil {
		Fail(c, where, "Server.continue is called from a process that is not a server")
	}
	if accepts, ok := cold.serving.(interface{ accepts(any) bool }); !ok || !accepts.accepts(value) {
		Fail(c, where, "Server.continue is given a request of another type than its server's")
	}
	cold.continued = append(cold.continued, value)
	return true
}

func (*Server[Q, R]) accepts(value any) bool {
	_, ok := value.(Q)
	return ok
}

// StartServer spawns a server. The handler receives the current state and a
// request and returns the next state with the reply.
func StartServer[S, Q, R any](c *Context, state S, handle func(*Context, S, Q) struct {
	E0 S
	E1 R
}, where string) *Server[Q, R] {
	s := &Server[Q, R]{ready: make(chan struct{})}
	s.pid = Spawn(c, serve(s, state, handle, where), serverCapacity, where)
	close(s.ready)
	return s
}

// StartSupervisedServer starts a server that is restarted after a failure, at
// most limit times within window milliseconds.
func StartSupervisedServer[S, Q, R any](c *Context, state S, handle func(*Context, S, Q) struct {
	E0 S
	E1 R
}, limit, window int64, where string) *Server[Q, R] {
	specs := []struct {
		E0 string
		E1 string
		E2 func(*Context, *PID[request[Q, R]]) int64
	}{{"server", "permanent", nil}}
	s := &Server[Q, R]{ready: make(chan struct{})}
	specs[0].E2 = serve(s, state, handle, where)
	s.group = StartSupervisor(c, "one_for_one", limit, window, specs, serverCapacity, where)
	close(s.ready)
	return s
}

// target returns the process currently serving, or nil between restarts.
func (s *Server[Q, R]) target(c *Context, where string) *PID[request[Q, R]] {
	if s == nil {
		Fail(c, where, "invalid server")
	}
	if s.group == nil {
		foreign(c, s.pid, where)
		return s.pid
	}
	validSupervisor(c, s.group, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	return s.group.children[0].pid
}

// lifetime is the context whose end means the server is gone for good.
func (s *Server[Q, R]) lifetime() *Context {
	if s.group != nil {
		return s.group.task
	}
	return s.pid.task
}

// Reply is the outcome of a call: a value, or the reason there is none.
type Reply[R any] struct {
	Value R
	Error string
}

// Call sends a request and waits for its reply. It fails softly, with a
// reason, when the deadline passes or the server stops before answering.
func Call[Q, R any](c *Context, s *Server[Q, R], value Q, ms int64, where string) Reply[R] {
	Check(c)
	started := time.Now()
	remaining := func() int64 {
		if ms <= 0 {
			return ms
		}
		if left := ms - time.Since(started).Milliseconds(); left > 0 {
			return left
		}
		return 0
	}
	reply := make(chan R, 1)
	var target *Context
	for {
		pid := s.target(c, where)
		if pid != nil {
			if pid.task == c {
				Fail(c, where, "a server cannot call itself")
			}
			if Send(c, pid, request[Q, R]{value: value, reply: reply}, remaining(), where) {
				target = pid.task
				break
			}
			if !pid.task.stopped.Load() {
				return Reply[R]{Error: "timeout"}
			}
		}
		// A supervised server may be between restarts: wait for its replacement.
		if s.group == nil || s.lifetime().stopped.Load() {
			return Reply[R]{Error: "server is not running"}
		}
		if ms == 0 || (ms > 0 && remaining() == 0) {
			return Reply[R]{Error: "timeout"}
		}
		Sleep(c, 1, where)
	}
	wait := remaining()
	if ms > 0 && wait == 0 {
		wait = 1
	}
	timer, stop := deadline(wait)
	defer stop()
	select {
	case answer := <-reply:
		return Reply[R]{Value: answer}
	case <-target.doneSignal():
		select {
		case answer := <-reply:
			return Reply[R]{Value: answer}
		default:
		}
		return Reply[R]{Error: "server stopped: " + target.reason}
	case <-c.stopSignal():
		Check(c)
	case <-timer:
	}
	return Reply[R]{Error: "timeout"}
}

// Cast queues a request without waiting for its reply. It reports false when
// the server has stopped or its queue is full.
func Cast[Q, R any](c *Context, s *Server[Q, R], value Q, where string) bool {
	Check(c)
	pid := s.target(c, where)
	return pid != nil && Send(c, pid, request[Q, R]{value: value}, 0, where)
}

// StopServer requests shutdown of the server, and of its supervisor if it has
// one, and reports whether it was still running.
func StopServer[Q, R any](c *Context, s *Server[Q, R], where string) bool {
	Check(c)
	s.target(c, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	task := s.lifetime()
	running := !task.ended && !task.stopping
	task.cancel("shutdown", nil)
	return running
}
func ServerAlive[Q, R any](c *Context, s *Server[Q, R], where string) bool {
	Check(c)
	s.target(c, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	task := s.lifetime()
	return !task.ended && !task.stopping
}
func AwaitServer[Q, R any](c *Context, s *Server[Q, R], ms int64, where string) Result {
	Check(c)
	s.target(c, where)
	if s.lifetime() == c {
		Fail(c, where, "cannot await self")
	}
	return wait(c, s.lifetime(), ms)
}

// ServerRestarts counts how often a supervised server has been replaced.
func ServerRestarts[Q, R any](c *Context, s *Server[Q, R], where string) int64 {
	s.target(c, where)
	if s.group == nil {
		return 0
	}
	return Restarts(c, s.group, where)
}

// ServerChild is the body of a supervisor child that runs a server under a
// name. The child starts the server, registers it, and lives as long as it:
// a server that fails makes the child fail, so the supervisor's strategy and
// the child's restart policy apply, and a child that is stopped stops its
// server. Every start begins from the initial state, and the name moves to
// the new server, so Server.whereis finds whichever is running.
func ServerChild[S, Q, R, T any](name string, state S, handle func(*Context, S, Q) struct {
	E0 S
	E1 R
}, where string) func(*Context, *PID[T]) int64 {
	body := func(c *Context, _ *PID[T]) int64 {
		s := StartServer(c, state, handle, where)
		task := s.pid.task
		OnEnd(c, func() {
			c.rt.mu.Lock()
			defer c.rt.mu.Unlock()
			task.cancel("shutdown", nil)
		})
		if !RegisterServer(c, s, name, where) {
			Fail(c, where, "Supervisor.server: the name "+name+" is already registered")
		}
		Started(c)
		ended := wait(c, task, -1)
		if abnormal(ended.E1) {
			Fail(c, where, "server "+name+" failed: "+ended.E1)
		}
		return 0
	}
	announcesStart(body)
	return body
}
