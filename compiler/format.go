package compiler

import (
	"fmt"
	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/lexer"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
	"regexp"
	"strconv"
	"strings"
)

// Format canonicalizes every supported syntax form without resolving imports.
func Format(source string) (string, error) {
	p, err := syntax.ParseSyntax(source)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	remark := func(lines []string, depth int) {
		for _, line := range lines {
			b.WriteString(strings.TrimRight(indent(depth)+"# "+line, " ") + "\n")
		}
	}
	remark(p.Leading, 0)
	b.WriteString("defmodule " + p.Module + " do\n")
	// docstring writes @doc text as a heredoc at the given depth.
	docstring := func(attribute, text string, depth int) {
		if text == "" {
			return
		}
		if strings.Contains(text, `"""`) {
			b.WriteString(indent(depth) + "@" + attribute + " " + strconv.Quote(text) + "\n")
			return
		}
		// Text with a backslash or #{ is written as ~S""", which takes it
		// as it is; a heredoc would read those as escapes and interpolation.
		opener := `"""`
		if strings.Contains(text, "\\") || strings.Contains(text, "#{") {
			opener = `~S"""`
		}
		b.WriteString(indent(depth) + "@" + attribute + " " + opener + "\n")
		for _, line := range strings.Split(strings.TrimSuffix(text, "\n"), "\n") {
			b.WriteString(strings.TrimRight(indent(depth)+line, " ") + "\n")
		}
		b.WriteString(indent(depth) + "\"\"\"\n")
	}
	docstring("moduledoc", p.ModuleDoc, 1)
	for _, path := range p.Imports {
		b.WriteString("  import " + strconv.Quote(path) + "\n")
	}
	for _, use := range p.Uses {
		line := "  use " + use.Module
		for i, name := range use.Names {
			line += ", " + name + ": " + formatExpr(use.Values[i], 1)
		}
		b.WriteString(line + "\n")
	}
	for _, name := range p.Doctests {
		b.WriteString("  doctest " + name + "\n")
	}
	for _, tag := range p.GroupTags[""] {
		b.WriteString("  @moduletag " + formatTag(tag) + "\n")
	}
	for _, require := range p.Requires {
		b.WriteString("  require " + strconv.Quote(require.Path) + " " + strconv.Quote(require.Version) + "\n")
	}
	for i, constant := range p.Constants {
		if i == 0 && len(p.Imports)+len(p.Requires)+len(p.Uses)+len(p.Doctests)+len(p.GroupTags[""])+len(p.ModuleDoc) > 0 {
			b.WriteString("\n")
		}
		remark(constant.Comments, 1)
		b.WriteString("  @" + constant.Name + " " + formatExpr(constant.Value, 1) + "\n")
	}
	implementing := ""
	for i, decl := range p.Types {
		if i > 0 || len(p.Imports)+len(p.Requires)+len(p.Constants)+len(p.ModuleDoc) > 0 {
			b.WriteString("\n")
		}
		remark(decl.Comments, 1)
		docstring("typedoc", decl.Doc, 1)
		if decl.Kind == "extern" {
			b.WriteString("  extern type " + decl.Local + " = " + strconv.Quote(decl.Extern) + "\n")
			continue
		}
		keyword := "struct"
		if decl.Kind == "sum" {
			keyword = "type"
		}
		if decl.Exception {
			keyword = "defexception"
		}
		b.WriteString("  " + keyword + " " + decl.Local)
		if len(decl.Params) > 0 {
			b.WriteString("[" + strings.Join(decl.Params, ", ") + "]")
		}
		b.WriteString(" do\n")
		for _, field := range decl.Fields {
			b.WriteString("    " + field.Name + ": " + spaced(field.Type))
			if field.Default != nil {
				b.WriteString(" = " + formatExpr(field.Default, 2))
			}
			b.WriteString("\n")
		}
		for _, variant := range decl.Variants {
			b.WriteString("    " + variant.Name)
			if len(variant.Fields) > 0 {
				b.WriteString("(" + formatParams(variant.Fields) + ")")
			}
			b.WriteString("\n")
		}
		b.WriteString("  end\n")
	}
	// open holds the describe blocks the next declaration would sit in.
	var open []string
	closeTo := func(depth int) {
		for len(open) > depth {
			open = open[:len(open)-1]
			b.WriteString(indent(len(open)+1) + "end\n")
		}
	}
	for i, protocol := range p.Protocols {
		if i > 0 || len(p.Imports)+len(p.Requires)+len(p.Types)+len(p.Doctests)+len(p.GroupTags[""])+len(p.Constants)+len(p.ModuleDoc) > 0 {
			b.WriteString("\n")
		}
		b.WriteString("  defprotocol " + protocol.Name + " do\n")
		for _, function := range protocol.Functions {
			b.WriteString("    def " + function.Name + "(" + strings.Join(function.Params, ", ") + ")")
			if function.Type != "void" {
				b.WriteString(": " + spaced(function.Type))
			}
			b.WriteString("\n")
		}
		b.WriteString("  end\n")
	}
	for i, macro := range p.Macros {
		if i > 0 || len(p.Imports)+len(p.Requires)+len(p.Types)+len(p.Protocols)+len(p.Doctests)+len(p.GroupTags[""])+len(p.Constants)+len(p.ModuleDoc) > 0 {
			b.WriteString("\n")
		}
		parameters := append([]string{}, macro.Params...)
		if macro.Block != "" {
			parameters = append(parameters, "do: "+macro.Block)
		}
		b.WriteString("  defmacro " + macro.Name + "(" + strings.Join(parameters, ", ") + ") do\n    quote do\n")
		for j, f := range macro.Definitions {
			if j > 0 {
				b.WriteString("\n")
			}
			keyword := "def"
			if f.Private {
				keyword = "defp"
			}
			b.WriteString(indent(3) + keyword + " " + f.Name + "(" + formatParams(f.Params) + ")")
			if f.Type != "void" {
				b.WriteString(": " + spaced(f.Type))
			}
			if f.Guard != nil {
				b.WriteString(" when " + formatExpr(f.Guard, 3))
			}
			b.WriteString(" do\n" + formatBlock(f.Body, 4) + indent(3) + "end\n")
		}
		b.WriteString(formatBlock(macro.Body, 3) + "    end\n  end\n")
	}
	for i, f := range p.Functions {
		path := ast.Groups(f.Group)
		shared := 0
		for shared < len(open) && shared < len(path) && open[shared] == path[shared] {
			shared++
		}
		closeTo(shared)
		// The functions of one defimpl block share the end of their name.
		block := ""
		if f.Protocol != "" {
			block = f.Name[strings.Index(f.Name, "$"):]
		}
		if block != implementing && implementing != "" {
			b.WriteString("  end\n")
		}
		if i > 0 || len(p.Imports)+len(p.Requires)+len(p.Types)+len(p.Protocols)+len(p.Macros)+len(p.Doctests)+len(p.GroupTags[""])+len(p.Constants)+len(p.ModuleDoc) > 0 {
			b.WriteString("\n")
		}
		if block != implementing && block != "" {
			b.WriteString("  defimpl " + f.Protocol + ", for: " + f.For + " do\n")
		}
		implementing = block
		inner := 0
		if block != "" {
			inner = 1
		}
		for _, name := range path[shared:] {
			inside := strings.Join(append(append([]string{}, open...), name), ast.GroupSeparator)
			for _, tag := range p.GroupTags[inside] {
				b.WriteString(indent(len(open)+1) + "@tag " + formatTag(tag) + "\n")
			}
			b.WriteString(indent(len(open)+1) + "describe " + strconv.Quote(name) + " do\n")
			open = append(open, name)
		}
		remark(f.Comments, len(open)+1+inner)
		docstring("doc", f.Doc, len(open)+1+inner)
		if f.Test != "" || f.Setup {
			depth := len(open) + 1
			head := "setup"
			if f.All {
				head = "setup_all"
			}
			if f.Test != "" {
				head = "test " + strconv.Quote(f.Test)
			}
			if len(f.Params) == 1 {
				separator := " "
				if f.Test != "" {
					separator = ", "
				}
				head += separator + formatParams(f.Params)
			}
			for _, tag := range f.Tags {
				b.WriteString(indent(depth) + "@tag " + formatTag(tag) + "\n")
			}
			b.WriteString(indent(depth) + head + " do\n" + formatBlock(f.Body, depth+1) + indent(depth) + "end\n")
			continue
		}
		keyword := "def"
		if f.Private {
			keyword = "defp"
		}
		if f.Extern != "" {
			keyword = "extern"
		}
		name, depth := f.Name, 1
		if f.Protocol != "" {
			name, depth = f.ProtocolFunction, 2
		}
		b.WriteString(indent(depth) + keyword + " " + name + "(" + formatParams(f.Params) + ")")
		if f.Type != "void" {
			b.WriteString(": " + spaced(f.Type))
		}
		if f.Extern != "" {
			b.WriteString(" = " + strconv.Quote(f.Extern) + "\n")
			continue
		}
		if f.Guard != nil {
			b.WriteString(" when " + formatExpr(f.Guard, depth))
		}
		b.WriteString(" do\n" + formatBlock(f.Body, depth+1) + indent(depth) + "end\n")
	}
	if implementing != "" {
		b.WriteString("  end\n")
	}
	closeTo(0)
	remark(p.Trailing, 1)
	b.WriteString("end\n")
	return b.String(), nil
}
func formatParams(params []ast.Parameter) string {
	out := []string{}
	for _, p := range params {
		text := p.Name
		if p.Pattern != nil {
			text = formatPattern(p.Pattern)
		}
		if p.Type != "" {
			text += ": " + spaced(p.Type)
		}
		if p.Default != nil {
			text += " \\\\ " + formatExpr(p.Default, 0)
		}
		out = append(out, text)
	}
	return strings.Join(out, ", ")
}

