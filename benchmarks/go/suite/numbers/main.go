// Go ceiling for benchmarks/alchem/suite/numbers.alc, using strconv and math.
package main

import (
	"math"
	"strconv"
	"strings"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

// floatText writes a float the way Alchem and Elixir do: the shortest
// digits, in exponent form when that is shorter than the plain form.
func floatText(x float64) string {
	plain := strconv.FormatFloat(x, 'f', -1, 64)
	if !strings.Contains(plain, ".") {
		plain += ".0"
	}
	mantissa, exponent, _ := strings.Cut(strconv.FormatFloat(x, 'e', -1, 64), "e")
	if !strings.Contains(mantissa, ".") {
		mantissa += ".0"
	}
	sign := ""
	if exponent[0] == '-' {
		sign = "-"
	}
	digits := strings.TrimLeft(exponent[1:], "0")
	if digits == "" {
		digits = "0"
	}
	if scientific := mantissa + "e" + sign + digits; len(scientific) < len(plain) || math.Abs(x) >= 1<<53 {
		return scientific
	}
	return plain
}

// floorTo and ceilTo round at one decimal place on the exact value of the
// float, as Alchem and Elixir do: the product is corrected by what
// multiplying rounded away.
func floorTo(x float64) float64 {
	product := x * 10
	whole := math.Floor(product)
	if whole == product && math.FMA(x, 10, -product) < 0 {
		whole--
	}
	return whole / 10
}

func ceilTo(x float64) float64 {
	product := x * 10
	whole := math.Ceil(product)
	if whole == product && math.FMA(x, 10, -product) > 0 {
		whole++
	}
	return whole / 10
}

func gcd(a, b int) int {
	for b != 0 {
		a, b = b, a%b
	}
	return a
}

func pow(base, exponent int) int {
	result := 1
	for ; exponent > 0; exponent-- {
		result *= base
	}
	return result
}

func main() {
	const n = 200000
	integers := make([]int, n)
	decimal := make([]string, n)
	hex := make([]string, n)
	floats := make([]float64, n)
	floatTexts := make([]string, n)
	for i := range integers {
		integers[i] = (i + 1) * 7919
		decimal[i] = strconv.Itoa(integers[i])
		hex[i] = strings.ToUpper(strconv.FormatInt(int64(integers[i]), 16))
		floats[i] = float64(i+1) * 0.37
		floatTexts[i] = floatText(floats[i])
	}

	bench.Run("integer.to_string 200k", func() int {
		total := 0
		for _, x := range integers {
			total += len(strconv.Itoa(x))
		}
		return total
	})
	bench.Run("integer.to_string base 16 200k", func() int {
		total := 0
		for _, x := range integers {
			total += len(strings.ToUpper(strconv.FormatInt(int64(x), 16)))
		}
		return total
	})
	parse := func() int {
		total := 0
		for _, text := range decimal {
			value, _ := strconv.Atoi(text)
			total += value
		}
		return total
	}
	bench.Run("integer.parse 200k", parse)
	bench.Run("string.to_integer 200k", parse)
	bench.Run("string.to_integer base 16 200k", func() int {
		total := 0
		for _, text := range hex {
			value, _ := strconv.ParseInt(text, 16, 64)
			total += int(value)
		}
		return total
	})
	bench.Run("float.to_string 200k", func() int {
		total := 0
		for _, x := range floats {
			total += len(floatText(x))
		}
		return total
	})
	parseFloat := func() int {
		total := 0.0
		for _, text := range floatTexts {
			value, _ := strconv.ParseFloat(text, 64)
			total += value
		}
		return int(math.Round(total))
	}
	bench.Run("float.parse 200k", parseFloat)
	bench.Run("string.to_float 200k", parseFloat)
	bench.Run("float.round 2 places 200k", func() int {
		total := 0.0
		for _, x := range floats {
			total += math.Round(x*100) / 100
		}
		return int(math.Round(total))
	})
	bench.Run("float.floor and ceil 200k", func() int {
		total := 0.0
		for _, x := range floats {
			total += floorTo(x) + ceilTo(x)
		}
		return int(math.Round(total))
	})
	bench.Run("round and trunc 1M", func() int {
		total := 0
		for i := 1; i <= 1000000; i++ {
			total += int(math.Round(float64(i)*0.37)) + int(float64(i)*0.73)
		}
		return total
	})
	bench.Run("float arithmetic 1M", func() int {
		total := 0.0
		for i := 1; i <= 1000000; i++ {
			total += float64(i) * 0.5 / (float64(i) + 1.0)
		}
		return int(math.Round(total))
	})
	bench.Run("integer arithmetic 5M", func() int {
		acc := 7
		for i := 1; i <= 5000000; i++ {
			acc = (acc*31 + i) % 1000000007
		}
		return acc
	})
	bench.Run("integer.digits and undigits 200k", func() int {
		total := 0
		var digits []int
		for _, x := range integers {
			digits = digits[:0]
			for rest := x; rest > 0; rest /= 10 {
				digits = append(digits, rest%10)
			}
			value := 0
			for i := len(digits) - 1; i >= 0; i-- {
				value = value*10 + digits[i]
			}
			total += value
		}
		return total
	})
	bench.Run("integer.gcd 1M", func() int {
		total := 0
		for i := 1; i <= 1000000; i++ {
			total += gcd(i*7919, 1000003-i)
		}
		return total
	})
	bench.Run("integer.pow 1M", func() int {
		total := 0
		for i := 1; i <= 1000000; i++ {
			total += pow(i%10+2, 10)
		}
		return total
	})
	bench.Run("bitwise mix 1M", func() int {
		acc := 0
		for i := 1; i <= 1000000; i++ {
			acc = ((acc ^ (i << 3)) + (i >> 2)) & 1073741823
		}
		return acc
	})
}
