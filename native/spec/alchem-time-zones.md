# Time zones

`DateTime.shift_zone`, `shift_zone!`, `now`, `from_naive/2`, `shift`,
`add`, `to_string` and `Calendar.strftime` (`%Z`, `%z`) in any zone of the
system's zone database, as the pinned runtime has them through Go's
`time.LoadLocation` and `time.Date`. `harness/time_zones.py` holds 12
programs (about 170 lines of output) with the pinned compiler's results
frozen in. It brings its own database: `$ZONEINFO` names a directory the
gate lays out, with Europe/Paris, Asia/Tokyo and America/New_York as they
were on the machine that froze it and 15 files made for the purpose, so
the gate depends on no installed database, zone or clock. Beyond the
gate, 3,000 random cases over 40 zone names of the installed database
(conversions, wall clocks in gaps and repeats, shifts by every unit,
additions, formatting) gave the pinned output.

## Finding a zone

The entry `dz/2` at the end of `library/Date.alc`. `UTC` and `Etc/UTC` are
UTC; `""`, `Local`, a name with `..` or one that starts with `/` or `\` is
no zone. Any other NAME is the first zone file among `$ZONEINFO/NAME`
(when the variable is set and not empty), `/usr/share/zoneinfo/NAME`,
`/usr/share/lib/zoneinfo/NAME`, `/usr/lib/locale/TZ/NAME` and
`/etc/zoneinfo/NAME`: Go's order. A file that is no zone file (wrong
magic, a version other than 1 to 3, cut short, a transition of a type it
does not have, an abbreviation outside its table, more than 10 MB) is
passed over for the next directory, as `LoadLocationFromTZData` failing
does there.

A file is read once, into mapped memory behind 512 bytes that say where
its parts stand, and kept for the life of the program: word 80 of the
library's state block (`alchem-system.md`) is the first of a chain of such
records. Nothing of it is in the arena. A name that has no file is looked
for again each time.

## What a zone has at a moment

`dz(name, seconds)` is `Location.lookup`: `[1, offset, start, end, where
the abbreviation stands, its length]`, or `[0]`.

- Before the first transition: the zone type `lookupFirstZone` picks (the
  first type when no transition uses it; else the nearest standard type
  before the first transition's when that one is summer time; else the
  first standard type).
- Otherwise the type of the last transition not after the moment, found
  by halving, in the 64-bit data of a version 2 or 3 file.
- After the last transition, when the file ends in a rule (a POSIX TZ
  text such as `CET-1CEST,M3.5.0,M10.5.0/3`), what Go's `tzset` makes of
  it: names bare or in `<>`, offsets `[+-]hh[:mm[:ss]]` up to 168 hours,
  changes as `Jn`, `n` or `Mm.w.d` with an optional `/time`, the default
  `,M3.2.0,M11.1.0` when a summer name has no changes, the two zones
  swapped when summer starts later in the year than it ends, and the last
  transition's type when the rule cannot be read.

## The wall clock

`dn(fields, name)` is `time.Date` in a zone: the offset is the one the
zone has at the fields read as UTC, or, when the moment that gives lies
outside that offset's span, the one at that moment. So a time the clocks
skipped moves on by the gap and one they repeated is its first.
`DateTime.from_naive/2` is that; `DateTime.shift` (`ds`) moves years,
months, weeks and days on the wall clock, each step through `dn` as the
runtime's `calShiftWall` goes through `time.Date` (to the first of the
target month, then to the day or the month's last, then by the days),
reads the wall clock once more, and then adds the hours and smaller units
as elapsed time.

## Differences that remain

- The pinned runtime carries Go's own copy of the zone database
  (`time/tzdata`) for a machine that has none installed. Here a machine
  without zone files knows only UTC and the zones of one offset that
  `Date.dv` names (`Etc/GMT+12` to `Etc/GMT-14`, the names of GMT and
  UTC): embedding the database would add about 400 KB to every compiler,
  whose source text holds the library.
- `$ZONEINFO` may name a zip archive for Go; here it is a directory.
- Go reads `$ZONEINFO` once; here it is read at each first use of a zone,
  so a `System.put_env` between two zones takes effect.