func init() {
	syntax.PatternText = formatPattern
	syntax.ExprText = func(e *ast.Expr) string { return formatExpr(e, 0) }
}

// lineBreak is a line end with the indentation around it.
var lineBreak = regexp.MustCompile(`[ \t]*\n[ \t]*`)

func indent(n int) string { return strings.Repeat("  ", n) }
func formatLiteral(v ast.Literal) string {
	switch v.Kind {
	case "integer":
		if v.Text != "" {
			return v.Text
		}
		return strconv.FormatInt(v.Integer, 10)
	case "boolean":
		return strconv.FormatBool(v.Boolean)
	case "float":
		return ast.FormatFloat(v.Float)
	case "atom":
		return ":" + v.Text
	default:
		return strings.ReplaceAll(strconv.Quote(v.Text), "#{", "\\#{")
	}
}

// spaced writes a type as people do, with a space after each comma:
// map[string, list[integer]].
func spaced(t string) string { return strings.ReplaceAll(t, ",", ", ") }

// binding is how tightly an expression holds together when it is the operand
// of an operator, with the parser's precedences; forms that are not operators
// bind tightest.
func binding(e *ast.Expr) int {
	switch {
	case e.Kind == "binary":
		return syntax.Precedence(e.Op)
	case e.Kind == "in":
		return syntax.Precedence("in")
	case e.Kind == "range":
		return syntax.Precedence("..")
	case e.Kind == "call" && e.Pipe && len(e.Args) > 0:
		return syntax.Precedence("|>")
	case e.Kind == "value" && len(e.Body) == 1 && e.Body[0].Declared == "do:":
		// A one-line if reads up to the end of its else: value, so as an
		// operand it needs parentheses.
		return 0
	}
	return 100
}

