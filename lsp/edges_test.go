package lsp

import (
	"bufio"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The requests editors send less often: unknown methods, documents saved
// without their text, completion with no module before the cursor, and
// questions about positions that hold nothing.
func TestLanguageServerEdges(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "edges.alc")
	text := "defmodule Edges do\n  struct Point do\n    x: integer\n  end\n\n  defp hidden(n: integer): integer do\n    n\n  end\n\n  def main() do\n    p = %Point{x: hidden(1)}\n    IO.inspect(p)\n  end\nend\n"
	os.WriteFile(path, []byte(text), 0o644)
	uri := uriOf(path)
	c := start(t)
	c.request("initialize", map[string]any{"rootUri": uriOf(dir)})
	c.notify("textDocument/didOpen", map[string]any{"textDocument": map[string]any{"uri": uri, "text": text}})
	if found := c.diagnostics(uri); len(found) != 0 {
		t.Fatalf("diagnostics: %v", found)
	}
	// A save without text checks what is on disk.
	c.notify("textDocument/didSave", map[string]any{"textDocument": map[string]any{"uri": uri}})
	c.diagnostics(uri)
	// A change with no content changes is ignored.
	c.notify("textDocument/didChange", map[string]any{"textDocument": map[string]any{"uri": uri}, "contentChanges": []any{}})

	completion := func(line, character int) []any {
		result := c.request("textDocument/completion", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": line, "character": character}})
		items, _ := result.([]any)
		return items
	}
	labels := func(items []any) string {
		var out []string
		for _, item := range items {
			out = append(out, item.(map[string]any)["label"].(string))
		}
		return strings.Join(out, " ")
	}
	// At the start of a line, every function, module and keyword.
	if got := labels(completion(11, 4)); !strings.Contains(got, "hidden") || !strings.Contains(got, "Enum") || !strings.Contains(got, "defmodule") {
		t.Fatalf("completion: %s", got)
	}
	if hover := c.request("textDocument/hover", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 4, "character": 0}}); hover != nil {
		t.Fatalf("hover on an empty line: %v", hover)
	}
	if found := c.request("textDocument/definition", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 10, "character": 19}}); found == nil {
		t.Fatal("no definition for hidden")
	}
	if found := c.request("textDocument/definition", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 4, "character": 0}}); found != nil {
		t.Fatalf("definition on an empty line: %v", found)
	}
	symbols := c.request("textDocument/documentSymbol", map[string]any{"textDocument": map[string]any{"uri": uri}}).([]any)
	if len(symbols) < 3 {
		t.Fatalf("symbols: %v", symbols)
	}
	unknown := "file://" + filepath.ToSlash(filepath.Join(dir, "never-opened.alc"))
	if got := c.request("textDocument/documentSymbol", map[string]any{"textDocument": map[string]any{"uri": unknown}}); got != nil && len(got.([]any)) != 0 {
		t.Fatalf("symbols of an unknown document: %v", got)
	}

	// An unknown request is answered with an error; an unknown
	// notification is ignored.
	c.notify("workspace/somethingNew", map[string]any{})
	c.next++
	c.write(map[string]any{"id": c.next, "method": "workspace/unknown", "params": map[string]any{}})
	for {
		m := c.receive()
		if m["id"] == float64(c.next) {
			if m["error"] == nil {
				t.Fatalf("unknown method answered: %v", m)
			}
			break
		}
	}
	c.notify("textDocument/didClose", map[string]any{"textDocument": map[string]any{"uri": uri}})
	if found := c.diagnostics(uri); len(found) != 0 {
		t.Fatalf("diagnostics after close: %v", found)
	}
	c.request("shutdown", nil)
}

func TestReadRejectsMessagesWithoutLength(t *testing.T) {
	if _, err := read(bufio.NewReader(strings.NewReader("X-Other: 1\r\n\r\n{}"))); err == nil {
		t.Fatal("a message without Content-Length was read")
	}
	if _, err := read(bufio.NewReader(strings.NewReader(""))); err == nil {
		t.Fatal("an empty stream was read")
	}
}
