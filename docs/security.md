# Privacy and deployment

This development branch is not yet a tested release. Runtime use does not require a cloud account, relay, DNS service or external web assets. Dependencies are fetched during build, not during normal operation.

## Install

Build from this fork, inspect the output and obtain a SHA-256 digest from a trusted source. Run `sudo bash site/install.sh /path/to/kv EXPECTED_SHA256` from the source checkout. The installer does not download executables or start the service. Set KV_USER and a unique, randomly generated KV_PASSWORD (at least 16 characters) in the root-only /etc/kv/kv.env file before enabling the service. Do not use credentials shared with other services.

The service defaults to loopback HTTP port 3000. For remote access use an HTTPS reverse proxy with a verified certificate, or bind explicitly to the device's WireGuard address and restrict firewall access to authorized peers. Do not expose port 3000 to the Internet. KV does not implement native TLS. Basic Auth over bare HTTP is not encrypted.

## Optional USB features

- `--enable-ethernet`: allow ECM activation; DHCP only, no DNS or default gateway advertisement. Apply firewall restrictions to usb0 separately.
- `--enable-mass-storage`: permit USB virtual disk attachment. Images are read-only to the controlled computer. Raw IMG/RAW/ISO and gzip, bzip2, xz and ZIP are supported. QCOW2 is rejected. Uploads are limited to 1 GiB and decompressed output to 8 GiB per image. Use a dedicated filesystem quota to cap aggregate storage.
- Neither feature is permitted by default. Keyboard/mouse/video remain independent of them.

The systemd service retains root and hardware access needed by configfs, modprobe and USB HID. Hardening is not a substitute for firewall restrictions. Test on actual hardware before deployment.

## Privacy verification

Test both the KVM device and browser in a network-isolated environment. Verify that no connections to external origins occur in browser DevTools (including fonts, CSS, WebSocket, PWA/cache and audio). Capture DNS and outbound traffic on the SBC during startup, idle, browser connections and optional USB activation. Use test text, not real passwords, to verify absence from logs even at DEBUG level. Clear any historical journal entries and legacy browser caches separately if appropriate.

Test missing/invalid credentials, authenticated HTTP and WebSocket, cross-origin requests, both USB opt-in flags, upload size limits, invalid paths, symlinks, compressed data and read-only USB behavior. Review the systemd unit on the target platform before enabling it. Dependency vulnerability and native binary audits remain separate tasks.

## Dependency security review (2026-11-26)

- Kemal 1.15.0: security fixes GHSA-x97g-6h7h-q9w6 and GHSA-89xc-29wg-6mm5.
- Crystal 1.22.3 minimum: HTTP parsing and networking security fixes; the Alpine build requests 1.22.3-r0 explicitly.
- ALSA: pinned 1.2.16.1 plus upstream patches for CVE-2026-90781, CVE-2026-96674 and CVE-2026-96675. The newer base also addresses CVE-2026-25068 and CVE-2026-56109.
- Further review of transitive libraries and compiled binary dependencies is required. Direct APK requirements and the base image digest are pinned below; transitive package inventory is captured per build.

## ARM64 static build

The Alpine builder image is pinned by digest and the directly installed packages by observed versions. The package repository is still rolling, so an unavailable exact version intentionally fails the build. Complete offline reproducibility would require retaining a verified APK repository snapshot.

The ARM64 release build pairs the existing musl archive members for sigsetjmp and setjmp into a relocatable object, avoiding the limited conditional branch displacement that can occur in a large statically linked executable. No libc instructions are changed. The build runs a sigsetjmp/siglongjmp smoke test including restoration of a blocked signal mask. Both the local static builder and CI use the same release build script.

CI uploads binaries and SHA-256 files only after the corresponding architecture's runtime privacy tests pass, together with the build package inventory and source commit. These are development artifacts, not production releases.

## Expanded opt-in and package checks

The headless runtime suite exercises optional feature flags, raw and gzip image uploads, duplicate rejection, invalid image rejection, path traversal, symlink rejection, and deletion without attaching real USB hardware. Actual mass-storage read-only enforcement, ECM/DHCP operation and video/audio/HID require physical hardware testing.

The build audit compares installed Alpine source-package versions with the current official Alpine edge security database. The JSON report is retained with each tested artifact, including database SHA-256 hashes and potential findings. A reported version below a fix is a review candidate, not automatic proof of exploitability. This check covers installed build packages, not source-built libraries, Crystal shards, the target operating system, or all vulnerabilities. It does not contact the network at application runtime.
