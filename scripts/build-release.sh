#!/bin/sh
set -eu

# Build with the installed musl archive. AArch64 sigsetjmp uses a conditional
# branch to setjmp with a limited displacement. Keep the original two archive
# members adjacent in one relocatable object instead of modifying libc.
case "$(uname -m)" in
    aarch64|arm64)
        workDir=$(mktemp -d)
        trap 'rm -rf "$workDir"' EXIT
        libcArchive=$(cc -print-file-name=libc.a)
        test -f "$libcArchive"
        ar p "$libcArchive" sigsetjmp.lo > "$workDir/sigsetjmp.o"
        ar p "$libcArchive" setjmp.lo > "$workDir/setjmp.o"
        test -s "$workDir/sigsetjmp.o"
        test -s "$workDir/setjmp.o"
        ld -r -o "$workDir/kv-musl-jmp.o" "$workDir/sigsetjmp.o" "$workDir/setjmp.o"

        # Exercise the paired objects before building KV.
        cc -static tests/musl_sigsetjmp.c "$workDir/kv-musl-jmp.o" -o "$workDir/test-jmp"
        "$workDir/test-jmp"
        shards build --static --release --link-flags="$workDir/kv-musl-jmp.o"
        ;;
    *)
        shards build --static --release
        ;;
esac
