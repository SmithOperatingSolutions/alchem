// Package node lets processes of one program exchange messages with
// processes of other programs. It is a package of its own so that a program
// which stays on its own carries no networking or cryptography.
//
// Messages are copied: the sender encodes a value and the receiver builds an
// equal one, which no program can tell from sharing, because values are
// immutable. The compiler supplies a Codec for every message type that
// crosses, so nothing is discovered while the program runs, and a process
// handle crosses as the name of its node and its number.
//
// Connections are encrypted with TLS 1.3 unless a node is started with
// encryption turned off. Nodes hold no certificates that anyone has signed;
// what admits a node is the cookie, a secret every node of a cluster shares.
// Each end proves it knows the cookie with a keyed hash over a value derived
// from the TLS session, so the proof cannot be relayed by someone sitting
// between two nodes. Two nodes connect only if both encrypt or neither does.
package node

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/binary"
	"errors"
	"io"
	"iter"
	"math"
	"math/big"
	"net"
	"sync"
	"time"

	"github.com/SmithOperatingSolutions/alchem/compiler/actor"
)

// Codec writes and reads the values of one type. Type names the type, so
// two nodes can check that they mean the same thing by a registered name.
type Codec[T any] struct {
	Type   string
	Encode func(*Encoder, T)
	Decode func(*Decoder) T
}

// Encoder builds the bytes of one message.
type Encoder struct {
	buf  []byte
	node *Node
}

func (e *Encoder) Int(v int64)     { e.buf = binary.AppendVarint(e.buf, v) }
func (e *Encoder) Float(v float64) { e.buf = binary.BigEndian.AppendUint64(e.buf, math.Float64bits(v)) }
func (e *Encoder) Bool(v bool) {
	if v {
		e.buf = append(e.buf, 1)
	} else {
		e.buf = append(e.buf, 0)
	}
}
func (e *Encoder) String(v string) {
	e.Int(int64(len(v)))
	e.buf = append(e.buf, v...)
}
func (e *Encoder) Atom(v actor.Atom) { e.String(string(v)) }

// Decoder reads the bytes of one message. A message that ends early or does
// not fit its type sets failed, and everything read after that is zero.
type Decoder struct {
	buf    []byte
	peer   *peer
	failed bool
}

func (d *Decoder) Int() int64 {
	v, n := binary.Varint(d.buf)
	if n <= 0 {
		d.failed, d.buf = true, nil
		return 0
	}
	d.buf = d.buf[n:]
	return v
}
func (d *Decoder) Float() float64 {
	if len(d.buf) < 8 {
		d.failed, d.buf = true, nil
		return 0
	}
	v := math.Float64frombits(binary.BigEndian.Uint64(d.buf))
	d.buf = d.buf[8:]
	return v
}
func (d *Decoder) Bool() bool {
	if len(d.buf) < 1 {
		d.failed = true
		return false
	}
	v := d.buf[0] != 0
	d.buf = d.buf[1:]
	return v
}
func (d *Decoder) String() string {
	n := d.Int()
	if n < 0 || n > int64(len(d.buf)) {
		d.failed, d.buf = true, nil
		return ""
	}
	v := string(d.buf[:n])
	d.buf = d.buf[n:]
	return v
}
func (d *Decoder) Atom() actor.Atom { return actor.Atom(d.String()) }

// Length reads the size of a collection, refusing one the message cannot hold.
func (d *Decoder) Length() int {
	n := d.Int()
	if n < 0 || n > int64(len(d.buf)) {
		d.failed, d.buf = true, nil
		return 0
	}
	return int(n)
}

// Fail marks the message as not fitting its type.
func (d *Decoder) Fail() { d.failed = true }

// EncodeMap and DecodeMap carry a map as its entries.
func EncodeMap[K comparable, V any](e *Encoder, m actor.Map[K, V], key func(*Encoder, K), value func(*Encoder, V)) {
	e.Int(int64(actor.MapLen(m)))
	actor.MapEach(m, func(k K, v V) {
		key(e, k)
		value(e, v)
	})
}

func DecodeMap[K comparable, V any](d *Decoder, key func(*Decoder) K, value func(*Decoder) V) actor.Map[K, V] {
	out := actor.NewMapBuilder(actor.Map[K, V]{})
	for n := d.Length(); n > 0 && !d.failed; n-- {
		k := key(d)
		out.Put(k, value(d))
	}
	return out.Map()
}

