# Elixir baseline for benchmarks/alchem/spawn.alc: 100,000 processes alive at
# once, each blocked in receive until released, then joined through monitors.
phase = fn name, since ->
  now = System.monotonic_time(:microsecond)
  IO.puts(:stderr, "phase #{name} #{now - since}")
  now
end
count = 100_000

started = System.monotonic_time(:microsecond)

pids =
  for _ <- 1..count do
    spawn(fn ->
      receive do
        _ -> :ok
      end
    end)
  end

spawned = phase.("spawn", started)
refs = Enum.map(pids, &Process.monitor/1)
Enum.each(pids, &send(&1, 1))

Enum.each(refs, fn ref ->
  receive do
    {:DOWN, ^ref, :process, _, :normal} -> :ok
  end
end)

phase.("release and join", spawned)
IO.puts("spawned #{count}")
