# Elixir baseline for benchmarks/alchem/suite/processes.alc. Waiting for a
# process to end uses a monitor.
Code.require_file("bench.exs", __DIR__)

defmodule ProcessesBench do
  def joined({_pid, ref}) do
    receive do
      {:DOWN, ^ref, :process, _, _} -> 1
    end
  end

  def wait do
    receive do
      _ -> :ok
    end
  end

  def echo do
    receive do
      {client, value} ->
        send(client, value)
        if value >= 0, do: echo()
    end
  end

  def head_of do
    receive do
      {client, items} ->
        send(client, hd(items))
        if hd(items) >= 0, do: head_of()
    end
  end

  def relay(next) do
    receive do
      token ->
        send(next, token)
        if token >= 0, do: relay(next)
    end
  end

  def produce(target, count), do: Enum.each(1..count, fn i -> send(target, i) end)

  def take do
    receive do
      value when is_integer(value) -> value
    end
  end

  def main do
    me = self()
    payload = Enum.to_list(1..10_000)

    Bench.run("process spawn and await 100k, one at a time", fn -> Enum.reduce(1..100_000, 0, fn _, acc -> acc + joined(spawn_monitor(fn -> :ok end)) end) end)

    Bench.run("process spawn 100k alive at once, release, await", fn ->
      workers = Enum.map(1..100_000, fn _ -> spawn_monitor(&wait/0) end)
      Enum.each(workers, fn {worker, _} -> send(worker, 1) end)
      Enum.reduce(workers, 0, fn worker, acc -> acc + joined(worker) end)
    end)

    Bench.run("process ping-pong 500k round trips", fn ->
      {server, _} = monitored = spawn_monitor(&echo/0)

      total =
        Enum.reduce(1..500_000, 0, fn i, acc ->
          send(server, {me, i})
          acc + take()
        end)

      send(server, {me, -1})
      total + take() + joined(monitored)
    end)

    Bench.run("process fan-in 8 senders, 1M messages", fn ->
      senders = Enum.map(1..8, fn _ -> spawn_monitor(fn -> produce(me, 125_000) end) end)
      total = Enum.reduce(1..1_000_000, 0, fn _, acc -> acc + take() end)
      total + Enum.reduce(senders, 0, fn sender, acc -> acc + joined(sender) end)
    end)

    Bench.run("process ring 1,000 processes, 1,000 laps", fn ->
      first = Enum.reduce(1..1000, me, fn _, next -> spawn(fn -> relay(next) end) end)

      laps =
        Enum.reduce(1..1000, 0, fn lap, acc ->
          send(first, lap)
          acc + take()
        end)

      send(first, -1)
      laps + take()
    end)

    Bench.run("process send a 10k-element list, 10k round trips", fn ->
      server = spawn(&head_of/0)

      total =
        Enum.reduce(1..10_000, 0, fn _, acc ->
          send(server, {me, payload})
          acc + take()
        end)

      send(server, {me, [-1]})
      total + take()
    end)

    Bench.run("process mailbox fill 500k then drain", fn ->
      done = joined(spawn_monitor(fn -> produce(me, 500_000) end))
      done + Enum.reduce(1..500_000, 0, fn _, acc -> acc + take() end)
    end)
  end
end

ProcessesBench.main()
