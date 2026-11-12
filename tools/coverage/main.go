// Command coverage measures the test coverage of the compiler, the tools and
// the runtime that compiled programs carry, and reports it by file.
//
//	go run ./tools/coverage [-min 95] [-o coverage.out] [-files] [-uncovered path]
//
// The Go tests are run once with coverage across every package in the
// repository. Programs the tests build are built with coverage too, by
// setting ALCHEM_GO_COVERAGE, and write their counts to the directory it names:
// that is how the actor runtime and the library in library.go.txt are
// measured as programs use them. Library sections no test program includes
// are counted as uncovered, so leaving code unused does not raise the figure.
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

const module = "github.com/SmithOperatingSolutions/alchem"

// measured are the packages whose code counts. Benchmarks and the generated
// programs' own main packages do not.
var measured = []string{"./cmd/...", "./compiler/...", "./lsp/...", "./testrunner/...", "./guide/..."}

type block struct {
	statements, count int
}

func main() {
	minimum := flag.Float64("min", 0, "fail when total coverage is below this percentage")
	output := flag.String("o", "", "write the merged profile here, for go tool cover -html")
	files := flag.Bool("files", false, "report every file, not only those below 100%")
	uncovered := flag.String("uncovered", "", "list the uncovered lines of files whose path contains this text")
	flag.Parse()

	work, err := os.MkdirTemp("", "alchem-coverage-*")
	check(err)
	defer os.RemoveAll(work)
	programs := filepath.Join(work, "programs")
	check(os.Mkdir(programs, 0o700))

	profile := filepath.Join(work, "go.out")
	args := append([]string{"test", "-count=1", "-timeout", "30m", "-coverpkg=" + strings.Join(measured, ","), "-coverprofile=" + profile}, append(measured, "./tests/...")...)
	test := exec.Command("go", args...)
	test.Env = append(os.Environ(), "ALCHEM_GO_COVERAGE="+programs)
	test.Stdout, test.Stderr = os.Stderr, os.Stderr
	failed := test.Run() != nil

	blocks := map[string]block{}
	readProfile(profile, blocks, func(file string) (string, int) { return file, 0 })

	text := filepath.Join(work, "programs.out")
	entries, _ := os.ReadDir(programs)
	fmt.Fprintf(os.Stderr, "coverage: %d files of counts from compiled programs\n", len(entries))
	if len(entries) > 0 {
		run("go", "tool", "covdata", "textfmt", "-i="+programs, "-o="+text)
		readProfile(text, blocks, func(file string) (string, int) {
			switch {
			case strings.HasPrefix(file, "alchem.local/actor/"):
				return module + "/compiler/" + strings.TrimPrefix(file, "alchem.local/"), 0
			case file == "alchem.local/library.go":
				return module + "/compiler/library.go.txt", compiler.LibraryLineOffset
			}
			return "", 0 // the programs' own code
		})
	}
	addLibrary(work, blocks)

	if *output != "" {
		writeProfile(*output, blocks)
	}
	total := report(blocks, *files)
	if *uncovered != "" {
		listUncovered(blocks, *uncovered)
	}
	if failed {
		fmt.Fprintln(os.Stderr, "coverage: some tests failed")
		os.Exit(1)
	}
	if total < *minimum {
		fmt.Fprintf(os.Stderr, "coverage: %.1f%% is below the minimum of %.1f%%\n", total, *minimum)
		os.Exit(1)
	}
}

var line = regexp.MustCompile(`^(.+):(\d+)\.(\d+),(\d+)\.(\d+) (\d+) (\d+)$`)

// readProfile adds a profile's blocks, keeping the highest count of a block
// seen more than once. rename maps a file to its name in the repository, or
// to "" to leave it out, and gives how many lines its positions are ahead.
func readProfile(path string, blocks map[string]block, rename func(string) (string, int)) {
	f, err := os.Open(path)
	if err != nil {
		return
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		m := line.FindStringSubmatch(scanner.Text())
		if m == nil {
			continue
		}
		file, offset := rename(m[1])
		if file == "" {
			continue
		}
		statements, _ := strconv.Atoi(m[6])
		count, _ := strconv.Atoi(m[7])
		start, _ := strconv.Atoi(m[2])
		end, _ := strconv.Atoi(m[4])
		key := fmt.Sprintf("%s:%d.%s,%d.%s", file, start-offset, m[3], end-offset, m[5])
		old := blocks[key]
		blocks[key] = block{statements, max(old.count, count)}
	}
}

