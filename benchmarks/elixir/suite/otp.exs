# Elixir baseline for benchmarks/alchem/suite/otp.alc: GenServer for Server,
# and Elixir's own Agent and Task.
Code.require_file("bench.exs", __DIR__)

defmodule Counter do
  use GenServer

  @impl true
  def init(total), do: {:ok, total}

  @impl true
  def handle_call(amount, _from, total), do: {:reply, total + amount, total + amount}

  @impl true
  def handle_cast(amount, total), do: {:noreply, total + amount}
end

defmodule OtpBench do
  def fib(n) when n < 2, do: n
  def fib(n), do: fib(n - 1) + fib(n - 2)

  def heavy(limit) do
    Task.async_stream(1..1000, fn i -> fib(22) + i end, max_concurrency: limit)
    |> Enum.reduce(0, fn {:ok, value}, acc -> acc + value end)
  end

  def main do
    Bench.run("server.call 200k", fn ->
      {:ok, counter} = GenServer.start(Counter, 0)
      total = Enum.reduce(1..200_000, 0, fn _, acc -> acc + GenServer.call(counter, 1) end)
      GenServer.stop(counter)
      total
    end)

    Bench.run("server.call 8 clients, 25k calls each", fn ->
      {:ok, counter} = GenServer.start(Counter, 0)
      clients = Enum.map(1..8, fn _ -> Task.async(fn -> Enum.reduce(1..25_000, 0, fn _, acc -> max(acc, GenServer.call(counter, 1)) end) end) end)
      total = Enum.max(Task.await_many(clients, 60_000))
      GenServer.stop(counter)
      total
    end)

    Bench.run("server.cast 200k then one call", fn ->
      {:ok, counter} = GenServer.start(Counter, 0)
      Enum.each(1..200_000, fn _ -> GenServer.cast(counter, 1) end)
      total = GenServer.call(counter, 0, 60_000)
      GenServer.stop(counter)
      total + 200_000
    end)

    Bench.run("agent.get 200k", fn ->
      {:ok, agent} = Agent.start(fn -> 7 end)
      total = Enum.reduce(1..200_000, 0, fn _, acc -> acc + Agent.get(agent, fn state -> state end) end)
      Agent.stop(agent)
      total
    end)

    Bench.run("agent.update 200k then get", fn ->
      {:ok, agent} = Agent.start(fn -> 0 end)
      Enum.each(1..200_000, fn _ -> Agent.update(agent, fn state -> state + 1 end) end)
      total = Agent.get(agent, fn state -> state end)
      Agent.stop(agent)
      total
    end)

    Bench.run("agent.get_and_update 200k", fn ->
      {:ok, agent} = Agent.start(fn -> 0 end)
      total = Enum.reduce(1..200_000, 0, fn _, acc -> acc + Agent.get_and_update(agent, fn state -> {state, state + 1} end) end)
      Agent.stop(agent)
      total
    end)

    Bench.run("task.async and await 100k, one at a time", fn -> Enum.reduce(1..100_000, 0, fn i, acc -> acc + Task.await(Task.async(fn -> i * 2 end)) end) end)
    Bench.run("task.async 10k at once, await_many", fn -> Enum.map(1..10_000, fn i -> Task.async(fn -> fib(15) + i end) end) |> Task.await_many(60_000) |> Enum.sum() end)
    Bench.run("task.async_stream 100k trivial items", fn -> Task.async_stream(1..100_000, fn i -> i * 2 end) |> Enum.reduce(0, fn {:ok, value}, acc -> acc + value end) end)
    Bench.run("serial 1,000 x fib(22)", fn -> Enum.reduce(1..1000, 0, fn i, acc -> acc + fib(22) + i end) end)
    Bench.run("task.async_stream 1,000 x fib(22), limit 1", fn -> heavy(1) end)
    Bench.run("task.async_stream 1,000 x fib(22), limit 2", fn -> heavy(2) end)
    Bench.run("task.async_stream 1,000 x fib(22), limit 4", fn -> heavy(4) end)
    Bench.run("task.async_stream 1,000 x fib(22), limit 8", fn -> heavy(8) end)
    Bench.run("task.async_stream 1,000 x fib(22), limit 14", fn -> heavy(14) end)
  end
end

OtpBench.main()
