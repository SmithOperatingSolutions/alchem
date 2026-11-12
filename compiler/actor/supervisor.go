package actor

import (
	"sync/atomic"
	"time"
)

type ChildSpec[T any] struct {
	E0, E1 string
	E2     func(*Context, *PID[T]) int64
}
type child[T any] struct {
	spec    ChildSpec[T]
	pid     *PID[T]
	handled bool
}
type Supervisor[T any] struct {
	task     *Context
	children []child[T]
	// published mirrors each child's current PID for lock-free lookup. It has
	// one fixed slot per child spec and is written only while starting a child.
	published []atomic.Pointer[PID[T]]
	strategy  string
	limit     int64
	window    time.Duration
	capacity  int64
	restarts  int64
}

func (*Supervisor[T]) capability() {}
func StartSupervisor[T any](c *Context, strategy string, limit, window int64, specs []struct {
	E0 string
	E1 string
	E2 func(*Context, *PID[T]) int64
}, capacity int64, where string) *Supervisor[T] {
	return startSupervisor(c, strategy, limit, window, specs, capacity, where, false)
}
func StartLinkedSupervisor[T any](c *Context, strategy string, limit, window int64, specs []struct {
	E0 string
	E1 string
	E2 func(*Context, *PID[T]) int64
}, capacity int64, where string) *Supervisor[T] {
	return startSupervisor(c, strategy, limit, window, specs, capacity, where, true)
}
func startSupervisor[T any](c *Context, strategy string, limit, window int64, specs []struct {
	E0 string
	E1 string
	E2 func(*Context, *PID[T]) int64
}, capacity int64, where string, linked bool) *Supervisor[T] {
	Check(c)
	if strategy != "one_for_one" && strategy != "one_for_all" && strategy != "rest_for_one" {
		Fail(c, where, "invalid supervision strategy")
	}
	if limit < 0 || window <= 0 || window > 86400000 || capacity < 1 || capacity > 1000000 || len(specs) == 0 {
		Fail(c, where, "invalid supervision limits, capacity or empty children")
	}
	names := map[string]bool{}
	for _, spec := range specs {
		if spec.E0 == "" || names[spec.E0] || (spec.E1 != "permanent" && spec.E1 != "transient" && spec.E1 != "temporary") || spec.E2 == nil {
			Fail(c, where, "invalid or duplicate child specification")
		}
		names[spec.E0] = true
	}
	r := c.rt
	r.mu.Lock()
	if r.closing || c.stopping {
		r.mu.Unlock()
		Check(c)
		Fail(c, where, "runtime shutting down")
	}
	task := r.newTask(c)
	if linked {
		relate(&task.links, c.id, c)
		relate(&c.links, task.id, task)
	}
	// Registered before the goroutine starts so no child exit is missed.
	r.observers++
	s := &Supervisor[T]{task: task, strategy: strategy, limit: limit, window: time.Duration(window) * time.Millisecond, capacity: capacity}
	for _, spec := range specs {
		s.children = append(s.children, child[T]{spec: ChildSpec[T]{spec.E0, spec.E1, spec.E2}})
	}
	s.published = make([]atomic.Pointer[PID[T]], len(specs))
	r.mu.Unlock()
	ready := make(chan struct{})
	go s.run(ready, where)
	select {
	case <-ready:
	case <-c.stopSignal():
		Check(c)
	}
	return s
}
func (s *Supervisor[T]) run(ready chan struct{}, where string) {
	reason := "normal"
	var failure *Failure
	signaled := false
	defer func() {
		if v := recover(); v != nil {
			reason, failure = recovered(v)
		}
		r := s.task.rt
		r.mu.Lock()
		r.observers--
		var tasks []*Context
		for _, child := range s.children {
			if child.pid != nil {
				child.pid.task.cancel("shutdown", nil)
				tasks = append(tasks, child.pid.task)
			}
		}
		r.mu.Unlock()
		for _, task := range tasks {
			<-task.doneSignal()
		}
		if !signaled {
			close(ready)
		}
		s.task.finish(reason, failure)
	}()
	start := func(i int) {
		pid := Spawn(s.task, s.children[i].spec.E2, s.capacity, where)
		s.task.rt.mu.Lock()
		s.children[i].pid = pid
		s.published[i].Store(pid)
		s.children[i].handled = false
		s.task.rt.wake()
		s.task.rt.mu.Unlock()
	}
	for i := range s.children {
		start(i)
	}
	close(ready)
	signaled = true
	history := []time.Time{}
	for {
		Check(s.task)
		r := s.task.rt
		r.mu.Lock()
		changed := r.changed
		failed := -1
		why := ""
		for i, child := range s.children {
			if child.pid != nil && child.pid.task.ended && !child.handled {
				failed = i
				why = child.pid.task.reason
				s.children[i].handled = true
				break
			}
		}
		r.mu.Unlock()
		if failed < 0 {
			select {
			case <-changed:
			case <-s.task.stopSignal():
				Check(s.task)
			}
			continue
		}
		policy := s.children[failed].spec.E1
		if policy == "temporary" || (policy == "transient" && !abnormal(why)) {
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
			failure = &Failure{Where: where, Message: reason}
			return
		}
		history = append(history, now)
		selected := []int{}
		switch s.strategy {
		case "one_for_one":
			selected = []int{failed}
		case "one_for_all":
			for i := range s.children {
				selected = append(selected, i)
			}
		default:
			for i := failed; i < len(s.children); i++ {
				selected = append(selected, i)
			}
		}
		r.mu.Lock()
		var tasks []*Context
		for _, i := range selected {
			if p := s.children[i].pid; p != nil {
				p.task.cancel("shutdown", nil)
				tasks = append(tasks, p.task)
			}
		}
		r.mu.Unlock()
		for _, task := range tasks {
			select {
			case <-task.doneSignal():
			case <-s.task.stopSignal():
				Check(s.task)
			}
		}
		Check(s.task)
		r.mu.Lock()
		s.restarts++
		r.mu.Unlock()
		for _, i := range selected {
			if s.children[i].spec.E1 != "temporary" {
				start(i)
			}
		}
	}
}
func validSupervisor[T any](c *Context, s *Supervisor[T], where string) {
	if s == nil || s.task.rt != c.rt {
		Fail(c, where, "invalid or foreign supervisor")
	}
}
func Child[T any](c *Context, s *Supervisor[T], name, where string) *PID[T] {
	Check(c)
	validSupervisor(c, s, where)
	// Child specs never change after the supervisor starts and the current PID
	// is published atomically, so a lookup takes no lock. A caller polling for
	// a replacement therefore cannot hold up the supervisor creating it.
	for i := range s.children {
		if s.children[i].spec.E0 == name {
			pid := s.published[i].Load()
			if pid == nil {
				Fail(c, where, "child has not started")
			}
			return pid
		}
	}
	Fail(c, where, "unknown supervised child: "+name)
	return nil
}
func StopSupervisor[T any](c *Context, s *Supervisor[T], ms int64, where string) bool {
	Check(c)
	validSupervisor(c, s, where)
	c.rt.mu.Lock()
	s.task.cancel("shutdown", nil)
	c.rt.mu.Unlock()
	return wait(c, s.task, ms).E0
}
func AwaitSupervisor[T any](c *Context, s *Supervisor[T], ms int64, where string) Result {
	Check(c)
	validSupervisor(c, s, where)
	return wait(c, s.task, ms)
}
func SupervisorAlive[T any](c *Context, s *Supervisor[T], where string) bool {
	Check(c)
	validSupervisor(c, s, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	return !s.task.ended && !s.task.stopping
}
func Restarts[T any](c *Context, s *Supervisor[T], where string) int64 {
	validSupervisor(c, s, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	return s.restarts
}
func Children[T any](c *Context, s *Supervisor[T], where string) []struct {
	E0 string
	E1 int64
} {
	Check(c)
	validSupervisor(c, s, where)
	c.rt.mu.Lock()
	defer c.rt.mu.Unlock()
	out := make([]struct {
		E0 string
		E1 int64
	}, len(s.children))
	for i, child := range s.children {
		out[i].E0 = child.spec.E0
		if child.pid != nil {
			out[i].E1 = child.pid.task.id
		}
	}
	return out
}
