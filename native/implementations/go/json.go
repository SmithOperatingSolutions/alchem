package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
)

// Check object keys before decoding into structs, which otherwise accepts case
// aliases and overwrites duplicate fields. Compare decoded keys so escaped
// spellings of the same name cannot bypass the check.
func validateJSONKeys(input []byte) error {
	d := json.NewDecoder(bytes.NewReader(input))
	d.UseNumber()
	var value func() error
	value = func() error {
		token, err := d.Token()
		if err != nil {
			return err
		}
		switch token {
		case json.Delim('{'):
			seen := map[string]bool{}
			for d.More() {
				token, err := d.Token()
				if err != nil {
					return err
				}
				key, ok := token.(string)
				if !ok {
					return fmt.Errorf("expected object key")
				}
				if seen[key] {
					return fmt.Errorf("duplicate object key %q", key)
				}
				seen[key] = true
				// Typed decoding below enforces each object's particular field set.
				switch key {
				case "version", "functions", "name", "params", "return_type", "blocks", "label", "instructions", "terminator", "op", "dest", "value", "lhs", "rhs", "callee", "args", "type", "cond", "then", "else", "values", "buffer", "index", "default", "stream", "limit", "arena_bytes", "count":
				default:
					return fmt.Errorf("unknown or incorrectly cased field %q", key)
				}
				if err := value(); err != nil {
					return err
				}
			}
			_, err = d.Token()
			return err
		case json.Delim('['):
			for d.More() {
				if err := value(); err != nil {
					return err
				}
			}
			_, err = d.Token()
			return err
		}
		return nil
	}
	if err := value(); err != nil {
		return err
	}
	if _, err := d.Token(); err != io.EOF {
		return fmt.Errorf("expected exactly one JSON document")
	}
	return nil
}
