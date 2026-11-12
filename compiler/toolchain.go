package compiler

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

// GoRelease is the Go release downloaded when no go command is installed.
// tools/gorelease rewrites it and goArchives from go.dev.
const GoRelease = "go1.27.4"

// goArchives holds the SHA-256 of each GoRelease archive, by GOOS/GOARCH.
// A download whose hash differs is discarded.
var goArchives = map[string]string{
	"darwin/amd64":  "2b799377704ef12db39bd254995d5c348c9cc8d86562ca817724390e56c38f43",
	"darwin/arm64":  "91a44a2b8a716600ad94a4f143e156116620db8828086a6e3602291be9bd0bb4",
	"linux/amd64":   "7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840",
	"linux/arm64":   "3392582988a273a87ab5043ee1b2c9c17a2c3c00580bf9326c47a2e0aaaeac92",
	"windows/amd64": "178ab98950ac69ab25069307dc6ade79f3816e414cce95b4da166a115cde1e7e",
	"windows/arm64": "9e7a72565792b8ab370b37ac9ac109799237abacb39ff2f541c438b963c0cc64",
}

// ToolchainLog receives the notice printed before Go is downloaded.
var ToolchainLog io.Writer = os.Stderr

// Toolchain describes the go command that builds will use.
type Toolchain struct {
	// Path is the go executable, or empty when none is available yet.
	Path string `json:"path,omitempty"`
	// Source is "ALCHEM_GO", "PATH", "downloaded", "download" (fetched on
	// first use) or "missing" (downloads are turned off).
	Source string `json:"source"`
	// Skipped explains why a go on PATH was not used, when it is too old.
	Skipped string `json:"skipped,omitempty"`
}

// LocateGo finds the go command without downloading anything. The
// ALCHEM_GO environment variable names one explicitly; otherwise a go on
// PATH is used when it is at least MinimumGo, then a release this compiler
// downloaded before.
func LocateGo() Toolchain {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	return locateGo(ctx)
}

func locateGo(ctx context.Context) Toolchain {
	if explicit := os.Getenv("ALCHEM_GO"); explicit != "" {
		return Toolchain{Path: explicit, Source: "ALCHEM_GO"}
	}
	skipped := ""
	if path, err := exec.LookPath("go"); err == nil {
		version, known := goVersion(ctx, path)
		if !known || atLeast(version, MinimumGo) {
			return Toolchain{Path: path, Source: "PATH"}
		}
		skipped = fmt.Sprintf("%s is %s; Alchem needs %s or newer", path, version, MinimumGo)
	}
	if root, err := toolchainRoot(); err == nil {
		executable := filepath.Join(root, "go", "bin", "go"+exeSuffix())
		if info, err := os.Stat(executable); err == nil && !info.IsDir() {
			return Toolchain{Path: executable, Source: "downloaded", Skipped: skipped}
		}
	}
	if downloadsOff() {
		return Toolchain{Source: "missing", Skipped: skipped}
	}
	return Toolchain{Source: "download", Skipped: skipped}
}

// MinimumGo is the oldest Go release that can build Alchem programs: the
// generated module and the embedded runtime declare it.
const MinimumGo = "go1.27"

var (
	versionMu sync.Mutex
	versions  = map[string]string{}
)

// goVersion asks the go executable at path for its release, such as
// "go1.27.4". known is false when it cannot tell, and such a go is used
// rather than second-guessed.
func goVersion(ctx context.Context, path string) (version string, known bool) {
	versionMu.Lock()
	cached, ok := versions[path]
	versionMu.Unlock()
	if ok {
		return cached, true
	}
	cmd := exec.CommandContext(ctx, path, "env", "GOVERSION")
	cmd.Dir = os.TempDir()
	cmd.Env = append(os.Environ(), "GOTOOLCHAIN=local", "GOFLAGS=")
	cmd.WaitDelay = time.Second
	out, err := cmd.Output()
	version = strings.TrimSpace(string(out))
	if err != nil || releaseNumbers(version) == nil {
		return version, false
	}
	versionMu.Lock()
	versions[path] = version
	versionMu.Unlock()
	return version, true
}

