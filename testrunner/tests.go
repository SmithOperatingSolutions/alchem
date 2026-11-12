package testrunner

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"math/rand/v2"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

// Options configure a run of test files.
type Options struct {
	// Seed fixes the order of test files and of the tests in each, and the
	// random source the tests see. Zero picks one and reports it, so that a
	// failing run can be repeated.
	Seed uint64
	// Only runs the tests whose name, or whose module's name, contains it.
	Only string
	// Tags runs only the tests carrying one of these tags; Exclude leaves out
	// those carrying one. Tests tagged "skip" run only when Tags names them.
	Tags, Exclude []string
	// Trace prints each test with its duration instead of a dot.
	Trace bool
	// MaxFailures stops each test file after that many failures; zero runs all.
	MaxFailures int
	// ReceiveTimeout is how long assert_receive and refute_receive wait when
	// a test gives no timeout; zero means 100 milliseconds.
	ReceiveTimeout time.Duration
	// Jobs is how many test files are compiled and run at once; zero means
	// one per processor.
	Jobs int
	// Timeout is the limit for one test; zero means one minute.
	Timeout time.Duration
	// Cover reports which lines of the code under test ran. CoverMin, when
	// positive, fails the run if total coverage is below that percentage.
	Cover    bool
	CoverMin float64
}

// Summary totals a run.
type Summary struct {
	Tests, Failures, Excluded, Skipped int
	Seed                               uint64
	Coverage                           []FileCoverage
}

// FileCoverage is the line coverage of one source file.
type FileCoverage struct {
	File           string
	Lines, Covered int
	Uncovered      []int
}

// Percent is the share of counted lines that ran.
func (f FileCoverage) Percent() float64 {
	if f.Lines == 0 {
		return 100
	}
	return 100 * float64(f.Covered) / float64(f.Lines)
}

// ErrFailed reports that tests failed or a test file could not be run; the
// details have already been written to the output.
var ErrFailed = errors.New("tests failed")