// reach is how a local process is reached from outside: deliver decodes a
// message into its mailbox, and watch asks to be told of its exit.
type reach struct {
	pid     any
	deliver func(*Decoder) bool
	watch   func(tell func(reason string)) (bool, string)
	// exit passes on the exit of a process linked to this one.
	exit func(reason string)
}

func reachOf[T any](p *actor.PID[T], codec Codec[T]) reach {
	return reach{
		pid: p,
		deliver: func(d *Decoder) bool {
			value := codec.Decode(d)
			// A full mailbox holds the connection's reader back for a
			// while, the only pressure a distant sender feels, and then
			// the message is dropped.
			return !d.failed && actor.Deliver(p, value, 5*time.Second)
		},
		watch: func(tell func(string)) (bool, string) { return actor.WatchExit(p, tell) },
		exit:  func(reason string) { actor.ExitLinked(p, 0, reason) },
	}
}

// handle makes the handle to a process of another node.
func handle[T any](p *peer, node string, id int64, codec Codec[T]) *actor.PID[T] {
	return actor.RemotePID(&actor.Remote[T]{
		Node: node,
		ID:   id,
		Send: func(value T) bool {
			if p == nil {
				return false
			}
			e := &Encoder{node: p.node}
			e.buf = append(e.buf, frameSend)
			e.Int(id)
			codec.Encode(e, value)
			return p.write(e.buf)
		},
		Alive: func() bool { return p != nil && !p.isClosed() },
		// Exit tells the process's node that a process linked to it ended
		// for a reason.
		Exit: func(reason string) bool {
			if p == nil {
				return false
			}
			e := &Encoder{}
			e.buf = append(e.buf, frameExit)
			e.Int(id)
			e.String(reason)
			return p.write(e.buf)
		},
		// Monitor asks the process's node to report its exit. If the
		// connection is lost first the reason is "noconnection".
		Monitor: func(c *actor.Context) int64 {
			ref := actor.NextReference(c)
			if p == nil || !p.watch(ref, watching{c, id}) {
				actor.Notify(c, actor.Event{Ref: ref, PID: id, Reason: "noconnection"})
				return ref
			}
			e := &Encoder{}
			e.buf = append(e.buf, frameMonitor)
			e.Int(id)
			e.Int(ref)
			p.write(e.buf)
			return ref
		},
		// The other node may still report the exit; without an entry here
		// the report is ignored.
		Demonitor: func(ref int64) bool {
			if p == nil {
				return false
			}
			p.mu.Lock()
			defer p.mu.Unlock()
			_, known := p.monitors[ref]
			delete(p.monitors, ref)
			return known
		},
	})
}

// EncodePID writes a process handle as its node and number. A local process
// becomes reachable from other nodes by being mentioned in a message.
func EncodePID[T any](e *Encoder, p *actor.PID[T], codec Codec[T]) {
	if distant := actor.RemoteOf(p); distant != nil {
		e.String(distant.Node)
		e.Int(distant.ID)
		return
	}
	id := actor.LocalID(p)
	e.node.export(id, reachOf(p, codec))
	e.String(e.node.name)
	e.Int(id)
}

// DecodePID rebuilds a process handle: the local process itself when the
// handle has come home, and otherwise a handle that sends over the
// connection to its node.
func DecodePID[T any](d *Decoder, codec Codec[T]) *actor.PID[T] {
	name, id := d.String(), d.Int()
	n := d.peer.node
	if name == n.name {
		n.mu.Lock()
		entry, ok := n.exports[id]
		n.mu.Unlock()
		if local, fits := entry.pid.(*actor.PID[T]); ok && fits {
			return local
		}
		d.failed = true
		return handle[T](nil, name, id, codec)
	}
	n.mu.Lock()
	target := n.peers[name]
	n.mu.Unlock()
	// A handle to a node this one is not connected to cannot be used yet:
	// sends to it report failure.
	return handle(target, name, id, codec)
}

const (
	frameSend byte = iota + 1
	frameWhereis
	frameFound
	frameMonitor
	frameDown
	frameStreamInfo
	frameStreamPull
	frameExit
	magic      = "alchem node 4"
	frameLimit = 64 << 20
)

