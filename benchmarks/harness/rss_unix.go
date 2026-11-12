//go:build unix

package main

import (
	"os"
	"runtime"
	"syscall"
)

// peakRSS reports the child's peak resident set size in bytes.
func peakRSS(state *os.ProcessState) int64 {
	usage, ok := state.SysUsage().(*syscall.Rusage)
	if !ok {
		return 0
	}
	if runtime.GOOS == "darwin" || runtime.GOOS == "ios" {
		return int64(usage.Maxrss) // already bytes
	}
	return int64(usage.Maxrss) * 1024 // kilobytes elsewhere
}
