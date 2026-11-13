package ast

import "strings"

// Program represents one typed module and its executable main/0 body.
type Program struct {
	// Leading and Trailing are the comments before defmodule and before the
	// module's final end. Doctests names the modules whose documented
	// examples a test file runs.
	Leading, Trailing, Doctests []string
	// ModuleDoc is the text of the module's @moduledoc.
	ModuleDoc string
	// Library is set when the module is checked without being built: it
	// may then be one that other files import, with no main.
	Library bool
	// Protocols are the protocols the module declares.
	Protocols []Protocol
	// Macros are the templates the module defines with defmacro, and Uses
	// the modules whose __using__ template it asked for with use.
	Macros []Macro
	Uses   []Use
	// GroupTags holds the tags written above each describe, by its path;
	// the empty path holds the module's own (@moduletag).
	GroupTags map[string][]string
	// Constants are the module's @name value declarations, in source order.
	Constants                []Constant
	Remotes                  []Remote
	Types                    []TypeDecl
	Requires                 []Require
	Imports                  []string
	ImportPositions          []Position
	ModuleLine, ModuleColumn int
	Source                   string
	Functions                []Function
	Statements               []Statement
	Module                   string
	Output                   string
	Comparison               *Comparison
	Assertion                *bool // nil for IO.puts, non-nil for assert(true|false)
}

// Constant is a module constant, @name value: every @name in the module
// stands for the value.
type Constant struct {
	Name         string
	Value        *Expr
	Line, Column int
	// Comments are the comment lines written directly above it.
	Comments []string
}

// Literal holds a validated value; integers use signed 64-bit semantics.
type Literal struct {
	Kind    string
	Integer int64
	Float   float64
	Text    string
	Boolean bool
}
type Comparison struct {
	Left, Right Literal
	Operator    string
}

// Statement represents a typed binding, call, assertion, return, conditional or case.
type Statement struct {
	Pattern      *Pattern
	Declared     string
	Arms         []Arm
	Kind         string
	Name         string
	Expr         *Expr
	Then, Else   []Statement
	Line, Column int
	Output       *string
	Comparison   *Comparison
	Assertion    *bool
}

// Expr carries a source position and the type assigned by semantic analysis.
type Expr struct {
	Pipe                 bool
	Kind, Type, Name, Op string
	Value                Literal
	Left, Right          *Expr
	Args                 []*Expr
	Keys                 []*Expr
	Params               []Parameter
	Body                 []Statement
	ReturnType           string
	// Labels names the fields of a struct literal, in source order. TypeArgs
	// holds the types chosen for a generic function's type variables.
	Labels, TypeArgs []string
	Line, Column     int
	// Heredoc is how a string or sigil written as a heredoc looked, kept
	// when parsing for the formatter; see lexer.Heredoc. Delimiter is the
	// opening delimiter of a one-line sigil, also kept for the formatter.
	Heredoc   string
	Delimiter string
}

// Parameter is a typed name. In a function clause as written it may instead
// carry a pattern, and its type may be left to another clause.
type Parameter struct {
	// Default is the value a call may leave out, written name: type \\\\ value.
	Default      *Expr
	Name, Type   string
	Pattern      *Pattern
	Line, Column int
}

// TypeDecl declares a struct (Fields), a sum type (Variants) or an opaque Go type. Name is the
// qualified name once the module is linked; Params are its type variables.
type TypeDecl struct {
	// Doc is the text of the @typedoc (or @doc) above the declaration, and
	// Comments the comment lines written directly above it.
	Doc                       string
	Comments                  []string
	Kind, Name, Local, Source string
	// Extern, for Kind "extern", is the Go type an opaque handle stands for
	// ("*bytes.Buffer"); ExternDir is its resolved project-local package.
	Extern, ExternDir string
	Params            []string
	// Exception marks a struct declared with defexception: it can be raised,
	// and has a message field.
	Exception    bool
	Fields       []Parameter
	Variants     []Variant
	Line, Column int
}
type Variant struct {
	Name         string
	Fields       []Parameter
	Line, Column int
}

// Remote is one fetched remote package with the hash of its content.
type Remote struct{ Path, Version, Sum string }

// GroupSeparator joins the names of nested describe blocks in Function.Group.
const GroupSeparator = "\x1f"

// Groups splits a describe path into its names, outermost first.
func Groups(group string) []string {
	if group == "" {
		return nil
	}
	return strings.Split(group, GroupSeparator)
}

// Within reports whether a test in group sits inside the describe path outer.
func Within(group, outer string) bool {
	return outer == "" || group == outer || strings.HasPrefix(group, outer+GroupSeparator)
}

// Require pins one Go module that extern declarations may bind to.
type Require struct {
	Path, Version, Source string
	Line, Column          int
}

// Function is a declared function. Extern, when set, names the Go function
// ("import/path.Symbol") it binds to and the body is empty; ExternDir is the
// resolved directory of a project-local Go package.
// Macro is a template: code with holes, written quote do ... end, that
// replaces each call of the macro, with the call's arguments put where the
// template says unquote(parameter). Block names the parameter that takes a
// do ... end block. Definitions holds the functions of a __using__ macro,
// which are added to the module that says use.
type Macro struct {
	Name, Block  string
	Params       []string
	Body         []Statement
	Definitions  []Function
	Line, Column int
}

// Use asks for another module's __using__ template, with a value for each
// of its parameters.
type Use struct {
	Module       string
	Names        []string
	Values       []*Expr
	Line, Column int
}

// Protocol declares functions that types implement separately; a call is
// resolved to the implementation for the type of its first argument.
type Protocol struct {
	Name, Doc    string
	Functions    []ProtocolFunction
	Line, Column int
}

// ProtocolFunction is one function of a protocol: its name, the names of
// its parameters and its result type.
type ProtocolFunction struct {
	Name, Type string
	Params     []string
}

type Function struct {
	// Protocol and ProtocolFunction name what a function written in a
	// defimpl block implements, and For the type it implements it for.
	Protocol, ProtocolFunction, For string
	// Test is the name of a test declared with test "name" do ... end, and
	// Setup marks a setup block. Group is the describe blocks either sits
	// in, outermost first, joined by GroupSeparator; it is empty at the top.
	Test, Group string
	Setup       bool
	// Doc is the text of the @doc above the function, and Comments the
	// comment lines written directly above it.
	Doc      string
	Comments []string
	// Tags are the @tag names written above a test. All marks setup_all,
	// which runs once before the module's tests.
	Tags []string
	All  bool
	// Private functions are declared with defp and callable only in their module.
	Private                   bool
	Extern, ExternDir         string
	Source, Module, LocalName string
	Name, Type                string
	Params                    []Parameter
	Guard                     *Expr
	Body                      []Statement
	Line, Column              int
}

type Pattern struct {
	Kind, Name, Type string
	Value            Literal
	Children         []*Pattern
	// Labels names the fields of a struct pattern; analysis records their
	// positions in Fields, and the matched variant's position in Index.
	Labels       []string
	Fields       []int
	Index        int
	Keys         []Literal
	Tail         *Pattern
	Line, Column int
}
type Arm struct {
	Pattern *Pattern
	Guard   *Expr
	Body    []Statement
	// Kind tells a try's arms apart: "" rescues a failure, "catch" takes a
	// thrown value and "else" the body's value. Type is the type the arm
	// matches, set by analysis.
	Kind, Type string
}

type Position struct{ Line, Column int }
