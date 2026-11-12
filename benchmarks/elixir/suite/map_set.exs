# Elixir baseline for benchmarks/alchem/suite/map_set.alc.
Code.require_file("bench.exs", __DIR__)

defmodule MapSetBench do
  def key(i), do: rem(i * 7919 + 13, 1_000_003)

  def build(n), do: Enum.reduce(1..n, %{}, fn i, acc -> Map.put(acc, key(i), i) end)

  def build_text(n), do: Enum.reduce(1..n, %{}, fn i, acc -> Map.put(acc, "k#{i}", i) end)

  def flag(true), do: 1
  def flag(false), do: 0

  def main do
    n = 100_000
    table = build(n)
    text = build_text(n)
    shifted = Map.new(50_001..150_000, fn i -> {key(i), i * 2} end)
    entries = Enum.map(1..n, fn i -> {key(i), i} end)
    numbers = Enum.map(1..1_000_000, fn i -> rem(i * 7919 + 13, 250_007) end)
    evens = MapSet.new(Enum.map(1..n, fn i -> i * 2 end))
    threes = MapSet.new(Enum.map(1..n, fn i -> i * 3 end))

    Bench.run("map.put build integer keys 1k", fn -> map_size(build(1000)) end)
    Bench.run("map.put build integer keys 100k", fn -> map_size(build(n)) end)
    Bench.run("map.put build integer keys 1M", fn -> map_size(build(1_000_000)) end)
    Bench.run("map.put build string keys 100k", fn -> map_size(build_text(n)) end)
    Bench.run("map.new from 100k pairs", fn -> map_size(Map.new(entries)) end)
    Bench.run("map.get hit integer keys 100k", fn -> Enum.reduce(1..n, 0, fn i, acc -> acc + Map.get(table, key(i), 0) end) end)
    Bench.run("map.get miss integer keys 100k", fn -> Enum.reduce(1..n, 0, fn i, acc -> acc + Map.get(table, 0 - i, 1) end) end)
    Bench.run("map.fetch! string keys 100k", fn -> Enum.reduce(1..n, 0, fn i, acc -> acc + Map.fetch!(text, "k#{i}") end) end)
    Bench.run("map.has_key? 100k", fn -> Enum.reduce(1..n, 0, fn i, acc -> acc + flag(Map.has_key?(table, i)) end) end)

    Bench.run("map.update 1M counters over 1000 keys", fn ->
      counts = Enum.reduce(1..1_000_000, %{}, fn i, acc -> Map.update(acc, rem(i, 1000), 1, fn count -> count + 1 end) end)
      Map.fetch!(counts, 7)
    end)

    Bench.run("map.update existing 100k keys", fn ->
      Enum.reduce(1..n, table, fn i, acc -> Map.update(acc, key(i), 0, fn value -> value + 1 end) end) |> map_size()
    end)

    Bench.run("map.merge 100k with 100k", fn -> map_size(Map.merge(table, shifted)) end)
    Bench.run("map.delete 100k keys", fn -> Enum.reduce(1..n, table, fn i, acc -> Map.delete(acc, key(i)) end) |> map_size() end)
    Bench.run("map.to_list 100k", fn -> table |> Map.to_list() |> length() end)
    Bench.run("map.keys 100k", fn -> table |> Map.keys() |> Enum.sum() end)
    Bench.run("map.values 100k", fn -> table |> Map.values() |> Enum.sum() end)
    Bench.run("map.filter 100k", fn -> table |> Map.filter(fn {_, value} -> rem(value, 2) == 0 end) |> map_size() end)
    Bench.run("mapset.new from 1M integers", fn -> numbers |> MapSet.new() |> MapSet.size() end)
    Bench.run("mapset.put 100k", fn -> Enum.reduce(1..n, MapSet.new(), fn i, acc -> MapSet.put(acc, key(i)) end) |> MapSet.size() end)
    Bench.run("mapset.member? 200k", fn -> Enum.reduce(1..200_000, 0, fn i, acc -> acc + flag(MapSet.member?(evens, i)) end) end)
    Bench.run("mapset.union 100k with 100k", fn -> MapSet.size(MapSet.union(evens, threes)) end)
    Bench.run("mapset.intersection 100k with 100k", fn -> MapSet.size(MapSet.intersection(evens, threes)) end)
    Bench.run("mapset.difference 100k with 100k", fn -> MapSet.size(MapSet.difference(evens, threes)) end)
  end
end

MapSetBench.main()
