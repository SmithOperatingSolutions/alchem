# Alchem

Alchem is a statically typed, Elixir-inspired language that compiles to native executables. Source files end in `.alc`. Its syntax resembles Elixir but it is a different language: types are checked at compile time, there is no `nil`, macros are templates rather than code run by the compiler, and the standard library is its own. Do not assume Elixir or Hex behaviour; look it up.

The `alchem` command documents itself, and what it prints always matches the installed compiler. Before writing or changing Alchem code, run:

```
alchem agent-guide
```

It lists the commands, the syntax topics and the library modules, and how to ask for more:

- `alchem syntax <topic>`: one construct with its rules and a working example (`alchem syntax` lists the topics).
- `alchem doc <Module>`: the functions of a library module; `alchem doc <Module.function>`: signatures and examples.
- `alchem doc --group <group>` and `alchem syntax --group <group>`: one group of modules or topics, with what each is for.
- `alchem doc --search <text>`: find functions and topics by name or description.
- `alchem doc <file.alc>`: the documentation written in a project file.

While working:

1. `alchem check --json <entry.alc>` after each change; fix every diagnostic before going on.
2. `alchem fmt <path>` to format.
3. `alchem test <path>` to run `*_test.alc` files; add `--seed N` to repeat a failing order.
4. Document public functions with `@doc` and `alx>` examples, and run them with `doctest Module` in a test file.