// Node is this program's end of its connections.
type Node struct {
	c        *actor.Context
	name     string
	cookie   string
	listener net.Listener
	identity tls.Certificate
	// encrypted is fixed when the node starts; a node only connects to
	// nodes with the same setting, so it is never negotiated down.
	encrypted bool
	mu        sync.Mutex
	peers     map[string]*peer
	exports   map[int64]reach
	watchers  map[string][]watcher
	closed    bool
}

type watcher struct {
	c   *actor.Context
	ref int64
}

// watching is a local process waiting to hear of a remote one's exit.
type watching struct {
	c  *actor.Context
	id int64
}

type peer struct {
	node    *Node
	name    string
	conn    net.Conn
	writing sync.Mutex
	mu      sync.Mutex
	pending map[int64]chan []byte
	next    int64
	closed  bool
	// monitors are the local processes monitoring processes of this peer.
	monitors map[int64]watching
}

func (n *Node) export(id int64, entry reach) {
	n.mu.Lock()
	if _, known := n.exports[id]; !known {
		n.exports[id] = entry
	}
	n.mu.Unlock()
}

func writeFrame(w io.Writer, payload []byte) error {
	header := binary.BigEndian.AppendUint32(nil, uint32(len(payload)))
	_, err := w.Write(append(header, payload...))
	return err
}

func readFrame(r io.Reader) ([]byte, error) {
	var header [4]byte
	if _, err := io.ReadFull(r, header[:]); err != nil {
		return nil, err
	}
	size := binary.BigEndian.Uint32(header[:])
	if size > frameLimit {
		return nil, errors.New("message too large")
	}
	payload := make([]byte, size)
	_, err := io.ReadFull(r, payload)
	return payload, err
}

func (p *peer) isClosed() bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.closed
}

// watch records a monitor, unless the connection has already closed.
func (p *peer) watch(ref int64, who watching) bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return false
	}
	p.monitors[ref] = who
	return true
}

func (p *peer) write(payload []byte) bool {
	p.writing.Lock()
	defer p.writing.Unlock()
	if p.isClosed() {
		return false
	}
	p.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	if err := writeFrame(p.conn, payload); err != nil {
		p.shut()
		return false
	}
	return true
}

// shut ends a connection and tells the processes watching the node or
// monitoring its processes.
func (p *peer) shut() {
	p.mu.Lock()
	if p.closed {
		p.mu.Unlock()
		return
	}
	p.closed = true
	for _, waiting := range p.pending {
		close(waiting)
	}
	p.pending = nil
	monitors := p.monitors
	p.monitors = nil
	p.mu.Unlock()
	p.conn.Close()
	for ref, watch := range monitors {
		actor.Notify(watch.c, actor.Event{Ref: ref, PID: watch.id, Reason: "noconnection"})
	}
	n := p.node
	n.mu.Lock()
	if n.peers[p.name] == p {
		delete(n.peers, p.name)
	}
	watchers := n.watchers[p.name]
	delete(n.watchers, p.name)
	n.mu.Unlock()
	for _, w := range watchers {
		actor.Notify(w.c, actor.Event{Ref: w.ref, Reason: "nodedown " + p.name})
	}
}

// identity makes the key and certificate a node presents. Nobody has signed
// it and nobody checks it: it exists so that TLS can encrypt, and the cookie
// decides who is let in.
func identity(name string) (tls.Certificate, error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return tls.Certificate{}, err
	}
	serial, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 120))
	if err != nil {
		return tls.Certificate{}, err
	}
	template := &x509.Certificate{
		SerialNumber: serial,
		Subject:      pkix.Name{CommonName: name},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().AddDate(20, 0, 0),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		return tls.Certificate{}, err
	}
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: key}, nil
}

// proof is what one end sends to show it knows the cookie: a keyed hash
// over a value both ends derive from this TLS session, the end's role and
// its name. Someone relaying between two nodes holds two different
// sessions, so a proof made for one is wrong for the other.
func proof(cookie string, binding []byte, role, name string) []byte {
	mac := hmac.New(sha256.New, []byte(cookie))
	mac.Write(binding)
	mac.Write([]byte{0})
	mac.Write([]byte(role))
	mac.Write([]byte{0})
	mac.Write([]byte(name))
	return mac.Sum(nil)
}

