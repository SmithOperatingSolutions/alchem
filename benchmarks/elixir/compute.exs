# Elixir baseline for benchmarks/alchem/compute.alc: recursive fib(32), then
# the sum of squares of 1..1,000,000 through an intermediate list.
phase = fn name, since ->
  now = System.monotonic_time(:microsecond)
  IO.puts(:stderr, "phase #{name} #{now - since}")
  now
end
defmodule Compute do
  def fib(n) when n < 2, do: n
  def fib(n), do: fib(n - 1) + fib(n - 2)
end

started = System.monotonic_time(:microsecond)
2_178_309 = Compute.fib(32)
recursed = phase.("fib", started)

total =
  1..1_000_000
  |> Enum.map(fn n -> n * n end)
  |> Enum.reduce(0, fn n, total -> total + n end)

333_333_833_333_500_000 = total
phase.("squares", recursed)
IO.puts("computed")
