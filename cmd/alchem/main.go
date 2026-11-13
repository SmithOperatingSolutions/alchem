package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"

	"github.com/SmithOperatingSolutions/alchem/compiler"
	"github.com/SmithOperatingSolutions/alchem/guide"
	"github.com/SmithOperatingSolutions/alchem/lsp"
	"github.com/SmithOperatingSolutions/alchem/testrunner"
)

func main() {
	// An interrupt or a request to terminate cancels what is running, which
	// ends the program alchem run started along with alchem itself.
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	os.Exit(run(ctx, os.Args[1:], os.Stdout, os.Stderr))
}

// settings holds every option a command may take.
type settings struct {
	options           compiler.BuildOptions
	jsonOutput, trace bool
	check, all, force bool
	list              bool
	timeout, shutdown time.Duration
	target, tags      string
	exclude, search   string
	scope, dir        string
	tests             testrunner.Options
}

// flagsFor declares the options of one command; nil means there is no such
// command. Help and the generated command reference read the same flags.
func flagsFor(name string, s *settings, errOut io.Writer) *flag.FlagSet {
	flags := flag.NewFlagSet(name, flag.ContinueOnError)
	flags.SetOutput(errOut)
	s.trace, s.timeout, s.shutdown = true, 2*time.Minute, 2*time.Second
	switch name {
	case "build":
		flags.StringVar(&s.options.Output, "o", "", "output executable")
		flags.StringVar(&s.target, "target", "", "target GOOS/GOARCH")
		flags.DurationVar(&s.timeout, "timeout", s.timeout, "build deadline")
		flags.DurationVar(&s.shutdown, "shutdown-timeout", s.shutdown, "runtime shutdown deadline")
		flags.BoolVar(&s.trace, "trace", true, "include Alchem runtime frames")
		flags.IntVar(&s.options.MaxCallDepth, "max-call-depth", compiler.DefaultMaxCallDepth, "nested Alchem calls allowed per process")
		flags.BoolVar(&s.options.Race, "race", false, "enable Go race detection in generated executable")
		flags.BoolVar(&s.jsonOutput, "json", false, "emit structured compile diagnostics")
		flags.BoolVar(&s.options.Locked, "locked", false, "fail instead of updating alchem.lock")
	case "run":
		flags.DurationVar(&s.timeout, "timeout", s.timeout, "build deadline")
		flags.DurationVar(&s.shutdown, "shutdown-timeout", s.shutdown, "runtime shutdown deadline")
		flags.IntVar(&s.options.MaxCallDepth, "max-call-depth", compiler.DefaultMaxCallDepth, "nested Alchem calls allowed per process")
		flags.BoolVar(&s.options.Race, "race", false, "enable Go race detection in the program")
		flags.BoolVar(&s.options.Locked, "locked", false, "fail instead of updating alchem.lock")
	case "new", "alx", "lsp":
	case "check":
		flags.BoolVar(&s.jsonOutput, "json", false, "emit structured diagnostics")
		flags.BoolVar(&s.options.Locked, "locked", false, "fail instead of updating alchem.lock")
	case "fmt":
		flags.BoolVar(&s.check, "check", false, "check formatting without writing")
	case "test":
		flags.DurationVar(&s.timeout, "timeout", 30*time.Second, "deadline for one fixture, or one test")
		flags.Uint64Var(&s.tests.Seed, "seed", 0, "seed for test order and random values; 0 picks one")
		flags.StringVar(&s.tests.Only, "only", "", "run only tests whose name or module contains this text")
		flags.BoolVar(&s.tests.Trace, "trace", false, "print each test with its duration")
		flags.StringVar(&s.tags, "tag", "", "run only tests carrying one of these comma-separated tags")
		flags.StringVar(&s.exclude, "exclude", "", "leave out tests carrying one of these comma-separated tags")
		flags.IntVar(&s.tests.MaxFailures, "max-failures", 0, "stop a test file after this many failures")
		flags.BoolVar(&s.tests.Cover, "cover", false, "report line coverage of the code under test")
		flags.Float64Var(&s.tests.CoverMin, "cover-min", 0, "fail if total coverage is below this percentage")
		flags.IntVar(&s.tests.Jobs, "jobs", 0, "test files compiled and run at once; 0 means one per processor")
		flags.DurationVar(&s.tests.ReceiveTimeout, "receive-timeout", 100*time.Millisecond, "how long assert_receive and refute_receive wait by default")
	case "syntax":
		flags.BoolVar(&s.all, "all", false, "print every topic")
		flags.BoolVar(&s.jsonOutput, "json", false, "emit structured output")
	case "doc":
		flags.BoolVar(&s.all, "all", false, "print every function of the module in full")
		flags.StringVar(&s.search, "search", "", "find functions, modules and topics containing this text")
		flags.BoolVar(&s.jsonOutput, "json", false, "emit structured output")
	case "agent-guide":
		flags.BoolVar(&s.jsonOutput, "json", false, "emit structured output")
	case "agent-install":
		flags.StringVar(&s.scope, "scope", "project", "install for this project, or for the user")
		flags.StringVar(&s.dir, "dir", "", "directory to install into instead of the one the scope implies")
		flags.BoolVar(&s.force, "force", false, "replace an existing file that differs")
		flags.BoolVar(&s.list, "list", false, "list the supported agents")
		flags.BoolVar(&s.jsonOutput, "json", false, "emit structured output")
	case "docs":
		flags.BoolVar(&s.check, "check", false, "fail if a generated file is out of date, without writing")
		flags.StringVar(&s.dir, "dir", "docs", "directory the reference files are written to")
	case "version":
		flags.BoolVar(&s.jsonOutput, "json", false, "emit structured output")
	default:
		return nil
	}
	return flags
}

