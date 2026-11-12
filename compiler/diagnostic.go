package compiler

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
)

type Diagnostic struct {
	File    string `json:"file"`
	Line    int    `json:"line"`
	Column  int    `json:"column"`
	Message string `json:"message"`
}

func (d *Diagnostic) Error() string {
	return fmt.Sprintf("%s:%d:%d: %s", d.File, d.Line, d.Column, d.Message)
}

var positioned = regexp.MustCompile(`^(.*):([0-9]+):([0-9]+): (.*)$`)
var relativePosition = regexp.MustCompile(`^([0-9]+):([0-9]+): (.*)$`)

func Describe(err error) *Diagnostic {
	if err == nil {
		return nil
	}
	var found *Diagnostic
	for current := err; current != nil; current = errors.Unwrap(current) {
		switch e := current.(type) {
		case *Diagnostic:
			found = e
		case *importDiagnostic:
			found = e.position
		}
	}
	if found != nil {
		return found
	}
	if fields := positioned.FindStringSubmatch(err.Error()); fields != nil {
		line, _ := strconv.Atoi(fields[2])
		col, _ := strconv.Atoi(fields[3])
		return &Diagnostic{fields[1], line, col, fields[4]}
	}
	return &Diagnostic{Message: err.Error()}
}
func syntaxDiagnostic(path string, err error) error {
	if fields := relativePosition.FindStringSubmatch(err.Error()); fields != nil {
		line, _ := strconv.Atoi(fields[1])
		col, _ := strconv.Atoi(fields[2])
		return &Diagnostic{path, line, col, "unsupported syntax: " + fields[3]}
	}
	return &Diagnostic{path, 1, 1, err.Error()}
}

type importDiagnostic struct {
	position *Diagnostic
	cause    error
}

func (e *importDiagnostic) Error() string { return e.position.Error() }
func (e *importDiagnostic) Unwrap() error { return e.cause }
func (e *importDiagnostic) As(target any) bool {
	if p, ok := target.(**Diagnostic); ok {
		*p = e.position
		return true
	}
	return false
}
func wrapImport(file string, positionLine, positionColumn int, path string, cause error) error {
	return &importDiagnostic{&Diagnostic{file, positionLine, positionColumn, fmt.Sprintf("import %q: %v", path, cause)}, cause}
}
