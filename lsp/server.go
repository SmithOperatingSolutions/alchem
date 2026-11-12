// Package lsp is a language server for Alchem: it speaks the Language Server
// Protocol over a reader and a writer, as alchem lsp does over standard input
// and output.
package lsp

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"unicode"

	"github.com/SmithOperatingSolutions/alchem/compiler"
	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
	"github.com/SmithOperatingSolutions/alchem/guide"
)

type message struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method,omitempty"`
	Params  json.RawMessage `json:"params,omitempty"`
	Result  any             `json:"result,omitempty"`
	Error   *responseError  `json:"error,omitempty"`
}

type responseError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type position struct {
	Line      int `json:"line"`
	Character int `json:"character"`
}

type span struct {
	Start position `json:"start"`
	End   position `json:"end"`
}

type location struct {
	URI   string `json:"uri"`
	Range span   `json:"range"`
}

type document struct {
	TextDocument struct {
		URI  string `json:"uri"`
		Text string `json:"text"`
	} `json:"textDocument"`
	ContentChanges []struct {
		Text string `json:"text"`
	} `json:"contentChanges"`
	Position position `json:"position"`
}

// server holds the open documents, by URI.
type server struct {
	mu        sync.Mutex
	out       io.Writer
	writeLock sync.Mutex
	documents map[string]string
	shutdown  bool
}

// Serve answers requests read from in until the client exits, writing to out.
func Serve(ctx context.Context, in io.Reader, out io.Writer) error {
	s := &server{out: out, documents: map[string]string{}}
	reader := bufio.NewReader(in)
	for {
		body, err := read(reader)
		if err != nil {
			if err == io.EOF {
				return nil
			}
			return err
		}
		var m message
		if err := json.Unmarshal(body, &m); err != nil {
			continue
		}
		if m.Method == "exit" {
			return nil
		}
		s.handle(ctx, m)
	}
}

// read takes one message framed by a Content-Length header.
func read(r *bufio.Reader) ([]byte, error) {
	length := -1
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			return nil, err
		}
		line = strings.TrimRight(line, "\r\n")
		if line == "" {
			break
		}
		if name, value, ok := strings.Cut(line, ":"); ok && strings.EqualFold(name, "Content-Length") {
			length, _ = strconv.Atoi(strings.TrimSpace(value))
		}
	}
	if length < 0 {
		return nil, fmt.Errorf("message without Content-Length")
	}
	body := make([]byte, length)
	_, err := io.ReadFull(r, body)
	return body, err
}

func (s *server) send(m message) {
	m.JSONRPC = "2.0"
	data, _ := json.Marshal(m)
	s.writeLock.Lock()
	defer s.writeLock.Unlock()
	fmt.Fprintf(s.out, "Content-Length: %d\r\n\r\n%s", len(data), data)
}

func (s *server) reply(id json.RawMessage, result any) {
	if result == nil {
		// A request answered with nothing still needs "result": null.
		data, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": id, "result": nil})
		s.writeLock.Lock()
		defer s.writeLock.Unlock()
		fmt.Fprintf(s.out, "Content-Length: %d\r\n\r\n%s", len(data), data)
		return
	}
	s.send(message{ID: id, Result: result})
}