func init() {
	for i := range guide.Commands {
		command := &guide.Commands[i]
		flagsFor(command.Name, &settings{}, io.Discard).VisitAll(func(f *flag.Flag) {
			value := f.DefValue
			if value == "false" || value == "0" {
				value = ""
			}
			command.Flags = append(command.Flags, guide.Flag{Name: f.Name, Summary: f.Usage, Default: value})
		})
	}
}

func run(ctx context.Context, args []string, out, errOut io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(errOut, guide.Usage())
		return 2
	}
	if args[0] == "help" || args[0] == "-h" || args[0] == "--help" {
		fmt.Fprint(out, guide.Usage())
		return 0
	}
	if args[0] == "--version" {
		args = []string{"version"}
	}
	s := &settings{}
	flags := flagsFor(args[0], s, errOut)
	if flags == nil {
		fmt.Fprintf(errOut, "unknown command: %s\n\n%s", args[0], guide.Usage())
		return 2
	}
	if err := flags.Parse(args[1:]); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}
	paths := flags.Args()
	if text, err, handled := help(args[0], s, paths); handled {
		if err != nil {
			fmt.Fprintln(errOut, err)
			if text != "" {
				fmt.Fprint(out, text)
			}
			return 1
		}
		fmt.Fprint(out, text)
		return 0
	}
	switch args[0] {
	case "alx":
		return shell(ctx, os.Stdin, out)
	case "lsp":
		return lsp.Main(ctx)
	case "run":
		if len(paths) == 0 {
			fmt.Fprintln(errOut, "provide the program to run, then its arguments")
			return 2
		}
		arguments := paths[1:]
		if len(arguments) > 0 && arguments[0] == "--" {
			arguments = arguments[1:]
		}
		s.options.Timeout, s.options.ShutdownTimeout = s.timeout, s.shutdown
		code, err := runProgram(ctx, paths[0], arguments, s.options, out, errOut)
		if err != nil {
			fmt.Fprintln(errOut, err)
		}
		return code
	case "new":
		if len(paths) != 1 {
			fmt.Fprintln(errOut, "provide the directory of the new project")
			return 2
		}
		written, err := newProject(paths[0])
		if err != nil {
			fmt.Fprintln(errOut, err)
			return 1
		}
		for _, path := range written {
			fmt.Fprintln(out, "created "+path)
		}
		fmt.Fprintf(out, "\ncd %s\nalchem run main.alc\nalchem test test\n", paths[0])
		return 0
	}
	if len(paths) == 0 || (args[0] != "fmt" && args[0] != "test" && len(paths) != 1) {
		fmt.Fprintln(errOut, "provide one entry path (fmt and test accept multiple paths)")
		return 2
	}
	var err error
	switch args[0] {
	case "build":
		if s.target != "" {
			parts := strings.Split(s.target, "/")
			if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
				fmt.Fprintln(errOut, "target must be GOOS/GOARCH")
				return 2
			}
			s.options.GOOS, s.options.GOARCH = parts[0], parts[1]
		}
		s.options.Timeout = s.timeout
		s.options.ShutdownTimeout = s.shutdown
		s.options.NoTrace = !s.trace
		err = compiler.BuildWithOptionsContext(ctx, paths[0], s.options)
	case "check":
		err = compiler.CheckLocked(ctx, paths[0], s.options.Locked)
	case "test":
		s.tests.Timeout = s.timeout
		if s.tags != "" {
			s.tests.Tags = strings.Split(s.tags, ",")
		}
		if s.exclude != "" {
			s.tests.Exclude = strings.Split(s.exclude, ",")
		}
		err = runTests(ctx, paths, s.tests, s.timeout, out)
	case "fmt":
		err = formatPaths(paths, s.check, out)
	}
	if errors.Is(err, testrunner.ErrFailed) {
		return 1
	}
	if err != nil {
		if s.jsonOutput {
			_ = json.NewEncoder(errOut).Encode(compiler.Describe(err))
		} else {
			fmt.Fprintln(errOut, err)
		}
		return 1
	}
	return 0
}