// formatWithin renders an expression that must bind at least as tightly as
// least, parenthesizing it when it does not.
func formatWithin(e *ast.Expr, n, least int) string {
	text := formatExpr(e, n)
	if binding(e) < least {
		return "(" + text + ")"
	}
	return text
}

func formatExpr(e *ast.Expr, n int) string {
	if e == nil {
		return ""
	}
	if e.Heredoc != "" {
		return formatHeredoc(e.Heredoc, n)
	}
	args := []string{}
	for _, a := range e.Args {
		args = append(args, formatExpr(a, n))
	}
	switch e.Kind {
	case "literal":
		return formatLiteral(e.Value)
	case "name":
		return e.Name
	case "constant":
		return "@" + e.Name
	case "template":
		text := ""
		for i, part := range e.Args {
			if part.Op == "text" {
				quoted := formatLiteral(part.Value)
				text += quoted[1 : len(quoted)-1]
			} else {
				// A string cannot span lines, so whatever was interpolated
				// was written on one: a block inside it holds one statement
				// and is put back on one line.
				text += "#{" + lineBreak.ReplaceAllString(args[i], " ") + "}"
			}
		}
		return "\"" + text + "\""
	case "funcref":
		if e.Op != "" {
			return "&" + e.Name + "/" + e.Op
		}
		return "&" + e.Name
	case "field":
		return formatOperand(e.Left, n) + "." + e.Name
	case "struct":
		for i, label := range e.Labels {
			args[i] = label + ": " + args[i]
		}
		base := ""
		if e.Left != nil {
			base = formatExpr(e.Left, n) + " | "
		}
		return "%" + e.Name + "{" + base + strings.Join(args, ", ") + "}"
	case "list":
		// A pair written name: value stays in that form.
		for i, item := range e.Args {
			if item.Kind == "tuple" && item.Op == "keyword" {
				args[i] = item.Args[0].Value.Text + ": " + formatExpr(item.Args[1], n)
			}
		}
		if e.Right != nil {
			return "[" + strings.Join(args, ", ") + " | " + formatExpr(e.Right, n) + "]"
		}
		// A long list puts each element on a line of its own.
		if one := "[" + strings.Join(args, ", ") + "]"; len(args) < 2 || len(one)+2*n <= 98 || strings.Contains(one, "\n") {
			return one
		}
		items := []string{}
		for _, item := range e.Args {
			text := formatExpr(item, n+1)
			if item.Kind == "tuple" && item.Op == "keyword" {
				text = item.Args[0].Value.Text + ": " + formatExpr(item.Args[1], n+1)
			}
			items = append(items, indent(n+1)+text)
		}
		return "[\n" + strings.Join(items, ",\n") + "\n" + indent(n) + "]"
	case "tuple":
		return "{" + strings.Join(args, ", ") + "}"
	case "map":
		for i, k := range e.Keys {
			args[i] = formatExpr(k, n) + " => " + args[i]
		}
		return "%{" + strings.Join(args, ", ") + "}"
	case "call":
		if e.Pipe && len(args) > 0 {
			pipe := syntax.Precedence("|>")
			return formatWithin(e.Args[0], n, pipe) + " |> " + e.Name + "(" + strings.Join(args[1:], ", ") + ")"
		}
		if e.Op == "do" {
			return e.Name + "(" + strings.Join(args, ", ") + ") do\n" + formatBlock(e.Body, n+1) + indent(n) + "end"
		}
		return e.Name + "(" + strings.Join(args, ", ") + ")"
	case "invoke":
		callee := formatOperand(e.Left, n)
		if e.Left.Kind == "lambda" && !strings.HasPrefix(callee, "(") {
			// A function literal called where it is written keeps its
			// parentheses: fn ... end(x) would not read back as a call.
			callee = "(" + callee + ")"
		}
		return callee + "(" + strings.Join(args, ", ") + ")"
	case "index":
		return formatOperand(e.Left, n) + "[" + formatExpr(e.Right, n) + "]"
	case "unary":
		// The parser folds "-" followed by digits into one literal, so emit that
		// literal directly; "(- 5)" would reparse differently and never settle.
		if e.Op == "-" && e.Left.Kind == "literal" && e.Left.Value.Kind == "integer" && e.Left.Value.Integer >= 0 {
			return strconv.FormatInt(-e.Left.Value.Integer, 10)
		}
		operand := formatWithin(e.Left, n, 100)
		if e.Op == "-" {
			// -(5) stays parenthesized: -5 would be read as one literal.
			if e.Left.Kind == "literal" {
				return "-(" + operand + ")"
			}
			return "-" + operand
		}
		if e.Op == "~~~" {
			return e.Op + operand
		}
		return e.Op + " " + operand
	case "binary":
		// Operators associate to the left, except **, which associates to
		// the right; comparisons do not chain, so both sides bind tighter.
		prec := syntax.Precedence(e.Op)
		left, right := prec, prec+1
		// and inside or, or or inside and, keeps its parentheses for the
		// reader, though precedence does not need them.
		if e.Op == "or" || e.Op == "and" {
			mixed := func(side *ast.Expr) bool {
				return side.Kind == "binary" && (side.Op == "or" || side.Op == "and") && side.Op != e.Op
			}
			if mixed(e.Left) {
				left = 100
			}
			if mixed(e.Right) {
				right = 100
			}
		}
		switch {
		case e.Op == "**":
			left, right = prec+1, prec
		case prec == syntax.Precedence("=="):
			left = prec + 1
		}
		return formatWithin(e.Left, n, left) + " " + e.Op + " " + formatWithin(e.Right, n, right)
	case "sigil":
		open, shut := "/", "/"
		for _, pair := range []string{"//", "()", "[]", "{}", "||", "\"\""} {
			if !strings.Contains(e.Value.Text, pair[1:]) || pair == "\"\"" {
				open, shut = pair[:1], pair[1:]
				break
			}
		}
		if e.Name != "r" && open == "/" {
			open, shut = "(", ")"
			if strings.Contains(e.Value.Text, ")") {
				open, shut = "[", "]"
			}
		}
		if e.Name == "D" || e.Name == "T" || e.Name == "N" || e.Name == "U" {
			open, shut = "[", "]"
		}
		// A sigil keeps the delimiters it was written with.
		if closer := lexer.SigilCloser(e.Delimiter); closer != "" {
			open, shut = e.Delimiter, closer
		}
		interpolates := e.Name[0] >= 'a' && e.Name[0] <= 'z'
		return "~" + e.Name + open + lexer.SigilEscape(e.Value.Text, shut[0], interpolates) + shut + e.Op
	case "try":
		s := e.Body[0]
		text := "try do\n" + formatBlock(s.Then, n+1)
		for _, kind := range []string{"", "catch", "else"} {
			var arms []ast.Arm
			for _, arm := range s.Arms {
				if arm.Kind == kind {
					arms = append(arms, arm)
				}
			}
			if len(arms) == 0 {
				continue
			}
			if kind == "" {
				kind = "rescue"
			}
			text += indent(n) + kind + "\n" + formatArms(arms, n+1)
		}
		if len(s.Else) > 0 {
			text += indent(n) + "after\n" + formatBlock(s.Else, n+1)
		}
		return text + indent(n) + "end"
	case "for":
		s := e.Body[0]
		parts := []string{}
		for _, arm := range s.Arms {
			part := formatExpr(arm.Guard, n)
			if arm.Pattern != nil {
				part = formatPattern(arm.Pattern) + " <- " + part
			}
			parts = append(parts, part)
		}
		if len(e.Labels) == 1 {
			parts = append(parts, e.Labels[0]+": "+formatExpr(e.Args[0], n))
			if e.Labels[0] == "reduce" {
				return "for " + strings.Join(parts, ", ") + " do\n" + formatArms(s.Then[0].Arms, n+1) + indent(n) + "end"
			}
		}
		if s.Name == "do:" {
			return "for(" + strings.Join(parts, ", ") + ", do: " + formatExpr(s.Then[0].Expr, n) + ")"
		}
		return "for " + strings.Join(parts, ", ") + " do\n" + formatBlock(s.Then, n+1) + indent(n) + "end"
	case "lambda":
		if len(e.Body) == 1 && e.Body[0].Kind == "clauses" {
			return "fn\n" + formatArms(e.Body[0].Arms, n+1) + indent(n) + "end"
		}
		head := "fn " + formatParams(e.Params)
		if len(e.Params) == 0 {
			head = "fn"
		}
		body := formatBlock(e.Body, n+1)
		// A function that is one short expression stays on one line.
		if line := strings.TrimSpace(body); len(e.Body) == 1 && (e.Body[0].Kind == "call" || e.Body[0].Kind == "output") &&
			strings.Count(body, "\n") == 1 && len(head)+len(line)+8 <= 72 {
			return head + " -> " + line + " end"
		}
		return head + " ->\n" + body + indent(n) + "end"
	case "capture":
		return "&(" + formatExpr(e.Left, n) + ")"
	case "range":
		step := ""
		if len(args) == 1 {
			step = "//" + args[0]
		}
		if step != "" {
			step = "//" + formatWithin(e.Args[0], n, syntax.Precedence("+"))
		}
		dots := syntax.Precedence("..")
		return formatWithin(e.Left, n, dots) + ".." + formatWithin(e.Right, n, dots+1) + step
	case "in":
		compare := syntax.Precedence("in")
		return formatWithin(e.Left, n, compare+1) + " in " + formatWithin(e.Right, n, compare+1)
	case "value":
		return strings.TrimSuffix(strings.TrimPrefix(formatBlock(e.Body, n), indent(n)), "\n")
	case "closure":
		return "fn(" + formatParams(e.Params) + "): " + spaced(e.ReturnType) + " do\n" + formatBlock(e.Body, n+1) + indent(n) + "end"
	}
	panic("unknown expression " + e.Kind)
}

