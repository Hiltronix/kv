#!/bin/bash
set -euo pipefail
# Use an existing native or externally configured multi-platform Docker builder.
# Never run a privileged third-party QEMU setup image here.
for arch in "$@"; do
    case "$arch" in amd64|arm64) ;; *) echo "Unsupported architecture: $arch" >&2; exit 1;; esac
done
if [[ $# -eq 0 ]]; then set -- amd64 arm64; fi
for arch in "$@"; do
    image="kv-builder-$arch"
    docker build --platform "linux/$arch" -f Dockerfile.static -t "$image" .
    docker run --rm --platform "linux/$arch" -v "$PWD":/work -w /work --user "$(id -u):$(id -g)" "$image" /bin/sh -ec 'shards install --frozen && shards build --static --release && strip bin/kv'
    mv bin/kv "bin/kv-static-linux-$arch"
    sha256sum "bin/kv-static-linux-$arch" > "bin/kv-static-linux-$arch.sha256"
done
