package actor

import (
	"testing"
	"time"
)

func TestSendAfterDeliversAndCancels(t *testing.T) {
	c := root(t)
	me := Self[string](c, 8, "test")
	SendAfter(c, me, "first", 10, "test")
	cancelled := SendAfter(c, me, "never", 20, "test")
	if !CancelTimer(c, cancelled) || CancelTimer(c, cancelled) {
		t.Fatal("a pending timer cancels once")
	}
	if got := Receive(c, me, 1000, "test"); !got.E0 || got.E1 != "first" {
		t.Fatalf("timer message: %+v", got)
	}
	if got := Receive(c, me, 60, "test"); got.E0 {
		t.Fatalf("cancelled timer delivered %q", got.E1)
	}
	fired := SendAfter(c, me, "again", 0, "test")
	Receive(c, me, 1000, "test")
	if CancelTimer(c, fired) {
		t.Fatal("a fired timer cannot be cancelled")
	}
}

// A timer aimed at a process that has ended goes nowhere and leaves nothing
// pending.
func TestSendAfterToEndedProcess(t *testing.T) {
	c := root(t)
	p := Spawn(c, func(*Context, *PID[int64]) int64 { return 0 }, 1, "test")
	wait(c, p.task, 1000)
	ref := SendAfter(c, p, 1, 5, "test")
	time.Sleep(30 * time.Millisecond)
	if CancelTimer(c, ref) {
		t.Fatal("timer to an ended process still pending")
	}
}

