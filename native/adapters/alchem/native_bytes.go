package main

import (
	"encoding/base64"
	"strconv"
	"strings"
)

// seedByteSyntax translates the native profile's explicit byte spelling for the
// pinned bootstrap frontend. Saved native source and native rebuilds are unchanged.
func seedByteSyntax(source string) string {
	var out strings.Builder
	for i := 0; i < len(source); {
		start := i
		if source[i] == '"' {
			i++
			for i < len(source) {
				c := source[i]
				i++
				if c == '\\' && i < len(source) {
					i++
				} else if c == '"' {
					break
				}
			}
			out.WriteString(source[start:i])
		} else if source[i] == '#' {
			for i < len(source) && source[i] != '\n' && source[i] != '\r' {
				i++
			}
			out.WriteString(source[start:i])
		} else if nativeWordStart(source[i]) {
			i++
			for i < len(source) && (nativeWordStart(source[i]) || source[i] >= '0' && source[i] <= '9') {
				i++
			}
			word := source[start:i]
			if word == "b" && i < len(source) && source[i] == '"' {
				// b"..." holds bytes in base64; the pinned frontend reads them as a list.
				end := strings.IndexByte(source[i+1:], '"')
				if end >= 0 {
					if data, err := base64.StdEncoding.DecodeString(source[i+1 : i+1+end]); err == nil {
						out.WriteByte('[')
						for k, value := range data {
							if k > 0 {
								out.WriteByte(',')
							}
							out.WriteString(strconv.Itoa(int(value)))
						}
						out.WriteByte(']')
						i += end + 2
						continue
					}
				}
				out.WriteString(word)
			} else if word == "bytes" {
				out.WriteString("list[integer]")
			} else if word != "b" || i == len(source) || source[i] != '[' {
				out.WriteString(word)
			}
		} else {
			out.WriteByte(source[i])
			i++
		}
	}
	return out.String()
}

func nativeWordStart(c byte) bool { return c == '_' || c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' }
