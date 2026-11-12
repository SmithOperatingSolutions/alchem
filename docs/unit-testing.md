# Testing Alchem programs

Tests live in files whose names end in `_test.alc`. A test file is a module with `test` blocks in place of `main`; it imports the modules it tests.

```elixir
defmodule CartTest do
  import "../lib/cart.alc"

  setup do
    File.mkdir_p("tmp")
  end

  test "totals price times quantity" do
    assert(Cart.total(basket()) == 1550)
  end

  describe "discount" do
    test "takes a percentage off" do
      assert(Cart.discount(1000, 25) == 750)
    end

    describe "at the limits" do
      test "rejects a percentage out of range" do
        assert_raise("percent must be between", fn -> Cart.discount(1000, 150) end)
      end
    end
  end
end
```

Run them with `alchem test`, naming files or directories; directories are searched for `*_test.alc` at any depth. `examples/testing` is a complete project.

```sh
alchem test examples/testing
alchem test --trace --only discount examples/testing
alchem test --seed 230331 --cover --cover-min 80 examples/testing
```

## Tests, describes and setup

- `test "name" do ... end` declares a test. A test passes when its body finishes and fails when anything in it fails: an assertion, a runtime failure such as division by zero, or a `raise`.
- `describe "name" do ... end` groups tests, and describes nest up to 16 deep. A test is reported under every describe around it: `test discount at the limits rejects a percentage out of range`.
- `setup_all do ... end` runs once before the file's tests; see Context below.
- `setup do ... end` runs before each test it applies to: every test in the file when written at the top level, and every test inside the describe that contains it, however deeply nested. Setups run outermost first, then in the order written. A setup that fails fails the test.
- A test file may also define ordinary functions, as helpers. It cannot define `main`.

Each test runs in its own process, so a failure in one cannot affect the next, and a test that runs longer than `--timeout` (30 seconds by default) is stopped and reported. Tests in a file run one after another.

## Context

A setup block's last expression is the context it provides. The setup blocks and tests beneath it receive that context by naming a parameter, a pattern after `setup`, or after the test's name and a comma:

```elixir
setup_all do
  Database.connect()
end

setup connection do
  %Context{connection: connection, user: insert_user(connection)}
end

test "finds the user", %Context{connection: connection, user: user} do
  assert(Users.find(connection, user.id) == some(user))
end
```

- `setup_all` runs once, before any test in the file, in the runner's process. It must be at the top level.
- Setup blocks run before each test, from the outermost describe inwards and in the order written. Each may receive the context in effect at that point and, by ending in a value, replace it for what follows. A block that ends in a statement leaves the context unchanged.
- A test or setup block that takes a context when no block above it provides one does not compile. Taking one is optional.
- The context has whatever type the providing block returns; a struct is usual. It is typed, so a test cannot ask for a field that is not there.

## Tags

```elixir
@moduletag "unit"

@tag "slow"
test "imports the whole catalogue" do ... end

@tag "db"
describe "persistence" do ... end
```

`@tag` marks the test or describe that follows, a describe passing its tags to everything inside it, `@describetag` marks the describe that follows, and `@moduletag` marks every test in the file. A tag is a name, `"slow"` or `:slow`, or names with values:

```elixir
@tag kind: :db, owner: "ada"
test "stores an order" do ... end
```

`--tag slow,db` runs only tests carrying one of those tags and `--exclude slow` leaves them out. A name alone matches the tag with any value, and `name:value` only that value: `--tag kind:db`. A test tagged `skip`, or `skip: "reason"`, does not run unless `--tag skip` asks for it. `@tag timeout: 500` gives one test its own time limit in milliseconds, and `timeout: :infinity` none.

## Properties

`check all` runs a block for many generated values, and when it fails, shrinks the value to the smallest that still fails:

```elixir
test "a sorted list is ordered" do
  check all list <- Gen.list_of(Gen.integer()),
            extra <- Gen.integer(),
            extra > 0,
            max_runs: 200 do
    sorted = Enum.sort([extra | list])
    assert(Enum.all?(Enum.zip(sorted, Enum.drop(sorted, 1)), fn {a, b} -> a <= b end))
  end
end
```

Generators come from the `Gen` module: `integer` with or without bounds, `positive_integer`, `float`, `boolean`, `string` of a kind of character, `list_of`, `map_of`, `tuple`, `member_of`, `one_of`, `constant`, and `map`, `filter`, `bind` and `resize` to build others; `Gen.sample(generator, n)` shows what one makes. A generator may use what the ones before it bound, and a condition among them drops the values that fail it. Values grow with each run: 100 runs unless `max_runs:` or `ALCHEM_PROPERTY_RUNS` says otherwise. They come from the test seed, so `alchem test --seed N` repeats a failure, which reports the shrunk value:

```
property failed after 4 of 100 runs; smallest failing value, after 31 shrinking steps:
{[0, 0, 0], 5}
assertion failed
```

## Doctests

`doctest Module` in a test file turns the examples in that module's documentation into tests. Documentation is the `@doc` string above a function; an example is a line starting with `alx>`, continued by lines starting with `...>`, followed by the value it should equal:

```elixir
@doc """
Doubles a number.

    alx> Calc.double(4)
    8
    alx> n = Calc.double(1)
    alx> Calc.double(n)
    4
"""
def double(n: integer): integer do
  n * 2
end
```

Comments are not documentation: an `alx>` line in a `#` comment is not run. `alchem doc calc.alc` prints a file's documentation, and the examples the compiler shows for its own library (`alchem doc Enum.map`) are checked the same way.

