package lexer

import (
	"fmt"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

type Kind string

const Assign Kind = "="
const (
	LBracket Kind = "["
	RBracket Kind = "]"
	LBrace   Kind = "{"
	RBrace   Kind = "}"
	Arrow    Kind = "->"
	Bar      Kind = "|"
	MapStart Kind = "%{"
	Pair     Kind = "=>"
	Amp      Kind = "&"
	Dot      Kind = "."
	// Sigil is ~X followed by delimited text and modifier letters; its text is
	// the letter, the content and the modifiers, separated by NUL.
	Sigil Kind = "sigil"
	At    Kind = "@"
	// StructStart is "%" directly followed by a type name; its text is the name.
	StructStart Kind = "%Name"
	Caret       Kind = "^"
	// Default is the \\\\ that introduces a parameter's default value.
	Default Kind = "\\\\"
)

const (
	Integer Kind = "integer"
	Float   Kind = "float"
	// Template is a string literal containing #{...} interpolation; its text
	// is the raw literal.
	Template Kind = "template"
	Operator Kind = "operator"
	EOF      Kind = "EOF"
	Ident    Kind = "identifier"
	String   Kind = "string"
	LParen   Kind = "("
	RParen   Kind = ")"
	Comma    Kind = ","
	Colon    Kind = ":"
	// Atom is :name; its text is the name.
	Atom Kind = "atom"
)

type Token struct {
	Kind         Kind
	Text         string
	Line, Column int
}

func Scan(source string) ([]Token, error) {
	tokens, _, err := ScanWithComments(source)
	return tokens, err
}

// sigilClosers pairs each delimiter a sigil may open with the one closing it.
var sigilClosers = map[byte]byte{'/': '/', '|': '|', '"': '"', '\'': '\'', '(': ')', '[': ']', '{': '}', '<': '>'}

// ScanWithComments also returns the comments, each a token whose text is the
// comment without its leading "#" and one following space.
func ScanWithComments(source string) ([]Token, []Token, error) {
	tokens, comments, err := scan(source)
	return tokens, comments, err
}

func scan(source string) ([]Token, []Token, error) {
	var comments []Token
	tokens, err := func() ([]Token, error) {
		tokens := make([]Token, 0)
		line, col := 1, 1
		for i := 0; i < len(source); {
			r, size := utf8.DecodeRuneInString(source[i:])
			if r == utf8.RuneError && size == 1 {
				return nil, fmt.Errorf("%d:%d: invalid UTF-8", line, col)
			}
			if r == '\n' {
				line++
				col = 1
				i += size
				continue
			}
			if unicode.IsSpace(r) {
				col++
				i += size
				continue
			}
			startLine, startCol := line, col
			if r == '#' {
				// A comment runs to the end of its line.
				end := strings.IndexByte(source[i:], '\n')
				if end < 0 {
					end = len(source) - i
				}
				comments = append(comments, Token{Kind("comment"), strings.TrimPrefix(strings.TrimRight(source[i+1:i+end], " \t\r"), " "), line, col})
				i += end
				continue
			}
			if r == '~' && i+4 < len(source) && unicode.IsLetter(rune(source[i+1])) && strings.HasPrefix(source[i+2:], `"""`) {
				// A sigil heredoc: ~S""" is literal text, ~s""" a string
				// with escapes, and any other letter its sigil over the text.
				text, next, lines, _, err := heredoc(source, i+2, startLine, startCol)
				if err != nil {
					return nil, err
				}
				letter := source[i+1 : i+2]
				switch letter {
				case "S":
					tokens = append(tokens, Token{String, strconv.Quote(text), startLine, startCol})
				case "s":
					token, err := heredocString(text, startLine, startCol)
					if err != nil {
						return nil, err
					}
					tokens = append(tokens, token)
				default:
					modifiers := next
					for modifiers < len(source) && (source[modifiers] >= 'a' && source[modifiers] <= 'z' || source[modifiers] == 'U') {
						modifiers++
					}
					tokens = append(tokens, Token{Sigil, letter + "\x00" + text + "\x00" + source[next:modifiers], startLine, startCol})
					next = modifiers
				}
				line += lines
				col = utf8.RuneCountInString(source[strings.LastIndex(source[:next], "\n")+1:next]) + 1
				i = next
				continue
			}
			if r == '~' && i+2 < len(source) && unicode.IsLetter(rune(source[i+1])) && sigilClosers[source[i+2]] != 0 {
				// ~r/.../i: a letter, delimited text, then optional modifier letters.
				closer := sigilClosers[source[i+2]]
				end := i + 3
				for ; end < len(source) && source[end] != closer; end++ {
					if source[end] == '\n' {
						return nil, fmt.Errorf("%d:%d: newline in sigil", line, col)
					}
					if source[end] == '\\' && end+1 < len(source) {
						end++
					}
				}
				if end >= len(source) {
					return nil, fmt.Errorf("%d:%d: unterminated sigil", line, col)
				}
				modifiers := end + 1
				for modifiers < len(source) && (source[modifiers] >= 'a' && source[modifiers] <= 'z' || source[modifiers] == 'U') {
					modifiers++
				}
				content := strings.ReplaceAll(source[i+3:end], "\\"+string(closer), string(closer))
				tokens = append(tokens, Token{Sigil, source[i+1:i+2] + "\x00" + content + "\x00" + source[end+1:modifiers], line, col})
				col += utf8.RuneCountInString(source[i:modifiers])
				i = modifiers
				continue
			}
			if r == '@' {
				tokens = append(tokens, Token{At, "@", line, col})
				i += size
				col++
				continue
			}
			if r >= '0' && r <= '9' {
				start := i
				// 0x, 0o and 0b introduce hexadecimal, octal and binary
				// integers.
				if r == '0' && i+2 < len(source) && strings.IndexByte("xob", source[i+1]) >= 0 {
					valid := map[byte]string{'x': "0123456789abcdefABCDEF", 'o': "01234567", 'b': "01"}[source[i+1]]
					end := i + 2
					for end < len(source) && (strings.IndexByte(valid, source[end]) >= 0 || source[end] == '_' && end+1 < len(source) && strings.IndexByte(valid, source[end+1]) >= 0) {
						end++
					}
					if end > i+2 {
						tokens = append(tokens, Token{Integer, source[i:end], startLine, startCol})
						col += end - i
						i = end
						continue
					}
				}
				digits := i
				// An underscore between digits separates them: 1_000_000.
				for i < len(source) && (source[i] >= '0' && source[i] <= '9' || source[i] == '_' && i+1 < len(source) && source[i+1] >= '0' && source[i+1] <= '9') {
					i++
					col++
				}
				if i == digits {
					return nil, fmt.Errorf("%d:%d: expected integer digits", startLine, startCol)
				}
				kind := Integer
				digit := func(at int) bool { return at < len(source) && source[at] >= '0' && source[at] <= '9' }
				if i < len(source) && source[i] == '.' && digit(i+1) {
					kind = Float
					for i++; digit(i); i++ {
					}
					if exponent := i + 1; i < len(source) && source[i] == 'e' {
						if exponent < len(source) && (source[exponent] == '+' || source[exponent] == '-') {
							exponent++
						}
						if digit(exponent) {
							for i = exponent; digit(i); i++ {
							}
						}
					}
					col = startCol + i - start
				}
				tokens = append(tokens, Token{kind, source[start:i], startLine, startCol})
				continue
			}
			if r == '%' && i+1 < len(source) {
				if next, _ := utf8.DecodeRuneInString(source[i+1:]); unicode.IsUpper(next) {
					start := i + 1
					for i++; i < len(source); {
						next, n := utf8.DecodeRuneInString(source[i:])
						if !unicode.IsLetter(next) && !unicode.IsDigit(next) && next != '_' && next != '.' {
							break
						}
						i += n
						col++
					}
					col++
					tokens = append(tokens, Token{StructStart, source[start:i], startLine, startCol})
					continue
				}
			}
			// Bitwise operators, as in Elixir's Bitwise module.
			if i+2 < len(source) {
				switch three := source[i : i+3]; three {
				case "&&&", "|||", "^^^", "<<<", ">>>", "~~~":
					tokens = append(tokens, Token{Operator, three, line, col})
					i += 3
					col += 3
					continue
				}
			}
			// Two-character operators. "&&", "||" and a prefix "!" are spellings
			// of and, or and not.
			if i+1 < len(source) {
				two := source[i : i+2]
				if text, ok := map[string]string{"..": "..", "++": "++", "--": "--", "**": "**", "//": "//", "&&": "and", "||": "or", "<-": "<-", "=~": "=~"}[two]; ok {
					tokens = append(tokens, Token{Operator, text, line, col})
					i += 2
					col += 2
					continue
				}
			}
			if r == '!' && (i+1 >= len(source) || source[i+1] != '=') {
				tokens = append(tokens, Token{Operator, "not", line, col})
				i += size
				col++
				continue
			}
			if r == '.' {
				tokens = append(tokens, Token{Dot, ".", line, col})
				i += size
				col++
				continue
			}
			if strings.HasPrefix(source[i:], "%{") || strings.HasPrefix(source[i:], "=>") {
				kind := MapStart
				if source[i:i+2] == "=>" {
					kind = Pair
				}
				tokens = append(tokens, Token{kind, source[i : i+2], line, col})
				i += 2
				col += 2
				continue
			}
			if r == '^' {
				tokens = append(tokens, Token{Caret, "^", line, col})
				i += size
				col++
				continue
			}
			if r == '&' {
				tokens = append(tokens, Token{Amp, "&", line, col})
				i += size
				col++
				continue
			}
			if strings.HasPrefix(source[i:], "\\\\") {
				tokens = append(tokens, Token{Default, "\\\\", line, col})
				i += 2
				col += 2
				continue
			}
			if r == ':' && i+1 < len(source) && atomStart(source[i+1]) && (i == 0 || !atomBefore(source[i-1])) {
				// :name is an atom unless the colon follows a name or a
				// closing bracket, where it introduces a type or a value.
				end := i + 2
				for end < len(source) && (atomStart(source[end]) || source[end] >= '0' && source[end] <= '9') {
					end++
				}
				if end < len(source) && (source[end] == '?' || source[end] == '!') {
					end++
				}
				tokens = append(tokens, Token{Atom, source[i+1 : end], line, col})
				col += end - i
				i = end
				continue
			}
			if strings.HasPrefix(source[i:], "<>") {
				// String concatenation; checked before the comparison operators.
				tokens = append(tokens, Token{Operator, "<>", line, col})
				i += 2
				col += 2
				continue
			}
			if strings.HasPrefix(source[i:], "->") || strings.HasPrefix(source[i:], "|>") {
				text := source[i : i+2]
				kind := Operator
				if text == "->" {
					kind = Arrow
				}
				tokens = append(tokens, Token{kind, text, line, col})
				i += 2
				col += 2
				continue
			}
			if kind, ok := map[rune]Kind{'[': LBracket, ']': RBracket, '{': LBrace, '}': RBrace, '|': Bar}[r]; ok {
				tokens = append(tokens, Token{kind, string(r), line, col})
				i += size
				col++
				continue
			}
			if strings.ContainsRune("+-*/%", r) {
				tokens = append(tokens, Token{Operator, string(r), line, col})
				i += size
				col++
				continue
			}
			if r == '=' || r == '!' || r == '<' || r == '>' {
				start := i
				i++
				col++
				if i < len(source) && source[i] == '=' {
					i++
					col++
				}
				op := source[start:i]
				if op == "=" {
					tokens = append(tokens, Token{Assign, op, startLine, startCol})
					continue
				}
				if op == "!" {
					return nil, fmt.Errorf("%d:%d: unsupported operator %q", startLine, startCol, op)
				}
				tokens = append(tokens, Token{Operator, op, startLine, startCol})
				continue
			}
			if unicode.IsLetter(r) || r == '_' {
				start := i
				for i < len(source) {
					next, n := utf8.DecodeRuneInString(source[i:])
					if !unicode.IsLetter(next) && !unicode.IsDigit(next) && next != '_' && next != '.' {
						break
					}
					// ".." is the range operator, not part of a qualified name.
					if next == '.' && strings.HasPrefix(source[i:], "..") {
						break
					}
					i += n
					col++
				}
				// A name may end in ? or !, as in Enum.empty? and Map.fetch!.
				if i < len(source) && (source[i] == '?' || (source[i] == '!' && (i+1 >= len(source) || source[i+1] != '='))) && source[i-1] != '.' {
					i++
					col++
				}
				tokens = append(tokens, Token{Ident, source[start:i], startLine, startCol})
				continue
			}
			if strings.HasPrefix(source[i:], `"""`) {
				// A heredoc: text up to a line holding only the closing
				// quotes, with escapes and interpolation as in a string. The
				// closing line's indentation is removed from every line.
				text, next, lines, _, err := heredoc(source, i, startLine, startCol)
				if err != nil {
					return nil, err
				}
				token, err := heredocString(text, startLine, startCol)
				if err != nil {
					return nil, err
				}
				tokens = append(tokens, token)
				line += lines
				col = utf8.RuneCountInString(source[strings.LastIndex(source[:next], "\n")+1:next]) + 1
				i = next
				continue
			}
			if r == '"' {
				end, interpolated, problem := StringEnd(source, i)
				if problem != "" {
					return nil, fmt.Errorf("%d:%d: %s", startLine, startCol, problem)
				}
				raw := source[i:end]
				col += utf8.RuneCountInString(raw)
				i = end
				if interpolated {
					tokens = append(tokens, Token{Template, raw, startLine, startCol})
					continue
				}
				written := raw
				raw = Unescape(raw)
				if _, err := strconv.Unquote(raw); err != nil {
					if problem := StringProblem(written); problem != "" {
						return nil, fmt.Errorf("%d:%d: %s", startLine, startCol, problem)
					}
					return nil, fmt.Errorf("%d:%d: invalid string: %w", startLine, startCol, err)
				}
				tokens = append(tokens, Token{String, raw, startLine, startCol})
				continue
			}
			kind := Kind("")
			if r == '(' {
				kind = LParen
			}
			if r == ')' {
				kind = RParen
			}
			if r == ',' {
				kind = Comma
			}
			if r == ':' {
				kind = Colon
			}
			if kind == "" {
				return nil, fmt.Errorf("%d:%d: unexpected character %q", line, col, r)
			}
			tokens = append(tokens, Token{kind, string(r), line, col})
			i += size
			col++
		}
		tokens = append(tokens, Token{EOF, "", line, col})
		return tokens, nil
	}()
	return tokens, comments, err
}

// StringEnd finds the end of the string literal opening at source[start]. An
// unescaped #{ begins an interpolated expression that runs to its matching }
// and may itself contain strings.
func StringEnd(source string, start int) (end int, interpolated bool, problem string) {
	for i := start + 1; i < len(source); {
		r, size := utf8.DecodeRuneInString(source[i:])
		switch {
		case r == utf8.RuneError && size == 1:
			return 0, false, "invalid UTF-8"
		case r == '\n':
			return 0, false, "newline in string"
		case r == '\\':
			i += size
			if i < len(source) {
				_, size = utf8.DecodeRuneInString(source[i:])
			}
		case r == '"':
			return i + 1, interpolated, ""
		case r == '#' && i+1 < len(source) && source[i+1] == '{':
			interpolated = true
			closing, problem := InterpolationEnd(source, i)
			if problem != "" {
				return 0, false, problem
			}
			i = closing + 1
			continue
		}
		i += size
	}
	return 0, false, "unterminated string"
}

// Unescape removes the backslash from \#, which only exists to keep #{ literal.
func Unescape(raw string) string {
	var out strings.Builder
	for i := 0; i < len(raw); i++ {
		if raw[i] == '\\' && i+1 < len(raw) {
			// Elixir's \u{...}, a code point of any length, which Go spells
			// \U and eight digits.
			if code, size, ok := bracedCodePoint(raw[i:]); ok {
				fmt.Fprintf(&out, `\U%08X`, code)
				i += size - 1
				continue
			}
			// Elixir's \e (escape) and \s (space), which Go spells otherwise.
			switch raw[i+1] {
			case 'e':
				out.WriteString(`\x1b`)
				i++
				continue
			case 's':
				out.WriteByte(' ')
				i++
				continue
			}
			if raw[i+1] != '#' {
				out.WriteByte(raw[i])
			}
			i++
		}
		out.WriteByte(raw[i])
	}
	return out.String()
}

// bracedCodePoint reads \u{...} at the start of text: one to six hex
// digits naming a Unicode code point. size is the escape's length.
func bracedCodePoint(text string) (code rune, size int, ok bool) {
	if !strings.HasPrefix(text, `\u{`) {
		return 0, 0, false
	}
	end := strings.IndexByte(text, '}')
	if end < 4 || end > 9 {
		return 0, 0, false
	}
	value, err := strconv.ParseUint(text[3:end], 16, 32)
	if err != nil || value > unicode.MaxRune || value >= 0xD800 && value <= 0xDFFF {
		return 0, 0, false
	}
	return rune(value), end + 1, true
}

// StringProblem explains why the quoted text raw is not a valid string: the
// first escape it does not take, and the escapes there are. It is "" when
// the fault is not an escape.
func StringProblem(raw string) string {
	for i := 0; i+1 < len(raw); i++ {
		if raw[i] != '\\' {
			continue
		}
		escape := raw[i : i+2]
		valid := true
		switch c := raw[i+1]; c {
		case 'a', 'b', 'f', 'n', 'r', 't', 'v', '\\', '"', '\'', 'e', 's', '#':
		case '0', '1', '2', '3', '4', '5', '6', '7':
			valid = i+3 < len(raw) && octal(raw[i+2]) && octal(raw[i+3])
			escape = raw[i:min(len(raw)-1, i+4)]
		case 'x':
			valid = i+3 < len(raw) && hex(raw[i+2]) && hex(raw[i+3])
			escape = raw[i:min(len(raw)-1, i+4)]
		case 'u', 'U':
			if _, size, ok := bracedCodePoint(raw[i:]); ok {
				i += size - 1
				continue
			}
			digits := 4
			if c == 'U' {
				digits = 8
			}
			// The text ends with its closing quote, which is no part of
			// an escape.
			end := min(len(raw)-1, i+2+digits)
			if c == 'u' && strings.HasPrefix(raw[i:], `\u{`) {
				if close := strings.IndexByte(raw[i:], '}'); close > 0 {
					end = i + close + 1
				}
			}
			escape = raw[i:end]
			valid = false
			if !strings.HasPrefix(raw[i:], `\u{`) && end-i == 2+digits {
				value, err := strconv.ParseUint(raw[i+2:end], 16, 32)
				valid = err == nil && value <= unicode.MaxRune && (value < 0xD800 || value > 0xDFFF)
			}
		default:
			valid = false
		}
		if !valid {
			return "invalid escape " + escape + "; a string takes \\n, \\t, \\r, \\e, \\s, \\\\, \\\", \\#, \\xHH (a byte), \\uHHHH, \\UHHHHHHHH and \\u{H...} (a Unicode code point)"
		}
		i++
	}
	return ""
}

func octal(c byte) bool { return c >= '0' && c <= '7' }

func hex(c byte) bool { return c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F' }

// InterpolationEnd returns the index of the } that closes the #{ at
// source[start]; nested strings and braces are skipped.
func InterpolationEnd(source string, start int) (int, string) {
	depth := 1
	for i := start + 2; i < len(source); i++ {
		switch source[i] {
		case '"':
			inner, _, problem := StringEnd(source, i)
			if problem != "" {
				return 0, problem
			}
			i = inner - 1
		case '\n':
			return 0, "newline in string"
		case '{':
			depth++
		case '}':
			if depth--; depth == 0 {
				return i, ""
			}
		}
	}
	return 0, "unterminated string"
}

func atomStart(c byte) bool {
	return c == '_' || c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z'
}

// atomBefore reports a character after which a colon is not the start of
// an atom: the end of a name, a number or a bracketed form.
func atomBefore(c byte) bool {
	return atomStart(c) || c >= '0' && c <= '9' || c == ')' || c == ']' || c == '}' || c == '?' || c == '!' || c == '"' || c >= 0x80
}

// heredoc reads a heredoc whose opening quotes are at start: its text, with
// the indentation of the closing quotes removed from every line, where the source
// goes on after it, how many lines it spans and the closing indentation.
func heredoc(source string, start, line, col int) (string, int, int, string, error) {
	body := strings.Index(source[start:], "\n")
	end := -1
	if body >= 0 && strings.TrimSpace(source[start+3:start+body]) == "" {
		for at := start + body + 1; at <= len(source); {
			stop := strings.Index(source[at:], "\n")
			if stop < 0 {
				stop = len(source) - at
			}
			// The closing quotes begin their line; the expression the
			// heredoc is part of may go on after them, as in """) or """, x).
			if strings.HasPrefix(strings.TrimLeft(source[at:at+stop], " \t"), `"""`) {
				end = at
				break
			}
			if at+stop >= len(source) {
				break
			}
			at += stop + 1
		}
	}
	if end < 0 {
		return "", 0, 0, "", fmt.Errorf("%d:%d: a heredoc starts with \"\"\" at the end of a line and ends with \"\"\" at the start of a later line", line, col)
	}
	closing := source[end : end+strings.Index(source[end:], `"""`)]
	var text strings.Builder
	for _, textLine := range strings.SplitAfter(source[start+body+1:end], "\n") {
		text.WriteString(strings.TrimPrefix(textLine, closing))
	}
	return text.String(), end + len(closing) + 3, strings.Count(source[start:end], "\n"), closing, nil
}

// heredocString makes the token of a heredoc's text read as a string:
// escapes apply and #{...} interpolates, while quotes and line breaks are
// part of the text.
func heredocString(text string, line, col int) (Token, error) {
	var raw strings.Builder
	raw.WriteByte('"')
	interpolated := false
	for i := 0; i < len(text); i++ {
		switch c := text[i]; {
		case c == '\\' && i+1 < len(text):
			raw.WriteByte(c)
			raw.WriteByte(text[i+1])
			i++
		case c == '#' && i+1 < len(text) && text[i+1] == '{':
			end, problem := InterpolationEnd(`"`+text[i:]+`"`, 1)
			if problem != "" {
				return Token{}, fmt.Errorf("%d:%d: %s", line, col, problem)
			}
			raw.WriteString(text[i : i+end])
			i += end - 1
			interpolated = true
		case c == '"':
			raw.WriteString(`\"`)
		case c == '\n':
			raw.WriteString(`\n`)
		case c == '\r':
			raw.WriteString(`\r`)
		case c == '\t':
			raw.WriteString(`\t`)
		default:
			raw.WriteByte(c)
		}
	}
	raw.WriteByte('"')
	if interpolated {
		return Token{Template, raw.String(), line, col}, nil
	}
	unescaped := Unescape(raw.String())
	if _, err := strconv.Unquote(unescaped); err != nil {
		if problem := StringProblem(raw.String()); problem != "" {
			return Token{}, fmt.Errorf("%d:%d: %s", line, col, problem)
		}
		return Token{}, fmt.Errorf("%d:%d: invalid string: %w", line, col, err)
	}
	return Token{String, unescaped, line, col}, nil
}

// Heredoc reports how the string or sigil at offset in source is written
// when it is a heredoc: the opening quotes with any sigil letter, a
// newline, its lines with the closing indentation removed, and the closing
// quotes with any modifiers. ok is false for anything else.
func Heredoc(source string, offset int) (written string, ok bool) {
	open := `"""`
	quotes := offset
	if strings.HasPrefix(source[offset:], "~") && offset+2 < len(source) {
		open = source[offset:offset+2] + `"""`
		quotes = offset + 2
	}
	if !strings.HasPrefix(source[offset:], open) {
		return "", false
	}
	text, next, _, _, err := heredoc(source, quotes, 0, 0)
	if err != nil {
		return "", false
	}
	modifiers := next
	if open != `"""` {
		for modifiers < len(source) && (source[modifiers] >= 'a' && source[modifiers] <= 'z' || source[modifiers] == 'U') {
			modifiers++
		}
	}
	return open + "\n" + text + `"""` + source[next:modifiers], true
}

// SigilCloser is the delimiter that closes a one-line sigil opened with
// open, or "" when open is not a sigil delimiter.
func SigilCloser(open string) string {
	if len(open) != 1 || sigilClosers[open[0]] == 0 {
		return ""
	}
	return string(sigilClosers[open[0]])
}
