package actor

import (
	"cmp"
	"hash/maphash"
	"math/bits"
	"slices"
	"sort"
)

// Atom is a name used as a value, written :name in source.
type Atom string

// Map is an immutable hash map (a hash array mapped trie). An update copies
// only the few nodes on the path to the changed key and shares the rest, so
// put and delete cost O(log n) instead of copying the whole map, and every
// earlier version stays valid. The zero Map is empty. Because nothing is ever
// modified in place, a Map can be shared between processes freely.
type Map[K comparable, V any] struct {
	root *mapNode[K, V]
	size int
}

// A node keeps its entries and its subtrees apart, as a CHAMP trie does:
// bit i of datamap says hash digit i holds an entry, and bit i of nodemap
// that it holds a subtree, each kept in order of digit. An update copies only
// the array it changes, so the path above a changed key copies pointers to
// subtrees, not entries. A node with neither bitmap set is a collision
// bucket: entries whose full hashes are equal, searched linearly.
type mapEntry[K comparable, V any] struct {
	key   K
	value V
}

type mapNode[K comparable, V any] struct {
	datamap, nodemap uint32
	entries          []mapEntry[K, V]
	children         []*mapNode[K, V]
	// edit names the builder or the fold that created the node and may
	// still change it in place; nodes of a finished map have an edit that
	// nothing holds any more.
	edit *mapEdit
}

// mapEdit is the right to change nodes in place. owned is set while the
// root of a map carrying it belongs to a fold; see MapOwned.
type mapEdit struct{ owned bool }

func (n *mapNode[K, V]) bucket() bool { return n.datamap|n.nodemap == 0 }

func entryIndex(bitmap, bit uint32) int { return bits.OnesCount32(bitmap & (bit - 1)) }

func inserted[T any](items []T, index int, item T) []T {
	out := make([]T, len(items)+1)
	copy(out, items[:index])
	out[index] = item
	copy(out[index+1:], items[index:])
	return out
}

func removed[T any](items []T, index int) []T {
	if len(items) == 1 {
		return nil
	}
	out := make([]T, len(items)-1)
	copy(out, items[:index])
	copy(out[index:], items[index+1:])
	return out
}

func replaced[T any](items []T, index int, item T) []T {
	out := append([]T(nil), items...)
	out[index] = item
	return out
}

const (
	mapBits  = 5
	mapMask  = 1<<mapBits - 1
	hashBits = 64
)

// The seed is random per program run, so key placement cannot be predicted
// from outside and a crafted key set cannot force collisions.
var (
	mapSeed = maphash.MakeSeed()
	intSeed = maphash.String(mapSeed, "alchem integer keys")
	// testHash replaces the hash in tests that need to force collisions.
	testHash func(any) uint64
)

func hashOf[K comparable](key K) uint64 {
	if testHash != nil {
		return testHash(key)
	}
	switch k := any(key).(type) {
	case int64:
		// splitmix64 finalizer over the seeded value.
		x := uint64(k) ^ intSeed
		x ^= x >> 30
		x *= 0xbf58476d1ce4e5b9
		x ^= x >> 27
		x *= 0x94d049bb133111eb
		return x ^ x>>31
	case string:
		return maphash.String(mapSeed, k)
	case Atom:
		return maphash.String(mapSeed, string(k))
	case bool:
		if k {
			return intSeed | 1
		}
		return intSeed &^ 1
	}
	// Floats and tuples of key types hash by value; 0.0 and -0.0, being
	// equal, hash alike.
	return maphash.Comparable(mapSeed, key)
}

// MapLen reports the number of entries.
func MapLen[K comparable, V any](m Map[K, V]) int { return m.size }

