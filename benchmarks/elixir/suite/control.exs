# Elixir baseline for benchmarks/alchem/suite/control.alc. Sum types become
# tagged tuples, option becomes {:ok, value} or :error, and failures are
# exceptions.
Code.require_file("bench.exs", __DIR__)

defmodule ControlBench do
  def step(n) when rem(n, 10) == 0, do: {:error, "multiple of ten"}
  def step(n), do: {:ok, n + 1}

  def chain(n) do
    with {:ok, first} <- step(n),
         {:ok, second} <- step(first),
         {:ok, third} <- step(second) do
      first + second + third
    else
      {:error, reason} -> byte_size(reason)
    end
  end

  def area({:circle, radius}), do: 3 * radius * radius
  def area({:square, side}), do: side * side
  def area({:rectangle, width, height}), do: width * height

  def shape(i) do
    case rem(i, 3) do
      0 -> {:circle, rem(i, 10)}
      1 -> {:square, rem(i, 7)}
      _ -> {:rectangle, rem(i, 5), rem(i, 11)}
    end
  end

  def fib(n) when n < 2, do: n
  def fib(n), do: fib(n - 1) + fib(n - 2)

  def bucket(n) do
    cond do
      n < 100 -> 1
      n < 10_000 -> 2
      n < 500_000 -> 3
      true -> 4
    end
  end

  def main do
    n = 1_000_000
    numbers = Enum.map(1..n, fn i -> rem(i * 7919 + 13, 1_000_003) end)
    maybes = Enum.map(numbers, fn x -> if rem(x, 2) == 0, do: {:ok, x}, else: :error end)
    table = Map.new(1..100_000, fn i -> {i, rem(i * 7919, 1009)} end)
    shapes = Enum.map(1..n, &shape/1)

    Bench.run("for filter and map list 1M", fn -> hd(for x <- numbers, rem(x, 3) == 0, do: x * 2) end)
    Bench.run("enum filter and map list 1M", fn -> numbers |> Enum.filter(fn x -> rem(x, 3) == 0 end) |> Enum.map(fn x -> x * 2 end) |> hd() end)
    Bench.run("for range 1M", fn -> hd(for x <- 1..n, do: x * 2 + 1) end)
    Bench.run("for two generators 1,000 x 1,000 with filter", fn -> length(for x <- 1..1000, y <- 1..1000, rem(x + y, 7) == 0, do: x * y) end)

    Bench.run("enum flat_map 1,000 x 1,000 with filter", fn ->
      1..1000 |> Enum.flat_map(fn x -> 1..1000 |> Enum.filter(fn y -> rem(x + y, 7) == 0 end) |> Enum.map(fn y -> x * y end) end) |> length()
    end)

    Bench.run("for pattern generator 1M", fn -> hd(for {:ok, x} <- maybes, do: x + 1) end)
    Bench.run("for map entries 100k", fn -> length(for {key, value} <- table, value > 500, do: key) end)
    Bench.run("loop without try 1M", fn -> Enum.reduce(1..n, 0, fn i, acc -> acc + div(i, 1 + rem(i, 7)) end) end)

    Bench.run("try with no failure 1M", fn ->
      Enum.reduce(1..n, 0, fn i, acc ->
        try do
          acc + div(i, 1 + rem(i, 7))
        rescue
          _ -> acc
        end
      end)
    end)

    Bench.run("try rescue raise 100k", fn ->
      Enum.reduce(1..100_000, 0, fn _, acc ->
        try do
          raise "boom"
        rescue
          failure in RuntimeError -> acc + byte_size(failure.message)
        end
      end)
    end)

    Bench.run("try rescue division by zero 100k", fn ->
      Enum.reduce(1..100_000, 0, fn i, acc ->
        try do
          acc + div(i, rem(i, 1))
        rescue
          ArithmeticError -> acc + 1
        end
      end)
    end)

    Bench.run("with three clauses 1M", fn -> Enum.reduce(1..n, 0, fn i, acc -> acc + chain(i) end) end)
    Bench.run("case over sum type 1M", fn -> Enum.reduce(shapes, 0, fn item, acc -> acc + area(item) end) end)
    Bench.run("cond 1M", fn -> Enum.reduce(numbers, 0, fn x, acc -> acc + bucket(x) end) end)
    Bench.run("recursive fib(27)", fn -> fib(27) end)
  end
end

ControlBench.main()
