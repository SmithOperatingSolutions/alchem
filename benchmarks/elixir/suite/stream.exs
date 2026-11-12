# Elixir baseline for benchmarks/alchem/suite/stream.alc.
Code.require_file("bench.exs", __DIR__)

defmodule StreamBench do
  def value(line), do: line |> String.split(",") |> Enum.at(2, "0") |> String.to_integer()

  def word(line), do: line |> String.split(",") |> Enum.at(1, "")

  def main([inputs | _]) do
    lines = Path.join(inputs, "lines.txt")
    head = Path.join(inputs, "head.txt")
    n = 1_000_000
    numbers = Enum.map(1..n, fn i -> rem(i * 7919 + 13, 1_000_003) end)

    Bench.run("stream map filter sum 1M", fn -> numbers |> Stream.map(fn x -> x * 3 end) |> Stream.filter(fn x -> rem(x, 2) == 0 end) |> Enum.sum() end)
    Bench.run("eager map filter sum 1M", fn -> numbers |> Enum.map(fn x -> x * 3 end) |> Enum.filter(fn x -> rem(x, 2) == 0 end) |> Enum.sum() end)
    Bench.run("stream map filter take 1,000 of 1M", fn -> numbers |> Stream.map(fn x -> x * 3 end) |> Stream.filter(fn x -> rem(x, 2) == 0 end) |> Enum.take(1000) |> Enum.sum() end)
    Bench.run("eager map filter take 1,000 of 1M", fn -> numbers |> Enum.map(fn x -> x * 3 end) |> Enum.filter(fn x -> rem(x, 2) == 0 end) |> Enum.take(1000) |> Enum.sum() end)
    Bench.run("stream chunk_every 100 then sum 1M", fn -> numbers |> Stream.chunk_every(100) |> Stream.map(fn chunk -> Enum.sum(chunk) end) |> Enum.max() end)
    Bench.run("eager chunk_every 100 then sum 1M", fn -> numbers |> Enum.chunk_every(100) |> Enum.map(fn chunk -> Enum.sum(chunk) end) |> Enum.max() end)
    Bench.run("stream range map filter sum 1M", fn -> 1..n |> Stream.map(fn x -> x * 3 end) |> Stream.filter(fn x -> rem(x, 2) == 0 end) |> Enum.sum() end)
    Bench.run("stream.iterate take 1M", fn -> Stream.iterate(1, fn x -> rem(x * 31 + 7, 1_000_003) end) |> Stream.take(n) |> Enum.sum() end)

    Bench.run("stream.unfold 1M", fn ->
      Stream.unfold(1, fn x -> if x > n, do: nil, else: {x * 2, x + 1} end) |> Enum.sum()
    end)

    Bench.run("stream.with_index 1M", fn -> numbers |> Stream.with_index() |> Stream.map(fn {x, index} -> x + index end) |> Enum.sum() end)
    Bench.run("stream.flat_map 200k", fn -> 1..200_000 |> Stream.flat_map(fn x -> [x, x + 1] end) |> Enum.sum() end)
    Bench.run("stream.scan 1M", fn -> numbers |> Stream.scan(0, fn x, acc -> rem(acc + x, 1_000_003) end) |> Enum.max() end)
    Bench.run("stream.zip 1M", fn -> Stream.zip(numbers, 1..n) |> Stream.map(fn {x, index} -> x * index end) |> Enum.max() end)
    Bench.run("file.stream! count lines 1M (64 MiB)", fn -> File.stream!(lines) |> Enum.count() end)
    Bench.run("file.stream! parse and sum a column 1M", fn -> File.stream!(lines) |> Stream.map(&value/1) |> Enum.sum() end)
    Bench.run("file.stream! word frequencies 1M", fn -> File.stream!(lines) |> Stream.map(&word/1) |> Enum.frequencies() |> map_size() end)

    Bench.run("file.stream! filter then chunk_every 1,000", fn ->
      File.stream!(lines) |> Stream.filter(fn line -> String.contains?(line, ",w12") end) |> Stream.chunk_every(1000) |> Stream.map(fn chunk -> length(chunk) end) |> Enum.sum()
    end)

    Bench.run("file.stream! 64 KiB chunks (64 MiB)", fn -> File.stream!(lines, 65_536) |> Stream.map(fn chunk -> byte_size(chunk) end) |> Enum.sum() end)
    Bench.run("file.stream! sum a column 120k (8 MiB)", fn -> File.stream!(head) |> Stream.map(&value/1) |> Enum.sum() end)

    Bench.run("file.read! split sum a column 120k (8 MiB)", fn ->
      File.read!(head) |> String.split("\n") |> Enum.reject(fn line -> line == "" end) |> Enum.map(&value/1) |> Enum.sum()
    end)
  end
end

StreamBench.main(System.argv())
