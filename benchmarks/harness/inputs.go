package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// writeInputs creates the input files the suite programs read, so that the
// Alchem, Elixir and Go versions of a case work on identical bytes:
//
//	lines.txt    1,000,000 comma-separated lines, about 64 MiB
//	head.txt     the first 120,000 of those lines, about 8 MiB
//	small.json   one record, about 150 bytes
//	medium.json  an object holding 60 records, about 10 KB
//	large.json   an array of 30,000 records, about 5 MB
func writeInputs(dir string) error {
	if err := writeLines(filepath.Join(dir, "lines.txt"), 1000000); err != nil {
		return err
	}
	if err := writeLines(filepath.Join(dir, "head.txt"), 120000); err != nil {
		return err
	}
	files := map[string]string{
		"small.json":  jsonRecord(1),
		"medium.json": `{"page":1,"total":60,"items":[` + records(60) + `]}`,
		"large.json":  "[" + records(30000) + "]",
	}
	for name, content := range files {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0o644); err != nil {
			return err
		}
	}
	return nil
}

// writeLines writes count lines of the form id,word,value,text. The word
// repeats, so counting words exercises a map; the value is a small integer.
func writeLines(path string, count int) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	out := bufio.NewWriterSize(file, 1<<20)
	for i := 1; i <= count; i++ {
		fmt.Fprintf(out, "%07d,w%05d,%d,the quick brown fox jumps over the lazy dog %d\n", i, i*7919%100003, i*31%997, i%10)
	}
	if err := out.Flush(); err != nil {
		file.Close()
		return err
	}
	return file.Close()
}

// jsonRecord is one JSON object without insignificant whitespace. Its float is
// never whole, so every encoder writes it with the same digits.
func jsonRecord(i int) string {
	return fmt.Sprintf(`{"active":%t,"address":{"city":"City %d","zip":"%05d"},"email":"user%d@example.com","id":%d,"name":"User Number %d","score":%s,"tags":["alpha","beta","t%d"]}`,
		i%2 == 0, i%100, i*7%100000, i, i, i, fmt.Sprintf("%.3f", float64(i)*0.25+0.125), i%10)
}

func records(count int) string {
	var out strings.Builder
	for i := 1; i <= count; i++ {
		if i > 1 {
			out.WriteByte(',')
		}
		out.WriteString(jsonRecord(i))
	}
	return out.String()
}