// secure encrypts a connection and checks that the other end knows the
// cookie, returning the encrypted connection and the other node's name.
// Before anything else crosses, each end says whether it encrypts, in one
// unencrypted byte: the dialling end first, then the accepting end answers
// with its own. Both must match, so a node that encrypts never talks to one
// that does not, whatever anyone between them says.
const (
	modeEncrypted byte = 'T'
	modePlain     byte = 'P'
)

func (n *Node) mode() byte {
	if n.encrypted {
		return modeEncrypted
	}
	return modePlain
}

func (n *Node) agree(raw net.Conn, dialling bool) error {
	var other [1]byte
	if dialling {
		if _, err := raw.Write([]byte{n.mode()}); err != nil {
			return err
		}
		if _, err := io.ReadFull(raw, other[:]); err != nil {
			return errors.New("the other end closed the connection before saying whether it encrypts; it may not be an Alchem node of this version")
		}
	} else {
		if _, err := io.ReadFull(raw, other[:]); err != nil {
			return err
		}
		raw.Write([]byte{n.mode()})
	}
	switch {
	case other[0] == n.mode():
		return nil
	case n.encrypted && other[0] == modePlain:
		return errors.New("this node encrypts its connections and the other node does not; start both with the same encrypted: setting")
	case !n.encrypted && other[0] == modeEncrypted:
		return errors.New("the other node encrypts its connections and this one does not; start both with the same encrypted: setting")
	}
	return errors.New("the other end is not an Alchem node of this version")
}

func (n *Node) secure(raw net.Conn, dialling bool) (net.Conn, string, error) {
	raw.SetDeadline(time.Now().Add(10 * time.Second))
	defer raw.SetDeadline(time.Time{})
	if err := n.agree(raw, dialling); err != nil {
		return nil, "", err
	}
	mine, theirs := "accepting", "dialling"
	if dialling {
		mine, theirs = theirs, mine
	}
	var conn net.Conn = raw
	var binding []byte
	if n.encrypted {
		var secured *tls.Conn
		if dialling {
			// The certificate is not verified: no authority vouches for a
			// node. The cookie proof below, tied to this session, is what
			// establishes who is at the other end.
			secured = tls.Client(raw, &tls.Config{InsecureSkipVerify: true, MinVersion: tls.VersionTLS13})
		} else {
			secured = tls.Server(raw, &tls.Config{Certificates: []tls.Certificate{n.identity}, MinVersion: tls.VersionTLS13})
		}
		if err := secured.Handshake(); err != nil {
			return nil, "", errors.New("could not set up an encrypted connection: " + err.Error())
		}
		state := secured.ConnectionState()
		exported, err := state.ExportKeyingMaterial("alchem node cookie proof", nil, 32)
		if err != nil {
			return nil, "", err
		}
		conn, binding = secured, exported
	} else {
		// Without encryption there is no session to tie the proof to. Each
		// end contributes a random value and both proofs cover the two, so
		// a proof recorded from one connection is no use on another. It does
		// not stop someone relaying between two nodes, and anyone who sees
		// the traffic can test guesses of the cookie against it.
		own := make([]byte, 32)
		rand.Read(own)
		if err := writeFrame(raw, own); err != nil {
			return nil, "", err
		}
		other, err := readFrame(raw)
		if err != nil || len(other) != 32 {
			return nil, "", errors.New("malformed greeting")
		}
		mixed := sha256.New()
		if dialling {
			mixed.Write(own)
			mixed.Write(other)
		} else {
			mixed.Write(other)
			mixed.Write(own)
		}
		binding = mixed.Sum(nil)
	}
	hello := &Encoder{}
	hello.String(magic)
	hello.String(n.name)
	hello.String(string(proof(n.cookie, binding, mine, n.name)))
	if err := writeFrame(conn, hello.buf); err != nil {
		return nil, "", err
	}
	payload, err := readFrame(conn)
	if err != nil {
		// A node that rejects this one's proof closes without a word.
		return nil, "", errors.New("the other node closed the connection; the nodes may not share a cookie")
	}
	greeting := &Decoder{buf: payload}
	if greeting.String() != magic {
		return nil, "", errors.New("the other end is not an Alchem node of this version")
	}
	name, shown := greeting.String(), greeting.String()
	if greeting.failed || name == "" {
		return nil, "", errors.New("malformed greeting")
	}
	if !hmac.Equal([]byte(shown), proof(n.cookie, binding, theirs, name)) {
		return nil, "", errors.New("the nodes do not share a cookie")
	}
	if name == n.name {
		return nil, "", errors.New("both nodes are named " + name)
	}
	return conn, name, nil
}

