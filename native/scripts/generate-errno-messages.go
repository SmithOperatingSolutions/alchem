//go:build ignore

// Regenerate spec/errno-messages.json from the pinned Go syscall.Errno.Error
// table, which os.PathError messages (File.read errors) use. Development step:
// go run scripts/generate-errno-messages.go > spec/errno-messages.json
package main

import (
	"fmt"
	"runtime"
	"strconv"
	"syscall"
)

func main() {
	// Errno.Error falls back to "errno N" past the table; record where that starts.
	last := 0
	for e := 1; e < 4096; e++ {
		if syscall.Errno(e).Error() != "errno "+strconv.Itoa(e) {
			last = e
		}
	}
	fmt.Printf("{\n \"go\": %q,\n \"goos\": %q,\n \"goarch\": %q,\n \"messages\": [\n", runtime.Version(), runtime.GOOS, runtime.GOARCH)
	for e := 0; e <= last; e++ {
		separator := ","
		if e == last {
			separator = ""
		}
		fmt.Printf("  %q%s\n", syscall.Errno(e).Error(), separator)
	}
	fmt.Println(" ]\n}")
}
