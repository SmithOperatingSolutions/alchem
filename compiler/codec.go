package compiler

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

// A message that crosses to another node is encoded on one side and built
// again on the other. The functions that do so are generated per type, from
// the type alone, so no type is examined while the program runs. Structs
// and sum types get named functions, which lets a type refer to itself.

// codec returns a Go expression for the actor.Codec of a type.
func (g *generator) codec(t string) string {
	return "node.Codec[" + goType(t) + "]{Type:" + strconv.Quote(t) + ",Encode:" + g.encoder(t) + ",Decode:" + g.decoder(t) + "}"
}

// named gives a struct or sum type its pair of functions, generated later.
func (g *generator) named(t string) int {
	if g.codecs == nil {
		g.codecs = map[string]int{}
	}
	index, known := g.codecs[t]
	if !known {
		index = len(g.codecOrder)
		g.codecs[t] = index
		g.codecOrder = append(g.codecOrder, t)
	}
	return index
}

func (g *generator) encoder(t string) string {
	head, args := ast.Split(t)
	switch head {
	case "integer":
		return "(*node.Encoder).Int"
	case "float":
		return "(*node.Encoder).Float"
	case "boolean":
		return "(*node.Encoder).Bool"
	case "string":
		return "(*node.Encoder).String"
	case "atom":
		return "(*node.Encoder).Atom"
	case "list":
		return "func(e *node.Encoder,v " + goType(t) + "){e.Int(int64(len(v.S)));each:=" + g.encoder(args[0]) + ";for i:=len(v.S)-1;i>=0;i--{each(e,v.S[i])}}"
	case "tuple":
		body := ""
		for i, part := range args {
			body += fmt.Sprintf("%s(e,v.E%d);", g.encoder(part), i)
		}
		return "func(e *node.Encoder,v " + goType(t) + "){" + body + "}"
	case "map":
		return "func(e *node.Encoder,v " + goType(t) + "){node.EncodeMap(e,v," + g.encoder(args[0]) + "," + g.encoder(args[1]) + ")}"
	case "set":
		return "func(e *node.Encoder,v " + goType(t) + "){node.EncodeMap(e,v," + g.encoder(args[0]) + ",func(*node.Encoder,struct{}){})}"
	case "pid":
		return "func(e *node.Encoder,v " + goType(t) + "){node.EncodePID(e,v," + g.codec(args[0]) + ")}"
	}
	return fmt.Sprintf("encode%d", g.named(t))
}

func (g *generator) decoder(t string) string {
	head, args := ast.Split(t)
	switch head {
	case "integer":
		return "(*node.Decoder).Int"
	case "float":
		return "(*node.Decoder).Float"
	case "boolean":
		return "(*node.Decoder).Bool"
	case "string":
		return "(*node.Decoder).String"
	case "atom":
		return "(*node.Decoder).Atom"
	case "list":
		element := goType(args[0])
		return "func(d *node.Decoder)" + goType(t) + "{n:=d.Length();out:=make([]" + element + ",n);each:=" + g.decoder(args[0]) + ";for i:=range out{out[n-1-i]=each(d)};return L[" + element + "]{S:out}}"
	case "tuple":
		parts := make([]string, len(args))
		for i, part := range args {
			parts[i] = g.decoder(part) + "(d)"
		}
		return "func(d *node.Decoder)" + goType(t) + "{return " + goType(t) + "{" + strings.Join(parts, ",") + "}}"
	case "map":
		return "func(d *node.Decoder)" + goType(t) + "{return node.DecodeMap(d," + g.decoder(args[0]) + "," + g.decoder(args[1]) + ")}"
	case "set":
		return "func(d *node.Decoder)" + goType(t) + "{return node.DecodeMap(d," + g.decoder(args[0]) + ",func(*node.Decoder)struct{}{return struct{}{}})}"
	case "pid":
		return "func(d *node.Decoder)" + goType(t) + "{return node.DecodePID(d," + g.codec(args[0]) + ")}"
	}
	return fmt.Sprintf("decode%d", g.named(t))
}

// substitute replaces a declaration's type parameters by the arguments of
// one use of it.
func substitute(t string, names, values []string) string {
	for i, name := range names {
		if t == name && i < len(values) {
			return values[i]
		}
	}
	head, args := ast.Split(t)
	if len(args) == 0 {
		return t
	}
	for i := range args {
		args[i] = substitute(args[i], names, values)
	}
	return ast.Join(head, args)
}

// codecFunctions emits the functions of every struct and sum type that
// crosses. Generating one may name further types, so the list is walked
// until it stops growing.
func (g *generator) codecFunctions() string {
	var out strings.Builder
	for index := 0; index < len(g.codecOrder); index++ {
		t := g.codecOrder[index]
		head, args := ast.Split(t)
		decl, known := g.decls[head]
		target := goType(t)
		if !known {
			// The checker lets only types with a wire form through.
			panic("no wire form for " + t)
		}
		field := func(parameter ast.Parameter) string { return substitute(parameter.Type, decl.Params, args) }
		if decl.Kind == "struct" {
			encode, parts := "", make([]string, len(decl.Fields))
			for i, parameter := range decl.Fields {
				encode += fmt.Sprintf("%s(e,v.F%d);", g.encoder(field(parameter)), i)
				parts[i] = g.decoder(field(parameter)) + "(d)"
			}
			fmt.Fprintf(&out, "func encode%d(e *node.Encoder,v %s){%s}\n", index, target, encode)
			fmt.Fprintf(&out, "func decode%d(d *node.Decoder)%s{return %s{%s}}\n", index, target, target, strings.Join(parts, ","))
			continue
		}
		encode, decode := "", ""
		for number, variant := range decl.Variants {
			name := variantType(t, number)
			writes, parts := "", make([]string, len(variant.Fields))
			for i, parameter := range variant.Fields {
				writes += fmt.Sprintf("%s(e,x.F%d);", g.encoder(field(parameter)), i)
				parts[i] = g.decoder(field(parameter)) + "(d)"
			}
			encode += fmt.Sprintf("case %s:e.Int(%d);_=x;%s\n", name, number, writes)
			decode += fmt.Sprintf("case %d:return %s(%s{%s})\n", number, target, name, strings.Join(parts, ","))
		}
		fmt.Fprintf(&out, "func encode%d(e *node.Encoder,v %s){switch x:=v.(type){\n%s}}\n", index, target, encode)
		fmt.Fprintf(&out, "func decode%d(d *node.Decoder)%s{switch d.Int(){\n%s};d.Fail();var none %s;return none}\n", index, target, decode, target)
	}
	return out.String()
}
