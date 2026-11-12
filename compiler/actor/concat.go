package actor

import "unsafe"

// joined remembers the string the process most recently built by
// concatenation: where its bytes are, how long it is, and, once it has been
// extended, the buffer it lives in.
type joined struct {
	data   *byte
	size   int
	buffer []byte
}

// concatMinimum is the length below which a plain concatenation is cheapest.
const concatMinimum = 32

// Concat returns a followed by b.
//
// A loop that grows a string, acc = acc <> piece, would copy the whole
// string on every step. When a is exactly the string this process last
// built, it is extended instead: the first time by moving it into a buffer
// with room to grow, and from then on by writing b into that room. The bytes
// written lie beyond the end of every string that shares the buffer, so no
// existing string, in this process or another, can observe them. A second
// concatenation onto an older string does not match the remembered length
// and copies as usual.
func Concat(c *Context, a, b string) string {
	if len(b) == 0 {
		return a
	}
	if len(a) < concatMinimum {
		return a + b
	}
	last := &c.joined
	if unsafe.StringData(a) != last.data || len(a) != last.size {
		text := a + b
		last.data, last.size, last.buffer = unsafe.StringData(text), len(text), nil
		return text
	}
	if last.buffer != nil && cap(last.buffer)-len(a) >= len(b) {
		last.buffer = append(last.buffer[:len(a)], b...)
	} else {
		buffer := make([]byte, len(a)+len(b), 2*(len(a)+len(b)))
		copy(buffer, a)
		copy(buffer[len(a):], b)
		last.buffer = buffer
	}
	last.data, last.size = unsafe.SliceData(last.buffer), len(last.buffer)
	return unsafe.String(last.data, last.size)
}
