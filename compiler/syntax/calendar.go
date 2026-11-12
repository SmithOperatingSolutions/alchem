package syntax

import (
	"strconv"
	"strings"
	"time"

	"github.com/SmithOperatingSolutions/alchem/compiler/ast"
)

func calendarFields(names ...string) []ast.Parameter {
	out := make([]ast.Parameter, len(names))
	for i, name := range names {
		out[i] = ast.Parameter{Name: name, Type: "integer"}
	}
	return out
}

// CalendarTypes are the builtin date and time structs. A DateTime is always
// in UTC; its time_zone and utc_offset fields record that.
func CalendarTypes() []ast.TypeDecl {
	dateTime := append(calendarFields("year", "month", "day", "hour", "minute", "second", "microsecond"), ast.Parameter{Name: "time_zone", Type: "string"}, ast.Parameter{Name: "utc_offset", Type: "integer"})
	return []ast.TypeDecl{
		{Kind: "struct", Name: "Date", Local: "Date", Fields: calendarFields("year", "month", "day")},
		{Kind: "struct", Name: "Time", Local: "Time", Fields: calendarFields("hour", "minute", "second", "microsecond")},
		{Kind: "struct", Name: "NaiveDateTime", Local: "NaiveDateTime", Fields: calendarFields("year", "month", "day", "hour", "minute", "second", "microsecond")},
		{Kind: "struct", Name: "DateTime", Local: "DateTime", Fields: dateTime},
		// A parsed address; the parts it lacks are none.
		{Kind: "struct", Name: "URI", Local: "URI", Fields: []ast.Parameter{
			{Name: "scheme", Type: "option[string]"}, {Name: "userinfo", Type: "option[string]"}, {Name: "host", Type: "option[string]"},
			{Name: "port", Type: "option[integer]"}, {Name: "path", Type: "string"}, {Name: "query", Type: "option[string]"}, {Name: "fragment", Type: "option[string]"}}},
		{Kind: "struct", Name: "Duration", Local: "Duration", Fields: calendarFields("year", "month", "week", "day", "hour", "minute", "second", "microsecond")},
		// An HTTP request as a handler sees it, and the response it gives.
		// Header names are lower case.
		{Kind: "struct", Name: "HTTP.Request", Local: "HTTP.Request", Fields: []ast.Parameter{
			{Name: "method", Type: "string"}, {Name: "path", Type: "string"}, {Name: "query", Type: "string"},
			{Name: "headers", Type: "list[tuple[string,string]]"}, {Name: "body", Type: "string"}}},
		// A range of integers, first..last//step. A range literal is a Range
		// unless a stream is expected where it is written.
		{Kind: "struct", Name: "Range", Local: "Range", Fields: []ast.Parameter{
			{Name: "first", Type: "integer"}, {Name: "last", Type: "integer"}, {Name: "step", Type: "integer"}}},
		// What Port.info reports about a running program.
		{Kind: "struct", Name: "Port.Info", Local: "Port.Info", Fields: []ast.Parameter{
			{Name: "name", Type: "string"}, {Name: "os_pid", Type: "integer"}, {Name: "input", Type: "integer"}, {Name: "output", Type: "integer"}}},
		// A semantic version, and a requirement versions are matched against.
		{Kind: "struct", Name: "Version", Local: "Version", Fields: []ast.Parameter{
			{Name: "major", Type: "integer"}, {Name: "minor", Type: "integer"}, {Name: "patch", Type: "integer"},
			{Name: "pre", Type: "list[string]", Default: &ast.Expr{Kind: "list"}}, {Name: "build", Type: "option[string]", Default: &ast.Expr{Kind: "name", Name: "none"}}}},
		{Kind: "struct", Name: "Version.Requirement", Local: "Version.Requirement", Fields: []ast.Parameter{{Name: "source", Type: "string"}}},
		// What File.stat reports: the size in bytes, the type (:regular,
		// :directory, :symlink or :other), the access the program has
		// (:read, :write, :read_write or :none), the time of the last change
		// in seconds since 1970, and the permission bits.
		{Kind: "struct", Name: "File.Stat", Local: "File.Stat", Fields: []ast.Parameter{
			{Name: "size", Type: "integer"}, {Name: "type", Type: "atom"}, {Name: "access", Type: "atom"},
			{Name: "mtime", Type: "integer"}, {Name: "mode", Type: "integer"}}},
		// A response whose chunks are some(stream) is sent as the stream
		// gives them, and a streamed client request returns one.
		{Kind: "struct", Name: "HTTP.Response", Local: "HTTP.Response", Fields: []ast.Parameter{
			{Name: "status", Type: "integer"}, {Name: "headers", Type: "list[tuple[string,string]]"}, {Name: "body", Type: "string"},
			{Name: "chunks", Type: "option[stream[string]]", Default: &ast.Expr{Kind: "name", Name: "none"}}}},
	}
}