// MapGet returns the value stored for key.
func MapGet[K comparable, V any](m Map[K, V], key K) (V, bool) {
	var zero V
	node := m.root
	if node == nil {
		return zero, false
	}
	hash := hashOf(key)
	for shift := uint(0); ; shift += mapBits {
		if node.bucket() {
			for i := range node.entries {
				if node.entries[i].key == key {
					return node.entries[i].value, true
				}
			}
			return zero, false
		}
		bit := uint32(1) << (hash >> shift & mapMask)
		switch {
		case node.datamap&bit != 0:
			if entry := &node.entries[entryIndex(node.datamap, bit)]; entry.key == key {
				return entry.value, true
			}
			return zero, false
		case node.nodemap&bit != 0:
			node = node.children[entryIndex(node.nodemap, bit)]
		default:
			return zero, false
		}
	}
}

// MapPut returns a map that also holds key with value, replacing any value
// already stored for key. m is unchanged.
func MapPut[K comparable, V any](m Map[K, V], key K, value V) Map[K, V] {
	if r := m.root; r != nil && r.edit != nil && r.edit.owned {
		// The map belongs to a fold that hands on only its newest version,
		// so the nodes the fold made are changed where they are.
		root, added := putOwned(r.edit, r, 0, hashOf(key), key, value)
		if added {
			return Map[K, V]{root, m.size + 1}
		}
		return Map[K, V]{root, m.size}
	}
	root, added := putNode(m.root, 0, hashOf(key), key, value)
	if added {
		return Map[K, V]{root, m.size + 1}
	}
	return Map[K, V]{root, m.size}
}

// pair makes the subtree holding two entries whose hash digits agree up to
// shift.
func pair[K comparable, V any](shift uint, a mapEntry[K, V], hashA uint64, b mapEntry[K, V], hashB uint64) *mapNode[K, V] {
	if shift >= hashBits {
		return &mapNode[K, V]{entries: []mapEntry[K, V]{a, b}}
	}
	bitA, bitB := uint32(1)<<(hashA>>shift&mapMask), uint32(1)<<(hashB>>shift&mapMask)
	if bitA == bitB {
		return &mapNode[K, V]{nodemap: bitA, children: []*mapNode[K, V]{pair(shift+mapBits, a, hashA, b, hashB)}}
	}
	if bitB < bitA {
		a, b = b, a
	}
	return &mapNode[K, V]{datamap: bitA | bitB, entries: []mapEntry[K, V]{a, b}}
}

func putNode[K comparable, V any](node *mapNode[K, V], shift uint, hash uint64, key K, value V) (*mapNode[K, V], bool) {
	entry := mapEntry[K, V]{key, value}
	if shift >= hashBits {
		// Hash digits are exhausted: keep colliding entries in a bucket.
		if node == nil {
			return &mapNode[K, V]{entries: []mapEntry[K, V]{entry}}, true
		}
		for i := range node.entries {
			if node.entries[i].key == key {
				return &mapNode[K, V]{entries: replaced(node.entries, i, entry)}, false
			}
		}
		return &mapNode[K, V]{entries: append(append([]mapEntry[K, V](nil), node.entries...), entry)}, true
	}
	bit := uint32(1) << (hash >> shift & mapMask)
	if node == nil {
		return &mapNode[K, V]{datamap: bit, entries: []mapEntry[K, V]{entry}}, true
	}
	switch {
	case node.datamap&bit != 0:
		index := entryIndex(node.datamap, bit)
		old := node.entries[index]
		if old.key == key {
			return &mapNode[K, V]{datamap: node.datamap, nodemap: node.nodemap, entries: replaced(node.entries, index, entry), children: node.children}, false
		}
		// Two different keys share this digit: they move to a subtree.
		child := pair(shift+mapBits, old, hashOf(old.key), entry, hash)
		return &mapNode[K, V]{
			datamap: node.datamap &^ bit, nodemap: node.nodemap | bit,
			entries:  removed(node.entries, index),
			children: inserted(node.children, entryIndex(node.nodemap, bit), child),
		}, true
	case node.nodemap&bit != 0:
		index := entryIndex(node.nodemap, bit)
		child, added := putNode(node.children[index], shift+mapBits, hash, key, value)
		return &mapNode[K, V]{datamap: node.datamap, nodemap: node.nodemap, entries: node.entries, children: replaced(node.children, index, child)}, added
	}
	return &mapNode[K, V]{datamap: node.datamap | bit, nodemap: node.nodemap, entries: inserted(node.entries, entryIndex(node.datamap, bit), entry), children: node.children}, true
}