// attach adds a secured connection and starts reading from it.
func (n *Node) attach(conn net.Conn, name string) error {
	p := &peer{node: n, name: name, conn: conn, pending: map[int64]chan []byte{}, monitors: map[int64]watching{}}
	n.mu.Lock()
	if n.closed {
		n.mu.Unlock()
		conn.Close()
		return errors.New("the node has stopped")
	}
	if n.peers[name] != nil {
		n.mu.Unlock()
		conn.Close()
		return nil
	}
	n.peers[name] = p
	n.mu.Unlock()
	go p.read()
	return nil
}

func (p *peer) reply(request int64, fill func(*Encoder)) {
	e := &Encoder{node: p.node}
	e.buf = append(e.buf, frameFound)
	e.Int(request)
	fill(e)
	p.write(e.buf)
}

func (p *peer) read() {
	defer p.shut()
	n := p.node
	for {
		payload, err := readFrame(p.conn)
		if err != nil || len(payload) == 0 {
			return
		}
		d := &Decoder{buf: payload[1:], peer: p}
		switch payload[0] {
		case frameSend:
			id := d.Int()
			n.mu.Lock()
			target, ok := n.exports[id]
			n.mu.Unlock()
			if ok && !d.failed {
				target.deliver(d)
			}
		case frameWhereis:
			request, name, kind := d.Int(), d.String(), d.String()
			entry, alive := actor.LookupName(n.c, name)
			found := false
			if extra, ok := entry.Extra.(reach); ok && alive && entry.Kind == kind && !d.failed {
				n.export(entry.ID, extra)
				found = true
			}
			p.reply(request, func(e *Encoder) {
				e.Bool(found)
				e.Int(entry.ID)
			})
		case frameMonitor:
			id, ref := d.Int(), d.Int()
			down := func(reason string) {
				e := &Encoder{}
				e.buf = append(e.buf, frameDown)
				e.Int(ref)
				e.Int(id)
				e.String(reason)
				p.write(e.buf)
			}
			n.mu.Lock()
			target, ok := n.exports[id]
			n.mu.Unlock()
			if !ok || d.failed {
				down("noproc")
				break
			}
			if ended, reason := target.watch(down); ended {
				down(reason)
			}
		case frameDown:
			ref, id, reason := d.Int(), d.Int(), d.String()
			p.mu.Lock()
			watch, ok := p.monitors[ref]
			delete(p.monitors, ref)
			p.mu.Unlock()
			if ok && !d.failed {
				actor.Notify(watch.c, actor.Event{Ref: ref, PID: id, Reason: reason})
			}
		case frameStreamInfo:
			request, name, kind := d.Int(), d.String(), d.String()
			offered := published(n.c).find(name)
			p.reply(request, func(e *Encoder) { e.Bool(offered != nil && offered.kind == kind && !d.failed) })
		case frameStreamPull:
			request, name, subscription, finished := d.Int(), d.String(), d.Int(), d.Bool()
			offered := published(n.c).find(name)
			if offered == nil || d.failed {
				if !finished {
					// Nothing is published under the name: an empty chunk
					// that ends the stream.
					p.reply(request, func(e *Encoder) {
						e.Bool(true)
						e.Int(0)
					})
				}
				break
			}
			select {
			case offered.requests <- pull{p, request, subscription, finished}:
			case <-time.After(30 * time.Second):
			}
		case frameExit:
			id, reason := d.Int(), d.String()
			n.mu.Lock()
			target, ok := n.exports[id]
			n.mu.Unlock()
			if ok && !d.failed && target.exit != nil {
				target.exit(reason)
			}
		case frameFound:
			request := d.Int()
			p.mu.Lock()
			waiting := p.pending[request]
			delete(p.pending, request)
			p.mu.Unlock()
			if waiting != nil {
				waiting <- d.buf
			}
		}
	}
}

func current(c *actor.Context) *Node {
	n, _ := actor.Extension(c, "node", nil).(*Node)
	return n
}