// ParseClock reads the ISO 8601 forms the calendar sigils and functions
// accept, returning the moment in UTC and, for a DateTime, the offset in
// seconds its text was written with.
func ParseClock(kind, text string) (time.Time, int, bool) {
	layouts := map[string][]string{
		"D": {"2006-01-02"},
		"T": {"15:04:05"},
		"N": {"2006-01-02T15:04:05", "2006-01-02 15:04:05"},
		"U": {time.RFC3339, "2006-01-02 15:04:05Z07:00"},
	}[kind]
	for _, layout := range layouts {
		if moment, err := time.Parse(layout, text); err == nil {
			_, offset := moment.Zone()
			return moment.UTC(), offset, true
		}
	}
	return time.Time{}, 0, false
}

func init() {
	// ~D[2026-01-05], ~T[13:04:05], ~N[2026-01-05 13:04:05] and
	// ~U[2026-01-05T13:04:05Z] are checked here and become struct literals.
	calendarSigil = func(e *ast.Expr) string {
		moment, _, ok := ParseClock(e.Name, strings.TrimSpace(e.Value.Text))
		name := map[string]string{"D": "Date", "T": "Time", "N": "NaiveDateTime", "U": "DateTime"}[e.Name]
		if !ok {
			return "~" + e.Name + " needs a valid ISO 8601 " + name + ", found " + e.Value.Text
		}
		number := func(n int) *ast.Expr {
			return &ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "integer", Integer: int64(n)}, Line: e.Line, Column: e.Column}
		}
		date := []*ast.Expr{number(moment.Year()), number(int(moment.Month())), number(moment.Day())}
		clock := []*ast.Expr{number(moment.Hour()), number(moment.Minute()), number(moment.Second()), number(moment.Nanosecond() / 1000)}
		e.Kind, e.Name, e.Labels, e.TypeArgs, e.Left = "struct", name, nil, nil, nil
		switch name {
		case "Date":
			e.Args = date
		case "Time":
			e.Args = clock
		default:
			e.Args = append(date, clock...)
		}
		if name == "DateTime" {
			e.Args = append(e.Args, &ast.Expr{Kind: "literal", Value: ast.Literal{Kind: "string", Text: "Etc/UTC"}, Line: e.Line, Column: e.Column}, number(0))
		}
		for _, decl := range CalendarTypes() {
			if decl.Name == name {
				for _, field := range decl.Fields {
					e.Labels = append(e.Labels, field.Name)
				}
			}
		}
		return ""
	}

	lib("Calendar.strftime", "a, string -> string", "calStrftime ctx where cal:a")
	lib("URI.encode", "string -> string", "uriEncode")
	lib("URI.decode", "string -> result[string,string]", "uriDecode")
	lib("URI.encode_www_form", "string -> string", "uriEncodeForm")
	lib("URI.decode_www_form", "string -> result[string,string]", "uriDecodeForm")
	lib("URI.encode_query", "map[string,string] -> string", "uriEncodeQuery")
	lib("URI.decode_query", "string -> map[string,string]", "uriDecodeQuery")
	lib("Version.parse", "string -> result[Version,string]", "versionParse")
	lib("Version.parse!", "string -> Version", "versionParseBang ctx where")
	lib("Version.to_string", "Version -> string", "versionString")
	lib("Version.parse_requirement", "string -> result[Version.Requirement,string]", "versionRequirement ctx where")
	lib("Version.parse_requirement!", "string -> Version.Requirement", "versionRequirementBang ctx where")
	lib("Version.compare", "string, string -> atom", "versionCompareAtom ctx where")
	lib("Version.match?", "string, string -> boolean", "versionMatch ctx where")
	libAlso("Version.match?", "Version, string -> boolean", "versionMatchStruct ctx where")
	libAlso("Version.match?", "Version, Version.Requirement -> boolean", "versionMatchRequirement ctx where")
	libAlso("Version.match?", "string, Version.Requirement -> boolean", "versionMatchStringRequirement ctx where")
	lib("Version.match?", "string, string, list[tuple[atom,boolean]] -> boolean", "versionMatchOptions ctx where")
	libAlso("Version.compare", "Version, Version -> atom", "versionCompareStructs ctx where")
	lib("URI.merge", "string, string -> URI", "uriMerge")
	libAlso("URI.merge", "URI, string -> URI", "uriMergeStruct")
	lib("URI.append_path", "URI, string -> URI", "uriAppendPath ctx where")
	lib("URI.append_query", "URI, string -> URI", "uriAppendQuery")
	lib("URI.parse", "string -> URI", "uriParse")
	lib("URI.new", "string -> result[URI,string]", "uriNew")
	lib("URI.to_string", "URI -> string", "uriString")
	for index, level := range []string{"debug", "info", "warning", "error"} {
		lib("Logger."+level, "string -> void", "log"+strings.ToUpper(level[:1])+level[1:])
		libAlso("Logger."+level, "fn[string] -> void", "logLazy("+strconv.Itoa(index)+") ctx")
		lib("Logger."+level, "string, list[tuple[atom,string]] -> void", "logAt("+strconv.Itoa(index)+") ctx")
	}
	lib("Logger.log", "atom, string -> void", "logLog ctx where")
	lib("Logger.metadata", "list[tuple[atom,string]] -> void", "logMetadata ctx")
	lib("Logger.metadata", "-> list[tuple[atom,string]]", "logCurrentMetadata ctx")
	lib("Logger.add_handler", "atom, fn[atom,string,list[tuple[atom,string]],b] -> boolean", "logAddHandler ctx")
	lib("Logger.remove_handler", "atom -> boolean", "logRemoveHandler")
	lib("Logger.configure", "string -> void", "logConfigure ctx where")
	libAlso("Logger.configure", "list[tuple[atom,string]] -> void", "logConfigureOptions ctx where")
	lib("Logger.level", "-> string", "logLevel")
	lib("OptionParser.parse", "enum[string], map[string,string] -> tuple[map[string,string],list[string],list[tuple[string,string]]]", "optionParse ctx where")
	lib("OptionParser.parse", "enum[string], map[string,string], map[string,string] -> tuple[map[string,string],list[string],list[tuple[string,string]]]", "optionParseAliases ctx where")
	libAlso("OptionParser.parse", "enum[string], list[tuple[atom,list[tuple[atom,atom]]]] -> tuple[list[tuple[atom,string]],list[string],list[tuple[string,option[string]]]]", "optionParseKeyword ctx where")
	lib("OptionParser.parse_head", "enum[string], list[tuple[atom,list[tuple[atom,atom]]]] -> tuple[list[tuple[atom,string]],list[string],list[tuple[string,option[string]]]]", "optionParseHead ctx where")
	lib("OptionParser.to_argv", "list[tuple[atom,string]] -> list[string]", "optionToArgv")
	lib("OptionParser.split", "string -> list[string]", "optionSplit")
	for _, kind := range []string{"Date", "Time", "NaiveDateTime", "DateTime"} {
		lib(kind+".to_iso8601", kind+" -> string", "cal"+kind+"Iso")
		lib(kind+".to_string", kind+" -> string", "cal"+kind+"String")
		lib(kind+".compare", kind+", "+kind+" -> atom", "cal"+kind+"CompareAtom")
		lib(kind+".before?", kind+", "+kind+" -> boolean", "cal"+kind+"Before")
		lib(kind+".after?", kind+", "+kind+" -> boolean", "cal"+kind+"After")
		lib(kind+".add", kind+", integer -> "+kind, "cal"+kind+"Add ctx where")
		lib(kind+".diff", kind+", "+kind+" -> integer", "cal"+kind+"Diff")
	}
	for _, kind := range []string{"Date", "Time", "NaiveDateTime", "DateTime"} {
		lib(kind+".shift", kind+", Duration -> "+kind, "cal"+kind+"Shift ctx where")
	}
	for index, unit := range []string{"years", "months", "weeks", "days", "hours", "minutes", "seconds", "microseconds"} {
		lib("Duration."+unit, "integer -> Duration", "durationUnit"+strconv.Itoa(index))
	}
	for _, kind := range []string{"Time", "NaiveDateTime", "DateTime"} {
		lib(kind+".add", kind+", integer, atom -> "+kind, "cal"+kind+"AddUnit ctx where")
		lib(kind+".diff", kind+", "+kind+", atom -> integer", "cal"+kind+"DiffUnit ctx where")
		lib(kind+".truncate", kind+", atom -> "+kind, "cal"+kind+"Truncate ctx where")
	}
	lib("Date.range", "Date, Date -> stream[Date]", "calDateRange")
	lib("Date.range", "Date, Date, integer -> stream[Date]", "calDateRangeStep ctx where")
	lib("Date.day_of_week", "Date, atom -> integer", "calDayOfWeekFrom ctx where")
	lib("Date.beginning_of_week", "Date, atom -> Date", "calWeekStartFrom ctx where")
	lib("Date.end_of_week", "Date, atom -> Date", "calWeekEndFrom ctx where")
	lib("Date.week_of_year", "Date -> integer", "calWeekOfYear")
	lib("Duration.new!", "list[tuple[atom,integer]] -> Duration", "durationNew ctx where")
	lib("Duration.add", "Duration, Duration -> Duration", "durationAdd")
	lib("Duration.subtract", "Duration, Duration -> Duration", "durationSubtract")
	lib("Duration.negate", "Duration -> Duration", "durationNegate")
	lib("Duration.multiply", "Duration, integer -> Duration", "durationMultiply")
	lib("Duration.to_iso8601", "Duration -> string", "durationIso")
	lib("Duration.from_iso8601", "string -> result[Duration,string]", "durationParse")
	lib("DateTime.shift_zone", "DateTime, string -> result[DateTime,string]", "calShiftZone")
	lib("DateTime.shift_zone!", "DateTime, string -> DateTime", "calShiftZoneBang ctx where")
	lib("DateTime.now", "string -> result[DateTime,string]", "calNowIn")
	lib("DateTime.from_naive", "NaiveDateTime, string -> result[DateTime,string]", "calFromNaiveIn")
	lib("Date.new", "integer, integer, integer -> result[Date,string]", "calDateNew")
	lib("Date.new!", "integer, integer, integer -> Date", "calDateNewBang ctx where")
	lib("Date.utc_today", "-> Date", "calDateToday")
	lib("Date.from_iso8601", "string -> result[Date,string]", "calDateParse")
	lib("Date.from_iso8601!", "string -> Date", "calDateParseBang ctx where")
	lib("Date.day_of_week", "Date -> integer", "calDayOfWeek")
	lib("Date.day_of_year", "Date -> integer", "calDayOfYear")
	lib("Date.days_in_month", "Date -> integer", "calDaysInMonth")
	lib("Date.leap_year?", "Date -> boolean", "calLeapYear")
	lib("Date.quarter_of_year", "Date -> integer", "calQuarter")
	lib("Date.beginning_of_month", "Date -> Date", "calMonthStart")
	lib("Date.end_of_month", "Date -> Date", "calMonthEnd")
	lib("Date.beginning_of_week", "Date -> Date", "calWeekStart")
	lib("Date.end_of_week", "Date -> Date", "calWeekEnd")

	lib("Time.new", "integer, integer, integer -> result[Time,string]", "calTimeNew")
	lib("Time.new", "integer, integer, integer, integer -> result[Time,string]", "calTimeNewMicro")
	lib("Time.new!", "integer, integer, integer -> Time", "calTimeNewBang ctx where")
	lib("Time.utc_now", "-> Time", "calTimeNow")
	lib("Time.from_iso8601", "string -> result[Time,string]", "calTimeParse")
	lib("Time.from_iso8601!", "string -> Time", "calTimeParseBang ctx where")

	lib("NaiveDateTime.new", "integer, integer, integer, integer, integer, integer -> result[NaiveDateTime,string]", "calNaiveNew")
	lib("NaiveDateTime.new!", "integer, integer, integer, integer, integer, integer -> NaiveDateTime", "calNaiveNewBang ctx where")
	lib("NaiveDateTime.new", "Date, Time -> result[NaiveDateTime,string]", "calNaiveJoin")
	lib("NaiveDateTime.new!", "Date, Time -> NaiveDateTime", "calNaiveJoinBang ctx where")
	lib("NaiveDateTime.utc_now", "-> NaiveDateTime", "calNaiveNow")
	lib("NaiveDateTime.from_iso8601", "string -> result[NaiveDateTime,string]", "calNaiveParse")
	lib("NaiveDateTime.from_iso8601!", "string -> NaiveDateTime", "calNaiveParseBang ctx where")
	lib("NaiveDateTime.to_date", "NaiveDateTime -> Date", "calNaiveDate")
	lib("NaiveDateTime.to_time", "NaiveDateTime -> Time", "calNaiveTime")

	lib("DateTime.utc_now", "-> DateTime", "calDateTimeNow")
	lib("DateTime.from_unix", "integer -> result[DateTime,string]", "calFromUnix")
	lib("DateTime.from_unix!", "integer -> DateTime", "calFromUnixBang ctx where")
	lib("DateTime.to_unix", "DateTime -> integer", "calToUnix")
	lib("DateTime.from_iso8601", "string -> result[tuple[DateTime,integer],string]", "calDateTimeParse")
	lib("DateTime.from_naive!", "NaiveDateTime -> DateTime", "calFromNaive ctx where")
	lib("DateTime.to_naive", "DateTime -> NaiveDateTime", "calToNaive")
	lib("DateTime.to_date", "DateTime -> Date", "calDateTimeDate")
	lib("DateTime.to_time", "DateTime -> Time", "calDateTimeTime")
}
