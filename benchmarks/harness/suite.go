package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// suitePrograms are the standard-library benchmark programs. Each exists as
// benchmarks/alchem/suite/NAME.alc, benchmarks/elixir/suite/NAME.exs and
// benchmarks/go/suite/NAME/main.go, times its own cases and prints one line
// per case: name, median microseconds, fastest microseconds and a check value,
// separated by tabs.
var suitePrograms = []struct{ name, what string }{
	{"enum", "Enum over lists, ranges and maps"},
	{"stream", "lazy Stream pipelines against eager ones, and File.stream!"},
	{"map_set", "Map and MapSet"},
	{"list", "positional List operations, ++ and --"},
	{"string", "String and Regex"},
	{"numbers", "Integer and Float parsing, formatting and arithmetic"},
	{"json", "JSON decode and encode"},
	{"calendar", "Date, NaiveDateTime and DateTime"},
	{"control", "for, try/rescue, with, case and cond"},
	{"processes", "spawn, send and receive"},
	{"otp", "Server, Agent and Task"},
}

// timing is one implementation's result for one case, in microseconds.
type timing struct {
	Median  int64  `json:"median_us"`
	Fastest int64  `json:"fastest_us"`
	Check   string `json:"check"`
}

// suiteCase is one case measured in up to three implementations.
type suiteCase struct {
	Program string  `json:"program"`
	Name    string  `json:"name"`
	Alchem  *timing `json:"alchem,omitempty"`
	Elixir  *timing `json:"elixir,omitempty"`
	Go      *timing `json:"go,omitempty"`
}

// buildFigures is what it costs to compile one program.
type buildFigures struct {
	Program       string `json:"program"`
	CheckMS       int64  `json:"alchem_check_ms"`
	BuildMS       int64  `json:"alchem_build_ms"`
	Size          int64  `json:"alchem_binary_bytes"`
	GoBuildMS     int64  `json:"go_build_ms"`
	GoSize        int64  `json:"go_binary_bytes"`
	ElixirBuildMS int64  `json:"elixir_compile_ms,omitempty"`
}

// record is everything one harness run measured, as written by -json and read
// by -compare.
type record struct {
	Environment []string       `json:"environment"`
	Cases       []suiteCase    `json:"cases"`
	Builds      []buildFigures `json:"builds"`
}

// parseCases reads the lines a suite program printed.
func parseCases(out []byte) (map[string]timing, []string, error) {
	found := map[string]timing{}
	var order []string
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		fields := strings.Split(line, "\t")
		if len(fields) != 4 {
			return nil, nil, fmt.Errorf("unexpected output %.80q", line)
		}
		median, err1 := strconv.ParseInt(fields[1], 10, 64)
		fastest, err2 := strconv.ParseInt(fields[2], 10, 64)
		if err1 != nil || err2 != nil {
			return nil, nil, fmt.Errorf("unexpected output %.80q", line)
		}
		found[fields[0]] = timing{median, fastest, fields[3]}
		order = append(order, fields[0])
	}
	return found, order, nil
}

