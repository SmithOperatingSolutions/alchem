package guide

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

func TestAgentGuideCoversEverything(t *testing.T) {
	text := AgentGuide()
	for _, command := range Commands {
		if !strings.Contains(text, "`"+command.Usage+"`") {
			t.Errorf("guide omits command %s", command.Name)
		}
	}
	for _, topic := range syntax.Topics {
		if !strings.Contains(text, "- `"+topic.Name+"`: ") {
			t.Errorf("guide omits topic %s", topic.Name)
		}
	}
	for _, module := range syntax.Modules {
		if !strings.Contains(text, "- `"+module.Name+"` (") {
			t.Errorf("guide omits module %s", module.Name)
		}
		if len(functionsOf(module.Name)) == 0 {
			t.Errorf("module %s has no functions", module.Name)
		}
	}
	known := functionsByName()
	groups := map[string]bool{}
	for _, module := range syntax.Modules {
		groups[module.Group] = true
	}
	for group, names := range featured {
		if !groups[group] {
			t.Errorf("featured examples for unknown group %q", group)
		}
		for _, name := range names {
			if known[name].Examples == "" {
				t.Errorf("featured function %s has no example", name)
			}
		}
	}
	// The overview stays small enough to read in one go.
	if len(text) > 16000 {
		t.Errorf("agent guide is %d bytes; keep the overview short and move detail into topics", len(text))
	}
	var data map[string]any
	if err := json.Unmarshal([]byte(AgentGuideJSON()), &data); err != nil || data["commands"] == nil || data["topics"] == nil || data["modules"] == nil {
		t.Errorf("agent guide JSON: %v", err)
	}
}

func TestSyntaxAndDocLookups(t *testing.T) {
	text, err := Syntax("with")
	if err != nil || !strings.Contains(text, "# with") || !strings.Contains(text, "```elixir") || !strings.Contains(text, "alchem syntax option-result") {
		t.Fatalf("syntax with: %v\n%s", err, text)
	}
	if _, err := Syntax("comprehension"); err == nil || !strings.Contains(err.Error(), "alchem syntax lists them") {
		t.Fatalf("unknown topic: %v", err)
	}
	all := SyntaxAll()
	for _, topic := range syntax.Topics {
		if !strings.Contains(all, "# "+topic.Name+"\n\n"+topic.Summary) {
			t.Errorf("syntax --all omits %s", topic.Name)
		}
	}
	text, err = Doc("Enum.chunk_every", false, false)
	if err != nil || !strings.Contains(text, "Enum.chunk_every(enum[a], integer) -> list[list[a]]") || !strings.Contains(text, "alx> Enum.chunk_every([10, 20, 30, 40, 50], 2)") {
		t.Fatalf("doc function: %v\n%s", err, text)
	}
	// Case and an arity suffix do not matter, and bare names are found.
	for _, query := range []string{"enum.map/2", "hd", "assert_raise", "Process.send"} {
		if _, err := Doc(query, false, false); err != nil {
			t.Errorf("doc %s: %v", query, err)
		}
	}
	text, err = Doc("stream", false, false)
	if err != nil || !strings.Contains(text, "Stream (Collections)") || !strings.Contains(text, "  chunk_every") || strings.Contains(text, "alx>") {
		t.Fatalf("doc module: %v\n%s", err, text)
	}
	if full, _ := Doc("Stream", true, false); !strings.Contains(full, "alx> Stream.cycle([1, 2])") {
		t.Fatalf("doc --all module lacks examples")
	}
	if _, err := Doc("Enum.mapp", false, false); err == nil || !strings.Contains(err.Error(), "Enum.map") {
		t.Fatalf("unknown function should suggest: %v", err)
	}
	var function struct {
		Name       string
		Signatures []string
		Examples   string
	}
	data, _ := Doc("Map.get", false, true)
	if err := json.Unmarshal([]byte(data), &function); err != nil || function.Name != "Map.get" || len(function.Signatures) != 2 || function.Examples == "" {
		t.Fatalf("doc --json: %v %+v", err, function)
	}
	found, err := Search("chunk", false)
	if err != nil || !strings.Contains(found, "Stream.chunk_every") || !strings.Contains(found, "File.stream!") || !strings.Contains(found, "topic    streams") {
		t.Fatalf("search: %v\n%s", err, found)
	}
	if _, err := Search("zzzzzz", false); err == nil {
		t.Fatal("a search without matches should say so")
	}
}

