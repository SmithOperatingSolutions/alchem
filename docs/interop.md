# Go interop

An `extern` declaration gives a Go function or method an Alchem name and type. It can then be called, piped into and referenced with `&name` like any other function.

```elixir
defmodule App do
  extern upper(text: string): string = "strings.ToUpper"
  extern repeat(text: string, count: integer): string = "strings.Repeat"
  extern atoi(text: string): result[integer, string] = "strconv.Atoi"

  def main() do
    IO.puts(upper("hello") |> repeat(2))
  end
end
```

The target is `"import/path.Function"`: the Go import path, a dot, and an exported function. `"import/path.Type.Method"` names a method; its receiver is the first parameter. A target that starts with `./` or `../` names a directory of Go files relative to the declaring `.alc` file, for example `"./native.Banner"`. Those files are copied into the build (test files are not) and may import the standard library and any required module.

Every declaration is checked against the Go declaration it names, by `alchem check` as well as `alchem build`, and a mismatch is reported at the `extern` line:

```
main.alc:2:10: extern repeat: parameter count: cannot pass string as Go int
```

## Types across the boundary

| Alchem | Go |
| --- | --- |
| `integer` | any integer type, including named ones such as `time.Duration` |
| `float` | `float64` or `float32` |
| `boolean` | `bool` |
| `string` | `string` or `[]byte` |
| `list[T]` | a slice; as the last parameter it also fills a variadic `...T` |
| `map[K,V]` | a map |
| a struct | a Go struct, or a pointer to one |
| `fn[A,R]` | a Go function value, in either direction |
| an `extern type` | exactly that Go type, or an interface it implements |
| any of the first six | `any` (an empty interface) parameter, as its natural Go value |

Results follow the Go result list:

| Declared result | Go results |
| --- | --- |
| none | none; callable only as a statement |
| `T` | one value |
| `tuple[A,B,...]` | several values |
| `result[T,string]` | `(T, error)`; the error text becomes `error(text)` |
| `result[tuple[],string]` | `error` alone; success is `ok({})` |
| `result[tuple[A,B],string]` | `(A, B, error)` |
| `option[T]` | `(T, bool)`, or a single pointer where `nil` is `none` |

An integer that does not fit the Go parameter, or a Go result that does not fit 64 signed bits, fails the calling process with `integer out of range for Go int32` (naming the type involved) instead of wrapping. Lists, maps and structs are copied in each direction.

## Go types as handles

```elixir
extern type Builder = "*strings.Builder"
extern new_builder(): Builder = "./native.NewBuilder"
extern write(builder: Builder, text: string): result[integer, string] = "strings.Builder.WriteString"
extern text(builder: Builder): string = "strings.Builder.String"
```

`extern type` names a Go type, with a leading `*` for a pointer, as an opaque Alchem type. Values of it come from and go to `extern` functions and can be bound, passed, stored and returned, but have no fields or patterns. Because the Go value behind a handle may be mutable, handles cannot be compared with `==` and cannot be sent to another process. A handle is accepted wherever Go expects an interface its type implements, so a `*os.File` handle can be passed as an `io.Reader`. A pointer handle can call both pointer-receiver and value-receiver methods.

## Structs and callbacks

An Alchem struct maps to a Go struct, or a pointer to one, field by field. Each Alchem field needs an exported Go field with the same name, ignoring case and underscores (`user_id` matches `UserID`); extra Go fields are left at their zero value when passing in and ignored when coming back. A `nil` struct pointer coming back fails the process with `Go returned a nil *pkg.Type`, unless the result is declared `option[...]`.

An Alchem function passed to Go arrives as an ordinary Go function; Go may call it any number of times, on the calling goroutine, before the extern returns. It must not keep it for later or call it from another goroutine. A Go function returned to Alchem becomes an ordinary function value.

Go functions that are generic, or that need an interface implemented in Alchem, cannot be bound directly; wrap them in a local Go package.

## Dependencies

```elixir
require "github.com/google/uuid" "v1.6.0"
extern new_id(): string = "github.com/google/uuid.NewString"
```

`require` adds a Go module at an exact version to the generated build. Any module of the program may declare requirements; two different versions of one module are a compile error. Programs with requirements run `go mod tidy` in the temporary build directory, which resolves indirect dependencies and verifies checksums through the Go checksum database and against `alchem.lock` (see [modules](modules.md)). Programs without `require` never touch the network or the module cache.

## Runtime behaviour

Go code runs on the calling process's goroutine. A Go panic fails that process like any Alchem failure, so monitors, links and supervisors observe it. Cancellation is cooperative: a blocking Go call is not interrupted when its process is stopped. Go strings are passed through unchanged, so a Go function can return text that is not valid UTF-8.