// addLibrary counts every statement of library.go.txt, by instrumenting the
// whole file the way a build does and reading back where its blocks are.
func addLibrary(work string, blocks map[string]block) {
	source, err := os.ReadFile(filepath.Join("compiler", "library.go.txt"))
	check(err)
	file := filepath.Join(work, "library.go")
	header := "package main" + strings.Repeat("\n", compiler.LibraryLineOffset)
	check(os.WriteFile(file, append([]byte(header), source...), 0o600))
	out, err := exec.Command("go", "tool", "cover", "-mode=set", "-var=Counts", file).Output()
	check(err)
	out = regexp.MustCompile(`//[^\n]*`).ReplaceAll(out, nil)
	positions := regexp.MustCompile(`(?s)Pos: \[3 \* \d+\]uint32\{(.*?)\}`).FindSubmatch(out)
	statements := regexp.MustCompile(`(?s)NumStmt: \[\d+\]uint16\{(.*?)\}`).FindSubmatch(out)
	if positions == nil || statements == nil {
		fmt.Fprintln(os.Stderr, "coverage: could not read the library's blocks")
		os.Exit(1)
	}
	numbers := func(text []byte) []int {
		var values []int
		for _, field := range regexp.MustCompile(`0x[0-9a-f]+|\d+`).FindAll(text, -1) {
			v, err := strconv.ParseInt(string(field), 0, 64)
			check(err)
			values = append(values, int(v))
		}
		return values
	}
	pos, counts := numbers(positions[1]), numbers(statements[1])
	for i := range counts {
		startLine, endLine, columns := pos[3*i], pos[3*i+1], pos[3*i+2]
		key := fmt.Sprintf("%s/compiler/library.go.txt:%d.%d,%d.%d", module, startLine-compiler.LibraryLineOffset, columns&0xFFFF, endLine-compiler.LibraryLineOffset, columns>>16&0xFFFF)
		if _, seen := blocks[key]; !seen {
			blocks[key] = block{counts[i], 0}
		}
	}
}

func writeProfile(path string, blocks map[string]block) {
	keys := sortedKeys(blocks)
	var b strings.Builder
	b.WriteString("mode: set\n")
	for _, key := range keys {
		set := 0
		if blocks[key].count > 0 {
			set = 1
		}
		fmt.Fprintf(&b, "%s %d %d\n", key, blocks[key].statements, set)
	}
	check(os.WriteFile(path, []byte(b.String()), 0o644))
}

// report prints coverage by file and returns the total percentage.
func report(blocks map[string]block, all bool) float64 {
	total, covered := map[string]int{}, map[string]int{}
	for key, b := range blocks {
		file := strings.TrimPrefix(key[:strings.LastIndex(key[:strings.LastIndex(key, ",")], ":")], module+"/")
		total[file] += b.statements
		if b.count > 0 {
			covered[file] += b.statements
		}
	}
	files := make([]string, 0, len(total))
	for file := range total {
		files = append(files, file)
	}
	sort.Slice(files, func(i, j int) bool {
		mi, mj := total[files[i]]-covered[files[i]], total[files[j]]-covered[files[j]]
		if mi != mj {
			return mi > mj
		}
		return files[i] < files[j]
	})
	all_, done := 0, 0
	for _, file := range files {
		all_ += total[file]
		done += covered[file]
		if all || covered[file] < total[file] {
			fmt.Printf("%6.1f%% %5d missed  %s\n", percent(covered[file], total[file]), total[file]-covered[file], file)
		}
	}
	result := percent(done, all_)
	fmt.Printf("total: %.1f%% of %d statements, %d missed\n", result, all_, all_-done)
	return result
}

// listUncovered prints the line ranges no test reached.
func listUncovered(blocks map[string]block, match string) {
	for _, key := range sortedKeys(blocks) {
		if blocks[key].count == 0 && strings.Contains(key, match) {
			fmt.Println(strings.TrimPrefix(key, module+"/"))
		}
	}
}

func sortedKeys(blocks map[string]block) []string {
	keys := make([]string, 0, len(blocks))
	for key := range blocks {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool { return less(keys[i], keys[j]) })
	return keys
}

// less orders block keys by file, then by line.
func less(a, b string) bool {
	fa, la := split(a)
	fb, lb := split(b)
	if fa != fb {
		return fa < fb
	}
	return la < lb
}

func split(key string) (string, int) {
	colon := strings.LastIndex(key[:strings.LastIndex(key, ",")], ":")
	n, _ := strconv.Atoi(key[colon+1 : colon+1+strings.Index(key[colon+1:], ".")])
	return key[:colon], n
}

func percent(part, whole int) float64 {
	if whole == 0 {
		return 100
	}
	return 100 * float64(part) / float64(whole)
}

func run(name string, args ...string) {
	cmd := exec.Command(name, args...)
	cmd.Stderr = os.Stderr
	check(cmd.Run())
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "coverage:", err)
		os.Exit(1)
	}
}
