# Elixir baseline for benchmarks/alchem/suite/string.alc.
Code.require_file("bench.exs", __DIR__)

defmodule StringBench do
  def flag(true), do: 1
  def flag(false), do: 0

  def line(i) do
    "2026-11-10 12:00:#{rem(i, 60)} host#{rem(i, 17)} GET /api/items/#{i} #{200 + rem(i, 7) * 50} #{rem(i * 31, 997)}ms"
  end

  def main do
    words = Enum.map(1..200_000, fn i -> "w#{rem(i * 7919, 100_003)}" end)
    padded = Enum.map(words, fn word -> "  #{word}\t " end)
    shifted = Enum.drop(words, 1)
    text = Enum.join(words, " ")
    accented = String.duplicate("naïve café 日本語 Straße ", 10_000)
    long = String.duplicate("abcdefghij", 100)
    lines = Enum.map(1..100_000, &line/1)
    few = Enum.take(lines, 10_000)
    server_error = ~r/ 5\d\d /
    request = ~r/GET (\S+) (\d+)/
    named = ~r/host(?P<host>\d+) GET (?P<path>\S+)/
    digits = ~r/\d+/
    separators = ~r/[ \/:]+/

    Bench.run("string <> append 1 byte 20k times", fn -> Enum.reduce(1..20_000, "", fn _, acc -> acc <> "x" end) |> byte_size() end)
    Bench.run("string interpolation 200k", fn -> Enum.reduce(1..200_000, 0, fn i, acc -> acc + byte_size("item #{i} of #{acc}") end) end)
    Bench.run("string.split on space 1.4 MB", fn -> text |> String.split(" ") |> length() end)
    Bench.run("string.split whitespace 1.4 MB", fn -> text |> String.split() |> length() end)
    Bench.run("string.replace 1.4 MB", fn -> text |> String.replace("w1", "W-") |> byte_size() end)
    Bench.run("string.contains? 200k words", fn -> Enum.count(words, fn word -> String.contains?(word, "99") end) end)
    Bench.run("string.starts_with? 200k words", fn -> Enum.count(words, fn word -> String.starts_with?(word, "w12") end) end)
    Bench.run("string.upcase ASCII 1.4 MB", fn -> text |> String.upcase() |> byte_size() end)
    Bench.run("string.downcase ASCII 1.4 MB", fn -> text |> String.downcase() |> byte_size() end)
    Bench.run("string.upcase non-ASCII 310 KB", fn -> accented |> String.upcase() |> byte_size() end)
    Bench.run("string.trim 200k words", fn -> Enum.reduce(padded, 0, fn word, acc -> acc + byte_size(String.trim(word)) end) end)
    Bench.run("string.length ASCII 1.4 MB", fn -> String.length(text) end)
    Bench.run("string.length non-ASCII 310 KB", fn -> String.length(accented) end)
    Bench.run("string.slice 100k from the middle of 1,000 characters", fn -> Enum.reduce(1..100_000, 0, fn i, acc -> acc + byte_size(String.slice(long, 400 + rem(i, 100), 20)) end) end)
    Bench.run("string.graphemes non-ASCII 310 KB", fn -> accented |> String.graphemes() |> length() end)
    Bench.run("string.codepoints non-ASCII 310 KB", fn -> accented |> String.codepoints() |> length() end)
    Bench.run("string.reverse ASCII 1.4 MB", fn -> text |> String.reverse() |> byte_size() end)
    Bench.run("string.pad_leading 200k words", fn -> Enum.reduce(words, 0, fn word, acc -> acc + byte_size(String.pad_leading(word, 12, "0")) end) end)
    Bench.run("string == and < compare 200k words", fn -> Enum.zip_reduce(words, shifted, 0, fn left, right, acc -> acc + flag(left < right) + flag(left == right) end) end)
    Bench.run("regex.match? 100k lines", fn -> Enum.count(lines, fn entry -> Regex.match?(server_error, entry) end) end)

    Bench.run("regex.run with captures 100k lines", fn ->
      Enum.reduce(lines, 0, fn entry, acc ->
        case Regex.run(request, entry) do
          [_, _, status] -> acc + String.to_integer(status)
          _ -> acc
        end
      end)
    end)

    Bench.run("regex.named_captures 100k lines", fn ->
      Enum.reduce(lines, 0, fn entry, acc ->
        case Regex.named_captures(named, entry) do
          nil -> acc
          found -> acc + byte_size(Map.get(found, "path", ""))
        end
      end)
    end)

    Bench.run("regex.scan 10k lines", fn -> Enum.reduce(few, 0, fn entry, acc -> acc + length(Regex.scan(digits, entry)) end) end)
    Bench.run("regex.replace 10k lines", fn -> Enum.reduce(few, 0, fn entry, acc -> acc + byte_size(Regex.replace(digits, entry, "N")) end) end)
    Bench.run("regex.split 10k lines", fn -> Enum.reduce(few, 0, fn entry, acc -> acc + length(Regex.split(separators, entry)) end) end)
  end
end

StringBench.main()
