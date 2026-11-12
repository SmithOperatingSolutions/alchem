# Elixir baseline for benchmarks/alchem/build.alc: build a 50,000-element list
# by prepending, then walk and sum it.
phase = fn name, since ->
  now = System.monotonic_time(:microsecond)
  IO.puts(:stderr, "phase #{name} #{now - since}")
  now
end
defmodule Build do
  def count([], seen), do: seen
  def count([_ | rest], seen), do: count(rest, seen + 1)
end

started = System.monotonic_time(:microsecond)
items = Enum.reduce(1..50_000, [], fn n, items -> [n | items] end)
50_000 = hd(items)
grown = phase.("grow", started)
50_000 = Build.count(items, 0)
1_250_025_000 = Enum.reduce(items, 0, fn n, total -> total + n end)
phase.("walk", grown)
IO.puts("built")
