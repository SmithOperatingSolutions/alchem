package compiler

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

type BuildOptions struct {
	Output, GOOS, GOARCH     string
	Timeout, ShutdownTimeout time.Duration
	NoTrace, Race            bool
	// Locked refuses to build when alchem.lock would have to change.
	Locked bool
	// Cover counts how often each statement outside the entry file runs and
	// writes the counts to the file named by ALCHEM_COVER_FILE at exit. It
	// applies to test files.
	Cover bool
	// MaxCallDepth limits nested Alchem calls per process; zero selects
	// DefaultMaxCallDepth.
	MaxCallDepth int
}

// Call-depth bounds. Very deep limits can still exhaust the Go stack, which
// is fatal, so the ceiling stays well inside what a goroutine can hold.
const (
	DefaultMaxCallDepth = 100000
	MaxCallDepthCeiling = 1000000
)

func (o BuildOptions) normalized(source string) (BuildOptions, error) {
	if o.Timeout == 0 {
		o.Timeout = 2 * time.Minute
	}
	if o.ShutdownTimeout == 0 {
		o.ShutdownTimeout = 2 * time.Second
	}
	if o.Timeout < 0 || o.ShutdownTimeout < time.Millisecond {
		return o, fmt.Errorf("timeouts must be positive (shutdown >= 1ms)")
	}
	if o.MaxCallDepth == 0 {
		o.MaxCallDepth = DefaultMaxCallDepth
	}
	if o.MaxCallDepth < 1 || o.MaxCallDepth > MaxCallDepthCeiling {
		return o, fmt.Errorf("max call depth must be 1..%d", MaxCallDepthCeiling)
	}
	if o.GOOS == "" {
		o.GOOS = os.Getenv("GOOS")
	}
	if o.GOOS == "" {
		o.GOOS = runtime.GOOS
	}
	if o.GOARCH == "" {
		o.GOARCH = os.Getenv("GOARCH")
	}
	if o.GOARCH == "" {
		o.GOARCH = runtime.GOARCH
	}
	for _, v := range []string{o.GOOS, o.GOARCH} {
		if v == "" || strings.ContainsAny(v, " /\\\x00\r\n") {
			return o, fmt.Errorf("invalid target")
		}
	}
	if o.Output == "" {
		// Resolve first so entries such as "." or ".." name their directory.
		absolute, err := filepath.Abs(source)
		if err != nil {
			return o, err
		}
		o.Output = strings.TrimSuffix(filepath.Base(absolute), filepath.Ext(absolute))
		if o.Output == "" || o.Output == "." || o.Output == string(filepath.Separator) {
			return o, fmt.Errorf("cannot derive an output name from %q; provide an explicit output path", source)
		}
		if o.GOOS == "windows" {
			o.Output += ".exe"
		}
	}
	return o, nil
}
func BuildWithOptions(source string, options BuildOptions) error {
	return BuildWithOptionsContext(context.Background(), source, options)
}
func BuildWithOptionsContext(parent context.Context, source string, options BuildOptions) error {
	options, err := options.normalized(source)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(parent, options.Timeout)
	defer cancel()
	return build(ctx, source, options)
}

// Check resolves the complete import graph and type-checks every module.
// The entry may be a library, a module without main.
func Check(source string) error { return CheckContext(context.Background(), source) }

// A program with extern declarations is also checked against the Go
// declarations they name, which needs the Go toolchain.
func CheckContext(ctx context.Context, source string) error {
	return CheckLocked(ctx, source, false)
}

// CheckLocked is CheckContext that, with locked set, fails instead of
// updating alchem.lock.
func CheckLocked(ctx context.Context, source string, locked bool) error {
	// Nothing is built, so the file may be a library: a module without main
	// that other files import.
	program, err := loadProjectAs(ctx, source, true)
	if err != nil {
		return err
	}
	lock, err := readLock(program.Source)
	if err != nil {
		return err
	}
	if packages, _ := externPackages(program); len(packages) == 0 {
		// Without preparing the Go module its checksums are unknown and the
		// locked ones are kept, unless the program requires no modules at all.
		var sums []string
		if len(program.Requires) == 0 {
			sums = []string{}
		}
		return syncLock(program, lock, sums, locked)
	}
	dir, err := os.MkdirTemp("", "alchem-check-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(dir)
	environment := append(os.Environ(), "GOWORK=off")
	if err := prepareModule(ctx, dir, program, environment, lock); err != nil {
		return err
	}
	if _, err = bindExterns(ctx, dir, program, environment); err != nil {
		return err
	}
	return syncLock(program, lock, moduleSums(dir), locked)
}
