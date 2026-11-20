#!/usr/bin/env python3
"""Gen and the assertions: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error, environment, standard input) as the pinned compiler runs it
RUNS=[('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(1, 6), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-9223372036854775807, 9223372036854775807), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-5, -5), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.positive_integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.float(), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.boolean(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.constant("c"), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.integer()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.boolean(), 2, 3), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:alphanumeric), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:printable), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:ascii), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:digit), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.member_of([:red, :green, :blue]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.one_of([Gen.constant(0), Gen.integer(10, 20)]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map(Gen.integer(), fn n -> n * 2 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.filter(Gen.integer(), fn n -> n != 0 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.bind(Gen.integer(0, 3), fn n -> Gen.list_of(Gen.constant(n), n, n) end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(0, 1), Gen.string(:lower)), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(), Gen.boolean(), Gen.float()), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map_of(Gen.integer(1, 3), Gen.boolean()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.integer(), 3), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.list_of(Gen.string(:lower)), 2), 5)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 0)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), -3)))\n'
  '    IO.puts(inspect(length(Gen.sample(Gen.list_of(Gen.integer()), 150))))\n'
  '  end\n'
  'end\n',
  0,
  b'[0, 0, 3, -3, 2, 5, 1, -3, -6, -4, 3, -7]\n[3, 4, 6, 2, 5, 6, 4, 2, 2, 2, 4, 2]\n[-2052914667195242427, 217999193850928602, 883086974628171847'
  b'5, -5217792744183480545]\n[-5, -5, -5]\n[2, 2, 4, 2, 5, 7, 5, 3, 2, 4, 8, 3]\n[-0.8386262221697354, -1.1889102547904882, -0.45904812739306755, '
  b'1.6690861483364463, 1.8025881141863975, -3.4642713164813546]\n[true, false, true, true, true, true, false, true, true, true, true, true]\n["c"'
  b', "c", "c"]\n[[0], [-1, 1], [0, -1, -2], [1], [-4], [-1, 0, 1, -6, 1], [], [6, 0, -7, -6, 2, 3, 1]]\n[[false, true, true], [true, false, true]'
  b', [true, true, true], [false, false, true], [false, false, false], [false, true, false]]\n["F", "nR", "Jtm", "N", "l", "CGJeK", "", "0FhhNRJ"'
  b']\n["L", "pY", "Pwo", "U", "n", "HLPfR", "", "9KiiUZP"]\n["P", "4b", "V=2", "\\\\", "0", "KQU&X"]\n["5", "26", "531", "6", "1", "45505"]\n[:gr'
  b'een, :green, :blue, :red, :blue, :blue, :green, :red, :red, :red]\n[15, 12, 20, 0, 12, 17, 11, 0, 0, 16]\n[0, 0, 6, -6, 4, 10, 2, -6, -12, -8]'
  b'\n[1, -1, 1, 4, 1, -2, -5, -3, 3, -6]\n[[1], [3, 3, 3], [1], [], [1], [3, 3, 3], [3, 3, 3], [2, 2], [3, 3, 3], []]\n[{1, ""}, {1, ""}, {1, "oif'
  b'"}, {1, "fev"}, {0, "obp"}, {0, "vnddq"}]\n[{0, false, -0.15301604246435585}, {-1, true, -1.1547571054937849}, {0, true, -2.1851743392845178}, {-'
  b'2, true, 3.447137107028758}]\n[%{2 => true}, %{}, %{3 => false}, %{1 => true}, %{1 => true, 2 => true, 3 => false}, %{}, %{}, %{1 => false, 2 => '
  b'false, 3 => false}]\n[-1, 0, 3, -2, 1, 3, 0, -1, -2, -1, 1, -2]\n[["z"], [], ["oi", ""], [], [""]]\n[]\n[]\n150\n',
  b'',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(1, 6), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-9223372036854775807, 9223372036854775807), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-5, -5), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.positive_integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.float(), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.boolean(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.constant("c"), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.integer()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.boolean(), 2, 3), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:alphanumeric), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:printable), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:ascii), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:digit), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.member_of([:red, :green, :blue]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.one_of([Gen.constant(0), Gen.integer(10, 20)]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map(Gen.integer(), fn n -> n * 2 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.filter(Gen.integer(), fn n -> n != 0 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.bind(Gen.integer(0, 3), fn n -> Gen.list_of(Gen.constant(n), n, n) end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(0, 1), Gen.string(:lower)), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(), Gen.boolean(), Gen.float()), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map_of(Gen.integer(1, 3), Gen.boolean()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.integer(), 3), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.list_of(Gen.string(:lower)), 2), 5)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 0)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), -3)))\n'
  '    IO.puts(inspect(length(Gen.sample(Gen.list_of(Gen.integer()), 150))))\n'
  '  end\n'
  'end\n',
  0,
  b'[0, -2, 2, 1, 5, 2, -6, 1, 2, -10, -9, -11]\n[4, 1, 5, 4, 6, 4, 1, 4, 4, 1, 1, 1]\n[2793761116638984326, -9182380692956331714, 400234629027634'
  b'8276, 2960269934410481981]\n[-5, -5, -5]\n[1, 1, 1, 4, 6, 5, 6, 5, 7, 1, 2, 1]\n[-0.6604166009824142, 0.20381352255222307, -0.9017976072707166,'
  b' 1.2478722304952585, -1.1063235193955978, 4.142861393984549]\n[false, false, false, true, false, false, true, true, false, false, true, true]'
  b'\n["c", "c", "c"]\n[[], [], [], [4, 1, -3], [1, -5, -4], [], [-7, -3, 6, 2, 5], [0, -2, 5, 5, 2, 4, -5, 3]]\n[[false, false], [false, false, tr'
  b'ue], [false, false, true], [true, false, false], [false, false], [false, true]]\n["", "", "", "7Mh", "Mbh", "", "as5OY", "FwYWLVoR"]\n["", "",'
  b' "", "\xe3\x81\x82Tj", "Scj", "", "bv\xc3\xb8V7", "LA74S3rY"]\n["", "", "", "{[+", "Z\\"+", ""]\n["", "", "", "961", "601", ""]\n[:green, :red,'
  b' :blue, :green, :blue, :green, :red, :green, :green, :red]\n[0, 0, 0, 20, 0, 15, 0, 0, 10, 10]\n[0, -4, 4, 2, 10, 4, -12, 2, 4, -20]\n[-1, 1, 1'
  b', 4, 1, -5, 2, -8, -7, -9]\n[[2, 2], [], [2, 2], [1], [2, 2], [3, 3, 3], [1], [], [2, 2], []]\n[{0, ""}, {0, "z"}, {0, "n"}, {0, ""}, {1, ""},'
  b' {1, ""}]\n[{0, false, -0.3005992024235722}, {1, false, 1.3809537979948496}, {-3, true, -1.6931260496294196}, {-4, true, -2.7803645279322327}'
  b']\n[%{}, %{}, %{}, %{1 => true, 2 => false, 3 => false}, %{}, %{}, %{1 => false, 2 => true, 3 => true}, %{2 => true, 3 => false}]\n[1, -3, 2, '
  b'1, 3, 1, -3, 0, 1, -3, -3, -3]\n[[""], ["z", "d"], ["a"], [], []]\n[]\n[]\n150\n',
  b'',
  {'ALCHEM_SEED': '12345678901234567890'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(1, 6), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-9223372036854775807, 9223372036854775807), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-5, -5), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.positive_integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.float(), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.boolean(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.constant("c"), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.integer()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.boolean(), 2, 3), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:alphanumeric), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:printable), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:ascii), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:digit), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.member_of([:red, :green, :blue]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.one_of([Gen.constant(0), Gen.integer(10, 20)]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map(Gen.integer(), fn n -> n * 2 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.filter(Gen.integer(), fn n -> n != 0 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.bind(Gen.integer(0, 3), fn n -> Gen.list_of(Gen.constant(n), n, n) end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(0, 1), Gen.string(:lower)), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(), Gen.boolean(), Gen.float()), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map_of(Gen.integer(1, 3), Gen.boolean()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.integer(), 3), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.list_of(Gen.string(:lower)), 2), 5)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 0)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), -3)))\n'
  '    IO.puts(inspect(length(Gen.sample(Gen.list_of(Gen.integer()), 150))))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 0, 0, -1, 1, 1, 3, -4, 4, -8, 5, 0]\n[6, 4, 3, 3, 4, 4, 5, 2, 5, 1, 5, 4]\n[7542696685863402401, 39061462597587333, -24582016283118376, -1'
  b'770572229185571405]\n[-5, -5, -5]\n[2, 2, 1, 3, 4, 5, 5, 3, 8, 2, 9, 7]\n[-0.18489431811783397, -0.6532259394496669, -1.374912281537119, -0.584'
  b'0444829687614, -4.112690637744548, -0.497573259880689]\n[true, true, false, true, false, true, false, false, true, true, false, true]\n["c", "'
  b'c", "c"]\n[[0], [0], [1, 1], [2], [], [0, -1, 3, 5], [-3, 0, 4], [-5, 8, -7, 4, 4, -1, -1, -3]]\n[[true, false, true], [true, false], [true, t'
  b'rue], [true, false], [false, true, true], [false, true, true]]\n["F", "z", "JR", "S", "", "FzS1", "qGW", "n7gRUBAv"]\n["K", "D", "PY", "0", ""'
  b', "LE0\xc3\xa9", "tL4", "p\xe3\x81\x82hZ2GFz"]\n["O", "F", "Va", "d", "", "PGdr"]\n["5", "4", "56", "7", "", "5478"]\n[:blue, :green, :green, '
  b':green, :green, :green, :blue, :red, :blue, :red]\n[15, 0, 16, 17, 0, 11, 0, 14, 19, 12]\n[2, 0, 0, -2, 2, 2, 6, -8, 8, -16]\n[1, 1, 1, 2, -3, '
  b'3, -6, 3, -2, 5]\n[[1], [], [2, 2], [], [3, 3, 3], [2, 2], [], [], [1], []]\n[{1, "m"}, {1, "o"}, {0, ""}, {1, ""}, {0, "ksw"}, {1, "n"}]\n[{1,'
  b' true, -0.45830409384570636}, {0, false, -0.165857753293563}, {1, false, -2.8620761061456124}, {-3, false, -0.25210990087875107}]\n[%{2 => false}'
  b', %{2 => true}, %{}, %{3 => true}, %{2 => false, 3 => false}, %{1 => false, 2 => false, 3 => true}, %{}, %{1 => false, 2 => true, 3 => true}]\n[3'
  b', 0, 0, -1, 1, 1, 1, -2, 2, -3, 1, 0]\n[["m", "q"], ["gs"], [], ["k", "wk"], []]\n[]\n[]\n150\n',
  b'',
  {'ALCHEM_SEED': '18446744073709551615'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(1, 6), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-9223372036854775807, 9223372036854775807), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-5, -5), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.positive_integer(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.float(), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.boolean(), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.constant("c"), 3)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.integer()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.boolean(), 2, 3), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:alphanumeric), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:printable), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:ascii), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.string(:digit), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.member_of([:red, :green, :blue]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.one_of([Gen.constant(0), Gen.integer(10, 20)]), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map(Gen.integer(), fn n -> n * 2 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.filter(Gen.integer(), fn n -> n != 0 end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.bind(Gen.integer(0, 3), fn n -> Gen.list_of(Gen.constant(n), n, n) end), 10)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(0, 1), Gen.string(:lower)), 6)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer(), Gen.boolean(), Gen.float()), 4)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.map_of(Gen.integer(1, 3), Gen.boolean()), 8)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.integer(), 3), 12)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.list_of(Gen.string(:lower)), 2), 5)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), 0)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(), -3)))\n'
  '    IO.puts(inspect(length(Gen.sample(Gen.list_of(Gen.integer()), 150))))\n'
  '  end\n'
  'end\n',
  0,
  b'[0, 2, -1, -3, 1, -1, 1, 3, 2, -10, 3, -11]\n[4, 6, 3, 1, 4, 3, 4, 5, 4, 1, 4, 1]\n[1650219871285900860, 9127479158545372976, -170442030613239'
  b'6793, -6406104940422410433]\n[-5, -5, -5]\n[1, 3, 4, 1, 4, 4, 4, 7, 6, 1, 8, 1]\n[-0.5775806408861266, -0.5849925586709119, 1.6279994958931117,'
  b' 2.2358375824585996, 0.5974703316756402, 1.0801844607179891]\n[false, false, true, true, false, false, true, true, true, false, false, false]'
  b'\n["c", "c", "c"]\n[[], [0, -2], [], [0, 2], [-5, 1, -5], [], [3, 6, -7, 0], [3, -7, 7, -8, -6, 5]]\n[[false, true], [false, false, true], [tru'
  b'e, false, false], [true, false], [true, true], [true, false, true]]\n["", "zj", "", "HQ", "bMd", "", "Q3bG", "Og2bhY"]\n["", "Dl", "", "NY", "'
  b'cSe", "", "Y\xc3\xbcbM", "Vh\xc3\xbcbj6"]\n["", "F.", "", "Sa", "#Z%", ""]\n["", "41", "", "56", "060", ""]\n[:green, :blue, :green, :red, :gre'
  b'en, :green, :green, :blue, :green, :red]\n[0, 0, 11, 0, 0, 17, 10, 0, 0, 20]\n[0, 4, -2, -6, 2, -2, 2, 6, 4, -20]\n[1, -2, 1, 1, -5, 2, -7, -8,'
  b' 9, 4]\n[[], [3, 3, 3], [], [3, 3, 3], [3, 3, 3], [2, 2], [1], [2, 2], [3, 3, 3], [3, 3, 3]]\n[{0, ""}, {1, ""}, {0, ""}, {1, "paq"}, {0, ""},'
  b' {0, "xans"}]\n[{0, false, 0.5426664986310372}, {-2, false, 0.3600614869059964}, {0, true, 1.8027609587238766}, {-4, false, -0.42150569471782795}'
  b']\n[%{}, %{2 => false}, %{1 => true, 3 => true}, %{1 => true, 3 => false}, %{}, %{}, %{}, %{1 => true, 2 => true}]\n[1, 3, -1, -2, 0, 0, 0, 1,'
  b' 1, -3, 1, -3]\n[["kd"], ["n"], ["a", "b"], [], ["xa", "s"]]\n[]\n[]\n150\n',
  b'',
  {'ALCHEM_SEED': '1'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.bind(Gen.integer(0, 3), fn n -> Gen.list_of(Gen.constant(n), n, n) end), 10), fn l -> Enum.all?(l, '
  'fn n -> n == length(l) end) end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.boolean(), 10), fn b -> b or not b end)))\n'
  '    Gen.check(Gen.integer(), fn n -> assert(n + 0 == n) end, 20)\n'
  '    IO.puts(inspect(Gen.sample(Gen.constant(7), 3)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.filter(Gen.integer(), fn n -> n != 0 end), 10), fn n -> n != 0 end)))\n'
  '    IO.puts(inspect(length(Gen.sample(Gen.float(), 5))))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.integer(1, 6), 20), fn n -> n >= 1 and n <= 6 end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.list_of(Gen.boolean(), 2, 3), 10), fn l -> length(l) >= 2 and length(l) <= 3 end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.map(Gen.integer(), fn n -> n * 2 end), 10), fn n -> rem(n, 2) == 0 end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.map_of(Gen.integer(1, 3), Gen.boolean()), 10), fn m -> map_size(m) <= 3 end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.member_of([:red, :green]), 10), fn c -> c in [:red, :green] end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.one_of([Gen.constant(0), Gen.integer(10, 20)]), 10), fn n -> n == 0 or n >= 10 end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.positive_integer(), 20), fn n -> n >= 1 end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.resize(Gen.integer(), 3), 20), fn n -> n >= -3 and n <= 3 end)))\n'
  '    IO.puts(inspect(length(Gen.sample(Gen.integer(), 4))))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.string(:digit), 10), fn s -> String.match?(s, ~r/^[0-9]*$/) end)))\n'
  '    IO.puts(inspect(Enum.all?(Gen.sample(Gen.tuple(Gen.integer(0, 1), Gen.constant("x")), 5), fn {n, s} -> n <= 1 and s == "x" end)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\ntrue\n[7, 7, 7]\ntrue\n5\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\n4\ntrue\ntrue\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Gen.sample(Gen.integer(-1000000000, 1000000000), 5) == Gen.sample(Gen.integer(-1000000000, 1000000000), 5)))\n'
  '  end\n'
  'end\n',
  0,
  b'false\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  struct User do\n'
  '    name: string\n'
  '    age: integer\n'
  '    tags: list[atom]\n'
  '  end\n'
  '  def users(): generator[User] do\n'
  '    Gen.map(Gen.tuple(Gen.string(:lower), Gen.integer(0, 120), Gen.list_of(Gen.member_of([:a, :b, :c]), 0, 2)), fn {n, a, t} -> %User{name: n, '
  'age: a, tags: t} end)\n'
  '  end\n'
  '  def twice(g: generator[a]): generator[tuple[a, a]] do\n'
  '    Gen.tuple(g, g)\n'
  '  end\n'
  '  def main() do\n'
  '    small: generator[integer] = Gen.integer(0, 9)\n'
  '    IO.puts(inspect(Gen.sample(users(), 4)))\n'
  '    IO.puts(inspect(Gen.sample(twice(small), 5)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.one_of([small, Gen.map(small, fn n -> n * 100 end)]), 8)))\n'
  '    Gen.check(users(), fn u -> assert(u.age < 60 or u.name == "") end)\n'
  '  end\n'
  'end\n',
  2,
  b'[%User{name: "n", age: 118, tags: []}, %User{name: "xo", age: 37, tags: []}, %User{name: "q", age: 25, tags: []}, %User{name: "lnob", age: 71, t'
  b'ags: [:c]}]\n[{3, 5}, {9, 2}, {6, 9}, {5, 3}, {1, 3}]\n[500, 200, 900, 3, 300, 200, 800, 5]\n',
  b'<stdin>:18:5: property failed after 1 of 100 runs; smallest failing value, after 29 shrinking steps:\n%User{name: "a", age: 60, tags: []}\nass'
  b'ertion failed\n  at Main.main (<stdin>:18)\n',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    Gen.check(Gen.integer(), fn n -> assert(n < 10) end)\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 16 of 100 runs; smallest failing value, after 15 shrinking steps:\n10\nassertion failed\n  at Main.main (<st'
  b'din>:4)\n',
  {'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.list_of(Gen.integer()), fn l -> assert(Enum.sum(l) < 20) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 12 of 100 runs; smallest failing value, after 14 shrinking steps:\n[20]\nassertion failed\n  at Main.main (<'
  b'stdin>:4)\n',
  {'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.tuple(Gen.string(:lower), Gen.float()), fn {s, f} -> assert(byte_size(s) < 3 or f < 1.0) end, 300)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 3 of 300 runs; smallest failing value, after 46 shrinking steps:\n{"aaa", 1.0}\nassertion failed\n  at Main.'
  b'main (<stdin>:4)\n',
  {'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.list_of(Gen.boolean(), 2, 8), fn l -> if Enum.count(l, fn b -> b end) > 2 do raise("too many") else 1 end end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 5 of 100 runs; smallest failing value, after 17 shrinking steps:\n[true, true, true]\ntoo many\n  at Main.ma'
  b'in (<stdin>:4)\n',
  {'ALCHEM_SEED': '11'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.map_of(Gen.integer(1, 5), Gen.string(:digit)), fn m -> assert(map_size(m) < 3) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 2 of 100 runs; smallest failing value, after 83 shrinking steps:\n%{1 => "", 2 => "", 3 => ""}\nassertion f'
  b'ailed\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '3'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.bind(Gen.integer(0, 9), fn n -> Gen.list_of(Gen.constant(n), n, n) end), fn l -> assert(length(l) < 4) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 1 of 100 runs; smallest failing value, after 3 shrinking steps:\n[4, 4, 4, 4]\nassertion failed\n  at Main.m'
  b'ain (<stdin>:4)\n',
  {'ALCHEM_SEED': '8'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.filter(Gen.integer(), fn n -> rem(n, 2) == 0 end), fn n -> assert(n > -7) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 16 of 100 runs; smallest failing value, after 3 shrinking steps:\n-8\nassertion failed\n  at Main.main (<std'
  b'in>:4)\n',
  {'ALCHEM_SEED': '8'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    IO.puts(inspect(Gen.sample(Gen.filter(Gen.integer(), fn n -> n > 1000 end), 3)))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:32: Gen.filter rejected 100 values in a row; generate more of the values wanted instead\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    Gen.check(Gen.integer(), fn n -> div(100, n) end)\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 1 of 100 runs; smallest failing value, after 0 shrinking steps:\n0\ndivision by zero\n  at Main.main (<stdin'
  b'>:4)\n',
  {'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    Gen.check(Gen.float(), fn x -> assert(x > -0.25) end)\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 2 of 100 runs; smallest failing value, after 10 shrinking steps:\n-0.25\nassertion failed\n  at Main.main (<'
  b'stdin>:4)\n',
  {'ALCHEM_SEED': '9'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.string(:printable), fn s -> refute(String.contains?(s, "\\u00e9")) end, 400)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 3 of 400 runs; smallest failing value, after 9 shrinking steps:\n"\xc3\xa9"\nrefute failed: the expression is'
  b' true\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '9'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.list_of(Gen.tuple(Gen.integer(), Gen.boolean())), fn l -> assert(length(Enum.filter(l, fn {_, b} -> b end)) < 3) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 3 of 100 runs; smallest failing value, after 30 shrinking steps:\n[{0, true}, {0, true}, {0, true}]\nassert'
  b'ion failed\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '4'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.positive_integer(), fn n -> assert(rem(n, 7) != 0) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 9 of 100 runs; smallest failing value, after 3 shrinking steps:\n7\nassertion failed\n  at Main.main (<stdin'
  b'>:4)\n',
  {'ALCHEM_SEED': '2'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.member_of([:a, :b, :c, :d]), fn a -> assert(a != :d) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 5 of 100 runs; smallest failing value, after 2 shrinking steps:\n:d\nassertion failed\n  at Main.main (<stdi'
  b'n>:4)\n',
  {'ALCHEM_SEED': '2'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.integer(-9223372036854775807, 9223372036854775807), fn n -> assert(n < 1000) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 1 of 100 runs; smallest failing value, after 139 shrinking steps:\n1000\nassertion failed\n  at Main.main (<'
  b'stdin>:4)\n',
  {'ALCHEM_SEED': '6'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.resize(Gen.list_of(Gen.integer(50, 60)), 4), fn l -> assert(length(l) < 2) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 1 of 100 runs; smallest failing value, after 10 shrinking steps:\n[50, 50]\nassertion failed\n  at Main.main'
  b' (<stdin>:4)\n',
  {'ALCHEM_SEED': '6'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.list_of(Gen.list_of(Gen.integer())), fn l -> assert(Enum.sum(Enum.map(l, fn x -> length(x) end)) < 6) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 4 of 100 runs; smallest failing value, after 62 shrinking steps:\n[[0, 0, 0, 0, 0, 0]]\nassertion failed\n  '
  b'at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '6'},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    Gen.check(Gen.integer(), fn n -> assert(n > 1000000) end, 1)\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 1 of 1 runs; smallest failing value, after 1 shrinking steps:\n0\nassertion failed\n  at Main.main (<stdin>:'
  b'4)\n',
  {'ALCHEM_SEED': '6'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    Gen.check(Gen.integer(), fn n -> flunk("always, with " <> Integer.to_string(n)) end)\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: property failed after 1 of 100 runs; smallest failing value, after 1 shrinking steps:\n0\nalways, with 0\n  at Main.main (<stdin>:'
  b'4)\n',
  {'ALCHEM_SEED': '6'},
  b''),
 ('defmodule Main do\n  def main() do\n    Gen.check(Gen.integer(), fn n -> assert(n < 30) end)\n    IO.puts("three runs are small")\n  end\nend\n',
  0,
  b'three runs are small\n',
  b'',
  {'ALCHEM_PROPERTY_RUNS': '3', 'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n  def main() do\n    Gen.check(Gen.integer(), fn n -> assert(n < 30) end)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: property failed after 19 of 400 runs; smallest failing value, after 5 shrinking steps:\n30\nassertion failed\n  at Main.main (<std'
  b'in>:3)\n',
  {'ALCHEM_PROPERTY_RUNS': '400', 'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n  def main() do\n    Gen.check(Gen.integer(), fn n -> assert(n < 30) end)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: property failed after 19 of 100 runs; smallest failing value, after 5 shrinking steps:\n30\nassertion failed\n  at Main.main (<std'
  b'in>:3)\n',
  {'ALCHEM_PROPERTY_RUNS': '-4', 'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n  def main() do\n    Gen.check(Gen.integer(), fn n -> assert(n < 30) end, 0)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: property failed after 19 of 100 runs; smallest failing value, after 5 shrinking steps:\n30\nassertion failed\n  at Main.main (<std'
  b'in>:3)\n',
  {'ALCHEM_PROPERTY_RUNS': 'x', 'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    g = Gen.integer(3, 2)\n'
  '    IO.puts(inspect(length(Gen.sample(g, 2))))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:9: Gen.integer needs its low bound no greater than its high one\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    g = Gen.list_of(Gen.integer(), -1, 3)\n'
  '    IO.puts(inspect(length(Gen.sample(g, 2))))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:9: Gen.list_of needs 0 <= min <= max\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    g = Gen.list_of(Gen.integer(), 3, 2)\n'
  '    IO.puts(inspect(length(Gen.sample(g, 2))))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:9: Gen.list_of needs 0 <= min <= max\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    g = Gen.string(:hex)\n    IO.puts(inspect(length(Gen.sample(g, 2))))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:9: Gen.string takes :alphanumeric, :alpha, :lower, :digit, :ascii or :printable\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    g = Gen.member_of(Enum.take([1], 0))\n'
  '    IO.puts(inspect(length(Gen.sample(g, 2))))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:9: Gen.member_of needs at least one value\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    g = Gen.one_of(Enum.take([Gen.integer()], 0))\n'
  '    IO.puts(inspect(length(Gen.sample(g, 2))))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:9: Gen.one_of needs at least one generator\n  at Main.main (<stdin>:4)\n',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(length(Gen.sample(Gen.list_of(Gen.integer(), 3, -1), 2))))\n'
  '    IO.puts(inspect(Gen.sample(Gen.list_of(Gen.integer(), 0, 0), 2)))\n'
  '    IO.puts(inspect(Gen.sample(Gen.resize(Gen.integer(), -5), 3)))\n'
  '  end\n'
  'end\n',
  0,
  b'2\n[[], []]\n[0, 0, 0]\n',
  b'',
  {'ALCHEM_SEED': '7'},
  b''),
 ('defmodule Main do\n'
  '  defexception Oops do\n'
  '    message: string\n'
  '    code: integer\n'
  '  end\n'
  '  def fail(n: integer, m: string): integer do\n'
  '    if n > 0 do raise(m) end\n'
  '    n\n'
  '  end\n'
  '  def oops(n: integer): integer do\n'
  '    if n > 0 do raise(%Oops{message: "bad thing", code: 2}) end\n'
  '    n\n'
  '  end\n'
  '  def trial(want: string, f: fn[integer]): string do\n'
  '    try do\n'
  '      assert_raise(want, f)\n'
  '      "passed"\n'
  '    rescue\n'
  '      m -> m\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(trial("division by zero", fn -> div(1, 0) end))\n'
  '    IO.puts(trial("zzz", fn -> div(1, 0) end))\n'
  '    IO.puts(trial("zzz", fn -> 5 end))\n'
  '    IO.puts(trial("", fn -> fail(1, "anything") end))\n'
  '    IO.puts(trial("no", fn -> fail(1, "multi\\nline \\"q\\"") end))\n'
  '    IO.puts(trial("no", fn -> fail(1, "") end))\n'
  '    IO.puts(trial("", fn -> fail(1, "") end))\n'
  '    IO.puts(trial("bad", fn -> oops(1) end))\n'
  '    IO.puts(trial("x", fn -> oops(1) end))\n'
  '    IO.puts(trial("x", fn -> hd(Enum.take([1], 0)) end))\n'
  '    IO.puts(trial("assert", fn ->\n'
  '      assert(1 == 2)\n'
  '      1\n'
  '    end))\n'
  '    IO.puts(trial("x", fn ->\n'
  '      flunk("flunked x")\n'
  '      1\n'
  '    end))\n'
  '    IO.puts(inspect(capture_io(fn -> IO.puts("hello") end)))\n'
  '    IO.puts(inspect(capture_io(fn -> 5 end)))\n'
  '    IO.puts(inspect(capture_io(fn ->\n'
  '      IO.write("a")\n'
  '      IO.puts(capture_io(fn -> IO.puts("inner") end))\n'
  '      IO.inspect({1, "x"})\n'
  '    end)))\n'
  '    IO.puts(inspect(byte_size(capture_io(fn -> IO.puts(String.duplicate("x", 300000)) end))))\n'
  '    on_exit(fn -> IO.puts("never") end)\n'
  '    IO.puts(try do\n'
  '      capture_io(fn ->\n'
  '        IO.puts("before the failure")\n'
  '        div(1, 0)\n'
  '      end)\n'
  '    rescue\n'
  '      m -> "rescued " <> m\n'
  '    end)\n'
  '    assert_raise("not reached", fn -> flunk("not reached") end)\n'
  '    refute(1 > 2)\n'
  '    assert_in_delta(0.1 + 0.2, 0.3, 0.0001)\n'
  '    IO.puts(capture_io(fn ->\n'
  '      IO.puts("lost?")\n'
  '      flunk("the end")\n'
  '    end))\n'
  '  end\n'
  'end\n',
  2,
  b'passed\nexpected a failure containing "zzz", got "division by zero"\nexpected a failure containing "zzz", but the function returned\npassed\nexp'
  b'ected a failure containing "no", got "multi\\nline \\"q\\""\nexpected a failure containing "no", but the function returned\nexpected a failure co'
  b'ntaining "", but the function returned\npassed\nexpected a failure containing "x", got "bad thing"\nexpected a failure containing "x", got "the'
  b' list is empty"\npassed\npassed\n"hello\\n"\n""\n"ainner\\n\\n{1, \\"x\\"}\\n"\n300001\nbefore the failure\nrescued division by zero\nlost?\n',
  b'<stdin>:63:7: the end\n  at Main.main <closure> (<stdin>:63)\n  at Main.main (<stdin>:61)\n',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    assert_raise("division by zero", fn -> div(1, 0) end)\n'
  '    IO.puts(inspect(capture_io(fn -> IO.puts("hello") end)))\n'
  '    assert_raise("not reached", fn -> flunk("not reached") end)\n'
  '    File.write!("doc_on_exit.txt", "temporary")\n'
  '    on_exit(fn -> File.rm!("doc_on_exit.txt") end)\n'
  '    IO.puts(inspect(File.exists?("doc_on_exit.txt")))\n'
  '    refute(1 > 2)\n'
  '    assert(1 + 1 == 2)\n'
  '    assert_in_delta(0.1 + 0.2, 0.3, 0.0001)\n'
  '  end\n'
  'end\n',
  0,
  b'"hello\\n"\ntrue\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    assert_raise("overflow", fn -> div(1, 0) end)\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:5: expected a failure containing "overflow", got "division by zero"\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    assert_raise("anything", fn -> 1 end)\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:5: expected a failure containing "anything", but the function returned\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(capture_io(fn -> IO.puts(capture_io(fn -> IO.write("deep")  end) <> "!") end) <> "?")\n'
  '    IO.puts("after")\n'
  '  end\n'
  'end\n',
  0,
  b'deep!\n?\nafter\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    assert_raise("boom", fn -> raise("boom 1") end)\n'
  '    assert_raise("division", fn -> 1 / (1 - 1) end)\n'
  '    assert_raise("uncaught", fn ->\n'
  '      if 2 > 1 do throw("x") end\n'
  '      1\n'
  '    end)\n'
  '    assert_raise("match", fn ->\n'
  '      [a] = [1, 2]\n'
  '      a\n'
  '    end)\n'
  '    IO.puts("passed four")\n'
  '    Gen.check(Gen.integer(0, 10), fn n -> if n > 5 do throw(n) end end)\n'
  '  end\n'
  'end\n',
  2,
  b'passed four\n',
  b'<stdin>:14:5: property failed after 1 of 100 runs; smallest failing value, after 3 shrinking steps:\n6\nuncaught throw\n  at Main.main (<stdin>'
  b':14)\n',
  {'ALCHEM_SEED': '5'},
  b''),
 ('defmodule Main do\n  def main() do\n    assert_raise("nothing", fn -> 5 end)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: expected a failure containing "nothing", but the function returned\n  at Main.main (<stdin>:3)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    assert_raise("other", fn -> raise("this") end)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: expected a failure containing "other", got "this"\n  at Main.main (<stdin>:3)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    assert_raise("x", fn -> raise("") end)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: expected a failure containing "x", but the function returned\n  at Main.main (<stdin>:3)\n',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    Gen.check(Gen.list_of(Gen.integer(0, 9), 0, 6), fn l -> if length(l) > 2 do raise("long: #{length(l)}") end end, 30)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: property failed after 1 of 30 runs; smallest failing value, after 20 shrinking steps:\n[0, 0, 0]\nlong: 3\n  at Main.main (<stdin>'
  b':3)\n',
  {'ALCHEM_SEED': '3'},
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule Main do\n  def main() do\n    Gen.check(Gen.integer())\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    Gen.check(5, fn n -> n end)\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Gen.sample(Gen.integer())))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Gen.sample(Gen.integer(), "3")))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    g: generator[string] = Gen.integer()\n    IO.puts("x")\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Gen.sample(Gen.integer(1), 2)))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Gen.sample(Gen.string("lower"), 2)))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Gen.sample(Gen.map(Gen.integer(), fn s -> s <> "x" end), 2)))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Gen.sample(Gen.tuple(Gen.integer()), 2)))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    assert_raise(5, fn -> 1 end)\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(capture_io("x"))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    flunk(5)\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Gen.sample(Gen.one_of([Gen.integer(), Gen.boolean()]), 2)))\n  end\nend\n']
# files laid out in the directory the programs run in
FILES={}


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-gen-') as d:
        out=Path(d)/'out'
        for path,data in FILES.items():
            (Path(d)/path).parent.mkdir(parents=True,exist_ok=True);(Path(d)/path).write_bytes(data)
        for source,status,stdout,stderr,env,stdin in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':'',**env},input=stdin,cwd=d,timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
        extra=""
    print(f'PASS gen: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected{extra}; every generator value for value under four seeds of ALCHEM_SEED (the pinned PCG), Gen.check with the smallest failing value and the count of shrinking steps, ALCHEM_PROPERTY_RUNS, generators as typed values, the failures; assert_raise (its function in a process of its own, as a property is), capture_io, flunk, on_exit')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
