# Logger

`Logger.debug`, `info`, `warning` and `error` (a text; a function that
makes the text only when the level is written; a text and metadata),
`Logger.log`, `configure` (a level, or `level:`, `format:`, `metadata:`),
`level`, `metadata/0,1`, `add_handler` and `remove_handler`, with the
pinned runtime's lines, values and failures. `harness/logger.py` holds 18
programs with the pinned compiler's status, standard output and standard
error frozen in (none of their formats holds the time), 13 programs it
rejects, a check of `$time` and `$date` against the clock under six
settings of `$TZ`, with a zone file of the gate's own, and 200,000
messages in one program whose arena is held to 4 MiB
(`native_memory.floor_arena`), which shows that a message of one text
costs none of it.

## What is kept

The language has no state a program's functions share, so the logger's is
a mapped page that word 88 of the library's state block points at
(`alchem-system.md`; word 80 is the zone files of `alchem-time-zones.md`):
the level (it starts at what `ALCHEM_LOG_LEVEL` names, else at debug),
whether the console is off, and the words of four values that live in the
arena: the format, the metadata keys to show, the handlers and the
metadata of the main process. The metadata is each process's own, as
upstream keeps it: for any other process (`Sys.state()+96` names the one
running, `alchem-processes.md`) word 144 of the page starts a chain of
records, next, process and the word of its list, which `Logger.metadata`
reads and writes. A record is 24 bytes of the arena; when a process sets
metadata for the first time the records of processes that are over are
taken out of the chain. A handler is kept as the word of its function value and called
as a function of an integer result; what it gives is not looked at, so a
handler of any result type is taken (`fn[atom, string, list[tuple[atom,
string]], b]`).

## A line

A message below the level is dropped before anything else, and the
function of the lazy form is not called. Then the handlers get the level,
the text and all the metadata, in the order they were added; then, unless
`:console` was removed, the format is written to standard error with
`$time`, `$date`, `$level`, `$metadata`, `$message` and `$node` replaced,
tried in that order at each `$` as Go's `strings.Replacer` tries them,
line breaks at the end taken off and one put after. The line is gathered
in the library's pad and written with one call. A message of one text
costs nothing of the arena; one with metadata costs the joined list, and
a handler what it does.

`Logger.info(text)` and its three siblings do not show the metadata of
`Logger.metadata`; `Logger.info(text, [])`, the lazy form and `Logger.log`
do. That is the pinned runtime's own behaviour (the one-text functions
pass no process), kept as it is.

`$time` (`15:04:05.000`) and `$date` (`2006-01-02`) are local time as Go's
`time.Local` has it: the zone file `$TZ` names (a path from the root, or a
name under the system's zone directories; a colon before it is passed
over), `/etc/localtime` when there is no `$TZ`, and UTC when `$TZ` is
empty or names no zone file. `Date.dl` reads it with the zone code of
`alchem-time-zones.md`, which is an entry of its own so that a program
that logs does not get the date library; the offset is asked again only
when the clock leaves the span the zone gave it for.

## Differences that remain

- Several handlers are called in the order they were added; upstream
  keeps them in a Go map and calls them in no fixed order.

The lazy form takes a function of a string, and also one whose body only
raises (`Logger.info(fn -> raise("x") end)`, a function of `{}` to the
compiler): a third form of each of the four names, which calls it when the
level is written and so fails as upstream does.