func (s *server) handle(ctx context.Context, m message) {
	var d document
	json.Unmarshal(m.Params, &d)
	uri := d.TextDocument.URI
	switch m.Method {
	case "initialize":
		s.reply(m.ID, map[string]any{
			"capabilities": map[string]any{
				"textDocumentSync":           map[string]any{"openClose": true, "change": 1, "save": map[string]any{"includeText": true}},
				"hoverProvider":              true,
				"definitionProvider":         true,
				"documentFormattingProvider": true,
				"documentSymbolProvider":     true,
				"completionProvider":         map[string]any{"triggerCharacters": []string{"."}},
			},
			"serverInfo": map[string]any{"name": "alchem"},
		})
	case "shutdown":
		s.shutdown = true
		s.reply(m.ID, nil)
	case "textDocument/didOpen":
		s.update(ctx, uri, d.TextDocument.Text)
	case "textDocument/didChange":
		if n := len(d.ContentChanges); n > 0 {
			s.update(ctx, uri, d.ContentChanges[n-1].Text)
		}
	case "textDocument/didSave":
		if d.TextDocument.Text != "" {
			s.update(ctx, uri, d.TextDocument.Text)
		} else {
			s.update(ctx, uri, s.text(uri))
		}
	case "textDocument/didClose":
		s.mu.Lock()
		delete(s.documents, uri)
		s.mu.Unlock()
		compiler.ClearOverlay(pathOf(uri))
		s.send(message{Method: "textDocument/publishDiagnostics", Params: mustJSON(map[string]any{"uri": uri, "diagnostics": []any{}})})
	case "textDocument/hover":
		s.reply(m.ID, s.hover(uri, d.Position))
	case "textDocument/definition":
		s.reply(m.ID, s.definition(uri, d.Position))
	case "textDocument/completion":
		s.reply(m.ID, s.complete(uri, d.Position))
	case "textDocument/formatting":
		s.reply(m.ID, s.format(uri))
	case "textDocument/documentSymbol":
		s.reply(m.ID, s.symbols(uri))
	default:
		if len(m.ID) > 0 {
			s.send(message{ID: m.ID, Error: &responseError{Code: -32601, Message: "method not found: " + m.Method}})
		}
	}
}

func mustJSON(v any) json.RawMessage {
	data, _ := json.Marshal(v)
	return data
}

func (s *server) text(uri string) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.documents[uri]
}

// pathOf turns a file URI into a path.
func pathOf(uri string) string {
	parsed, err := url.Parse(uri)
	if err != nil || parsed.Scheme != "file" {
		return uri
	}
	path := parsed.Path
	if runtime.GOOS == "windows" {
		path = strings.TrimPrefix(path, "/")
	}
	return filepath.FromSlash(path)
}

func uriOf(path string) string {
	path = filepath.ToSlash(path)
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}
	return (&url.URL{Scheme: "file", Path: path}).String()
}

// update records a document's text and publishes its diagnostics.
func (s *server) update(ctx context.Context, uri, text string) {
	s.mu.Lock()
	s.documents[uri] = text
	s.mu.Unlock()
	path := pathOf(uri)
	compiler.SetOverlay(path, []byte(text))
	diagnostics := []any{}
	if err := compiler.CheckContext(ctx, path); err != nil {
		d := compiler.Describe(err)
		line, column, problem := 1, 1, err.Error()
		if d != nil {
			problem = d.Message
			if d.File == "" || sameFile(d.File, path) {
				line, column = d.Line, d.Column
			} else {
				problem = filepath.Base(d.File) + ":" + strconv.Itoa(d.Line) + ":" + strconv.Itoa(d.Column) + ": " + d.Message
			}
		}
		start := position{max(line-1, 0), max(column-1, 0)}
		end := position{start.Line, start.Character + wordLength(lineOf(text, start.Line), start.Character)}
		diagnostics = append(diagnostics, map[string]any{"range": span{start, end}, "severity": 1, "source": "alchem", "message": problem})
	}
	s.send(message{Method: "textDocument/publishDiagnostics", Params: mustJSON(map[string]any{"uri": uri, "diagnostics": diagnostics})})
}

func sameFile(a, b string) bool {
	x, _ := filepath.Abs(a)
	y, _ := filepath.Abs(b)
	return x == y
}

func lineOf(text string, n int) string {
	lines := strings.Split(text, "\n")
	if n < 0 || n >= len(lines) {
		return ""
	}
	return strings.TrimRight(lines[n], "\r")
}

