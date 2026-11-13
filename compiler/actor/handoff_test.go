package actor

import (
	"sync"
	"testing"
)

// Messages from several senders reach a receiver that keeps parking, each
// sender's in the order it sent them, with none lost or repeated, whether
// they are handed over or queued.
func TestReceiveHandoffKeepsOrderAndLosesNothing(t *testing.T) {
	c := root(t)
	const senders, each = 8, 2000
	got := make(chan []int64, 1)
	receiver := Spawn(c, func(self *Context, me *PID[int64]) int64 {
		var all []int64
		for len(all) < senders*each {
			if r := Receive(self, me, 5000, "test"); r.E0 {
				all = append(all, r.E1)
			}
		}
		got <- all
		return 0
	}, 4, "test")
	var wg sync.WaitGroup
	for s := 0; s < senders; s++ {
		wg.Add(1)
		go func(s int64) {
			defer wg.Done()
			sender := Spawn(c, func(self *Context, _ *PID[struct{}]) int64 {
				for i := int64(0); i < each; i++ {
					if !Send(self, receiver, s*1_000_000+i, -1, "test") {
						t.Errorf("send %d/%d failed", s, i)
					}
				}
				return 0
			}, 1, "test")
			Await(c, sender, -1, "test")
		}(int64(s))
	}
	wg.Wait()
	all := <-got
	next := map[int64]int64{}
	for _, value := range all {
		s, i := value/1_000_000, value%1_000_000
		if i != next[s] {
			t.Fatalf("sender %d: got message %d, expected %d", s, i, next[s])
		}
		next[s]++
	}
	for s := int64(0); s < senders; s++ {
		if next[s] != each {
			t.Fatalf("sender %d: %d messages arrived of %d", s, next[s], each)
		}
	}
}

// A receive that times out while a message is being handed over still gets
// it, now or on the next receive: timeouts never drop messages.
func TestReceiveTimeoutsDoNotDropHandedMessages(t *testing.T) {
	c := root(t)
	const total = 3000
	got := make(chan int, 1)
	receiver := Spawn(c, func(self *Context, me *PID[int64]) int64 {
		count, timeouts := 0, 0
		for count < total {
			if r := Receive(self, me, 0, "test"); r.E0 {
				count++
				continue
			}
			if r := Receive(self, me, 1, "test"); r.E0 {
				count++
			} else {
				timeouts++
			}
		}
		got <- count
		return 0
	}, 2, "test")
	sender := Spawn(c, func(self *Context, _ *PID[struct{}]) int64 {
		for i := 0; i < total; i++ {
			Send(self, receiver, int64(i), -1, "test")
			if i%7 == 0 {
				Sleep(self, 1, "test")
			}
		}
		return 0
	}, 1, "test")
	Await(c, sender, -1, "test")
	if n := <-got; n != total {
		t.Fatalf("received %d of %d", n, total)
	}
}

// A receiver stopped while it waits ends, and a later send to it fails
// instead of handing a message to a process that is gone.
func TestStoppedWaitingReceiver(t *testing.T) {
	c := root(t)
	receiver := Spawn(c, func(self *Context, me *PID[int64]) int64 {
		Receive(self, me, -1, "test")
		return 0
	}, 1, "test")
	waitFor(t, func() bool {
		receiver.mu.Lock()
		defer receiver.mu.Unlock()
		return receiver.waiting
	})
	Stop(c, receiver, "test")
	if result := Await(c, receiver, 2000, "test"); !result.E0 {
		t.Fatal("the stopped receiver did not end")
	}
	if Send(c, receiver, 1, 0, "test") {
		t.Fatal("a send to an ended process succeeded")
	}
}
