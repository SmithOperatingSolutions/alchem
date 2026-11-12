# Security

## Reporting a vulnerability

Report vulnerabilities privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Please do not open a public issue for a security problem.

Include what is affected (the compiler, the runtime that compiled programs carry, the node protocol, or a tool), the version (`alchem version`), and the steps or program that show the problem. You will get an acknowledgement, and the fix and advisory are published together once a release carries the fix.

## Supported versions

Alchem is experimental and has no long-term support branches. Fixes go into the next release; use the latest one.

## Scope

In scope:

- The compiler and CLI, including the Go toolchain it downloads (`compiler/toolchain.go` checks each download against recorded SHA-256 sums).
- The runtime embedded in compiled programs: processes, supervision, the `TCP`, `UDP`, `HTTP` and `File` libraries, and connections between nodes (TLS 1.3 with a cookie proof).
- The release workflow and the archives it publishes.

Not vulnerabilities:

- The private key in `tests/fixtures/http_more.alc`. It is a self-signed key used only by the HTTPS tests and protects nothing.
- Programs that run untrusted Alchem source. Compiling and running a program executes it with your permissions; neither `alchem test` nor `alchem alx` is a sandbox.
