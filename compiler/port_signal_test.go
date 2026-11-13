//go:build !windows

package compiler

import (
	"bufio"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
)

// A program ended by SIGTERM or SIGINT ends the programs its ports started
// before it goes, and still ends as that signal ends a program.
func TestPortProgramsEndWithTheProgram(t *testing.T) {
	if testing.Short() {
		t.Skip("builds and runs a program")
	}
	dir := t.TempDir()
	source := filepath.Join(dir, "main.alc")
	if err := os.WriteFile(source, []byte(`defmodule Outlive do
  def main() do
    me: pid[PortEvent] = Process.self(16)
    ok(port) = Port.open("sleep", ["60"], me)
    IO.puts(Integer.to_string(Port.os_pid(port)))
    Process.sleep(60000)
  end
end
`), 0600); err != nil {
		t.Fatal(err)
	}
	binary := filepath.Join(dir, "outlive")
	if err := BuildTo(source, binary); err != nil {
		t.Fatal(err)
	}
	for _, signal := range []syscall.Signal{syscall.SIGTERM, syscall.SIGINT} {
		program := exec.Command(binary)
		output, err := program.StdoutPipe()
		if err != nil {
			t.Fatal(err)
		}
		if err := program.Start(); err != nil {
			t.Fatal(err)
		}
		line, err := bufio.NewReader(output).ReadString('\n')
		child, convErr := strconv.Atoi(strings.TrimSpace(line))
		if err != nil || convErr != nil {
			program.Process.Kill()
			t.Fatalf("the program did not report its port: %q %v", line, err)
		}
		program.Process.Signal(signal)
		err = program.Wait()
		status, ok := err.(*exec.ExitError)
		if !ok || !status.Sys().(syscall.WaitStatus).Signaled() || status.Sys().(syscall.WaitStatus).Signal() != signal {
			t.Errorf("%v: the program ended with %v, not by the signal", signal, err)
		}
		gone := false
		for deadline := time.Now().Add(3 * time.Second); time.Now().Before(deadline); time.Sleep(50 * time.Millisecond) {
			if syscall.Kill(child, 0) != nil {
				gone = true
				break
			}
		}
		if !gone {
			syscall.Kill(child, syscall.SIGKILL)
			t.Errorf("%v: the port's program (pid %d) outlived the program", signal, child)
		}
	}
}
