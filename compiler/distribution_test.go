package compiler

import (
	"bufio"
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// Two programs, compiled separately from testdata/nodes, run as two nodes:
// the client finds a process the shop registered, sends it structs holding
// lists, maps, atoms and its own handle, gets sum-type answers back through
// that handle, reads from an endless stream the shop publishes, and is told
// when the shop's node goes away.
func TestTwoProgramsExchangeMessages(t *testing.T) {
	if testing.Short() {
		t.Skip("builds and runs two programs")
	}
	dir := t.TempDir()
	extension := ""
	if runtime.GOOS == "windows" {
		extension = ".exe"
	}
	shop, client := filepath.Join(dir, "shop"+extension), filepath.Join(dir, "client"+extension)
	if err := BuildTo(filepath.Join("testdata", "nodes", "shop.alc"), shop); err != nil {
		t.Fatal(err)
	}
	if err := BuildTo(filepath.Join("testdata", "nodes", "client.alc"), client); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	serving := exec.CommandContext(ctx, shop)
	output, err := serving.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := serving.Start(); err != nil {
		t.Fatal(err)
	}
	defer serving.Wait()
	// The shop prints the address it listens at, with the port it was given.
	address, err := bufio.NewReader(output).ReadString('\n')
	if err != nil || !strings.HasPrefix(address, "127.0.0.1:") {
		t.Fatalf("the shop did not report its address: %q %v", address, err)
	}
	got, err := exec.CommandContext(ctx, client, strings.TrimSpace(address)).CombinedOutput()
	want := "started client\nconnected to shop, nodes: [\"shop\"]\n[\"item 301\", \"item 302\"]\n{true, Answer.shipped(\"tea\", 6)}\n{true, Answer.refused(\"only 5 cup left\")}\ntrue true nodedown shop\n"
	if err != nil || strings.ReplaceAll(string(got), "\r\n", "\n") != want {
		t.Fatalf("err=%v\ngot:\n%s\nwant:\n%s", err, got, want)
	}
}

// Two nodes from testdata/cluster: the client calls functions the server
// serves, finds a process by a global name and cannot take the name again,
// links a process to one on the server and sees it end when that one fails,
// and gets its connection back after dropping it.
func TestClusterCallsLinksAndReconnects(t *testing.T) {
	if testing.Short() {
		t.Skip("builds and runs two programs")
	}
	dir := t.TempDir()
	extension := ""
	if runtime.GOOS == "windows" {
		extension = ".exe"
	}
	server, client := filepath.Join(dir, "server"+extension), filepath.Join(dir, "client"+extension)
	if err := BuildTo(filepath.Join("testdata", "cluster", "server.alc"), server); err != nil {
		t.Fatal(err)
	}
	if err := BuildTo(filepath.Join("testdata", "cluster", "client.alc"), client); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	serving := exec.CommandContext(ctx, server)
	output, err := serving.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	input, err := serving.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := serving.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() {
		input.Close()
		serving.Wait()
	}()
	lines := bufio.NewReader(output)
	registered, _ := lines.ReadString('\n')
	address, err := lines.ReadString('\n')
	if strings.TrimSpace(registered) != "true" || err != nil || !strings.HasPrefix(address, "127.0.0.1:") {
		t.Fatalf("the server did not start: %q %q %v", registered, address, err)
	}
	got, err := exec.CommandContext(ctx, client, strings.TrimSpace(address)).CombinedOutput()
	want := "ok(49)\nerror(\"division by zero\")\n\"worker found\"\nfalse\nok(true)\n{true, \"linked: victim crashed\"}\nfalse\ntrue\nok(9)\n"
	if err != nil || strings.ReplaceAll(string(got), "\r\n", "\n") != want {
		t.Fatalf("err=%v\ngot:\n%s\nwant:\n%s", err, got, want)
	}
}

func TestOnlyCopyableMessagesCross(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.alc")
	check := func(body string) string {
		if err := os.WriteFile(path, []byte("defmodule T do\n  def main() do\n"+body+"  end\nend\n"), 0600); err != nil {
			t.Fatal(err)
		}
		if err := Check(path); err != nil {
			return err.Error()
		}
		return ""
	}
	if message := check("    me: pid[tuple[string, list[option[integer]]]] = Process.self(1)\n    Process.register(me, :fine)\n"); message != "" {
		t.Fatalf("a copyable message type was refused: %s", message)
	}
	// A compiled pattern can be sent within the program but has no form on
	// the wire.
	patterns := check("    me: pid[list[regex]] = Process.self(1)\n    Process.register(me, :patterns)\n")
	if !strings.Contains(patterns, "messages of type list[regex]: regex cannot be sent to another node") {
		t.Fatalf("patterns as messages: %q", patterns)
	}
	untyped := check("    found = Node.whereis(\"other\", :orders)\n    IO.puts(inspect(found == found))\n")
	if !strings.Contains(untyped, "cannot infer the result type of Node.whereis here; annotate the binding") {
		t.Fatalf("a lookup without a type: %q", untyped)
	}
}

// Networking and encryption are linked only into programs that use nodes:
// a program that does not must not import the node package at all.
func TestNodePackageIsLinkedOnlyWhenUsed(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.alc")
	generated := func(body string) string {
		if err := os.WriteFile(path, []byte("defmodule T do\n  def main() do\n"+body+"  end\nend\n"), 0600); err != nil {
			t.Fatal(err)
		}
		program, err := loadProject(path)
		if err != nil {
			t.Fatal(err)
		}
		code := generateWithOptions(program, BuildOptions{})
		return code + selectLibrary(code)
	}
	plain := generated("    me: pid[string] = Process.self(1)\n    Process.send(me, \"x\", 1)\n    IO.puts(inspect(Enum.map([1], &(&1 + 1))))\n")
	if strings.Contains(plain, "actor/node") || strings.Contains(plain, "node.") {
		t.Fatal("a program without nodes imports the node package")
	}
	nodes := generated("    me: pid[string] = Process.self(1)\n    Process.register(me, :me)\n    IO.puts(Node.self())\n")
	if !strings.Contains(nodes, "\"alchem.local/actor/node\"") || !strings.Contains(nodes, "node.Codec[string]") {
		t.Fatal("a program with nodes lacks the node package")
	}
}