// MapDelete returns a map without key. m is unchanged; when key is absent the
// result shares all of m.
func MapDelete[K comparable, V any](m Map[K, V], key K) Map[K, V] {
	root, gone := deleteNode(m.root, 0, hashOf(key), key)
	if !gone {
		return m
	}
	return Map[K, V]{root, m.size - 1}
}

// single reports a node that holds one entry and nothing else, which its
// parent keeps as an entry instead.
func (n *mapNode[K, V]) single() bool { return len(n.entries) == 1 && len(n.children) == 0 }

func deleteNode[K comparable, V any](node *mapNode[K, V], shift uint, hash uint64, key K) (*mapNode[K, V], bool) {
	if node == nil {
		return nil, false
	}
	if node.bucket() {
		for i := range node.entries {
			if node.entries[i].key == key {
				if len(node.entries) == 1 {
					return nil, true
				}
				return &mapNode[K, V]{entries: removed(node.entries, i)}, true
			}
		}
		return node, false
	}
	bit := uint32(1) << (hash >> shift & mapMask)
	switch {
	case node.datamap&bit != 0:
		index := entryIndex(node.datamap, bit)
		if node.entries[index].key != key {
			return node, false
		}
		if len(node.entries) == 1 && len(node.children) == 0 {
			return nil, true
		}
		return &mapNode[K, V]{datamap: node.datamap &^ bit, nodemap: node.nodemap, entries: removed(node.entries, index), children: node.children}, true
	case node.nodemap&bit != 0:
		index := entryIndex(node.nodemap, bit)
		child, gone := deleteNode(node.children[index], shift+mapBits, hash, key)
		if !gone {
			return node, false
		}
		switch {
		case child == nil:
			if len(node.children) == 1 && len(node.entries) == 0 {
				return nil, true
			}
			return &mapNode[K, V]{datamap: node.datamap, nodemap: node.nodemap &^ bit, entries: node.entries, children: removed(node.children, index)}, true
		case child.single():
			// A subtree left with one entry becomes an entry again.
			return &mapNode[K, V]{
				datamap: node.datamap | bit, nodemap: node.nodemap &^ bit,
				entries:  inserted(node.entries, entryIndex(node.datamap, bit), child.entries[0]),
				children: removed(node.children, index),
			}, true
		}
		return &mapNode[K, V]{datamap: node.datamap, nodemap: node.nodemap, entries: node.entries, children: replaced(node.children, index, child)}, true
	}
	return node, false
}

// MapEach calls visit for every entry, in an unspecified order.
func MapEach[K comparable, V any](m Map[K, V], visit func(K, V)) {
	eachNode(m.root, visit)
}

func eachNode[K comparable, V any](node *mapNode[K, V], visit func(K, V)) {
	if node == nil {
		return
	}
	for i := range node.entries {
		visit(node.entries[i].key, node.entries[i].value)
	}
	for _, child := range node.children {
		eachNode(child, visit)
	}
}

// MapKeys returns the keys in an unspecified order.
func MapKeys[K comparable, V any](m Map[K, V]) []K {
	keys := make([]K, 0, m.size)
	MapEach(m, func(key K, _ V) { keys = append(keys, key) })
	return keys
}

// EqualWith reports whether other is a map of the same type holding the same
// keys with values that eq accepts. It serves equality on values whose type
// is only known at run time.
func (m Map[K, V]) EqualWith(other any, eq func(any, any) bool) bool {
	o, ok := other.(Map[K, V])
	if !ok || m.size != o.size {
		return false
	}
	same := true
	MapEach(m, func(key K, value V) {
		if match, found := MapGet(o, key); !found || !eq(value, match) {
			same = false
		}
	})
	return same
}

