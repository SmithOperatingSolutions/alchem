# Elixir baseline for benchmarks/alchem/restart.alc: a one_for_one supervisor
# restarts a permanent worker 20,000 times. Each cycle crashes the worker,
# waits for its replacement and completes one round trip with it. A new
# worker announces itself to the process measuring, so finding it costs no
# polling of the supervisor. Each cycle is timed, and the phase and the
# distribution go to standard error.
Logger.configure(level: :none)
restarts = 20_000

defmodule Worker do
  def child_spec(_), do: %{id: :worker, start: {Worker, :start_link, []}, restart: :permanent}

  def start_link do
    pid = spawn_link(&Worker.loop/0)
    send(:client, {:started, pid})
    {:ok, pid}
  end

  def loop do
    receive do
      {_client, value} when value < 0 ->
        exit(:requested)

      {client, value} ->
        send(client, value)
        loop()
    end
  end
end

defmodule Restart do
  def run(_doomed, done, total, durations) when done == total, do: {total, durations}

  def run(doomed, done, total, durations) do
    since = System.monotonic_time(:microsecond)
    ref = Process.monitor(doomed)
    send(doomed, {self(), -1})

    receive do
      {:DOWN, ^ref, :process, _, :requested} -> :ok
    end

    replacement =
      receive do
        {:started, pid} -> pid
      end

    send(replacement, {self(), done})

    receive do
      ^done ->
        took = System.monotonic_time(:microsecond) - since
        run(replacement, done + 1, total, [took | durations])
    end
  end
end

Process.register(self(), :client)

{:ok, supervisor} =
  Supervisor.start_link([Worker], strategy: :one_for_one, max_restarts: 1_000_000, max_seconds: 1)

first =
  receive do
    {:started, pid} -> pid
  end

started = System.monotonic_time(:microsecond)
{^restarts, durations} = Restart.run(first, 0, restarts, [])
IO.puts(:stderr, "phase cycles #{System.monotonic_time(:microsecond) - started}")
sorted = Enum.sort(durations)
count = length(sorted)
IO.puts(:stderr, "latency restart (us) #{Enum.at(sorted, 0)} #{Enum.at(sorted, div(count, 2))} #{Enum.at(sorted, div(count * 99, 100))}")
Supervisor.stop(supervisor)
IO.puts("restarted #{restarts}")