Each documented function becomes one test, `doctest Calc.double/1`, in which the examples run in order and share their bindings. An example with no result line is simply run. Calls must be qualified, as from any other module, and the module must be imported by the test file. The expected value is compared with `==`, so it must be of a type that supports equality.

## Assertions

| Assertion | Passes when |
| --- | --- |
| `assert(condition)` | the condition is true |
| `refute(condition)` | the condition is false |
| `assert_raise(text, fn -> ... end)` | the function fails with a reason containing `text` |
| `assert_in_delta(a, b, delta)` | two floats differ by at most `delta` |
| `flunk(message)` | never; fails with the message |
| `assert_receive(self, pattern)` | a message matching the pattern is in the test's own mailbox or arrives within the wait; a third argument sets the wait in milliseconds and a fourth replaces the first line of the failure |
| `refute_receive(self, pattern)` | no message matching the pattern is there or arrives in that time; `_` means any message |
| `assert_received(self, pattern)`, `refute_received(self, pattern)` | the same, looking only at messages that have already arrived; an argument after the pattern is the failure message |

Two helpers work with any assertion. `capture_io(fn -> ... end)` runs the function and returns what was written to standard output meanwhile. `on_exit(fn -> ... end)` registers a function to run when the test ends, whether it passed or failed; several run last first, and one that fails makes the test fail. `assert_receive` and `refute_receive` are statements whose second argument is a pattern, not a value. `assert_receive` searches the mailbox for the first message that matches and takes it out, leaving the others in their order, so messages may arrive in any order. Names in the pattern are bound for the rest of the test, `^name` compares with an existing binding, and `when` adds a guard: `assert_receive(me, {"progress", percent} when percent > 50, 500)`. The wait is 100 milliseconds unless the test gives one or `alchem test --receive-timeout 500ms` changes the default. When nothing matches in time the failure shows the pattern, the values of the names it pins and the last ten messages in the mailbox:

```
  1) test worker reports (WorkerTest)
     worker_test.alc:12:5: no message matching the pattern arrived within 100ms
          pattern: {^wanted, n} when (n > 3)
          pinned:  wanted = "b"
          mailbox: {"a", 1}, {"a", 2}
```

Unlike ExUnit, the process is named, because a mailbox has a type; a name the pattern binds must be new, because bindings are immutable; and exit and monitor notices are read with `Process.event`, not from the mailbox. A mailbox has the capacity given to `Process.self`: messages that no assertion takes stay in it, and once it is full a sender waits, so give the test's mailbox room for everything it will be sent.

A test may call `Process.self` to get a mailbox for `assert_receive`:

```elixir
test "worker replies" do
  me: pid[string] = Process.self(4)
  on_exit(fn -> File.rm!("worker.log") end)
  Worker.start(me)
  assert_receive(me, "ready")
  assert(capture_io(fn -> Worker.report() end) == "1 job\n")
end
```

In a test file a failed `assert` reports the expression, and for a comparison both sides as `inspect` prints them:

```
  1) test compares structs (FlakyTest)
     flaky_test.alc:7
     flaky_test.alc:8:5: assertion failed
          code:  %FlakyTest.Point{x: 1, y: 2} == %FlakyTest.Point{x: 1, y: 3}
          left:  %Point{x: 1, y: 2}
          right: %Point{x: 1, y: 3}
       at test compares structs (flaky_test.alc:8)
```

## Seeds

Test files run in a random order, and so do the tests inside each. Every run ends by printing `Randomized with seed N`. Passing `--seed N` repeats that run exactly: the same order, and the same values from `Enum.random`, `Enum.shuffle` and `Enum.take_random`, which are seeded from it. A failure that depends on order or on a random value can therefore be reproduced from the seed its run printed.

## Options

| Option | Effect |
| --- | --- |
| `--seed N` | repeat the run that printed seed `N` |
| `--only text` | run only tests whose full name, or whose module's name, contains the text; the rest are counted as excluded |
| `--tag a,b` | run only tests carrying one of these tags |
| `--exclude a,b` | leave out tests carrying one of these tags |
| `--trace` | print each test with its duration instead of a dot |
| `--max-failures N` | stop each test file after `N` failures; the tests not run are counted as skipped |
| `--timeout d` | the limit for one test, such as `5s` |
| `--jobs N` | compile and run `N` test files at once; one per processor by default, and `1` runs them one at a time. The output is in the same order either way |
| `--receive-timeout d` | how long `assert_receive` and `refute_receive` wait when a test gives no timeout; `100ms` by default |
| `--cover` | report line coverage |
| `--cover-min P` | with `--cover`, fail when total coverage is below `P` percent |

The command exits with status 1 when a test fails, a test file does not compile, or coverage is below the minimum.

## Coverage

`--cover` counts how often each statement of the code under test runs and reports, per file, the share of its statements' lines that ran at least once, followed by the lines that did not:

```
Percentage | File
-----------|--------------------------
     75.0% | examples/testing/lib/cart.alc
-----------|--------------------------
     75.0% | Total

examples/testing/lib/cart.alc: lines not run: 31, 36-37
```

Only files imported by a test file appear: a module no test imports is not in the report at all, rather than at 0%. The test files themselves are not counted. A line counts as run when any statement starting on it ran, so one line holding an `if` with both branches is covered by either branch.

## Output fixtures

A directory without test files is still run the earlier way: each `.alc` program is built and run and its output compared with the `.stdout` file beside it. See [testing](testing.md).
