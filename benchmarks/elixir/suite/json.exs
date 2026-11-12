# Elixir baseline for benchmarks/alchem/suite/json.alc, using the JSON module
# that ships with Elixir.
Code.require_file("bench.exs", __DIR__)

defmodule JsonBench do
  def width(document) when is_list(document), do: length(document)
  def width(document) when is_map(document), do: map_size(document)
  def width(_), do: 0

  def main([inputs | _]) do
    small = File.read!(Path.join(inputs, "small.json"))
    medium = File.read!(Path.join(inputs, "medium.json"))
    large = File.read!(Path.join(inputs, "large.json"))
    small_value = JSON.decode!(small)
    medium_value = JSON.decode!(medium)
    large_value = JSON.decode!(large)

    Bench.run("json.decode 159 B, 10,000 times", fn -> Enum.reduce(1..10_000, 0, fn _, acc -> acc + width(JSON.decode!(small)) end) end)
    Bench.run("json.decode 10 KB, 200 times", fn -> Enum.reduce(1..200, 0, fn _, acc -> acc + width(JSON.decode!(medium)) end) end)
    Bench.run("json.decode 5 MB", fn -> width(JSON.decode!(large)) end)
    Bench.run("json.encode 159 B, 10,000 times", fn -> Enum.reduce(1..10_000, 0, fn _, acc -> acc + byte_size(JSON.encode!(small_value)) end) end)
    Bench.run("json.encode 10 KB, 200 times", fn -> Enum.reduce(1..200, 0, fn _, acc -> acc + byte_size(JSON.encode!(medium_value)) end) end)
    Bench.run("json.encode 5 MB", fn -> byte_size(JSON.encode!(large_value)) end)
  end
end

JsonBench.main(System.argv())
