// Command gorelease pins the Go release that alchem downloads when no go
// command is installed: it reads the release's archive checksums from
// go.dev and rewrites GoRelease and goArchives in compiler/toolchain.go.
//
//	go run ./tools/gorelease go1.27.4
package main

import (
	"encoding/json"
	"fmt"
	"go/format"
	"net/http"
	"os"
	"regexp"
	"sort"
	"strings"
)

const toolchainFile = "compiler/toolchain.go"

var platforms = []string{"darwin/amd64", "darwin/arm64", "linux/amd64", "linux/arm64", "windows/amd64", "windows/arm64"}

func main() {
	if len(os.Args) != 2 || !strings.HasPrefix(os.Args[1], "go1.") {
		fmt.Fprintln(os.Stderr, "usage: go run ./tools/gorelease go1.N.M")
		os.Exit(2)
	}
	if err := pin(os.Args[1]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func pin(release string) error {
	response, err := http.Get("https://go.dev/dl/?mode=json&include=all")
	if err != nil {
		return err
	}
	defer response.Body.Close()
	var releases []struct {
		Version string
		Files   []struct{ OS, Arch, Kind, SHA256 string }
	}
	if err := json.NewDecoder(response.Body).Decode(&releases); err != nil {
		return fmt.Errorf("read go.dev releases: %w", err)
	}
	sums := map[string]string{}
	for _, r := range releases {
		if r.Version != release {
			continue
		}
		for _, f := range r.Files {
			if f.Kind == "archive" {
				sums[f.OS+"/"+f.Arch] = f.SHA256
			}
		}
	}
	var table strings.Builder
	table.WriteString("var goArchives = map[string]string{\n")
	sort.Strings(platforms)
	for _, platform := range platforms {
		sum, ok := sums[platform]
		if !ok {
			return fmt.Errorf("go.dev lists no %s archive for %s", release, platform)
		}
		fmt.Fprintf(&table, "\t%q: %q,\n", platform, sum)
	}
	table.WriteString("}")
	source, err := os.ReadFile(toolchainFile)
	if err != nil {
		return err
	}
	text := regexp.MustCompile(`const GoRelease = "[^"]*"`).ReplaceAllString(string(source), fmt.Sprintf("const GoRelease = %q", release))
	text = regexp.MustCompile(`(?s)var goArchives = map\[string\]string\{.*?\n\}`).ReplaceAllString(text, table.String())
	formatted, err := format.Source([]byte(text))
	if err != nil {
		return err
	}
	return os.WriteFile(toolchainFile, formatted, 0o644)
}