func TestFileDoc(t *testing.T) {
	path := filepath.Join(t.TempDir(), "shop.alc")
	source := "defmodule Shop do\n  @moduledoc \"\"\"\n  Prices and totals.\n  \"\"\"\n\n  @typedoc \"One line of an order.\"\n  struct Line do\n    name: string\n    cents: integer\n  end\n\n  @doc \"\"\"\n  Adds up the lines.\n\n      alx> Shop.total([])\n      0\n  \"\"\"\n  def total([]: list[Line]): integer do\n    0\n  end\n\n  def total([line | rest]) do\n    line.cents + total(rest)\n  end\n\n  def untold(n: integer): integer do\n    n\n  end\n\n  defp hidden(n: integer): integer do\n    n\n  end\nend\n"
	if err := os.WriteFile(path, []byte(source), 0o644); err != nil {
		t.Fatal(err)
	}
	text, err := FileDoc(path, false)
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"Shop\n\nPrices and totals.", "struct Line { name: string, cents: integer }", "One line of an order.", "-> integer\n\n    Adds up the lines.", "alx> Shop.total([])", "untold(n: integer) -> integer\n\n    (undocumented)"} {
		if !strings.Contains(text, want) {
			t.Errorf("file doc lacks %q:\n%s", want, text)
		}
	}
	if strings.Contains(text, "hidden") || strings.Count(text, "total(") != 2 {
		t.Errorf("private functions or repeated clauses shown:\n%s", text)
	}
}

func TestInstall(t *testing.T) {
	dir := t.TempDir()
	first, err := Install("claude", "project", dir, false)
	if err != nil || first.Action != "created" {
		t.Fatalf("%+v %v", first, err)
	}
	data, _ := os.ReadFile(filepath.Join(dir, ".claude", "skills", "alchem", "SKILL.md"))
	if !strings.HasPrefix(string(data), "---\nname: alchem\ndescription: ") || !strings.Contains(string(data), "alchem agent-guide") {
		t.Fatalf("skill file:\n%s", data)
	}
	if again, _ := Install("claude", "project", dir, false); again.Action != "unchanged" {
		t.Fatalf("second install: %+v", again)
	}
	os.WriteFile(first.Path, []byte("mine"), 0o644)
	if _, err := Install("claude", "project", dir, false); err == nil || !strings.Contains(err.Error(), "--force") {
		t.Fatalf("an edited file needs --force: %v", err)
	}
	if forced, err := Install("claude", "project", dir, true); err != nil || forced.Action != "updated" {
		t.Fatalf("%+v %v", forced, err)
	}

	// A shared file keeps what its owner wrote; only the block is managed.
	agents := filepath.Join(dir, "AGENTS.md")
	os.WriteFile(agents, []byte("# House rules\n\nBe kind.\n"), 0o644)
	if added, err := Install("agents", "project", dir, false); err != nil || added.Action != "updated" {
		t.Fatalf("%+v %v", added, err)
	}
	text, _ := os.ReadFile(agents)
	if !strings.HasPrefix(string(text), "# House rules\n\nBe kind.\n\n"+blockBegin+"\n") || !strings.HasSuffix(string(text), blockEnd+"\n") {
		t.Fatalf("managed block:\n%s", text)
	}
	stale := strings.Replace(string(text), "alchem agent-guide", "alchem old-guide", 1) + "\nAfter the block.\n"
	os.WriteFile(agents, []byte(stale), 0o644)
	if refreshed, err := Install("agents", "project", dir, false); err != nil || refreshed.Action != "updated" {
		t.Fatalf("%+v %v", refreshed, err)
	}
	text, _ = os.ReadFile(agents)
	if strings.Contains(string(text), "old-guide") || !strings.HasSuffix(string(text), "After the block.\n") || strings.Count(string(text), blockBegin) != 1 {
		t.Fatalf("refreshed block:\n%s", text)
	}
	if same, _ := Install("agents", "project", dir, false); same.Action != "unchanged" {
		t.Fatalf("%+v", same)
	}

	if _, err := Install("cursor", "user", dir, false); err == nil {
		t.Fatal("cursor has no user scope")
	}
	if _, err := Install("emacs", "project", dir, false); err == nil || !strings.Contains(err.Error(), "claude") {
		t.Fatalf("unknown agent: %v", err)
	}
	for _, target := range Targets {
		if _, err := Install(target.Name, "project", t.TempDir(), false); err != nil {
			t.Errorf("%s: %v", target.Name, err)
		}
	}
}
