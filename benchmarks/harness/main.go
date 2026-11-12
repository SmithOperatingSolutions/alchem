// Command harness builds and runs the Alchem benchmarks next to their Go and
// Elixir baselines and prints a Markdown report. Run it from the repository
// root: go run ./benchmarks/harness
//
// It measures two sets of programs. The whole-program workloads (hello, spawn,
// echo and so on) are timed from outside over several runs. The standard
// library suite (enum, stream, map_set and so on) times its own cases from
// inside, so that process startup does not hide small operations.
//
//	-only enum,json     run only the named programs, from either set
//	-json out.json      also write the suite's figures as JSON
//	-compare base.json  fail if a suite case got slower than in that record
//
// It executes only the fixed programs under benchmarks/, never a shell, and
// bounds every build and run with a deadline.
package main

import (
	"bytes"
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"
)

type workload struct {
	name, what string
	// units is the number of operations a run performs, for per-unit figures.
	units  int
	expect string
}

var workloads = []workload{
	{"hello", "start, print one line, exit", 0, "hello\n"},
	{"spawn", "100,000 processes alive at once, then released and joined", 100000, "spawned 100000\n"},
	{"echo", "200,000 request/reply round trips between two processes", 200000, "round trips 200000\n"},
	{"compute", "recursive fib(32), then the sum of squares of 1..1,000,000 through a list", 0, "computed\n"},
	{"build", "build a 50,000-element list one prepend at a time, then walk and sum it", 0, "built\n"},
	{"state", "build a 50,000-entry map one key at a time, sum it in key order, then update 1,000 counters 50,000 times", 0, "state kept\n"},
	{"restart", "20,000 supervised crash, restart and round-trip cycles", 20000, "restarted 20000\n"},
}

type result struct {
	median, fastest time.Duration
	rss, size       int64
	note            string
	// phases are the median times each program reported for its own
	// phases, in order, and latencies the distributions it reported from
	// its median run.
	phases    []phaseTime
	latencies []latency
}

// A program reports on standard error "phase NAME MICROSECONDS" for each
// part of its work, timed inside it, and "latency NAME FASTEST MEDIAN P99"
// for a distribution of single operations.
type phaseTime struct {
	name   string
	median time.Duration
}

type latency struct {
	name                 string
	fastest, median, p99 string
}

// readTimings reads what a program reported about its own timing.
func readTimings(stderr []byte) (map[string]time.Duration, []string, []latency) {
	phases := map[string]time.Duration{}
	var order []string
	var latencies []latency
	for _, line := range strings.Split(string(stderr), "\n") {
		fields := strings.Fields(line)
		switch {
		case len(fields) >= 3 && fields[0] == "phase":
			micros, err := strconv.ParseInt(fields[len(fields)-1], 10, 64)
			if err != nil {
				continue
			}
			name := strings.Join(fields[1:len(fields)-1], " ")
			if _, seen := phases[name]; !seen {
				order = append(order, name)
			}
			phases[name] = time.Duration(micros) * time.Microsecond
		case len(fields) >= 5 && fields[0] == "latency":
			n := len(fields)
			latencies = append(latencies, latency{strings.Join(fields[1:n-3], " "), fields[n-3], fields[n-2], fields[n-1]})
		}
	}
	return phases, order, latencies
}

const maxRuns = 100

func main() {
	runs := flag.Int("runs", 5, "timed runs per whole-program workload (1..100)")
	limit := flag.Duration("timeout", 10*time.Minute, "deadline for each build and each run")
	only := flag.String("only", "", "comma-separated programs to run; all when empty")
	jsonPath := flag.String("json", "", "write the suite's figures to this file as JSON")
	baseline := flag.String("compare", "", "compare the suite with this JSON record and fail on regressions")
	threshold := flag.Float64("threshold", 1.25, "growth in Alchem's ratio to Elixir and Go that counts as a regression")
	compiler := flag.String("compiler", "", "use this alchem executable instead of building ./cmd/alchem")
	inputs := flag.String("inputs", "", "only write the suite's input files to this directory")
	flag.Parse()
	if *inputs != "" {
		if err := writeInputs(*inputs); err != nil {
			fmt.Fprintln(os.Stderr, "harness:", err)
			os.Exit(1)
		}
		return
	}
	selected, err := selection(*only)
	if *runs < 1 || *runs > maxRuns || *limit <= 0 || *threshold <= 1 || flag.NArg() != 0 || err != nil {
		if err != nil {
			fmt.Fprintln(os.Stderr, "harness:", err)
		}
		fmt.Fprintln(os.Stderr, "usage: harness [-runs 1..100] [-timeout duration] [-only names] [-json file] [-compare file] [-threshold ratio] [-compiler path]")
		os.Exit(2)
	}
	regressions, err := report(*runs, *limit, selected, *compiler, *jsonPath, *baseline, *threshold)
	if err != nil {
		fmt.Fprintln(os.Stderr, "harness:", err)
		os.Exit(1)
	}
	if regressions > 0 {
		os.Exit(3)
	}
}

