package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"github.com/SmithOperatingSolutions/alchem/compiler/lexer"
)

// For each file named, one line: the tokens and comments as JSON, or the error.
func main() {
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	for _, path := range os.Args[1:] {
		data, err := os.ReadFile(path)
		if err != nil {
			fmt.Fprintln(out, path, "unreadable")
			continue
		}
		tokens, comments, err := lexer.ScanWithComments(string(data))
		if err != nil {
			line, _ := json.Marshal([]any{path, "error", err.Error()})
			fmt.Fprintln(out, string(line))
			continue
		}
		var t, c [][]any
		for _, k := range tokens {
			t = append(t, []any{string(k.Kind), k.Text, k.Line, k.Column})
		}
		for _, k := range comments {
			c = append(c, []any{k.Text, k.Line, k.Column})
		}
		line, _ := json.Marshal([]any{path, t, c})
		fmt.Fprintln(out, string(line))
	}
}
