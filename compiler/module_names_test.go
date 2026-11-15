package compiler

import (
	"testing"
)

// A module may name its functions put, get, length, map and the like, as a
// library module does. Inside that module a bare call reaches its own
// function, and the builtin is written Map.put; elsewhere the bare name is
// the builtin as before. A module may also take the name of a builtin module
// that is being moved to a package, and is then the one calls reach.
func TestModulesMayUseBuiltinNames(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"main.alc": `defmodule Main do
  import "disk_store.alc"

  def main() do
    box = DiskStore.put(%DiskStore.Held{items: %{}}, "k", "v") |> DiskStore.twice("x") |> DiskStore.map(&String.upcase/1)
    IO.puts(DiskStore.get(box, "k") <> DiskStore.get(box, "x2") <> Integer.to_string(DiskStore.length(box)))
    held: map[string, integer] = put(%{}, "a", 1)
    IO.puts(Integer.to_string(get(held, "a", 0) + length([1, 2])))
    puts = &DiskStore.put/3
    IO.puts(DiskStore.get(puts(box, "z", "ref"), "z"))
    IO.puts(DiskStore.shout("native"))
  end
end
`,
		"disk_store.alc": `defmodule DiskStore do
  struct Held do
    items: map[string, string]
  end

  extern concat(text: string, count: integer): string = "strings.Repeat"

  def put(box: Held, key: string, value: string): Held do
    %Held{items: Map.put(box.items, key, value)}
  end

  def get(box: Held, key: string): string do
    Map.get(box.items, key, "none")
  end

  def length(box: Held): integer do
    map_size(box.items)
  end

  def map(box: Held, change: fn[string, string]): Held do
    %Held{items: Map.new(Enum.map(Map.to_list(box.items), fn {key, value} -> {key, change(value)} end))}
  end

  def twice(box: Held, key: string): Held do
    put(put(box, key, "a"), key <> "2", "b")
  end

  def shout(text: string): string do
    concat(text, 2)
  end
end
`})
	if err != nil || output != "VB3\n3\nref\nnativenative\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
	// Without a module of that name, the builtin is used as before.
	output, err = buildAndRun(t, map[string]string{"main.alc": `defmodule Main do
  def main() do
    path = Path.join(System.tmp_dir!(), "alchem_names_" <> Base.encode16(Crypto.strong_rand_bytes(6)))
    ok(store) = DiskStore.open(path)
    assert(DiskStore.put(store, "k", "v") == ok({}))
    assert(DiskStore.get(store, "k") == some("v"))
    DiskStore.close(store)
    File.rm(path)
    IO.puts("builtin")
  end
end
`})
	if err != nil || output != "builtin\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

// A package that takes over a library module declares the module's types
// itself: they take the place of the builtin ones, under the names the
// library gave them, and the library's own are still there for a program
// that has no such module.
func TestPackagesReplaceLibraryTypes(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"main.alc": `defmodule Main do
  import "version.alc"
  import "websocket.alc"

  def label(v: Version): string do
    Version.to_string(v) <> " " <> Version.to_string("text")
  end

  def main() do
    v = %Version{major: 1, minor: 2, patch: 3, note: "own"}
    IO.puts(label(v) <> " " <> v.note)
    req: Version.Requirement = Version.requirement(">= 1.0.0")
    IO.puts(req.source)
    event: WebSocket.Event = WebSocket.next("hi")
    case event do
      WebSocket.Event.text(text) -> IO.puts("text " <> text)
      WebSocket.Event.gone -> IO.puts("gone")
    end
    IO.inspect(WebSocket.next(""))
  end
end
`,
		"version.alc": `defmodule Version do
  struct Version do
    major: integer
    minor: integer
    patch: integer
    note: string
  end

  struct Requirement do
    source: string
  end

  def to_string(v: Version): string do
    Integer.to_string(v.major) <> "." <> Integer.to_string(v.minor) <> "." <> Integer.to_string(v.patch)
  end

  def to_string(text: string): string do
    "(" <> text <> ")"
  end

  def requirement(text: string): Requirement do
    %Requirement{source: text}
  end
end
`,
		"websocket.alc": `defmodule WebSocket do
  type Event do
    text(text: string)
    gone
  end

  def next(""): Event do
    Event.gone
  end

  def next(text: string): Event do
    Event.text(text)
  end
end
`})
	if err != nil || output != "1.2.3 (text) own\n>= 1.0.0\ntext hi\nEvent.gone\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
	output, err = buildAndRun(t, map[string]string{"main.alc": `defmodule Main do
  def main() do
    v = Version.parse!("1.2.3-rc.1")
    IO.inspect({v.major, v.pre, Version.match?(v, "~> 1.2")})
    {options, _, _} = OptionParser.parse(["--n", "3"], %{"n" => "integer"})
    IO.inspect(options)
  end
end
`})
	if err != nil || output != "{1, [\"rc\", \"1\"], true}\n%{\"n\" => \"3\"}\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}
