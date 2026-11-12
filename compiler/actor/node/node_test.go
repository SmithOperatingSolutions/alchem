package node

import (
	"bytes"
	"crypto/tls"
	"io"
	"iter"
	"net"
	"strings"
	"sync"
	"testing"

	"github.com/SmithOperatingSolutions/alchem/compiler/actor"
)

func root(t *testing.T) *actor.Context {
	t.Helper()
	c := actor.NewRoot()
	t.Cleanup(func() {
		if !actor.Close(c, 3000) {
			t.Error("runtime leaked tasks")
		}
	})
	return c
}

type order struct {
	Item  string
	Count int64
	Reply *actor.PID[string]
}

var textCodec = Codec[string]{
	Type:   "string",
	Encode: func(e *Encoder, v string) { e.String(v) },
	Decode: func(d *Decoder) string { return d.String() },
}

var orderCodec = Codec[order]{
	Type: "order",
	Encode: func(e *Encoder, v order) {
		e.String(v.Item)
		e.Int(v.Count)
		EncodePID(e, v.Reply, textCodec)
	},
	Decode: func(d *Decoder) order {
		return order{d.String(), d.Int(), DecodePID(d, textCodec)}
	},
}

// Two nodes in one test stand for two programs: each has its own runtime, so
// nothing passes between them except over the connection.
func TestNodesExchangeMessages(t *testing.T) {
	shop, client := root(t), root(t)
	if problem := Start(shop, "shop", "127.0.0.1:0", "secret", true); problem != "" {
		t.Fatal(problem)
	}
	if problem := Start(client, "client", "127.0.0.1:0", "secret", true); problem != "" {
		t.Fatal(problem)
	}
	orders := actor.Self[order](shop, 8, "test")
	if !Register(shop, orders, "orders", orderCodec) || Register(shop, orders, "orders", orderCodec) {
		t.Fatal("a name registers once")
	}
	if local, ok := Whereis(shop, "orders", orderCodec); !ok || local != orders {
		t.Fatal("local lookup")
	}
	if _, ok := Whereis(shop, "orders", textCodec); ok {
		t.Fatal("a lookup for another message type found the process")
	}

	name, problem := Connect(client, Address(shop))
	if problem != "" || name != "shop" {
		t.Fatalf("connect: %q %q", name, problem)
	}
	if list := List(client); len(list) != 1 || list[0] != "shop" {
		t.Fatalf("list: %v", list)
	}
	if _, ok := RemoteWhereis(client, "shop", "orders", 1000, textCodec); ok {
		t.Fatal("a remote lookup for another message type found the process")
	}
	if _, ok := RemoteWhereis(client, "shop", "nobody", 1000, orderCodec); ok {
		t.Fatal("found a name nobody registered")
	}
	remoteOrders, ok := RemoteWhereis(client, "shop", "orders", 1000, orderCodec)
	if !ok {
		t.Fatal("remote lookup")
	}

	// The message carries the client's own handle, which the shop answers.
	inbox := actor.Self[string](client, 8, "test")
	if !actor.Send(client, remoteOrders, order{"tea", 3, inbox}, 1000, "test") {
		t.Fatal("send to a remote process")
	}
	got := actor.Receive(shop, orders, 2000, "test")
	if !got.E0 || got.E1.Item != "tea" || got.E1.Count != 3 {
		t.Fatalf("shop received %+v", got)
	}
	if !actor.Send(shop, got.E1.Reply, "3 tea shipped", 1000, "test") {
		t.Fatal("reply through a handle that arrived in a message")
	}
	if answer := actor.Receive(client, inbox, 2000, "test"); !answer.E0 || answer.E1 != "3 tea shipped" {
		t.Fatalf("client received %+v", answer)
	}
	if !actor.Alive(client, remoteOrders, "test") || actor.ID(client, remoteOrders, "test") != actor.ID(shop, orders, "test") {
		t.Fatal("alive and id of a remote handle")
	}

	// A process of another node can be monitored: its exit arrives as an
	// event, as a local one would.
	worker := actor.Spawn(shop, func(child *actor.Context, self *actor.PID[order]) int64 {
		actor.Receive(child, self, 5000, "test")
		actor.Fail(child, "worker.alc:1:1", "out of stock")
		return 0
	}, 4, "test")
	Register(shop, worker, "worker", orderCodec)
	remoteWorker, ok := RemoteWhereis(client, "shop", "worker", 1000, orderCodec)
	if !ok {
		t.Fatal("remote lookup of the worker")
	}
	watch := actor.Monitor(client, remoteWorker, "test")
	unwatched := actor.Monitor(client, remoteWorker, "test")
	if !actor.Demonitor(client, remoteWorker, unwatched, "test") {
		t.Fatal("demonitor of a remote process")
	}
	actor.Send(client, remoteWorker, order{"anything", 1, inbox}, 1000, "test")
	if down := actor.NextEvent(client, 3000); !down.E0 || down.E1 != watch || down.E2 != actor.ID(shop, worker, "test") || !strings.Contains(down.E3, "out of stock") {
		t.Fatalf("exit of a remote process: %+v", down)
	}
	if extra := actor.NextEvent(client, 100); extra.E0 {
		t.Fatalf("a cancelled monitor still reported: %+v", extra)
	}
	// One that has already ended is reported at once.
	late := actor.Monitor(client, remoteWorker, "test")
	if down := actor.NextEvent(client, 3000); !down.E0 || down.E1 != late || !strings.Contains(down.E3, "out of stock") {
		t.Fatalf("monitoring an ended remote process: %+v", down)
	}
	// And one whose node goes away is reported as unreachable.
	orphan := actor.Monitor(client, remoteOrders, "test")

	// Losing the connection is reported once to those who asked.
	ref := Monitor(client, "shop")
	if !Disconnect(shop, "client") {
		t.Fatal("disconnect")
	}
	seen := map[int64]string{}
	for range 2 {
		event := actor.NextEvent(client, 2000)
		seen[event.E1] = event.E3
	}
	if seen[ref] != "nodedown shop" || seen[orphan] != "noconnection" {
		t.Fatalf("events after losing the connection: %v", seen)
	}
	if actor.Send(client, remoteOrders, order{"late", 1, inbox}, 100, "test") || actor.Alive(client, remoteOrders, "test") {
		t.Fatal("a send after the connection closed reported success")
	}
	again := Monitor(client, "shop")
	if event := actor.NextEvent(client, 1000); !event.E0 || event.E1 != again {
		t.Fatalf("monitoring a node that is not connected: %+v", event)
	}
}

