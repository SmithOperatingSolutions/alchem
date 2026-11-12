# Elixir baseline for benchmarks/alchem/suite/numbers.alc.
Code.require_file("bench.exs", __DIR__)

defmodule NumbersBench do
  import Bitwise

  def parsed(text) do
    case Integer.parse(text) do
      {value, ""} -> value
      _ -> 0
    end
  end

  def parsed_float(text) do
    case Float.parse(text) do
      {value, ""} -> value
      _ -> 0.0
    end
  end

  def main do
    n = 200_000
    integers = Enum.map(1..n, fn i -> i * 7919 end)
    decimal = Enum.map(integers, &Integer.to_string/1)
    hex = Enum.map(integers, &Integer.to_string(&1, 16))
    floats = Enum.map(1..n, fn i -> i * 1.0 * 0.37 end)
    float_text = Enum.map(floats, &Float.to_string/1)

    Bench.run("integer.to_string 200k", fn -> Enum.reduce(integers, 0, fn x, acc -> acc + byte_size(Integer.to_string(x)) end) end)
    Bench.run("integer.to_string base 16 200k", fn -> Enum.reduce(integers, 0, fn x, acc -> acc + byte_size(Integer.to_string(x, 16)) end) end)
    Bench.run("integer.parse 200k", fn -> Enum.reduce(decimal, 0, fn text, acc -> acc + parsed(text) end) end)
    Bench.run("string.to_integer 200k", fn -> Enum.reduce(decimal, 0, fn text, acc -> acc + String.to_integer(text) end) end)
    Bench.run("string.to_integer base 16 200k", fn -> Enum.reduce(hex, 0, fn text, acc -> acc + String.to_integer(text, 16) end) end)
    Bench.run("float.to_string 200k", fn -> Enum.reduce(floats, 0, fn x, acc -> acc + byte_size(Float.to_string(x)) end) end)
    Bench.run("float.parse 200k", fn -> round(Enum.reduce(float_text, 0.0, fn text, acc -> acc + parsed_float(text) end)) end)
    Bench.run("string.to_float 200k", fn -> round(Enum.reduce(float_text, 0.0, fn text, acc -> acc + String.to_float(text) end)) end)
    Bench.run("float.round 2 places 200k", fn -> round(Enum.reduce(floats, 0.0, fn x, acc -> acc + Float.round(x, 2) end)) end)
    Bench.run("float.floor and ceil 200k", fn -> round(Enum.reduce(floats, 0.0, fn x, acc -> acc + Float.floor(x, 1) + Float.ceil(x, 1) end)) end)
    Bench.run("round and trunc 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> acc + round(i * 1.0 * 0.37) + trunc(i * 1.0 * 0.73) end) end)
    Bench.run("float arithmetic 1M", fn -> round(Enum.reduce(1..1_000_000, 0.0, fn i, acc -> acc + i * 1.0 * 0.5 / (i * 1.0 + 1.0) end)) end)
    Bench.run("integer arithmetic 5M", fn -> Enum.reduce(1..5_000_000, 7, fn i, acc -> rem(acc * 31 + i, 1_000_000_007) end) end)
    Bench.run("integer.digits and undigits 200k", fn -> Enum.reduce(integers, 0, fn x, acc -> acc + Integer.undigits(Integer.digits(x)) end) end)
    Bench.run("integer.gcd 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> acc + Integer.gcd(i * 7919, 1_000_003 - i) end) end)
    Bench.run("integer.pow 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> acc + Integer.pow(rem(i, 10) + 2, 10) end) end)
    Bench.run("bitwise mix 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> band(bxor(acc, bsl(i, 3)) + bsr(i, 2), 1_073_741_823) end) end)
  end
end

NumbersBench.main()
