// Go ceiling for benchmarks/alchem/suite/calendar.alc, using time.Time in UTC
// for dates, naive date-times and date-times alike.
package main

import (
	"slices"
	"strings"
	"time"

	"github.com/SmithOperatingSolutions/alchem/benchmarks/go/suite/bench"
)

const (
	dateLayout  = "2006-01-02"
	naiveLayout = "2006-01-02T15:04:05"
	day         = 24 * time.Hour
)

func main() {
	const n = 100000
	base := time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)
	dates := make([]time.Time, n)
	dateText := make([]string, n)
	naive := make([]time.Time, n)
	naiveText := make([]string, n)
	moments := make([]time.Time, n)
	momentText := make([]string, n)
	for i := 1; i <= n; i++ {
		dates[i-1] = base.AddDate(0, 0, i*7919%20011)
		dateText[i-1] = dates[i-1].Format(dateLayout)
		naive[i-1] = base.Add(time.Duration(i*7919) * time.Second)
		naiveText[i-1] = naive[i-1].Format(naiveLayout)
		moments[i-1] = time.Unix(int64(946684800+i*7919), 0).UTC()
		momentText[i-1] = strings.Replace(moments[i-1].Format(time.RFC3339), "Z", "+02:00", 1)
	}

	bench.Run("date.add 1M", func() int {
		total := 0
		for i := 1; i <= 1000000; i++ {
			total += base.AddDate(0, 0, i%20011).Day()
		}
		return total
	})
	bench.Run("date.new! 1M", func() int {
		total := 0
		for i := 1; i <= 1000000; i++ {
			total += time.Date(2000+i%50, time.Month(i%12+1), i%28+1, 0, 0, 0, 0, time.UTC).Year()
		}
		return total
	})
	bench.Run("date.diff 100k", func() int {
		total := 0
		for _, date := range dates {
			total += int(date.Sub(base) / day)
		}
		return total
	})
	bench.Run("date.day_of_week 100k", func() int {
		total := 0
		for _, date := range dates {
			weekday := int(date.Weekday())
			if weekday == 0 {
				weekday = 7
			}
			total += weekday
		}
		return total
	})
	bench.Run("date.end_of_month 100k", func() int {
		total := 0
		for _, date := range dates {
			total += time.Date(date.Year(), date.Month()+1, 0, 0, 0, 0, 0, time.UTC).Day()
		}
		return total
	})
	bench.Run("date.to_iso8601 100k", func() int {
		total := 0
		for _, date := range dates {
			total += len(date.Format(dateLayout))
		}
		return total
	})
	bench.Run("date.from_iso8601 100k", func() int {
		total := 0
		for _, text := range dateText {
			if date, err := time.Parse(dateLayout, text); err == nil {
				total += date.Day()
			}
		}
		return total
	})
	bench.Run("date sort 100k", func() int {
		out := slices.Clone(dates)
		slices.SortFunc(out, func(a, b time.Time) int { return a.Compare(b) })
		return int(out[0].Sub(base) / day)
	})
	bench.Run("naive_date_time.add 1M", func() int {
		total := 0
		for i := 1; i <= 1000000; i++ {
			total += base.Add(time.Duration(i*61) * time.Second).Second()
		}
		return total
	})
	bench.Run("naive_date_time.diff 100k", func() int {
		total := 0
		for _, moment := range naive {
			total += int(moment.Sub(base) / time.Second)
		}
		return total
	})
	bench.Run("naive_date_time.to_iso8601 100k", func() int {
		total := 0
		for _, moment := range naive {
			total += len(moment.Format(naiveLayout))
		}
		return total
	})
	bench.Run("naive_date_time.from_iso8601 100k", func() int {
		total := 0
		for _, text := range naiveText {
			if moment, err := time.Parse(naiveLayout, text); err == nil {
				total += moment.Minute()
			}
		}
		return total
	})
	bench.Run("date_time.from_unix! 1M", func() int {
		total := 0
		for i := 1; i <= 1000000; i++ {
			total += time.Unix(int64(946684800+i*61), 0).UTC().Minute()
		}
		return total
	})
	bench.Run("date_time.to_unix 100k", func() int {
		total := 0
		for _, moment := range moments {
			total += int(moment.Unix())
		}
		return total
	})
	bench.Run("date_time.add 100k", func() int {
		total := 0
		for _, moment := range moments {
			total += moment.Add(86399 * time.Second).Day()
		}
		return total
	})
	bench.Run("date_time.compare 100k", func() int {
		total := 0
		for i, moment := range moments {
			total += moment.Compare(moments[len(moments)-1-i]) + 1
		}
		return total
	})
	bench.Run("date_time.to_iso8601 100k", func() int {
		total := 0
		for _, moment := range moments {
			total += len(moment.Format(time.RFC3339))
		}
		return total
	})
	bench.Run("date_time.from_iso8601 with offset 100k", func() int {
		total := 0
		for _, text := range momentText {
			if moment, err := time.Parse(time.RFC3339, text); err == nil {
				_, offset := moment.Zone()
				total += moment.UTC().Minute() + offset
			}
		}
		return total
	})
}