func TestNodesNeedTheSameCookie(t *testing.T) {
	one, two := root(t), root(t)
	Start(one, "one", "127.0.0.1:0", "red", true)
	Start(two, "two", "127.0.0.1:0", "blue", true)
	if name, problem := Connect(two, Address(one)); name != "" || !strings.Contains(problem, "cookie") {
		t.Fatalf("connected with different cookies: %q %q", name, problem)
	}
	if _, problem := Connect(root(t), Address(one)); !strings.Contains(problem, "Node.start") {
		t.Fatalf("connected without being a node: %q", problem)
	}
	if problem := Start(one, "again", "127.0.0.1:0", "red", true); problem == "" {
		t.Fatal("a program became a node twice")
	}
}

var numberCodec = Codec[int64]{
	Type:   "integer",
	Encode: func(e *Encoder, v int64) { e.Int(v) },
	Decode: func(d *Decoder) int64 { return d.Int() },
}

// A published stream is pulled in chunks: reading all of it gives every
// element in order, stopping early pulls no more, an endless stream can be
// read from, and each reader starts at the beginning.
func TestStreamIsPulledFromItsNode(t *testing.T) {
	origin, reader := root(t), root(t)
	Start(origin, "origin", "127.0.0.1:0", "secret", true)
	Start(reader, "reader", "127.0.0.1:0", "secret", true)
	built, produced := 0, int64(0)
	counting := func(limit int64) func(*actor.Context) iter.Seq[int64] {
		return func(*actor.Context) iter.Seq[int64] {
			built++
			return func(yield func(int64) bool) {
				for n := int64(1); limit == 0 || n <= limit; n++ {
					produced = n
					if !yield(n) {
						return
					}
				}
			}
		}
	}
	if !PublishStream(origin, "thousand", counting(1000), numberCodec, "test") || PublishStream(origin, "thousand", counting(1), numberCodec, "test") {
		t.Fatal("a stream is published under a name once")
	}
	PublishStream(origin, "endless", counting(0), numberCodec, "test")
	if _, problem := Connect(reader, Address(origin)); problem != "" {
		t.Fatal(problem)
	}
	if _, problem := RemoteStream(reader, "origin", "missing", numberCodec, "test"); !strings.Contains(problem, "publishes no stream missing") {
		t.Fatalf("an unpublished stream: %q", problem)
	}
	if _, problem := RemoteStream(reader, "origin", "thousand", textCodec, "test"); !strings.Contains(problem, "of string") {
		t.Fatalf("a stream of another type: %q", problem)
	}
	thousand, problem := RemoteStream(reader, "origin", "thousand", numberCodec, "test")
	if problem != "" {
		t.Fatal(problem)
	}
	total, count := int64(0), 0
	thousand(func(n int64) bool { total += n; count++; return true })
	if total != 500500 || count != 1000 {
		t.Fatalf("read %d elements adding up to %d", count, total)
	}
	// A second reading starts again from the first element.
	var first []int64
	thousand(func(n int64) bool { first = append(first, n); return len(first) < 3 })
	if len(first) != 3 || first[0] != 1 || first[2] != 3 || built != 2 {
		t.Fatalf("second reading: %v after %d builds", first, built)
	}
	endless, problem := RemoteStream(reader, "origin", "endless", numberCodec, "test")
	if problem != "" {
		t.Fatal(problem)
	}
	seen := 0
	endless(func(int64) bool { seen++; return seen < 600 })
	// Only the chunks that were asked for were produced on the other side.
	if seen != 600 || produced < 600 || produced > 3*chunkItems {
		t.Fatalf("read %d of an endless stream; its node produced %d", seen, produced)
	}
}

