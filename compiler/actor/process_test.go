package actor

import (
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func root(t testing.TB) *Context {
	t.Helper()
	c := NewRoot()
	t.Cleanup(func() {
		if !Close(c, 3000) {
			t.Error("runtime leaked tasks")
		}
	})
	return c
}

// Messages are shared, not copied: Alchem values are immutable, so no program
// can observe the difference. The mailbox preserves order, grows on demand to
// its capacity and refuses more.
func TestMailboxOwnershipSharingAndFIFO(t *testing.T) {
	c := root(t)
	p := Self[map[string][]int64](c, 3, "test")
	first := map[string][]int64{"a": {1, 2}}
	for _, message := range []map[string][]int64{first, {"b": {3}}, {"c": {4}}} {
		if !Send(c, p, message, 0, "test") {
			t.Fatal("send")
		}
	}
	if Send(c, p, first, 0, "test") {
		t.Fatal("send beyond capacity succeeded")
	}
	got := Receive(c, p, 0, "test")
	if !got.E0 || len(got.E1["a"]) != 2 || &got.E1["a"][0] != &first["a"][0] {
		t.Fatalf("first message was not delivered by reference: %v", got)
	}
	// Wrap the ring: free one slot, refill it, and drain in order.
	if !Send(c, p, map[string][]int64{"d": {5}}, 0, "test") {
		t.Fatal("send after receive")
	}
	for _, key := range []string{"b", "c", "d"} {
		if next := Receive(c, p, 0, "test"); !next.E0 || next.E1[key] == nil {
			t.Fatalf("expected %q next, got %v", key, next)
		}
	}
	if extra := Receive(c, p, 0, "test"); extra.E0 {
		t.Fatalf("unexpected message %v", extra)
	}
	bad := Spawn(c, func(child *Context, self *PID[int64]) int64 { Receive(child, p, 0, "owner.alc:1:1"); return 0 }, 1, "test")
	result := Await(c, bad, 1000, "test")
	if !result.E0 || result.E1 != "only the mailbox owner may receive" {
		t.Fatalf("got %v", result)
	}
}
func TestBoundedSendReceiveStop(t *testing.T) {
	c := root(t)
	p := Self[int64](c, 2, "test")
	Send(c, p, 1, 0, "test")
	Send(c, p, 2, 0, "test")
	if Send(c, p, 3, 5, "test") {
		t.Fatal("mailbox exceeded capacity")
	}
	for _, want := range []int64{1, 2} {
		if got := Receive(c, p, 0, "test"); !got.E0 || got.E1 != want {
			t.Fatalf("got %v", got)
		}
	}
	if Receive(c, p, 1, "test").E0 {
		t.Fatal("timeout")
	}
	worker := Spawn(c, func(child *Context, self *PID[int64]) int64 { Receive(child, self, -1, "test"); return 0 }, 1, "test")
	if !Stop(c, worker, "test") {
		t.Fatal("stop")
	}
	if result := Await(c, worker, 1000, "test"); !result.E0 || result.E1 != "shutdown" {
		t.Fatalf("%v", result)
	}
	if Send(c, worker, 1, 0, "test") || Alive(c, worker, "test") {
		t.Fatal("dead process accepted message")
	}
}
func TestMonitorsLinksAndDemonitor(t *testing.T) {
	c := root(t)
	Trap(c, true)
	p := Spawn(c, func(child *Context, self *PID[int64]) int64 {
		Receive(child, self, -1, "test")
		return Crash(child, "boom", "worker.alc:3:1")
	}, 1, "test")
	ref := Monitor(c, p, "test")
	if !Link(c, p, "test") {
		t.Fatal("link")
	}
	Send(c, p, 1, 100, "test")
	if got := Await(c, p, 1000, "test"); !got.E0 || got.E1 != "boom" {
		t.Fatalf("%v", got)
	}
	seen := map[int64]bool{}
	for i := 0; i < 2; i++ {
		e := NextEvent(c, 1000)
		if !e.E0 || e.E2 != ID(c, p, "test") || e.E3 != "boom" {
			t.Fatalf("%v", e)
		}
		seen[e.E1] = true
	}
	if !seen[0] || !seen[ref] {
		t.Fatalf("events=%v", seen)
	}
	ref = Monitor(c, p, "test")
	if !Demonitor(c, p, ref, "test") || NextEvent(c, 0).E0 {
		t.Fatal("demonitor did not flush")
	}
}
func TestRaceLifecycle(t *testing.T) {
	c := root(t)
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			p := Spawn(c, func(child *Context, self *PID[int64]) int64 { Sleep(child, 1, "test"); return 0 }, 1, "test")
			Send(c, p, 1, 0, "test")
			Stop(c, p, "test")
			if !Await(c, p, 2000, "test").E0 {
				t.Error("join timed out")
			}
		}()
	}
	wg.Wait()
	start := time.Now()
	if !Close(c, 1000) || time.Since(start) > time.Second {
		t.Fatal("cleanup")
	}
}

