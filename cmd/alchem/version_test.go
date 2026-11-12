package main

import (
	"bytes"
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

func TestVersionCommand(t *testing.T) {
	saved := version
	t.Cleanup(func() { version = saved })

	version = ""
	if got := compilerVersion(); got != "devel" {
		t.Fatalf("unstamped build: %q", got)
	}
	version = "v1.2.3"
	for _, args := range [][]string{{"version"}, {"--version"}} {
		var out, errOut bytes.Buffer
		if code := run(context.Background(), args, &out, &errOut); code != 0 || !strings.HasPrefix(out.String(), "alchem v1.2.3 ") || !strings.Contains(out.String(), "\ngo: ") {
			t.Fatalf("%v: code=%d out=%q err=%q", args, code, out.String(), errOut.String())
		}
	}

	var out, errOut bytes.Buffer
	if code := run(context.Background(), []string{"version", "--json"}, &out, &errOut); code != 0 {
		t.Fatalf("json: %d %s", code, errOut.String())
	}
	var report struct {
		Version string `json:"version"`
		Release string `json:"go_release"`
	}
	if err := json.Unmarshal(out.Bytes(), &report); err != nil || report.Version != "v1.2.3" || report.Release != compiler.GoRelease {
		t.Fatalf("json: %+v %v", report, err)
	}

	if code := run(context.Background(), []string{"version", "extra"}, &out, &errOut); code != 1 {
		t.Fatalf("extra argument: %d", code)
	}

	t.Setenv("PATH", t.TempDir())
	t.Setenv("ALCHEM_GO", "")
	t.Setenv("ALCHEM_CACHE", t.TempDir())
	t.Setenv("ALCHEM_GO_DOWNLOAD", "")
	if text := versionText(false); !strings.Contains(text, "the first build downloads "+compiler.GoRelease) {
		t.Fatalf("no go: %q", text)
	}
	t.Setenv("ALCHEM_GO_DOWNLOAD", "off")
	if text := versionText(false); !strings.Contains(text, "turns downloading off") {
		t.Fatalf("downloads off: %q", text)
	}
}
