package main

import (
	"bytes"
	"testing"
)

func TestNativeByteSourceSpelling(t *testing.T) {
	legacy := "defmodule M do def first(x: list[integer]): integer do Enum.at(x,0,0) end def main() do System.halt(first([255])) end end"
	native := "defmodule M do def first(x: bytes): integer do Enum.at(x,0,0) end def main() do System.halt(first(b[255])) end end"
	want, err := lower(legacy, "")
	if err != nil {
		t.Fatal(err)
	}
	got, err := lower(native, "")
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, want) {
		t.Fatal("byte spelling changed bootstrap IR")
	}
}

func TestSeedByteSyntaxProtectsQuotedContent(t *testing.T) {
	source := "# bytes b[1]\nx: bytes do b[255] end\ns=\"bytes b[2]\"\nbytes_name=1\nb = 2"
	want := "# bytes b[1]\nx: list[integer] do [255] end\ns=\"bytes b[2]\"\nbytes_name=1\nb = 2"
	if got := seedByteSyntax(source); got != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}

func TestSeedByteSyntaxBase64(t *testing.T) {
	source := "x: bytes do Enum.concat(b\"AP8Q\", b\"YQ==\") end\ns=\"b\\\"AP8Q\\\"\""
	want := "x: list[integer] do Enum.concat([0,255,16], [97]) end\ns=\"b\\\"AP8Q\\\"\""
	if got := seedByteSyntax(source); got != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}
