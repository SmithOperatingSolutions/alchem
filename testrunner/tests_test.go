package testrunner

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const library = `defmodule Calc do
  def double(n: integer): integer do
    n * 2
  end

  def sign(n: integer): string do
    if n < 0 do
      "negative"
    else
      "non-negative"
    end
  end

  def untested(n: integer): integer do
    n + 1
  end
end
`

func project(t *testing.T, tests string) string {
	t.Helper()
	dir := t.TempDir()
	for name, content := range map[string]string{"calc.alc": library, "calc_test.alc": tests} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func run(t *testing.T, dir string, options Options) (Summary, string, error) {
	t.Helper()
	files, err := TestFiles([]string{dir})
	if err != nil || len(files) != 1 {
		t.Fatalf("files=%v err=%v", files, err)
	}
	var out bytes.Buffer
	summary, err := RunTests(context.Background(), files, options, &out)
	return summary, out.String(), err
}

func TestPassingTestsWithCoverage(t *testing.T) {
	dir := project(t, `defmodule CalcTest do
  import "calc.alc"

  test "doubles" do
    assert(Calc.double(4) == 8)
  end

  describe "sign" do
    setup do
      assert(Calc.double(1) == 2)
    end

    test "is non-negative for zero" do
      assert(Calc.sign(0) == "non-negative")
    end
  end
end
`)
	summary, out, err := run(t, dir, Options{Seed: 11, Cover: true})
	if err != nil || summary.Tests != 2 || summary.Failures != 0 || summary.Seed != 11 {
		t.Fatalf("err=%v summary=%+v\n%s", err, summary, out)
	}
	if !strings.Contains(out, "2 tests, 0 failures") || !strings.Contains(out, "Randomized with seed 11") {
		t.Fatalf("summary missing:\n%s", out)
	}
	if len(summary.Coverage) != 1 {
		t.Fatalf("%+v", summary.Coverage)
	}
	// double, the if and its else branch ran; "negative" and untested did not.
	coverage := summary.Coverage[0]
	if coverage.Lines != 5 || coverage.Covered != 3 || len(coverage.Uncovered) != 2 || coverage.Uncovered[0] != 8 || coverage.Uncovered[1] != 15 {
		t.Fatalf("%+v\n%s", coverage, out)
	}
	if !strings.Contains(out, "60.0% | ") || !strings.Contains(out, "lines not run: 8, 15") {
		t.Fatalf("coverage report:\n%s", out)
	}
	if _, _, err := run(t, dir, Options{Seed: 11, Cover: true, CoverMin: 90}); err == nil || !strings.Contains(err.Error(), "below the required 90.0%") {
		t.Fatalf("got %v", err)
	}
	if _, _, err := run(t, dir, Options{Seed: 11, Cover: true, CoverMin: 60}); err != nil {
		t.Fatal(err)
	}
}

func TestFailuresAreIsolatedAndReported(t *testing.T) {
	dir := project(t, `defmodule CalcTest do
  import "calc.alc"

  test "wrong value" do
    assert(Calc.double(4) == 9)
  end

  test "crashes" do
    assert(Calc.double(1 / (Calc.double(1) - 2)) == 0)
  end

  test "still runs" do
    assert(Calc.sign(-1) == "negative")
    assert_raise("division by zero", fn -> 1 / (Calc.double(1) - 2) end)
    refute(Calc.double(1) == 3)
  end

  test "expects a failure that does not happen" do
    assert_raise("boom", fn -> Calc.double(1) end)
  end
end
`)
	summary, out, err := run(t, dir, Options{Seed: 5})
	if !errors.Is(err, ErrFailed) || summary.Tests != 4 || summary.Failures != 3 {
		t.Fatalf("err=%v summary=%+v\n%s", err, summary, out)
	}
	for _, want := range []string{
		"test wrong value (CalcTest)", "code:  Calc.double(4) == 9", "left:  8", "right: 9",
		"test crashes (CalcTest)", "division by zero",
		`expected a failure containing "boom", but the function returned`,
		"4 tests, 3 failures",
	} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
	}
	if strings.Contains(out, "test still runs (CalcTest)") {
		t.Fatalf("a passing test was reported as failed:\n%s", out)
	}
	limited, out, _ := run(t, dir, Options{Seed: 5, MaxFailures: 1})
	if limited.Failures != 1 || limited.Skipped == 0 || !strings.Contains(out, "skipped") {
		t.Fatalf("%+v\n%s", limited, out)
	}
}

