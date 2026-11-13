package main

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
)

func fakeSums(version string) map[string]string {
	sums := map[string]string{}
	for i, platform := range []string{"darwin_amd64.tar.gz", "darwin_arm64.tar.gz", "linux_amd64.tar.gz", "linux_arm64.tar.gz", "windows_amd64.zip", "windows_arm64.zip"} {
		sums["alchem_"+version+"_"+platform] = strings.Repeat(fmt.Sprintf("%x", i+1), 64)
	}
	return sums
}

func TestFormulaNamesEveryUnixArchive(t *testing.T) {
	formula, err := Formula("v1.2.3", fakeSums("v1.2.3"))
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		`version "1.2.3"`,
		`url "https://github.com/SmithOperatingSolutions/alchem/releases/download/v1.2.3/alchem_v1.2.3_darwin_arm64.tar.gz"`,
		`sha256 "` + strings.Repeat("2", 64) + `"`,
		`url "https://github.com/SmithOperatingSolutions/alchem/releases/download/v1.2.3/alchem_v1.2.3_linux_amd64.tar.gz"`,
		`bin.install "alchem"`,
		`assert_match "alchem v1.2.3"`,
	} {
		if !strings.Contains(formula, want) {
			t.Errorf("formula lacks %s:\n%s", want, formula)
		}
	}
	missing := fakeSums("v1.2.3")
	delete(missing, "alchem_v1.2.3_linux_arm64.tar.gz")
	if _, err := Formula("v1.2.3", missing); err == nil || !strings.Contains(err.Error(), "linux_arm64") {
		t.Fatalf("a missing archive: %v", err)
	}
}

func TestManifestNamesBothWindowsArchives(t *testing.T) {
	text, err := Manifest("v1.2.3", fakeSums("v1.2.3"))
	if err != nil {
		t.Fatal(err)
	}
	var manifest struct {
		Version      string
		Bin          string
		Architecture map[string]struct {
			URL        string `json:"url"`
			Hash       string `json:"hash"`
			ExtractDir string `json:"extract_dir"`
		}
		Autoupdate struct {
			Hash struct{ URL string }
		}
	}
	if err := json.Unmarshal([]byte(text), &manifest); err != nil {
		t.Fatal(err)
	}
	x64 := manifest.Architecture["64bit"]
	if manifest.Version != "1.2.3" || manifest.Bin != "alchem.exe" || x64.Hash != strings.Repeat("5", 64) ||
		x64.ExtractDir != "alchem_v1.2.3_windows_amd64" || !strings.HasSuffix(x64.URL, "/v1.2.3/alchem_v1.2.3_windows_amd64.zip") ||
		manifest.Architecture["arm64"].Hash != strings.Repeat("6", 64) || manifest.Autoupdate.Hash.URL != "$baseurl/checksums.txt" {
		t.Fatalf("manifest:\n%s", text)
	}
	missing := fakeSums("v1.2.3")
	delete(missing, "alchem_v1.2.3_windows_arm64.zip")
	if _, err := Manifest("v1.2.3", missing); err == nil {
		t.Fatal("a missing Windows archive was accepted")
	}
}

