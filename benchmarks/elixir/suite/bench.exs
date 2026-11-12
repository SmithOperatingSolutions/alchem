defmodule Bench do
  # Runs work twice to warm up and seven more times, then prints the case
  # name, the median and fastest time in microseconds and the value work
  # returned, separated by tabs.
  def run(name, work) do
    samples =
      for _ <- 1..9 do
        started = System.monotonic_time(:microsecond)
        value = work.()
        {System.monotonic_time(:microsecond) - started, value}
      end

    times = samples |> Enum.drop(2) |> Enum.map(&elem(&1, 0)) |> Enum.sort()
    {_, check} = List.last(samples)
    IO.puts("#{name}\t#{Enum.at(times, 3)}\t#{hd(times)}\t#{check}")
  end
end