// help runs the commands that print documentation rather than compile.
func help(command string, s *settings, arguments []string) (text string, err error, handled bool) {
	one := func() (string, error) {
		switch len(arguments) {
		case 0:
			return "", nil
		case 1:
			return arguments[0], nil
		}
		return "", fmt.Errorf("alchem %s takes one argument, not %d", command, len(arguments))
	}
	switch command {
	case "version":
		if len(arguments) > 0 {
			return "", fmt.Errorf("alchem version takes no arguments"), true
		}
		return versionText(s.jsonOutput), nil, true
	case "agent-guide":
		if s.jsonOutput {
			return guide.AgentGuideJSON(), nil, true
		}
		return guide.AgentGuide(), nil, true
	case "syntax":
		name, err := one()
		switch {
		case err != nil:
			return "", err, true
		case s.jsonOutput:
			text, err = guide.SyntaxJSON(name)
		case name != "":
			text, err = guide.Syntax(name)
		case s.all:
			text = guide.SyntaxAll()
		default:
			text = guide.SyntaxIndex()
		}
		return text, err, true
	case "doc":
		name, err := one()
		switch {
		case err != nil:
			return "", err, true
		case s.search != "":
			text, err = guide.Search(s.search, s.jsonOutput)
		default:
			text, err = guide.Doc(name, s.all, s.jsonOutput)
		}
		return text, err, true
	case "agent-install":
		if s.list {
			return guide.TargetList(s.jsonOutput), nil, true
		}
		name, err := one()
		if err == nil && name == "" {
			err = fmt.Errorf("name an agent to install for\n\n%s", guide.TargetList(false))
		}
		if err != nil {
			return "", err, true
		}
		installed, err := guide.Install(name, s.scope, s.dir, s.force)
		if err != nil {
			return "", err, true
		}
		if s.jsonOutput {
			data, _ := json.MarshalIndent(installed, "", "  ")
			return string(data) + "\n", nil, true
		}
		return fmt.Sprintf("%s %s\n", installed.Action, installed.Path), nil, true
	case "docs":
		changed, err := guide.WriteReferences(s.dir, s.check)
		if err != nil {
			return "", err, true
		}
		text := strings.Join(changed, "\n")
		if text != "" {
			text += "\n"
		}
		if s.check && len(changed) > 0 {
			return text, fmt.Errorf("generated documentation is out of date; run alchem docs"), true
		}
		return text, nil, true
	}
	return "", nil, false
}
func formatPaths(paths []string, check bool, out io.Writer) error {
	files := map[string]bool{}
	for _, path := range paths {
		info, err := os.Lstat(path)
		if err != nil {
			return err
		}
		if !info.IsDir() {
			files[path] = true
			continue
		}
		if err := filepath.WalkDir(path, func(name string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				if d.Name() == ".git" || d.Name() == "artifacts" {
					return filepath.SkipDir
				}
				return nil
			}
			if filepath.Ext(name) == ".alc" {
				files[name] = true
			}
			return nil
		}); err != nil {
			return err
		}
	}
	names := []string{}
	for name := range files {
		names = append(names, name)
	}
	sort.Strings(names)
	if len(names) == 0 {
		return fmt.Errorf("no .alc files found")
	}
	changed := false
	// Parse every file before any write, so syntax errors leave the batch intact.
	formatted := map[string]string{}
	for _, name := range names {
		info, err := os.Lstat(name)
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			return fmt.Errorf("%s: formatter requires a regular file", name)
		}
		data, err := compiler.ReadSource(name)
		if err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
		text, err := compiler.Format(string(data))
		if err != nil {
			return fmt.Errorf("%s:%w", name, err)
		}
		if text != string(data) {
			formatted[name] = text
		}
	}
	for _, name := range names {
		text, ok := formatted[name]
		if !ok {
			continue
		}
		changed = true
		fmt.Fprintln(out, name)
		if check {
			continue
		}
		if err := writeFormatted(name, text); err != nil {
			return err
		}
	}
	if check && changed {
		return fmt.Errorf("formatting changes required")
	}
	return nil
}
func writeFormatted(name, text string) error {
	info, err := os.Stat(name)
	if err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(name), ".alchem-fmt-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if err = f.Chmod(info.Mode().Perm()); err != nil {
		f.Close()
		return err
	}
	if _, err = f.WriteString(text); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	return os.Rename(f.Name(), name)
}

