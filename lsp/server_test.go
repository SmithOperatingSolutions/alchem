package lsp

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// client drives a server over pipes, as an editor would.
type client struct {
	t      *testing.T
	in     io.Writer
	out    *bufio.Reader
	next   int
	queued []map[string]any
}

func start(t *testing.T) *client {
	clientToServer, serverIn := io.Pipe()
	serverOut, serverToClient := io.Pipe()
	go func() {
		Serve(context.Background(), clientToServer, serverToClient)
		serverToClient.Close()
	}()
	t.Cleanup(func() { serverIn.Close() })
	return &client{t: t, in: serverIn, out: bufio.NewReader(serverOut)}
}

func (c *client) write(m map[string]any) {
	m["jsonrpc"] = "2.0"
	data, _ := json.Marshal(m)
	fmt.Fprintf(c.in, "Content-Length: %d\r\n\r\n%s", len(data), data)
}

func (c *client) receive() map[string]any {
	if len(c.queued) > 0 {
		m := c.queued[0]
		c.queued = c.queued[1:]
		return m
	}
	done := make(chan map[string]any, 1)
	go func() {
		body, err := read(c.out)
		if err != nil {
			done <- nil
			return
		}
		var m map[string]any
		json.Unmarshal(body, &m)
		done <- m
	}()
	select {
	case m := <-done:
		if m == nil {
			c.t.Fatal("server closed")
		}
		return m
	case <-time.After(60 * time.Second):
		c.t.Fatal("no message from the server")
	}
	return nil
}

func (c *client) request(method string, params any) any {
	c.next++
	id := c.next
	c.write(map[string]any{"id": id, "method": method, "params": params})
	for {
		m := c.receive()
		if got, ok := m["id"].(float64); ok && int(got) == id {
			if m["error"] != nil {
				c.t.Fatalf("%s: %v", method, m["error"])
			}
			return m["result"]
		}
		c.queued = append(c.queued, m)
	}
}

func (c *client) notify(method string, params any) {
	c.write(map[string]any{"method": method, "params": params})
}

// diagnostics waits for the diagnostics published for a document.
func (c *client) diagnostics(uri string) []any {
	for i := 0; ; i++ {
		var m map[string]any
		if i < len(c.queued) {
			m = c.queued[i]
		} else {
			m = c.receive()
			c.queued = append(c.queued, m)
		}
		if m["method"] == "textDocument/publishDiagnostics" {
			params := m["params"].(map[string]any)
			if params["uri"] == uri {
				c.queued = append(c.queued[:i], c.queued[i+1:]...)
				return params["diagnostics"].([]any)
			}
		}
	}
}

