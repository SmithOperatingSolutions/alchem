package compiler

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
)

// JSON.decode_as builds a value of the type its result is annotated with.
// The function that does so is generated from the type alone, as the codecs
// of messages are, and reads what JSON.encode writes for that type: a struct
// from an object by field name, a variant from its name or from
// {"name": [fields]}, lists, sets and tuples from arrays, a map from an
// object, none from null. Each takes the path to the value it reads, so
// that an error can say where the JSON did not fit.

// reader returns a Go expression of type func(TJSON, string) (T, error).
func (g *generator) reader(t string) string {
	head, args := ast.Split(t)
	switch head {
	case "integer":
		return "jsonAsInteger"
	case "float":
		return "jsonAsFloat"
	case "boolean":
		return "jsonAsBoolean"
	case "string":
		return "jsonAsString"
	case "atom":
		return "jsonAsAtom"
	case "JSON":
		return "jsonAsJSON"
	case "list":
		return "jsonAsList(" + g.reader(args[0]) + ")"
	case "set":
		return "jsonAsSet(" + g.reader(args[0]) + ")"
	case "option":
		return "jsonAsOption(" + g.reader(args[0]) + ")"
	case "map":
		key := map[string]string{"string": "jsonKeyString", "atom": "jsonKeyAtom", "integer": "jsonKeyInteger", "float": "jsonKeyFloat", "boolean": "jsonKeyBoolean"}[args[0]]
		return "jsonAsMap(" + key + "," + g.reader(args[1]) + ")"
	case "tuple":
		target := goType(t)
		body := ""
		for i, part := range args {
			body += fmt.Sprintf("if out.E%d,err=%s(items[%d],jsonIndex(path,%d));err!=nil{return out,err};", i, g.reader(part), i, i)
		}
		return "func(v TJSON,path string)(" + target + ",error){var out " + target + ";items,err:=jsonItems(v,path," + strconv.Itoa(len(args)) + ");_=items;if err!=nil{return out,err};" + body + "return out,nil}"
	}
	if ast.TypeVariable(t) {
		// A type the function was called with: its caller supplied this.
		return readerName(t)
	}
	if g.readers == nil {
		g.readers = map[string]int{}
	}
	index, known := g.readers[head]
	if !known {
		index = len(g.readerOrder)
		g.readers[head] = index
		g.readerOrder = append(g.readerOrder, head)
	}
	if len(args) == 0 {
		return fmt.Sprintf("jsonAs%d", index)
	}
	// A generic type has one function for all its uses, which takes how
	// each of its parameters is read.
	call := fmt.Sprintf("jsonAs%d(v,path", index)
	for _, arg := range args {
		call += "," + g.reader(arg)
	}
	return "func(v TJSON,path string)(" + goType(t) + ",error){return " + call + ")}"
}

// readerName is the parameter that reads a type variable.
func readerName(variable string) string { return "jsonRead_" + variable }

// readerType is the Go type of a function reading a type.
func readerType(t string) string { return "func(TJSON,string)(" + goType(t) + ",error)" }

// readersFor gives the readers a call or reference to a function passes
// after its arguments: one for each type variable the function reads, for
// the type chosen here.
func (g *generator) readersFor(name string, typeArgs []string) []string {
	def := g.defs[name]
	if def == nil || len(def.Reads) == 0 {
		return nil
	}
	var out []string
	for i, variable := range syntax.Generic(def) {
		for _, read := range def.Reads {
			if read == variable && i < len(typeArgs) {
				out = append(out, g.reader(typeArgs[i]))
			}
		}
	}
	return out
}

// readerFunctions emits the function of every struct and sum type read
// from JSON. Generating one may name further types, so the list is walked
// until it stops growing.
func (g *generator) readerFunctions() string {
	var out strings.Builder
	for index := 0; index < len(g.readerOrder); index++ {
		head := g.readerOrder[index]
		decl, known := g.decls[head]
		if !known {
			// The checker lets only types with a JSON form through.
			panic("no JSON form for " + head)
		}
		t := ast.Join(head, decl.Params)
		target := goType(t)
		field := func(parameter ast.Parameter) string { return parameter.Type }
		extra := ""
		for _, parameter := range decl.Params {
			extra += "," + readerName(parameter) + " " + readerType(parameter)
		}
		fmt.Fprintf(&out, "func jsonAs%d%s(v TJSON,path string%s)(%s,error){\n", index, typeParameters(decl.Params), extra, target)
		if decl.Kind == "struct" {
			fmt.Fprintf(&out, "var out %s\nfields,err:=jsonFields(v,path,%s)\nif err!=nil{return out,err}\n", target, strconv.Quote(decl.Local))
			for i, parameter := range decl.Fields {
				optional, _ := ast.Split(field(parameter))
				fmt.Fprintf(&out, "if member,at,err:=jsonMember(fields,path,%s,%t);err!=nil{return out,err}else if out.F%d,err=%s(member,at);err!=nil{return out,err}\n",
					strconv.Quote(parameter.Name), optional == "option", i, g.reader(field(parameter)))
			}
			out.WriteString("return out,nil}\n")
			continue
		}
		names := make([]string, len(decl.Variants))
		for i, variant := range decl.Variants {
			names[i] = variant.Name
		}
		fmt.Fprintf(&out, "var none %s\nname,items,err:=jsonVariant(v,path,%s)\nif err!=nil{return none,err}\nswitch name{\n", target, strconv.Quote(strings.Join(names, ", ")))
		for number, variant := range decl.Variants {
			fmt.Fprintf(&out, "case %s:\nif err:=jsonCount(items,path,name,%d);err!=nil{return none,err}\nvar out %s\n", strconv.Quote(variant.Name), len(variant.Fields), variantType(t, number))
			for i, parameter := range variant.Fields {
				fmt.Fprintf(&out, "if out.F%d,err=%s(items[%d],jsonIndex(jsonName(path,name),%d));err!=nil{return none,err}\n", i, g.reader(field(parameter)), i, i)
			}
			fmt.Fprintf(&out, "return %s(out),nil\n", target)
		}
		fmt.Fprintf(&out, "}\nreturn none,jsonUnknown(path,%s,name)}\n", strconv.Quote(strings.Join(names, ", ")))
	}
	return out.String()
}
