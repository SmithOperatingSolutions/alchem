package testrunner

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The test modules among the fixtures pass.
func TestFixtureTestModules(t *testing.T) {
	files, err := filepath.Glob(filepath.Join("..", "tests", "fixtures", "*_test.alc"))
	if err != nil || len(files) == 0 {
		t.Fatalf("no fixture test modules: %v", err)
	}
	var out bytes.Buffer
	summary, err := RunTests(context.Background(), files, Options{Seed: 7}, &out)
	if err != nil || summary.Failures != 0 || summary.Tests == 0 {
		t.Fatalf("%+v %v\n%s", summary, err, out.String())
	}
}

// Tags with values select tests by name or by name and value, and the
// timeout tag gives a test its own time limit.
func TestTagValues(t *testing.T) {
	dir := t.TempDir()
	source := `defmodule TaggedTest do
  @tag kind: :db, owner: "ada"
  test "database" do
    assert(true)
  end

  @tag kind: :cache
  test "cache" do
    assert(true)
  end

  @tag timeout: 50
  test "too slow for its own limit" do
    Process.sleep(2000)
  end

  @tag timeout: :infinity
  @tag skip: "not today"
  test "skipped with a reason" do
    assert(false)
  end
end
`
	path := filepath.Join(dir, "tagged_test.alc")
	if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct {
		tags, exclude   []string
		tests, failures int
		output          string
	}{
		{tags: []string{"kind:db"}, tests: 1},
		{tags: []string{"kind"}, tests: 2},
		{tags: []string{"owner:bob"}, tests: 0},
		{exclude: []string{"kind"}, tests: 1, failures: 1, output: "timed out after 50ms"},
		{tags: []string{"skip"}, tests: 1, failures: 1},
	} {
		var out bytes.Buffer
		summary, _ := RunTests(context.Background(), []string{path}, Options{Seed: 1, Tags: c.tags, Exclude: c.exclude}, &out)
		if summary.Tests != c.tests || summary.Failures != c.failures || !strings.Contains(out.String(), c.output) {
			t.Errorf("tags %v exclude %v: %+v\n%s", c.tags, c.exclude, summary, out.String())
		}
	}
}

// Receive assertions that fail say what was in the mailbox.
func TestReceiveFailuresReport(t *testing.T) {
	dir := t.TempDir()
	source := `defmodule MailboxTest do
  def fill(me: pid[string]): integer do
    for n <- 1..12 do
      Process.send(me, "m" <> to_string(n), 100)
    end
    12
  end

  test "waits for a message that never comes" do
    me: pid[string] = Process.self(32)
    fill(me)
    assert_receive(me, "never", 10)
  end

  test "looks for one that has not arrived" do
    me: pid[string] = Process.self(32)
    fill(me)
    assert_received(me, "never")
  end

  test "refutes one that comes" do
    me: pid[string] = Process.self(32)
    fill(me)
    refute_receive(me, "m1", 10, "custom text")
  end

  test "refutes one that has arrived" do
    me: pid[string] = Process.self(32)
    fill(me)
    refute_received(me, "m2")
  end
end
`
	path := filepath.Join(dir, "mailbox_test.alc")
	if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	summary, _ := RunTests(context.Background(), []string{path}, Options{Seed: 1}, &out)
	report := out.String()
	if summary.Failures != 4 {
		t.Fatalf("%+v\n%s", summary, report)
	}
	for _, want := range []string{"last 10 of 12", "has arrived", "custom text", "a message matching the pattern"} {
		if !strings.Contains(report, want) {
			t.Errorf("the report does not say %q:\n%s", want, report)
		}
	}
}
