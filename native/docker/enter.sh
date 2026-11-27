#!/bin/sh
# The development container's entrypoint. With ALCHEM_UID set (as
# scripts/linux-container.sh sets it), the command runs as that user, the one
# who owns the mounted repository, and not as root: files it writes belong to
# that user, and a file made read-only is read-only to it, as on a host.
set -eu
uid="${ALCHEM_UID:-0}"
gid="${ALCHEM_GID:-0}"
if [ "$uid" = 0 ]; then exec mise exec -- "$@"; fi
# The caches are volumes that outlive the container: they become the user's
# once, the first time a container runs as that user.
for dir in /var/cache/alchem-native /opt/cargo/registry; do
  mkdir -p "$dir"
  if [ "$(stat -c %u:%g "$dir")" != "$uid:$gid" ]; then chown -R "$uid:$gid" "$dir"; fi
done
export HOME=/var/cache/alchem-native/home
mkdir -p "$HOME" && chown "$uid:$gid" "$HOME"
# A name for the user, for the programs that look one up.
if ! getent passwd "$uid" >/dev/null; then echo "alchem:x:$uid:$gid::$HOME:/bin/bash" >> /etc/passwd; fi
if ! getent group "$gid" >/dev/null; then echo "alchem:x:$gid:" >> /etc/group; fi
exec setpriv --reuid "$uid" --regid "$gid" --clear-groups mise exec -- "$@"
