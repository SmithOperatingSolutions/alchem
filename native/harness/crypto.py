#!/usr/bin/env python3
"""Crypto: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error, environment, standard input) as the pinned compiler runs it
RUNS=[('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, "abc"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, "abc"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, "abc"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, "abc"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, "abc"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, "abc"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, ""), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'900150983cd24fb0d6963f7d28e17f72\na9993e364706816aba3e25717850c26c9cd0d89d\n23097d223405d8228642a477bda255b32aadbce4bda0b3f7e36c9da7\nba7816bf8'
  b'f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\ncb00753f45a35e8bb5a03d699ac65007272c32ab0eded1631a8b605a43ff5bed8086072ba1e7cc2358baeca1'
  b'34c825a7\nddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f\nd4'
  b'1d8cd98f00b204e9800998ecf8427e\nda39a3ee5e6b4b0d3255bfef95601890afd80709\nd14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f\ne3b0c44298f'
  b'c1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da274edebfe76f65fbd51ad2f148'
  b'98b95b\ncf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("a", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("a", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("a", 63)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("a", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("a", 65)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("a", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("a", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("a", 63)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("a", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("a", 65)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("a", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("a", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("a", 63)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("a", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("a", 65)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("a", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("a", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("a", 63)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("a", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("a", 65)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("a", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("a", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("a", 63)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("a", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("a", 65)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("a", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("a", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("a", 63)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("a", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("a", 65)), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'ef1772b6dff9a122358552954ad0df65\n3b0c8ac703f828b04c6c197006d17218\nb06521f39153d618550606be297466d5\n014842d480b571495a4a0363793f7367\nc743a45e'
  b'0d2e6a95cb859adae0248435\nc1c8bbdc22796e28c0e15163d20899b65621d65a\nc2db330f6083854c99d4b5bfb6e8f29f201be699\n03f09f5b158a7a8cdad920bddc29b81c1'
  b'8a551f5\n0098ba824b5c16427bd7a1122a5a442a25ec644d\n11655326c708d70319be2610e8a57d9a5b959d3b\nfb0bd626a70c28541dfa781bb5cc4d7d7f56622a58f01a0b1d'
  b'dd646f\nd40854fc9caf172067136f2e29e1380b14626bf6f0dd06779f820dcd\n1d4e051f4d6fed2a63fd2421e65834cec00d64456553de3496ae8b1d\na88cd5cde6d6fe9136a'
  b'4e58b49167461ea95d388ca2bdb7afdc3cbf4\nff8716f600af42959d0efb52e1f21b01bb328733009344d511c299fb\n9f4390f8d30c2dd92ec9f095b65e2b9ae9b0a925a5258'
  b'e241c9f1e910f734318\nb35439a4ac6f0948b6d6f9e3c6af0f5f590ce20f1bde7090ef7970686ec6738a\n7d3e74a05d7db15bce4ad9ec0658ea98e3f06eeecf16b4c6fff2da4'
  b'57ddc2f34\nffe054fe7ae0cb6dc65c3af9b61d5209f439851db43d0ba5997337df154668eb\n635361c48bb9eab14198e76ea8ab7f1a41685d6ad62aa9146d301d4f17eb0ae0\n'
  b'5d91ac7e74e62b5c728904b40f10784d66b7af9cb6302123e48c92f0432ceb8d2a92c02de77dcb29ed75c4b42bde46f4\n8a8d9649ea04e993a6ca7135af7e3392cc5fca84f8531ca'
  b'c7aa3feed4eb98f55dcbe0f3284b61c6f35f98b02cc644b4c\n7e7f097e95b52bb8f53383450ecaf9868187c130981730c03b6d573adfc0b991e365244e5b4bfa082bfb43c517d371'
  b'20\n2e404b9339da795776e510d96930b3be2904c500395b8cb7413334b82d4dec413b4b8113045a05bbbcff846f027423f6\na2b797de45aa1d20594e2ea0cb1801d6dd7ffa3a'
  b'58281c37dde04029f1c98157bb6eb005e90dd76b79a1d6ddd52dd58d\nb0220c772cbf6c1822e2cb38a437d0e1d58772417a4bbb21c961364f8b6143e05aa6316dca8d1d7b19e1644'
  b'8419076395f6086cb55101fbd6d5497b148e1745f\n962b64aae357d2a4fee3ded8b539bdc9d325081822b0bfc55583133aab44f18bafe11d72a7ae16c79ce2ba620ae2242d514480'
  b'9161945f1367f41b3972e26e04\nc1b0f5c6d3b03dfe4a2602e67242f54e344090b66e01100a469b129f583f016c7e27dddeaa438393dcc7ec54b0b57c9ba7af007f9b56db5f6fb67'
  b'7d972a31362\n01d35c10c6c38c2dcf48f7eebb3235fb5ad74a65ec4cd016e2354c637a8fb49b695ef3c1d6f7ae4cd74d78cc9c9bcac9d4f23a73019998a7f73038a5c9b2dbde'
  b'\nb83086cd8494e55708ad7ecd82dfb4bca1bda61ecbb7caf0c68967902e709345e5d8305eb7ac0d588afc6cbb75161aa9c8c7e0ea986bd833dafe5e1ccd37345a\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("\\xff\\x00z", 37) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("\\xff\\x00z", 39) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("\\xff\\x00z", 40) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("\\xff\\x00z", 42) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("\\xff\\x00z", 43) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("\\xff\\x00z", 1000) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("\\xff\\x00z", 37) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("\\xff\\x00z", 39) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("\\xff\\x00z", 40) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("\\xff\\x00z", 42) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("\\xff\\x00z", 43) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("\\xff\\x00z", 1000) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("\\xff\\x00z", 37) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("\\xff\\x00z", 39) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("\\xff\\x00z", 40) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("\\xff\\x00z", 42) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("\\xff\\x00z", 43) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("\\xff\\x00z", 1000) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("\\xff\\x00z", 37) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("\\xff\\x00z", 39) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("\\xff\\x00z", 40) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("\\xff\\x00z", 42) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("\\xff\\x00z", 43) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("\\xff\\x00z", 1000) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("\\xff\\x00z", 37) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("\\xff\\x00z", 39) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("\\xff\\x00z", 40) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("\\xff\\x00z", 42) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("\\xff\\x00z", 43) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("\\xff\\x00z", 1000) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("\\xff\\x00z", 37) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("\\xff\\x00z", 39) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("\\xff\\x00z", 40) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("\\xff\\x00z", 42) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("\\xff\\x00z", 43) <> "q"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("\\xff\\x00z", 1000) <> "q"), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'8e2813a88617156143b5b3c7d6b4774d\n7279bfa007bd4c60d2283bc5641ee1e0\nac83a10719dd47b9b080bc6afc83879d\n22b55b72739cf386975ca4ee30f84553\na4808562'
  b'f921e5c276d58fe0b03260d8\n01806981f4afe815a70120dacdc17370\nd0eb0541a7d00be454777fa4fefe54164291c92b\n16d1dc352ff31692881884be968410c655308091\n'
  b'622b35ade610bb90b4da4663e03f77dc063f6779\n971620ecf987043b8ec9c91e4cf95b35acdd9b9c\n8a417f565134a2e766e6398d9a169a7679d474c0\nc0f517768e7035ffb'
  b'ececba343c95938ab2878a6\nef8895602d9d282ff53b6c5743d7c22d7bb1684e8262ddc5a229577b\n871bf468d43940f7474a9c3f5acb95ff3bc4a4d39a8d126878579ca7\n41'
  b'6d4da62f00ed48aee23beb8a12eeadd11b5e45f3bff1d0e6d08f01\nc48d49f9eb0759c8685255a7510b615fd3ddd9a3b6935a2ae326a5f9\na1e276963a7867f628002690ce5e'
  b'afa0eec0c3534d66df23c8af44c7\n18878585db1472c13331c6e328f102c03628bd72d8f4bf84c269a7a0\n1abfadd800bc5c911c2366e1c2a1a08611917edf4c6d9c761aa036'
  b'813be2a324\na3a67c4da361d59a16a696019c5015bf26bcc38901cedfed9d0f7b0b8c775842\n75ec3802fda27190c24d798d5aa3d442418b6321f3d4dff6a9b364d61acf5a8e'
  b'\n0f1aaae8e6f9e89d6d7eede0bcf636b98556e2d3fdf10d6cf6e59b65e28656b5\n9a386372806185222e730909f13bb3d77e2c132ea0e45a54d837a8dd02761596\nf9c42cfdb'
  b'cbdb5f044ddaee43058ab21943273384062d2b5c657c9b5db78baf2\n5be9be8a8b24090919fe25316c214a19aa638d1ce2451fe2a6f07fda6ce574fee5907ec10360a562678b742a'
  b'9ba4ceec\n9c982c2665779682596783e6e56e9e48125d75575d7560c2af324c69100b136ffaa948f99ebd755f076fab7bdc5c311c\n8dd14ba1f2636514d23a0bbf4d268b451a'
  b'9787580feef10dadc1bef191aa713deb86088b7f16e3da4f8fd62e964e1dce\n4e01b6b65b6e46ec5fbcf84b99b5b60c18888446a7045750d6554679870b9155e8a80ec0fdd397331'
  b'a14d07529a50e23\n2bff610542d4c908a623d4705033373c9fa671fb4eb70221db5f80e2cf0e457bcf42445945e60d0f74754f93070642c1\n992975e0df8c8475cb25e5e8840'
  b'087acd2f131b241dd42983c59ab52f82501d635b61ab409320843b8953eb76debeaf3\nb29ff5dee8b074fedafb9159a5aab3e19e81543ec4346156ae15fd092e79e353b829204977'
  b'e7fe1eb4418b92f5685d6d7fb482eb45dc0e322d48b745bfba5718\n5260cd2503feb245295d5ac357689d9df756cdff6156c08f7337dc36c3a3ba098f140abf98880eb13c5e6fc95'
  b'4b4cc83bb9c84323e3970ac88c671cd736bc528\n8b8c7c6ba39dd5a7648cb498f9560dd248c8023d86afe9dd7b0c12622394ae961113ad39706174925114010e1c5a068926087c42'
  b'3c25fcdb54def93f1a65fb09\n6464cfeec6523c1995bcc976f068e2ad6780cc8cc28ed137c9ba504c94ae8085b8f2d07fa65044d4f374b30624b0c92e1da283ef831a8fcaa0b0ede'
  b'143e2c87c\n984c84dedbbf7a786dae7128be72d3b648110804b9d28beaee80bdd65adcab7e1e2d3970199eaa9c909a682222e93001a4d977d020a9777985676a67b3fe9ac0\n7'
  b'206f229a0c7512dfb521cf9b1e4838d5571424131d11bb97208a83db46229bc401d5ea71bb12814a51befa7b9283511257e209e4236461065970fcf4fb8f0e1\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.hash(:md5, String.duplicate("a", 500000)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha1, String.duplicate("a", 500000)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha224, String.duplicate("a", 500000)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha256, String.duplicate("a", 500000)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha384, String.duplicate("a", 500000)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hash(:sha512, String.duplicate("a", 500000)), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'87b1c2bb5bcb76dfdd141c5cbf3bec48\nc3acc310183f238acea1cf5c243c74c11e53ca24\n1d3823f8b804b29c391ef12049a16835e5126dedd4882261ab74c32b\n0071c4a7e'
  b'7200b572501284e9a46954580950d9a73d401869236e87ed2ce99f8\n02b4e0d88fd2fed5b423ef7dc787638567c3558281b98f7cd02b5e58da1b548f33f95b6f9e2398acf82a52b2'
  b'f36a691b\n9c6779b01b3456081dda1d5ec4ed7210e89e5cd702d3cfe12b9d866772eb3305d78a4f4bb8a29dcd67031774d6e36177cf64c1738698853767447c5d04bd97bd\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, "Jefe", "what do ya want for nothing?"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, "Jefe", "what do ya want for nothing?"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, "Jefe", "what do ya want for nothing?"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, "Jefe", "what do ya want for nothing?"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, "Jefe", "what do ya want for nothing?"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, "Jefe", "what do ya want for nothing?"), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, "", ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, "", ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, "", ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, "", ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, "", ""), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, "", ""), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'750c783e6ab0b503eaa86e310a5db738\neffcdf6ae5eb2fa2d27416d5f184df9c259a7c79\na30e01098bc6dbbf45690f3a7e9e6d0f8bbea2a39e6148008fd05e44\n5bdcc146b'
  b'f60754e6a042426089575c75a003f089d2739839dec58b964ec3843\naf45d2e376484031617f78d2b58a6b1b9c7ef464f5a01b47e42ec3736322445e8e2240ca5e69e2c78b3239ec'
  b'fab21649\n164b7a7bfcf819e2e395fbe73b56e0a387bd64222e831fd610270cd7ea2505549758bf75c05a994a6d034f65f8f0e6fdcaeab1a34d4a6b4b636e070a38bce737\n74'
  b'e6f7298a9c2d168935f58c001bad88\nfbdb1d1b18aa6c08324b7d64b71fb76370690e1d\n5ce14f72894662213e2748d2a6ba234b74263910cedde2f5a9271524\nb613679a081'
  b'4d9ec772f95d778c35fc5ff1697c493715653c6c712144292c5ad\n6c1f2ee938fad2e24bd91298474382ca218c75db3d83e114b3d4367776d14d3551289e75e8209cd4b792302840'
  b'234adc\nb936cee86c9f87aa5d3c6f2e84cb5a4239a5fe50480a6ec66b70ab5b1f4ac6730c6c515421b327ec1d69402e53dfb49ad7381eb067b338fd7b0cb22247225d47\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, String.duplicate("k", 63), String.duplicate("d", 1)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, String.duplicate("k", 64), String.duplicate("d", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, String.duplicate("k", 65), String.duplicate("d", 200)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, String.duplicate("k", 127), String.duplicate("d", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, String.duplicate("k", 128), String.duplicate("d", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, String.duplicate("k", 129), String.duplicate("d", 0)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:md5, String.duplicate("k", 500), String.duplicate("d", 129)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, String.duplicate("k", 63), String.duplicate("d", 1)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, String.duplicate("k", 64), String.duplicate("d", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, String.duplicate("k", 65), String.duplicate("d", 200)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, String.duplicate("k", 127), String.duplicate("d", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, String.duplicate("k", 128), String.duplicate("d", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, String.duplicate("k", 129), String.duplicate("d", 0)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha1, String.duplicate("k", 500), String.duplicate("d", 129)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, String.duplicate("k", 63), String.duplicate("d", 1)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, String.duplicate("k", 64), String.duplicate("d", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, String.duplicate("k", 65), String.duplicate("d", 200)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, String.duplicate("k", 127), String.duplicate("d", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, String.duplicate("k", 128), String.duplicate("d", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, String.duplicate("k", 129), String.duplicate("d", 0)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha224, String.duplicate("k", 500), String.duplicate("d", 129)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, String.duplicate("k", 63), String.duplicate("d", 1)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, String.duplicate("k", 64), String.duplicate("d", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, String.duplicate("k", 65), String.duplicate("d", 200)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, String.duplicate("k", 127), String.duplicate("d", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, String.duplicate("k", 128), String.duplicate("d", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, String.duplicate("k", 129), String.duplicate("d", 0)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha256, String.duplicate("k", 500), String.duplicate("d", 129)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, String.duplicate("k", 63), String.duplicate("d", 1)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, String.duplicate("k", 64), String.duplicate("d", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, String.duplicate("k", 65), String.duplicate("d", 200)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, String.duplicate("k", 127), String.duplicate("d", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, String.duplicate("k", 128), String.duplicate("d", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, String.duplicate("k", 129), String.duplicate("d", 0)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha384, String.duplicate("k", 500), String.duplicate("d", 129)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, String.duplicate("k", 63), String.duplicate("d", 1)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, String.duplicate("k", 64), String.duplicate("d", 64)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, String.duplicate("k", 65), String.duplicate("d", 200)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, String.duplicate("k", 127), String.duplicate("d", 55)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, String.duplicate("k", 128), String.duplicate("d", 56)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, String.duplicate("k", 129), String.duplicate("d", 0)), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.hmac(:sha512, String.duplicate("k", 500), String.duplicate("d", 129)), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'1f00db62d611e1c27e373be4f518108e\n0b5f5f7181b922733e53e4c652047106\ncf5f8b93a82236b0816f814d2bb1d0a4\ndcccee3557ff8199718f03739d899f38\nfc1142e6'
  b'dc64d4a30418618a70db794a\n578deb97aa6ada264eb25d61c8748bd8\n52304841a130fbdf8a3615dd517660b9\n928ddba49ecabcb4b30b819cd0c5dce03d866041\n37fdfded'
  b'c886a39f895be540696fb91cc7f5c2d2\n8e7fb4911af92ced5caa86019ef9e4455765eaf1\n5b8104811bb5143ceae6b120e3a148967a7da1c2\nb48860b1713801aaaf66389ad'
  b'e33d34ade570475\nf1df19a20bdc59d033e3c5017eba211d656acce2\n1ff546319f7a04e0c75bb411e04f201cc5036dc8\n839ac0bd20e89edcf268e86a233d474937ed0f36c4'
  b'79cc2266d29e7a\n5885b42078dbaa83292f57944615cea4d26222c2eebd300162e5737b\n56d73f7cbbd44680e4a8909eb2043a3ea3c7a40f38dc94f75a64a6cb\n06b489f3b9b'
  b'53265259b04e2ec4805b1b45950b860a4bce2a28e4d93\n1d6ef9f7f16451d573c53743eb1bb3ad028b8345bc5074acb1bd7b4a\n1c04afd65a69fa57bc47a30a120efac07a100'
  b'8a166d968fee348389a\n0675e75c37dac496d3880ddeaa7a7b45114aa7b899a7d4f093f190e3\n63ee06c76cc34ecfa9e76567751378bcb07030be5f14f20b0b30c7b5379afff'
  b'f\n13bbaa94f99c1de7ad81bed07343f358530799c735d463fe5ec801fb0e5c48eb\n78ee3307679a3b65f13532a373fd976ae8e03d4cfce0b6d6c2f6132db6163c0b\n06ad21b9'
  b'858e3f18cff3db64c43048ee342f223932b17eb1ab4e8aef02236ac2\n9318833bd1a0a1f46e3df9eb8233e12397e2250851f84f4efb50fdacfb83ce71\n6fccbbdf42a3aa30d4'
  b'8ac78c3370dd2e703a1f839b0342efe35a9428f01f2fc6\n615d777cc5dcfbcb92c9bc0bad2c79da22811e459603155249624aa4013b12f6\nce1bd32598718568f242d7694beb'
  b'80eb56307a072efcb7e9b703af820eb21bca1b8a2639ebdceb524be2fa1bd5cd0afb\n3bfd0568b94f8a6c746027ef32f88247177deecadb6b7cf7635c966e2b4d843c7f0a9d7818d'
  b'ed2c144d22681f3dd99f9\na0e2572cb9c9491e362bdb67318d122b81fe8153252940837fe4d866d642deb7471dd626f438fdac01a86ca328c1d16f\n0c133c0ceb8f16ac40b57'
  b'33a924aab901c533ad14955a4c13bbcc0375fad4ed5a13e7b39264e7b7fa4bae3a37d281759\nb53798e9890cf5f3bc929a108c40cf31f7584f3683789d7beb8c5e8eba3e6393e258'
  b'899e12d3428a41c6b16296868038\n0b06fcbb1b03bed88326ca27f2a71a1c72d2d316898ad69604a1e2f0e5d9a25f63e6b8a30704cfb6946704974c72137e\na35aa4115de789'
  b'3350e1de68f5472085da5a6664f30e21e07d78d8b361dbb1288825b44187bf75b226d9ed74de6e85fd\n68760a201b38df4e250ed71b59f7a75ff9e3fb64766b98ca9503a5dd87dd0'
  b'e204090dc9bb003899c749628bfb9a81a566d2719d2ee092bb7df9191a423f18722\n6332dcda6695a833f243f533456423bcae0884c993c1fd0351f555496652b7b05420fa189be1'
  b'e698ab5d24fd92a192ffb76a1c765999e0b9ec1ef9ae39776a9b\n44b229bd82ff1528e8f73025d7dbc67d8041feedcc064378ab4594f9bd42e1ae5caa7b84285b9769ab68874a4ff'
  b'7987d21be11d831e3aa3240b43d97cf126834\nc708890a671b345fca8343bde1885e2fbdf8d7e63d9ae595c8020947445a7f612af77e12cd9e6d87284630a73b98506a588de5182f'
  b'8f4b503c024af238b15fb0\n6e6b7f75e03510eb274e825344f5aa89f18520068be13c6aa6031ea70b3307dd991f12678d827f2433bffa6146eeec345efe3af130fcc1c7c7dbb59d7'
  b'712b096\nfddb8a2194cbfb75ae9c862b615b44a2dcd28ffed5a6ed3f49723358398331c8e295c9ab9661cd448d8aee44b80689d0a2f4f2bc7d0014d418283f5326a7c02d\nf73'
  b'0f8217988d12287daba88039ab33e13ad9a9fa432a4f077032e90dceb6dde28ff311c1fcd2b2d9a64c99046b438a26381ae1519845b4d21faadb0b8161df1\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.pbkdf2(:sha256, "password", "salt", 4096, 32), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.pbkdf2(:sha1, "password", "salt", 2, 20), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.pbkdf2(:sha512, "password", "salt", 3, 1024), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.pbkdf2(:md5, "", "", 1, 1), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.pbkdf2(:sha224, String.duplicate("p", 200), String.duplicate("s", 300), 7, 29), [case: :lower]))\n'
  '    IO.puts(Base.encode16(Crypto.pbkdf2(:sha384, "passwordPASSWORDpassword", "saltSALTsaltSALTsaltSALTsaltSALTsalt", 4096, 49), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a\nea6c014dc72d6f8ccd1ed92ace1d41f0d8de8957\nb6b07cb2cebf4ad84468391a543824fccf'
  b'fe0e0769dbe6bddf10a65673c4b648e612d44918f9ce9a19a1294cf5140628084ba994c3b21a4ef4741220b811c633cfc0641fccbcc4164f1bbfcb1f33f595ae9aa4a33ddcce5701'
  b'57775980362c0ee28aa340c842a3ae84710167aea2f9ba34833cbf66a8922e5f165d886868fd3fd426f9ba2a82a5e97ef8eda7d02d982ff13f1a96f0ea9e8ccc90947753b18de30d'
  b'2a4f8f8cdf1fd8fc5a59062256a0a20d78a0954c8d6378dc6d06037d4c447b961d4f3174c5eae81e26fe8f1ca14d9b2576054c09800bec0557d5904cbebde0fd3e870d571e01b72e'
  b'f8ace3e4a22959c32d6d55c58b130f12c2c17bc92cdb6de57c1ed48a55a5bc138cd9dd9e51f14e105687f4b8b0259542b10b9afccc292321b71f19b222d9b327cfb9e684f9d49a31'
  b'176ac96dd606400cfb2adfc75f7656dfb565d20be5a954e20cb7850ec7e49a1ce1ef6d47cb7a7ead8869d7092f595cb9a10f70e7a936eba7034ff4775ab2bfaf83db5880b0f8e318'
  b'4dadbb92a182823dc0ecb78f0d9fa4c4c41485ba712b5bb13c04df2b97f5329b5d319b0fb14633e33175e636c104c89e2d1b23ccd8702ca7fa50337a01efdf4703ad7f7cf358bf20'
  b'795a4b27bb9b1b82dcceb772f84cd5847af43eec320210e586c313eb6f4d7d963ec7cd865639a66c716ddd5a343c30ed47c45b718ff4ed76f4ff7cdaa7f7b401c03465f2b824b1af'
  b'47b750838a65bbeb6d73b833b9882fa1ca8eb0d172a3029eb85b8e3f598f3f6767d25c61dc9e595e3f4abaabb9e690cad82da8759a7d5d43ad0bdd146ed19189183e1e6a7d5e8d32'
  b'db94ab8e26b2dc496ddb1ae06be0bb2beed41f036a654827ea6806b41bd9edc350da36720463e207d61c5755dc30d1365b93e15033edf3d48e6745cb71d91b9fb66bea2712aef2be'
  b'c7cbda30fc5e0aa19cdaf5962b9d251234a379ce54991fc184dc627498cc9c597058e53474dd3f0e1b3b08c84e4083e4774a6ac56b8baa247fc1e9b04eff88c1a71fb33400ccb894'
  b'd885519a9353cede5a0277f1cc3d62086780ac3e8875ad0acb4552df2b331d310275679a3b36c08e6f59ea3187f6fc78af8c044b9077fc49eeb2ef75627eb98e9f2ee344be63fc0f'
  b'f95d0ee5c98dcd8465f9c97524af63fdb69daf2e784de80231c5369a1fc26a78b1589c9e39343d86ec0023c36b326efb7bede6e22531d60f80d3f1dfed10eaad47fd9765e342a72d'
  b'79e0a5051d1ee350c731e2b7ca89bbf51b441dcc0ee5afaa612c583fef64c2d9db1f76176a55504cd2281bf61e24d692aaf922e3b119947b98497a6747908ac6fbfb062a2927fdbc'
  b'17bd40035f2a8fe16eb6b7eb9c7baa6a1ff4286cdbdae36c8aeee1946e71ceacd9a8ee376e04a2c569ad3bca7ec11c98cc175022761ef8eb9f685f396371e4101162a14cd65d81\n9'
  b'c\n56bc9808931d945e3d20bfcc7c7eb48539fb8448c1717812b0dab20be5\n819143ad66df9a552559b9e131c52ae6c5c1b0eed18f4d283b8c5c9eaeb92b392c147cc2d2869d5'
  b'8ffe2f7da13d15f8d92\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(Base.encode16(Crypto.pbkdf2(:sha256, "password", "salt", 600000, 32), [case: :lower]))\n'
  '  end\n'
  'end\n',
  0,
  b'669cfe52482116fda1aa2cbe409b2f56c8e4563752b7a28f6eaab614ee005178\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(byte_size(Crypto.strong_rand_bytes(16))))\n'
  '    IO.puts(inspect(byte_size(Crypto.strong_rand_bytes(0))))\n'
  '    IO.puts(inspect(byte_size(Crypto.strong_rand_bytes(1048576))))\n'
  '    IO.puts(inspect(Crypto.strong_rand_bytes(16) == Crypto.strong_rand_bytes(16)))\n'
  '    IO.puts(inspect(Crypto.strong_rand_bytes(1) == ""))\n'
  '  end\n'
  'end\n',
  0,
  b'16\n0\n1048576\nfalse\nfalse\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Crypto.secure_compare("token", "token")))\n'
  '    IO.puts(inspect(Crypto.secure_compare("token", "tokem")))\n'
  '    IO.puts(inspect(Crypto.secure_compare("", "")))\n'
  '    IO.puts(inspect(Crypto.secure_compare("a", "ab")))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\ntrue\nfalse\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    stored = Crypto.hash_password("correct horse", [iterations: 1000])\n'
  '    IO.puts(inspect(String.starts_with?(stored, "$pbkdf2-sha256$i=1000$")))\n'
  '    IO.puts(inspect(byte_size(stored)))\n'
  '    IO.puts(inspect({Crypto.verify_password("correct horse", stored), Crypto.verify_password("wrong", stored), Crypto.verify_password("", '
  'stored)}))\n'
  '    IO.puts(inspect(stored == Crypto.hash_password("correct horse", [iterations: 1000])))\n'
  '    IO.puts(inspect(Crypto.verify_password("correct horse", "not a stored password")))\n'
  '    IO.puts(inspect(String.split(stored, "$") |> Enum.map(fn p -> byte_size(p) end)))\n'
  '    IO.puts(inspect(Regex.match?(~r/^\\$pbkdf2-sha256\\$i=1000\\$[A-Za-z0-9+\\/]{22}\\$[A-Za-z0-9+\\/]{43}$/, stored)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n88\n{true, false, false}\nfalse\nfalse\n[0, 13, 6, 22, 43]\ntrue\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    s = Crypto.hash_password("pw")\n'
  '    IO.puts(inspect({String.starts_with?(s, "$pbkdf2-sha256$i=600000$"), byte_size(s), Crypto.verify_password("pw", s), '
  'Crypto.verify_password("pW", s)}))\n'
  '    IO.puts(inspect(byte_size(Crypto.hash_password("a", [iterations: 0, iterations: 5]))))\n'
  '    IO.puts(inspect(byte_size(Crypto.hash_password("a", []))))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, 90, true, false}\n85\n90\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=1$$ag")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", '
  '"$pbkdf2-sha256$i=2$eA$oEple8J0F5boBSOqXBoaHmitlmanMnJ3PcLRZADuIjqarNfGdKHVaI7WzSlX/TaKw2ASZ9u+UNmSR0StqoRXYLF7Cf8CVwCu6pUrp7ntJJSk2Sp5aVniAhDj6Dy8OKVSum8c5NUActBM0ALceFItOlG3GYmW9qC1jsWGJxqPQ84Kg/QirMybIzovblYtWunLlF2I2RqBZFxklx3w4C86pHZ1KxaXOoUzxdLRxCrs2tQD18TCnD7KDp/a+NkCH6hTJ0nbiFw9gU7XxJ8VjtuiCnDqCToonTb9/WJ5CiKNIfa7HNqafeZ8c/8WIBY9STdn7bFxPEmPbTiKwBzTpbskuJT9bvfkyFu7yuCASjBGXgTMH0YcEeZmvLm/gA7FCjWvX4K9gHIzFp73YHTNxFMurJsY+64DrT8E8JAYowXJN1K1kBSz3r9zEVykB1P9YaYsH9sklVzATqkNnNRRZE1EknaC+ujO//CFfvk3QvXa9OPwn0GOMcrmTihjNJqat9TrOv63+VVI6E3KioFClW6qw8OyreYS8dhcWrtrkzbW/+4S42divJVMn6D7Ffjx0E25DSYuqSG28gNOmT2t5DJI6b4D6EizilxwNT48m1LCpr6L+xtclAvV14dfFCPegoVEIF8Ndv0nzMz+YyfV9gPFwYDTypu9aji5RYKATKoxgjQSiO9yHLdinjdmiPz4HJUifZd6AeELsa1qgYbjjnrStPrZMSqJoywDwHTxpq96fZS0up0qnX4rVsdwXmGTuWF5B73kuFa9x0pcAfKgob4PU6hXKOA7h23CrX5hKApVGxRgAo6MbSZzC9az0Gwalsw4ocCTPQZEmkpUmEEG1/FhNXlcWhJQFQOV9+Q2pM/Tat7iHsDA3hOCNcYhYOOZnQPV87RhvErH96mYiafYT45fhUrHy99ZBKqgCR8JvSxwKK5L8JNLn5wVvsi6MyqkJkVjNMZQOgeR+24URQ4GirGrH3JPdPF3wa4VpJHzo+iN7UAcAvcQ/6o7oegDihAM/2biOf181qUtCB/irj5J7FLFJOlOBiVwGB+rc1MaKPy7zwFpkUlHEG79KZINE4Mnw93+Lv0qWZ+nvVdMvJKKGPU6qVjuIV40ABkcyzhxjhV7Kr+044a8OI/ugcGJdzRoBCi6u2rZCWZ3THhq/IioWsYQhjE22Y+xZ2UQhJdEsadTJxChSiWSEwb9ednCuph7Lckyv0u49tZsDJL7Ga4Wqg7oOsz2UCZrOZOftNmxTTxwOb/dK+y8t+IIgXZhvSxfuxg7dJoUoKjd3A8bMqaYt7yOpBotO0uSml+lK7GQjsnUlvYZ2XX0q3VYb+13qta2af9lWXx/3Z0QiI8Gdqt4G3zxUw")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", '
  '"$pbkdf2-sha256$i=2$eA$oEple8J0F5boBSOqXBoaHmitlmanMnJ3PcLRZADuIjqarNfGdKHVaI7WzSlX/TaKw2ASZ9u+UNmSR0StqoRXYLF7Cf8CVwCu6pUrp7ntJJSk2Sp5aVniAhDj6Dy8OKVSum8c5NUActBM0ALceFItOlG3GYmW9qC1jsWGJxqPQ84Kg/QirMybIzovblYtWunLlF2I2RqBZFxklx3w4C86pHZ1KxaXOoUzxdLRxCrs2tQD18TCnD7KDp/a+NkCH6hTJ0nbiFw9gU7XxJ8VjtuiCnDqCToonTb9/WJ5CiKNIfa7HNqafeZ8c/8WIBY9STdn7bFxPEmPbTiKwBzTpbskuJT9bvfkyFu7yuCASjBGXgTMH0YcEeZmvLm/gA7FCjWvX4K9gHIzFp73YHTNxFMurJsY+64DrT8E8JAYowXJN1K1kBSz3r9zEVykB1P9YaYsH9sklVzATqkNnNRRZE1EknaC+ujO//CFfvk3QvXa9OPwn0GOMcrmTihjNJqat9TrOv63+VVI6E3KioFClW6qw8OyreYS8dhcWrtrkzbW/+4S42divJVMn6D7Ffjx0E25DSYuqSG28gNOmT2t5DJI6b4D6EizilxwNT48m1LCpr6L+xtclAvV14dfFCPegoVEIF8Ndv0nzMz+YyfV9gPFwYDTypu9aji5RYKATKoxgjQSiO9yHLdinjdmiPz4HJUifZd6AeELsa1qgYbjjnrStPrZMSqJoywDwHTxpq96fZS0up0qnX4rVsdwXmGTuWF5B73kuFa9x0pcAfKgob4PU6hXKOA7h23CrX5hKApVGxRgAo6MbSZzC9az0Gwalsw4ocCTPQZEmkpUmEEG1/FhNXlcWhJQFQOV9+Q2pM/Tat7iHsDA3hOCNcYhYOOZnQPV87RhvErH96mYiafYT45fhUrHy99ZBKqgCR8JvSxwKK5L8JNLn5wVvsi6MyqkJkVjNMZQOgeR+24URQ4GirGrH3JPdPF3wa4VpJHzo+iN7UAcAvcQ/6o7oegDihAM/2biOf181qUtCB/irj5J7FLFJOlOBiVwGB+rc1MaKPy7zwFpkUlHEG79KZINE4Mnw93+Lv0qWZ+nvVdMvJKKGPU6qVjuIV40ABkcyzhxjhV7Kr+044a8OI/ugcGJdzRoBCi6u2rZCWZ3THhq/IioWsYQhjE22Y+xZ2UQhJdEsadTJxChSiWSEwb9ednCuph7Lckyv0u49tZsDJL7Ga4Wqg7oOsz2UCZrOZOftNmxTTxwOb/dK+y8t+IIgXZhvSxfuxg7dJoUoKjd3A8bMqaYt7yOpBotO0uSml+lK7GQjsnUlvYZ2XX0q3VYb+13qta2af9lWXx/3Z0QiI8Gdqt4G3zxUx0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=2$eHk$aZftuOqvfwEnDMNtVqiEWyLFJUfOEhRITq50FaXeKz/o")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=2$eHl6$Ur/RgasqPbzJvJHze8hwJ/CUEKbkG3jd1fr+M4daDg")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0$")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "x$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha512$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=+3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=03$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=0$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=-3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3 $c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=100000001$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3_0$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$I=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ=$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0=")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2Fsd\\nHNhbHQ$Gw9J7ot\\r\\n0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0\\n")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl1")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQ")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0A")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ$")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHQ $Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$-2FsdHNhbHQ$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbH$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$c2FsdHNhbHR$Gw9J7ot0OEClxhiPitRxDqdFt+B56mDlJBu2/LKXQl0")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$$$$")))\n'
  '    IO.puts(inspect(Crypto.verify_password("pw", "$pbkdf2-sha256$i=3$$")))\n'
  '  end\n'
  'end\n',
  0,
  b'true\ntrue\ntrue\nfalse\ntrue\ntrue\nfalse\nfalse\nfalse\nfalse\ntrue\ntrue\nfalse\nfalse\nfalse\nfalse\nfalse\nfalse\nfalse\nfalse\nfalse\nfalse'
  b'\ntrue\ntrue\ntrue\nfalse\nfalse\nfalse\nfalse\nfalse\nfalse\ntrue\nfalse\nfalse\nfalse\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.hash(:sha3, "abc")))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.hash: the algorithms are :md5, :sha1, :sha224, :sha256, :sha384 and :sha512, not :sha3\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.hmac(:whirlpool, "abc", "")))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.hmac: the algorithms are :md5, :sha1, :sha224, :sha256, :sha384 and :sha512, not :whirlpool\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.pbkdf2(:sha1, "abc", "", 0, 1)))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.pbkdf2 takes from 1 to 100000000 iterations\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.pbkdf2(:sha1, "abc", "", 100000001, 1)))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.pbkdf2 takes from 1 to 100000000 iterations\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.pbkdf2(:sha1, "abc", "", 1, 1025)))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.pbkdf2 gives a key of 1 to 1024 bytes\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.pbkdf2(:sha1, "abc", "", 1, 0)))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.pbkdf2 gives a key of 1 to 1024 bytes\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.pbkdf2(:x, "abc", "", 0, 0)))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.pbkdf2: the algorithms are :md5, :sha1, :sha224, :sha256, :sha384 and :sha512, not :x\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.strong_rand_bytes(-1)))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.strong_rand_bytes takes a count from 0 to 1048576\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.strong_rand_bytes(1048577)))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.strong_rand_bytes takes a count from 0 to 1048576\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    IO.puts(inspect(Crypto.hash_password("a", [iterations: 2, rounds: 0])))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.hash_password takes iterations:, not rounds:\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.hash_password("a", [iterations: 0])))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.hash_password takes from 1 to 100000000 iterations\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n  def main() do\n    IO.puts("before")\n    IO.puts(inspect(Crypto.hash_password("a", [iterations: 100000001])))\n  end\nend\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.hash_password takes from 1 to 100000000 iterations\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    IO.puts(inspect(Crypto.hash_password("a", [salt: 1, iterations: 0])))\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:21: Crypto.hash_password takes iterations:, not salt:\n  at Main.main (<stdin>:4)\n',
  {},
  b''),
 ('defmodule Main do\n'
  '  def digest(a: atom, d: string): string do\n'
  '    try do\n'
  '      Base.encode16(Crypto.hash(a, d))\n'
  '    rescue\n'
  '      e -> "failed: " <> inspect(e)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(digest(:md5, "x"))\n'
  '    IO.puts(digest(:md4, "x"))\n'
  '    IO.puts(inspect(Enum.map([:sha1, :sha256], fn a -> byte_size(Crypto.hmac(a, "k", "d")) end)))\n'
  '    IO.puts(:sha1 |> Crypto.hash("abc") |> Base.encode16())\n'
  '  end\n'
  'end\n',
  0,
  b'9DD4E461268C8034F5C8564E155C67A6\nfailed: "Crypto.hash: the algorithms are :md5, :sha1, :sha224, :sha256, :sha384 and :sha512, not :md4"\n[20,'
  b' 32]\nA9993E364706816ABA3E25717850C26C9CD0D89D\n',
  b'',
  {},
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    a = String.duplicate("ab", 150000)\n'
  '    IO.puts(inspect({Crypto.secure_compare(a, a <> ""), Crypto.secure_compare(a, String.duplicate("ab", 149999) <> "aa"), '
  'Crypto.secure_compare("\\x00", "\\x01"), Crypto.secure_compare("b" <> a, "a" <> a)}))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, false, false, false}\n',
  b'',
  {},
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule Main do\n  def main() do\n    IO.puts(Crypto.hash("sha256", "abc"))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(Crypto.hash(:sha256, 5))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(Crypto.hash(:sha256))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(Crypto.hmac(:sha256, "k"))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(Crypto.pbkdf2(:sha256, "p", "s", "4", 4))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Crypto.strong_rand_bytes("4")))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(Crypto.hash_password("p", [iterations: "4"]))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Crypto.verify_password("p")))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(inspect(Crypto.secure_compare("p", 1)))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.puts(Crypto.sha256("p"))\n  end\nend\n']

import hashlib, hmac, random

def differential(compiler, d):
    """Random data against hashlib: the lengths around every block boundary and 3 MB from a file."""
    rnd=random.Random(20261118);names=['md5','sha1','sha224','sha256','sha384','sha512'];lines=[];want=[]
    sizes=[0,1,55,56,57,63,64,65,111,112,113,119,120,127,128,129,255,256,257,4095,4096,65537,3000000]
    for index,size in enumerate(sizes):
        data=rnd.randbytes(size);(d/f'd{index}').write_bytes(data)
        key=bytes(rnd.choice(b'abcxyz0189') for _ in range(rnd.choice([0,1,20,63,64,65,127,128,129,300])))
        salt=bytes(rnd.choice(b'abcxyz0189') for _ in range(rnd.randrange(40)))
        rounds=rnd.randrange(1,40);wanted=rnd.choice([1,16,20,32,33,64,65,200])
        lines.append(f'    one("d{index}", "{key.decode()}", "{salt.decode()}", {rounds}, {wanted})\n')
        for name in names:
            want.append(hashlib.new(name,data).hexdigest()+' '+hmac.new(key,data,name).hexdigest()+' '+hashlib.pbkdf2_hmac(name,key,salt,rounds,wanted).hex())
    source=('defmodule Main do\n  def hex(b: string): string do Base.encode16(b, [case: :lower]) end\n'
      '  def one(path: string, key: string, salt: string, rounds: integer, wanted: integer): integer do\n    case File.read_binary(path) do\n      ok(data) ->\n'
      '        Enum.each([:md5, :sha1, :sha224, :sha256, :sha384, :sha512], fn a -> IO.puts(hex(Crypto.hash(a, data)) <> " " <> hex(Crypto.hmac(a, key, data)) <> " " <> hex(Crypto.pbkdf2(a, key, salt, rounds, wanted))) end)\n'
      '        0\n      error(reason) ->\n        IO.puts(reason)\n        1\n    end\n  end\n')
    count=0
    # A program per file, as each was measured.
    for line in lines:
        built=subprocess.run([str(compiler)],input=(source+'  def main() do\n'+line+'  end\nend\n').encode(),capture_output=True,env={'PATH':''},timeout=120)
        assert (built.returncode,built.stderr)==(0,b''),(built.returncode,built.stderr)
        out=d/'differential';out.write_bytes(built.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},cwd=d,timeout=120)
        assert (run.returncode,run.stderr)==(0,b''),(line,run.returncode,run.stderr)
        got=run.stdout.decode().split('\n')[:-1]
        assert got==want[count:count+6],(line,got,want[count:count+6])
        count+=6
    return count


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-crypto-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr,env,stdin in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':'',**env},input=stdin,cwd=d,timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
        extra=f', {differential(compiler,Path(d))} digest, HMAC and PBKDF2 triples of random data equal to hashlib'

    print(f'PASS crypto: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected{extra}; the six digests at the block boundaries and over a megabyte, HMAC with keys around a block, PBKDF2 to 600000 rounds, random bytes, stored passwords read as Go reads them, the pinned failures')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
