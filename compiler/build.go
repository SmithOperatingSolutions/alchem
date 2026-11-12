package compiler

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// Build compiles source into an executable in the current working directory.
func Build(sourcePath string) error { return BuildWithOptions(sourcePath, BuildOptions{}) }
func BuildTo(sourcePath, outputPath string) error {
	if outputPath == "" {
		return fmt.Errorf("output path required")
	}
	return BuildWithOptions(sourcePath, BuildOptions{Output: outputPath})
}
func BuildToContext(ctx context.Context, sourcePath, outputPath string) error {
	if outputPath == "" {
		return fmt.Errorf("output path required")
	}
	return BuildWithOptionsContext(ctx, sourcePath, BuildOptions{Output: outputPath})
}
func build(ctx context.Context, sourcePath string, options BuildOptions) error {
	outputPath := options.Output

	if err := ctx.Err(); err != nil {
		return fmt.Errorf("build: %w", err)
	}
	if info, err := os.Stat(sourcePath); (err != nil || !info.IsDir()) && filepath.Ext(sourcePath) != ".alc" {
		return fmt.Errorf("source must have .alc extension")
	}
	if outputPath == "" {
		return fmt.Errorf("output path required")
	}
	program, err := loadProjectContext(ctx, sourcePath)
	if err != nil {
		return err
	}

	dir, err := os.MkdirTemp("", "alchem-build-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(dir)

	if strings.ContainsAny(program.Source, "\r\n") {
		return fmt.Errorf("source path contains a newline")
	}
	environment := append(os.Environ(), "GOWORK=off", "GOOS="+options.GOOS, "GOARCH="+options.GOARCH)
	lock, err := readLock(program.Source)
	if err != nil {
		return err
	}
	if err := prepareModule(ctx, dir, program, environment, lock); err != nil {
		return err
	}
	if err := syncLock(program, lock, moduleSums(dir), options.Locked); err != nil {
		return err
	}
	plan, err := bindExterns(ctx, dir, program, environment)
	if err != nil {
		return err
	}
	input := filepath.Join(dir, "main.go")
	generated := generateProgram(program, options, plan)
	if err := os.WriteFile(input, []byte(generated), 0600); err != nil {
		return err
	}
	library := selectLibrary(generated)
	if mapLibraryLines {
		// go test runs its binaries with GOCOVERDIR set to a directory of its
		// own, which the programs they run would inherit; so a covered
		// program writes its counts itself, where ALCHEM_GO_COVERAGE says.
		generated = strings.ReplaceAll(generated, "os.Exit(", "coverageExit(") + "\nvar _ = os.Exit\n"
		library = strings.ReplaceAll(library, "os.Exit(", "coverageExit(")
		if err := os.WriteFile(input, []byte(generated), 0600); err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(dir, "coverage.go"), []byte(coverageExit), 0600); err != nil {
			return err
		}
	}
	if err := os.WriteFile(filepath.Join(dir, "library.go"), []byte(library), 0600); err != nil {
		return err
	}
	destination, err := filepath.Abs(outputPath)
	if err != nil {
		return err
	}
	for _, function := range program.Functions {
		same := destination == function.Source
		if runtime.GOOS == "windows" {
			same = strings.EqualFold(destination, function.Source)
		}
		if same {
			return fmt.Errorf("output would overwrite source file %s", function.Source)
		}
	}
	// Build next to the destination for a same-filesystem atomic rename.
	staged, err := os.CreateTemp(filepath.Dir(destination), ".alchem-output-*")
	if err != nil {
		return fmt.Errorf("stage output: %w", err)
	}
	stagedPath := staged.Name()
	defer os.Remove(stagedPath)
	if err := staged.Close(); err != nil {
		return err
	}
	arguments := []string{"build", "-buildvcs=false", "-o", stagedPath}
	if options.Race {
		arguments = append(arguments, "-race")
	}
	if mapLibraryLines {
		arguments = append(arguments, "-cover", "-covermode=atomic", "-coverpkg=./...")
	}
	arguments = append(arguments, ".")
	goPath, err := goCommand(ctx)
	if err != nil {
		return err
	}
	cmd := exec.CommandContext(ctx, goPath, arguments...)
	cmd.Dir = dir
	cmd.Env = goEnvironment(goPath, environment)
	cmd.WaitDelay = time.Second
	if result, err := cmd.CombinedOutput(); err != nil {
		if ctx.Err() != nil {
			return fmt.Errorf("go build: %w", ctx.Err())
		}
		return fmt.Errorf("go build: %w: %s", err, result)
	}
	if err := ctx.Err(); err != nil {
		return fmt.Errorf("build: %w", err)
	}
	if err := os.Rename(stagedPath, destination); err != nil {
		return fmt.Errorf("publish output: %w", err)
	}
	return nil
}

// coverageExit ends a program built for coverage after writing its counts.
const coverageExit = `package main

import (
	"os"
	"runtime/coverage"
)

func coverageExit(code int) {
	if dir := os.Getenv("ALCHEM_GO_COVERAGE"); dir != "" {
		_ = coverage.WriteMetaDir(dir)
		_ = coverage.WriteCountersDir(dir)
	}
	os.Exit(code)
}
`
