// Go ceiling for benchmarks/alchem/suite/control.alc: comprehensions become
// loops, result values become (value, error) returns and rescued failures
// become recovered panics.
package main

import (
	"errors"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

type shape struct{ kind, a, b int }

var errTen = errors.New("multiple of ten")

func step(n int) (int, error) {
	if n%10 == 0 {
		return 0, errTen
	}
	return n + 1, nil
}

func chain(n int) int {
	first, err := step(n)
	if err != nil {
		return len(err.Error())
	}
	second, err := step(first)
	if err != nil {
		return len(err.Error())
	}
	third, err := step(second)
	if err != nil {
		return len(err.Error())
	}
	return first + second + third
}

func area(s shape) int {
	switch s.kind {
	case 0:
		return 3 * s.a * s.a
	case 1:
		return s.a * s.a
	}
	return s.a * s.b
}

func fib(n int) int {
	if n < 2 {
		return n
	}
	return fib(n-1) + fib(n-2)
}

func bucket(n int) int {
	switch {
	case n < 100:
		return 1
	case n < 10000:
		return 2
	case n < 500000:
		return 3
	}
	return 4
}

// rescued runs work and returns fallback applied to the panic value if it
// panics.
func rescued(work func() int, fallback func(any) int) (result int) {
	defer func() {
		if failure := recover(); failure != nil {
			result = fallback(failure)
		}
	}()
	return work()
}

func main() {
	const n = 1000000
	numbers := make([]int, n)
	shapes := make([]shape, n)
	for i := 1; i <= n; i++ {
		numbers[i-1] = (i*7919 + 13) % 1000003
		switch i % 3 {
		case 0:
			shapes[i-1] = shape{0, i % 10, 0}
		case 1:
			shapes[i-1] = shape{1, i % 7, 0}
		default:
			shapes[i-1] = shape{2, i % 5, i % 11}
		}
	}
	table := make(map[int]int, 100000)
	for i := 1; i <= 100000; i++ {
		table[i] = i * 7919 % 1009
	}

	filterMap := func() int {
		var out []int
		for _, x := range numbers {
			if x%3 == 0 {
				out = append(out, x*2)
			}
		}
		return out[0]
	}
	bench.Run("for filter and map list 1M", filterMap)
	bench.Run("enum filter and map list 1M", filterMap)
	bench.Run("for range 1M", func() int {
		out := make([]int, n)
		for x := 1; x <= n; x++ {
			out[x-1] = x*2 + 1
		}
		return out[0]
	})
	nested := func() int {
		var out []int
		for x := 1; x <= 1000; x++ {
			for y := 1; y <= 1000; y++ {
				if (x+y)%7 == 0 {
					out = append(out, x*y)
				}
			}
		}
		return len(out)
	}
	bench.Run("for two generators 1,000 x 1,000 with filter", nested)
	bench.Run("enum flat_map 1,000 x 1,000 with filter", nested)
	bench.Run("for pattern generator 1M", func() int {
		var out []int
		for _, x := range numbers {
			if x%2 == 0 {
				out = append(out, x+1)
			}
		}
		return out[0]
	})
	bench.Run("for map entries 100k", func() int {
		var out []int
		for key, value := range table {
			if value > 500 {
				out = append(out, key)
			}
		}
		return len(out)
	})
	plain := func() int {
		acc := 0
		for i := 1; i <= n; i++ {
			acc += i / (1 + i%7)
		}
		return acc
	}
	bench.Run("loop without try 1M", plain)
	bench.Run("try with no failure 1M", func() int {
		acc := 0
		for i := 1; i <= n; i++ {
			acc = rescued(func() int { return acc + i/(1+i%7) }, func(any) int { return acc })
		}
		return acc
	})
	bench.Run("try rescue raise 100k", func() int {
		acc := 0
		for i := 0; i < 100000; i++ {
			acc = rescued(func() int { panic("boom") }, func(failure any) int { return acc + len(failure.(string)) })
		}
		return acc
	})
	bench.Run("try rescue division by zero 100k", func() int {
		acc := 0
		for i := 1; i <= 100000; i++ {
			acc = rescued(func() int { return acc + i/(i%1) }, func(any) int { return acc + 1 })
		}
		return acc
	})
	bench.Run("with three clauses 1M", func() int {
		acc := 0
		for i := 1; i <= n; i++ {
			acc += chain(i)
		}
		return acc
	})
	bench.Run("case over sum type 1M", func() int {
		acc := 0
		for _, s := range shapes {
			acc += area(s)
		}
		return acc
	})
	bench.Run("cond 1M", func() int {
		acc := 0
		for _, x := range numbers {
			acc += bucket(x)
		}
		return acc
	})
	bench.Run("recursive fib(27)", func() int { return fib(27) })
}