func TestLanguageServer(t *testing.T) {
	dir := t.TempDir()
	os.MkdirAll(filepath.Join(dir, "lib"), 0o755)
	os.WriteFile(filepath.Join(dir, "lib", "greet.alc"), []byte(`defmodule Greet do
  @doc """
  Greets someone.
  """
  def hello(name: string): string do
    "Hello, " <> name
  end
end
`), 0o644)
	main := filepath.Join(dir, "main.alc")
	broken := "defmodule Main do\n  import \"lib/greet.alc\"\n\n  def main() do\n    IO.puts(Greet.hello(1))\n  end\nend\n"
	os.WriteFile(main, []byte(broken), 0o644)
	uri := uriOf(main)
	c := start(t)
	capabilities := c.request("initialize", map[string]any{"rootUri": uriOf(dir)}).(map[string]any)["capabilities"].(map[string]any)
	if capabilities["hoverProvider"] != true || capabilities["completionProvider"] == nil {
		t.Fatalf("capabilities: %v", capabilities)
	}
	c.notify("initialized", map[string]any{})
	c.notify("textDocument/didOpen", map[string]any{"textDocument": map[string]any{"uri": uri, "languageId": "alchem", "version": 1, "text": broken}})
	found := c.diagnostics(uri)
	if len(found) != 1 || !strings.Contains(found[0].(map[string]any)["message"].(string), "string") {
		t.Fatalf("diagnostics: %v", found)
	}
	if line := found[0].(map[string]any)["range"].(map[string]any)["start"].(map[string]any)["line"]; line != float64(4) {
		t.Fatalf("diagnostic line: %v", line)
	}
	// The unsaved fix clears the diagnostic.
	fixed := "defmodule Main do\n  import \"lib/greet.alc\"\n\n  def main() do\n    IO.puts(Greet.hello(\"ada\"))\n    IO.puts(Enum.join([\"a\"], \",\"))\n  end\nend\n"
	c.notify("textDocument/didChange", map[string]any{"textDocument": map[string]any{"uri": uri, "version": 2}, "contentChanges": []any{map[string]any{"text": fixed}}})
	if found := c.diagnostics(uri); len(found) != 0 {
		t.Fatalf("after the fix: %v", found)
	}
	hover := c.request("textDocument/hover", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 5, "character": 18}})
	if text := fmt.Sprint(hover); !strings.Contains(text, "Enum.join") {
		t.Fatalf("library hover: %v", hover)
	}
	hover = c.request("textDocument/hover", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 4, "character": 20}})
	if text := fmt.Sprint(hover); !strings.Contains(text, "def hello(name: string): string") || !strings.Contains(text, "Greets someone.") {
		t.Fatalf("imported hover: %v", hover)
	}
	definition := c.request("textDocument/definition", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 4, "character": 20}}).(map[string]any)
	if !strings.HasSuffix(definition["uri"].(string), "lib/greet.alc") || definition["range"].(map[string]any)["start"].(map[string]any)["line"] != float64(4) {
		t.Fatalf("definition: %v", definition)
	}
	// Completion after "Enum." lists Enum's functions.
	withDot := strings.Replace(fixed, "Enum.join", "Enum.", 1)
	c.notify("textDocument/didChange", map[string]any{"textDocument": map[string]any{"uri": uri, "version": 3}, "contentChanges": []any{map[string]any{"text": withDot}}})
	c.diagnostics(uri)
	items := c.request("textDocument/completion", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 5, "character": 17}}).([]any)
	labels := map[string]bool{}
	for _, item := range items {
		labels[item.(map[string]any)["label"].(string)] = true
	}
	if !labels["map"] || !labels["reduce"] || labels["Enum"] {
		t.Fatalf("completion after Enum.: %d items", len(items))
	}
	items = c.request("textDocument/completion", map[string]any{"textDocument": map[string]any{"uri": uri}, "position": map[string]any{"line": 4, "character": 18}}).([]any)
	labels = map[string]bool{}
	for _, item := range items {
		labels[item.(map[string]any)["label"].(string)] = true
	}
	if !labels["hello"] {
		t.Fatalf("completion after Greet.: %v", labels)
	}
	// Formatting replaces the document with its canonical form.
	messy := "defmodule Main do\n  def main() do\n    x = (1 + 2)\n    IO.puts(to_string(x))\n  end\nend\n"
	c.notify("textDocument/didChange", map[string]any{"textDocument": map[string]any{"uri": uri, "version": 4}, "contentChanges": []any{map[string]any{"text": messy}}})
	c.diagnostics(uri)
	edits := c.request("textDocument/formatting", map[string]any{"textDocument": map[string]any{"uri": uri}, "options": map[string]any{"tabSize": 2}}).([]any)
	if len(edits) != 1 || !strings.Contains(edits[0].(map[string]any)["newText"].(string), "x = 1 + 2") {
		t.Fatalf("formatting: %v", edits)
	}
	symbols := c.request("textDocument/documentSymbol", map[string]any{"textDocument": map[string]any{"uri": uri}}).([]any)
	if len(symbols) != 1 || symbols[0].(map[string]any)["name"] != "main" {
		t.Fatalf("symbols: %v", symbols)
	}
	if c.request("shutdown", nil) != nil {
		t.Fatal("shutdown result")
	}
	c.notify("exit", nil)
}