// releaseNumbers parses "go1.27.4", "go1.27" or "go1.28rc1" into its
// numbers; anything else, such as a development build, is nil.
func releaseNumbers(version string) []int {
	rest, ok := strings.CutPrefix(version, "go")
	if !ok {
		return nil
	}
	if i := strings.IndexAny(rest, "abcdefghijklmnopqrstuvwxyz -+"); i >= 0 {
		rest = rest[:i]
	}
	var numbers []int
	for _, part := range strings.Split(rest, ".") {
		n := 0
		if part == "" {
			return nil
		}
		for _, c := range part {
			if c < '0' || c > '9' {
				return nil
			}
			n = n*10 + int(c-'0')
		}
		numbers = append(numbers, n)
	}
	return numbers
}

// atLeast reports whether release version is minimum or newer.
func atLeast(version, minimum string) bool {
	have, want := releaseNumbers(version), releaseNumbers(minimum)
	for i := range want {
		if i >= len(have) {
			return false
		}
		if have[i] != want[i] {
			return have[i] > want[i]
		}
	}
	return true
}

var downloadMu sync.Mutex

// goCommand returns the go executable, downloading GoRelease into the user
// cache when no go command is installed.
func goCommand(ctx context.Context) (string, error) {
	found := locateGo(ctx)
	switch found.Source {
	case "missing":
		if found.Skipped != "" {
			return "", fmt.Errorf("%s: install a newer Go, set ALCHEM_GO to a go executable, or unset ALCHEM_GO_DOWNLOAD to let alchem download %s", found.Skipped, GoRelease)
		}
		return "", fmt.Errorf("no go command: install Go 1.27 or newer, set ALCHEM_GO to a go executable, or unset ALCHEM_GO_DOWNLOAD to let alchem download %s", GoRelease)
	case "download":
		downloadMu.Lock()
		defer downloadMu.Unlock()
		if again := locateGo(ctx); again.Path != "" {
			return again.Path, nil
		}
		return downloadGo(ctx)
	}
	return found.Path, nil
}

// goEnvironment adjusts environment for the go executable at goPath: a
// downloaded release gets its own GOROOT, so one inherited from another
// installation cannot mix two releases' tools.
func goEnvironment(goPath string, environment []string) []string {
	root, err := toolchainRoot()
	if err != nil || !within(root, goPath) {
		return environment
	}
	kept := make([]string, 0, len(environment)+2)
	for _, entry := range environment {
		upper := strings.ToUpper(entry)
		if !strings.HasPrefix(upper, "GOROOT=") && !strings.HasPrefix(upper, "GOTOOLDIR=") && !strings.HasPrefix(upper, "GOTOOLCHAIN=") {
			kept = append(kept, entry)
		}
	}
	return append(kept, "GOROOT="+filepath.Join(root, "go"), "GOTOOLCHAIN=local")
}

func downloadsOff() bool {
	switch strings.ToLower(os.Getenv("ALCHEM_GO_DOWNLOAD")) {
	case "off", "0", "false", "no":
		return true
	}
	return false
}

func exeSuffix() string {
	if runtime.GOOS == "windows" {
		return ".exe"
	}
	return ""
}

// toolchainRoot is the directory GoRelease is unpacked into.
func toolchainRoot() (string, error) {
	cache := os.Getenv("ALCHEM_CACHE")
	if cache == "" {
		user, err := os.UserCacheDir()
		if err != nil {
			return "", err
		}
		cache = filepath.Join(user, "alchem")
	}
	return filepath.Join(cache, "toolchains", GoRelease), nil
}

// goDownloadBase is where release archives are fetched from;
// ALCHEM_GO_MIRROR replaces it.
const goDownloadBase = "https://go.dev/dl/"

