package actor

import (
	"runtime"
	"sync"
	"testing"
)

// The stated budget for 100,000 simultaneously live processes is 512 MiB of
// memory obtained from the operating system (about 5 KiB per process), or
// 1280 MiB on Windows, where Go reserves a larger minimum goroutine stack.
// The measurements recorded in docs/benchmarks.md sit below both; this test
// fails if a runtime change pushes per-process cost past the budget.
func TestHundredThousandProcessesWithinMemoryBudget(t *testing.T) {
	if testing.Short() || raceEnabled {
		t.Skip("scale measurement is skipped in short and race-instrumented runs")
	}
	const processes = 100000
	budget := uint64(512 << 20)
	if runtime.GOOS == "windows" {
		budget = 1280 << 20
	}
	root := NewRoot()
	var before, after runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&before)
	var started sync.WaitGroup
	started.Add(processes)
	pids := make([]*PID[int64], processes)
	for i := range pids {
		pids[i] = Spawn(root, func(c *Context, self *PID[int64]) int64 {
			started.Done()
			if !Receive(c, self, -1, "test").E0 {
				return 1
			}
			return 0
		}, 1, "test")
	}
	started.Wait()
	runtime.ReadMemStats(&after)
	used := after.Sys - before.Sys
	t.Logf("%d live processes: %.1f MiB from the OS, %.2f KiB per process", processes, float64(used)/(1<<20), float64(used)/processes/1024)
	for _, pid := range pids {
		if !Send(root, pid, 1, -1, "test") {
			t.Fatal("send failed")
		}
	}
	for _, pid := range pids {
		if result := Await(root, pid, -1, "test"); !result.E0 || result.E1 != "normal" {
			t.Fatalf("worker ended with %+v", result)
		}
	}
	if !Close(root, 10000) {
		t.Fatal("runtime did not shut down")
	}
	if used > budget {
		t.Fatalf("%d bytes exceeds the %d byte budget", used, budget)
	}
}
