package actor

import (
	"testing"
)

type counterRequest = int64

func counterHandler(_ *Context, total int64, n counterRequest) struct {
	E0 int64
	E1 int64
} {
	if n < 0 {
		panic(&Failure{Where: "test", Message: "negative"})
	}
	return struct {
		E0 int64
		E1 int64
	}{total + n, total + n}
}

func serverSpecs(names ...string) []struct {
	E0 string
	E1 string
	E2 func(*Context, *PID[struct{}]) int64
} {
	var specs []struct {
		E0 string
		E1 string
		E2 func(*Context, *PID[struct{}]) int64
	}
	for _, name := range names {
		specs = append(specs, struct {
			E0 string
			E1 string
			E2 func(*Context, *PID[struct{}]) int64
		}{name, "permanent", ServerChild[int64, int64, int64, struct{}](name, 0, counterHandler, "test")})
	}
	return specs
}

// A supervisor returns only once each server child has registered its name,
// so every name is found at once.
func TestServerChildrenAreRegisteredWhenTheSupervisorStarts(t *testing.T) {
	c := root(t)
	for round := 0; round < 50; round++ {
		s := StartSupervisor(c, "one_for_one", 5, 5000, serverSpecs("a", "b", "c"), 1, "test")
		for _, name := range []string{"a", "b", "c"} {
			server, ok := ServerWhereis[int64, int64](c, name)
			if !ok {
				t.Fatalf("round %d: %s is not registered when the supervisor returns", round, name)
			}
			if reply := Call(c, server, 1, 1000, "test"); reply.Error != "" || reply.Value != 1 {
				t.Fatalf("round %d: %s answered %+v", round, name, reply)
			}
		}
		if !StopSupervisor(c, s, 1000, "test") {
			t.Fatal("stop")
		}
		waitFor(t, func() bool {
			_, ok := ServerWhereis[int64, int64](c, "a")
			return !ok
		})
	}
}

// A failed server is replaced by one with the initial state under its name,
// and a stopped supervisor leaves no server behind.
func TestServerChildRestartsAndStops(t *testing.T) {
	c := root(t)
	s := StartSupervisor(c, "one_for_one", 5, 5000, serverSpecs("restarting"), 1, "test")
	first, _ := ServerWhereis[int64, int64](c, "restarting")
	if reply := Call(c, first, 7, 1000, "test"); reply.Value != 7 {
		t.Fatalf("first reply %+v", reply)
	}
	Cast(c, first, -1, "test")
	waitFor(t, func() bool { return Restarts(c, s, "test") == 1 })
	waitFor(t, func() bool {
		replacement, ok := ServerWhereis[int64, int64](c, "restarting")
		return ok && replacement != first
	})
	replacement, _ := ServerWhereis[int64, int64](c, "restarting")
	if reply := Call(c, replacement, 1, 1000, "test"); reply.Value != 1 {
		t.Fatalf("the replacement kept the old state: %+v", reply)
	}
	if !StopSupervisor(c, s, 1000, "test") {
		t.Fatal("stop")
	}
	waitFor(t, func() bool { return !ServerAlive(c, replacement, "test") })
}

// A child that cannot register its name fails, and the supervisor does not
// wait on it for ever.
func TestServerChildWithATakenName(t *testing.T) {
	c := root(t)
	first := StartSupervisor(c, "one_for_one", 5, 5000, serverSpecs("taken"), 1, "test")
	second := StartSupervisor(c, "one_for_one", 1, 5000, serverSpecs("taken"), 1, "test")
	if result := AwaitSupervisor(c, second, 3000, "test"); !result.E0 || result.E1 != "restart_intensity" {
		t.Fatalf("second supervisor: %+v", result)
	}
	StopSupervisor(c, first, 1000, "test")
}
