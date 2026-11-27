# Linux x86-64 development image. Toolchain versions come from the repository's
# mise.toml, so the container and a native Linux host use exactly the same
# pins. scripts/linux-container.sh builds it with that file and docker/enter.sh
# as the context, mounts the repository at /work and runs the command as the
# repository's owner (docker/enter.sh). The tools are installed outside /root
# so that user can run them.
FROM debian:trixie-slim

RUN apt-get -o Acquire::Retries=5 update \
 && apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
      ca-certificates curl git build-essential binutils binutils-aarch64-linux-gnu qemu-user-static strace \
 && rm -rf /var/lib/apt/lists/*

ARG MISE_VERSION=2026.7.3
ENV MISE_INSTALL_PATH=/usr/local/bin/mise \
    MISE_YES=1 \
    MISE_TRUSTED_CONFIG_PATHS=/work:/etc/alchem-native \
    MISE_DATA_DIR=/opt/mise \
    MISE_CACHE_DIR=/var/cache/alchem-native/mise \
    MISE_STATE_DIR=/var/cache/alchem-native/mise-state \
    RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    MISE_DISABLE_TOOLS=erlang,elixir \
    CARGO_TARGET_DIR=/var/cache/alchem-native/rust-target \
    GOCACHE=/var/cache/alchem-native/go-build
# Erlang and Elixir are only for the benchmarks' baselines: not installed.
# A download that fails is tried again for some minutes: a server that is
# down for a moment is no failure of what is built here.
RUN curl -fsSL --retry 8 --retry-all-errors --retry-max-time 300 -o /tmp/mise.sh https://mise.run \
 && MISE_VERSION="v${MISE_VERSION}" sh /tmp/mise.sh && rm /tmp/mise.sh

COPY mise.toml /etc/alchem-native/mise.toml
RUN cd /etc/alchem-native \
 && for wait in 5 15 45 90 end; do mise install && break; [ "$wait" != end ] || exit 1; sleep "$wait"; done \
 && mise exec -- go version \
 && mise exec -- cargo --version && mise exec -- python3 --version

# The repository mounted at /work belongs to the host's user: git (and the
# VCS stamp of go build) reads it as it does on the host, also as root.
RUN git config --system --add safe.directory /work

COPY enter.sh /usr/local/bin/alchem-enter
WORKDIR /work/native
ENTRYPOINT ["/usr/local/bin/alchem-enter"]
CMD ["bash"]