func TestRunWritesBothFilesAndChecksVersions(t *testing.T) {
	dir := t.TempDir()
	var sums strings.Builder
	for file, sum := range fakeSums("v0.9.0") {
		sums.WriteString(sum + "  " + file + "\n")
	}
	sums.WriteString("not a checksum line\n")
	path := filepath.Join(dir, "checksums.txt")
	if err := os.WriteFile(path, []byte(sums.String()), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := run("v0.9.0", path, dir); err != nil {
		t.Fatal(err)
	}
	for _, file := range []string{"Formula/alchem.rb", "bucket/alchem.json"} {
		data, err := os.ReadFile(filepath.Join(dir, file))
		if err != nil || !strings.Contains(string(data), "0.9.0") {
			t.Fatalf("%s: %v", file, err)
		}
	}
	for _, bad := range []string{"0.9.0", "v1", "latest", "v1.2.3;rm"} {
		if err := run(bad, path, dir); err == nil {
			t.Errorf("version %q was accepted", bad)
		}
	}
	if err := run("v0.9.0", filepath.Join(dir, "missing.txt"), dir); err == nil {
		t.Error("a missing checksums file was accepted")
	}
}

// The committed manifests describe the same release.
func TestCommittedManifestsAgree(t *testing.T) {
	formula, err := os.ReadFile("../../Formula/alchem.rb")
	if err != nil {
		t.Fatal(err)
	}
	bucket, err := os.ReadFile("../../bucket/alchem.json")
	if err != nil {
		t.Fatal(err)
	}
	version := regexp.MustCompile(`version "([^"]+)"`).FindSubmatch(formula)
	var manifest struct{ Version string }
	if version == nil || json.Unmarshal(bucket, &manifest) != nil || manifest.Version != string(version[1]) {
		t.Fatalf("Formula is %s and bucket is %s", version, manifest.Version)
	}
}

// install.sh downloads a release, checks it against checksums.txt and puts
// the binary in place; it refuses a download whose checksum differs.
func TestInstallScript(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("install.sh is for macOS and Linux")
	}
	goos := runtime.GOOS
	name := "alchem_v9.9.9_" + goos + "_" + runtime.GOARCH
	var archive bytes.Buffer
	zipped := gzip.NewWriter(&archive)
	files := tar.NewWriter(zipped)
	script := "#!/bin/sh\necho \"alchem v9.9.9 fake\"\n"
	files.WriteHeader(&tar.Header{Name: name + "/", Typeflag: tar.TypeDir, Mode: 0o755})
	files.WriteHeader(&tar.Header{Name: name + "/alchem", Typeflag: tar.TypeReg, Mode: 0o755, Size: int64(len(script))})
	files.Write([]byte(script))
	files.Close()
	zipped.Close()
	sum := sha256.Sum256(archive.Bytes())
	checksums := hex.EncodeToString(sum[:]) + "  " + name + ".tar.gz\n"
	corrupt := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/releases/latest":
			http.Redirect(w, r, "/releases/tag/v9.9.9", http.StatusFound)
		case "/releases/tag/v9.9.9":
			fmt.Fprint(w, "<html>Alchem v9.9.9</html>")
		case "/releases/download/v9.9.9/" + name + ".tar.gz":
			data := archive.Bytes()
			if corrupt {
				data = append([]byte{}, data...)
				data[len(data)-1] ^= 0xff
			}
			w.Write(data)
		case "/releases/download/v9.9.9/checksums.txt":
			fmt.Fprint(w, checksums)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	install := func(dir string, env ...string) (string, error) {
		cmd := exec.Command("sh", "../../install.sh")
		cmd.Env = append(os.Environ(), append([]string{
			"ALCHEM_RELEASES_URL=" + server.URL + "/releases",
			"ALCHEM_INSTALL_DIR=" + dir,
			"ALCHEM_VERSION=",
		}, env...)...)
		out, err := cmd.CombinedOutput()
		return string(out), err
	}
	dir := filepath.Join(t.TempDir(), "bin")
	out, err := install(dir)
	if err != nil || !strings.Contains(out, "Installed alchem v9.9.9 fake to "+dir+"/alchem") {
		t.Fatalf("install: %v\n%s", err, out)
	}
	if out, err = install(dir, "ALCHEM_VERSION=9.9.9"); err != nil {
		t.Fatalf("install of a named version: %v\n%s", err, out)
	}
	corrupt = true
	other := filepath.Join(t.TempDir(), "bin")
	if out, err = install(other); err == nil || !strings.Contains(out, "checksum mismatch") {
		t.Fatalf("a corrupt download: %v\n%s", err, out)
	}
	if _, statErr := os.Stat(filepath.Join(other, "alchem")); statErr == nil {
		t.Fatal("a corrupt download was installed")
	}
	if out, err = install(other, "ALCHEM_VERSION=v1.0.0"); err == nil || !strings.Contains(out, "could not download") {
		t.Fatalf("a missing release: %v\n%s", err, out)
	}
}
