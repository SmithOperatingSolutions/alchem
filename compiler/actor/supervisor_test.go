package actor

import (
	"testing"
	"time"
)

func specifications(n int, policy string, fn func(*Context, *PID[int64]) int64) []struct {
	E0 string
	E1 string
	E2 func(*Context, *PID[int64]) int64
} {
	out := make([]struct {
		E0 string
		E1 string
		E2 func(*Context, *PID[int64]) int64
	}, n)
	for i := range out {
		out[i].E0 = string(rune('a' + i))
		out[i].E1 = policy
		out[i].E2 = fn
	}
	return out
}
func eventually(t *testing.T, fn func() bool) {
	t.Helper()
	until := time.Now().Add(3 * time.Second)
	for time.Now().Before(until) {
		if fn() {
			return
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatal("condition timed out")
}
func TestStrategies(t *testing.T) {
	for _, strategy := range []string{"one_for_one", "one_for_all", "rest_for_one"} {
		t.Run(strategy, func(t *testing.T) {
			c := root(t)
			s := StartSupervisor(c, strategy, 5, 1000, specifications(3, "permanent", func(child *Context, p *PID[int64]) int64 {
				Receive(child, p, -1, "test")
				return Crash(child, "boom", "test")
			}), 2, "test")
			before := Children(c, s, "test")
			pid := Child(c, s, "b", "test")
			Send(c, pid, 1, 1000, "test")
			eventually(t, func() bool {
				after := Children(c, s, "test")
				for i := range after {
					want := strategy == "one_for_all" || i == 1 || (strategy == "rest_for_one" && i == 2)
					if (after[i].E1 != before[i].E1) != want {
						return false
					}
				}
				return true
			})
			if Restarts(c, s, "test") != 1 {
				t.Fatal("restart count")
			}
			if !StopSupervisor(c, s, 1000, "test") {
				t.Fatal("shutdown")
			}
			if got := AwaitSupervisor(c, s, 0, "test"); !got.E0 || got.E1 != "shutdown" {
				t.Fatalf("%v", got)
			}
		})
	}
}
func TestPoliciesAndIntensity(t *testing.T) {
	for _, policy := range []string{"permanent", "transient", "temporary"} {
		t.Run(policy, func(t *testing.T) {
			c := root(t)
			s := StartSupervisor(c, "one_for_one", 2, 1000, specifications(1, policy, func(*Context, *PID[int64]) int64 { return 0 }), 1, "test")
			pid := Child(c, s, "a", "test")
			if !Await(c, pid, 1000, "test").E0 {
				t.Fatal("child exit")
			}
			if policy == "permanent" {
				got := AwaitSupervisor(c, s, 1000, "test")
				if !got.E0 || got.E1 != "restart_intensity" || Restarts(c, s, "test") != 2 {
					t.Fatalf("%v", got)
				}
			} else {
				if !SupervisorAlive(c, s, "test") || Restarts(c, s, "test") != 0 {
					t.Fatal("normal child was restarted")
				}
				StopSupervisor(c, s, 1000, "test")
			}
		})
	}
	for _, policy := range []string{"transient", "temporary"} {
		c := root(t)
		s := StartSupervisor(c, "one_for_one", 1, 1000, specifications(1, policy, func(child *Context, _ *PID[int64]) int64 { return Crash(child, "bad", "test") }), 1, "test")
		if policy == "transient" {
			got := AwaitSupervisor(c, s, 1000, "test")
			if !got.E0 || got.E1 != "restart_intensity" {
				t.Fatalf("%v", got)
			}
		} else {
			if !Await(c, Child(c, s, "a", "test"), 1000, "test").E0 || !SupervisorAlive(c, s, "test") {
				t.Fatal("temporary policy")
			}
			StopSupervisor(c, s, 1000, "test")
		}
	}
}
func TestRestartWindowAndNestedCleanup(t *testing.T) {
	c := root(t)
	s := StartSupervisor(c, "one_for_one", 1, 20, specifications(1, "permanent", func(child *Context, p *PID[int64]) int64 { Receive(child, p, -1, "test"); return 1 }), 1, "test")
	first := Child(c, s, "a", "test")
	Send(c, first, 1, 100, "test")
	eventually(t, func() bool { return ID(c, Child(c, s, "a", "test"), "test") != ID(c, first, "test") })
	Sleep(c, 30, "test")
	second := Child(c, s, "a", "test")
	Send(c, second, 1, 100, "test")
	eventually(t, func() bool { return ID(c, Child(c, s, "a", "test"), "test") != ID(c, second, "test") })
	if !SupervisorAlive(c, s, "test") {
		t.Fatal("restart window did not reset")
	}
	StopSupervisor(c, s, 1000, "test")
	outer := StartSupervisor(c, "one_for_one", 1, 1000, specifications(1, "permanent", func(child *Context, self *PID[int64]) int64 {
		StartLinkedSupervisor(child, "one_for_one", 0, 1000, specifications(1, "permanent", func(*Context, *PID[int64]) int64 { return 1 }), 1, "test")
		Receive(child, self, -1, "test")
		return 0
	}), 1, "test")
	got := AwaitSupervisor(c, outer, 2000, "test")
	if !got.E0 || got.E1 != "restart_intensity" {
		t.Fatalf("nested failure: %v", got)
	}
}

// The shutdown deadline is the last line of defence: a supervised child that
// never reaches a cancellation point must not keep the root from exiting.
func TestRunHonoursShutdownDeadlineWithStuckSupervisedChild(t *testing.T) {
	release := make(chan struct{})
	defer close(release)
	started := make(chan struct{})
	finished := make(chan int, 1)
	go func() {
		finished <- Run(func(c *Context) {
			StartSupervisor(c, "one_for_one", 1, 1000, specifications(1, "permanent", func(*Context, *PID[int64]) int64 {
				close(started)
				<-release
				return 0
			}), 1, "test")
			<-started
		}, nil, false, 20, 0)
	}()
	select {
	case code := <-finished:
		if code != 2 {
			t.Fatalf("exit code %d", code)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("Run ignored the shutdown deadline")
	}
}

// Looking up a child takes no lock, so a client polling for a replacement
// cannot starve the supervisor creating it, and always sees either the old
// PID or a fully started new one. A zero-length sleep yields between polls.
func TestChildLookupWhileRestarting(t *testing.T) {
	c := root(t)
	sup := StartSupervisor(c, "one_for_one", 1000000, 1, specifications(1, "permanent", func(child *Context, self *PID[int64]) int64 {
		Receive(child, self, -1, "worker.alc:1:1")
		Fail(child, "worker.alc:1:1", "requested")
		return 0
	}), 1, "test")
	seen := map[int64]bool{}
	for i := 0; i < 200; i++ {
		doomed := Child(c, sup, "a", "test")
		if seen[ID(c, doomed, "test")] {
			t.Fatalf("cycle %d returned a PID that had already been replaced", i)
		}
		seen[ID(c, doomed, "test")] = true
		if !Send(c, doomed, 1, 1000, "test") {
			t.Fatalf("cycle %d: replacement was not ready to receive", i)
		}
		if result := Await(c, doomed, 3000, "test"); !result.E0 || result.E1 != "requested" {
			t.Fatalf("cycle %d: %+v", i, result)
		}
		if report := Report(c, doomed, "test"); report != "worker.alc:1:1: requested" {
			t.Fatalf("cycle %d: report %q", i, report)
		}
		deadline := time.Now().Add(3 * time.Second)
		for Child(c, sup, "a", "test") == doomed {
			if time.Now().After(deadline) {
				t.Fatalf("cycle %d: no replacement", i)
			}
			Sleep(c, 0, "test")
		}
	}
	if Restarts(c, sup, "test") < 200 {
		t.Fatalf("restarts %d", Restarts(c, sup, "test"))
	}
}
