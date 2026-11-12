// Go ceiling for benchmarks/alchem/suite/json.alc, decoding into and encoding
// from untyped values with encoding/json, as the Alchem JSON type is untyped.
package main

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

func read(dir, name string) []byte {
	data, err := os.ReadFile(filepath.Join(dir, name))
	if err != nil {
		panic(err)
	}
	return data
}

func decode(data []byte) any {
	var value any
	if err := json.Unmarshal(data, &value); err != nil {
		panic(err)
	}
	return value
}

func encode(value any) []byte {
	data, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	return data
}

func width(value any) int {
	switch v := value.(type) {
	case []any:
		return len(v)
	case map[string]any:
		return len(v)
	}
	return 0
}

func main() {
	inputs := os.Args[1]
	small, medium, large := read(inputs, "small.json"), read(inputs, "medium.json"), read(inputs, "large.json")
	smallValue, mediumValue, largeValue := decode(small), decode(medium), decode(large)

	repeat := func(times int, work func() int) func() int {
		return func() int {
			total := 0
			for i := 0; i < times; i++ {
				total += work()
			}
			return total
		}
	}
	bench.Run("json.decode 159 B, 10,000 times", repeat(10000, func() int { return width(decode(small)) }))
	bench.Run("json.decode 10 KB, 200 times", repeat(200, func() int { return width(decode(medium)) }))
	bench.Run("json.decode 5 MB", func() int { return width(decode(large)) })
	bench.Run("json.encode 159 B, 10,000 times", repeat(10000, func() int { return len(encode(smallValue)) }))
	bench.Run("json.encode 10 KB, 200 times", repeat(200, func() int { return len(encode(mediumValue)) }))
	bench.Run("json.encode 5 MB", func() int { return len(encode(largeValue)) })
}