// selection turns the -only list into a predicate over program names.
func selection(only string) (func(string) bool, error) {
	if only == "" {
		return func(string) bool { return true }, nil
	}
	known := map[string]bool{}
	for _, w := range workloads {
		known[w.name] = true
	}
	for _, p := range suitePrograms {
		known[p.name] = true
	}
	chosen := map[string]bool{}
	for _, name := range strings.Split(only, ",") {
		if !known[name] {
			return nil, fmt.Errorf("unknown program %q", name)
		}
		chosen[name] = true
	}
	return func(name string) bool { return chosen[name] }, nil
}

func command(limit time.Duration, dir string, name string, args ...string) ([]byte, *os.ProcessState, time.Duration, error) {
	return run(limit, dir, nil, name, args...)
}

// commandEnv is command with extra environment variables.
func commandEnv(limit time.Duration, env []string, name string, args ...string) ([]byte, *os.ProcessState, time.Duration, error) {
	return run(limit, "", env, name, args...)
}

func run(limit time.Duration, dir string, env []string, name string, args ...string) ([]byte, *os.ProcessState, time.Duration, error) {
	out, _, state, elapsed, err := runBoth(limit, dir, env, name, args...)
	return out, state, elapsed, err
}

// runBoth is run that also returns what the program wrote to standard error.
func runBoth(limit time.Duration, dir string, env []string, name string, args ...string) ([]byte, []byte, *os.ProcessState, time.Duration, error) {
	ctx, cancel := context.WithTimeout(context.Background(), limit)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir = dir
	if env != nil {
		cmd.Env = append(os.Environ(), env...)
	}
	cmd.WaitDelay = time.Second
	var out, errOut bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errOut
	start := time.Now()
	err := cmd.Run()
	elapsed := time.Since(start)
	if ctx.Err() != nil {
		err = fmt.Errorf("%s: %w", name, ctx.Err())
	} else if err != nil {
		err = fmt.Errorf("%s: %w: %.2000s", name, err, errOut.String())
	}
	return out.Bytes(), errOut.Bytes(), cmd.ProcessState, elapsed, err
}

func measure(runs int, limit time.Duration, expect, size string, name string, args ...string) result {
	var times []time.Duration
	var r result
	byPhase := map[string][]time.Duration{}
	var order []string
	type timed struct {
		elapsed   time.Duration
		latencies []latency
	}
	var all []timed
	for i := 0; i < runs; i++ {
		out, stderr, state, elapsed, err := runBoth(limit, "", nil, name, args...)
		if err != nil {
			return result{note: err.Error()}
		}
		if string(out) != expect {
			return result{note: fmt.Sprintf("unexpected output %.80q", out)}
		}
		times = append(times, elapsed)
		if rss := peakRSS(state); rss > r.rss {
			r.rss = rss
		}
		phases, names, latencies := readTimings(stderr)
		for _, phase := range names {
			if _, seen := byPhase[phase]; !seen {
				order = append(order, phase)
			}
			byPhase[phase] = append(byPhase[phase], phases[phase])
		}
		all = append(all, timed{elapsed, latencies})
	}
	sort.Slice(times, func(i, j int) bool { return times[i] < times[j] })
	r.fastest, r.median = times[0], times[len(times)/2]
	for _, phase := range order {
		values := byPhase[phase]
		sort.Slice(values, func(i, j int) bool { return values[i] < values[j] })
		r.phases = append(r.phases, phaseTime{phase, values[len(values)/2]})
	}
	// The distributions are the median run's, by wall time.
	sort.Slice(all, func(i, j int) bool { return all[i].elapsed < all[j].elapsed })
	r.latencies = all[len(all)/2].latencies
	if size != "" {
		if info, err := os.Stat(size); err == nil {
			r.size = info.Size()
		}
	}
	return r
}

