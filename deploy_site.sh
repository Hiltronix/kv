#!/bin/bash
set -euo pipefail
# Prepare a local site without connecting to the upstream deployment server.
[[ $# -eq 1 ]] || { echo "Usage: $0 OUTPUT_DIRECTORY" >&2; exit 1; }
mkdir -p -- "$1/vendor"
cp -a site/. "$1/"
cp -a assets/vendor/. "$1/vendor/"