// TestFiles lists the *_test.alc files named by the paths or found under
// them, sorted.
func TestFiles(paths []string) ([]string, error) {
	seen := map[string]bool{}
	for _, path := range paths {
		info, err := os.Stat(path)
		if err != nil {
			return nil, err
		}
		if !info.IsDir() {
			if strings.HasSuffix(path, "_test.alc") {
				seen[path] = true
			}
			continue
		}
		err = filepath.WalkDir(path, func(name string, entry fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if entry.IsDir() && name != path && strings.HasPrefix(entry.Name(), ".") {
				return filepath.SkipDir
			}
			if !entry.IsDir() && strings.HasSuffix(name, "_test.alc") {
				seen[name] = true
			}
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	files := make([]string, 0, len(seen))
	for file := range seen {
		files = append(files, file)
	}
	sort.Strings(files)
	return files, nil
}

// RunTests builds and runs each test file and writes progress, failures and
// a summary to out. The error is non-nil when any test failed, a file did
// not compile, or coverage fell below the requested minimum.
func RunTests(ctx context.Context, files []string, options Options, out io.Writer) (Summary, error) {
	summary := Summary{Seed: options.Seed}
	if summary.Seed == 0 {
		summary.Seed = uint64(time.Now().UnixNano()%999999) + 1
	}
	if options.Timeout <= 0 {
		options.Timeout = time.Minute
	}
	receiveTimeout := options.ReceiveTimeout
	if receiveTimeout <= 0 {
		receiveTimeout = 100 * time.Millisecond
	}
	files = append([]string{}, files...)
	rand.New(rand.NewPCG(summary.Seed, summary.Seed)).Shuffle(len(files), func(i, j int) { files[i], files[j] = files[j], files[i] })
	work, err := os.MkdirTemp("", "alchem-tests-*")
	if err != nil {
		return summary, err
	}
	defer os.RemoveAll(work)
	started := time.Now()
	hits := map[string]map[int]int{}
	broken := 0
	// Each file is compiled and run on its own. With several jobs the files
	// proceed at once and each one's output is held until the files before
	// it have printed theirs, so a run reads the same whatever the timing.
	type outcome struct {
		output                            bytes.Buffer
		passed, failed, excluded, skipped int
		broken                            bool
		coverage                          string
	}
	jobs := options.Jobs
	if jobs <= 0 {
		jobs = runtime.NumCPU()
	}
	jobs = min(jobs, max(len(files), 1))
	one := func(i int, file string, out io.Writer, result *outcome) {
		binary := filepath.Join(work, fmt.Sprintf("test%d", i))
		if runtime.GOOS == "windows" {
			binary += ".exe"
		}
		if err := compiler.BuildWithOptionsContext(ctx, file, compiler.BuildOptions{Output: binary, Cover: options.Cover}); err != nil {
			fmt.Fprintf(out, "\n%s did not compile:\n  %v\n", file, err)
			result.broken = true
			return
		}
		report, coverage := binary+".result", binary+".cover"
		cmd := exec.CommandContext(ctx, binary)
		cmd.Stdout, cmd.Stderr = out, out
		cmd.Env = append(os.Environ(),
			"ALCHEM_SEED="+strconv.FormatUint(summary.Seed, 10),
			"ALCHEM_TEST_ONLY="+options.Only,
			"ALCHEM_TEST_TAGS="+strings.Join(options.Tags, ","),
			"ALCHEM_TEST_EXCLUDE="+strings.Join(options.Exclude, ","),
			"ALCHEM_TEST_MAX_FAILURES="+strconv.Itoa(options.MaxFailures),
			"ALCHEM_TEST_TIMEOUT="+strconv.FormatInt(options.Timeout.Milliseconds(), 10),
			"ALCHEM_TEST_RECEIVE_TIMEOUT="+strconv.FormatInt(receiveTimeout.Milliseconds(), 10),
			"ALCHEM_TEST_RESULT="+report,
			"ALCHEM_COVER_FILE="+coverage)
		if options.Trace {
			cmd.Env = append(cmd.Env, "ALCHEM_TEST_TRACE=1")
		}
		runErr := cmd.Run()
		data, _ := os.ReadFile(report)
		if _, err := fmt.Sscanf(string(data), "%d %d %d %d", &result.passed, &result.failed, &result.excluded, &result.skipped); err != nil {
			// The program ended before its runner could report.
			fmt.Fprintf(out, "\n%s stopped before finishing its tests: %v\n", file, runErr)
			result.broken = true
			return
		}
		result.coverage = coverage
	}
	results := make([]outcome, len(files))
	finished := make([]chan struct{}, len(files))
	for i := range finished {
		finished[i] = make(chan struct{})
	}
	if jobs > 1 {
		slots := make(chan struct{}, jobs)
		for i, file := range files {
			go func() {
				slots <- struct{}{}
				defer func() { <-slots; close(finished[i]) }()
				if ctx.Err() == nil {
					one(i, file, &results[i].output, &results[i])
				}
			}()
		}
	}
	for i, file := range files {
		if jobs > 1 {
			<-finished[i]
			out.Write(results[i].output.Bytes())
		} else if ctx.Err() == nil {
			// One job writes as it goes.
			one(i, file, out, &results[i])
		}
		if err := ctx.Err(); err != nil {
			return summary, err
		}
		result := &results[i]
		if result.broken {
			broken++
			continue
		}
		summary.Tests += result.passed + result.failed
		summary.Failures += result.failed
		summary.Excluded += result.excluded
		summary.Skipped += result.skipped
		if options.Cover {
			readCoverage(result.coverage, hits)
		}
	}
	fmt.Fprintf(out, "\nFinished in %.1f seconds\n%s, %s", time.Since(started).Seconds(), count(summary.Tests, "test"), count(summary.Failures, "failure"))
	if summary.Excluded > 0 {
		fmt.Fprintf(out, ", %d excluded", summary.Excluded)
	}
	if summary.Skipped > 0 {
		fmt.Fprintf(out, ", %d skipped", summary.Skipped)
	}
	if broken > 0 {
		fmt.Fprintf(out, ", %s", count(broken, "file")+" not run")
	}
	fmt.Fprintf(out, "\n\nRandomized with seed %d\n", summary.Seed)
	total := 100.0
	if options.Cover {
		summary.Coverage, total = report(hits, out)
	}
	switch {
	case summary.Failures > 0 || broken > 0:
		return summary, ErrFailed
	case options.Cover && total < options.CoverMin:
		return summary, fmt.Errorf("coverage %.1f%% is below the required %.1f%%", total, options.CoverMin)
	}
	return summary, nil
}

func count(n int, word string) string {
	if n == 1 {
		return "1 " + word
	}
	return fmt.Sprintf("%d %ss", n, word)
}

// readCoverage adds one test program's line counts to hits.
func readCoverage(path string, hits map[string]map[int]int) {
	data, _ := os.ReadFile(path)
	for _, line := range strings.Split(string(data), "\n") {
		fields := strings.Split(line, "\t")
		if len(fields) != 3 {
			continue
		}
		number, _ := strconv.Atoi(fields[1])
		times, _ := strconv.Atoi(fields[2])
		if hits[fields[0]] == nil {
			hits[fields[0]] = map[int]int{}
		}
		hits[fields[0]][number] += times
	}
}

// report prints line coverage per file and in total, and returns both.
func report(hits map[string]map[int]int, out io.Writer) ([]FileCoverage, float64) {
	var files []FileCoverage
	lines, covered := 0, 0
	cwd, _ := os.Getwd()
	for file, counts := range hits {
		entry := FileCoverage{File: file, Lines: len(counts)}
		if relative, err := filepath.Rel(cwd, file); err == nil && !strings.HasPrefix(relative, "..") {
			entry.File = relative
		}
		for number, times := range counts {
			if times > 0 {
				entry.Covered++
			} else {
				entry.Uncovered = append(entry.Uncovered, number)
			}
		}
		sort.Ints(entry.Uncovered)
		lines, covered = lines+entry.Lines, covered+entry.Covered
		files = append(files, entry)
	}
	sort.Slice(files, func(i, j int) bool { return files[i].File < files[j].File })
	total := 100.0
	if lines > 0 {
		total = 100 * float64(covered) / float64(lines)
	}
	fmt.Fprintf(out, "\nPercentage | File\n-----------|--------------------------\n")
	for _, file := range files {
		fmt.Fprintf(out, "%9.1f%% | %s\n", file.Percent(), file.File)
	}
	fmt.Fprintf(out, "-----------|--------------------------\n%9.1f%% | Total\n", total)
	for _, file := range files {
		if len(file.Uncovered) > 0 {
			fmt.Fprintf(out, "\n%s: lines not run: %s\n", file.File, ranges(file.Uncovered))
		}
	}
	return files, total
}

// ranges renders sorted line numbers compactly: 3, 7-9, 12.
func ranges(lines []int) string {
	var parts []string
	for i := 0; i < len(lines); {
		j := i
		for j+1 < len(lines) && lines[j+1] == lines[j]+1 {
			j++
		}
		if j > i {
			parts = append(parts, fmt.Sprintf("%d-%d", lines[i], lines[j]))
		} else {
			parts = append(parts, strconv.Itoa(lines[i]))
		}
		i = j + 1
	}
	return strings.Join(parts, ", ")
}