// runSuite builds and runs the selected suite programs. A program that fails
// in one implementation is reported in notes and leaves that column empty.
func runSuite(limit time.Duration, work, compiler, elixir, exe string, selected func(string) bool) (cases []suiteCase, builds []buildFigures, notes []string, err error) {
	inputs := filepath.Join(work, "inputs")
	if err := os.Mkdir(inputs, 0o755); err != nil {
		return nil, nil, nil, err
	}
	if err := writeInputs(inputs); err != nil {
		return nil, nil, nil, err
	}
	for _, program := range suitePrograms {
		if !selected(program.name) {
			continue
		}
		figures := buildFigures{Program: program.name}
		source := filepath.Join("benchmarks", "alchem", "suite", program.name+".alc")
		results := map[string]map[string]timing{}
		var order []string
		run := func(implementation string, name string, args ...string) {
			out, _, _, err := command(limit, "", name, args...)
			if err == nil {
				var found map[string]timing
				var names []string
				if found, names, err = parseCases(out); err == nil {
					results[implementation] = found
					if implementation == "Alchem" || order == nil {
						order = names
					}
					return
				}
			}
			notes = append(notes, fmt.Sprintf("%s (%s): %v", program.name, implementation, err))
		}

		alchemBinary := filepath.Join(work, "suite-alchem-"+program.name+exe)
		if _, _, elapsed, err := command(limit, "", compiler, "check", source); err == nil {
			figures.CheckMS = elapsed.Milliseconds()
		}
		if _, _, elapsed, err := command(limit, "", compiler, "build", "-o", alchemBinary, source); err != nil {
			notes = append(notes, fmt.Sprintf("%s (Alchem build): %v", program.name, err))
		} else {
			figures.BuildMS, figures.Size = elapsed.Milliseconds(), fileSize(alchemBinary)
			run("Alchem", alchemBinary, inputs)
		}
		goBinary := filepath.Join(work, "suite-go-"+program.name+exe)
		if _, _, elapsed, err := command(limit, "", "go", "build", "-o", goBinary, "./benchmarks/go/suite/"+program.name); err != nil {
			notes = append(notes, fmt.Sprintf("%s (Go build): %v", program.name, err))
		} else {
			figures.GoBuildMS, figures.GoSize = elapsed.Milliseconds(), fileSize(goBinary)
			run("Go", goBinary, inputs)
		}
		if elixir != "" {
			figures.ElixirBuildMS = elixirCompile(limit, work, program.name)
			run("Elixir", elixir, filepath.Join("benchmarks", "elixir", "suite", program.name+".exs"), inputs)
		}
		builds = append(builds, figures)
		for _, name := range order {
			c := suiteCase{Program: program.name, Name: name}
			for implementation, target := range map[string]**timing{"Alchem": &c.Alchem, "Elixir": &c.Elixir, "Go": &c.Go} {
				if t, ok := results[implementation][name]; ok {
					*target = &t
				}
			}
			cases = append(cases, c)
		}
	}
	return cases, builds, notes, nil
}

func fileSize(path string) int64 {
	info, err := os.Stat(path)
	if err != nil {
		return 0
	}
	return info.Size()
}

var entryCall = regexp.MustCompile(`(?m)^\w+\.main\(.*\)\s*$`)

// elixirCompile times elixirc on a copy of a suite program with its final
// call to main removed, so that the program is compiled but not run. It
// returns 0 when that cannot be measured.
func elixirCompile(limit time.Duration, work, name string) int64 {
	elixirc := "elixirc"
	dir := filepath.Join(work, "elixirc-"+name)
	if err := os.Mkdir(dir, 0o755); err != nil {
		return 0
	}
	for _, file := range []string{"bench.exs", name + ".exs"} {
		data, err := os.ReadFile(filepath.Join("benchmarks", "elixir", "suite", file))
		if err != nil {
			return 0
		}
		if file != "bench.exs" {
			data = entryCall.ReplaceAll(data, nil)
		}
		if err := os.WriteFile(filepath.Join(dir, file), data, 0o644); err != nil {
			return 0
		}
	}
	_, _, elapsed, err := command(limit, "", elixirc, "-o", filepath.Join(dir, "out"), filepath.Join(dir, name+".exs"))
	if err != nil {
		return 0
	}
	return elapsed.Milliseconds()
}

// coldBuild times one compiler build of hello with an empty Go build cache.
func coldBuild(limit time.Duration, work, compiler, exe string) time.Duration {
	cache := filepath.Join(work, "cold-cache")
	_, _, elapsed, err := commandEnv(limit, []string{"GOCACHE=" + cache}, compiler, "build", "-o", filepath.Join(work, "cold-hello"+exe), filepath.Join("benchmarks", "alchem", "hello.alc"))
	// The Go build cache is written read-only; make it removable.
	filepath.Walk(cache, func(path string, info os.FileInfo, err error) error {
		if err == nil && info.IsDir() {
			os.Chmod(path, 0o755)
		}
		return nil
	})
	if err != nil {
		return 0
	}
	return elapsed
}

