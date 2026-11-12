package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler"
	"github.com/SmithOperatingSolutions/alchem/guide"
)

var helpRequest = regexp.MustCompile(`^h(?:\s+|\()\s*([A-Za-z_][\w.?!]*)\s*\)?\s*$`)

// shell runs alchem alx: it reads inputs, a line or a block at a time, and
// prints what each printed and its value.
func shell(ctx context.Context, in io.Reader, out io.Writer) int {
	dir, _ := os.Getwd()
	s := &compiler.Shell{Dir: dir}
	fmt.Fprintln(out, "alx, the Alchem Language Executor. Each input is compiled and run with the ones before it.")
	fmt.Fprintln(out, "h Module.function shows documentation, :reset forgets everything, :quit or ctrl-D leaves.")
	reader := bufio.NewReader(in)
	number := 1
	var pending []string
	for {
		if len(pending) == 0 {
			fmt.Fprintf(out, "alx(%d)> ", number)
		} else {
			fmt.Fprintf(out, "...(%d)> ", number)
		}
		line, err := reader.ReadString('\n')
		if err != nil && line == "" {
			fmt.Fprintln(out)
			return 0
		}
		line = strings.TrimRight(line, "\r\n")
		if len(pending) == 0 {
			switch trimmed := strings.TrimSpace(line); {
			case trimmed == ":quit" || trimmed == "exit":
				return 0
			case trimmed == ":reset":
				s.Reset()
				fmt.Fprintln(out, ":ok")
				continue
			case helpRequest.MatchString(trimmed):
				text, err := guide.Doc(helpRequest.FindStringSubmatch(trimmed)[1], false, false)
				if err != nil {
					fmt.Fprintln(out, err)
				} else {
					fmt.Fprint(out, text)
				}
				continue
			}
		}
		pending = append(pending, line)
		result, err := s.Eval(ctx, strings.Join(pending, "\n"))
		if err == nil && result.Incomplete {
			continue
		}
		pending = nil
		number++
		if err != nil {
			fmt.Fprintln(out, "** "+strings.ReplaceAll(err.Error(), "\n", "\n   "))
			continue
		}
		fmt.Fprint(out, result.Output)
	}
}