func downloadGo(ctx context.Context) (string, error) {
	platform := runtime.GOOS + "/" + runtime.GOARCH
	want, ok := goArchives[platform]
	if !ok {
		return "", fmt.Errorf("no go command, and alchem has no Go download for %s: install Go 1.27 or newer", platform)
	}
	root, err := toolchainRoot()
	if err != nil {
		return "", fmt.Errorf("no go command, and no cache directory to download one into: %w", err)
	}
	archive := GoRelease + "." + runtime.GOOS + "-" + runtime.GOARCH + ".tar.gz"
	if runtime.GOOS == "windows" {
		archive = strings.TrimSuffix(archive, ".tar.gz") + ".zip"
	}
	base := os.Getenv("ALCHEM_GO_MIRROR")
	if base == "" {
		base = goDownloadBase
	}
	url := strings.TrimSuffix(base, "/") + "/" + archive
	if found := locateGo(ctx); found.Skipped != "" {
		fmt.Fprintf(ToolchainLog, "alchem: %s; downloading %s to %s (once)\n", found.Skipped, GoRelease, root)
	} else {
		fmt.Fprintf(ToolchainLog, "alchem: no go command found; downloading %s to %s (once)\n", GoRelease, root)
	}

	if err := os.MkdirAll(filepath.Dir(root), 0o755); err != nil {
		return "", fmt.Errorf("download Go: %w", err)
	}
	file, err := os.CreateTemp(filepath.Dir(root), ".download-*")
	if err != nil {
		return "", fmt.Errorf("download Go: %w", err)
	}
	defer os.Remove(file.Name())
	defer file.Close()
	if err := fetch(ctx, url, want, file); err != nil {
		return "", fmt.Errorf("download Go from %s: %w", url, err)
	}

	staging, err := os.MkdirTemp(filepath.Dir(root), ".unpack-*")
	if err != nil {
		return "", fmt.Errorf("unpack Go: %w", err)
	}
	defer os.RemoveAll(staging)
	if strings.HasSuffix(archive, ".zip") {
		err = unzip(file, staging)
	} else {
		if _, err = file.Seek(0, io.SeekStart); err == nil {
			err = untar(file, staging)
		}
	}
	if err != nil {
		return "", fmt.Errorf("unpack Go: %w", err)
	}
	executable := filepath.Join(staging, "go", "bin", "go"+exeSuffix())
	if _, err := os.Stat(executable); err != nil {
		return "", fmt.Errorf("unpack Go: the archive has no go/bin/go%s", exeSuffix())
	}
	if err := os.Rename(staging, root); err != nil {
		// Another alchem process may have finished first.
		if existing := filepath.Join(root, "go", "bin", "go"+exeSuffix()); fileExists(existing) {
			return existing, nil
		}
		return "", fmt.Errorf("install Go: %w", err)
	}
	return filepath.Join(root, "go", "bin", "go"+exeSuffix()), nil
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// fetch writes the body at url to out and checks its SHA-256.
func fetch(ctx context.Context, url, want string, out io.Writer) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	client := &http.Client{Timeout: 30 * time.Minute}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("server answered %s", response.Status)
	}
	hash := sha256.New()
	if _, err := io.Copy(io.MultiWriter(out, hash), response.Body); err != nil {
		return err
	}
	if got := hex.EncodeToString(hash.Sum(nil)); got != want {
		return fmt.Errorf("checksum mismatch: got %s, want %s", got, want)
	}
	return nil
}

// unpackTarget joins name to dir, refusing a name that would leave dir.
func unpackTarget(dir, name string) (string, error) {
	target := filepath.Join(dir, filepath.FromSlash(name))
	if !within(dir, target) {
		return "", fmt.Errorf("archive entry %q is outside the archive", name)
	}
	return target, nil
}

func writeEntry(target string, mode os.FileMode, body io.Reader) error {
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return err
	}
	out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode.Perm()|0o200)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, body); err != nil {
		out.Close()
		return err
	}
	return out.Close()
}

func untar(in io.Reader, dir string) error {
	compressed, err := gzip.NewReader(in)
	if err != nil {
		return err
	}
	archive := tar.NewReader(compressed)
	for {
		header, err := archive.Next()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}
		target, err := unpackTarget(dir, header.Name)
		if err != nil {
			return err
		}
		switch header.Typeflag {
		case tar.TypeDir:
			err = os.MkdirAll(target, 0o755)
		case tar.TypeReg:
			err = writeEntry(target, header.FileInfo().Mode(), archive)
		}
		if err != nil {
			return err
		}
	}
}

func unzip(file *os.File, dir string) error {
	info, err := file.Stat()
	if err != nil {
		return err
	}
	archive, err := zip.NewReader(file, info.Size())
	if err != nil {
		return err
	}
	for _, entry := range archive.File {
		target, err := unpackTarget(dir, entry.Name)
		if err != nil {
			return err
		}
		if entry.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0o755); err != nil {
				return err
			}
			continue
		}
		body, err := entry.Open()
		if err != nil {
			return err
		}
		err = writeEntry(target, entry.Mode(), body)
		body.Close()
		if err != nil {
			return err
		}
	}
	return nil
}
