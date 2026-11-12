package actor

// Task is a computation running in its own process whose result can be
// awaited once.
type Task[T any] struct {
	pid   *PID[struct{}]
	value T
}

func (*Task[T]) capability() {}

// taskBody is the process body of a task that stores its result.
func taskBody[T any](task *Task[T], fn func(*Context) T) func(*Context, *PID[struct{}]) int64 {
	return func(c *Context, _ *PID[struct{}]) int64 {
		c.rt.mu.Lock()
		c.untyped = true
		c.rt.mu.Unlock()
		// The value is stored before the process finishes, and read only
		// after it has, so no lock is needed.
		task.value = fn(c)
		return 0
	}
}

// StartTask runs fn in a new process linked to the caller, as Task.async
// does: a task that fails takes its caller with it, unless the caller traps
// exits.
func StartTask[T any](c *Context, fn func(*Context) T, where string) *Task[T] {
	task := StartUnlinkedTask(c, fn, where)
	Link(c, task.pid, where)
	return task
}

// StartUnlinkedTask runs fn in a new process whose failure is seen only by
// awaiting it.
func StartUnlinkedTask[T any](c *Context, fn func(*Context) T, where string) *Task[T] {
	task := &Task[T]{}
	task.pid = Spawn(c, taskBody(task, fn), 1, where)
	return task
}

// StartSupervisedTask runs fn as a temporary child of a dynamic supervisor,
// linked to the caller when linked is set.
func StartSupervisedTask[T any](c *Context, s *DynamicSupervisor, fn func(*Context) T, linked bool, where string) (*Task[T], string) {
	task := &Task[T]{}
	problem := s.add(c, func() *Context {
		task.pid = Spawn(s.task, taskBody(task, fn), 1, where)
		return task.pid.task
	}, "temporary", where)
	if problem != "" {
		return nil, problem
	}
	if linked {
		Link(c, task.pid, where)
	}
	return task, ""
}

// TaskID is the process id of a task.
func TaskID[T any](t *Task[T]) int64 { return t.pid.task.id }

// Outcome is the state of a task: finished with a value, ended without one
// for the given reason, or still running.
type Outcome[T any] struct {
	Value   T
	Reason  string
	Running bool
}

// YieldTask waits up to ms milliseconds for a task.
func YieldTask[T any](c *Context, t *Task[T], ms int64, where string) Outcome[T] {
	Check(c)
	foreign(c, t.pid, where)
	if t.pid.task == c {
		Fail(c, where, "a task cannot await itself")
	}
	result := wait(c, t.pid.task, ms)
	switch {
	case !result.E0:
		return Outcome[T]{Running: true}
	case result.E1 != "normal":
		return Outcome[T]{Reason: result.E1}
	}
	return Outcome[T]{Value: t.value}
}

// AwaitTask returns a task's value, failing the caller if the task failed or
// does not finish in time.
func AwaitTask[T any](c *Context, t *Task[T], ms int64, where string) T {
	outcome := YieldTask(c, t, ms, where)
	if outcome.Running {
		Fail(c, where, "task timed out")
	}
	if outcome.Reason != "" {
		Fail(c, where, "task failed: "+outcome.Reason)
	}
	return outcome.Value
}

// TaskReport describes how a finished task failed, with its Alchem frames.
func TaskReport[T any](c *Context, t *Task[T], where string) string {
	return Report(c, t.pid, where)
}

// StopTask ends a task that is no longer needed.
func StopTask[T any](c *Context, t *Task[T], where string) bool {
	return Stop(c, t.pid, where)
}

// Agent is a process that holds a state and applies functions to it one at a
// time.
type Agent[S any] struct {
	pid *PID[func(*Context, *S)]
}

func (*Agent[S]) capability() {}

// agentCapacity bounds the operations queued for one agent.
const agentCapacity = 1024

// RegisterAgent names an agent, as Server.register names a server.
func RegisterAgent[S any](c *Context, a *Agent[S], name, where string) bool {
	Check(c)
	foreign(c, a.pid, where)
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
	r.registered[name] = Registered{ID: a.pid.task.id, PID: a, task: a.pid.task}
	return true
}

// AgentWhereis finds the living agent registered under a name, when its
// state has the type asked for.
func AgentWhereis[S any](c *Context, name string) (*Agent[S], bool) {
	entry, alive := LookupName(c, name)
	if !alive {
		return nil, false
	}
	a, fits := entry.PID.(*Agent[S])
	return a, fits
}

// NamedAgent is the agent under a name, failing the caller when there is
// none of the state's type.
func NamedAgent[S any](c *Context, name, where string) *Agent[S] {
	a, ok := AgentWhereis[S](c, name)
	if !ok {
		Fail(c, where, "no agent named :"+name+" with this state type is running")
	}
	return a
}

// StartAgent starts an agent whose first state is computed in its own process.
func StartAgent[S any](c *Context, initial func(*Context) S, where string) *Agent[S] {
	return &Agent[S]{Spawn(c, func(c *Context, self *PID[func(*Context, *S)]) int64 {
		state := initial(c)
		for {
			Receive(c, self, -1, where).E1(c, &state)
		}
	}, agentCapacity, where)}
}

// ask runs an operation in the agent and waits for it to finish. An agent
// that stops first, or does not answer in time, fails the caller.
func ask[S any](c *Context, a *Agent[S], ms int64, where string, operation func(*Context, *S)) {
	Check(c)
	foreign(c, a.pid, where)
	if a.pid.task == c {
		Fail(c, where, "an agent cannot call itself")
	}
	done := make(chan struct{})
	if !Send(c, a.pid, func(agent *Context, state *S) { operation(agent, state); close(done) }, ms, where) {
		Fail(c, where, "agent is not running")
	}
	timer, stop := deadline(ms)
	defer stop()
	select {
	case <-done:
	case <-a.pid.task.doneSignal():
		select {
		case <-done:
		default:
			Fail(c, where, "agent stopped: "+a.pid.task.reason)
		}
	case <-c.stopSignal():
		Check(c)
	case <-timer:
		Fail(c, where, "agent timed out")
	}
}

// AgentGet returns a value computed from the state.
func AgentGet[S, R any](c *Context, a *Agent[S], f func(*Context, S) R, ms int64, where string) R {
	var result R
	ask(c, a, ms, where, func(agent *Context, state *S) { result = f(agent, *state) })
	return result
}

// AgentUpdate replaces the state and returns once it has been replaced.
func AgentUpdate[S any](c *Context, a *Agent[S], f func(*Context, S) S, ms int64, where string) {
	ask(c, a, ms, where, func(agent *Context, state *S) { *state = f(agent, *state) })
}

// AgentGetAndUpdate returns a value and replaces the state in one step.
func AgentGetAndUpdate[S, R any](c *Context, a *Agent[S], f func(*Context, S) struct {
	E0 R
	E1 S
}, ms int64, where string) R {
	var result R
	ask(c, a, ms, where, func(agent *Context, state *S) {
		next := f(agent, *state)
		result, *state = next.E0, next.E1
	})
	return result
}

// AgentCast replaces the state without waiting. It reports false when the
// agent has stopped or its queue is full.
func AgentCast[S any](c *Context, a *Agent[S], f func(*Context, S) S, where string) bool {
	Check(c)
	foreign(c, a.pid, where)
	return Send(c, a.pid, func(agent *Context, state *S) { *state = f(agent, *state) }, 0, where)
}

func StopAgent[S any](c *Context, a *Agent[S], where string) bool { return Stop(c, a.pid, where) }
func AgentAlive[S any](c *Context, a *Agent[S], where string) bool {
	return Alive(c, a.pid, where)
}
