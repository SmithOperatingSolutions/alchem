# Provenance

Alchem borrows Elixir's ideas: module and function names, the shape of its standard library, pipes, pattern matching and the conventions of its documentation. Names, signatures and the behaviour they describe are what make the two familiar to the same people; they are not copied text. Alchem's documentation, examples and code are written for Alchem.

Elixir is distributed under the Apache License 2.0, the license Alchem uses. Alchem is not Elixir, is not affiliated with or endorsed by the Elixir team, and "Elixir" is used here only to describe what Alchem resembles.

## Checking for copied text

`tools/provenance` compares Alchem's documentation with an Elixir source tree, word for word:

```bash
git clone --depth 1 --branch v1.20.5 https://github.com/elixir-lang/elixir /tmp/elixir
go run ./tools/provenance -elixir /tmp/elixir
```

It reads the library and syntax documentation (`compiler/syntax`), the guide, `docs/` and the README, and reports every run of 10 or more consecutive words, compared case-insensitively without punctuation, that also appears in Elixir's `.ex`, `.exs` and Markdown files. Its exit status is 1 when it finds one. The generated reference pages are skipped because they repeat the sources it does read.

## Result

Against Elixir v1.20.5 the check reports no shared passages.

The first run found no shared prose. It found short examples whose values matched Elixir's: calls on `[1, 2, 3]`, keyword lists of `a:`, `b:` and `c:`, and a few distinctive ones such as the date in the `Calendar.strftime` example and `Integer.extended_gcd(240, 46)`. Those examples were given different values; every example is still run by the documentation tests.

At 8 words the remaining matches are lists of names that any description of the same thing would use, such as calendar field names and the ANSI colour names, and examples like `List.flatten([[1], [2, 3]])` that have no other natural form.
