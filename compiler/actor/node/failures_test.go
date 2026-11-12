package node

import (
	"bytes"
	"encoding/binary"
	"strings"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler/actor"
)

// Before a program is a node, the node functions report that rather than
// fail, and Start refuses settings it cannot use.
func TestBeforeAndWhileStarting(t *testing.T) {
	c := root(t)
	if Name(c) != "" || Address(c) != "" || List(c) != nil || Disconnect(c, "other") {
		t.Fatal("a program that is not a node reported one")
	}
	if _, problem := Connect(c, "127.0.0.1:1"); !strings.Contains(problem, "start this node first") {
		t.Fatalf("connect before start: %q", problem)
	}
	if _, problem := Reconnect(c, "127.0.0.1:1"); problem == "" {
		t.Fatal("reconnect before start succeeded")
	}
	if _, problem := RemoteStream[string](c, "other", "feed", textCodec, "test"); !strings.Contains(problem, "start this node first") {
		t.Fatalf("stream before start: %q", problem)
	}
	if _, found := RemoteWhereis(c, "other", "name", 10, textCodec); found {
		t.Fatal("found a process with no node")
	}
	for _, c2 := range []struct{ name, cookie, want string }{
		{"", "secret", "needs a name"},
		{"a", "", "needs a cookie"},
	} {
		if problem := Start(c, c2.name, "127.0.0.1:0", c2.cookie, false); !strings.Contains(problem, c2.want) {
			t.Fatalf("start %q %q: %q", c2.name, c2.cookie, problem)
		}
	}
	if problem := Start(c, "a", "not an address", "secret", false); problem == "" {
		t.Fatal("started at no address")
	}
	if problem := Start(c, "a", "127.0.0.1:0", "secret", false); problem != "" {
		t.Fatal(problem)
	}
	if problem := Start(c, "a", "127.0.0.1:0", "secret", false); !strings.Contains(problem, "already a node") {
		t.Fatalf("second start: %q", problem)
	}
	if _, problem := Connect(c, "127.0.0.1:1"); problem == "" {
		t.Fatal("connected to a closed port")
	}
	// A node that is not connected is reported down at once.
	ref := Monitor(c, "nobody")
	if event := actor.NextEvent(c, 1000); !event.E0 || event.E1 != ref || !strings.Contains(event.E3, "nodedown nobody") {
		t.Fatalf("monitor of an unconnected node: %+v", event)
	}
	if Disconnect(c, "nobody") {
		t.Fatal("disconnected from no one")
	}
}

// A message that ends early marks its decoder as failed instead of reading
// past its end.
func TestDecoderStopsAtTheEnd(t *testing.T) {
	for _, read := range []func(*Decoder){
		func(d *Decoder) { d.Int() },
		func(d *Decoder) { d.Float() },
		func(d *Decoder) { d.Bool() },
		func(d *Decoder) { _ = d.String() },
		func(d *Decoder) { d.Length() },
	} {
		d := &Decoder{}
		read(d)
		if !d.failed {
			t.Fatal("reading from nothing did not fail")
		}
	}
	// A string or length longer than what is left fails too.
	e := &Encoder{}
	e.Int(100)
	d := &Decoder{buf: e.buf}
	if _ = d.String(); !d.failed {
		t.Fatal("an overlong string was read")
	}
	d = &Decoder{buf: append([]byte(nil), e.buf...)}
	if d.Length(); !d.failed {
		t.Fatal("an overlong length was read")
	}
	d = &Decoder{buf: []byte{1}}
	d.Fail()
	if !d.failed {
		t.Fatal("Fail did not mark the decoder")
	}
}

func TestFramesHaveALimit(t *testing.T) {
	var buf bytes.Buffer
	buf.Write(binary.BigEndian.AppendUint32(nil, frameLimit+1))
	if _, err := readFrame(&buf); err == nil || !strings.Contains(err.Error(), "too large") {
		t.Fatalf("an oversized frame was read: %v", err)
	}
	if _, err := readFrame(bytes.NewReader([]byte{0, 0})); err == nil {
		t.Fatal("a cut header was read")
	}
}
