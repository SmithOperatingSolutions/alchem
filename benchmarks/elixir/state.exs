# Elixir baseline for benchmarks/alchem/state.alc: build a 50,000-entry map
# one key at a time, sum it in key order, then update 1,000 counters 50,000
# times.
phase = fn name, since ->
  now = System.monotonic_time(:microsecond)
  IO.puts(:stderr, "phase #{name} #{now - since}")
  now
end
started = System.monotonic_time(:microsecond)
numbers = 1..50_000
counts = Enum.reduce(numbers, %{}, fn n, counts -> Map.update(counts, n, n, &(&1 + n)) end)
50_000 = map_size(counts)
50_000 = Map.fetch!(counts, 50_000)
built = phase.("build", started)

1_250_025_000 =
  counts |> Enum.sort() |> Enum.reduce(0, fn {_key, value}, sum -> sum + value end)

summed = phase.("sum", built)

buckets =
  Enum.reduce(numbers, %{}, fn n, buckets -> Map.update(buckets, rem(n, 1000), 1, &(&1 + 1)) end)

1000 = map_size(buckets)
50 = Map.fetch!(buckets, 0)
phase.("update", summed)
IO.puts("state kept")