// formatOperand renders the target of a postfix call or index. Statements are
// not newline-terminated, so a statement that began with an added "(" would be
// parsed as a call on the end of the previous one. Operators and pipes already
// carry their own parentheses; every other form binds tighter than a postfix.
func formatOperand(e *ast.Expr, n int) string { return formatWithin(e, n, 100) }
func formatPattern(p *ast.Pattern) string {
	switch p.Kind {
	case "name":
		return p.Name
	case "wildcard":
		return "_"
	case "pin":
		return "^" + p.Name
	case "in":
		return p.Name + " in " + p.Type
	case "typed":
		return p.Name + ": " + spaced(p.Type)
	case "literal":
		return formatLiteral(p.Value)
	}
	parts := []string{}
	for _, c := range p.Children {
		parts = append(parts, formatPattern(c))
	}
	switch p.Kind {
	case "struct":
		for i, label := range p.Labels {
			parts[i] = label + ": " + parts[i]
		}
		return "%" + p.Name + "{" + strings.Join(parts, ", ") + "}"
	case "variant":
		if len(parts) == 0 {
			return p.Name
		}
		return p.Name + "(" + strings.Join(parts, ", ") + ")"
	case "map":
		for i, key := range p.Keys {
			parts[i] = formatLiteral(key) + " => " + parts[i]
		}
		return "%{" + strings.Join(parts, ", ") + "}"
	case "tuple":
		return "{" + strings.Join(parts, ", ") + "}"
	default:
		tail := ""
		if p.Tail != nil {
			tail = " | " + formatPattern(p.Tail)
		}
		return "[" + strings.Join(parts, ", ") + tail + "]"
	}
}

