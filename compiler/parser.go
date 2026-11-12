package compiler

import (
	"fmt"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// ParseHello keeps the initial compiler API while delegating to the token-based parser.
func ParseHello(source string) (string, error) {
	program, err := syntax.Parse(source)
	if err != nil {
		return "", fmt.Errorf("unsupported syntax: %w", err)
	}
	if len(program.Statements) != 1 || program.Statements[0].Output == nil {
		return "", fmt.Errorf("ParseHello requires exactly one IO.puts statement")
	}
	if strings.ContainsRune(program.Output, 0) {
		return "", fmt.Errorf("string literal contains NUL")
	}
	return program.Output, nil
}
