package actor

import (
	"strings"
	"sync"
	"testing"
)

func TestTaskAwaitYieldAndFailure(t *testing.T) {
	c := root(t)
	task := StartTask(c, func(child *Context) int64 { Sleep(child, 20, "task"); return 42 }, "test")
	if outcome := YieldTask(c, task, 0, "test"); !outcome.Running {
		t.Fatalf("%+v", outcome)
	}
	if value := AwaitTask(c, task, 2000, "test"); value != 42 {
		t.Fatal(value)
	}
	if outcome := YieldTask(c, task, 0, "test"); outcome.Running || outcome.Value != 42 {
		t.Fatalf("%+v", outcome)
	}
	failing := StartUnlinkedTask(c, func(child *Context) int64 { Fail(child, "task", "boom"); return 0 }, "test")
	if outcome := YieldTask(c, failing, 2000, "test"); outcome.Running || !strings.Contains(outcome.Reason, "boom") {
		t.Fatalf("%+v", outcome)
	}
	slow := StartTask(c, func(child *Context) int64 { Sleep(child, 60000, "task"); return 1 }, "test")
	if outcome := YieldTask(c, slow, 10, "test"); !outcome.Running {
		t.Fatalf("%+v", outcome)
	}
	if !StopTask(c, slow, "test") {
		t.Fatal("stop")
	}
	eventually(t, func() bool { return !YieldTask(c, slow, 0, "test").Running })
}

// A linked task that fails takes its caller with it.
func TestLinkedTaskFailureEndsCaller(t *testing.T) {
	c := root(t)
	caller := Spawn(c, func(child *Context, _ *PID[int64]) int64 {
		StartTask(child, func(task *Context) int64 { Fail(task, "task", "boom"); return 0 }, "test")
		Sleep(child, 5000, "test")
		return 0
	}, 1, "test")
	result := Await(c, caller, 2000, "test")
	if !result.E0 || !strings.Contains(result.E1, "linked: boom") {
		t.Fatalf("%+v", result)
	}
}

func TestAgentSerializesUpdates(t *testing.T) {
	c := root(t)
	agent := StartAgent(c, func(*Context) int64 { return 0 }, "test")
	var group sync.WaitGroup
	for worker := 0; worker < 8; worker++ {
		group.Add(1)
		Spawn(c, func(child *Context, _ *PID[int64]) int64 {
			defer group.Done()
			for i := 0; i < 100; i++ {
				AgentUpdate(child, agent, func(_ *Context, n int64) int64 { return n + 1 }, 5000, "test")
			}
			return 0
		}, 1, "test")
	}
	group.Wait()
	if total := AgentGet(c, agent, func(_ *Context, n int64) int64 { return n }, 1000, "test"); total != 800 {
		t.Fatal(total)
	}
	previous := AgentGetAndUpdate(c, agent, func(_ *Context, n int64) struct {
		E0 int64
		E1 int64
	} {
		return struct {
			E0 int64
			E1 int64
		}{n, 0}
	}, 1000, "test")
	if previous != 800 || AgentGet(c, agent, func(_ *Context, n int64) int64 { return n }, 1000, "test") != 0 {
		t.Fatal(previous)
	}
	if !AgentCast(c, agent, func(_ *Context, n int64) int64 { return n + 5 }, "test") {
		t.Fatal("cast")
	}
	if total := AgentGet(c, agent, func(_ *Context, n int64) int64 { return n }, 1000, "test"); total != 5 {
		t.Fatal(total)
	}
	if !StopAgent(c, agent, "test") {
		t.Fatal("stop")
	}
	eventually(t, func() bool { return !AgentAlive(c, agent, "test") })
	if AgentCast(c, agent, func(_ *Context, n int64) int64 { return n }, "test") {
		t.Fatal("stopped agent accepted a cast")
	}
}