// formatPipeline writes a chain of three or more stages one stage to a
// line, each |> under the start of the statement; a shorter chain, or any
// other expression, as formatExpr does.
func formatPipeline(e *ast.Expr, n int) string {
	var stages []*ast.Expr
	first := e
	for first != nil && first.Kind == "call" && first.Pipe && len(first.Args) > 0 {
		stages = append([]*ast.Expr{first}, stages...)
		first = first.Args[0]
	}
	if len(stages) < 2 {
		return formatExpr(e, n)
	}
	text := formatWithin(first, n, syntax.Precedence("|>"))
	for _, stage := range stages {
		args := []string{}
		for _, arg := range stage.Args[1:] {
			args = append(args, formatExpr(arg, n))
		}
		text += "\n" + indent(n) + "|> " + stage.Name + "(" + strings.Join(args, ", ") + ")"
	}
	return text
}

func formatBlock(body []ast.Statement, n int) string {
	var b strings.Builder
	for _, s := range body {
		pad := indent(n)
		e := formatExpr(s.Expr, n)
		if s.Kind == "bind" || s.Kind == "call" || s.Kind == "yield" || s.Kind == "return" {
			e = formatPipeline(s.Expr, n)
		}
		switch s.Kind {
		case "comment":
			b.WriteString(strings.TrimRight(pad+"# "+s.Name, " ") + "\n")
			continue
		case "bind":
			annotation := ""
			if s.Declared != "" {
				annotation = ": " + spaced(s.Declared)
			}
			b.WriteString(pad + formatPattern(s.Pattern) + annotation + " = " + e + "\n")
		case "receive":
			text := s.Name + "(" + formatExpr(s.Expr.Args[0], n) + ", " + formatPattern(s.Pattern)
			if len(s.Arms) > 0 {
				text += " when " + formatExpr(s.Arms[0].Guard, n)
			}
			for _, extra := range s.Expr.Args[1:] {
				text += ", " + formatExpr(extra, n)
			}
			b.WriteString(pad + text + ")\n")
		case "output":
			b.WriteString(pad + "IO.puts(" + e + ")\n")
		case "assert":
			b.WriteString(pad + "assert(" + e + ")\n")
		case "call", "yield":
			b.WriteString(pad + e + "\n")
		case "return":
			b.WriteString(pad + "return " + e + "\n")
		case "if":
			keyword := "if "
			if s.Name == "unless" {
				keyword = "unless "
			}
			if s.Declared == "do:" {
				line := pad + keyword + e + ", do: " + strings.TrimSpace(formatBlock(s.Then, 0))
				if len(s.Else) > 0 {
					line += ", else: " + strings.TrimSpace(formatBlock(s.Else, 0))
				}
				b.WriteString(line + "\n")
				break
			}
			b.WriteString(pad + keyword + e + " do\n" + formatBlock(s.Then, n+1))
			if len(s.Else) > 0 {
				b.WriteString(pad + "else\n" + formatBlock(s.Else, n+1))
			}
			b.WriteString(pad + "end\n")
		case "cond":
			b.WriteString(pad + "cond do\n")
			for _, arm := range s.Arms {
				head := indent(n+1) + formatExpr(arm.Guard, n+1) + " ->"
				body := formatBlock(arm.Body, n+2)
				if line := strings.TrimSpace(body); len(arm.Body) == 1 && (arm.Body[0].Kind == "call" || arm.Body[0].Kind == "output") &&
					strings.Count(body, "\n") == 1 && len(head)+1+len(line) <= 98 {
					b.WriteString(head + " " + line + "\n")
					continue
				}
				b.WriteString(head + "\n" + body)
			}
			b.WriteString(pad + "end\n")
		case "with":
			clauses := []string{}
			for _, arm := range s.Arms {
				clauses = append(clauses, formatPattern(arm.Pattern)+" <- "+formatExpr(arm.Guard, n))
			}
			b.WriteString(pad + "with " + strings.Join(clauses, ",\n"+pad+"     ") + " do\n" + formatBlock(s.Then, n+1))
			if len(s.Else) > 0 {
				b.WriteString(pad + "else\n" + formatArms(s.Else[0].Arms, n+1))
			}
			b.WriteString(pad + "end\n")
		case "case":
			b.WriteString(pad + "case " + e + " do\n" + formatArms(s.Arms, n+1) + pad + "end\n")
		case "check":
			clauses := []string{}
			for _, arm := range s.Arms {
				if arm.Pattern == nil {
					clauses = append(clauses, formatExpr(arm.Guard, n))
				} else {
					clauses = append(clauses, formatPattern(arm.Pattern)+" <- "+formatExpr(arm.Guard, n))
				}
			}
			if s.Expr != nil {
				clauses = append(clauses, "max_runs: "+formatExpr(s.Expr, n))
			}
			b.WriteString(pad + "check all " + strings.Join(clauses, ",\n"+pad+"          ") + " do\n" + formatBlock(s.Then, n+1) + pad + "end\n")
		default:
			panic(fmt.Sprintf("unknown statement %s", s.Kind))
		}
	}
	return b.String()
}

