package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// For each file named, one line: the tree ParseModule gives, the module as
// the loader reads it once it is lowered, as JSON, or its error.
func main() {
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	for _, path := range os.Args[1:] {
		data, err := os.ReadFile(path)
		if err != nil {
			fmt.Fprintln(out, path, "unreadable")
			continue
		}
		program, err := syntax.ParseModule(string(data))
		var line []byte
		if err != nil {
			line, _ = json.Marshal([]any{path, "error", err.Error()})
		} else {
			line, _ = json.Marshal([]any{path, program})
		}
		fmt.Fprintln(out, string(line))
	}
}
