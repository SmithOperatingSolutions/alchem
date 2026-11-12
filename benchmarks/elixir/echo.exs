# Elixir baseline for benchmarks/alchem/echo.alc: 200,000 request/reply round
# trips between two processes. Each round trip is timed, and the phase and
# the distribution go to standard error.
round_trips = 200_000

defmodule Echo do
  def serve do
    receive do
      {client, value} ->
        send(client, value)
        serve()
    end
  end

  def run(_server, sent, total, _since, durations) when sent == total, do: {total, durations}

  def run(server, sent, total, since, durations) do
    send(server, {self(), sent})

    receive do
      ^sent ->
        now = System.monotonic_time(:nanosecond)
        run(server, sent + 1, total, now, [now - since | durations])
    end
  end
end

server = spawn(&Echo.serve/0)
started = System.monotonic_time(:nanosecond)
{^round_trips, durations} = Echo.run(server, 0, round_trips, started, [])
IO.puts(:stderr, "phase round trips #{div(System.monotonic_time(:nanosecond) - started, 1000)}")
sorted = Enum.sort(durations)
count = length(sorted)
IO.puts(:stderr, "latency round trip (ns) #{Enum.at(sorted, 0)} #{Enum.at(sorted, div(count, 2))} #{Enum.at(sorted, div(count * 99, 100))}")
Process.exit(server, :kill)
IO.puts("round trips #{round_trips}")