// Start makes this program a node listening at an address such as
// "127.0.0.1:4000"; port 0 picks a free one. With encrypted false its
// connections are not encrypted. It returns "" or what went wrong.
func Start(c *actor.Context, name, address, cookie string, encrypted bool) string {
	actor.Check(c)
	switch {
	case current(c) != nil:
		return "this program is already a node"
	case name == "":
		return "a node needs a name"
	case cookie == "":
		return "a node needs a cookie: the secret every node of the cluster shares"
	}
	var certificate tls.Certificate
	if encrypted {
		made, err := identity(name)
		if err != nil {
			return err.Error()
		}
		certificate = made
	}
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return err.Error()
	}
	n := &Node{c: c, name: name, cookie: cookie, listener: listener, identity: certificate, encrypted: encrypted, peers: map[string]*peer{}, exports: map[int64]reach{}, watchers: map[string][]watcher{}}
	if kept := actor.Extension(c, "node", func() any { return n }); kept != any(n) {
		listener.Close()
		return "this program is already a node"
	}
	actor.AtClose(c, n.shutdown)
	go func() {
		for {
			raw, err := listener.Accept()
			if err != nil {
				return
			}
			go func() {
				conn, name, err := n.secure(raw, false)
				if err != nil {
					raw.Close()
					return
				}
				n.attach(conn, name)
			}()
		}
	}()
	return ""
}

// Name and Address describe this node; both are "" before Start.
func Name(c *actor.Context) string {
	if n := current(c); n != nil {
		return n.name
	}
	return ""
}

func Address(c *actor.Context) string {
	if n := current(c); n != nil {
		return n.listener.Addr().String()
	}
	return ""
}

// Connect connects to the node listening at an address and returns its
// name, or "" and what went wrong.
func Connect(c *actor.Context, address string) (string, string) {
	actor.Check(c)
	n := current(c)
	if n == nil {
		return "", "start this node first, with Node.start"
	}
	raw, err := net.DialTimeout("tcp", address, 10*time.Second)
	if err != nil {
		return "", err.Error()
	}
	conn, name, err := n.secure(raw, true)
	if err != nil {
		raw.Close()
		return "", err.Error()
	}
	if err := n.attach(conn, name); err != nil {
		return "", err.Error()
	}
	return name, ""
}

// dial connects to the node at an address without a process to act for.
func (n *Node) dial(address string) (string, string) {
	raw, err := net.DialTimeout("tcp", address, 10*time.Second)
	if err != nil {
		return "", err.Error()
	}
	conn, name, err := n.secure(raw, true)
	if err != nil {
		raw.Close()
		return "", err.Error()
	}
	if err := n.attach(conn, name); err != nil {
		return "", err.Error()
	}
	return name, ""
}

// reconnectPoll is how often a kept connection is checked.
const reconnectPoll = 50 * time.Millisecond

// Reconnect connects to the node at an address, as Connect does, and keeps
// the connection: when it is lost it is made again, after a second at first
// and up to 30 seconds apart while it keeps failing, until this node stops.
func Reconnect(c *actor.Context, address string) (string, string) {
	name, problem := Connect(c, address)
	if problem != "" {
		return "", problem
	}
	n := current(c)
	go func() {
		// The wait is counted from when the connection was found lost, or
		// from the last failed attempt, not from a fixed tick: a connection
		// lost just before a tick would otherwise be made again at once.
		wait, lost := time.Second, time.Time{}
		for {
			time.Sleep(reconnectPoll)
			n.mu.Lock()
			closed, connected := n.closed, n.peers[name] != nil
			n.mu.Unlock()
			switch {
			case closed:
				return
			case connected:
				wait, lost = time.Second, time.Time{}
			case lost.IsZero():
				lost = time.Now()
			case time.Since(lost) >= wait:
				if _, problem := n.dial(address); problem != "" {
					wait, lost = min(wait*2, 30*time.Second), time.Now()
				}
			}
		}
	}()
	return name, ""
}

// List names the nodes this one is connected to.
func List(c *actor.Context) []string {
	n := current(c)
	if n == nil {
		return nil
	}
	n.mu.Lock()
	defer n.mu.Unlock()
	names := make([]string, 0, len(n.peers))
	for name := range n.peers {
		names = append(names, name)
	}
	return names
}

func (n *Node) peer(name string) *peer {
	n.mu.Lock()
	defer n.mu.Unlock()
	return n.peers[name]
}