// The same seed gives the same order and the same random values; a failure
// seen once can be repeated.
func TestSeedRepeatsARun(t *testing.T) {
	dir := project(t, `defmodule CalcTest do
  import "calc.alc"

  test "a" do
    IO.puts("a drew #{Enum.random(1..1000000)}")
  end

  test "b" do
    IO.puts("b drew #{Enum.random(1..1000000)}")
  end

  test "c" do
    IO.puts("c drew #{Enum.random(1..1000000)}")
  end

  test "d" do
    IO.puts("d drew #{Enum.random(1..1000000)}")
  end
end
`)
	draws := func(seed uint64) string {
		_, out, err := run(t, dir, Options{Seed: seed, Trace: true})
		if err != nil {
			t.Fatalf("%v\n%s", err, out)
		}
		var lines []string
		for _, line := range strings.Split(out, "\n") {
			if strings.Contains(line, " drew ") {
				lines = append(lines, line)
			}
		}
		if len(lines) != 4 {
			t.Fatalf("output:\n%s", out)
		}
		return strings.Join(lines, "\n")
	}
	first := draws(1234)
	if again := draws(1234); again != first {
		t.Fatalf("seed 1234 gave\n%s\nthen\n%s", first, again)
	}
	different := false
	for seed := uint64(1); seed <= 5 && !different; seed++ {
		different = draws(seed) != first
	}
	if !different {
		t.Fatal("five other seeds all repeated seed 1234")
	}
	picked, out, err := run(t, dir, Options{})
	if err != nil || picked.Seed == 0 || !strings.Contains(out, "Randomized with seed ") {
		t.Fatalf("seed=%d err=%v\n%s", picked.Seed, err, out)
	}
}

func TestOnlyAndBrokenFiles(t *testing.T) {
	dir := project(t, `defmodule CalcTest do
  import "calc.alc"

  test "doubles small numbers" do
    assert(Calc.double(1) == 2)
  end

  test "names the sign" do
    assert(Calc.sign(1) == "non-negative")
  end
end
`)
	summary, out, err := run(t, dir, Options{Seed: 3, Only: "sign", Trace: true})
	if err != nil || summary.Tests != 1 || summary.Excluded != 1 || !strings.Contains(out, "* test names the sign") || strings.Contains(out, "doubles small") {
		t.Fatalf("err=%v summary=%+v\n%s", err, summary, out)
	}
	os.WriteFile(filepath.Join(dir, "calc_test.alc"), []byte("defmodule CalcTest do\n  test \"typo\" do\n    assert(missing(1) == 2)\n  end\nend\n"), 0600)
	_, out, err = run(t, dir, Options{Seed: 3})
	if !errors.Is(err, ErrFailed) || !strings.Contains(out, "did not compile") || !strings.Contains(out, "undefined function missing") || !strings.Contains(out, "1 file not run") {
		t.Fatalf("err=%v\n%s", err, out)
	}
}

// Describe blocks nest: a test's name carries every enclosing describe, and
// setup blocks run outermost first for everything beneath them.
func TestNestedDescribes(t *testing.T) {
	dir := project(t, `defmodule CalcTest do
  import "calc.alc"

  setup do
    IO.write("[top]")
  end

  test "outside" do
    IO.puts(" outside")
  end

  describe "double" do
    setup do
      IO.write("[double]")
    end

    test "of zero" do
      IO.puts(" zero")
      assert(Calc.double(0) == 0)
    end

    describe "of a negative" do
      setup do
        IO.write("[negative]")
      end

      test "stays negative" do
        IO.puts(" negative")
        assert(Calc.double(-2) == 4)
      end

      describe "deeply" do
        test "nested" do
          IO.puts(" deep")
        end
      end
    end
  end

  describe "sign" do
    test "of one" do
      IO.puts(" sign")
    end
  end
end
`)
	summary, out, err := run(t, dir, Options{Seed: 9, Trace: true})
	if !errors.Is(err, ErrFailed) || summary.Tests != 5 || summary.Failures != 1 {
		t.Fatalf("err=%v summary=%+v\n%s", err, summary, out)
	}
	for _, want := range []string{
		"[top] outside\n", "[top][double] zero\n", "[top][double][negative] negative\n", "[top][double][negative] deep\n", "[top] sign\n",
		"* test double of zero", "* test double of a negative deeply nested", "* test sign of one",
		"1) test double of a negative stays negative (CalcTest)", "left:  -4",
	} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
	}
	only, out, err := run(t, dir, Options{Seed: 9, Only: "of a negative deeply"})
	if err != nil || only.Tests != 1 || only.Excluded != 4 {
		t.Fatalf("err=%v summary=%+v\n%s", err, only, out)
	}
}