// relay stands between two nodes. With tap set it only copies bytes and
// records them, as someone listening on the network would. Otherwise it
// ends the encryption on each side with a certificate of its own and passes
// along what the nodes say, as someone trying to sit between them would.
func relay(t *testing.T, target string, tap *bytes.Buffer) string {
	t.Helper()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { listener.Close() })
	var lock sync.Mutex
	go func() {
		for {
			near, err := listener.Accept()
			if err != nil {
				return
			}
			far, err := net.Dial("tcp", target)
			if err != nil {
				near.Close()
				continue
			}
			var inner, outer net.Conn = near, far
			if tap == nil {
				// It knows the protocol: the byte saying whether a node
				// encrypts is passed along before the encryption starts.
				var mode [1]byte
				if _, err := io.ReadFull(near, mode[:]); err != nil {
					near.Close()
					far.Close()
					continue
				}
				far.Write(mode[:])
				if _, err := io.ReadFull(far, mode[:]); err != nil {
					near.Close()
					far.Close()
					continue
				}
				near.Write(mode[:])
				certificate, _ := identity("relay")
				inner = tls.Server(near, &tls.Config{Certificates: []tls.Certificate{certificate}, MinVersion: tls.VersionTLS13})
				outer = tls.Client(far, &tls.Config{InsecureSkipVerify: true, MinVersion: tls.VersionTLS13})
			}
			copyAcross := func(to, from net.Conn) {
				defer to.Close()
				defer from.Close()
				buffer := make([]byte, 32<<10)
				for {
					n, err := from.Read(buffer)
					if n > 0 {
						if tap != nil {
							lock.Lock()
							tap.Write(buffer[:n])
							lock.Unlock()
						}
						if _, err := to.Write(buffer[:n]); err != nil {
							return
						}
					}
					if err != nil {
						return
					}
				}
			}
			go copyAcross(outer, inner)
			go copyAcross(inner, outer)
		}
	}()
	return listener.Addr().String()
}

// What crosses between nodes cannot be read from the network: neither the
// names the nodes give themselves, nor the name a process is looked up by,
// nor the text of a message.
func TestTrafficIsEncrypted(t *testing.T) {
	shop, client := root(t), root(t)
	Start(shop, "shop-node-name", "127.0.0.1:0", "a shared secret", true)
	Start(client, "client-node-name", "127.0.0.1:0", "a shared secret", true)
	notes := actor.Self[string](shop, 8, "test")
	Register(shop, notes, "private-notes", textCodec)
	var seen bytes.Buffer
	through := relay(t, Address(shop), &seen)
	if name, problem := Connect(client, through); name != "shop-node-name" {
		t.Fatalf("connecting through a relay that only copies: %q %q", name, problem)
	}
	remote, ok := RemoteWhereis(client, "shop-node-name", "private-notes", 2000, textCodec)
	if !ok {
		t.Fatal("lookup through the relay")
	}
	actor.Send(client, remote, "the launch code is 0451", 1000, "test")
	if got := actor.Receive(shop, notes, 2000, "test"); !got.E0 || got.E1 != "the launch code is 0451" {
		t.Fatalf("message through the relay: %+v", got)
	}
	if seen.Len() < 200 {
		t.Fatalf("the relay saw only %d bytes", seen.Len())
	}
	for _, secret := range []string{"the launch code", "0451", "private-notes", "shop-node-name", "client-node-name", "a shared secret", magic} {
		if bytes.Contains(seen.Bytes(), []byte(secret)) {
			t.Errorf("%q can be read from the network", secret)
		}
	}
}

