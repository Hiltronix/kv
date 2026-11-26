#!/bin/bash
set -euo pipefail

PKGNAME=$(basename "$PWD")
VERSION=$(git cliff --bumped-version --unreleased |cut -dv -f2)

sed "s/^version:.*$/version: $VERSION/g" -i shard.yml
./build_static.sh
git add shard.yml
git cliff --bump -o
git commit -a -m "bump: Release v$VERSION"
git tag "v$VERSION"
git push --tags
gh release create "v$VERSION" "bin/$PKGNAME-static-linux-amd64" "bin/$PKGNAME-static-linux-arm64" "bin/$PKGNAME-static-linux-amd64.sha256" "bin/$PKGNAME-static-linux-arm64.sha256" --title "Release v$VERSION" --notes "$(git cliff -l -s all)"
