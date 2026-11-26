#!/bin/bash
set -euo pipefail

# Install only a locally supplied, independently verified executable.
if [[ $EUID -ne 0 || $# -ne 2 ]]; then
    echo "Usage: sudo bash site/install.sh /path/to/kv EXPECTED_SHA256" >&2
    exit 1
fi
binary=$1
expected=$2
[[ -f "$binary" && "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || exit 1
source_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
[[ -f "$source_dir/kv.service" ]] || { echo "Run from a trusted KV source checkout." >&2; exit 1; }
if systemctl is-active --quiet kv.service; then
    echo "Stop the running KV service before installing." >&2
    exit 1
fi
install -d -m 0700 /etc/kv /var/lib/kv
install -d -m 0755 /usr/local/bin
temp=$(mktemp /usr/local/bin/.kv.XXXXXXXX)
trap 'rm -f -- "$temp"' EXIT
install -m 0755 -- "$binary" "$temp"
actual=$(sha256sum "$temp")
actual=${actual%% *}
[[ "$actual" == "$expected" || "$actual" == "${expected,,}" ]] || { echo "SHA-256 mismatch." >&2; exit 1; }
mv -fT -- "$temp" /usr/local/bin/kv
install -m 0644 -- "$source_dir/kv.service" /etc/systemd/system/kv.service
if [[ ! -e /etc/kv/kv.env ]]; then
    (umask 077; printf '%s\n' 'KV_USER=' 'KV_PASSWORD=' > /etc/kv/kv.env)
fi
chmod 0600 /etc/kv/kv.env
systemctl daemon-reload
echo "Installed without starting the service."
echo "Set credentials in /etc/kv/kv.env, review the bind address, then run:"
echo "  systemctl enable --now kv.service"
