package actor

import (
	"math/rand"
	"sort"
	"testing"
)

func checkMap(t *testing.T, got Map[int64, int64], want map[int64]int64) {
	t.Helper()
	if MapLen(got) != len(want) {
		t.Fatalf("size %d, want %d", MapLen(got), len(want))
	}
	for key, value := range want {
		if actual, ok := MapGet(got, key); !ok || actual != value {
			t.Fatalf("key %d: got %d,%v want %d", key, actual, ok, value)
		}
	}
	seen := 0
	MapEach(got, func(key, value int64) {
		seen++
		if want[key] != value {
			t.Fatalf("iteration produced %d=%d", key, value)
		}
	})
	keys := MapKeys(got)
	sort.Slice(keys, func(i, j int) bool { return keys[i] < keys[j] })
	for i := 1; i < len(keys); i++ {
		if keys[i] == keys[i-1] {
			t.Fatalf("duplicate key %d", keys[i])
		}
	}
	if seen != len(want) || len(keys) != len(want) {
		t.Fatalf("iterated %d entries and %d keys, want %d", seen, len(keys), len(want))
	}
}

// Random puts, overwrites and deletes are checked against a Go map, and every
// earlier version must stay exactly as it was. The same run is repeated with
// hashes that collide partially and completely.
func TestMapMatchesReferenceAndKeepsOldVersions(t *testing.T) {
	hashes := map[string]func(any) uint64{
		"seeded":           nil,
		"low bits only":    func(key any) uint64 { return uint64(key.(int64)) & 0x3ff },
		"high bits only":   func(key any) uint64 { return uint64(key.(int64)) << 60 },
		"every key equal":  func(any) uint64 { return 42 },
		"two hash classes": func(key any) uint64 { return uint64(key.(int64)) & 1 },
	}
	for name, hash := range hashes {
		t.Run(name, func(t *testing.T) {
			testHash = hash
			defer func() { testHash = nil }()
			random := rand.New(rand.NewSource(1))
			var current Map[int64, int64]
			reference := map[int64]int64{}
			type version struct {
				value Map[int64, int64]
				want  map[int64]int64
			}
			var versions []version
			steps := 4000
			if hash != nil {
				steps = 600
			}
			for step := 0; step < steps; step++ {
				key := int64(random.Intn(steps / 2))
				if random.Intn(3) == 0 {
					current = MapDelete(current, key)
					delete(reference, key)
				} else {
					current = MapPut(current, key, int64(step))
					reference[key] = int64(step)
				}
				if step%97 == 0 {
					snapshot := make(map[int64]int64, len(reference))
					for k, v := range reference {
						snapshot[k] = v
					}
					versions = append(versions, version{current, snapshot})
				}
			}
			checkMap(t, current, reference)
			for _, old := range versions {
				checkMap(t, old.value, old.want)
			}
			for key := range reference {
				current = MapDelete(current, key)
			}
			if MapLen(current) != 0 || current.root != nil {
				t.Fatalf("map not empty after deleting everything: %d", MapLen(current))
			}
		})
	}
}

func TestMapKeyTypesAndAbsentKeys(t *testing.T) {
	var words Map[string, int64]
	for i, word := range []string{"", "a", "b", "alpha", "beta"} {
		words = MapPut(words, word, int64(i))
	}
	if value, ok := MapGet(words, "alpha"); !ok || value != 3 || MapLen(words) != 5 {
		t.Fatalf("string keys: %d %v", value, ok)
	}
	if _, ok := MapGet(words, "missing"); ok {
		t.Fatal("found a missing key")
	}
	if same := MapDelete(words, "missing"); same.root != words.root || MapLen(same) != 5 {
		t.Fatal("deleting an absent key changed the map")
	}
	var flags Map[bool, string]
	flags = MapPut(MapPut(flags, true, "yes"), false, "no")
	if yes, _ := MapGet(flags, true); yes != "yes" || MapLen(flags) != 2 {
		t.Fatalf("boolean keys: %q", yes)
	}
	var empty Map[int64, int64]
	if _, ok := MapGet(empty, 1); ok || MapLen(empty) != 0 || len(MapKeys(empty)) != 0 {
		t.Fatal("zero map is not empty")
	}
}

// Two processes extend the same shared map at once; neither sees the other's
// keys and the shared original is untouched.
func TestMapSharedBetweenProcesses(t *testing.T) {
	c := root(t)
	var shared Map[int64, int64]
	for i := int64(0); i < 500; i++ {
		shared = MapPut(shared, i, i)
	}
	results := Self[Map[int64, int64]](c, 2, "test")
	for offset := int64(1); offset <= 2; offset++ {
		Spawn(c, func(child *Context, _ *PID[int64]) int64 {
			mine := shared
			for i := int64(0); i < 500; i++ {
				mine = MapPut(mine, 1000*offset+i, offset)
				mine = MapDelete(mine, i)
			}
			Send(child, results, mine, 1000, "test")
			return 0
		}, 1, "test")
	}
	for i := 0; i < 2; i++ {
		got := Receive(c, results, 3000, "test")
		if !got.E0 || MapLen(got.E1) != 500 {
			t.Fatalf("result %d: %v size %d", i, got.E0, MapLen(got.E1))
		}
		MapEach(got.E1, func(key, value int64) {
			if key < 1000*value || key >= 1000*value+500 {
				t.Fatalf("foreign key %d in map of process %d", key, value)
			}
		})
	}
	if MapLen(shared) != 500 {
		t.Fatalf("shared map changed: %d", MapLen(shared))
	}
}