func TestServerSelfSchedulesItself(t *testing.T) {
	c := root(t)
	s := StartServer(c, int64(0), func(c *Context, state, n int64) step {
		if n > 0 {
			ServerSendAfter(c, ServerSelf[int64, int64](c, "test"), n-1, 1, "test")
		}
		return step{state + 1, state + 1}
	}, "test")
	Cast(c, s, 5, "test")
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if reply := Call(c, s, -1, 1000, "test"); reply.Value >= 7 {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatal("server did not handle the requests it scheduled")
}

func TestServerSelfOutsideServer(t *testing.T) {
	c := root(t)
	p := Spawn(c, func(c *Context, _ *PID[int64]) int64 {
		ServerSelf[int64, int64](c, "test")
		return 0
	}, 1, "test")
	if result := wait(c, p.task, 1000); !result.E0 || result.E1 == "normal" {
		t.Fatalf("Server.self outside a server: %+v", result)
	}
}

func TestNamedServerSurvivesRestart(t *testing.T) {
	c := root(t)
	s := StartSupervisedServer(c, int64(0), func(c *Context, state, n int64) step {
		if n < 0 {
			Fail(c, "test", "negative")
		}
		return step{state + n, state + n}
	}, 5, 1000, "test")
	if !RegisterServer(c, s, "counter", "test") || RegisterServer(c, s, "counter", "test") {
		t.Fatal("a name is given once")
	}
	Call(c, s, -1, 1000, "test")
	found, ok := ServerWhereis[int64, int64](c, "counter")
	if !ok || found != s {
		t.Fatal("name lost across a restart")
	}
	if reply := Call(c, found, 2, 1000, "test"); reply.Value != 2 {
		t.Fatalf("restarted server: %+v", reply)
	}
	if _, ok := ServerWhereis[string, int64](c, "counter"); ok {
		t.Fatal("found under other types")
	}
	StopServer(c, s, "test")
	AwaitServer(c, s, 1000, "test")
	if _, ok := ServerWhereis[int64, int64](c, "counter"); ok {
		t.Fatal("a stopped server is still found")
	}
}

func TestServerMonitorQueuesExit(t *testing.T) {
	c := root(t)
	s := StartServer(c, "", func(_ *Context, state, event string) struct {
		E0 string
		E1 string
	} {
		if event != "" {
			state = event
		}
		return struct {
			E0 string
			E1 string
		}{state, state}
	}, "test")
	p := Spawn(c, func(c *Context, _ *PID[int64]) int64 {
		Fail(c, "test", "boom")
		return 0
	}, 1, "test")
	ServerMonitor(c, s, p, func(_ *Context, reason string) string { return "down " + reason }, "test")
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if reply := Call(c, s, "", 1000, "test"); reply.Value == "down boom" {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatal("exit did not reach the server")
}

func TestRegistryForgetsEndedOwners(t *testing.T) {
	c := root(t)
	unique := NewRegistry[string, int64](true)
	if !unique.Register(c, "a", 1) || unique.Register(c, "a", 2) {
		t.Fatal("unique key taken twice")
	}
	holder := Spawn(c, func(w *Context, self *PID[int64]) int64 {
		unique.Register(w, "b", 3)
		Receive(w, self, -1, "test")
		return 0
	}, 1, "test")
	for unique.Count() < 2 {
		time.Sleep(time.Millisecond)
	}
	if got := unique.Lookup("b"); len(got) != 1 || got[0] != 3 {
		t.Fatalf("lookup: %v", got)
	}
	if unique.Register(c, "b", 4) {
		t.Fatal("key of a living process taken")
	}
	Send(c, holder, 0, 1000, "test")
	wait(c, holder.task, 1000)
	if got := unique.Lookup("b"); len(got) != 0 {
		t.Fatalf("entry outlived its process: %v", got)
	}
	if !unique.Register(c, "b", 5) {
		t.Fatal("key not freed by its owner's exit")
	}
	duplicate := NewRegistry[string, int64](false)
	duplicate.Register(c, "k", 1)
	duplicate.Register(c, "k", 2)
	if got := duplicate.Lookup("k"); len(got) != 2 {
		t.Fatalf("duplicate entries: %v", got)
	}
	if !duplicate.Unregister(c, "k") || duplicate.Count() != 0 {
		t.Fatal("unregister leaves entries")
	}
}

func TestDynamicSupervisorRestartsByPolicy(t *testing.T) {
	c := root(t)
	s := StartDynamicSupervisor(c, 10, 5000, "test")
	// A crash every 20 ms keeps ten restarts well inside the five-second
	// window while the test looks at the restarted child.
	crash := func(c *Context, _ *PID[int64]) int64 {
		time.Sleep(20 * time.Millisecond)
		Fail(c, "test", "crash")
		return 0
	}
	normal := func(*Context, *PID[int64]) int64 { return 0 }
	StartDynamicChild(c, s, normal, "transient", "test")
	StartDynamicChild(c, s, normal, "temporary", "test")
	waitFor(t, func() bool { return len(DynamicChildren(c, s, "test")) == 0 })
	if DynamicRestarts(c, s, "test") != 0 {
		t.Fatal("a child that ended normally was restarted")
	}
	first, _ := StartDynamicChild(c, s, crash, "transient", "test")
	waitFor(t, func() bool { return DynamicRestarts(c, s, "test") >= 2 })
	if !DynamicSupervisorAlive(c, s, "test") {
		t.Fatal("gave up too soon")
	}
	// Between a crash and its restart the supervisor has no children, so
	// the replacement is looked for, and terminated, until one is found.
	waitFor(t, func() bool {
		children := DynamicChildren(c, s, "test")
		return len(children) == 1 && children[0] != first.task.id && TerminateDynamicChild(c, s, children[0], "test")
	})
	if len(DynamicChildren(c, s, "test")) != 0 {
		t.Fatal("terminate_child")
	}
	// Past the restart intensity the supervisor stops.
	StartDynamicChild(c, s, crash, "permanent", "test")
	if result := AwaitDynamic(c, s, 3000); !result.E0 || result.E1 != "restart_intensity" {
		t.Fatalf("supervisor end: %+v", result)
	}
}

func TestDynamicSupervisorStopsServers(t *testing.T) {
	c := root(t)
	s := StartDynamicSupervisor(c, 3, 5000, "test")
	server, problem := StartDynamicServer(c, s, int64(0), func(_ *Context, state, n int64) step {
		return step{state + n, state + n}
	}, "test")
	if problem != "" {
		t.Fatal("server not started:", problem)
	}
	if reply := Call(c, server, 3, 1000, "test"); reply.Value != 3 {
		t.Fatalf("call: %+v", reply)
	}
	if !StopDynamicSupervisor(c, s, 1000, "test") || ServerAlive(c, server, "test") {
		t.Fatal("server outlived its supervisor")
	}
	if _, problem := StartDynamicChild(c, s, func(*Context, *PID[int64]) int64 { return 0 }, "permanent", "test"); problem != NotRunning {
		t.Fatal("stopped supervisor started a child:", problem)
	}
}

func AwaitDynamic(c *Context, s *DynamicSupervisor, ms int64) Result { return wait(c, s.task, ms) }

func waitFor(t *testing.T, ready func() bool) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for !ready() {
		if time.Now().After(deadline) {
			t.Fatal("condition not reached")
		}
		time.Sleep(2 * time.Millisecond)
	}
}
