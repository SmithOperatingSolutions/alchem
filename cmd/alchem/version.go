package main

import (
	"encoding/json"
	"fmt"
	"runtime"
	"runtime/debug"

	"github.com/SmithOperatingSolutions/alchem/compiler"
)

// version is set by release builds with -ldflags "-X main.version=v1.2.3".
var version = ""

// compilerVersion is the release this binary was built from: the linker
// setting, else the module version go install recorded, else "devel".
func compilerVersion() string {
	if version != "" {
		return version
	}
	if info, ok := debug.ReadBuildInfo(); ok && info.Main.Version != "" && info.Main.Version != "(devel)" {
		return info.Main.Version
	}
	return "devel"
}

func versionText(asJSON bool) string {
	toolchain := compiler.LocateGo()
	if asJSON {
		data, _ := json.MarshalIndent(struct {
			Version   string             `json:"version"`
			Platform  string             `json:"platform"`
			GoRelease string             `json:"go_release"`
			Toolchain compiler.Toolchain `json:"toolchain"`
		}{compilerVersion(), runtime.GOOS + "/" + runtime.GOARCH, compiler.GoRelease, toolchain}, "", "  ")
		return string(data) + "\n"
	}
	text := fmt.Sprintf("alchem %s %s/%s\n", compilerVersion(), runtime.GOOS, runtime.GOARCH)
	switch toolchain.Source {
	case "download":
		text += fmt.Sprintf("go: none installed; the first build downloads %s\n", compiler.GoRelease)
	case "missing":
		text += "go: none installed, and ALCHEM_GO_DOWNLOAD turns downloading off\n"
	default:
		text += fmt.Sprintf("go: %s (%s)\n", toolchain.Path, toolchain.Source)
	}
	return text
}