func report(runs int, limit time.Duration, selected func(string) bool, compiler, jsonPath, baseline string, threshold float64) (regressions int, err error) {
	if _, err := os.Stat(filepath.Join("benchmarks", "alchem", "spawn.alc")); err != nil {
		return 0, errors.New("run from the repository root")
	}
	work, err := os.MkdirTemp("", "alchem-bench-*")
	if err != nil {
		return 0, err
	}
	defer os.RemoveAll(work)
	exe := ""
	if runtime.GOOS == "windows" {
		exe = ".exe"
	}
	source := "built from this working tree"
	if compiler == "" {
		compiler = filepath.Join(work, "alchem"+exe)
		if _, _, _, err := command(limit, "", "go", "build", "-o", compiler, "./cmd/alchem"); err != nil {
			return 0, err
		}
	} else {
		if compiler, err = filepath.Abs(compiler); err != nil {
			return 0, err
		}
		source = "supplied with -compiler"
	}
	elixir, _ := exec.LookPath("elixir")
	results := map[string]map[string]result{}
	var measured []workload
	for _, w := range workloads {
		if !selected(w.name) {
			continue
		}
		measured = append(measured, w)
		row := map[string]result{}
		alchemBinary := filepath.Join(work, "alchem-"+w.name+exe)
		if _, _, _, err := command(limit, "", compiler, "build", "-o", alchemBinary, filepath.Join("benchmarks", "alchem", w.name+".alc")); err != nil {
			return 0, err
		}
		row["Alchem"] = measure(runs, limit, w.expect, alchemBinary, alchemBinary)
		goBinary := filepath.Join(work, "go-"+w.name+exe)
		if _, _, _, err := command(limit, "", "go", "build", "-o", goBinary, "./benchmarks/go/"+w.name); err != nil {
			return 0, err
		}
		row["Go"] = measure(runs, limit, w.expect, goBinary, goBinary)
		if elixir == "" {
			row["Elixir"] = result{note: "not measured: elixir is not on PATH"}
		} else {
			row["Elixir"] = measure(runs, limit, w.expect, "", elixir, filepath.Join("benchmarks", "elixir", w.name+".exs"))
		}
		results[w.name] = row
	}
	cases, builds, notes, err := runSuite(limit, work, compiler, elixir, exe, selected)
	if err != nil {
		return 0, err
	}
	var cold time.Duration
	if len(builds) > 0 {
		cold = coldBuild(limit, work, compiler, exe)
	}

	lines := environment(limit, elixir, runs, source)
	fmt.Printf("## Environment\n\n%s\n", strings.Join(lines, "\n"))
	startup := map[string]time.Duration{}
	for name, r := range results["hello"] {
		startup[name] = r.median
	}
	if len(measured) > 0 {
		fmt.Print("\n## Whole programs\n\nEach program is run from outside and timed as a whole.\n")
	}
	for _, w := range measured {
		fmt.Printf("\n### %s\n\n%s.\n\n", w.name, strings.ToUpper(w.what[:1])+w.what[1:])
		fmt.Println("| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |")
		fmt.Println("| --- | --- | --- | --- | --- | --- | --- |")
		for _, name := range []string{"Alchem", "Go", "Elixir"} {
			r := results[w.name][name]
			if r.note != "" {
				fmt.Printf("| %s | %s | | | | | |\n", name, r.note)
				continue
			}
			per, rate := "n/a", "n/a"
			// Subtract process startup so per-operation figures describe the work.
			if work := r.median - startup[name]; w.units > 0 && work > 0 {
				per = (work / time.Duration(w.units)).String()
				rate = fmt.Sprintf("%.0f", float64(w.units)/work.Seconds())
			}
			fmt.Printf("| %s | %s | %s | %s | %s | %s | %s |\n", name, r.median.Round(10*time.Microsecond), r.fastest.Round(10*time.Microsecond), bytesText(r.rss), bytesText(r.size), per, rate)
		}
		printTimings(results[w.name])
	}
	if len(cases) > 0 || len(notes) > 0 {
		printSuite(cases, builds, cold, notes)
	}
	if jsonPath != "" {
		if err := writeRecord(jsonPath, record{lines, cases, builds}); err != nil {
			return 0, err
		}
	}
	if baseline != "" {
		if regressions, err = compare(baseline, cases, threshold); err != nil {
			return 0, err
		}
	}
	if len(notes) > 0 {
		return regressions, fmt.Errorf("%d suite programs could not be measured", len(notes))
	}
	return regressions, nil
}

