# Linux x86-64 development image. Toolchain versions come from mise.toml, so the
# container and a native Linux host use exactly the same pins.
FROM debian:trixie-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential binutils strace \
 && rm -rf /var/lib/apt/lists/*

ARG MISE_VERSION=2026.7.3
ENV MISE_INSTALL_PATH=/usr/local/bin/mise \
    MISE_YES=1 \
    MISE_TRUSTED_CONFIG_PATHS=/work:/etc/alchem-native \
    CARGO_TARGET_DIR=/var/cache/alchem-native/rust-target \
    GOCACHE=/var/cache/alchem-native/go-build
RUN curl -fsSL https://mise.run | MISE_VERSION="v${MISE_VERSION}" sh

COPY mise.toml /etc/alchem-native/mise.toml
RUN cd /etc/alchem-native && mise install && mise exec -- go version \
 && mise exec -- cargo --version && mise exec -- python3 --version

WORKDIR /work
ENTRYPOINT ["mise", "exec", "--"]
CMD ["bash"]
