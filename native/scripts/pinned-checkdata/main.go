package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// The tables the pinned checker types a program's calls with, one record a
// line, fields apart by \x1f and lists by \x1e (scripts/generate-check-data.py):
//
//	L key name params result vars equal order show keys num cal codec read
//	O key further-keys
//	S name params result
//	T kind name local params fields variants   (a variant is name\x1dfield:type...)
func main() {
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	list := func(items []string) string { return strings.Join(items, "\x1e") }
	keys := []string{}
	for key := range syntax.Libraries {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		e := syntax.Libraries[key]
		fmt.Fprintln(out, strings.Join([]string{"L", key, e.Name, list(e.Params), e.Result, list(e.Vars), list(e.Equal), list(e.Order), list(e.Show), list(e.Keys), list(e.Num), list(e.Cal), list(e.Codec), list(e.Read)}, "\x1f"))
	}
	keys = keys[:0]
	for key := range syntax.Overloads {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		fmt.Fprintln(out, strings.Join([]string{"O", key, list(syntax.Overloads[key])}, "\x1f"))
	}
	keys = keys[:0]
	for name := range syntax.SimpleBuiltins {
		keys = append(keys, name)
	}
	sort.Strings(keys)
	for _, name := range keys {
		b := syntax.SimpleBuiltins[name]
		fmt.Fprintln(out, strings.Join([]string{"S", name, list(b.Params), b.Result}, "\x1f"))
	}
	for _, d := range syntax.BuiltinTypes() {
		fields := []string{}
		for _, f := range d.Fields {
			// A field with a default value is marked: name=:type.
			marked := f.Name
			if f.Default != nil {
				marked += "="
			}
			fields = append(fields, marked+":"+f.Type)
		}
		variants := []string{}
		for _, v := range d.Variants {
			parts := []string{v.Name}
			for _, f := range v.Fields {
				parts = append(parts, f.Name+":"+f.Type)
			}
			variants = append(variants, strings.Join(parts, "\x1d"))
		}
		fmt.Fprintln(out, strings.Join([]string{"T", d.Kind, d.Name, d.Local, list(d.Params), list(fields), list(variants)}, "\x1f"))
	}
}
