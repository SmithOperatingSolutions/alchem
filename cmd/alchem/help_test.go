package main

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/guide"
)

// The reference files in docs/ are written by `alchem docs`; this fails
// when a change to the library, the syntax topics or a command's options
// has not been followed by running it.
func TestGeneratedDocsAreCurrent(t *testing.T) {
	var out, errOut bytes.Buffer
	if code := run(context.Background(), []string{"docs", "--check", "--dir", filepath.Join("..", "..", "docs")}, &out, &errOut); code != 0 {
		t.Fatalf("%s%s\nrun: go run ./cmd/alchem docs", out.String(), errOut.String())
	}
}

func TestHelpCommands(t *testing.T) {
	var out, errOut bytes.Buffer
	invoke := func(args ...string) int {
		out.Reset()
		errOut.Reset()
		return run(context.Background(), args, &out, &errOut)
	}
	// Every command is described, and every option it parses is listed.
	for _, command := range guide.Commands {
		if flagsFor(command.Name, &settings{}, &errOut) == nil {
			t.Errorf("guide describes %s, which the command line does not have", command.Name)
		}
		for _, option := range command.Flags {
			if option.Summary == "" {
				t.Errorf("%s --%s has no description", command.Name, option.Name)
			}
		}
	}
	if invoke() != 2 || !strings.Contains(errOut.String(), "agent-guide") {
		t.Fatalf("usage: %s", errOut.String())
	}
	if invoke("help") != 0 || !strings.Contains(out.String(), "commands:") {
		t.Fatalf("help: %s", out.String())
	}
	if invoke("agent-guide") != 0 || !strings.Contains(out.String(), "# Alchem agent guide") {
		t.Fatalf("agent-guide: %s%s", out.String(), errOut.String())
	}
	if invoke("agent-guide", "--json") != 0 || !strings.HasPrefix(out.String(), "{") {
		t.Fatalf("agent-guide --json: %s", out.String())
	}
	if invoke("syntax") != 0 || !strings.Contains(out.String(), "  for  ") {
		t.Fatalf("syntax: %s", out.String())
	}
	if invoke("syntax", "for") != 0 || !strings.Contains(out.String(), "for n <- 1..5, do: n * n") {
		t.Fatalf("syntax for: %s", out.String())
	}
	if invoke("syntax", "nope") != 1 || !strings.Contains(errOut.String(), "no syntax topic") {
		t.Fatalf("unknown topic: %s", errOut.String())
	}
	if invoke("syntax", "--json", "for") != 0 || !strings.Contains(out.String(), "\"name\": \"for\"") {
		t.Fatalf("syntax --json: %s", out.String())
	}
	if invoke("doc") != 0 || !strings.Contains(out.String(), "  Enum  ") {
		t.Fatalf("doc: %s", out.String())
	}
	if invoke("doc", "Enum.map") != 0 || !strings.Contains(out.String(), "alx> Enum.map([1, 2, 3], fn n -> n * 2 end)") {
		t.Fatalf("doc Enum.map: %s", out.String())
	}
	if invoke("doc", "--search", "leap") != 0 || !strings.Contains(out.String(), "Date.leap_year?") {
		t.Fatalf("doc --search: %s", out.String())
	}
	if invoke("doc", "Nope.nothing") != 1 {
		t.Fatal("unknown function accepted")
	}
	dir := t.TempDir()
	if invoke("agent-install", "--list") != 0 || !strings.Contains(out.String(), "claude") {
		t.Fatalf("agent-install --list: %s", out.String())
	}
	if invoke("agent-install", "--dir", dir, "agents") != 0 || !strings.HasPrefix(out.String(), "created ") {
		t.Fatalf("agent-install: %s%s", out.String(), errOut.String())
	}
	if data, err := os.ReadFile(filepath.Join(dir, "AGENTS.md")); err != nil || !strings.Contains(string(data), "alchem agent-guide") {
		t.Fatalf("AGENTS.md: %v", err)
	}
	if invoke("agent-install") != 1 || invoke("agent-install", "nobody") != 1 {
		t.Fatal("agent-install without a known agent succeeded")
	}
	// docs writes the files, reports them, and is then up to date.
	if invoke("docs", "--check", "--dir", dir) != 1 || !strings.Contains(out.String(), "library-reference.md") {
		t.Fatalf("docs --check on an empty directory: %s", out.String())
	}
	if invoke("docs", "--dir", dir) != 0 || strings.Count(out.String(), "\n") != 4 {
		t.Fatalf("docs: %s%s", out.String(), errOut.String())
	}
	if invoke("docs", "--check", "--dir", dir) != 0 || out.String() != "" {
		t.Fatalf("docs --check after writing: %s", out.String())
	}
}