// formatArms renders pattern [when guard] -> body arms at the given depth.
func formatArms(arms []ast.Arm, n int) string {
	var b strings.Builder
	for _, arm := range arms {
		guard := ""
		if arm.Guard != nil {
			guard = " when " + formatExpr(arm.Guard, n)
		}
		head := indent(n) + formatPattern(arm.Pattern) + guard + " ->"
		body := formatBlock(arm.Body, n+1)
		// An arm that is one short expression stays on the line of its
		// pattern.
		if line := strings.TrimSpace(body); len(arm.Body) == 1 && (arm.Body[0].Kind == "call" || arm.Body[0].Kind == "output") &&
			strings.Count(body, "\n") == 1 && len(head)+1+len(line) <= 98 {
			b.WriteString(head + " " + line + "\n")
			continue
		}
		b.WriteString(head + "\n" + body)
	}
	return b.String()
}

// formatTag writes a tag as it is written: "name", or name: value for a tag
// with a value, the value bare when it is a number or boolean.
func formatTag(tag string) string {
	name, value, valued := strings.Cut(tag, ":")
	if !valued {
		return strconv.Quote(tag)
	}
	if _, err := strconv.ParseInt(value, 10, 64); err == nil || value == "true" || value == "false" {
		return name + ": " + value
	}
	return name + ": " + strconv.Quote(value)
}

// formatHeredoc writes a heredoc as it was written, its lines and closing
// quotes indented to depth n. Whatever follows the closing quotes in the
// expression stays on their line, as in """) or """, x).
func formatHeredoc(written string, n int) string {
	lines := strings.Split(written, "\n")
	var b strings.Builder
	b.WriteString(lines[0])
	for _, line := range lines[1:] {
		b.WriteString("\n")
		if line != "" {
			b.WriteString(indent(n) + line)
		}
	}
	return b.String()
}
