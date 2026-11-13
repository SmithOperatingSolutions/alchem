#!/bin/sh
# Installs alchem from a GitHub release on macOS or Linux:
#
#   curl -fsSL https://raw.githubusercontent.com/SmithOperatingSolutions/alchem/main/install.sh | sh
#
# ALCHEM_VERSION picks a release (the latest by default) and ALCHEM_INSTALL_DIR
# the directory for the alchem binary (~/.local/bin by default). The download
# is checked against the release's checksums.txt before anything is installed.
# Go is not needed: alchem downloads the Go release it builds with on first use.
set -eu

repository="SmithOperatingSolutions/alchem"
base="${ALCHEM_RELEASES_URL:-https://github.com/$repository/releases}"
install_dir="${ALCHEM_INSTALL_DIR:-$HOME/.local/bin}"

fail() {
	echo "alchem install: $*" >&2
	exit 1
}

need() {
	command -v "$1" >/dev/null 2>&1 || fail "needs $1"
}

need curl
need tar
need uname

case "$(uname -s)" in
Darwin) os=darwin ;;
Linux) os=linux ;;
*) fail "this script installs on macOS and Linux; on Windows use install.ps1 or Scoop" ;;
esac

case "$(uname -m)" in
x86_64 | amd64) arch=amd64 ;;
arm64 | aarch64) arch=arm64 ;;
*) fail "no release for the $(uname -m) processor" ;;
esac

version="${ALCHEM_VERSION:-}"
if [ -z "$version" ]; then
	# releases/latest redirects to the latest release's tag, which avoids the
	# API and its limit on requests from shared addresses.
	latest=$(curl -fsSL -o /dev/null -w '%{url_effective}' "$base/latest") || fail "could not find the latest release"
	version=${latest##*/}
	case "$version" in
	v[0-9]*) ;;
	*) fail "could not find the latest release" ;;
	esac
fi
case "$version" in
v*) ;;
*) version="v$version" ;;
esac

name="alchem_${version}_${os}_${arch}"
archive="$name.tar.gz"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT INT TERM

echo "Downloading alchem $version for $os/$arch"
curl -fsSL -o "$work/$archive" "$base/download/$version/$archive" || fail "could not download $archive"
curl -fsSL -o "$work/checksums.txt" "$base/download/$version/checksums.txt" || fail "could not download checksums.txt"

expected=$(grep " $archive\$" "$work/checksums.txt" | cut -d' ' -f1)
[ -n "$expected" ] || fail "checksums.txt has no entry for $archive"
if command -v sha256sum >/dev/null 2>&1; then
	actual=$(sha256sum "$work/$archive" | cut -d' ' -f1)
elif command -v shasum >/dev/null 2>&1; then
	actual=$(shasum -a 256 "$work/$archive" | cut -d' ' -f1)
else
	fail "needs sha256sum or shasum to check the download"
fi
[ "$actual" = "$expected" ] || fail "checksum mismatch for $archive: expected $expected, got $actual"

tar -xzf "$work/$archive" -C "$work"
mkdir -p "$install_dir"
cp "$work/$name/alchem" "$install_dir/alchem.new"
chmod 755 "$install_dir/alchem.new"
mv "$install_dir/alchem.new" "$install_dir/alchem"

echo "Installed $("$install_dir/alchem" version | head -n 1) to $install_dir/alchem"
case ":$PATH:" in
*":$install_dir:"*) ;;
*) echo "Add $install_dir to your PATH to run alchem from anywhere." ;;
esac