// Setup blocks build a context that the blocks and tests beneath them
// receive; setup_all runs once.
func TestContextTagsAndDoctests(t *testing.T) {
	dir := t.TempDir()
	files := map[string]string{
		"calc.alc": `defmodule Calc do
  @moduledoc ` + "\"\"\"" + `
  Small arithmetic helpers.
  ` + "\"\"\"" + `

  @doc ` + "\"\"\"" + `
  Doubles a number.

      alx> Calc.double(4)
      8
      alx> n = Calc.double(1)
      alx> Calc.double(n)
      4
  ` + "\"\"\"" + `
  def double(n: integer): integer do
    n * 2
  end

  @doc ` + "\"\"\"" + `
  Finds the first even number.

      alx> Calc.first_even([1, 4, 6])
      some(4)
      alx> Calc.first_even([1])
      none
  ` + "\"\"\"" + `
  def first_even(xs: list[integer]): option[integer] do
    Enum.find(xs, &(rem(&1, 2) == 0))
  end

  # This example is wrong on purpose.
  @doc ` + "\"\"\"" + `
      alx> Calc.triple(2)
      7
  ` + "\"\"\"" + `
  def triple(n: integer): integer do
    n * 3
  end

  # A comment is not documentation:
  #     alx> Calc.undocumented(1)
  #     99
  def undocumented(n: integer): integer do
    n
  end
end
` + "",
		"calc_test.alc": `defmodule CalcTest do
  import "calc.alc"
  doctest Calc

  struct Context do
    base: integer
    log: list[string]
  end

  setup_all do
    IO.puts("[all]")
    10
  end

  setup base do
    %Context{base: base, log: ["top"]}
  end

  test "receives the context", context do
    assert(context.base == 10 and context.log == ["top"])
  end

  test "matches on the context", %Context{base: base} do
    assert(Calc.double(base) == 20)
  end

  test "needs no context" do
    assert(true)
  end

  describe "nested" do
    setup context do
      %Context{context | log: context.log ++ ["nested"]}
    end

    setup do
      IO.write("")
    end

    @tag "slow"
    test "sees every setup above it", context do
      assert(context.log == ["top", "nested"])
    end

    @tag "skip"
    test "is skipped by default" do
      flunk("should not run")
    end
  end

  @tag "integration"
  describe "tagged group" do
    test "inherits the tag" do
      assert(true)
    end
  end
end
`,
	}
	for name, content := range files {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	summary, out, err := run(t, dir, Options{Seed: 4, Trace: true})
	// Three doctests (one of them wrong) and five tests run; the skipped one does not.
	if !errors.Is(err, ErrFailed) || summary.Tests != 8 || summary.Failures != 1 || summary.Excluded != 1 {
		t.Fatalf("err=%v summary=%+v\n%s", err, summary, out)
	}
	for _, want := range []string{
		"* test doctest Calc.double/1", "* test doctest Calc.first_even/1", "* test doctest Calc.triple/1", "[failed]",
		"code:  Calc.triple(2) == 7", "left:  6", "calc.alc:36",
		"* test nested sees every setup above it", "* test receives the context",
	} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
	}
	if strings.Count(out, "[all]") != 1 || strings.Contains(out, "undocumented") {
		t.Fatalf("setup_all or doctests wrong:\n%s", out)
	}
	slow, out, _ := run(t, dir, Options{Seed: 4, Tags: []string{"slow"}})
	if slow.Tests != 1 || slow.Failures != 0 {
		t.Fatalf("%+v\n%s", slow, out)
	}
	rest, out, _ := run(t, dir, Options{Seed: 4, Exclude: []string{"slow", "integration"}})
	if rest.Tests != 6 || rest.Excluded != 3 {
		t.Fatalf("%+v\n%s", rest, out)
	}
	skipped, out, err := run(t, dir, Options{Seed: 4, Tags: []string{"skip"}})
	if !errors.Is(err, ErrFailed) || skipped.Tests != 1 || !strings.Contains(out, "should not run") {
		t.Fatalf("err=%v %+v\n%s", err, skipped, out)
	}
	// A test that asks for a context nobody provides does not compile.
	os.WriteFile(filepath.Join(dir, "calc_test.alc"), []byte("defmodule CalcTest do\n  test \"wants\", context do\n    assert(context == 1)\n  end\nend\n"), 0600)
	if _, out, err := run(t, dir, Options{Seed: 4}); !errors.Is(err, ErrFailed) || !strings.Contains(out, "no setup block above it ends in a value") {
		t.Fatalf("err=%v\n%s", err, out)
	}
}

