# Elixir baseline for benchmarks/alchem/suite/calendar.alc.
Code.require_file("bench.exs", __DIR__)

defmodule CalendarBench do
  def day(text) do
    case Date.from_iso8601(text) do
      {:ok, date} -> date.day
      _ -> 0
    end
  end

  def minute(text) do
    case DateTime.from_iso8601(text) do
      {:ok, moment, offset} -> moment.minute + offset
      _ -> 0
    end
  end

  def order(:lt), do: -1
  def order(:eq), do: 0
  def order(:gt), do: 1

  def main do
    n = 100_000
    base = ~D[2000-01-01]
    start = ~N[2000-01-01 00:00:00]
    dates = Enum.map(1..n, fn i -> Date.add(base, rem(i * 7919, 20_011)) end)
    date_text = Enum.map(dates, &Date.to_iso8601/1)
    naive = Enum.map(1..n, fn i -> NaiveDateTime.add(start, i * 7919) end)
    naive_text = Enum.map(naive, &NaiveDateTime.to_iso8601/1)
    moments = Enum.map(1..n, fn i -> DateTime.from_unix!(946_684_800 + i * 7919) end)
    moment_text = Enum.map(moments, fn moment -> String.replace(DateTime.to_iso8601(moment), "Z", "+02:00") end)

    Bench.run("date.add 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> acc + Date.add(base, rem(i, 20_011)).day end) end)
    Bench.run("date.new! 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> acc + Date.new!(2000 + rem(i, 50), rem(i, 12) + 1, rem(i, 28) + 1).year end) end)
    Bench.run("date.diff 100k", fn -> Enum.reduce(dates, 0, fn date, acc -> acc + Date.diff(date, base) end) end)
    Bench.run("date.day_of_week 100k", fn -> Enum.reduce(dates, 0, fn date, acc -> acc + Date.day_of_week(date) end) end)
    Bench.run("date.end_of_month 100k", fn -> Enum.reduce(dates, 0, fn date, acc -> acc + Date.end_of_month(date).day end) end)
    Bench.run("date.to_iso8601 100k", fn -> Enum.reduce(dates, 0, fn date, acc -> acc + byte_size(Date.to_iso8601(date)) end) end)
    Bench.run("date.from_iso8601 100k", fn -> Enum.reduce(date_text, 0, fn text, acc -> acc + day(text) end) end)
    Bench.run("date sort 100k", fn -> Date.diff(hd(Enum.sort(dates, Date)), base) end)
    Bench.run("naive_date_time.add 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> acc + NaiveDateTime.add(start, i * 61).second end) end)
    Bench.run("naive_date_time.diff 100k", fn -> Enum.reduce(naive, 0, fn moment, acc -> acc + NaiveDateTime.diff(moment, start) end) end)
    Bench.run("naive_date_time.to_iso8601 100k", fn -> Enum.reduce(naive, 0, fn moment, acc -> acc + byte_size(NaiveDateTime.to_iso8601(moment)) end) end)
    Bench.run("naive_date_time.from_iso8601 100k", fn -> Enum.reduce(naive_text, 0, fn text, acc -> acc + NaiveDateTime.from_iso8601!(text).minute end) end)
    Bench.run("date_time.from_unix! 1M", fn -> Enum.reduce(1..1_000_000, 0, fn i, acc -> acc + DateTime.from_unix!(946_684_800 + i * 61).minute end) end)
    Bench.run("date_time.to_unix 100k", fn -> Enum.reduce(moments, 0, fn moment, acc -> acc + DateTime.to_unix(moment) end) end)
    Bench.run("date_time.add 100k", fn -> Enum.reduce(moments, 0, fn moment, acc -> acc + DateTime.add(moment, 86_399).day end) end)
    Bench.run("date_time.compare 100k", fn -> Enum.zip_reduce(moments, Enum.reverse(moments), 0, fn left, right, acc -> acc + order(DateTime.compare(left, right)) + 1 end) end)
    Bench.run("date_time.to_iso8601 100k", fn -> Enum.reduce(moments, 0, fn moment, acc -> acc + byte_size(DateTime.to_iso8601(moment)) end) end)
    Bench.run("date_time.from_iso8601 with offset 100k", fn -> Enum.reduce(moment_text, 0, fn text, acc -> acc + minute(text) end) end)
  end
end

CalendarBench.main()
