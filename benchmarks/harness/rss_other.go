//go:build !unix

package main

import "os"

// peakRSS is unavailable on this platform; zero is reported as "n/a".
func peakRSS(*os.ProcessState) int64 { return 0 }
