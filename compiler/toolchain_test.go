package compiler

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// fakeGoArchive builds a release archive for this platform holding
// go/bin/go and any extra entries.
func fakeGoArchive(t *testing.T, extra ...string) []byte {
	t.Helper()
	entries := append([]string{"go/bin/go" + exeSuffix()}, extra...)
	var buf bytes.Buffer
	if runtime.GOOS == "windows" {
		w := zip.NewWriter(&buf)
		w.Create("go/")
		for _, name := range entries {
			f, _ := w.Create(name)
			f.Write([]byte("fake"))
		}
		w.Close()
		return buf.Bytes()
	}
	gz := gzip.NewWriter(&buf)
	w := tar.NewWriter(gz)
	w.WriteHeader(&tar.Header{Name: "go/", Typeflag: tar.TypeDir, Mode: 0o755})
	for _, name := range entries {
		w.WriteHeader(&tar.Header{Name: name, Typeflag: tar.TypeReg, Mode: 0o755, Size: 4})
		w.Write([]byte("fake"))
	}
	w.Close()
	gz.Close()
	return buf.Bytes()
}

// withoutGo hides any installed go command and points downloads at a
// server returning archive, recorded in goArchives with hash sum.
func withoutGo(t *testing.T, archive []byte, sum string) (cache string, requests *int) {
	t.Helper()
	count := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count++
		if r.URL.Path != ("/dl/" + GoRelease + "." + runtime.GOOS + "-" + runtime.GOARCH + map[bool]string{true: ".zip", false: ".tar.gz"}[runtime.GOOS == "windows"]) {
			http.NotFound(w, r)
			return
		}
		w.Write(archive)
	}))
	t.Cleanup(server.Close)
	cache = t.TempDir()
	t.Setenv("PATH", t.TempDir())
	t.Setenv("ALCHEM_GO", "")
	t.Setenv("ALCHEM_GO_DOWNLOAD", "")
	t.Setenv("ALCHEM_CACHE", cache)
	t.Setenv("ALCHEM_GO_MIRROR", server.URL+"/dl/")
	platform := runtime.GOOS + "/" + runtime.GOARCH
	saved, had := goArchives[platform]
	goArchives[platform] = sum
	t.Cleanup(func() {
		if had {
			goArchives[platform] = saved
		} else {
			delete(goArchives, platform)
		}
	})
	savedLog := ToolchainLog
	ToolchainLog = io.Discard
	t.Cleanup(func() { ToolchainLog = savedLog })
	return cache, &count
}

func hashOf(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func TestGoIsDownloadedOnceWhenMissing(t *testing.T) {
	archive := fakeGoArchive(t, "go/src/runtime/extern.go")
	cache, requests := withoutGo(t, archive, hashOf(archive))
	if found := LocateGo(); found.Source != "download" || found.Path != "" {
		t.Fatalf("before download: %+v", found)
	}
	path, err := goCommand(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	want := filepath.Join(cache, "toolchains", GoRelease, "go", "bin", "go"+exeSuffix())
	if path != want {
		t.Fatalf("path %s, want %s", path, want)
	}
	if !fileExists(filepath.Join(cache, "toolchains", GoRelease, "go", "src", "runtime", "extern.go")) {
		t.Fatal("the rest of the archive was not unpacked")
	}
	if found := LocateGo(); found.Source != "downloaded" || found.Path != want {
		t.Fatalf("after download: %+v", found)
	}
	if _, err := goCommand(context.Background()); err != nil || *requests != 1 {
		t.Fatalf("second use: err=%v requests=%d", err, *requests)
	}
}

func TestGoDownloadRejectsABadChecksum(t *testing.T) {
	archive := fakeGoArchive(t)
	cache, _ := withoutGo(t, archive, strings.Repeat("0", 64))
	_, err := goCommand(context.Background())
	if err == nil || !strings.Contains(err.Error(), "checksum mismatch") {
		t.Fatalf("got %v", err)
	}
	if fileExists(filepath.Join(cache, "toolchains", GoRelease)) {
		t.Fatal("a rejected download was installed")
	}
}

func TestGoDownloadRejectsEntriesOutsideTheArchive(t *testing.T) {
	archive := fakeGoArchive(t, "../escape")
	withoutGo(t, archive, hashOf(archive))
	if _, err := goCommand(context.Background()); err == nil || !strings.Contains(err.Error(), "outside the archive") {
		t.Fatalf("got %v", err)
	}
}

func TestGoDownloadFailures(t *testing.T) {
	archive := fakeGoArchive(t)
	withoutGo(t, archive, hashOf(archive))
	t.Setenv("ALCHEM_GO_MIRROR", os.Getenv("ALCHEM_GO_MIRROR")+"missing/")
	if _, err := goCommand(context.Background()); err == nil || !strings.Contains(err.Error(), "404") {
		t.Fatalf("missing archive: %v", err)
	}

	t.Setenv("ALCHEM_GO_DOWNLOAD", "off")
	if found := LocateGo(); found.Source != "missing" {
		t.Fatalf("downloads off: %+v", found)
	}
	if _, err := goCommand(context.Background()); err == nil || !strings.Contains(err.Error(), "install Go 1.27") {
		t.Fatalf("downloads off: %v", err)
	}

	t.Setenv("ALCHEM_GO", "/custom/go")
	if found := LocateGo(); found != (Toolchain{Path: "/custom/go", Source: "ALCHEM_GO"}) {
		t.Fatalf("explicit: %+v", found)
	}
}

func TestGoDownloadNeedsAKnownPlatformAndAGoBinary(t *testing.T) {
	empty := fakeGoArchive(t)
	withoutGo(t, empty, hashOf(empty))
	delete(goArchives, runtime.GOOS+"/"+runtime.GOARCH)
	if _, err := goCommand(context.Background()); err == nil || !strings.Contains(err.Error(), "no Go download for") {
		t.Fatalf("unknown platform: %v", err)
	}
}

func TestBuildWithoutGoExplainsWhatToDo(t *testing.T) {
	withoutGo(t, nil, "")
	t.Setenv("ALCHEM_GO_DOWNLOAD", "off")
	dir := t.TempDir()
	source := filepath.Join(dir, "hello.alc")
	os.WriteFile(source, []byte("defmodule Hello do\n  def main() do\n    IO.puts(\"hi\")\n  end\nend\n"), 0o600)
	err := BuildTo(source, filepath.Join(dir, "hello"))
	if err == nil || !strings.Contains(err.Error(), "no go command") {
		t.Fatalf("got %v", err)
	}
}

func TestDownloadedGoGetsItsOwnRoot(t *testing.T) {
	cache := t.TempDir()
	t.Setenv("ALCHEM_CACHE", cache)
	inherited := []string{"GOROOT=/elsewhere", "GOTOOLDIR=/elsewhere/pkg/tool", "GOTOOLCHAIN=auto", "HOME=/h"}
	downloaded := filepath.Join(cache, "toolchains", GoRelease, "go", "bin", "go")
	got := strings.Join(goEnvironment(downloaded, inherited), " ")
	want := "HOME=/h GOROOT=" + filepath.Join(cache, "toolchains", GoRelease, "go") + " GOTOOLCHAIN=local"
	if got != want {
		t.Fatalf("got %s, want %s", got, want)
	}
	if got := goEnvironment("/usr/local/go/bin/go", inherited); len(got) != len(inherited) {
		t.Fatalf("an installed go had its environment changed: %v", got)
	}
}