func BenchmarkMapPutGrowing(b *testing.B) {
	b.ReportAllocs()
	var m Map[int64, int64]
	for i := 0; i < b.N; i++ {
		m = MapPut(m, int64(i), int64(i))
	}
}

func BenchmarkMapGet(b *testing.B) {
	var m Map[int64, int64]
	for i := int64(0); i < 100000; i++ {
		m = MapPut(m, i, i)
	}
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		MapGet(m, int64(i%100000))
	}
}

// A builder must produce the same map as repeated MapPut, and neither the
// map it started from nor any map it has handed out may change afterwards,
// including when hashes collide. Puts, deletes and further building on the
// handed-out maps are interleaved to catch a node changed in place.
func TestMapBuilderLeavesOtherMapsAlone(t *testing.T) {
	hashes := map[string]func(any) uint64{
		"seeded":           nil,
		"low bits only":    func(key any) uint64 { return uint64(key.(int64)) & 0x3ff },
		"high bits only":   func(key any) uint64 { return uint64(key.(int64)) << 60 },
		"every key equal":  func(any) uint64 { return 42 },
		"two hash classes": func(key any) uint64 { return uint64(key.(int64)) & 1 },
	}
	for name, hash := range hashes {
		t.Run(name, func(t *testing.T) {
			testHash = hash
			defer func() { testHash = nil }()
			random := rand.New(rand.NewSource(7))
			steps := 3000
			if hash != nil {
				steps = 500
			}
			var start Map[int64, int64]
			reference := map[int64]int64{}
			for i := 0; i < steps/4; i++ {
				key := int64(random.Intn(steps))
				start = MapPut(start, key, -key)
				reference[key] = -key
			}
			startWant := copyReference(reference)
			type version struct {
				value Map[int64, int64]
				want  map[int64]int64
			}
			var versions []version
			builder := NewMapBuilder(start)
			for step := 0; step < steps; step++ {
				key := int64(random.Intn(steps))
				builder.Put(key, int64(step))
				reference[key] = int64(step)
				if value, ok := builder.Get(key); !ok || value != int64(step) {
					t.Fatalf("builder.Get(%d) = %d,%v", key, value, ok)
				}
				if step%53 == 0 {
					handed := builder.Map()
					versions = append(versions, version{handed, copyReference(reference)})
					// Changing a handed-out map must not reach the builder.
					other := MapDelete(MapPut(handed, -1, -1), key)
					if _, leaked := builder.Get(-1); leaked {
						t.Fatal("a put on a handed-out map reached the builder")
					}
					if _, kept := builder.Get(key); !kept || MapLen(other) != MapLen(handed) {
						t.Fatal("a delete on a handed-out map reached the builder")
					}
				}
			}
			checkMap(t, builder.Map(), reference)
			checkMap(t, start, startWant)
			for _, old := range versions {
				checkMap(t, old.value, old.want)
			}
		})
	}
}

func copyReference(reference map[int64]int64) map[int64]int64 {
	out := make(map[int64]int64, len(reference))
	for key, value := range reference {
		out[key] = value
	}
	return out
}

func TestMapSortedOrdersKeys(t *testing.T) {
	var numbers Map[int64, string]
	var words Map[string, int64]
	var flags Map[bool, int64]
	for _, n := range []int64{5, -3, 9, 0, 2} {
		numbers = MapPut(numbers, n, "v")
	}
	for i, word := range []string{"pear", "apple", "fig"} {
		words = MapPut(words, word, int64(i))
	}
	flags = MapPut(MapPut(flags, true, 1), false, 0)
	keys, _ := MapSorted(numbers, nil)
	if len(keys) != 5 || !sort.SliceIsSorted(keys, func(i, j int) bool { return keys[i] < keys[j] }) {
		t.Fatalf("integer keys %v", keys)
	}
	names, positions := MapSorted(words, nil)
	if len(names) != 3 || names[0] != "apple" || positions[0] != 1 || names[2] != "pear" || positions[2] != 0 {
		t.Fatalf("string keys %v %v", names, positions)
	}
	order, values := MapSorted(flags, func(a, b bool) bool { return !a && b })
	if len(order) != 2 || order[0] || values[0] != 0 || !order[1] {
		t.Fatalf("boolean keys %v %v", order, values)
	}
}

func TestMapSortedLargeIntegerKeys(t *testing.T) {
	random := rand.New(rand.NewSource(3))
	for _, spread := range []int64{1 << 62, 1 << 20, 300} {
		var m Map[int64, int64]
		for i := 0; i < 5000; i++ {
			key := random.Int63n(spread) - spread/2
			m = MapPut(m, key, key*3)
		}
		keys, values := MapSorted(m, nil)
		if len(keys) != MapLen(m) {
			t.Fatalf("spread %d: %d keys of %d", spread, len(keys), MapLen(m))
		}
		for i, key := range keys {
			if values[i] != key*3 || (i > 0 && keys[i-1] >= key) {
				t.Fatalf("spread %d: position %d holds %d=%d after %d", spread, i, key, values[i], keys[max(i-1, 0)])
			}
		}
	}
}