func microseconds(t *timing) string {
	if t == nil {
		return "n/a"
	}
	switch us := t.Median; {
	case us < 1000:
		return fmt.Sprintf("%d µs", us)
	case us < 100000:
		return fmt.Sprintf("%.2f ms", float64(us)/1e3)
	case us < 1000000:
		return fmt.Sprintf("%.1f ms", float64(us)/1e3)
	default:
		return fmt.Sprintf("%.2f s", float64(us)/1e6)
	}
}

// ratio is how many times longer a took than b, or 0 when either is missing
// or b is too short to divide by.
func ratio(a, b *timing) float64 {
	if a == nil || b == nil || b.Median <= 0 {
		return 0
	}
	return float64(a.Median) / float64(b.Median)
}

func ratioText(r float64) string {
	if r == 0 {
		return "n/a"
	}
	if r >= 10 {
		return fmt.Sprintf("%.0f", r)
	}
	return fmt.Sprintf("%.2f", r)
}

// checkText says whether the implementations computed the same value.
func checkText(c suiteCase) string {
	var differs []string
	if c.Alchem != nil && c.Elixir != nil && c.Alchem.Check != c.Elixir.Check {
		differs = append(differs, "Elixir")
	}
	if c.Alchem != nil && c.Go != nil && c.Alchem.Check != c.Go.Check {
		differs = append(differs, "Go")
	}
	if differs == nil {
		return "same"
	}
	return "differs from " + strings.Join(differs, " and ")
}

// noiseFloor is the shortest median, in microseconds, that ratios are ranked
// or compared on; below it timer resolution and scheduling dominate.
const noiseFloor = 100

func printSuite(cases []suiteCase, builds []buildFigures, cold time.Duration, notes []string) {
	fmt.Print("\n## Standard library suite\n\nEach program times its own cases: two warm-up iterations, then the median of seven. `Alchem / Elixir` and `Alchem / Go` are how many times longer Alchem took, so below 1 Alchem is faster. `Result` says whether the implementations computed the same value.\n")
	program := ""
	for _, c := range cases {
		if c.Program != program {
			program = c.Program
			what := ""
			for _, p := range suitePrograms {
				if p.name == program {
					what = p.what
				}
			}
			fmt.Printf("\n### %s\n\n%s.\n\n", program, strings.ToUpper(what[:1])+what[1:])
			fmt.Println("| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |")
			fmt.Println("| --- | --- | --- | --- | --- | --- | --- |")
		}
		fmt.Printf("| %s | %s | %s | %s | %s | %s | %s |\n", c.Name, microseconds(c.Alchem), microseconds(c.Elixir), microseconds(c.Go), ratioText(ratio(c.Alchem, c.Elixir)), ratioText(ratio(c.Alchem, c.Go)), checkText(c))
	}
	for _, note := range notes {
		fmt.Printf("\nNot measured: %s\n", note)
	}

	var ranked []suiteCase
	for _, c := range cases {
		if c.Alchem != nil && c.Elixir != nil && c.Alchem.Median >= noiseFloor && ratio(c.Alchem, c.Elixir) > 1 {
			ranked = append(ranked, c)
		}
	}
	sort.SliceStable(ranked, func(i, j int) bool {
		return ratio(ranked[i].Alchem, ranked[i].Elixir) > ratio(ranked[j].Alchem, ranked[j].Elixir)
	})
	if len(ranked) > 0 {
		fmt.Printf("\n### Slowest relative to Elixir\n\nThe %d cases, of %d, where Alchem took longer than Elixir (cases under %d µs in Alchem are left out), slowest first.\n\n", len(ranked), len(cases), noiseFloor)
		fmt.Println("| Case | Alchem | Elixir | Go | Alchem / Elixir |")
		fmt.Println("| --- | --- | --- | --- | --- |")
		for _, c := range ranked {
			fmt.Printf("| %s | %s | %s | %s | %s |\n", c.Name, microseconds(c.Alchem), microseconds(c.Elixir), microseconds(c.Go), ratioText(ratio(c.Alchem, c.Elixir)))
		}
	}

	if len(builds) > 0 {
		fmt.Print("\n### Compile time and binary size\n\n`alchem check` analyses without building. `alchem build` includes the Go build of the generated program, with the Go build cache warm. Elixir is `elixirc` on the same program, including starting the virtual machine.\n\n")
		fmt.Println("| Program | alchem check | alchem build | Alchem binary | go build | Go binary | elixirc |")
		fmt.Println("| --- | --- | --- | --- | --- | --- | --- |")
		for _, b := range builds {
			elixirc := "n/a"
			if b.ElixirBuildMS > 0 {
				elixirc = fmt.Sprintf("%d ms", b.ElixirBuildMS)
			}
			fmt.Printf("| %s | %d ms | %d ms | %s | %d ms | %s | %s |\n", b.Program, b.CheckMS, b.BuildMS, bytesText(b.Size), b.GoBuildMS, bytesText(b.GoSize), elixirc)
		}
		if cold > 0 {
			fmt.Printf("\nWith an empty Go build cache, `alchem build` of `hello.alc` took %s: the Go standard library and the embedded runtime are compiled once and then cached.\n", cold.Round(10*time.Millisecond))
		}
	}
}

