#!/usr/bin/env python3
"""TLS: TCP.connect_tls, https and wss addresses and HTTP.serve_tls, as the pinned compiler runs them.

The library's TLS (library/TLS.alc, spec/alchem-tls.md) against other
implementations, on this machine alone: 127.0.0.1 on ports the system
chooses, no name looked up, no address outside. Four parts.

KNOWN: a program that calls the library's own functions (a module named
Alchem... may) and writes what they give for known inputs: the machine code
of spec/tls-x86_64.s (large numbers against Python's integers; AES-GCM on
both of its paths, ChaCha20-Poly1305 and AES-CBC against the published
vectors), X25519 (RFC 7748), Ed25519 (RFC 8032), the curves P-256, P-384 and
P-521 against arithmetic written here, RSA with PKCS #1 v1.5 and PSS against
Python's pow, the key schedules against hmac and hashlib, and the reading and
verification of certificates at a fixed time.

CLIENTS: a native program dials servers of Python's ssl module (OpenSSL)
that show the certificates of tls_data.py; what it writes is what the same
program built by the pinned compiler writes (EXPECT, frozen when this file
was made; with build/dev/alchem-upstream at hand the pinned program is run
again and compared). SERVERS: a native HTTP.serve_tls is asked by Python's
ssl, by curl and by openssl s_client where they are installed, and by a
native client over https and wss; what they see is what they see of the
pinned server. FILES: what HTTP.serve_tls says of certificate and key files
it cannot use.

Each program runs under scripts/limited in a session of its own, which is
killed whole when the program is done or out of time."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import base64
import hashlib
import hmac
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import warnings

sys.path.insert(0,str(Path(__file__).resolve().parent))
import tls_data as DATA

ROOT=Path(__file__).resolve().parents[1]
T12=ssl.TLSVersion.TLSv1_2

# ---- arithmetic to check the library against ----
CURVES={
 23:(0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff,0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b,
     0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296,0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5,
     0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551,32),
 24:(2**384-2**128-2**96+2**32-1,0xb3312fa7e23ee7e4988e056be3f82d19181d9c6efe8141120314088f5013875ac656398d8a2ed19d2a85c8edd3ec2aef,
     0xaa87ca22be8b05378eb1c71ef320ad746e1d3b628ba79b9859f741e082542a385502f25dbf55296c3a545e3872760ab7,0x3617de4a96262c6f5d9e98bf9292dc29f8f41dbd289a147ce9da3113b5f0b8c00a60b1ce1d7e819d7a431d7c90ea0e5f,
     0xffffffffffffffffffffffffffffffffffffffffffffffffc7634d81f4372ddf581a0db248b0a77aecec196accc52973,48),
 25:(2**521-1,0x0051953eb9618e1c9a1f929a21a0b68540eea2da725b99b315f3b8b489918ef109e156193951ec7e937b1652c0bd3bb1bf073573df883d2c34f1ef451fd46b503f00,
     0x00c6858e06b70404e9cd9e3ecb662395b4429c648139053fb521f828af606b4d3dbaa14b5e77efe75928fe1dc127a2ffa8de3348b3c1856a429bf97e7e31c2e5bd66,0x011839296a789a3bc0045c8a5fb42c7d1bd998f54449579b446817afbd17273e662c97ee72995ef42640c550b9013fad0761353c7086a272c24088be94769fd16650,
     0x01fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffa51868783bf2f966b7fcc0148f709a5d03bb5c9b8899c47aebb6fb71e91386409,66)}


def ec_add(c,a,b):
    p=CURVES[c][0]
    if a is None:return b
    if b is None:return a
    if a[0]==b[0] and (a[1]+b[1])%p==0:return None
    l=(3*a[0]*a[0]-3)*pow(2*a[1],-1,p)%p if a==b else (b[1]-a[1])*pow(b[0]-a[0],-1,p)%p
    x=(l*l-a[0]-b[0])%p
    return x,(l*(a[0]-x)-a[1])%p


def ec_mul(c,k,point):
    r=None
    while k:
        if k&1:r=ec_add(c,r,point)
        point=ec_add(c,point,point);k>>=1
    return r


def ec_point(c,point):
    size=CURVES[c][5]
    return '04'+point[0].to_bytes(size,'big').hex()+point[1].to_bytes(size,'big').hex()


def ec_e(c,digest):
    n,size=CURVES[c][4],CURVES[c][5]
    return int.from_bytes(digest[:size],'big')


def ec_verify(c,pub,digest,r,s):
    n=CURVES[c][4]
    if not (0<r<n and 0<s<n):return False
    w=pow(s,-1,n)
    got=ec_add(c,ec_mul(c,ec_e(c,digest)*w%n,(CURVES[c][2],CURVES[c][3])),ec_mul(c,r*w%n,pub))
    return got is not None and got[0]%n==r


def ec_sign(c,d,digest,k):
    n=CURVES[c][4]
    r=ec_mul(c,k,(CURVES[c][2],CURVES[c][3]))[0]%n
    return r,pow(k,-1,n)*(ec_e(c,digest)+r*d)%n


def der_ints(der):
    """The INTEGERs of a SEQUENCE of them (an RSA key of PKCS #1)."""
    def element(i):
        size=der[i+1];i+=2
        if size&128:
            count=size&127;size=int.from_bytes(der[i:i+count],'big');i+=count
        return i,size
    i,size=element(0);stop=i+size;found=[]
    while i<stop:
        assert der[i]==2
        j,size=element(i);found.append(int.from_bytes(der[j:j+size],'big'));i=j+size
    return found


def pem_bytes(text):
    return base64.b64decode(''.join(line for line in text.split('\n') if line and not line.startswith('-----')))


def mgf1(seed,size,name):
    out=b'';i=0
    while len(out)<size:
        out+=hashlib.new(name,seed+i.to_bytes(4,'big')).digest();i+=1
    return out[:size]


def pss_ok(n,e,sig,digest,name):
    bits=n.bit_length()-1;size=(bits+7)//8;h=len(digest)
    em=pow(int.from_bytes(sig,'big'),e,n).to_bytes((n.bit_length()+7)//8,'big')[-size:]
    if em[-1]!=0xbc:return False
    masked,hh=em[:size-h-1],em[size-h-1:-1]
    db=bytearray(a^b for a,b in zip(masked,mgf1(hh,size-h-1,name)))
    db[0]&=0xff>>(8*size-bits)
    if db[:size-2*h-2]!=bytes(size-2*h-2) or db[size-2*h-2]!=1:return False
    return hashlib.new(name,bytes(8)+digest+bytes(db[-h:])).digest()==hh


def expand_label(name,secret,label,context,size):
    info=size.to_bytes(2,'big')+bytes([6+len(label)])+b'tls13 '+label+bytes([len(context)])+context
    return hmac.new(secret,info+b'\x01',name).digest()[:size]


def prf12(name,secret,label,seed,size):
    seed=label+seed;a=seed;out=b''
    while len(out)<size:
        a=hmac.new(secret,a,name).digest();out+=hmac.new(secret,a+seed,name).digest()
    return out[:size]


# ---- KNOWN ----
NOW=1795000000   # 2026-11-18, for the certificates
KAT_HEAD=r'''defmodule AlchemKat do
  def h(s: string): string do
    String.downcase(Base.encode16(s))
  end
  def big(name: string, k: integer, bits: integer, v: list[string]): integer do
    [m, a, b, e, wide] = v
    c = TLS._mont(TLS._limbs(TLS._hex(m), k), k)
    al = TLS._limbs(TLS._hex(a), k)
    bl = TLS._limbs(TLS._hex(b), k)
    r = TLS._lz(k)
    TLS._t(2, c, r, al, bl)
    IO.puts(name <> " mul " <> h(TLS._bytes(r, k, 8 * k)))
    TLS._t(3, c, r, al, bl)
    IO.puts(name <> " add " <> h(TLS._bytes(r, k, 8 * k)))
    TLS._t(4, c, r, al, bl)
    IO.puts(name <> " sub " <> h(TLS._bytes(r, k, 8 * k)))
    TLS._exp(c, r, al, TLS._limbs(TLS._hex(e), k), bits)
    IO.puts(name <> " exp " <> h(TLS._bytes(r, k, 8 * k)))
    TLS._t(7, c, r, TLS._limbs(TLS._hex(wide), 2 * k), 2 * k)
    IO.puts(name <> " red " <> h(TLS._bytes(r, k, 8 * k)))
    IO.puts(name <> " cmp " <> inspect(TLS._t(10, al, bl, k, 0)) <> " " <> inspect(TLS._t(10, bl, al, k, 0)) <> " " <> inspect(TLS._t(10, al, al, k, 0)))
    IO.puts(name <> " ctx " <> h(TLS._bytes(c + 8, 1, 8)) <> " " <> h(TLS._bytes(c + 16 + 8 * k, k, 8 * k)) <> " " <> h(TLS._bytes(c + 16 + 16 * k, k, 8 * k)))
    0
  end
  def aead(name: string, seal: integer, key: integer, v: list[string]): integer do
    [nonce, aad, text] = v
    n = byte_size(text)
    out = String.duplicate("\x00", n)
    tag = String.duplicate("\x00", 16)
    TLS._t9(seal, key, Sys.addr(nonce), aad, [Sys.addr(text), n, Sys.addr(out)], Sys.addr(tag))
    back = String.duplicate("\x00", n)
    fine = TLS._t9(seal + 1, key, Sys.addr(nonce), aad, [Sys.addr(out), n, Sys.addr(back)], Sys.addr(tag))
    other = TLS._xor(tag, String.duplicate("\x00", 15) <> "\x01")
    wrong = TLS._t9(seal + 1, key, Sys.addr(nonce), aad, [Sys.addr(out), n, Sys.addr(back)], Sys.addr(other))
    IO.puts(name <> " " <> h(out) <> " " <> h(tag) <> " " <> inspect(fine) <> inspect(back == text) <> " " <> inspect(wrong))
    0
  end
  def gcm(name: string, force: integer, v: list[string]): integer do
    [key, nonce, aad, text] = v
    ctx = String.duplicate("\x00", 512)
    TLS._t(16, Sys.addr(ctx), Sys.addr(key), byte_size(key), force)
    aead(name <> " " <> inspect(Sys.peek(Sys.addr(ctx) + 8) + force), 17, Sys.addr(ctx), [nonce, aad, text])
  end
  def cbc(name: string, force: integer, v: list[string]): integer do
    [key, iv, text] = v
    ctx = String.duplicate("\x00", 512)
    TLS._t(16, Sys.addr(ctx), Sys.addr(key), byte_size(key), force)
    n = byte_size(text)
    out = String.duplicate("\x00", n)
    k = TLS._g() + 64
    Sys.poke(k + 40, Sys.addr(out))
    a = TLS._t(22, Sys.addr(ctx), Sys.addr(iv), Sys.addr(text), n)
    back = String.duplicate("\x00", n)
    Sys.poke(k + 40, Sys.addr(back))
    b = TLS._t(23, Sys.addr(ctx), Sys.addr(iv), Sys.addr(out), n)
    IO.puts(name <> " " <> inspect(force) <> " " <> h(out) <> " " <> inspect(a + b) <> inspect(back == text))
    0
  end
  def ec(name: string, id: integer, v: list[string]): integer do
    [d, peer, digest, r, s] = v
    c = TLS._curve(id)
    pub = TLS._ecpub(c, TLS._hex(d))
    IO.puts(name <> " pub " <> h(pub))
    IO.puts(name <> " ecdh " <> h(TLS._ecdh(c, TLS._hex(d), TLS._hex(peer))))
    off = TLS._xor(TLS._hex(peer), String.duplicate("\x00", byte_size(TLS._hex(peer)) - 1) <> "\x01")
    IO.puts(name <> " ecdh off the curve " <> inspect(TLS._ecdh(c, TLS._hex(d), off)))
    IO.puts(name <> " verify " <> inspect(TLS._ecverify(c, pub, TLS._hex(digest), TLS._hex(r), TLS._hex(s))) <> inspect(TLS._ecverify(c, pub, "x" <> TLS._hex(digest), TLS._hex(r), TLS._hex(s))) <> inspect(TLS._ecverify(c, pub, TLS._hex(digest), TLS._hex(s), TLS._hex(r))) <> inspect(TLS._ecverify(c, pub, TLS._hex(digest), "", TLS._hex(s))))
    sig = TLS._ecsign(c, TLS._hex(d), TLS._hex(digest))
    n = div(byte_size(sig), 2)
    IO.puts(name <> " sign " <> h(sig) <> " " <> inspect(TLS._ecverify(c, pub, TLS._hex(digest), TLS._sub(sig, 0, n), TLS._sub(sig, n, n))))
    0
  end
  def trust(name: string, chain: list[string], roots: string, host: string, now: integer): integer do
    empty: list[tuple[string, string]] = []
    ders = Enum.map(Enum.flat_map(chain, fn f -> TLS._pem(TCP._file(f), 0) end), fn x -> elem(x, 1) end)
    pool = if roots == "" do empty else TLS._pool(empty, TCP._file(roots)) end
    IO.puts(name <> ": " <> elem(TLS._verify(ders, pool, host, now, false), 1))
    0
  end
  def pair(a: string, b: string): integer do
    {id, why} = TLS._keypair(a, b)
    IO.puts(a <> " " <> b <> ": " <> (if why == "" do "kind #{elem(id, 1)} curve #{elem(id, 2)} certificates #{length(elem(id, 0))}" else why end))
    0
  end
  def main() do
'''
KAT_TAIL='''  end
end
'''


def known(directory):
    """The program and what it must write, line by line; a line of None is checked by `checks`."""
    body=[];want=[];checks={}
    def line(text,expected):body.append('    '+text+'\n');want.extend(expected)
    for b in DATA.BIG:
        k=b['k'];m,a,c,e,wide=(int(b[x],16) for x in ('m','a','b','e','wide'));R=1<<(64*k);size=16*k
        f=lambda v:'%0*x'%(size,v)
        line(f'big("{b["name"]}", {k}, {b["bits"]}, ["{b["m"]}", "{b["a"]}", "{b["b"]}", "{b["e"]}", "{b["wide"]}"])',
             [f'{b["name"]} mul '+f(a*c*pow(R,-1,m)%m),f'{b["name"]} add '+f((a+c)%m),f'{b["name"]} sub '+f((a-c)%m),
              f'{b["name"]} exp '+f(pow(a,e&((1<<b["bits"])-1),m)),f'{b["name"]} red '+f(wide%m),
              f'{b["name"]} cmp {(a>c)-(a<c)} {(c>a)-(c<a)} 0',f'{b["name"]} ctx '+'%016x'%((-pow(m,-1,1<<64))%(1<<64))+' '+f(R*R%m)+' '+f(R%m)])
    for i,v in enumerate(DATA.GCM):
        for force in (0,1):
            line(f'gcm("gcm {i}", {force}, [TLS._hex("{v["key"]}"), TLS._hex("{v["nonce"]}"), TLS._hex("{v["aad"]}"), TLS._hex("{v["plaintext"]}")])',[None])
            checks[len(want)-1]=('gcm',i,force,v)
    for i,v in enumerate(DATA.CHACHA):
        line(f'aead("chacha {i}", 20, Sys.addr(TLS._hex("{v["key"]}")), [TLS._hex("{v["nonce"]}"), TLS._hex("{v["aad"]}"), TLS._hex("{v["plaintext"]}")])',
             [f'chacha {i} {v["ciphertext"]} {v["tag"]} 1true 0'])
    for i,v in enumerate(DATA.CBC):
        for force in (0,1):
            line(f'cbc("cbc {i}", {force}, [TLS._hex("{v["key"]}"), TLS._hex("{v["iv"]}"), TLS._hex("{v["plaintext"]}")])',[f'cbc {i} {force} {v["ciphertext"]} 2true'])
    line('IO.puts("cbc of 15 bytes " <> inspect(TLS._t(22, Sys.addr(String.duplicate("\\x00", 512)), Sys.addr(String.duplicate("\\x00", 16)), Sys.addr(String.duplicate("\\x00", 16)), 15)))',['cbc of 15 bytes 0'])
    # RFC 7748, 5.2 and 6.1.
    line('IO.puts("x25519 " <> h(TLS._x25519(TLS._hex("a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4"), TLS._hex("e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c"))))',
         ['x25519 c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552'])
    line('IO.puts("x25519 " <> h(TLS._x25519(TLS._hex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"), TLS._hex("de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f"))))',
         ['x25519 4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742'])
    # RFC 8032, 7.1, tests 1 to 3.
    for seed,pk,message,sig in [
        ('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60','d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a','','e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b'),
        ('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb','3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c','72','92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00'),
        ('c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7','fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025','af82','6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a')]:
        line(f'key{len(want)} = TLS._edkey(TLS._hex("{seed}"))',[])
        line(f'IO.puts("ed25519 " <> h(elem(key{len(want)}, 1)) <> " " <> h(TLS._edsign(key{len(want)}, TLS._hex("{message}"))) <> " " <> inspect(TLS._edverify(TLS._hex("{pk}"), TLS._hex("{message}"), TLS._hex("{sig}"))) <> inspect(TLS._edverify(TLS._hex("{pk}"), TLS._hex("{message}") <> "x", TLS._hex("{sig}"))) <> inspect(TLS._edverify(TLS._hex("{pk}"), TLS._hex("{message}"), TLS._hex("{sig[:64]}" <> "{"ff"*32}"))))',
             [f'ed25519 {pk} {sig} truefalsefalse'])
    for c,(p,b,gx,gy,n,size) in CURVES.items():
        d=int.from_bytes(hashlib.sha512(b'private %d'%c).digest()*2,'big')%(n-1)+1
        other=int.from_bytes(hashlib.sha512(b'peer %d'%c).digest()*2,'big')%(n-1)+1
        g=(gx,gy);pub=ec_mul(c,d,g);peer=ec_mul(c,other,g)
        digest=hashlib.sha384(b'message %d'%c).digest()
        r,s=ec_sign(c,d,digest,int.from_bytes(hashlib.sha512(b'nonce %d'%c).digest()*2,'big')%(n-1)+1)
        assert ec_verify(c,pub,digest,r,s)
        f=lambda v:v.to_bytes(size,'big').hex()
        line(f'ec("p{c}", {c}, ["{f(d)}", "{ec_point(c,peer)}", "{digest.hex()}", "{f(r)}", "{f(s)}"])',
             [f'p{c} pub {ec_point(c,pub)}',f'p{c} ecdh {f(ec_mul(c,d,peer)[0])}',f'p{c} ecdh off the curve ""',f'p{c} verify truefalsefalsefalse',None])
        checks[len(want)-1]=('ecsign',c,pub,digest)
    # RSA: the key of leaf-rsa as PKCS #1 holds it.
    version,n,e,d=der_ints(pem_bytes(DATA.PEMS['leaf-rsa.pkcs1.key']))[:4]
    size=(n.bit_length()+7)//8;f=lambda v:'%0*x'%(2*size,v)
    digest=hashlib.sha256(b'an RSA message').digest()
    em=b'\x00\x01'+b'\xff'*(size-3-19-32)+b'\x00'+bytes.fromhex('3031300d060960864801650304020105000420')+digest
    line(f'rsa = {{TLS._hex("{f(n)}"), TLS._hex("{"%x"%e if len("%x"%e)%2==0 else "0%x"%e}"), TLS._hex("{f(d)}")}}',[])
    line(f'IO.puts("rsa pkcs1 " <> h(TLS._rsasign(rsa, 1, 3, TLS._hex("{digest.hex()}"))))',['rsa pkcs1 '+f(pow(int.from_bytes(em,'big'),d,n))])
    line(f'pss = TLS._rsasign(rsa, 2, 3, TLS._hex("{digest.hex()}"))',[])
    line(f'IO.puts("rsa pss " <> h(pss) <> " " <> inspect(TLS._rsaverify(elem(rsa, 0), elem(rsa, 1), 2, 3, TLS._hex("{digest.hex()}"), pss)) <> inspect(TLS._rsaverify(elem(rsa, 0), elem(rsa, 1), 2, 3, TLS._hex("{hashlib.sha256(b"other").hexdigest()}"), pss)) <> inspect(TLS._rsaverify(elem(rsa, 0), elem(rsa, 1), 1, 3, TLS._hex("{digest.hex()}"), pss)))',[None])
    checks[len(want)-1]=('pss',n,e,digest)
    # The key schedules.
    secret=hashlib.sha384(b'a secret').digest()
    for name,alg,size in (('sha256',3,32),('sha384',4,48)):
        key=secret[:size];context=hashlib.new(name,b'messages').digest()
        line(f'IO.puts("hkdf {name} " <> h(TLS._hx({alg}, TLS._hex("{key.hex()}"), "c hs traffic", TLS._hex("{context.hex()}"), {size})) <> " " <> h(TLS._hx({alg}, TLS._hex("{key.hex()}"), "iv", "", 12)))',
             [f'hkdf {name} '+expand_label(name,key,b'c hs traffic',context,size).hex()+' '+expand_label(name,key,b'iv',b'',12).hex()])
        line(f'IO.puts("prf {name} " <> h(TLS._prf({alg}, TLS._hex("{key.hex()}"), "key expansion", TLS._hex("{context.hex()}"), 104)))',[f'prf {name} '+prf12(name,key,b'key expansion',context,104).hex()])
    # RFC 5246 has no vector; this one is the usual test of the PRF with SHA-256.
    line('IO.puts("prf " <> h(TLS._prf(3, TLS._hex("9bbe436ba940f017b17652849a71db35"), "test label", TLS._hex("a0ba9f936cda311827a6f796ffd5198c"), 100)))',
         ['prf e3f229ba727be17b8d122620557cd453c2aab21d07c3d495329b52d4e61edb5a6b301791e90d35c9c9a46b4e14baf9af0fa022f7077def17abfd3797c0564bab4fbc91666e9def9b97fce34f796789baa48082d122ee42c5a72e5a5110fff70187347b66'])
    # Certificates, at a fixed time.
    for name,chain,roots,host,now,expected in TRUST:
        files=', '.join('"%s"'%x for x in chain)
        line(f'trust("{name}", [{files}], "{roots}", "{host}", {now})',[name+': '+expected])
    for a,b,expected in FILES:
        line(f'pair("{a}", "{b}")',[f'{a} {b}: {expected}'])
    line('{texts, nums, dns, ips} = TLS._cert(elem(hd(TLS._pem(TCP._file("leaf-rsa.crt"), 0)), 1))',[])
    line('IO.puts(inspect(nums) <> " " <> inspect(dns) <> " " <> inspect(Enum.map(ips, fn x -> TLS._ipshow(x) end)) <> " " <> Enum.at(texts, 9, ""))',
         ['[3, 19, 1, 0, 1577836800, 4102444799, 1, 0, -1, 40960, 2, 1, 0, 0] ["localhost", "*.example.test"] ["127.0.0.1", "::1"] leaf rsa'])
    return KAT_HEAD+''.join(body)+KAT_TAIL,want,checks


UNKNOWN='tls: failed to verify certificate: x509: certificate signed by unknown authority'
TRUST=[
 ('chain rsa',['leaf-rsa.crt','inter.crt'],'root.crt','localhost',NOW,''),
 ('chain p256',['leaf-p256.crt','inter.crt'],'root.crt','127.0.0.1',NOW,''),
 ('chain p384',['leaf-p384.crt','inter.crt'],'root.crt','[::1]',NOW,''),
 ('chain p521',['leaf-p521.crt','inter.crt'],'root.crt','A.Example.Test',NOW,''),
 ('chain ed',['leaf-ed.crt','inter.crt'],'root.crt','localhost.',NOW,''),
 ('the root sent too',['leaf-rsa.crt','inter.crt','root.crt'],'root.crt','localhost',NOW,''),
 ('no name asked',['leaf-rsa.crt','inter.crt'],'root.crt','',NOW,''),
 ('two labels under a wildcard',['leaf-rsa.crt','inter.crt'],'root.crt','a.b.example.test',NOW,'tls: failed to verify certificate: x509: certificate is valid for localhost, *.example.test, not a.b.example.test'),
 ('another address',['leaf-rsa.crt','inter.crt'],'root.crt','127.0.0.9',NOW,'tls: failed to verify certificate: x509: certificate is valid for 127.0.0.1, ::1, not 127.0.0.9'),
 ('no intermediate',['leaf-rsa.crt'],'root.crt','localhost',NOW,UNKNOWN),
 ('another root',['leaf-rsa.crt','inter.crt'],'root2.crt','localhost',NOW,UNKNOWN),
 ('no roots',['leaf-rsa.crt','inter.crt'],'','localhost',NOW,UNKNOWN),
 ('after 2099',['leaf-rsa.crt','inter.crt'],'root.crt','localhost',4102444800,'tls: failed to verify certificate: x509: certificate has expired or is not yet valid: current time 2100-01-01T00:00:00Z is after 2099-12-31T23:59:59Z'),
 ('before 2020',['leaf-rsa.crt','inter.crt'],'root.crt','localhost',1500000000,'tls: failed to verify certificate: x509: certificate has expired or is not yet valid: current time 2017-07-14T02:40:00Z is before 2020-01-01T00:00:00Z'),
 ('expired',['expired.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: certificate has expired or is not yet valid: current time 2026-11-18T11:06:40Z is after 2021-01-01T00:00:00Z'),
 ('not yet valid',['future.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: certificate has expired or is not yet valid: current time 2026-11-18T11:06:40Z is before 2098-01-01T00:00:00Z'),
 ('another host',['other.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: certificate is valid for other.test, not localhost'),
 ('a common name alone',['nosan.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: certificate relies on legacy Common Name field, use SANs instead'),
 ('no names',['nosan.crt'],'root.crt','elsewhere.test',NOW,'tls: failed to verify certificate: x509: certificate is not valid for any names, but wanted to match elsewhere.test'),
 ('no addresses',['nosan.crt'],'root.crt','127.0.0.1',NOW,"tls: failed to verify certificate: x509: cannot validate certificate for 127.0.0.1 because it doesn't contain any IP SANs"),
 ('for clients alone',['clientonly.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: certificate specifies an incompatible key usage'),
 ('a critical extension nobody knows',['critical.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: unhandled critical extension'),
 ('issued by what is no authority',['under-notca.crt','notca.crt'],'root.crt','localhost',NOW,UNKNOWN+' (possibly because of "x509: invalid signature: parent certificate cannot sign this kind of certificate" while trying to verify candidate authority certificate "Not A CA")'),
 ('a path too long',['under-deep.crt','deep.crt','inter.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: too many intermediates for path length constraint'),
 ('names permitted',['nc-good.crt','nc.crt'],'root.crt','a.example.test',NOW,''),
 ('a name not permitted',['nc-bad.crt','nc.crt'],'root.crt','localhost',NOW,'tls: failed to verify certificate: x509: a root or intermediate certificate is not authorized to sign for this name: DNS name "localhost" is not permitted by any constraint'),
 ('a name excluded',['nc-excl.crt','nc.crt'],'root.crt','bad.example.test',NOW,'tls: failed to verify certificate: x509: a root or intermediate certificate is not authorized to sign for this name: DNS name "bad.example.test" is excluded by constraint "bad.example.test"'),
 ('self rsa',['self-rsa.crt'],'self-rsa.crt','localhost',NOW,''),
 ('self rsa 4096 sha512',['self-rsa4.crt'],'self-rsa4.crt','localhost',NOW,''),
 ('self pss',['self-pss.crt'],'self-pss.crt','localhost',NOW,''),
 ('self p256',['self-p256.crt'],'self-p256.crt','localhost',NOW,''),
 ('self p384',['self-p384.crt'],'self-p384.crt','localhost',NOW,''),
 ('self p521',['self-p521.crt'],'self-p521.crt','localhost',NOW,''),
 ('self ed25519',['self-ed.crt'],'self-ed.crt','localhost',NOW,''),
 ('self-signed and not trusted',['self-p256.crt'],'root.crt','localhost',NOW,UNKNOWN),
 ('signed with sha1',['self-sha1.crt'],'root.crt','localhost',NOW,UNKNOWN),
 ('no certificate',[],'root.crt','localhost',NOW,'tls: received empty certificates message'),
 ('no certificate at all',['garbage.crt'],'root.crt','localhost',NOW,'tls: failed to parse certificate from server: x509: malformed certificate'),
]
TAGS="{optional:false explicit:false application:false private:false defaultValue:<nil> tag:<nil> stringType:0 timeType:0 set:false omitEmpty:false}"
FILES=[
 ('leaf-rsa.crt','leaf-rsa.key','kind 1 curve 0 certificates 1'),
 ('leaf-rsa.crt','leaf-rsa.pkcs1.key','kind 1 curve 0 certificates 1'),
 ('chain-p256.pem','leaf-p256.key','kind 2 curve 23 certificates 2'),
 ('leaf-p256.crt','leaf-p256.sec1.key','kind 2 curve 23 certificates 1'),
 ('leaf-p384.crt','leaf-p384.key','kind 2 curve 24 certificates 1'),
 ('leaf-p521.crt','leaf-p521.key','kind 2 curve 25 certificates 1'),
 ('leaf-ed.crt','leaf-ed.key','kind 3 curve 0 certificates 1'),
 ('none.crt','leaf-rsa.key','open none.crt: no such file or directory'),
 ('leaf-rsa.crt','none.key','open none.key: no such file or directory'),
 ('empty.txt','leaf-rsa.key','tls: failed to find any PEM data in certificate input'),
 ('leaf-rsa.crt','empty.txt','tls: failed to find any PEM data in key input'),
 ('leaf-rsa.key','leaf-rsa.crt','tls: failed to find certificate PEM data in certificate input, but did find a private key; PEM inputs may have been switched'),
 ('leaf-rsa.crt','leaf-rsa.crt','tls: found a certificate rather than a key in the PEM for the private key'),
 ('foo.pem','leaf-rsa.key','tls: failed to find "CERTIFICATE" PEM block in certificate input after skipping PEM blocks of the following types: [FOO BAR]'),
 ('leaf-rsa.crt','foo.pem','tls: failed to find PEM block with type ending in "PRIVATE KEY" in key input after skipping PEM blocks of the following types: [FOO BAR]'),
 ('leaf-rsa.crt','leaf-p256.key','tls: private key type does not match public key type'),
 ('leaf-p256.crt','leaf-ed.key','tls: private key type does not match public key type'),
 ('leaf-p256.crt','leaf-p384.key','tls: private key does not match public key'),
 ('leaf-ed.crt','self-ed.key','tls: private key does not match public key'),
 ('leaf-rsa.crt','self-rsa.key','tls: private key does not match public key'),
 ('garbage.crt','leaf-rsa.key','x509: malformed certificate'),
 ('leaf-rsa.crt','garbage.key',"tls: failed to parse private key: asn1: structure error: tags don't match (16 vs {class:0 tag:0 length:0 isCompound:false}) "+TAGS+" pkcs8 @2"),
 ('leaf-p256.crt','enc.key',"tls: failed to parse private key: asn1: structure error: tags don't match (2 vs {class:0 tag:16 length:87 isCompound:true}) "+TAGS+" int @2"),
]

# ---- CLIENTS ----
CLIENT='''defmodule T do
  def opts(ca: string, name: string, insecure: string): list[tuple[atom, string]] do
    a = if ca == "-" do [] else [ca_file: ca] end
    b = if name == "-" do [] else [server_name: name] end
    c = if insecure == "-" do [] else [insecure: insecure] end
    a ++ b ++ c
  end
  def main() do
    [kind, addr, ca, name, insecure] = System.argv()
    if kind == "tcp" do
      case TCP.connect_tls(addr, 5000, opts(ca, name, insecure)) do
        ok(s) ->
          IO.puts(inspect(TCP.send(s, "ping\\n")))
          IO.puts(inspect(TCP.recv_line(s, 3000)))
          IO.puts(inspect(TCP.shutdown(s, :write)))
          IO.puts(inspect(TCP.peer(s) != none))
          IO.puts(inspect(TCP.close(s)))
        error(why) -> IO.puts("error: " <> why)
      end
    end
    if kind == "quick" do
      case TCP.connect_tls(addr, 300) do
        ok(s) -> IO.puts("connected")
        error(why) -> IO.puts("error: " <> why)
      end
    end
    if kind == "big" do
      case TCP.connect_tls(addr, 5000, opts(ca, name, insecure)) do
        ok(s) ->
          sent = String.duplicate("0123456789abcdef", 12500)
          IO.puts(inspect(TCP.send(s, sent <> "\\n")))
          case TCP.recv(s, 200007, 10000) do
            ok(back) -> IO.puts(inspect(back == "pong: " <> sent <> "\\n"))
            error(why) -> IO.puts("error: " <> why)
          end
          IO.puts(inspect(TCP.recv(s, 0, 3000)))
        error(why) -> IO.puts("error: " <> why)
      end
    end
    if kind == "http" do
      case HTTP.request("GET", "https://" <> addr <> "/x", [{"X-Test", "1"}], "", opts(ca, "-", insecure)) do
        ok(r) -> IO.puts(inspect(r.status) <> " " <> inspect(r.body))
        error(why) -> IO.puts("error: " <> why)
      end
    end
    if kind == "get" do
      case HTTP.get("https://" <> addr <> "/x") do
        ok(r) -> IO.puts(inspect(r.status) <> " " <> inspect(r.body))
        error(why) -> IO.puts("error: " <> why)
      end
    end
    if kind == "ws" do
      case WebSocket.connect("wss://" <> addr <> "/ws", 5000, opts(ca, "-", insecure)) do
        ok(w) ->
          IO.puts(inspect(WebSocket.send(w, "hello")))
          IO.puts(inspect(WebSocket.recv(w, 3000)))
          IO.puts(inspect(WebSocket.close(w)))
        error(why) -> IO.puts("error: " <> why)
      end
    end
  end
end
'''
FINE='ok({}) | ok("pong: ping") | error("not a connected socket") | true | true'
VERIFY='error: tls: failed to verify certificate: x509: '


def client_cases():
    """Name, how the server is, the program's arguments (A: the server's address), its environment, what it writes."""
    cases=[];root='root.crt'
    def case(name,server,arguments,expected,env=None):cases.append((name,server,arguments,env or {},expected))
    for t in ('rsa','p256','p384','p521','ed'):
        case(f'tcp {t} 1.3',dict(chain=f'chain-{t}.pem',key=f'leaf-{t}.key'),['tcp','A',root,'localhost','-'],FINE)
        case(f'tcp {t} 1.2',dict(chain=f'chain-{t}.pem',key=f'leaf-{t}.key',maxv=T12),['tcp','A',root,'-','-'],FINE)
        case(f'https {t} 1.3',dict(chain=f'chain-{t}.pem',key=f'leaf-{t}.key'),['http','A',root,'-','-'],'200 "hi\\n"')
        case(f'https {t} 1.2',dict(chain=f'chain-{t}.pem',key=f'leaf-{t}.key',maxv=T12),['http','A',root,'-','-'],'200 "hi\\n"')
    rsa=dict(chain='chain-rsa.pem',key='leaf-rsa.key');p256=dict(chain='chain-p256.pem',key='leaf-p256.key')
    for name,ciphers in (('aes128','TLS_AES_128_GCM_SHA256'),('aes256','TLS_AES_256_GCM_SHA384'),('chacha','TLS_CHACHA20_POLY1305_SHA256')):
        case(f'1.3 {name}',dict(rsa,suites=ciphers),['tcp','A',root,'-','-'],FINE)
    for name,ciphers in (('rsa aes128 gcm','ECDHE-RSA-AES128-GCM-SHA256'),('rsa aes256 gcm','ECDHE-RSA-AES256-GCM-SHA384'),('rsa chacha','ECDHE-RSA-CHACHA20-POLY1305'),('rsa aes128 cbc','ECDHE-RSA-AES128-SHA'),('rsa aes256 cbc','ECDHE-RSA-AES256-SHA')):
        case(f'1.2 {name}',dict(rsa,maxv=T12,ciphers=ciphers),['tcp','A',root,'-','-'],FINE)
    for name,ciphers in (('ecdsa aes128 gcm','ECDHE-ECDSA-AES128-GCM-SHA256'),('ecdsa aes256 gcm','ECDHE-ECDSA-AES256-GCM-SHA384'),('ecdsa chacha','ECDHE-ECDSA-CHACHA20-POLY1305'),('ecdsa aes128 cbc','ECDHE-ECDSA-AES128-SHA'),('ecdsa aes256 cbc','ECDHE-ECDSA-AES256-SHA')):
        case(f'1.2 {name}',dict(p256,maxv=T12,ciphers=ciphers),['tcp','A',root,'-','-'],FINE)
    for group in ('prime256v1','secp384r1','secp521r1','X25519'):
        case(f'1.3 group {group}',dict(p256,groups=group),['tcp','A',root,'-','-'],FINE)
        case(f'1.2 group {group}',dict(rsa,groups=group,maxv=T12),['tcp','A',root,'-','-'],FINE)
    case('200000 bytes 1.3',dict(rsa,big=True),['big','A',root,'-','-'],'ok({}) | true | error("closed")')
    case('200000 bytes 1.2 cbc',dict(rsa,big=True,maxv=T12,ciphers='ECDHE-RSA-AES256-SHA'),['big','A',root,'-','-'],'ok({}) | true | error("closed")')
    case('200000 bytes 1.2 chacha',dict(rsa,big=True,maxv=T12,ciphers='ECDHE-RSA-CHACHA20-POLY1305'),['big','A',root,'-','-'],'ok({}) | true | error("closed")')
    case('a certificate asked for, 1.3',dict(rsa,verify=ssl.CERT_OPTIONAL),['tcp','A',root,'-','-'],FINE)
    case('a certificate asked for, 1.2',dict(rsa,verify=ssl.CERT_OPTIONAL,maxv=T12),['tcp','A',root,'-','-'],FINE)
    case('a certificate required, 1.3',dict(rsa,verify=ssl.CERT_REQUIRED),['tcp','A',root,'-','-'],'ok({}) | error("remote error: tls: certificate required") | error("not a connected socket") | true | true')
    case('a certificate required, 1.2',dict(rsa,verify=ssl.CERT_REQUIRED,maxv=T12),['http','A',root,'-','-'],'error: Get "https://ADDR/x": remote error: tls: handshake failure')
    case('unknown authority',rsa,['tcp','A','root2.crt','-','-'],VERIFY+'certificate signed by unknown authority')
    case('the roots of SSL_CERT_FILE',rsa,['tcp','A','-','-','-'],FINE,dict(SSL_CERT_FILE='root.crt',SSL_CERT_DIR='/nonexistent'))
    case('the roots of SSL_CERT_DIR',rsa,['get','A','-','-','-'],'200 "hi\\n"',dict(SSL_CERT_FILE='/nonexistent',SSL_CERT_DIR='/nonexistent:certs'))
    case('no roots',rsa,['get','A','-','-','-'],'error: Get "https://ADDR/x": tls: failed to verify certificate: x509: certificate signed by unknown authority',dict(SSL_CERT_FILE='/nonexistent',SSL_CERT_DIR='/nonexistent'))
    case('insecure',rsa,['tcp','A','-','-','true'],FINE,dict(SSL_CERT_FILE='/nonexistent',SSL_CERT_DIR='/nonexistent'))
    case('insecure: "false"',rsa,['tcp','A','-','-','false'],VERIFY+'certificate signed by unknown authority',dict(SSL_CERT_FILE='/nonexistent',SSL_CERT_DIR='/nonexistent'))
    case('https insecure',dict(chain='expired.crt',key='expired.key'),['http','A','-','-','true'],'200 "hi\\n"')
    case('no intermediate',dict(chain='leaf-rsa.crt',key='leaf-rsa.key'),['tcp','A',root,'-','-'],VERIFY+'certificate signed by unknown authority')
    case('expired',dict(chain='expired.crt',key='expired.key'),['tcp','A',root,'-','-'],VERIFY+'certificate has expired or is not yet valid: current time NOW is after 2021-01-01T00:00:00Z')
    case('not yet valid',dict(chain='future.crt',key='future.key'),['http','A',root,'-','-'],'error: Get "https://ADDR/x": tls: failed to verify certificate: x509: certificate has expired or is not yet valid: current time NOW is before 2098-01-01T00:00:00Z')
    case('another address',dict(chain='other.crt',key='other.key'),['tcp','A',root,'-','-'],VERIFY+'certificate is valid for 127.0.0.2, not 127.0.0.1')
    case('another name',dict(chain='other.crt',key='other.key'),['tcp','A',root,'localhost','-'],VERIFY+'certificate is valid for other.test, not localhost')
    case('server_name: that is not its name',rsa,['tcp','A',root,'nothere.test','-'],VERIFY+'certificate is valid for localhost, *.example.test, not nothere.test')
    case('a wildcard',rsa,['tcp','A',root,'A.Example.Test','-'],FINE)
    case('a common name alone',dict(chain='nosan.crt',key='nosan.key'),['tcp','A',root,'localhost','-'],VERIFY+'certificate relies on legacy Common Name field, use SANs instead')
    case('for clients alone',dict(chain='clientonly.crt',key='clientonly.key'),['tcp','A',root,'-','-'],VERIFY+'certificate specifies an incompatible key usage')
    case('a path too long',dict(chain='chain-deep.pem',key='under-deep.key'),['tcp','A',root,'-','-'],VERIFY+'too many intermediates for path length constraint')
    case('a name not permitted',dict(chain='chain-nc-bad.pem',key='nc-bad.key'),['tcp','A',root,'localhost','-'],VERIFY+'a root or intermediate certificate is not authorized to sign for this name: DNS name "localhost" is not permitted by any constraint')
    for t in ('rsa','rsa4','pss','p256','p384','p521','ed','sha1'):
        case(f'self-signed {t}, trusted',dict(chain=f'self-{t}.crt',key=f'self-{t}.key'),['tcp','A',f'self-{t}.crt','-','-'],FINE)
    case('ca_file: that is not there',rsa,['tcp','A','none.crt','-','-'],'error: open none.crt: no such file or directory')
    case('ca_file: without certificates',rsa,['http','A','leaf-rsa.key','-','-'],'error: no certificates in leaf-rsa.key')
    case('a server of plain HTTP',dict(rsa,plain=b'HTTP/1.1 400 Bad Request\r\n\r\n'),['http','A',root,'-','-'],'error: Get "https://ADDR/x": http: server gave HTTP response to HTTPS client')
    case('a server of something else',dict(rsa,plain=b'hello there, this is not TLS\n'),['tcp','A',root,'-','-'],'error: tls: first record does not look like a TLS handshake')
    case('a server that says nothing',dict(rsa,silent=True),['quick','A',root,'-','-'],'error: timeout')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        old=ssl.TLSVersion.TLSv1_1
    case('a server of TLS 1.1',dict(rsa,maxv=old,minv=old,ciphers='ALL:@SECLEVEL=0'),['tcp','A',root,'-','-'],'error: remote error: tls: protocol version not supported')
    case('a server of DHE alone',dict(rsa,maxv=T12,ciphers='DHE-RSA-AES128-GCM-SHA256'),['tcp','A',root,'-','-'],'error: remote error: tls: handshake failure')
    return cases


def serving(directory,chain,key,minv=None,maxv=None,ciphers=None,suites=None,groups=None,plain=None,verify=None,silent=False,big=False):
    """A server of Python's ssl module on a port of its own: the listening socket."""
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(directory/chain),str(directory/key))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        if minv:context.minimum_version=minv
        if maxv:context.maximum_version=maxv
    if ciphers:context.set_ciphers(ciphers)
    if suites:
        if not hasattr(context,'set_ciphersuites'):return None
        context.set_ciphersuites(suites)
    if groups:context.set_ecdh_curve(groups)
    if verify is not None:
        context.verify_mode=verify;context.load_verify_locations(str(directory/'root.crt'))
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('127.0.0.1',0));listener.listen(8)
    def one(raw):
        try:
            raw.settimeout(15)
            if silent:
                time.sleep(2);return
            if plain is not None:
                raw.recv(100);raw.sendall(plain);return
            # The handshake is made apart from the wrapping: wrap_socket closes
            # the connection itself when the handshake it makes fails.
            secured=context.wrap_socket(raw,server_side=True,do_handshake_on_connect=False)
            try:secured.do_handshake()
            except ssl.SSLError:
                # A handshake refused (a certificate required, 1.3) is closed
                # once the client has closed, with what it wrote after the
                # handshake read: closing with that unread, or before it is
                # written, resets the connection, and the client's write then
                # fails or not as the reset comes before it or after.
                left=socket.socket(fileno=secured.detach())
                try:
                    left.shutdown(socket.SHUT_WR);left.settimeout(15)
                    while left.recv(65536):pass
                finally:left.close()
                return
            data=secured.recv(65536)
            while big and not data.endswith(b'\n'):data+=secured.recv(65536)
            if data.startswith(b'GET '):secured.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\nhi\n')
            else:secured.sendall(b'pong: '+data)
            try:secured.unwrap()
            except (ssl.SSLError,OSError):pass
            secured.close()
        except (ssl.SSLError,OSError):pass
        finally:
            try:raw.close()
            except OSError:pass
    def accept():
        while True:
            try:raw,_=listener.accept()
            except OSError:return
            threading.Thread(target=one,args=(raw,),daemon=True).start()
    threading.Thread(target=accept,daemon=True).start()
    return listener


def bounds(directory,seconds,more=None):
    env=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),ALCHEM_SECONDS=str(seconds),ALCHEM_MEMORY='3G',TMPDIR=str(directory))
    for name in ('XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'):
        if name in os.environ:env[name]=os.environ[name]
    env.update(more or {})
    return env


def build(compiler,source,path):
    built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=180)
    assert (built.returncode,built.stderr)==(0,b''),(source[:200],built.returncode,built.stderr)
    path.unlink(missing_ok=True);path.write_bytes(built.stdout);path.chmod(0o700)
    return path


def pinned(source,path):
    """The program as the pinned compiler builds it, or None where that compiler is not at hand."""
    upstream=ROOT/'build/dev/alchem-upstream'
    if not upstream.exists():return None
    text=path.with_suffix('.alc');text.write_text(source)
    built=subprocess.run([str(upstream),'build','-o',str(path),str(text)],capture_output=True,env=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=mod'),timeout=600)
    return path if built.returncode==0 and path.exists() else None


def killed(process):
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait()


def ran(program,arguments,directory,env=None,seconds=40):
    process=subprocess.Popen([str(ROOT/'scripts/limited'),str(program)]+arguments,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=bounds(directory,seconds,env),cwd=directory,start_new_session=True)
    try:out,_=process.communicate(timeout=seconds+30)
    finally:killed(process)
    return out.decode(errors='replace')


def said(text):
    """What a client wrote, without what differs from run to run: ports and the time."""
    return re.sub(r'current time \S+','current time NOW',re.sub(r'127\.0\.0\.1:\d+','ADDR',text.strip())).replace('\n',' | ')


def clients(programs,directory):
    count=0;skipped=0
    def one(case):
        name,server,arguments,env,expected=case
        listener=serving(directory,**server)
        if listener is None:return None
        try:
            address='127.0.0.1:%d'%listener.getsockname()[1]
            return [said(ran(program,[address if x=='A' else x for x in arguments],directory,env)) for program in programs]
        finally:listener.close()
    cases=client_cases()
    with ThreadPoolExecutor(8) as pool:results=list(pool.map(one,cases))
    for (name,server,arguments,env,expected),got in zip(cases,results):
        if got is None:skipped+=1;continue
        for which,text in zip(('native','pinned'),got):
            assert text==expected,(name,which,text,expected)
        count+=1
    return count,skipped


def proxying(target,mode,seen):
    """A proxy that tunnels (CONNECT) to one address, refuses or hangs up: the listening socket."""
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('127.0.0.1',0));listener.listen(4)
    def pump(a,b):
        try:
            while True:
                part=a.recv(65536)
                if not part:break
                b.sendall(part)
        except OSError:pass
        try:b.shutdown(socket.SHUT_WR)
        except OSError:pass
    def one(raw):
        try:
            raw.settimeout(15);data=b''
            while b'\r\n\r\n' not in data:
                part=raw.recv(4096)
                if not part:break
                data+=part
            seen.append(re.sub(rb':\d{4,5}',b':PORT',data))
            if mode=='deny':raw.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
            elif mode=='tunnel':
                with socket.create_connection(target,timeout=15) as there:
                    raw.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
                    threading.Thread(target=pump,args=(raw,there),daemon=True).start();pump(there,raw)
        except OSError:pass
        finally:
            try:raw.close()
            except OSError:pass
    def accept():
        while True:
            try:raw,_=listener.accept()
            except OSError:return
            threading.Thread(target=one,args=(raw,),daemon=True).start()
    threading.Thread(target=accept,daemon=True).start()
    return listener


CONNECT=b'CONNECT a.example.test:PORT HTTP/1.1\r\nHost: a.example.test:PORT\r\nUser-Agent: Go-http-client/1.1\r\n'
TUNNELS=[('tunnel','http://ADDR','200 "hi\\n"',[CONNECT+b'\r\n']),
 ('tunnel','http://user:pw@ADDR','200 "hi\\n"',[CONNECT+b'Proxy-Authorization: Basic dXNlcjpwdw==\r\n\r\n']),
 ('deny','ADDR','error: Get "https://a.example.test:PORT/x": Forbidden',[CONNECT+b'\r\n']),
 ('hang up','http://ADDR','error: Get "https://a.example.test:PORT/x": unexpected EOF',[CONNECT+b'\r\n']),
 ('nobody','http://127.0.0.1:1','error: Get "https://a.example.test:PORT/x": proxyconnect tcp: dial tcp ADDR: connect: connection refused',[])]


def tunnels(programs,directory):
    """https through the proxy of HTTPS_PROXY: what the program writes and what the proxy was asked."""
    server=serving(directory,'chain-rsa.pem','leaf-rsa.key')
    try:
        port=server.getsockname()[1]
        for mode,proxy,expected,asked_for in TUNNELS:
            for program in programs:
                seen=[];listener=proxying(('127.0.0.1',port),mode,seen)
                try:
                    wrote=said(ran(program,['http',f'a.example.test:{port}','root.crt','-','-'],directory,dict(HTTPS_PROXY=proxy.replace('ADDR','127.0.0.1:%d'%listener.getsockname()[1]))))
                finally:listener.close()
                wrote=re.sub(r'a\.example\.test:\d+','a.example.test:PORT',wrote)
                assert (wrote,seen)==(expected,asked_for),(mode,proxy,wrote,seen)
    finally:server.close()
    return len(TUNNELS)


# ---- SERVERS ----
SERVER='''defmodule T do
  def handle(r: HTTP.Request): HTTP.Response do
    if r.path == "/ws" do
      case WebSocket.upgrade(r) do
        ok(w) ->
          answered: result[tuple[], string] = case WebSocket.recv(w, 3000) do
            ok(WebSocket.Event.text(m)) -> WebSocket.send(w, "echo " <> m)
            _ -> ok({})
          end
          WebSocket.recv(w, 3000)
          HTTP.text(200, "")
        error(why) -> HTTP.text(400, why)
      end
    else
      HTTP.text(200, r.method <> " " <> r.path <> " " <> inspect(byte_size(r.body)) <> "\\n")
    end
  end
  def main() do
    [cert, key] = System.argv()
    case HTTP.serve_tls("127.0.0.1:0", fn(r: HTTP.Request): HTTP.Response do handle(r) end, [certfile: cert, keyfile: key]) do
      ok(s) ->
        IO.puts(HTTP.address(s))
        IO.read(:eof)
        IO.puts(inspect(HTTP.stop(s)))
      error(why) -> IO.puts("error: " <> why)
    end
  end
end
'''


def asked(directory,address,maxv=None,minv=None,ciphers=None,groups=None,request=b'GET /py HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n',ca='root.crt',host='localhost'):
    """What a client of Python's ssl module sees of a server."""
    try:
        context=ssl.create_default_context(cafile=str(directory/ca))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            if maxv:context.maximum_version=maxv
            if minv:context.minimum_version=minv
        if ciphers:context.set_ciphers(ciphers)
        if groups:context.set_ecdh_curve(groups)
        name,port=address.rsplit(':',1)
        with socket.create_connection((name,int(port)),timeout=20) as raw:
            with context.wrap_socket(raw,server_hostname=host) as secured:
                secured.sendall(request);data=b''
                while True:
                    part=secured.recv(65536)
                    if not part:break
                    data+=part
                return '%s %s %r %r'%(secured.version(),secured.cipher()[0],data.split(b'\r\n\r\n',1)[-1][-40:],secured.selected_alpn_protocol())
    except (ssl.SSLError,OSError) as problem:
        return 'ERR '+re.sub(r' \(_ssl\.c:\d+\)','',str(problem))


def plainly(address,data):
    name,port=address.rsplit(':',1)
    with socket.create_connection((name,int(port)),timeout=20) as raw:
        raw.sendall(data);raw.settimeout(3);got=b''
        try:
            while True:
                part=raw.recv(4096)
                if not part:break
                got+=part
        except OSError:got+=b' and nothing more'
        return repr(got)


def tool(arguments,stdin=b''):
    try:done=subprocess.run(arguments,input=stdin,capture_output=True,timeout=40)
    except subprocess.TimeoutExpired:return 'timed out'
    return (done.stdout+done.stderr).decode(errors='replace')


def staged(arguments,parts):
    """A tool given its input in parts, half a second apart, and a while to answer the last."""
    process=subprocess.Popen(arguments,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    out=[]
    reader=threading.Thread(target=lambda:out.append(process.stdout.read()),daemon=True);reader.start()
    try:
        for part in parts:
            if part:
                process.stdin.write(part);process.stdin.flush();time.sleep(0.5)
        try:process.wait(timeout=6)
        except subprocess.TimeoutExpired:pass
        try:process.stdin.close()
        except OSError:pass
        try:process.wait(timeout=20)
        except subprocess.TimeoutExpired:pass
    except OSError:pass
    finally:killed(process)
    reader.join(timeout=10)
    return (out[0] if out else b'').decode(errors='replace')


def served(program,kind,directory,client,optional):
    """What its clients see of a server with a key of a kind; a line per client."""
    process=subprocess.Popen([str(ROOT/'scripts/limited'),str(program),f'chain-{kind}.pem',f'leaf-{kind}.key'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=bounds(directory,150),cwd=directory,start_new_session=True)
    try:
        address=process.stdout.readline().decode().strip()
        assert re.fullmatch(r'127\.0\.0\.1:\d+',address),address
        port=address.rsplit(':',1)[1]
        auth='RSA' if kind=='rsa' else 'ECDSA'
        # In TLS 1.2 OpenSSL takes a certificate of a curve only when that curve is among its groups.
        own={'p256':'prime256v1','p384':'secp384r1','p521':'secp521r1'}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            old=ssl.TLSVersion.TLSv1_1
        seen=[asked(directory,address),asked(directory,address,maxv=T12),
              asked(directory,address,maxv=T12,ciphers='ECDHE+CHACHA20'),
              asked(directory,address,maxv=T12,ciphers='ECDHE+AES256+AESGCM',groups=own.get(kind,'secp384r1')),
              asked(directory,address,maxv=T12,ciphers=f'ECDHE-{auth}-AES128-SHA'),
              asked(directory,address,maxv=T12,ciphers=f'ECDHE-{auth}-AES256-SHA',groups=own.get(kind,'secp521r1')),
              asked(directory,address,groups='secp521r1'),asked(directory,address,groups='prime256v1'),
              asked(directory,address,maxv=old,minv=old,ciphers='ALL:@SECLEVEL=0'),
              asked(directory,address,maxv=T12,ciphers='DHE-RSA-AES128-GCM-SHA256'),
              asked(directory,address,request=b'POST /post HTTP/1.1\r\nHost: x\r\nContent-Length: 70000\r\nConnection: close\r\n\r\n'+b'z'*70000),
              asked(directory,address,maxv=T12,ciphers=f'ECDHE-{auth}-AES128-SHA',request=b'POST /post HTTP/1.1\r\nHost: x\r\nContent-Length: 70000\r\nConnection: close\r\n\r\n'+b'z'*70000),
              asked(directory,address,ca='root2.crt'),asked(directory,address,host='elsewhere.test'),
              plainly(address,b'GET / HTTP/1.1\r\nHost: x\r\n\r\n'),plainly(address,b'hello, not tls at all\r\n\r\n')]
        for arguments in (['http',address,'root.crt','-','-'],['ws',address,'root.crt','-','-'],['ws',address,'root2.crt','-','-'],['ws',address,'-','-','true']):
            seen.append(said(ran(client,arguments,directory)))
        if 'curl' in optional:
            for more in ([],['--tls-max','1.2','--http1.1'],['--http2'],['--tlsv1.3','--curves','P-384']):
                seen.append('curl: '+tool(['curl','-sS','--max-time','20','--cacert',str(directory/'root.crt'),'--resolve',f'localhost:{port}:127.0.0.1',*more,f'https://localhost:{port}/curl']).strip())
        if 'openssl' in optional:
            # K asks the server for new keys (KeyUpdate) before the request goes; s_client answers it and so does the server.
            for more,keys in ((['-tls1_3'],b'K\n'),(['-tls1_3'],b'k\n'),(['-tls1_2'],b'')):
                out=staged(['openssl','s_client','-connect',address,'-CAfile',str(directory/'root.crt'),'-servername','localhost',*more],[keys,b'GET /openssl HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n'])
                # s_client writes the verification again for each session ticket, which Go's server sends and this library's does not.
                seen.append('openssl: '+' '.join(dict.fromkeys(re.findall(r'Verify return code: \d+ \(\w+\)|GET /openssl 0|KEYUPDATE',out))))
        process.stdin.close()
        seen.append('stopped: '+process.stdout.read().decode().strip())
        process.wait(timeout=60)
    finally:killed(process)
    return seen


def expected_of(kind,optional):
    auth='RSA' if kind=='rsa' else 'ECDSA'
    body="b'GET /py 0\\n' None"
    seen=[f'TLSv1.3 TLS_AES_128_GCM_SHA256 {body}',f'TLSv1.2 ECDHE-{auth}-AES128-GCM-SHA256 {body}',f'TLSv1.2 ECDHE-{auth}-CHACHA20-POLY1305 {body}',
          f'TLSv1.2 ECDHE-{auth}-AES256-GCM-SHA384 {body}',f'TLSv1.2 ECDHE-{auth}-AES128-SHA {body}',f'TLSv1.2 ECDHE-{auth}-AES256-SHA {body}',
          f'TLSv1.3 TLS_AES_128_GCM_SHA256 {body}',f'TLSv1.3 TLS_AES_128_GCM_SHA256 {body}',
          'ERR [SSL: TLSV1_ALERT_PROTOCOL_VERSION] tlsv1 alert protocol version',None,
          "TLSv1.3 TLS_AES_128_GCM_SHA256 b'POST /post 70000\\n' None",f"TLSv1.2 ECDHE-{auth}-AES128-SHA b'POST /post 70000\\n' None",
          None,None,
          "b'HTTP/1.0 400 Bad Request\\r\\n\\r\\nClient sent an HTTP request to an HTTPS server.\\n'","b''",
          '200 "GET /x 0\\n"','ok({}) | ok(WebSocket.Event.text("echo hello")) | true','error: tls: failed to verify certificate: x509: certificate signed by unknown authority',
          'ok({}) | ok(WebSocket.Event.text("echo hello")) | true']
    return seen


def servers(programs,client,directory,optional):
    """Native and, where it is at hand, pinned: the same lines, and the lines expected."""
    count=0
    kinds=('rsa','p256','p384','p521','ed')
    def one(kind):return [served(program,kind,directory,client,optional) for program in programs]
    with ThreadPoolExecutor(5) as pool:results=list(pool.map(one,kinds))
    for kind,got in zip(kinds,results):
        native=got[0]
        for line,expected in zip(native,expected_of(kind,optional)):
            assert expected is None or line==expected,(kind,line,expected)
        # What no expectation above pins down (the words of Python's and OpenSSL's failures) is at least what was asked for.
        assert native[9].startswith('ERR ') and 'HANDSHAKE_FAILURE' in native[9],(kind,native[9])
        assert native[12].startswith('ERR ') and 'CERTIFICATE_VERIFY_FAILED' in native[12],(kind,native[12])
        assert native[13].startswith('ERR ') and 'CERTIFICATE_VERIFY_FAILED' in native[13],(kind,native[13])
        assert native[-1]=='stopped: true',(kind,native[-1])
        rest=native[20:-1]
        for line in rest:
            if line.startswith('curl: '):assert line=='curl: GET /curl 0',(kind,line)
            else:assert line in ('openssl: Verify return code: 0 (ok) KEYUPDATE GET /openssl 0','openssl: Verify return code: 0 (ok) GET /openssl 0'),(kind,line)
        if len(got)>1:assert got[1]==native,(kind,[pair for pair in zip(native,got[1]) if pair[0]!=pair[1]])
        count+=len(native)
    return count


REJECTS=['defmodule T do\n  def main() do\n    IO.inspect(TCP.connect_tls("127.0.0.1:1", 100, [insecure: true]))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(TCP.connect_tls("127.0.0.1:1"))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(TCP.connect_tls("127.0.0.1:1", "100"))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(HTTP.serve_tls("127.0.0.1:0", fn r -> HTTP.text(200, "") end))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(HTTP.serve_tls("127.0.0.1:0", fn r -> HTTP.text(200, "") end, [certfile: 1]))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(HTTP.serve_tls("127.0.0.1:0", fn r -> 200 end, [certfile: "a", keyfile: "b"]))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(WebSocket.connect("wss://127.0.0.1:1", 100, [insecure: true]))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(TLS._hex("00"))\n  end\nend\n']
# Programs with what the pinned compiler's program gives: status, output, errors.
RUNS=[
 ('defmodule T do\n  def main() do\n    IO.inspect(TCP.connect_tls("127.0.0.1:1", 100))\n    IO.inspect(TCP.connect_tls("127.0.0.1:1", 100, [insecure: "true", server_name: "x"]))\n    IO.inspect(TCP.connect_tls("nowhere", 100))\n    IO.inspect(TCP.connect_tls("127.0.0.1:1", 100, [ca_file: "missing.pem", insecure: "true"]))\n  end\nend\n',
  0,b'error("dial tcp 127.0.0.1:1: connect: connection refused")\nerror("dial tcp 127.0.0.1:1: connect: connection refused")\nerror("address nowhere: missing port in address")\nerror("open missing.pem: no such file or directory")\n',b''),
 ('defmodule T do\n  def main() do\n    IO.inspect(TCP.connect_tls("127.0.0.1:1", 100, [verify: "no"]))\n  end\nend\n',
  2,b'',b'<stdin>:3:16: TCP.connect_tls: unknown option :verify; the options are ca_file:, insecure: and server_name:\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\n    case HTTP.serve_tls("127.0.0.1:0", fn r -> HTTP.text(200, "") end, [certfile: "missing.pem", keyfile: "missing.key"]) do\n      ok(_) -> IO.puts("serving")\n      error(why) -> IO.puts(why)\n    end\n    case HTTP.get("https://127.0.0.1:1/") do\n      ok(_) -> IO.puts("answered")\n      error(why) -> IO.puts(why)\n    end\n    case WebSocket.connect("wss://127.0.0.1:1/", 100) do\n      ok(_) -> IO.puts("connected")\n      error(why) -> IO.puts(why)\n    end\n  end\nend\n',
  0,b'open missing.pem: no such file or directory\nGet "https://127.0.0.1:1/": dial tcp 127.0.0.1:1: connect: connection refused\ndial tcp 127.0.0.1:1: connect: connection refused\n',b''),
 ('defmodule T do\n  def main() do\n    IO.inspect(HTTP.serve_tls("127.0.0.1:0", fn r -> HTTP.text(200, "") end, [cert: "a"]))\n  end\nend\n',
  2,b'',b'<stdin>:3:16: HTTP.serve_tls: unknown option :cert; it takes certfile: and keyfile:\n  at T.main (<stdin>:3)\n'),
 # A program may have a module named TLS: the pinned library has none.
 ('defmodule TLS do\n  def _hex(x: string): string do\n    "mine " <> x\n  end\n  def main() do\n    IO.puts(_hex("a") <> TLS._hex("b"))\n    IO.inspect(TCP.connect_tls("127.0.0.1:1", 100))\n  end\nend\n',
  0,b'mine amine b\nerror("dial tcp 127.0.0.1:1: connect: connection refused")\n',b''),
]


def verify(compiler):
    optional=[name for name in ('curl','openssl') if shutil.which(name)]
    with tempfile.TemporaryDirectory(prefix='alchem-tls-') as base:
        directory=Path(base)/'files';directory.mkdir(0o700);(directory/'certs').mkdir()
        for name,text in DATA.PEMS.items():(directory/name).write_text(text)
        for name,parts in DATA.CHAINS.items():(directory/name).write_text(''.join(DATA.PEMS[part] for part in parts))
        (directory/'certs'/'root.pem').write_text(DATA.PEMS['root.crt'])
        # KNOWN
        source,want,checks=known(directory)
        program=build(compiler,source,Path(base)/'known')
        got=ran(program,[],directory,seconds=120).split('\n')
        assert got[-1]=='' and len(got)-1==len(want),(len(got)-1,len(want),got[-3:])
        paths=set()
        for index,(line,expected) in enumerate(zip(got,want)):
            if expected is not None:
                assert line==expected,(index,line,expected);continue
            check=checks[index]
            if check[0]=='gcm':
                _,i,force,v=check
                words=line.split(' ')
                assert words[:2]==['gcm',str(i)] and words[3:]==[v['ciphertext'],v['tag'],'1true','0'],(line,v)
                # The word after the number is the cipher that ran plus what was forced: 1 for the processor's AES
                # unforced, 0 for software unforced (a processor without AES), 1 for software forced.
                paths.add((force,words[2]))
            elif check[0]=='ecsign':
                _,c,pub,digest=check;words=line.split(' ');size=CURVES[c][5]
                signature=bytes.fromhex(words[2])
                assert words[3]=='true' and len(signature)==2*size and ec_verify(c,pub,digest,int.from_bytes(signature[:size],'big'),int.from_bytes(signature[size:],'big')),line
            else:
                _,n,e,digest=check;words=line.split(' ')
                assert words[3]=='truefalsefalse' and pss_ok(n,e,bytes.fromhex(words[2]),digest,'sha256'),line
        assert (1,'1') in paths,paths
        # CLIENTS, SERVERS
        client=build(compiler,CLIENT,Path(base)/'client');server=build(compiler,SERVER,Path(base)/'server')
        others=[pinned(CLIENT,Path(base)/'client.pinned'),pinned(SERVER,Path(base)/'server.pinned')]
        both=all(other is not None for other in others)
        dialled,skipped=clients([client]+([others[0]] if both else []),directory)
        tunnelled=tunnels([client]+([others[0]] if both else []),directory)
        lines=servers([server]+([others[1]] if both else []),client,directory,optional)
        for source,status,stdout,stderr in RUNS:
            program=build(compiler,source,Path(base)/'run')
            done=subprocess.run([str(ROOT/'scripts/limited'),str(program)],capture_output=True,env=bounds(directory,40),cwd=directory,stdin=subprocess.DEVNULL,timeout=120)
            assert (done.returncode,done.stdout,done.stderr)==(status,stdout,stderr),(source,done.returncode,done.stdout,done.stderr)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    for name in ('curl','openssl'):
        if name not in optional:print(f'SKIP the clients of {name}, which is not installed')
    if skipped:print(f'SKIP {skipped} servers this Python cannot set up')
    if not both:print('SKIP the comparison with programs of the pinned compiler, which is not at build/dev/alchem-upstream: the frozen results stand')
    print(f'PASS tls: {len(want)} known answers ({len(TRUST)} certificate chains, {len(FILES)} pairs of files), {dialled} servers of Python\'s ssl dialled by a native client'
          f'{" and by the pinned one" if both else ""}, {tunnelled} requests through the tunnel of a proxy, {lines} observations of native servers by Python\'s ssl{"".join(", "+name for name in optional)} and a native client'
          f'{", the same of pinned servers" if both else ""}, {len(RUNS)} programs, {len(REJECTS)} rejected')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
