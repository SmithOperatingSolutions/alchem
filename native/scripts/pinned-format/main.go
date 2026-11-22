package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

// For each file named, one line: the text Format gives, as JSON, or its error.
func main() {
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	for _, path := range os.Args[1:] {
		data, err := os.ReadFile(path)
		if err != nil {
			fmt.Fprintln(out, path, "unreadable")
			continue
		}
		text, err := compiler.Format(string(data))
		var line []byte
		if err != nil {
			line, _ = json.Marshal([]any{path, "error", err.Error()})
		} else {
			line, _ = json.Marshal([]any{path, text})
		}
		fmt.Fprintln(out, string(line))
	}
}