// Disconnect closes the connection to a node.
func Disconnect(c *actor.Context, name string) bool {
	n := current(c)
	if n == nil {
		return false
	}
	p := n.peer(name)
	if p == nil {
		return false
	}
	p.shut()
	return true
}

// Monitor asks for one event when the connection to a node ends: its reason
// is "nodedown" and the node's name. A node that is not connected produces
// the event at once.
func Monitor(c *actor.Context, name string) int64 {
	actor.Check(c)
	ref := actor.NextReference(c)
	connected := false
	if n := current(c); n != nil {
		n.mu.Lock()
		if n.peers[name] != nil {
			n.watchers[name] = append(n.watchers[name], watcher{c, ref})
			connected = true
		}
		n.mu.Unlock()
	}
	if !connected {
		actor.Notify(c, actor.Event{Ref: ref, Reason: "nodedown " + name})
	}
	return ref
}

// Register gives a process a name by which this node and others can find
// it. A name belongs to one living process at a time.
func Register[T any](c *actor.Context, p *actor.PID[T], name string, codec Codec[T]) bool {
	if p == nil || actor.RemoteOf(p) != nil {
		return false
	}
	return actor.RegisterName(c, p, name, codec.Type, reachOf(p, codec))
}

// Unregister frees a name.
func Unregister(c *actor.Context, name string) bool { return actor.UnregisterName(c, name) }

// Whereis finds a process of this node by name; the name must have been
// registered for the same message type.
func Whereis[T any](c *actor.Context, name string, codec Codec[T]) (*actor.PID[T], bool) {
	entry, alive := actor.LookupName(c, name)
	if !alive {
		return nil, false
	}
	p, fits := entry.PID.(*actor.PID[T])
	return p, fits
}

// ask sends a request to the peer and waits for its answer.
func (p *peer) ask(c *actor.Context, kind byte, ms int64, fill func(*Encoder)) ([]byte, bool) {
	answer := make(chan []byte, 1)
	p.mu.Lock()
	if p.closed {
		p.mu.Unlock()
		return nil, false
	}
	p.next++
	request := p.next
	p.pending[request] = answer
	p.mu.Unlock()
	e := &Encoder{node: p.node}
	e.buf = append(e.buf, kind)
	e.Int(request)
	fill(e)
	if !p.write(e.buf) {
		return nil, false
	}
	timer, stop := actor.After(max(ms, 1))
	defer stop()
	select {
	case body, ok := <-answer:
		return body, ok
	case <-timer:
		p.mu.Lock()
		delete(p.pending, request)
		p.mu.Unlock()
	case <-actor.Stopping(c):
		actor.Check(c)
	}
	return nil, false
}

// RemoteWhereis finds a process another node has registered, waiting up to
// ms milliseconds for its answer. The name must be registered there for the
// same message type.
func RemoteWhereis[T any](c *actor.Context, node, name string, ms int64, codec Codec[T]) (*actor.PID[T], bool) {
	actor.Check(c)
	n := current(c)
	if n == nil {
		return nil, false
	}
	p := n.peer(node)
	if p == nil {
		return nil, false
	}
	body, ok := p.ask(c, frameWhereis, ms, func(e *Encoder) {
		e.String(name)
		e.String(codec.Type)
	})
	if !ok {
		return nil, false
	}
	d := &Decoder{buf: body, peer: p}
	if found, id := d.Bool(), d.Int(); found && !d.failed {
		return handle(p, node, id, codec), true
	}
	return nil, false
}

// shutdown closes the listener and every connection when the program ends.
func (n *Node) shutdown() {
	n.mu.Lock()
	n.closed = true
	peers := make([]*peer, 0, len(n.peers))
	for _, p := range n.peers {
		peers = append(peers, p)
	}
	n.mu.Unlock()
	n.listener.Close()
	for _, p := range peers {
		p.shut()
	}
}

// A published stream stays on its node. Another node pulls it a chunk at a
// time, so only what is consumed crosses, and a stream too large to hold,
// or without end, can still be read from elsewhere. The stream is built and
// advanced by a process of its own node, once for each reader.

const (
	chunkItems = 256
	chunkBytes = 64 << 10
)

type publication struct {
	kind     string
	requests chan pull
}

type pull struct {
	from         *peer
	request      int64
	subscription int64
	finished     bool
}

