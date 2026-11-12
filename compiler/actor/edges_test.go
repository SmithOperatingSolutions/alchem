package actor

import (
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// failsWith runs body in a process of its own and reports the reason it
// ended with.
func failsWith(t *testing.T, c *Context, body func(*Context)) string {
	t.Helper()
	p := Spawn(c, func(w *Context, _ *PID[struct{}]) int64 {
		body(w)
		return 0
	}, 1, "test")
	result := Await(c, p, 5000, "test")
	if !result.E0 {
		t.Fatal("the process did not end")
	}
	return result.E1
}

// A fake handle to a process of another program, which records what it is
// asked and reports its exit when told to.
type fakeRemote struct {
	exits    atomic.Int64
	reason   atomic.Value
	watching chan *Context
}

func newFakeRemote() (*fakeRemote, *PID[string]) {
	f := &fakeRemote{watching: make(chan *Context, 4)}
	return f, RemotePID(&Remote[string]{
		Node: "far", ID: 7,
		Send: func(string) bool { return true },
		Monitor: func(c *Context) int64 {
			f.watching <- c
			return NextReference(c)
		},
		Demonitor: func(int64) bool { return true },
		Alive:     func() bool { return true },
		Exit: func(reason string) bool {
			f.exits.Add(1)
			f.reason.Store(reason)
			return true
		},
	})
}

func TestLinksToProcessesOfOtherPrograms(t *testing.T) {
	c := root(t)
	// The far process ends abnormally: the linked one ends too.
	fake, far := newFakeRemote()
	linked := Spawn(c, func(w *Context, _ *PID[int64]) int64 {
		if !Link(w, far, "test") {
			Fail(w, "test", "not linked")
		}
		Sleep(w, 5000, "test")
		return 0
	}, 1, "test")
	watcher := <-fake.watching
	Notify(watcher, Event{Ref: 1, PID: 7, Reason: "crashed"})
	if result := Await(c, linked, 5000, "test"); !result.E0 || !strings.Contains(result.E1, "linked: crashed") {
		t.Fatalf("linked process: %+v", result)
	}
	// A process that traps exits is told instead.
	fake2, far2 := newFakeRemote()
	trapping := Spawn(c, func(w *Context, _ *PID[int64]) int64 {
		Trap(w, true)
		Link(w, far2, "test")
		event := NextEvent(w, 5000)
		if !event.E0 || event.E3 != "crashed" {
			Fail(w, "test", "no exit event")
		}
		return 0
	}, 1, "test")
	Notify(<-fake2.watching, Event{Ref: 1, PID: 7, Reason: "crashed"})
	if result := Await(c, trapping, 5000, "test"); result.E1 != "normal" {
		t.Fatalf("trapping process: %+v", result)
	}
	// A linked process that fails tells the far one; after unlinking, it
	// does not.
	fake3, far3 := newFakeRemote()
	failing := Spawn(c, func(w *Context, _ *PID[int64]) int64 {
		Link(w, far3, "test")
		Fail(w, "test", "boom")
		return 0
	}, 1, "test")
	Await(c, failing, 5000, "test")
	eventually(t, func() bool { return fake3.exits.Load() == 1 })
	fake4, far4 := newFakeRemote()
	unlinked := Spawn(c, func(w *Context, _ *PID[int64]) int64 {
		Link(w, far4, "test")
		if !Unlink(w, far4, "test") || Unlink(w, far4, "test") {
			Fail(w, "test", "unlink")
		}
		Fail(w, "test", "boom")
		return 0
	}, 1, "test")
	Await(c, unlinked, 5000, "test")
	time.Sleep(50 * time.Millisecond)
	if fake4.exits.Load() != 0 {
		t.Fatal("an unlinked process was told of an exit")
	}
	// A handle without the means to link is not linked.
	if Link(c, RemotePID(&Remote[string]{Node: "far", ID: 8}), "test") {
		t.Fatal("linked without an Exit")
	}
}

func TestExitLinkedFromOtherPrograms(t *testing.T) {
	c := root(t)
	normal := Spawn(c, func(w *Context, _ *PID[int64]) int64 {
		Sleep(w, 200, "test")
		return 0
	}, 1, "test")
	ExitLinked(normal, 7, "normal")
	if result := Await(c, normal, 5000, "test"); result.E1 != "normal" {
		t.Fatalf("a normal exit ended a linked process: %+v", result)
	}
	ExitLinked(normal, 7, "crashed")
	ended := Spawn(c, func(w *Context, _ *PID[int64]) int64 {
		Sleep(w, 5000, "test")
		return 0
	}, 1, "test")
	ExitLinked(ended, 7, "crashed")
	if result := Await(c, ended, 5000, "test"); !strings.Contains(result.E1, "linked: crashed") {
		t.Fatalf("an abnormal exit did not end a linked process: %+v", result)
	}
}

func TestDeliveryAndArgumentFailures(t *testing.T) {
	c := root(t)
	full := Spawn(c, func(w *Context, _ *PID[int64]) int64 {
		Sleep(w, 5000, "test")
		return 0
	}, 1, "test")
	if !Deliver(full, 1, time.Second) || Deliver(full, 2, 20*time.Millisecond) {
		t.Fatal("a full mailbox took a second message")
	}
	Stop(c, full, "test")
	Await(c, full, 5000, "test")
	if Deliver(full, 3, time.Second) {
		t.Fatal("a stopped process took a message")
	}
	for want, body := range map[string]func(*Context){
		"mailbox capacity":           func(w *Context) { Spawn(w, func(*Context, *PID[int64]) int64 { return 0 }, 0, "test") },
		"mailbox capacity must be 1": func(w *Context) { Self[int64](w, 0, "test") },
		"invalid PID":                func(w *Context) { SendAfter[int64](w, nil, 1, 10, "test") },
		"invalid supervision limits": func(w *Context) { StartDynamicSupervisor(w, -1, 1000, "test") },
		"restart is permanent": func(w *Context) {
			s := StartDynamicSupervisor(w, 1, 1000, "test")
			StartDynamicChild(w, s, func(*Context, *PID[int64]) int64 { return 0 }, "sometimes", "test")
		},
	} {
		if reason := failsWith(t, c, body); !strings.Contains(reason, want) {
			t.Errorf("%s: ended with %q", want, reason)
		}
	}
	// A timer to a process of another program sends to it.
	fake, far := newFakeRemote()
	_ = fake
	if ref := SendAfter(c, far, "later", 1, "test"); ref == 0 {
		t.Fatal("no timer")
	}
	// A remote process's exit reaches a server it is turned into a request for.
	log := StartServer(c, []string{}, func(_ *Context, seen []string, event string) struct {
		E0 []string
		E1 []string
	} {
		seen = append(seen, event)
		return struct {
			E0 []string
			E1 []string
		}{seen, seen}
	}, "test")
	fake2, far2 := newFakeRemote()
	ServerMonitor(c, log, far2, func(_ *Context, reason string) string { return "down " + reason }, "test")
	Notify(<-fake2.watching, Event{Ref: 1, PID: 7, Reason: "gone"})
	eventually(t, func() bool {
		reply := Call(c, log, "check", 1000, "test")
		return len(reply.Value) >= 2
	})
	if failsWith(t, c, func(w *Context) { ServerMonitor[string, []string, string](w, log, nil, nil, "test") }) == "normal" {
		t.Fatal("a nil pid was monitored")
	}
}
