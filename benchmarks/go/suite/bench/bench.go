// Package bench times one benchmark case inside the running program.
package bench

import (
	"fmt"
	"slices"
	"time"
)

// Run calls work twice to warm up and seven more times, then prints the case
// name, the median and fastest time in microseconds and the value work
// returned, separated by tabs.
func Run(name string, work func() int) {
	var times []int64
	check := 0
	for i := 0; i < 9; i++ {
		started := time.Now()
		check = work()
		if i >= 2 {
			times = append(times, time.Since(started).Microseconds())
		}
	}
	slices.Sort(times)
	fmt.Printf("%s\t%d\t%d\t%d\n", name, times[3], times[0], check)
}