// wordLength is the length of the name starting at a column, at least 1.
func wordLength(line string, column int) int {
	runes := []rune(line)
	n := 0
	for i := column; i < len(runes) && (isNameRune(runes[i]) || runes[i] == '.'); i++ {
		n++
	}
	return max(n, 1)
}

func isNameRune(r rune) bool {
	return unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_' || r == '?' || r == '!'
}

// nameAt is the possibly qualified name under a position, such as
// Enum.map, and the part of it before the position.
func nameAt(text string, at position) (string, string) {
	runes := []rune(lineOf(text, at.Line))
	column := min(at.Character, len(runes))
	start := column
	for start > 0 && (isNameRune(runes[start-1]) || runes[start-1] == '.') {
		start--
	}
	end := column
	for end < len(runes) && isNameRune(runes[end]) {
		end++
	}
	return string(runes[start:end]), string(runes[start:column])
}

// project is a document and the modules it imports, parsed as written.
type project struct {
	path    string
	program ast.Program
	// imported maps a module name to its file and parsed program.
	imported map[string]importedModule
}

type importedModule struct {
	path    string
	program ast.Program
}

func (s *server) load(uri string) (project, bool) {
	path := pathOf(uri)
	program, err := syntax.ParseSyntax(s.text(uri))
	if err != nil {
		return project{}, false
	}
	p := project{path: path, program: program, imported: map[string]importedModule{}}
	for _, target := range program.Imports {
		if strings.Contains(target, "@") {
			continue
		}
		file := filepath.Join(filepath.Dir(path), filepath.FromSlash(target))
		data, err := compiler.ReadSource(file)
		if err != nil {
			continue
		}
		if other, err := syntax.ParseSyntax(string(data)); err == nil {
			p.imported[other.Module] = importedModule{file, other}
		}
	}
	return p, true
}

// find returns the declaration of a function by its name as written, local
// or Module.function.
func (p project) find(name string) (*ast.Function, string) {
	module, local := "", name
	if i := strings.LastIndex(name, "."); i >= 0 {
		module, local = name[:i], name[i+1:]
	}
	search := func(program ast.Program, path string) (*ast.Function, string) {
		for i := range program.Functions {
			if f := &program.Functions[i]; f.Name == local && f.Test == "" && !f.Setup {
				return f, path
			}
		}
		return nil, ""
	}
	if module == "" || module == p.program.Module {
		return search(p.program, p.path)
	}
	if other, ok := p.imported[module]; ok {
		return search(other.program, other.path)
	}
	return nil, ""
}

func signature(f *ast.Function) string {
	params := []string{}
	for _, param := range f.Params {
		text := param.Name
		if param.Type != "" {
			text += ": " + param.Type
		}
		params = append(params, text)
	}
	keyword := "def"
	if f.Private {
		keyword = "defp"
	}
	text := keyword + " " + f.Name + "(" + strings.Join(params, ", ") + ")"
	if f.Type != "" && f.Type != "void" {
		text += ": " + f.Type
	}
	return text
}

func (s *server) hover(uri string, at position) any {
	name, _ := nameAt(s.text(uri), at)
	if name == "" {
		return nil
	}
	markdown := ""
	if p, ok := s.load(uri); ok {
		if f, _ := p.find(name); f != nil {
			markdown = "```elixir\n" + signature(f) + "\n```"
			if f.Doc != "" {
				markdown += "\n\n" + strings.TrimSpace(f.Doc)
			}
		}
	}
	if markdown == "" {
		if text, err := guide.Doc(name, false, false); err == nil && strings.TrimSpace(text) != "" {
			markdown = "```\n" + strings.TrimSpace(text) + "\n```"
		}
	}
	if markdown == "" {
		return nil
	}
	return map[string]any{"contents": map[string]any{"kind": "markdown", "value": markdown}}
}

func (s *server) definition(uri string, at position) any {
	name, _ := nameAt(s.text(uri), at)
	p, ok := s.load(uri)
	if name == "" || !ok {
		return nil
	}
	f, path := p.find(name)
	if f == nil {
		return nil
	}
	start := position{max(f.Line-1, 0), max(f.Column-1, 0)}
	return location{URI: uriOf(path), Range: span{start, start}}
}

