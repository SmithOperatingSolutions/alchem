package actor

import (
	"strings"
	"sync"
	"testing"
)

type step = struct {
	E0 int64
	E1 int64
}

func TestServerAnswersInOrder(t *testing.T) {
	c := root(t)
	s := StartServer(c, int64(0), func(_ *Context, state, add int64) step {
		return step{state + add, state + add}
	}, "test")
	for i := int64(1); i <= 100; i++ {
		if reply := Call(c, s, 1, 1000, "test"); reply.Error != "" || reply.Value != i {
			t.Fatalf("call %d: %+v", i, reply)
		}
	}
	if !Cast(c, s, 5, "test") {
		t.Fatal("cast rejected")
	}
	if reply := Call(c, s, 0, 1000, "test"); reply.Value != 105 {
		t.Fatalf("after cast: %+v", reply)
	}
	if !StopServer(c, s, "test") || !AwaitServer(c, s, 1000, "test").E0 {
		t.Fatal("server did not stop")
	}
	if reply := Call(c, s, 1, 1000, "test"); reply.Error != "server is not running" {
		t.Fatalf("after stop: %+v", reply)
	}
	if Cast(c, s, 1, "test") || ServerAlive(c, s, "test") {
		t.Fatal("stopped server accepted work")
	}
}

// Concurrent callers each get the reply to their own request.
func TestServerConcurrentCallers(t *testing.T) {
	c := root(t)
	s := StartServer(c, int64(0), func(_ *Context, state, value int64) step {
		return step{state + 1, value * 2}
	}, "test")
	var group sync.WaitGroup
	for worker := int64(0); worker < 16; worker++ {
		group.Add(1)
		Spawn(c, func(child *Context, _ *PID[int64]) int64 {
			defer group.Done()
			for i := int64(0); i < 50; i++ {
				value := worker*1000 + i
				if reply := Call(child, s, value, 5000, "test"); reply.Error != "" || reply.Value != value*2 {
					t.Errorf("worker %d: %+v", worker, reply)
				}
			}
			return 0
		}, 1, "test")
	}
	group.Wait()
	if reply := Call(c, s, 0, 1000, "test"); reply.Error != "" {
		t.Fatal(reply.Error)
	}
	StopServer(c, s, "test")
}

func TestServerFailureAndTimeout(t *testing.T) {
	c := root(t)
	failing := StartServer(c, int64(0), func(child *Context, state, value int64) step {
		if value == 0 {
			Fail(child, "handler", "bad request")
		}
		return step{state, value}
	}, "test")
	if reply := Call(c, failing, 7, 1000, "test"); reply.Value != 7 {
		t.Fatalf("%+v", reply)
	}
	if reply := Call(c, failing, 0, 1000, "test"); !strings.Contains(reply.Error, "server stopped") || !strings.Contains(reply.Error, "bad request") {
		t.Fatalf("%+v", reply)
	}
	eventually(t, func() bool { return !ServerAlive(c, failing, "test") })

	slow := StartServer(c, int64(0), func(child *Context, state, wait int64) step {
		Sleep(child, wait, "handler")
		return step{state + 1, state + 1}
	}, "test")
	if reply := Call(c, slow, 200, 10, "test"); reply.Error != "timeout" {
		t.Fatalf("%+v", reply)
	}
	if reply := Call(c, slow, 0, 3000, "test"); reply.Error != "" || reply.Value != 2 {
		t.Fatalf("abandoned call must still run: %+v", reply)
	}
	StopServer(c, slow, "test")
}

func TestSupervisedServerRestartsWithInitialState(t *testing.T) {
	c := root(t)
	s := StartSupervisedServer(c, int64(10), func(child *Context, state, value int64) step {
		if value == 0 {
			Fail(child, "handler", "bad request")
		}
		return step{state + value, state + value}
	}, 2, 60000, "test")
	if reply := Call(c, s, 5, 1000, "test"); reply.Value != 15 {
		t.Fatalf("%+v", reply)
	}
	for restart := int64(1); restart <= 2; restart++ {
		if reply := Call(c, s, 0, 1000, "test"); !strings.Contains(reply.Error, "bad request") {
			t.Fatalf("%+v", reply)
		}
		// The replacement starts again from the initial state.
		if reply := Call(c, s, 1, 3000, "test"); reply.Error != "" || reply.Value != 11 {
			t.Fatalf("after restart %d: %+v", restart, reply)
		}
		if got := ServerRestarts(c, s, "test"); got != restart {
			t.Fatalf("restarts=%d want %d", got, restart)
		}
	}
	// A third failure exceeds the restart limit and ends the server for good.
	Call(c, s, 0, 1000, "test")
	eventually(t, func() bool { return !ServerAlive(c, s, "test") })
	if reply := Call(c, s, 1, 1000, "test"); reply.Error != "server is not running" {
		t.Fatalf("%+v", reply)
	}
	if !AwaitServer(c, s, 1000, "test").E0 {
		t.Fatal("supervisor still running")
	}
}

func TestSupervisedServerStops(t *testing.T) {
	c := root(t)
	s := StartSupervisedServer(c, int64(0), func(_ *Context, state, value int64) step {
		return step{state + value, state + value}
	}, 1, 1000, "test")
	if reply := Call(c, s, 2, 1000, "test"); reply.Value != 2 || !Cast(c, s, 1, "test") {
		t.Fatalf("%+v", reply)
	}
	if !StopServer(c, s, "test") || !AwaitServer(c, s, 2000, "test").E0 || StopServer(c, s, "test") {
		t.Fatal("stop")
	}
	if reply := Call(c, s, 1, 1000, "test"); reply.Error != "server is not running" {
		t.Fatalf("%+v", reply)
	}
}