// Pairs returns the entries in no particular order, for code that only knows
// the map as a value of unknown type.
func (m Map[K, V]) Pairs() [][2]any {
	out := make([][2]any, 0, m.size)
	MapEach(m, func(key K, value V) { out = append(out, [2]any{key, value}) })
	return out
}

// MapOwned returns m as the starting value of a fold: a reduce whose
// function only reads its accumulator and returns it changed by one put, so
// that no version but the newest can be seen. Puts to the map, and to what
// they return, then change the fold's own nodes in place instead of copying
// a path each time. m itself is not touched. MapShared ends the fold.
func MapOwned[K comparable, V any](m Map[K, V]) Map[K, V] {
	edit := &mapEdit{owned: true}
	if m.root == nil {
		return Map[K, V]{&mapNode[K, V]{edit: edit}, 0}
	}
	return Map[K, V]{ownNode(edit, m.root), m.size}
}

// MapShared returns the result of a fold as an ordinary map: its nodes are
// never changed again.
func MapShared[K comparable, V any](m Map[K, V]) Map[K, V] {
	if m.root != nil && m.root.edit != nil {
		m.root.edit.owned = false
	}
	if m.size == 0 {
		return Map[K, V]{}
	}
	return m
}

// MapBuilder builds a map from many insertions without copying a path of
// nodes for each one: nodes the builder created itself are changed in place.
// Nodes of the map it started from, and of every map it has handed out, are
// never touched, so those maps stay valid.
type MapBuilder[K comparable, V any] struct {
	root *mapNode[K, V]
	size int
	edit *mapEdit
}

// NewMapBuilder starts from m, which may be the zero Map.
func NewMapBuilder[K comparable, V any](m Map[K, V]) *MapBuilder[K, V] {
	return &MapBuilder[K, V]{root: m.root, size: m.size, edit: new(mapEdit)}
}

// Get returns the value currently stored for key.
func (b *MapBuilder[K, V]) Get(key K) (V, bool) {
	return MapGet(Map[K, V]{b.root, b.size}, key)
}

// Put stores value for key, replacing any value already there.
func (b *MapBuilder[K, V]) Put(key K, value V) {
	root, added := putOwned(b.edit, b.root, 0, hashOf(key), key, value)
	b.root = root
	if added {
		b.size++
	}
}

// Map returns what has been built. The builder may go on being used: nodes
// of the returned map are from then on copied before they change.
func (b *MapBuilder[K, V]) Map() Map[K, V] {
	b.edit = new(mapEdit)
	return Map[K, V]{b.root, b.size}
}

// ownNode returns node itself when edit created it, and otherwise a copy
// that edit may change.
func ownNode[K comparable, V any](edit *mapEdit, node *mapNode[K, V]) *mapNode[K, V] {
	if node.edit == edit {
		return node
	}
	return &mapNode[K, V]{
		datamap: node.datamap, nodemap: node.nodemap,
		entries:  append(make([]mapEntry[K, V], 0, len(node.entries)+1), node.entries...),
		children: append([]*mapNode[K, V](nil), node.children...),
		edit:     edit,
	}
}

