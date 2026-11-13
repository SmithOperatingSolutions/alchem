package compiler

import (
	"strings"
	"testing"
)

// Go may keep an Alchem function or interface implementation and call it
// later, from goroutines of its own: during an extern call one call at a
// time runs in the lending process, and every other call runs in a process
// of its own. A failure becomes the Go error result.
func TestExternCallsFromGoLater(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"main.alc": `defmodule App do
  struct Greeter do
    greet: fn[string, result[string, string]]
  end

  extern keep(g: Greeter) = "./native.Keep"
  extern greet_all(names: list[string]): list[string] = "./native.GreetAll"
  extern keep_square(f: fn[integer, integer]) = "./native.KeepSquare"
  extern squares(n: integer): integer = "./native.Squares"
  extern at_once(f: fn[integer, integer], n: integer): integer = "./native.AtOnce"

  def greeting(name: string): result[string, string] do
    if name == "bad" do
      raise("no greeting for bad")
    end
    ok("hello " <> name)
  end

  def main() do
    keep(%Greeter{greet: fn name -> greeting(name) end})
    names = Enum.map(Enum.to_list(1..50), fn i -> "n" <> Integer.to_string(i) end)
    greeted = greet_all(names ++ ["bad"])
    assert(Enum.take(greeted, 2) == ["hello n1", "hello n2"])
    assert(List.last(greeted) == some("error: alchem: no greeting for bad"))
    keep_square(fn n -> n * n end)
    assert(squares(100) == 338350)
    total = at_once(fn n -> n + 1 end, 64)
    assert(total == 2080)
    # The process that kept the greeter ends: calls into it fail softly.
    me: pid[boolean] = Process.self(1)
    _keeper: pid[integer] = Process.spawn(fn(_self: pid[integer]): integer do
      keep(%Greeter{greet: fn name -> ok(name) end})
      Process.send(me, true, 100)
      0
    end, 1)
    assert(Process.receive(me, 1000) == {true, true})
    Process.sleep(50)
    assert(greet_all(["x"]) == ["error: alchem: the Alchem process that made this function has ended"])
    IO.puts("later")
  end
end
`,
		"native/native.go": `package native

import (
	"sync"
)

type Greeter interface{ Greet(name string) (string, error) }

var kept Greeter

func Keep(g Greeter) { kept = g }

// GreetAll greets each name from a goroutine of its own.
func GreetAll(names []string) []string {
	out := make([]string, len(names))
	var wg sync.WaitGroup
	for i, name := range names {
		wg.Add(1)
		go func() {
			defer wg.Done()
			greeting, err := kept.Greet(name)
			if err != nil {
				greeting = "error: " + err.Error()
			}
			out[i] = greeting
		}()
	}
	wg.Wait()
	return out
}

var square func(int64) int64

func KeepSquare(f func(int64) int64) { square = f }

func Squares(n int64) int64 {
	var mu sync.Mutex
	var total int64
	var wg sync.WaitGroup
	for i := int64(1); i <= n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			s := square(i)
			mu.Lock()
			total += s
			mu.Unlock()
		}()
	}
	wg.Wait()
	return total
}

// AtOnce calls f from n goroutines while the caller waits.
func AtOnce(f func(int64) int64, n int64) int64 {
	var mu sync.Mutex
	var total int64
	var wg sync.WaitGroup
	for i := int64(0); i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			v := f(i)
			mu.Lock()
			total += v
			mu.Unlock()
		}()
	}
	wg.Wait()
	return total
}
`,
	})
	if err != nil || !strings.HasSuffix(output, "later\n") {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

// An Alchem http.Handler served by Go's own net/http: each request arrives
// on a goroutine of the Go server, long after the call that handed the
// handler over has returned.
func TestExternHTTPHandlerServedByGo(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"main.alc": `defmodule App do
  extern type Writer = "net/http.ResponseWriter"
  extern type Request = "*net/http.Request"
  extern type TestServer = "*net/http/httptest.Server"

  struct Handler do
    serve_http: fn[Writer, Request, tuple[]]
  end

  extern start(h: Handler): TestServer = "net/http/httptest.NewServer"
  extern close(s: TestServer) = "./native.Close"
  extern url(s: TestServer): string = "./native.URL"
  extern path(r: Request): string = "./native.Path"
  extern reply(w: Writer, text: string): result[integer, string] = "io.WriteString"
  extern fetch_all(base: string, paths: list[string]): list[string] = "./native.FetchAll"

  def handle(w: Writer, r: Request): tuple[] do
    reply(w, "you asked for " <> path(r))
    {}
  end

  def main() do
    server = start(%Handler{serve_http: fn w, r -> handle(w, r) end})
    paths = Enum.map(Enum.to_list(1..40), fn i -> "/p" <> Integer.to_string(i) end)
    bodies = fetch_all(url(server), paths)
    assert(length(bodies) == 40)
    assert(List.first(bodies) == some("you asked for /p1"))
    assert(List.last(bodies) == some("you asked for /p40"))
    close(server)
    IO.puts("served")
  end
end
`,
		"native/native.go": `package native

import (
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
)

func Close(s *httptest.Server) { s.Close() }
func URL(s *httptest.Server) string { return s.URL }
func Path(r *http.Request) string { return r.URL.Path }

// FetchAll gets every path at once and returns the bodies in order.
func FetchAll(base string, paths []string) []string {
	out := make([]string, len(paths))
	var wg sync.WaitGroup
	for i, p := range paths {
		wg.Add(1)
		go func() {
			defer wg.Done()
			response, err := http.Get(base + p)
			if err != nil {
				out[i] = err.Error()
				return
			}
			defer response.Body.Close()
			body, _ := io.ReadAll(response.Body)
			out[i] = string(body)
		}()
	}
	wg.Wait()
	return out
}
`,
	})
	if err != nil || output != "served\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}
