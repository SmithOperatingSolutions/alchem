package syntax

func init() {
	doc("Enum.all?", "Reports whether every element is true, or satisfies the function.",
		"alx> Enum.all?([2, 4, 6], fn n -> rem(n, 2) == 0 end)", "true", "alx> Enum.all?([true, false])", "false")
	doc("Enum.any?", "Reports whether any element is true, or satisfies the function.",
		"alx> Enum.any?([1, 2, 3], &(&1 > 2))", "true", "alx> Enum.any?([false, false])", "false")
	doc("Enum.at", "Returns the element at a zero-based index as an option, or the given default. Negative indexes count from the end.",
		"alx> Enum.at([10, 20, 30], 1)", "some(20)", "alx> Enum.at([10, 20, 30], -1)", "some(30)", "alx> Enum.at([10, 20, 30], 9, 0)", "0")
	doc("Enum.chunk_by", "Splits into lists, starting a new one each time the function's result changes.",
		"alx> Enum.chunk_by([1, 3, 2, 4, 5], &(rem(&1, 2) == 1))", "[[1, 3], [2, 4], [5]]")
	doc("Enum.chunk_every", "Splits into lists of count elements; with a step, a new chunk starts every step elements. The last chunk may be shorter.",
		"alx> Enum.chunk_every([10, 20, 30, 40, 50], 2)", "[[10, 20], [30, 40], [50]]", "alx> Enum.chunk_every([5, 6, 7, 8], 3, 1)", "[[5, 6, 7], [6, 7, 8]]")
	doc("Enum.concat", "Joins two enumerables, or a list of lists, into one list.",
		"alx> Enum.concat([1, 2], 3..4)", "[1, 2, 3, 4]", "alx> Enum.concat([[1], [2, 3]])", "[1, 2, 3]")
	doc("Enum.count", "Counts the elements, or those satisfying the function.",
		"alx> Enum.count([1, 2, 3])", "3", "alx> Enum.count([1, 2, 3], &(&1 > 1))", "2")
	doc("Enum.count_until", "Counts elements, or those satisfying the function, stopping at the limit.",
		"alx> Enum.count_until(1..1000000, 5)", "5", "alx> Enum.count_until([1, 2, 3], &(&1 > 1), 10)", "2")
	doc("Enum.dedup", "Removes consecutive duplicate elements.",
		"alx> Enum.dedup([1, 1, 2, 2, 1])", "[1, 2, 1]")
	doc("Enum.dedup_by", "Removes consecutive elements for which the function returns the same value.",
		"alx> Enum.dedup_by([1, 3, 2, 4, 5], &rem(&1, 2))", "[1, 2, 5]")
	doc("Enum.drop", "Drops the first count elements, or the last when count is negative.",
		"alx> Enum.drop([1, 2, 3, 4], 1)", "[2, 3, 4]", "alx> Enum.drop([1, 2, 3, 4], -1)", "[1, 2, 3]")
	doc("Enum.drop_every", "Drops every nth element, starting with the first.",
		"alx> Enum.drop_every([1, 2, 3, 4, 5], 2)", "[2, 4]")
	doc("Enum.drop_while", "Drops elements from the start while the function returns true.",
		"alx> Enum.drop_while([1, 2, 3, 1], &(&1 < 3))", "[3, 1]")
	doc("Enum.each", "Calls the function with each element, for its effect.",
		"alx> Enum.each([\"a\", \"b\"], fn text -> IO.write(text) end)")
	doc("Enum.empty?", "Reports whether there are no elements.",
		"alx> Enum.empty?([1])", "false", "alx> Enum.empty?(Enum.filter([1], &(&1 > 5)))", "true")
	doc("Enum.fetch", "Returns the element at an index as an option.",
		"alx> Enum.fetch([10, 20], 1)", "some(20)", "alx> Enum.fetch([10, 20], 5)", "none")
	doc("Enum.fetch!", "Returns the element at an index, failing when it is out of bounds.",
		"alx> Enum.fetch!([10, 20], 0)", "10")
	doc("Enum.filter", "Keeps the elements for which the function returns true.",
		"alx> Enum.filter([1, 2, 3, 4], fn n -> rem(n, 2) == 0 end)", "[2, 4]")
	doc("Enum.find", "Returns the first element satisfying the function, as an option or with a default.",
		"alx> Enum.find([1, 2, 3], &(&1 > 1))", "some(2)", "alx> Enum.find([1, 2, 3], 0, &(&1 > 5))", "0")
	doc("Enum.find_index", "Returns the index of the first element satisfying the function.",
		"alx> Enum.find_index([\"a\", \"b\"], &(&1 == \"b\"))", "some(1)")
	doc("Enum.find_value", "Returns the first some(...) the function produces.",
		"alx> Enum.find_value([1, 2, 3], fn n -> if n > 1 do some(n * 10) else none end end)", "some(20)")
	doc("Enum.flat_map", "Maps each element to a list and concatenates the results.",
		"alx> Enum.flat_map([1, 2], fn n -> [n, n * 10] end)", "[1, 10, 2, 20]")
	doc("Enum.flat_map_reduce", "Maps to lists and threads an accumulator, returning the concatenation and the final accumulator.",
		"alx> Enum.flat_map_reduce([1, 2], 0, fn n, acc -> {[n, n], acc + n} end)", "{[1, 1, 2, 2], 3}")
	doc("Enum.frequencies", "Counts how often each element occurs.",
		"alx> Enum.frequencies([\"a\", \"b\", \"a\"])", "%{\"a\" => 2, \"b\" => 1}")
	doc("Enum.frequencies_by", "Counts how often each result of the function occurs.",
		"alx> Enum.frequencies_by([\"aa\", \"b\", \"cc\"], &String.length(&1))", "%{1 => 1, 2 => 2}")
	doc("Enum.group_by", "Groups elements into a map keyed by the function's result; a second function transforms the grouped values.",
		"alx> Enum.group_by([1, 2, 3, 4], &rem(&1, 2))", "%{0 => [2, 4], 1 => [1, 3]}",
		"alx> Enum.group_by([\"ant\", \"bee\", \"asp\"], &String.slice(&1, 0, 1), &String.length(&1))", "%{\"a\" => [3, 3], \"b\" => [3]}")
	doc("Enum.intersperse", "Places the separator between elements.",
		"alx> Enum.intersperse([\"a\", \"b\", \"c\"], \"/\")", "[\"a\", \"/\", \"b\", \"/\", \"c\"]")
	doc("Enum.join", "Joins strings, integers, floats or booleans into a string, with an optional separator.",
		"alx> Enum.join([1, 2, 3], \", \")", "\"1, 2, 3\"", "alx> Enum.join([\"a\", \"b\"])", "\"ab\"")
	doc("Enum.map", "Returns a list with the function applied to each element.",
		"alx> Enum.map([1, 2, 3], fn n -> n * 2 end)", "[2, 4, 6]", "alx> Enum.map(%{\"a\" => 1}, fn {key, value} -> \"#{key}=#{value}\" end)", "[\"a=1\"]")
	doc("Enum.map_every", "Applies the function to every nth element, starting with the first.",
		"alx> Enum.map_every([1, 2, 3, 4, 5], 2, &(&1 * 10))", "[10, 2, 30, 4, 50]")
	doc("Enum.map_intersperse", "Maps each element and places the separator between the results.",
		"alx> Enum.map_intersperse([1, 2], \"-\", &Integer.to_string(&1))", "[\"1\", \"-\", \"2\"]")
	doc("Enum.map_join", "Maps each element and joins the results into a string.",
		"alx> Enum.map_join([4, 5, 6], \"+\", &(&1 * 10))", "\"40+50+60\"")
	doc("Enum.map_reduce", "Maps while threading an accumulator, returning the mapped list and the final accumulator.",
		"alx> Enum.map_reduce([5, 6, 7], 0, fn n, acc -> {n * 2, acc + n} end)", "{[10, 12, 14], 18}")
	doc("Enum.max", "Returns the greatest element. On an empty enumerable it fails, or returns what the given function returns.",
		"alx> Enum.max([3, 9, 2])", "9", "alx> Enum.max(Enum.take([1], 0), fn -> 0 end)", "0")
	doc("Enum.max_by", "Returns the element for which the function's result is greatest.",
		"alx> Enum.max_by([\"a\", \"ccc\", \"bb\"], &String.length(&1))", "\"ccc\"")
	doc("Enum.member?", "Reports whether the enumerable contains the value. The in operator does the same.",
		"alx> Enum.member?([1, 2, 3], 2)", "true", "alx> 5 in 1..3", "false")
	doc("Enum.min", "Returns the least element. On an empty enumerable it fails, or returns what the given function returns.",
		"alx> Enum.min([3, 9, 2])", "2", "alx> Enum.min(Enum.take([1], 0), fn -> 0 end)", "0")
	doc("Enum.min_by", "Returns the element for which the function's result is least.",
		"alx> Enum.min_by([\"ccc\", \"a\", \"bb\"], &String.length(&1))", "\"a\"")
	doc("Enum.min_max", "Returns the least and greatest elements as a tuple.",
		"alx> Enum.min_max([3, 9, 2])", "{2, 9}")
	doc("Enum.min_max_by", "Returns the elements with the least and greatest function results.",
		"alx> Enum.min_max_by([\"ccc\", \"a\", \"bb\"], &String.length(&1))", "{\"a\", \"ccc\"}")
	doc("Enum.product", "Multiplies integers or floats.",
		"alx> Enum.product([2, 3, 4])", "24")
	doc("Enum.product_by", "Multiplies the function's results.",
		"alx> Enum.product_by([1, 2, 3], &(&1 + 1))", "24")
	doc("Enum.random", "Returns a random element; fails on an empty enumerable. Seeded by ALCHEM_SEED.",
		"alx> Enum.random([7, 7, 7])", "7")
	doc("Enum.reduce", "Folds the elements into one value. The function takes the element first, then the accumulator; without an initial value the first element starts.",
		"alx> Enum.reduce([1, 2, 3], 0, fn n, acc -> acc + n end)", "6", "alx> Enum.reduce([1, 2, 3], &(&1 * &2))", "6")
	doc("Enum.reduce_while", "Folds until the function returns halt(acc); cont(acc) continues.",
		"alx> Enum.reduce_while(1..100, 0, fn n, acc -> if acc > 5 do halt(acc) else cont(acc + n) end end)", "6")
	doc("Enum.reject", "Drops the elements for which the function returns true.",
		"alx> Enum.reject([1, 2, 3, 4], &(rem(&1, 2) == 0))", "[1, 3]")
	doc("Enum.reverse", "Reverses the elements; with a second enumerable, appends it after the reversed elements.",
		"alx> Enum.reverse([1, 2, 3])", "[3, 2, 1]", "alx> Enum.reverse([1, 2], [9])", "[2, 1, 9]")
	doc("Enum.reverse_slice", "Reverses count elements starting at an index.",
		"alx> Enum.reverse_slice([10, 20, 30, 40, 50], 1, 3)", "[10, 40, 30, 20, 50]")
	doc("Enum.scan", "Returns every intermediate result of a fold.",
		"alx> Enum.scan([1, 2, 3, 4], &(&1 + &2))", "[1, 3, 6, 10]", "alx> Enum.scan([1, 2], 10, &(&1 + &2))", "[11, 13]")
	doc("Enum.shuffle", "Returns the elements in random order. Seeded by ALCHEM_SEED.",
		"alx> Enum.sort(Enum.shuffle([3, 1, 2]))", "[1, 2, 3]")
	doc("Enum.slice", "Returns count elements starting at an index, or the elements at a range of indexes; a negative index counts from the end.",
		"alx> Enum.slice([10, 20, 30, 40, 50], 1, 3)", "[20, 30, 40]", "alx> Enum.slice([10, 20, 30, 40, 50], -2, 2)", "[40, 50]", "alx> Enum.slice([10, 20, 30, 40, 50], 1..-2)", "[20, 30, 40]")
	doc("Enum.sort", "Sorts ascending, or by a function saying whether its first argument may come before its second.",
		"alx> Enum.sort([3, 1, 2])", "[1, 2, 3]", "alx> Enum.sort([3, 1, 2], &(&1 >= &2))", "[3, 2, 1]")
	doc("Enum.sort_by", "Sorts by the function's result, optionally with a sorter for those results.",
		"alx> Enum.sort_by([\"ccc\", \"a\", \"bb\"], &String.length(&1))", "[\"a\", \"bb\", \"ccc\"]",
		"alx> Enum.sort_by([\"ccc\", \"a\", \"bb\"], &String.length(&1), &(&1 >= &2))", "[\"ccc\", \"bb\", \"a\"]")
	doc("Enum.split", "Splits into the first count elements and the rest.",
		"alx> Enum.split([1, 2, 3], 2)", "{[1, 2], [3]}")
	doc("Enum.split_while", "Splits at the first element for which the function returns false.",
		"alx> Enum.split_while([1, 2, 3, 1], &(&1 < 3))", "{[1, 2], [3, 1]}")
	doc("Enum.split_with", "Partitions into the elements that satisfy the function and those that do not.",
		"alx> Enum.split_with([1, 2, 3, 4], &(rem(&1, 2) == 0))", "{[2, 4], [1, 3]}")
	doc("Enum.sum", "Adds integers or floats.",
		"alx> Enum.sum(1..100)", "5050", "alx> Enum.sum([1.5, 2.5])", "4.0")
	doc("Enum.sum_by", "Adds the function's results.",
		"alx> Enum.sum_by([\"a\", \"bb\"], &String.length(&1))", "3")
	doc("Enum.take", "Takes the first count elements, or the last when count is negative.",
		"alx> Enum.take([1, 2, 3], 2)", "[1, 2]", "alx> Enum.take([1, 2, 3], -1)", "[3]")
	doc("Enum.take_every", "Takes every nth element, starting with the first.",
		"alx> Enum.take_every([1, 2, 3, 4, 5], 2)", "[1, 3, 5]")
	doc("Enum.take_random", "Takes count random elements. Seeded by ALCHEM_SEED.",
		"alx> length(Enum.take_random([1, 2, 3, 4], 2))", "2")
	doc("Enum.take_while", "Takes elements from the start while the function returns true.",
		"alx> Enum.take_while([1, 2, 3, 1], &(&1 < 3))", "[1, 2]")
	doc("Enum.to_list", "Collects any enumerable into a list.",
		"alx> Enum.to_list(1..3)", "[1, 2, 3]", "alx> Enum.to_list(%{\"a\" => 1})", "[{\"a\", 1}]")
	doc("Enum.uniq", "Removes duplicate elements, keeping the first of each.",
		"alx> Enum.uniq([1, 2, 1, 3, 2])", "[1, 2, 3]")
	doc("Enum.uniq_by", "Removes elements whose function result has been seen before.",
		"alx> Enum.uniq_by([\"a\", \"bb\", \"c\"], &String.length(&1))", "[\"a\", \"bb\"]")
	doc("Enum.unzip", "Splits a list of pairs into a pair of lists.",
		"alx> Enum.unzip([{1, \"a\"}, {2, \"b\"}])", "{[1, 2], [\"a\", \"b\"]}")
	doc("Enum.with_index", "Pairs each element with its index, optionally starting from an offset.",
		"alx> Enum.with_index([\"a\", \"b\"])", "[{\"a\", 0}, {\"b\", 1}]", "alx> Enum.with_index([\"a\"], 5)", "[{\"a\", 5}]")
	doc("Enum.zip", "Pairs elements of two enumerables, stopping at the shorter.",
		"alx> Enum.zip([1, 2, 3], [\"a\", \"b\"])", "[{1, \"a\"}, {2, \"b\"}]")
	doc("Enum.zip_reduce", "Folds over the paired elements of two enumerables.",
		"alx> Enum.zip_reduce([2, 3], [4, 5], 0, fn a, b, acc -> acc + a * b end)", "23")
	doc("Enum.zip_with", "Combines paired elements of two enumerables with the function.",
		"alx> Enum.zip_with([1, 2], [10, 20], &(&1 + &2))", "[11, 22]")

	doc("Stream.chunk_by", "Lazily splits into lists, starting a new one each time the function's result changes.",
		"alx> Stream.chunk_by([1, 1, 2, 3, 3], &(&1)) |> Enum.to_list()", "[[1, 1], [2], [3, 3]]")
	doc("Stream.chunk_every", "Lazily splits into lists of count elements, optionally starting one every step elements.",
		"alx> Stream.chunk_every(11..18, 3) |> Enum.to_list()", "[[11, 12, 13], [14, 15, 16], [17, 18]]",
		"alx> Stream.from_index() |> Stream.chunk_every(2) |> Enum.take(2)", "[[0, 1], [2, 3]]")
	doc("Stream.concat", "Lazily joins two enumerables, or a list of lists.",
		"alx> Stream.concat([7, 8], 9..10) |> Enum.to_list()", "[7, 8, 9, 10]")
	doc("Stream.cycle", "Repeats an enumerable forever.",
		"alx> Stream.cycle([1, 2]) |> Enum.take(5)", "[1, 2, 1, 2, 1]")
	doc("Stream.dedup", "Lazily removes consecutive duplicates.",
		"alx> Stream.dedup([5, 5, 6, 5]) |> Enum.to_list()", "[5, 6, 5]")
	doc("Stream.dedup_by", "Lazily removes consecutive elements with the same function result.",
		"alx> Stream.dedup_by([1, 3, 2], &rem(&1, 2)) |> Enum.to_list()", "[1, 2]")
	doc("Stream.drop", "Lazily drops the first count elements.",
		"alx> Stream.drop(1..5, 3) |> Enum.to_list()", "[4, 5]")
	doc("Stream.drop_every", "Lazily drops every nth element, starting with the first.",
		"alx> Stream.drop_every(1..6, 2) |> Enum.to_list()", "[2, 4, 6]")
	doc("Stream.drop_while", "Lazily drops elements while the function returns true.",
		"alx> Stream.drop_while(1..6, &(&1 < 4)) |> Enum.to_list()", "[4, 5, 6]")
	doc("Stream.duplicate", "A stream of the value repeated count times.",
		"alx> Stream.duplicate(\"ab\", 3) |> Enum.to_list()", "[\"ab\", \"ab\", \"ab\"]")
	doc("Stream.each", "Calls the function with each element as it passes through, leaving the elements unchanged.",
		"alx> Stream.each([1, 2], fn n -> IO.write(Integer.to_string(n)) end) |> Enum.to_list()", "[1, 2]")
	doc("Stream.filter", "Lazily keeps elements for which the function returns true.",
		"alx> Stream.filter(1..10, &(rem(&1, 3) == 0)) |> Enum.to_list()", "[3, 6, 9]")
	doc("Stream.flat_map", "Lazily maps each element to a list and concatenates.",
		"alx> Stream.flat_map(1..2, fn n -> [n, -n] end) |> Enum.to_list()", "[1, -1, 2, -2]")
	doc("Stream.from_index", "The integers from 0, or from the given start, without end.",
		"alx> Stream.from_index() |> Enum.take(3)", "[0, 1, 2]", "alx> Stream.from_index(5) |> Enum.take(2)", "[5, 6]")
	doc("Stream.intersperse", "Lazily places the separator between elements.",
		"alx> Stream.intersperse(4..6, 0) |> Enum.to_list()", "[4, 0, 5, 0, 6]")
	doc("Stream.interval", "Emits 0, 1, 2, ... waiting the given milliseconds before each.",
		"alx> Stream.interval(1) |> Enum.take(3)", "[0, 1, 2]")
	doc("Stream.iterate", "Starts with a value and keeps applying the function to the previous one.",
		"alx> Stream.iterate(3, &(&1 * 3)) |> Enum.take(4)", "[3, 9, 27, 81]")
	doc("Stream.map", "Lazily applies the function to each element.",
		"alx> Stream.map(1..1000000000, &(&1 * 2)) |> Enum.take(3)", "[2, 4, 6]")
	doc("Stream.map_every", "Lazily applies the function to every nth element.",
		"alx> Stream.map_every(1..5, 2, &(&1 * 10)) |> Enum.to_list()", "[10, 2, 30, 4, 50]")
	doc("Stream.reject", "Lazily drops elements for which the function returns true.",
		"alx> Stream.reject(1..6, &(rem(&1, 2) == 0)) |> Enum.to_list()", "[1, 3, 5]")
	doc("Stream.repeatedly", "Calls the function for each element, without end.",
		"alx> Stream.repeatedly(fn -> \"x\" end) |> Enum.take(2)", "[\"x\", \"x\"]")
	doc("Stream.resource", "Builds a stream from a start function, a next function returning some({items, state}) or none, and a cleanup function that always runs.",
		"alx> counter = Stream.resource(fn -> 3 end, fn n -> if n == 0 do none else some({[n], n - 1}) end end, fn _ -> 0 end)",
		"alx> Enum.to_list(counter)", "[3, 2, 1]")
	doc("Stream.run", "Consumes a stream for its effects.",
		"alx> Stream.run(Stream.each(1..2, fn n -> IO.write(Integer.to_string(n)) end))")
	doc("Stream.scan", "Lazily emits every intermediate result of a fold.",
		"alx> Stream.scan(1..4, &(&1 + &2)) |> Enum.to_list()", "[1, 3, 6, 10]")
	doc("Stream.take", "Lazily takes the first count elements.",
		"alx> Stream.take(Stream.cycle([1]), 3) |> Enum.to_list()", "[1, 1, 1]")
	doc("Stream.take_every", "Lazily takes every nth element, starting with the first.",
		"alx> Stream.take_every(1..10, 4) |> Enum.to_list()", "[1, 5, 9]")
	doc("Stream.take_while", "Lazily takes elements while the function returns true.",
		"alx> Stream.take_while(Stream.from_index(), &(&1 < 3)) |> Enum.to_list()", "[0, 1, 2]")
	doc("Stream.timer", "Emits 0 once, after the given milliseconds.",
		"alx> Stream.timer(1) |> Enum.to_list()", "[0]")
	doc("Stream.transform", "Maps with state: the function returns some({items, state}) to emit and continue, or none to stop.",
		"alx> Stream.transform(1..10, 0, fn n, total -> if total + n > 6 do none else some({[total + n], total + n}) end end) |> Enum.to_list()", "[1, 3, 6]")
	doc("Stream.unfold", "Generates values from a state: the function returns some({value, next_state}), or none to stop.",
		"alx> Stream.unfold(1, fn n -> if n > 20 do none else some({n, n * 3}) end end) |> Enum.to_list()", "[1, 3, 9]")
	doc("Stream.uniq", "Lazily removes elements seen before.",
		"alx> Stream.uniq(Stream.cycle([1, 2, 3])) |> Enum.take(3)", "[1, 2, 3]")
	doc("Stream.uniq_by", "Lazily removes elements whose function result was seen before.",
		"alx> Stream.uniq_by([\"a\", \"b\", \"cc\"], &String.length(&1)) |> Enum.to_list()", "[\"a\", \"cc\"]")
	doc("Stream.with_index", "Lazily pairs each element with its index.",
		"alx> Stream.with_index([\"a\", \"b\"]) |> Enum.to_list()", "[{\"a\", 0}, {\"b\", 1}]")
	doc("Stream.zip", "Lazily pairs elements of two enumerables.",
		"alx> Stream.zip(Stream.from_index(), [\"a\", \"b\"]) |> Enum.to_list()", "[{0, \"a\"}, {1, \"b\"}]")
	doc("Stream.zip_with", "Lazily combines paired elements with the function.",
		"alx> Stream.zip_with(1..3, Stream.cycle([10]), &(&1 + &2)) |> Enum.to_list()", "[11, 12, 13]")

	legacy("map", "map(list[a], fn[a,b]) -> list[b]")
	legacy("filter", "filter(list[a], fn[a,boolean]) -> list[a]")
	legacy("reduce", "reduce(list[a], b, fn[b,a,b]) -> b")
	legacy("prepend", "prepend(list[a], a) -> list[a]")
	legacy("concat", "concat(list[a], list[a]) -> list[a]")
	legacy("length", "length(list[a]) -> integer", "length(map[k,v]) -> integer", "length(tuple) -> integer")
	legacy("put", "put(map[k,v], k, v) -> map[k,v]")
	legacy("get", "get(map[k,v], k, v) -> v")
	legacy("has_key", "has_key(map[k,v], k) -> boolean")
	legacy("raise", "raise(string)", "raise(Exception)")
	legacy("throw", "throw(a)")
	doc("map", "Applies a named or annotated function to each element of a list. Enum.map also accepts inferred functions and any enumerable.",
		"alx> map([1, 2, 3], fn(n: integer): integer do n * 2 end)", "[2, 4, 6]")
	doc("filter", "Keeps the list elements for which the function returns true. See also Enum.filter.",
		"alx> filter([1, 2, 3], fn(n: integer): boolean do n > 1 end)", "[2, 3]")
	doc("reduce", "Folds a list; the function takes the accumulator first, then the element. Enum.reduce takes them the other way round.",
		"alx> reduce([1, 2, 3], 0, fn(acc: integer, n: integer): integer do acc + n end)", "6")
	doc("prepend", "Returns the list with the value added at the front, in constant time.",
		"alx> prepend([2, 3], 1)", "[1, 2, 3]")
	doc("concat", "Joins two lists. The ++ operator does the same.",
		"alx> concat([1], [2, 3])", "[1, 2, 3]", "alx> [1] ++ [2, 3]", "[1, 2, 3]")
	doc("length", "The number of elements of a list, entries of a map, or positions of a tuple.",
		"alx> length([1, 2, 3])", "3", "alx> length(%{\"a\" => 1})", "1")
	doc("put", "Returns the map with the key set to the value. Map.put does the same.",
		"alx> put(%{\"x\" => 1}, \"y\", 2)", "%{\"x\" => 1, \"y\" => 2}")
	doc("get", "Returns the value for the key, or the default when it is absent.",
		"alx> get(%{\"a\" => 1}, \"z\", 0)", "0")
	doc("has_key", "Reports whether the map has the key. Map.has_key? does the same.",
		"alx> has_key(%{\"a\" => 1}, \"a\")", "true")
	doc("raise", "Fails the current process with a message, or with an exception declared by defexception, whose message field is the message. try/rescue can catch it: e in Name binds the exception.",
		"alx> try do raise(\"boom\") rescue message -> message end", "\"boom\"")
	doc("throw", "Unwinds to the nearest enclosing try with a catch arm for the value's type, leaving loops and calls on the way. Uncaught, it fails the process with \"uncaught throw\".",
		"alx> try do", "...>   Enum.each([1, 4, 9], fn n -> if n > 3 do throw(n) end end)", "...>   0", "...> catch", "...>   n -> n", "...> end", "4")

	legacy("List.reverse", "List.reverse(list[a]) -> list[a]")
	legacy("List.take", "List.take(list[a], integer) -> list[a]")
	legacy("List.drop", "List.drop(list[a], integer) -> list[a]")
	legacy("List.contains", "List.contains(list[a], a) -> boolean")
	legacy("List.sort", "List.sort(list[a]) -> list[a]")
	legacy("List.range", "List.range(integer, integer) -> list[integer]")
	legacy("List.zip", "List.zip(list[a], list[b]) -> list[tuple[a,b]]")
	doc("List.reverse", "Reverses a list.", "alx> List.reverse([1, 2, 3])", "[3, 2, 1]")
	doc("List.take", "Takes the first count elements, sharing storage with the original.", "alx> List.take([1, 2, 3], 2)", "[1, 2]")
	doc("List.drop", "Drops the first count elements, sharing storage with the original.", "alx> List.drop([1, 2, 3], 2)", "[3]")
	doc("List.contains", "Reports whether the list contains the value.", "alx> List.contains([1, 2, 3], 2)", "true")
	doc("List.sort", "Sorts a list of integers, floats or strings ascending.", "alx> List.sort([3, 1, 2])", "[1, 2, 3]")
	doc("List.range", "The integers from first to last inclusive, as a list; empty when last is below first.", "alx> List.range(1, 4)", "[1, 2, 3, 4]")
	doc("List.zip", "Pairs the elements of two lists.", "alx> List.zip([1, 2], [\"a\", \"b\"])", "[{1, \"a\"}, {2, \"b\"}]")
	doc("List.delete", "Removes the first occurrence of a value.", "alx> List.delete([1, 2, 1], 1)", "[2, 1]")
	doc("List.delete_at", "Removes the element at an index; negative indexes count from the end.", "alx> List.delete_at([1, 2, 3], -1)", "[1, 2]")
	doc("List.duplicate", "A list of the value repeated count times.", "alx> List.duplicate(\"a\", 3)", "[\"a\", \"a\", \"a\"]")
	doc("List.ends_with?", "Reports whether the list ends with the given elements.", "alx> List.ends_with?([1, 2, 3], [2, 3])", "true")
	doc("List.first", "The first element as an option, or the default for an empty list.", "alx> List.first([1, 2])", "some(1)", "alx> List.first(Enum.take([1], 0), 0)", "0")
	doc("List.first!", "The first element; fails on an empty list.", "alx> List.first!([1, 2])", "1")
	doc("List.flatten", "Concatenates a list of lists, one level deep.", "alx> List.flatten([[1], [2, 3]])", "[1, 2, 3]")
	doc("List.foldl", "Folds from the left; the function takes the element, then the accumulator.", "alx> List.foldl([1, 2, 3], \"\", fn n, acc -> acc <> Integer.to_string(n) end)", "\"123\"")
	doc("List.foldr", "Folds from the right.", "alx> List.foldr([1, 2, 3], \"\", fn n, acc -> acc <> Integer.to_string(n) end)", "\"321\"")
	doc("List.insert_at", "Inserts a value at an index; -1 appends.", "alx> List.insert_at([1, 3], 1, 2)", "[1, 2, 3]", "alx> List.insert_at([1, 2], -1, 3)", "[1, 2, 3]")
	doc("List.last", "The last element as an option, or the default for an empty list.", "alx> List.last([1, 2])", "some(2)")
	doc("List.last!", "The last element; fails on an empty list.", "alx> List.last!([1, 2])", "2")
	doc("List.pop_at", "Removes the element at an index, returning it as an option with the remaining list.", "alx> List.pop_at([1, 2, 3], 1)", "{some(2), [1, 3]}")
	doc("List.replace_at", "Replaces the element at an index.", "alx> List.replace_at([4, 5, 6], 1, 0)", "[4, 0, 6]")
	doc("List.starts_with?", "Reports whether the list starts with the given elements.", "alx> List.starts_with?([1, 2, 3], [1, 2])", "true")
	doc("List.update_at", "Applies the function to the element at an index.", "alx> List.update_at([4, 5, 6], 0, &(&1 * 10))", "[40, 5, 6]")

	legacy("Map.keys", "Map.keys(map[k,v]) -> list[k]")
	legacy("Map.values", "Map.values(map[k,v]) -> list[v]")
	legacy("Map.entries", "Map.entries(map[k,v]) -> list[tuple[k,v]]")
	legacy("Map.delete", "Map.delete(map[k,v], k) -> map[k,v]")
	legacy("Map.merge", "Map.merge(map[k,v], map[k,v]) -> map[k,v]")
	doc("Map.keys", "The keys in ascending order.", "alx> Map.keys(%{\"b\" => 2, \"a\" => 1})", "[\"a\", \"b\"]")
	doc("Map.values", "The values in ascending key order.", "alx> Map.values(%{\"b\" => 2, \"a\" => 1})", "[1, 2]")
	doc("Map.entries", "The {key, value} pairs in ascending key order. Map.to_list does the same.", "alx> Map.entries(%{\"a\" => 1})", "[{\"a\", 1}]")
	doc("Map.delete", "Returns the map without the key.", "alx> Map.delete(%{\"x\" => 1, \"y\" => 2}, \"x\")", "%{\"y\" => 2}")
	doc("Map.merge", "Merges two maps, the second winning on shared keys; a function may resolve those instead.",
		"alx> Map.merge(%{\"a\" => 1}, %{\"a\" => 5, \"b\" => 2})", "%{\"a\" => 5, \"b\" => 2}",
		"alx> Map.merge(%{\"a\" => 1}, %{\"a\" => 5}, fn _, left, right -> left + right end)", "%{\"a\" => 6}")
	doc("Map.drop", "Returns the map without the given keys.", "alx> Map.drop(%{\"x\" => 1, \"y\" => 2}, [\"x\"])", "%{\"y\" => 2}")
	doc("Map.equal?", "Reports whether two maps hold the same entries.", "alx> Map.equal?(%{\"a\" => 1}, %{\"a\" => 1})", "true")
	doc("Map.fetch", "The value for a key as an option.", "alx> Map.fetch(%{\"a\" => 1}, \"a\")", "some(1)")
	doc("Map.fetch!", "The value for a key; fails when it is absent.", "alx> Map.fetch!(%{\"a\" => 1}, \"a\")", "1")
	doc("Map.filter", "Keeps the entries for which the function returns true.", "alx> Map.filter(%{\"a\" => 1, \"b\" => 9}, fn {_, value} -> value > 5 end)", "%{\"b\" => 9}")
	doc("Map.from_keys", "A map with every given key set to one value.", "alx> Map.from_keys([\"a\", \"b\"], 0)", "%{\"a\" => 0, \"b\" => 0}")
	doc("Map.get", "The value for a key as an option, or the default when it is absent.", "alx> Map.get(%{\"a\" => 1}, \"a\")", "some(1)", "alx> Map.get(%{\"a\" => 1}, \"z\", 0)", "0")
	doc("Map.get_lazy", "The value for a key, calling the function only when it is absent.", "alx> Map.get_lazy(%{\"a\" => 1}, \"z\", fn -> 99 end)", "99")
	doc("Map.has_key?", "Reports whether the map has the key.", "alx> Map.has_key?(%{\"a\" => 1}, \"a\")", "true")
	doc("Map.intersect", "Keeps the keys both maps have, with the second map's values.", "alx> Map.intersect(%{\"a\" => 1, \"b\" => 2}, %{\"b\" => 0})", "%{\"b\" => 0}")
	doc("Map.new", "Builds a map from {key, value} pairs, or from elements transformed into pairs.", "alx> Map.new([{\"x\", 7}, {\"y\", 8}])", "%{\"x\" => 7, \"y\" => 8}", "alx> Map.new([1, 2], fn n -> {n, n * n} end)", "%{1 => 1, 2 => 4}")
	doc("Map.pop", "Removes a key, returning its value (an option, or the default) with the remaining map.", "alx> Map.pop(%{\"a\" => 1}, \"a\")", "{some(1), Map.delete(%{\"a\" => 1}, \"a\")}")
	doc("Map.put", "Returns the map with the key set to the value.", "alx> Map.put(%{\"x\" => 1}, \"y\", 2)", "%{\"x\" => 1, \"y\" => 2}")
	doc("Map.put_new", "Sets the key only when it is absent.", "alx> Map.put_new(%{\"a\" => 1}, \"a\", 9)", "%{\"a\" => 1}")
	doc("Map.put_new_lazy", "Sets the key from the function only when it is absent.", "alx> Map.put_new_lazy(%{\"a\" => 1}, \"b\", fn -> 2 end)", "%{\"a\" => 1, \"b\" => 2}")
	doc("Map.reject", "Drops the entries for which the function returns true.", "alx> Map.reject(%{\"a\" => 1, \"b\" => 9}, fn {_, value} -> value > 5 end)", "%{\"a\" => 1}")
	doc("Map.replace", "Sets the key only when it is present.", "alx> Map.replace(%{\"a\" => 1}, \"z\", 9)", "%{\"a\" => 1}")
	doc("Map.replace!", "Sets the key; fails when it is absent.", "alx> Map.replace!(%{\"a\" => 1}, \"a\", 9)", "%{\"a\" => 9}")
	doc("Map.split", "Splits into the entries with the given keys and the rest.", "alx> Map.split(%{\"a\" => 1, \"b\" => 2}, [\"a\"])", "{%{\"a\" => 1}, %{\"b\" => 2}}")
	doc("Map.split_with", "Partitions the entries by the function.", "alx> Map.split_with(%{\"a\" => 1, \"b\" => 9}, fn {_, value} -> value > 5 end)", "{%{\"b\" => 9}, %{\"a\" => 1}}")
	doc("Map.take", "Keeps only the given keys.", "alx> Map.take(%{\"a\" => 1, \"b\" => 2}, [\"a\", \"z\"])", "%{\"a\" => 1}")
	doc("Map.to_list", "The {key, value} pairs in ascending key order.", "alx> Map.to_list(%{\"a\" => 1})", "[{\"a\", 1}]")
	doc("Map.update", "Applies the function to the key's value, or sets the default when the key is absent.", "alx> Map.update(%{\"a\" => 1}, \"a\", 0, &(&1 + 1))", "%{\"a\" => 2}")
	doc("Map.update!", "Applies the function to the key's value; fails when it is absent.", "alx> Map.update!(%{\"a\" => 1}, \"a\", &(&1 * 5))", "%{\"a\" => 5}")

	doc("MapSet.delete", "Returns the set without the value.", "alx> MapSet.delete(MapSet.new([1, 2]), 1) |> MapSet.to_list()", "[2]")
	doc("MapSet.difference", "The elements of the first set that are not in the second.", "alx> MapSet.difference(MapSet.new([4, 5, 6]), MapSet.new([5])) |> MapSet.to_list()", "[4, 6]")
	doc("MapSet.disjoint?", "Reports whether two sets share no elements.", "alx> MapSet.disjoint?(MapSet.new([1]), MapSet.new([2]))", "true")
	doc("MapSet.equal?", "Reports whether two sets hold the same elements.", "alx> MapSet.equal?(MapSet.new([3, 4]), MapSet.new([4, 3]))", "true")
	doc("MapSet.filter", "Keeps the elements for which the function returns true.", "alx> MapSet.filter(MapSet.new(1..5), &(&1 > 3)) |> MapSet.to_list()", "[4, 5]")
	doc("MapSet.intersection", "The elements in both sets.", "alx> MapSet.intersection(MapSet.new([3, 4]), MapSet.new([4, 5])) |> MapSet.to_list()", "[4]")
	doc("MapSet.member?", "Reports whether the set contains the value.", "alx> MapSet.member?(MapSet.new([1, 2]), 2)", "true")
	doc("MapSet.new", "Builds a set from an enumerable, optionally transforming each element. With no arguments, an empty set whose type comes from its annotation.",
		"alx> MapSet.new([3, 1, 3]) |> MapSet.to_list()", "[1, 3]", "alx> MapSet.new([\"a\", \"bb\"], &String.length(&1)) |> MapSet.to_list()", "[1, 2]")
	doc("MapSet.put", "Returns the set with the value added.", "alx> MapSet.put(MapSet.new([1]), 2) |> MapSet.to_list()", "[1, 2]")
	doc("MapSet.reject", "Drops the elements for which the function returns true.", "alx> MapSet.reject(MapSet.new(1..5), &(&1 > 2)) |> MapSet.to_list()", "[1, 2]")
	doc("MapSet.size", "The number of elements.", "alx> MapSet.size(MapSet.new([1, 1, 2]))", "2")
	doc("MapSet.split_with", "Partitions the set by the function.", "alx> MapSet.split_with(MapSet.new(1..3), &(&1 == 2)) == {MapSet.new([2]), MapSet.new([1, 3])}", "true")
	doc("MapSet.subset?", "Reports whether every element of the first set is in the second.", "alx> MapSet.subset?(MapSet.new([1]), MapSet.new([1, 2]))", "true")
	doc("MapSet.symmetric_difference", "The elements in exactly one of the sets.", "alx> MapSet.symmetric_difference(MapSet.new([3, 4]), MapSet.new([4, 5])) |> MapSet.to_list()", "[3, 5]")
	doc("MapSet.to_list", "The elements in ascending order.", "alx> MapSet.to_list(MapSet.new([3, 1, 2]))", "[1, 2, 3]")
	doc("MapSet.union", "The elements in either set.", "alx> MapSet.union(MapSet.new([1]), MapSet.new([2])) |> MapSet.to_list()", "[1, 2]")
}
