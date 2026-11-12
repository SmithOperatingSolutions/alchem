package actor

import "testing"

// These benchmarks track the runtime's hot paths. Compare before and after a
// change with: go test -run '^$' -bench . -benchmem ./compiler/actor

func BenchmarkCheck(b *testing.B) {
	root := NewRoot()
	defer Close(root, 1000)
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		Check(root)
	}
}

func BenchmarkSpawnJoin(b *testing.B) {
	root := NewRoot()
	defer Close(root, 1000)
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		pid := Spawn(root, func(*Context, *PID[int64]) int64 { return 0 }, 1, "bench")
		Await(root, pid, -1, "bench")
	}
}

type benchRequest struct {
	E0 *PID[int64]
	E1 int64
}

func BenchmarkRoundTrip(b *testing.B) {
	root := NewRoot()
	defer Close(root, 1000)
	me := Self[int64](root, 1, "bench")
	server := Spawn(root, func(c *Context, self *PID[benchRequest]) int64 {
		for {
			message := Receive(c, self, -1, "bench")
			Send(c, message.E1.E0, message.E1.E1, -1, "bench")
		}
	}, 1, "bench")
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		Send(root, server, benchRequest{me, int64(i)}, -1, "bench")
		Receive(root, me, -1, "bench")
	}
}

func BenchmarkSendStructuredMessage(b *testing.B) {
	root := NewRoot()
	defer Close(root, 1000)
	me := Self[map[string][]int64](root, 1, "bench")
	message := map[string][]int64{"a": {1, 2, 3}, "b": {4, 5, 6}}
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		Send(root, me, message, -1, "bench")
		Receive(root, me, -1, "bench")
	}
}

// One supervised crash, restart and lookup of the replacement.
func BenchmarkCrashAndRestart(b *testing.B) {
	root := NewRoot()
	defer Close(root, 5000)
	sup := StartSupervisor(root, "one_for_one", 1000000, 1, specifications(1, "permanent", func(c *Context, self *PID[int64]) int64 {
		Receive(c, self, -1, "bench.alc:1:1")
		Fail(c, "bench.alc:1:1", "requested")
		return 0
	}), 1, "bench")
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		doomed := Child(root, sup, "a", "bench")
		Send(root, doomed, 1, -1, "bench")
		Await(root, doomed, -1, "bench")
		for Child(root, sup, "a", "bench") == doomed {
			Sleep(root, 0, "bench")
		}
	}
}