// Fifty processes contend for an eight-slot mailbox. Each sender is its own
// process: a context belongs to exactly one goroutine, as in generated code.
func TestBlockedSendersWake(t *testing.T) {
	c := root(t)
	p := Self[int64](c, 8, "test")
	var next atomic.Int64
	senders := make([]*PID[int64], 50)
	for i := range senders {
		senders[i] = Spawn(c, func(child *Context, _ *PID[int64]) int64 {
			if !Send(child, p, next.Add(1), 2000, "test") {
				return 1
			}
			return 0
		}, 1, "test")
	}
	seen := map[int64]bool{}
	for i := 0; i < 50; i++ {
		got := Receive(c, p, 2000, "test")
		if !got.E0 || seen[got.E1] {
			t.Fatalf("message %v", got)
		}
		seen[got.E1] = true
	}
	for _, sender := range senders {
		if result := Await(c, sender, 2000, "test"); !result.E0 || result.E1 != "normal" {
			t.Fatalf("sender ended with %+v", result)
		}
	}
}

func TestUntrappedLinksAndUnlink(t *testing.T) {
	for _, unlink := range []bool{false, true} {
		c := root(t)
		victim := Spawn(c, func(child *Context, self *PID[int64]) int64 {
			target := Spawn(child, func(targetContext *Context, p *PID[int64]) int64 {
				Receive(targetContext, p, -1, "test")
				return Crash(targetContext, "linked failure", "test")
			}, 1, "test")
			Link(child, target, "test")
			if unlink {
				Unlink(child, target, "test")
			}
			Send(child, target, 1, 1000, "test")
			Await(child, target, 1000, "test")
			Check(child)
			return 0
		}, 1, "test")
		got := Await(c, victim, 2000, "test")
		want := "linked: linked failure"
		if unlink {
			want = "normal"
		}
		if !got.E0 || got.E1 != want {
			t.Fatalf("unlink=%v got %v", unlink, got)
		}
	}
}

func TestCrashCannotMasqueradeAsNormalExit(t *testing.T) {
	c := root(t)
	for _, reason := range []string{"normal", "shutdown"} {
		p := Spawn(c, func(child *Context, _ *PID[int64]) int64 { return Crash(child, reason, "test") }, 1, "test")
		result := Await(c, p, 1000, "test")
		if !result.E0 || result.E1 != "error: "+reason {
			t.Fatalf("%v", result)
		}
	}
}

func TestTrappedNormalExit(t *testing.T) {
	c := root(t)
	Trap(c, true)
	p := Spawn(c, func(child *Context, self *PID[int64]) int64 { Receive(child, self, -1, "test"); return 0 }, 1, "test")
	Link(c, p, "test")
	Send(c, p, 1, 1000, "test")
	e := NextEvent(c, 1000)
	if !e.E0 || e.E1 != 0 || e.E2 != ID(c, p, "test") || e.E3 != "normal" {
		t.Fatalf("%v", e)
	}
}