func bytesText(n int64) string {
	if n <= 0 {
		return "n/a"
	}
	return fmt.Sprintf("%.1f MiB", float64(n)/(1<<20))
}

// environment describes the machine and toolchains as Markdown list items.
func environment(limit time.Duration, elixir string, runs int, compiler string) []string {
	lines := []string{
		"- Date: " + time.Now().UTC().Format("2006-01-02"),
		fmt.Sprintf("- OS/architecture: %s/%s", runtime.GOOS, runtime.GOARCH),
		fmt.Sprintf("- Logical CPUs: %d", runtime.NumCPU()),
	}
	add := func(label, value string) {
		if value = strings.TrimSpace(value); value != "" {
			lines = append(lines, "- "+label+": "+value)
		}
	}
	output := func(name string, args ...string) string {
		out, _, _, err := command(limit, "", name, args...)
		if err != nil {
			return ""
		}
		return strings.TrimSpace(string(out))
	}
	if data, err := os.ReadFile("/proc/cpuinfo"); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			if strings.HasPrefix(line, "model name") {
				add("CPU", strings.SplitN(line, ":", 2)[1])
				break
			}
		}
	}
	if data, err := os.ReadFile("/proc/meminfo"); err == nil {
		if fields := strings.Fields(strings.SplitN(string(data), "\n", 2)[0]); len(fields) >= 2 {
			add("Memory", fields[1]+" kB")
		}
	}
	if runtime.GOOS == "darwin" {
		add("CPU", output("sysctl", "-n", "machdep.cpu.brand_string"))
		if bytes, err := strconv.ParseInt(output("sysctl", "-n", "hw.memsize"), 10, 64); err == nil {
			add("Memory", fmt.Sprintf("%d GiB", bytes>>30))
		}
		add("macOS", output("sw_vers", "-productVersion"))
	}
	add("Go", output("go", "version"))
	if elixir != "" {
		version := strings.Split(output(elixir, "--version"), "\n")
		add("Elixir", version[len(version)-1])
	} else {
		add("Elixir", "not installed")
	}
	commit := output("git", "rev-parse", "--short", "HEAD")
	if commit != "" && output("git", "status", "--porcelain", "--untracked-files=no") != "" {
		commit += " with uncommitted changes"
	}
	add("Benchmarks at commit", commit)
	add("Alchem compiler", compiler)
	add("Runs per whole-program workload", fmt.Sprintf("%d (median reported)", runs))
	return lines
}

// printTimings shows what the programs reported from inside: the median
// time of each phase, with no startup in it, and the latency distributions.
func printTimings(row map[string]result) {
	var phases []string
	seen := map[string]bool{}
	for _, name := range []string{"Alchem", "Go", "Elixir"} {
		for _, p := range row[name].phases {
			if !seen[p.name] {
				seen[p.name] = true
				phases = append(phases, p.name)
			}
		}
	}
	if len(phases) > 0 {
		fmt.Printf("\nTimed inside each program, median of the runs:\n\n| Implementation | %s |\n|%s\n", strings.Join(phases, " | "), strings.Repeat(" --- |", len(phases)+1))
		for _, name := range []string{"Alchem", "Go", "Elixir"} {
			if row[name].note != "" {
				continue
			}
			cells := make([]string, len(phases))
			for i, phase := range phases {
				cells[i] = "n/a"
				for _, p := range row[name].phases {
					if p.name == phase {
						cells[i] = p.median.Round(10 * time.Microsecond).String()
					}
				}
			}
			fmt.Printf("| %s | %s |\n", name, strings.Join(cells, " | "))
		}
	}
	for _, name := range []string{"Alchem", "Go", "Elixir"} {
		if len(row[name].latencies) == 0 {
			continue
		}
		fmt.Printf("\n| Distribution | Fastest | Median | 99th percentile |\n| --- | --- | --- | --- |\n")
		for _, other := range []string{"Alchem", "Go", "Elixir"} {
			for _, l := range row[other].latencies {
				fmt.Printf("| %s, %s | %s | %s | %s |\n", other, l.name, l.fastest, l.median, l.p99)
			}
		}
		return
	}
}