// complete offers the functions of a module after "Module.", and otherwise
// the document's functions, the modules and the keywords.
func (s *server) complete(uri string, at position) any {
	_, before := nameAt(s.text(uri), at)
	items := []map[string]any{}
	seen := map[string]bool{}
	add := func(label string, kind int, detail string) {
		if seen[label] {
			return
		}
		seen[label] = true
		items = append(items, map[string]any{"label": label, "kind": kind, "detail": detail})
	}
	p, loaded := s.load(uri)
	if i := strings.LastIndex(before, "."); i >= 0 {
		module := before[:i]
		names := []string{}
		for key := range syntax.Libraries {
			name := key[:strings.LastIndex(key, "/")]
			if strings.HasPrefix(name, module+".") && !strings.Contains(name[len(module)+1:], ".") {
				names = append(names, name)
			}
		}
		for name := range syntax.Docs {
			if strings.HasPrefix(name, module+".") && !strings.Contains(name[len(module)+1:], ".") {
				names = append(names, name)
			}
		}
		sort.Strings(names)
		for _, name := range names {
			summary := ""
			if doc, ok := syntax.Docs[name]; ok {
				summary = doc.Summary
			}
			add(name[len(module)+1:], 3, summary)
		}
		if loaded {
			if other, ok := p.imported[module]; ok {
				for i := range other.program.Functions {
					if f := &other.program.Functions[i]; !f.Private && f.Test == "" && !f.Setup {
						add(f.Name, 3, signature(f))
					}
				}
			}
		}
		return items
	}
	if loaded {
		for i := range p.program.Functions {
			if f := &p.program.Functions[i]; f.Test == "" && !f.Setup && f.Name != "main" {
				add(f.Name, 3, signature(f))
			}
		}
		for module := range p.imported {
			add(module, 9, "imported module")
		}
	}
	for _, module := range syntax.Modules {
		add(module.Name, 9, module.Summary)
	}
	for _, keyword := range []string{"def", "defp", "defmodule", "defexception", "struct", "type", "case", "cond", "if", "else", "unless", "with", "for", "try", "rescue", "catch", "after", "fn", "end", "do", "import", "raise", "throw", "test", "describe", "assert", "refute"} {
		add(keyword, 14, "")
	}
	return items
}

func (s *server) format(uri string) any {
	text := s.text(uri)
	formatted, err := compiler.Format(text)
	if err != nil || formatted == text {
		return []any{}
	}
	lines := strings.Count(text, "\n") + 1
	return []any{map[string]any{"range": span{position{0, 0}, position{lines, 0}}, "newText": formatted}}
}

func (s *server) symbols(uri string) any {
	p, ok := s.load(uri)
	if !ok {
		return []any{}
	}
	out := []any{}
	symbol := func(name string, kind, line, column int, detail string) {
		at := position{max(line-1, 0), max(column-1, 0)}
		out = append(out, map[string]any{"name": name, "kind": kind, "detail": detail, "range": span{at, at}, "selectionRange": span{at, at}})
	}
	for _, decl := range p.program.Types {
		kind := 23 // struct
		if decl.Kind == "sum" {
			kind = 10 // enum
		}
		symbol(decl.Local, kind, decl.Line, decl.Column, decl.Kind)
	}
	for i := range p.program.Functions {
		f := &p.program.Functions[i]
		switch {
		case f.Test != "":
			symbol("test "+strconv.Quote(f.Test), 12, f.Line, f.Column, f.Group)
		case f.Setup:
		default:
			symbol(f.Name, 12, f.Line, f.Column, signature(f))
		}
	}
	return out
}

// Main runs the server over standard input and output.
func Main(ctx context.Context) int {
	if err := Serve(ctx, os.Stdin, os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}