func TestConstantStackStateLoop(t *testing.T) {
	c := root(t)
	firstDepth, lastDepth := 0, 0
	result := Loop(c, int64(0), func(ctx *Context, n int64) struct {
		E0 bool
		E1 int64
	} {
		if n == 0 || n == 99999 {
			pcs := make([]uintptr, 256)
			depth := runtime.Callers(0, pcs)
			if n == 0 {
				firstDepth = depth
			} else {
				lastDepth = depth
			}
		}
		return struct {
			E0 bool
			E1 int64
		}{n < 99999, n + 1}
	}, "test")
	if firstDepth == 0 || lastDepth > firstDepth+2 {
		t.Fatalf("stack grew from %d to %d", firstDepth, lastDepth)
	}
	if result != 100000 {
		t.Fatalf("state=%d", result)
	}
	p := Spawn(c, func(child *Context, _ *PID[int64]) int64 {
		return Loop(child, int64(0), func(*Context, int64) struct {
			E0 bool
			E1 int64
		} {
			return struct {
				E0 bool
				E1 int64
			}{true, 0}
		}, "test")
	}, 1, "test")
	Sleep(c, 1, "test")
	Stop(c, p, "test")
	if got := Await(c, p, 1000, "test"); !got.E0 || got.E1 != "shutdown" {
		t.Fatalf("loop not canceled: %v", got)
	}
}

// A selective receive takes the oldest message its function accepts and
// leaves the rest in order, including when the ring buffer has wrapped; it
// waits for a message a sender delivers later, wakes a sender blocked on a
// full mailbox, and gives up at its deadline.
func TestReceiveMatchingLeavesOtherMessages(t *testing.T) {
	c := root(t)
	p := Self[int64](c, 4, "test")
	even := func(_ *Context, n int64) bool { return n%2 == 0 }
	// Wrap the ring before filling it.
	for _, n := range []int64{9, 9} {
		Send(c, p, n, 0, "test")
	}
	Receive(c, p, 0, "test")
	Receive(c, p, 0, "test")
	for _, n := range []int64{1, 3, 4, 6} {
		if !Send(c, p, n, 0, "test") {
			t.Fatal("send")
		}
	}
	if got := ReceiveMatching(c, p, 0, even, "test"); !got.E0 || got.E1 != 4 {
		t.Fatalf("first even message: %v", got)
	}
	if pending := Pending(p); len(pending) != 3 || pending[0] != 1 || pending[1] != 3 || pending[2] != 6 {
		t.Fatalf("mailbox after taking from the middle: %v", pending)
	}
	if got := ReceiveMatching(c, p, 0, func(_ *Context, n int64) bool { return n > 100 }, "test"); got.E0 {
		t.Fatalf("nothing should match: %v", got)
	}
	started := time.Now()
	if got := ReceiveMatching(c, p, 30, func(_ *Context, n int64) bool { return n > 100 }, "test"); got.E0 || time.Since(started) < 25*time.Millisecond {
		t.Fatalf("deadline not honoured: %v after %v", got, time.Since(started))
	}
	// The mailbox holds 1, 3, 6: one more fills it. A sender then blocks,
	// and taking a message from the middle makes the room it is waiting for.
	Send(c, p, 5, 0, "test")
	sender := Spawn(c, func(child *Context, self *PID[int64]) int64 {
		if !Send(child, p, 7, 2000, "test") {
			return 1
		}
		return 0
	}, 1, "test")
	time.Sleep(20 * time.Millisecond)
	if got := ReceiveMatching(c, p, 2000, even, "test"); !got.E0 || got.E1 != 6 {
		t.Fatalf("even message from a full mailbox: %v", got)
	}
	if result := Await(c, sender, 1000, "test"); !result.E0 || result.E1 != "normal" {
		t.Fatalf("sender: %v", result)
	}
	// A message that arrives while waiting is found.
	late := Spawn(c, func(child *Context, self *PID[int64]) int64 {
		Sleep(child, 20, "test")
		Receive(child, self, 2000, "test")
		Send(child, p, 200, 2000, "test")
		return 0
	}, 1, "test")
	if got := Receive(c, p, 0, "test"); !got.E0 || got.E1 != 1 {
		t.Fatalf("oldest message: %v", got)
	}
	Send(c, late, 0, 100, "test")
	if got := ReceiveMatching(c, p, 2000, func(_ *Context, n int64) bool { return n > 100 }, "test"); !got.E0 || got.E1 != 200 {
		t.Fatalf("message that arrived while waiting: %v", got)
	}
	Await(c, late, 1000, "test")
	for _, want := range []int64{3, 5, 7} {
		if got := Receive(c, p, 0, "test"); !got.E0 || got.E1 != want {
			t.Fatalf("expected %d next, got %v", want, got)
		}
	}
}
