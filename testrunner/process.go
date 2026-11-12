package testrunner

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"time"
)

// Keep a noisy fixture from exhausting the runner's memory. Excess bytes are
// discarded while pipes continue draining so the process cannot block on them.
type limitedBuffer struct {
	bytes.Buffer
	limit    int
	exceeded bool
}

func (b *limitedBuffer) Write(p []byte) (int, error) {
	n := len(p)
	remaining := b.limit - b.Len()
	if n > remaining {
		b.exceeded = true
		p = p[:remaining]
	}
	_, _ = b.Buffer.Write(p)
	return n, nil
}

func execute(parent context.Context, cmd *exec.Cmd, timeout time.Duration) (string, string, error) {
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()
	// Preserve caller-selected arguments, environment and working directory.
	bounded := exec.CommandContext(ctx, cmd.Path, cmd.Args[1:]...)
	bounded.Env, bounded.Dir = cmd.Env, cmd.Dir
	bounded.WaitDelay = time.Second
	stdout := &limitedBuffer{limit: 1 << 20}
	stderr := &limitedBuffer{limit: 1 << 20}
	bounded.Stdout, bounded.Stderr = stdout, stderr
	err := bounded.Run()
	if ctx.Err() != nil {
		err = fmt.Errorf("fixture execution: %w", ctx.Err())
	} else if stdout.exceeded || stderr.exceeded {
		err = fmt.Errorf("fixture output exceeds 1 MiB per stream")
	}
	return stdout.String(), stderr.String(), err
}
