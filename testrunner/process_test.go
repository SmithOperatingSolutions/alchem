package testrunner

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

func TestFixtureProcess(t *testing.T) {
	mode := os.Getenv("ALCHEM_TEST_PROCESS")
	if mode == "" {
		return
	}
	if mode == "timeout" {
		time.Sleep(10 * time.Second)
		os.Exit(0)
	}
	if mode == "streams" {
		os.Stdout.WriteString("hello\n")
		os.Stderr.WriteString("diagnostic\n")
		os.Exit(0)
	}
	os.Stdout.WriteString(strings.Repeat("x", 4096))
	os.Exit(0)
}

func TestExecuteSeparatesStreams(t *testing.T) {
	cmd := exec.Command(os.Args[0], "-test.run=^TestFixtureProcess$")
	cmd.Env = append(os.Environ(), "ALCHEM_TEST_PROCESS=streams")
	stdout, stderr, err := execute(context.Background(), cmd, time.Second*5)
	if err != nil || stdout != "hello\n" || stderr != "diagnostic\n" {
		t.Fatalf("stdout=%q stderr=%q err=%v", stdout, stderr, err)
	}
}

func TestExecuteTimeout(t *testing.T) {
	cmd := exec.Command(os.Args[0], "-test.run=^TestFixtureProcess$")
	cmd.Env = append(os.Environ(), "ALCHEM_TEST_PROCESS=timeout")
	_, _, err := execute(context.Background(), cmd, 100*time.Millisecond)
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("expected timeout, got %v", err)
	}
}

func TestExecuteBoundsOutput(t *testing.T) {
	cmd := exec.Command(os.Args[0], "-test.run=^TestFixtureProcess$")
	cmd.Env = append(os.Environ(), "ALCHEM_TEST_PROCESS=output")
	stdout, _, err := execute(context.Background(), cmd, time.Second*5)
	if err != nil || len(stdout) != 4096 {
		t.Fatalf("length=%d err=%v", len(stdout), err)
	}
	b := limitedBuffer{limit: 10}
	n, err := b.Write([]byte(strings.Repeat("x", 100)))
	if n != 100 || err != nil || b.String() != strings.Repeat("x", 10) || !b.exceeded {
		t.Fatalf("buffer=%+v n=%d err=%v", b, n, err)
	}
}
