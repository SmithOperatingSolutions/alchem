# `extern` is out of the language

`extern` gave an Alchem name to a Go function, method or type:

```elixir
extern sqrt(value: float): float = "math.Sqrt"
extern type Buffer = "*bytes.Buffer"
```

It could only mean something while a program was compiled to Go. The native `alchem` compiles a program itself, with no Go to call, and it is what Alchem is moving to ([native/](../native/README.md)), so `extern` and `extern type` are gone, and with them `require` of a Go module and Go packages beside a program.

- **The native `alchem` refuses a program with an `extern`**, at the declaration, and names the library function to use where there is one:

  ```
  main.alc:2:10: extern is no longer in the language: sqrt was bound to the Go function "math.Sqrt", and a program is not built with Go; use Float.pow(value, 0.5)
  ```

- **The Go `alchem` still takes it** until it is retired, so that older programs build with the releases that have it. Nothing new should use it.

## What to write instead

| Go function | Alchem |
| --- | --- |
| `strconv.Atoi` | `Integer.parse` |
| `strconv.ParseFloat` | `Float.parse` |
| `strconv.Itoa` | `Integer.to_string` |
| `os.LookupEnv`, `os.Getenv` | `System.get_env` |
| `os.Setenv` | `System.put_env` |
| `os.ReadFile`, `os.WriteFile` | `File.read`, `File.write` |
| `strings.ToUpper`, `strings.ToLower` | `String.upcase`, `String.downcase` |
| `strings.TrimSpace` | `String.trim` |
| `strings.Contains` | `String.contains?` |
| `strings.HasPrefix`, `strings.HasSuffix` | `String.starts_with?`, `String.ends_with?` |
| `strings.Split`, `strings.Join` | `String.split`, `Enum.join` |
| `strings.Repeat` | `String.duplicate` |
| `strings.ReplaceAll` | `String.replace` |
| `math.Sqrt` | `Float.pow(value, 0.5)` |
| `math.Pow`, `math.Floor`, `math.Ceil`, `math.Abs` | `Float.pow`, `Float.floor`, `Float.ceil`, `abs` |

The [library reference](library-reference.md) has the rest: files, the environment, time, JSON, HTTP, TCP and TLS, cryptography, processes. A program that needs another program's work runs it with `System.cmd` or `Port`. What the library does not have is written in Alchem, in the program or in a [package](modules.md).

Nothing replaces `extern` as a way to call code in another language. A way to call a C function from a native program would be a feature of its own.