// Someone between two nodes who ends the encryption on each side sees a
// different session with each. The nodes' proofs of the cookie are tied to
// their sessions, so passing them along does not work, and the nodes refuse
// to connect even though both know the cookie.
func TestRelayThatDecryptsIsRejected(t *testing.T) {
	shop, client := root(t), root(t)
	Start(shop, "shop", "127.0.0.1:0", "a shared secret", true)
	Start(client, "client", "127.0.0.1:0", "a shared secret", true)
	between := relay(t, Address(shop), nil)
	name, problem := Connect(client, between)
	if name != "" || !strings.Contains(problem, "cookie") {
		t.Fatalf("connected through a relay that decrypts: %q %q", name, problem)
	}
	if len(List(shop)) != 0 || len(List(client)) != 0 {
		t.Fatalf("a rejected connection was kept: %v %v", List(shop), List(client))
	}
	// Directly, the same two nodes connect.
	if name, problem := Connect(client, Address(shop)); name != "shop" {
		t.Fatalf("direct connection: %q %q", name, problem)
	}
}

// Two nodes started without encryption connect, check the cookie and
// exchange messages, which can then be read from the network.
func TestUnencryptedNodes(t *testing.T) {
	shop, client := root(t), root(t)
	Start(shop, "shop", "127.0.0.1:0", "a shared secret", false)
	Start(client, "client", "127.0.0.1:0", "a shared secret", false)
	notes := actor.Self[string](shop, 8, "test")
	Register(shop, notes, "notes", textCodec)
	var seen bytes.Buffer
	through := relay(t, Address(shop), &seen)
	if name, problem := Connect(client, through); name != "shop" {
		t.Fatalf("connecting: %q %q", name, problem)
	}
	remote, ok := RemoteWhereis(client, "shop", "notes", 2000, textCodec)
	if !ok {
		t.Fatal("lookup")
	}
	actor.Send(client, remote, "plain words", 1000, "test")
	if got := actor.Receive(shop, notes, 2000, "test"); !got.E0 || got.E1 != "plain words" {
		t.Fatalf("message: %+v", got)
	}
	if !bytes.Contains(seen.Bytes(), []byte("plain words")) {
		t.Fatal("an unencrypted message did not cross as plain text")
	}
	// The cookie is still checked, and never sent.
	if bytes.Contains(seen.Bytes(), []byte("a shared secret")) {
		t.Fatal("the cookie crossed the network")
	}
	stranger := root(t)
	Start(stranger, "stranger", "127.0.0.1:0", "another secret", false)
	if name, problem := Connect(stranger, Address(shop)); name != "" || !strings.Contains(problem, "cookie") {
		t.Fatalf("connected with a different cookie: %q %q", name, problem)
	}
}

// A node that encrypts and one that does not refuse each other, whichever
// one dials, and each says why.
func TestEncryptionSettingsMustMatch(t *testing.T) {
	secure, plain := root(t), root(t)
	Start(secure, "secure", "127.0.0.1:0", "secret", true)
	Start(plain, "plain", "127.0.0.1:0", "secret", false)
	if name, problem := Connect(plain, Address(secure)); name != "" || !strings.Contains(problem, "the other node encrypts its connections and this one does not") {
		t.Fatalf("plain dialling secure: %q %q", name, problem)
	}
	if name, problem := Connect(secure, Address(plain)); name != "" || !strings.Contains(problem, "this node encrypts its connections and the other node does not") {
		t.Fatalf("secure dialling plain: %q %q", name, problem)
	}
	if len(List(secure)) != 0 || len(List(plain)) != 0 {
		t.Fatalf("a refused connection was kept: %v %v", List(secure), List(plain))
	}
}