func writeRecord(path string, r record) error {
	data, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}

// compare reports the cases whose Alchem time got worse against a baseline
// record. Times are compared as ratios to Elixir and to Go measured in the
// same run, which cancels most of the difference between machines. A case
// regresses when every ratio available for it grew by more than threshold;
// a reference under the noise floor in either run is not used.
func compare(baselinePath string, current []suiteCase, threshold float64) (regressions int, err error) {
	data, err := os.ReadFile(baselinePath)
	if err != nil {
		return 0, err
	}
	var baseline record
	if err := json.Unmarshal(data, &baseline); err != nil {
		return 0, fmt.Errorf("%s: %w", baselinePath, err)
	}
	before := map[string]suiteCase{}
	for _, c := range baseline.Cases {
		before[c.Program+"\x00"+c.Name] = c
	}
	usable := func(a, b *timing) bool {
		return a != nil && b != nil && a.Median >= noiseFloor && b.Median >= noiseFloor
	}
	fmt.Printf("\n## Comparison with %s\n\n", baselinePath)
	var rows []string
	compared := 0
	for _, now := range current {
		was, ok := before[now.Program+"\x00"+now.Name]
		if !ok {
			continue
		}
		worse, references := 0, 0
		var changes []string
		for _, reference := range []struct {
			name     string
			now, was *timing
		}{{"Elixir", now.Elixir, was.Elixir}, {"Go", now.Go, was.Go}} {
			if !usable(now.Alchem, reference.now) || !usable(was.Alchem, reference.was) {
				continue
			}
			references++
			change := ratio(now.Alchem, reference.now) / ratio(was.Alchem, reference.was)
			if change > threshold {
				worse++
			}
			changes = append(changes, fmt.Sprintf("%s to %s against %s", ratioText(ratio(was.Alchem, reference.was)), ratioText(ratio(now.Alchem, reference.now)), reference.name))
		}
		if references == 0 {
			continue
		}
		compared++
		if worse == references {
			rows = append(rows, fmt.Sprintf("| %s | %s | %s | %s |", now.Name, microseconds(was.Alchem), microseconds(now.Alchem), strings.Join(changes, "; ")))
		}
	}
	if len(rows) == 0 {
		fmt.Printf("No regressions: none of %d comparable cases grew by more than %.2f times against every reference.\n", compared, threshold)
		return 0, nil
	}
	fmt.Printf("%d of %d comparable cases grew by more than %.2f times against every reference:\n\n", len(rows), compared, threshold)
	fmt.Println("| Case | Alchem before | Alchem now | Alchem ratio, before to now |")
	fmt.Println("| --- | --- | --- | --- |")
	fmt.Println(strings.Join(rows, "\n"))
	return len(rows), nil
}