func putOwned[K comparable, V any](edit *mapEdit, node *mapNode[K, V], shift uint, hash uint64, key K, value V) (*mapNode[K, V], bool) {
	entry := mapEntry[K, V]{key, value}
	if shift >= hashBits {
		// Hash digits are exhausted: keep colliding entries in a bucket.
		if node == nil {
			return &mapNode[K, V]{entries: []mapEntry[K, V]{entry}, edit: edit}, true
		}
		node = ownNode(edit, node)
		for i := range node.entries {
			if node.entries[i].key == key {
				node.entries[i] = entry
				return node, false
			}
		}
		node.entries = append(node.entries, entry)
		return node, true
	}
	bit := uint32(1) << (hash >> shift & mapMask)
	if node == nil {
		return &mapNode[K, V]{datamap: bit, entries: []mapEntry[K, V]{entry}, edit: edit}, true
	}
	node = ownNode(edit, node)
	switch {
	case node.datamap&bit != 0:
		index := entryIndex(node.datamap, bit)
		old := node.entries[index]
		if old.key == key {
			node.entries[index].value = value
			return node, false
		}
		// Two different keys share this digit: they move to a subtree.
		child := pair(shift+mapBits, old, hashOf(old.key), entry, hash)
		node.entries = slices.Delete(node.entries, index, index+1)
		node.children = slices.Insert(node.children, entryIndex(node.nodemap, bit), child)
		node.datamap &^= bit
		node.nodemap |= bit
		return node, true
	case node.nodemap&bit != 0:
		index := entryIndex(node.nodemap, bit)
		child, added := putOwned(edit, node.children[index], shift+mapBits, hash, key, value)
		node.children[index] = child
		return node, added
	}
	node.entries = slices.Insert(node.entries, entryIndex(node.datamap, bit), entry)
	node.datamap |= bit
	return node, true
}

// MapSorted returns the keys in ascending order with their values. Integer
// and string keys are sorted directly; less orders any other key type.
func MapSorted[K comparable, V any](m Map[K, V], less func(K, K) bool) ([]K, []V) {
	keys := make([]K, 0, m.size)
	values := make([]V, 0, m.size)
	MapEach(m, func(key K, value V) {
		keys = append(keys, key)
		values = append(values, value)
	})
	if len(keys) < 2 {
		return keys, values
	}
	order := make([]int32, len(keys))
	for i := range order {
		order[i] = int32(i)
	}
	switch typed := any(keys).(type) {
	case []int64:
		sortIntegerOrder(typed, order)
	case []string:
		slices.SortFunc(order, func(a, b int32) int { return cmp.Compare(typed[a], typed[b]) })
	default:
		sort.Slice(order, func(i, j int) bool { return less(keys[order[i]], keys[order[j]]) })
	}
	sortedKeys := make([]K, len(keys))
	sortedValues := make([]V, len(keys))
	for i, at := range order {
		sortedKeys[i], sortedValues[i] = keys[at], values[at]
	}
	return sortedKeys, sortedValues
}

// sortIntegerOrder sorts order, a list of positions in keys, by key. Large
// inputs use a byte-wise radix sort, which is linear and skips the bytes
// every key has in common; keys spread over a small range need two or three
// passes.
func sortIntegerOrder(keys []int64, order []int32) {
	if len(keys) < 512 {
		slices.SortFunc(order, func(a, b int32) int { return cmp.Compare(keys[a], keys[b]) })
		return
	}
	type entry struct {
		key uint64
		at  int32
	}
	entries := make([]entry, len(keys))
	var counts [8][256]int
	for i, key := range keys {
		// Flipping the sign bit makes unsigned order match signed order.
		unsigned := uint64(key) ^ 1<<63
		entries[i] = entry{unsigned, int32(i)}
		for digit := 0; digit < 8; digit++ {
			counts[digit][unsigned>>(8*digit)&0xff]++
		}
	}
	spare := make([]entry, len(keys))
	for digit := 0; digit < 8; digit++ {
		count := &counts[digit]
		if count[entries[0].key>>(8*digit)&0xff] == len(keys) {
			continue
		}
		total := 0
		for value, n := range count {
			count[value], total = total, total+n
		}
		for _, item := range entries {
			value := item.key >> (8 * digit) & 0xff
			spare[count[value]] = item
			count[value]++
		}
		entries, spare = spare, entries
	}
	for i, item := range entries {
		order[i] = item.at
	}
}

// Collect returns the map with the given elements added: {key, value} pairs
// for a map, or keys alone when the map is a set.
func (m Map[K, V]) Collect(each func(func(any) bool)) any {
	out := NewMapBuilder(m)
	each(func(element any) bool {
		switch entry := element.(type) {
		case struct {
			E0 K
			E1 V
		}:
			out.Put(entry.E0, entry.E1)
		case K:
			var member V
			out.Put(entry, member)
		}
		return true
	})
	return out.Map()
}
