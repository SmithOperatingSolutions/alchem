package guide

import (
	_ "embed"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// skill is the short instruction file installed for coding agents. It only
// says what Alchem is and where the real guide is: alchem agent-guide.
//
//go:embed skill.md
var skill string

const (
	skillName        = "alchem"
	skillDescription = "Write, check, test and document Alchem (.alc) programs. Use whenever a task touches .alc files or the alchem command."
	blockBegin       = "<!-- BEGIN alchem agent guide -->"
	blockEnd         = "<!-- END alchem agent guide -->"
)

// Target is one place an agent reads instructions from.
type Target struct {
	Name    string `json:"name"`
	Summary string `json:"summary"`
	// Path is relative to the project, or to the home directory for the
	// user scope; UserPath is empty when there is no user-wide location.
	Path     string `json:"path"`
	UserPath string `json:"user_path,omitempty"`
	// Shared files belong to the user: only a marked block is managed.
	Shared bool `json:"shared"`
	header string
}

// Targets lists the supported agents.
var Targets = []Target{
	{Name: "claude", Summary: "Claude Code skill", Path: ".claude/skills/alchem/SKILL.md", UserPath: ".claude/skills/alchem/SKILL.md",
		header: "---\nname: " + skillName + "\ndescription: " + skillDescription + "\n---\n\n"},
	{Name: "cursor", Summary: "Cursor rule", Path: ".cursor/rules/alchem.mdc",
		header: "---\ndescription: " + skillDescription + "\nglobs: \"**/*.alc\"\nalwaysApply: false\n---\n\n"},
	{Name: "windsurf", Summary: "Windsurf rule", Path: ".windsurf/rules/alchem.md"},
	{Name: "cline", Summary: "Cline rule", Path: ".clinerules/alchem.md"},
	{Name: "copilot", Summary: "GitHub Copilot instructions (managed block)", Path: ".github/copilot-instructions.md", Shared: true},
	{Name: "agents", Summary: "AGENTS.md, read by many agents (managed block)", Path: "AGENTS.md", UserPath: "AGENTS.md", Shared: true},
}

// TargetList describes the supported agents.
func TargetList(asJSON bool) string {
	if asJSON {
		return encode(Targets)
	}
	var b strings.Builder
	b.WriteString("Agents alchem agent-install can set up:\n\n")
	for _, target := range Targets {
		scopes := "project"
		if target.UserPath != "" {
			scopes = "project, user"
		}
		fmt.Fprintf(&b, "  %-9s %-48s %s (%s)\n", target.Name, target.Summary, target.Path, scopes)
	}
	return b.String()
}

// Installed reports what an installation did.
type Installed struct {
	Agent  string `json:"agent"`
	Path   string `json:"path"`
	Action string `json:"action"`
}

// Install writes the instruction file for an agent. scope is "project" or
// "user"; dir overrides the directory the scope implies. A file this command
// owns is replaced only with force; in a shared file only the marked block
// is written, and the rest is left as it is.
func Install(agent, scope, dir string, force bool) (Installed, error) {
	var target *Target
	var names []string
	for i := range Targets {
		names = append(names, Targets[i].Name)
		if Targets[i].Name == agent {
			target = &Targets[i]
		}
	}
	if target == nil {
		sort.Strings(names)
		return Installed{}, fmt.Errorf("unknown agent %q; choose one of %s", agent, strings.Join(names, ", "))
	}
	relative := target.Path
	switch scope {
	case "", "project":
		if dir == "" {
			dir = "."
		}
	case "user":
		if target.UserPath == "" {
			return Installed{}, fmt.Errorf("%s has no user-wide location; use --scope project", agent)
		}
		relative = target.UserPath
		if dir == "" {
			home, err := os.UserHomeDir()
			if err != nil {
				return Installed{}, err
			}
			dir = home
		}
	default:
		return Installed{}, fmt.Errorf("scope must be project or user, not %q", scope)
	}
	path := filepath.Join(dir, filepath.FromSlash(relative))
	result := Installed{Agent: agent, Path: path}
	current, err := os.ReadFile(path)
	exists := err == nil
	if err != nil && !os.IsNotExist(err) {
		return result, err
	}
	want := target.header + skill
	if target.Shared {
		block := blockBegin + "\n" + strings.TrimRight(skill, "\n") + "\n" + blockEnd + "\n"
		text := string(current)
		begin, end := strings.Index(text, blockBegin), strings.Index(text, blockEnd)
		switch {
		case begin >= 0 && end > begin:
			rest := strings.TrimPrefix(text[end+len(blockEnd):], "\n")
			want = text[:begin] + block + rest
		case begin >= 0 || end >= 0:
			return result, fmt.Errorf("%s has an incomplete alchem block; repair or remove its markers first", path)
		case strings.TrimSpace(text) == "":
			want = block
		default:
			want = strings.TrimRight(text, "\n") + "\n\n" + block
		}
	} else if exists && string(current) != want && !force {
		return result, fmt.Errorf("%s already exists with different content; pass --force to replace it", path)
	}
	switch {
	case exists && string(current) == want:
		result.Action = "unchanged"
		return result, nil
	case exists:
		result.Action = "updated"
	default:
		result.Action = "created"
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return result, err
	}
	return result, os.WriteFile(path, []byte(want), 0o644)
}