func TestExitHooksCaptureAndReceive(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "hooks_test.alc")
	source := `defmodule HooksTest do
  test "cleanup runs after a passing test, last registered first" do
    on_exit(fn -> IO.puts("[first registered]") end)
    on_exit(fn -> IO.puts("[second registered]") end)
    assert(capture_io(fn -> IO.puts("inside") end) == "inside\n")
  end

  test "cleanup runs after a failing test" do
    on_exit(fn -> IO.puts("[after failure]") end)
    assert(1 == 2)
  end

  test "a failing cleanup fails the test" do
    on_exit(fn -> File.rm!("no_such_directory/cleanup_broke.txt") end)
  end

  test "captured output is passed on when the function fails" do
    capture_io(fn ->
      IO.puts("[written before failing]")
      div(1, 0)
    end)
  end

  test "the default wait comes from the runner" do
    me: pid[integer] = Process.self(1)
    started = Time.monotonic()
    refute_receive(me, _)
    assert(Time.monotonic() - started >= 240)
  end

  test "messages" do
    me: pid[integer] = Process.self(4)
    Process.send(me, 7, 100)
    Process.send(me, 12, 100)
    assert_receive(me, n when n > 10)
    assert(n == 12)
    assert_receive(me, 7)
    refute_receive(me, _, 5)
    refute_received(me, _)
    Process.send(me, 8, 100)
    wanted = 9
    assert_receive(me, ^wanted, 20, "the nine never came")
  end
end
`
	if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	summary, err := RunTests(context.Background(), []string{path}, Options{Seed: 3, Trace: true, ReceiveTimeout: 250 * time.Millisecond}, &out)
	text := out.String()
	if err == nil || summary.Tests != 6 || summary.Failures != 4 {
		t.Fatalf("%+v %v\n%s", summary, err, text)
	}
	for _, want := range []string{
		"[second registered]\n[first registered]", "[after failure]", "on_exit failed:", "cleanup_broke.txt",
		"[written before failing]", "division by zero", "the nine never came", "pattern: ^wanted", "pinned:  wanted = 9", "mailbox: 8",
	} {
		if !strings.Contains(text, want) {
			t.Errorf("output lacks %q:\n%s", want, text)
		}
	}
}

// Files run at once must report exactly what they report one at a time, in
// the same order, including a file that fails and one that does not compile.
func TestParallelFilesReportInOrder(t *testing.T) {
	dir := t.TempDir()
	var files []string
	for i := 0; i < 6; i++ {
		body := fmt.Sprintf("    IO.puts(\"[file %d]\")\n    Process.sleep(%d)\n    assert(%d != 3)\n", i, (6-i)*15, i)
		if i == 4 {
			body = "    assert(undefined_name)\n"
		}
		path := filepath.Join(dir, fmt.Sprintf("part%d_test.alc", i))
		source := fmt.Sprintf("defmodule Part%dTest do\n  test \"runs\" do\n%s  end\nend\n", i, body)
		if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
			t.Fatal(err)
		}
		files = append(files, path)
	}
	run := func(jobs int) (Summary, string) {
		var out bytes.Buffer
		summary, err := RunTests(context.Background(), files, Options{Seed: 5, Jobs: jobs}, &out)
		if err == nil {
			t.Fatalf("jobs=%d: a failing run reported success", jobs)
		}
		var kept []string
		for _, line := range strings.Split(out.String(), "\n") {
			if !strings.HasPrefix(line, "Finished in") {
				kept = append(kept, line)
			}
		}
		return summary, strings.Join(kept, "\n")
	}
	serialSummary, serial := run(1)
	parallelSummary, parallel := run(6)
	if serial != parallel {
		t.Fatalf("output differs.\none at a time:\n%s\nat once:\n%s", serial, parallel)
	}
	if serialSummary.Tests != 5 || serialSummary.Failures != 1 || parallelSummary.Tests != 5 || parallelSummary.Failures != 1 {
		t.Fatalf("summaries: %+v %+v", serialSummary, parallelSummary)
	}
	if !strings.Contains(parallel, "did not compile") || strings.Count(parallel, "[file ") != 5 {
		t.Fatalf("unexpected output:\n%s", parallel)
	}
}

// A program started through a port must not outlive the test that started
// it: when the test's processes are stopped the program is ended, so the
// run finishes at once instead of waiting for it.
func TestPortProgramEndsWithItsOwner(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "port_test.alc")
	source := `defmodule PortTest do
  test "leaves a program running" do
    me: pid[PortEvent] = Process.self(8)
    started = case Port.open("cat", Enum.take([""], 0), me) do
      ok(reader) -> Port.command(reader, "still here\n")
      error(_) -> false
    end
    assert(started)
    assert_receive(me, PortEvent.data("still here"), 5000)
  end
end
`
	if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	began := time.Now()
	summary, err := RunTests(context.Background(), []string{path}, Options{Seed: 1}, &out)
	if err != nil || summary.Tests != 1 || summary.Failures != 0 {
		t.Fatalf("%+v %v\n%s", summary, err, out.String())
	}
	// The build takes most of this; a program left running would add the
	// whole shutdown wait, or never return.
	if elapsed := time.Since(began); elapsed > 20*time.Second || strings.Contains(out.String(), "shutdown") {
		t.Fatalf("the run took %v:\n%s", elapsed, out.String())
	}
}
