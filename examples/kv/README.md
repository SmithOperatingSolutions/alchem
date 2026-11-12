# kv: a key-value server in Alchem

A small Redis-like server, written to find out what building a real service in Alchem is like. It uses most of the language: processes and supervision, servers with timers, a registry, TCP, HTTP, JSON, files, error handling with `result`, and tests at three levels.

```sh
alchem run main.alc -- --port 127.0.0.1:6380 --http 127.0.0.1:8380 --data kv.log
alchem run client.alc -- SET greeting "hello there"
alchem run client.alc -- GET greeting
alchem run client.alc                       # interactive
curl 127.0.0.1:8380/stats
alchem test test
```

## Commands

Strings: `GET`, `SET key value [EX s | PX ms] [NX | XX]`, `DEL`, `EXISTS`, `INCR`, `DECR`, `INCRBY`, `DECRBY`, `APPEND`, `STRLEN`. Keys: `KEYS pattern` (`*` and `?`), `EXPIRE`, `PEXPIREAT`, `TTL`, `PERSIST`, `DBSIZE`, `FLUSHDB`. Lists: `LPUSH`, `RPUSH`, `LPOP`, `RPOP`, `LRANGE`, `LLEN`. Messages: `PUBLISH`, `SUBSCRIBE`, `UNSUBSCRIBE`. Server: `PING`, `ECHO`, `INFO`, `REWRITE`, `QUIT`. The wire format is described in `lib/protocol.alc`.

## How it is built

| File | What it does |
| --- | --- |
| `lib/protocol.alc` | Request lines to commands and back, replies to text and back. Pure functions, with doctests. |
| `lib/store.alc` | The data and every command's effect on it, as a function of the state and the time. Pure, so tested without processes. |
| `lib/glob.alc` | `KEYS` patterns. |
| `lib/log.alc` | The append-only log, a server that writes changes in order and rewrites the log atomically. |
| `lib/database.alc` | The server that owns the data: runs commands one at a time, logs each change before replying, and expires keys with `Server.send_after`. |
| `lib/connection.alc` | One process per client connection; subscriptions through a `Registry`, so a closed connection unsubscribes itself. |
| `lib/web.alc` | `/health`, `/stats`, `/keys` and `/key/NAME` over HTTP. |
| `lib/kv.alc` | Starts everything: connections are temporary children of a `DynamicSupervisor`. |
| `main.alc`, `client.alc` | The server and client programs. |

The tests in `test/` cover the protocol, the store, the database with its log and timers, and the whole server over real TCP and HTTP connections, including twenty concurrent clients and a restart.