type reader struct {
	from         *peer
	subscription int64
}

// streams are what a program offers, whether or not it is yet a node.
type streams struct {
	mu     sync.Mutex
	byName map[string]*publication
}

func published(c *actor.Context) *streams {
	return actor.Extension(c, "node streams", func() any { return &streams{byName: map[string]*publication{}} }).(*streams)
}

func (s *streams) find(name string) *publication {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.byName[name]
}

// PublishStream offers a stream to other nodes under a name. build makes
// the stream, once for each reader, inside the process that serves it.
func PublishStream[T any](c *actor.Context, name string, build func(*actor.Context) iter.Seq[T], codec Codec[T], where string) bool {
	actor.Check(c)
	table := published(c)
	offered := &publication{kind: codec.Type, requests: make(chan pull, 64)}
	table.mu.Lock()
	if _, taken := table.byName[name]; taken || name == "" {
		table.mu.Unlock()
		return false
	}
	table.byName[name] = offered
	table.mu.Unlock()
	actor.Spawn(c, func(server *actor.Context, _ *actor.PID[struct{}]) int64 {
		type cursor struct {
			next func() (T, bool)
			stop func()
		}
		open := map[reader]cursor{}
		defer func() {
			table.mu.Lock()
			delete(table.byName, name)
			table.mu.Unlock()
			for _, each := range open {
				each.stop()
			}
		}()
		for {
			var asked pull
			select {
			case asked = <-offered.requests:
			case <-actor.Stopping(server):
				actor.Check(server)
			}
			// Readers whose node has gone are forgotten.
			for key, each := range open {
				if key.from.isClosed() {
					each.stop()
					delete(open, key)
				}
			}
			key := reader{asked.from, asked.subscription}
			at, reading := open[key]
			if asked.finished {
				if reading {
					at.stop()
					delete(open, key)
				}
				continue
			}
			if !reading {
				at.next, at.stop = iter.Pull(build(server))
				open[key] = at
			}
			items := &Encoder{node: asked.from.node}
			count, done := int64(0), false
			for count < chunkItems && len(items.buf) < chunkBytes {
				value, more := at.next()
				if !more {
					done = true
					break
				}
				codec.Encode(items, value)
				count++
			}
			if done {
				at.stop()
				delete(open, key)
			}
			asked.from.reply(asked.request, func(e *Encoder) {
				e.Bool(done)
				e.Int(count)
				e.buf = append(e.buf, items.buf...)
			})
		}
	}, 1, where)
	return true
}

// RemoteStream finds a stream another node has published and returns one
// that pulls from it as it is consumed, or what went wrong.
func RemoteStream[T any](c *actor.Context, node, name string, codec Codec[T], where string) (iter.Seq[T], string) {
	actor.Check(c)
	n := current(c)
	if n == nil {
		return nil, "start this node first, with Node.start"
	}
	p := n.peer(node)
	if p == nil {
		return nil, "not connected to node " + node
	}
	body, ok := p.ask(c, frameStreamInfo, 5000, func(e *Encoder) {
		e.String(name)
		e.String(codec.Type)
	})
	if !ok {
		return nil, "node " + node + " did not answer"
	}
	if d := (&Decoder{buf: body}); !d.Bool() {
		return nil, "node " + node + " publishes no stream " + name + " of " + codec.Type
	}
	return func(yield func(T) bool) {
		p.mu.Lock()
		p.next++
		subscription := p.next
		p.mu.Unlock()
		finished := false
		defer func() {
			if !finished {
				e := &Encoder{}
				e.buf = append(e.buf, frameStreamPull)
				e.Int(0)
				e.String(name)
				e.Int(subscription)
				e.Bool(true)
				p.write(e.buf)
			}
		}()
		for {
			body, ok := p.ask(c, frameStreamPull, 30000, func(e *Encoder) {
				e.String(name)
				e.Int(subscription)
				e.Bool(false)
			})
			if !ok {
				finished = true
				actor.Fail(c, where, "the node holding the stream stopped answering")
			}
			d := &Decoder{buf: body, peer: p}
			done, count := d.Bool(), d.Int()
			for ; count > 0 && !d.failed; count-- {
				if !yield(codec.Decode(d)) {
					finished = done
					return
				}
			}
			if done || d.failed {
				finished = true
				return
			}
		}
	}, ""
}