// runTests runs the test files (*_test.alc) named by the paths or found
// under them, and the output fixtures of any directory that has them.
func runTests(ctx context.Context, paths []string, options testrunner.Options, timeout time.Duration, out io.Writer) error {
	files, err := testrunner.TestFiles(paths)
	if err != nil {
		return err
	}
	ran := false
	for _, path := range paths {
		info, err := os.Stat(path)
		if err != nil || !info.IsDir() {
			continue
		}
		entries, _ := os.ReadDir(path)
		fixtures := false
		for _, entry := range entries {
			name := entry.Name()
			fixtures = fixtures || (strings.HasSuffix(name, ".alc") && !strings.HasSuffix(name, "_test.alc") && !entry.IsDir())
		}
		// A directory with test files may also hold the modules they test;
		// those are fixtures only when no test file sits beside them.
		beside, _ := testrunner.TestFiles([]string{path})
		if fixtures && len(beside) == 0 {
			if err := testrunner.RunContext(ctx, path, timeout); err != nil {
				return err
			}
			ran = true
		}
	}
	if len(files) == 0 {
		if !ran {
			return fmt.Errorf("no test files (*_test.alc) or fixtures found")
		}
		return nil
	}
	_, err = testrunner.RunTests(ctx, files, options, out)
	return err
}
