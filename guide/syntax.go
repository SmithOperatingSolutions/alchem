package guide

import (
	"fmt"
	"sort"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// SyntaxIndex lists the topics by group.
func SyntaxIndex() string {
	var b strings.Builder
	b.WriteString("Syntax topics. Run alchem syntax <topic> for the rules and an example, or alchem syntax --all for everything.\n")
	order, topics := groups(syntax.Topics, func(t syntax.Topic) string { return t.Group })
	for _, group := range order {
		b.WriteString("\n" + group + "\n")
		for _, topic := range topics[group] {
			fmt.Fprintf(&b, "  %-20s %s\n", topic.Name, topic.Summary)
		}
	}
	return b.String()
}

// sampleText is an example as help shows it: a whole file when it has
// declarations, otherwise just the statements.
func sampleText(sample syntax.Sample) string {
	var b strings.Builder
	names := make([]string, 0, len(sample.Files))
	for name := range sample.Files {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		b.WriteString("# " + name + "\n" + sample.Files[name] + "\n")
	}
	switch {
	case sample.File != "":
		b.WriteString(sample.File)
	case sample.Defs != "":
		b.WriteString(sample.Program("Example", false))
	default:
		b.WriteString(sample.Body + "\n")
	}
	return b.String()
}

func topicText(topic syntax.Topic, heading string) string {
	var b strings.Builder
	b.WriteString(heading + topic.Name + "\n\n" + topic.Summary + "\n\n")
	for _, note := range topic.Notes {
		b.WriteString("- " + note + "\n")
	}
	for _, sample := range topic.Examples {
		b.WriteString("\nExample: " + sample.Title + "\n\n```elixir\n" + sampleText(sample) + "```\n")
	}
	if len(topic.See) > 0 {
		var topics, modules []string
		for _, name := range topic.See {
			if _, ok := syntax.TopicNamed(name); ok {
				topics = append(topics, "alchem syntax "+name)
			} else {
				modules = append(modules, "alchem doc "+name)
			}
		}
		b.WriteString("\nSee also: " + strings.Join(append(topics, modules...), ", ") + "\n")
	}
	return b.String()
}

// Syntax explains one topic.
func Syntax(name string) (string, error) {
	topic, ok := syntax.TopicNamed(strings.ToLower(name))
	if !ok {
		var names []string
		for _, entry := range syntax.Topics {
			names = append(names, entry.Name)
		}
		return "", fmt.Errorf("no syntax topic %q%s (alchem syntax lists them)", name, suggest(name, names))
	}
	return topicText(topic, "# "), nil
}

// SyntaxAll explains every topic.
func SyntaxAll() string {
	var parts []string
	for _, topic := range syntax.Topics {
		parts = append(parts, topicText(topic, "# "))
	}
	return strings.Join(parts, "\n")
}

type topicJSON struct {
	Name     string       `json:"name"`
	Group    string       `json:"group"`
	Summary  string       `json:"summary"`
	Notes    []string     `json:"notes"`
	Examples []sampleJSON `json:"examples"`
	See      []string     `json:"see,omitempty"`
}

type sampleJSON struct {
	Title  string `json:"title"`
	Source string `json:"source"`
}

// SyntaxJSON is one topic, or all of them when the name is empty, as data.
func SyntaxJSON(name string) (string, error) {
	var out []topicJSON
	for _, topic := range syntax.Topics {
		if name != "" && topic.Name != strings.ToLower(name) {
			continue
		}
		entry := topicJSON{Name: topic.Name, Group: topic.Group, Summary: topic.Summary, Notes: topic.Notes, See: topic.See}
		for _, sample := range topic.Examples {
			entry.Examples = append(entry.Examples, sampleJSON{sample.Title, sampleText(sample)})
		}
		out = append(out, entry)
	}
	if name != "" {
		if len(out) == 0 {
			_, err := Syntax(name)
			return "", err
		}
		return encode(out[0]), nil
	}
	return encode(out), nil
}
