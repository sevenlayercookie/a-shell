#!/bin/sh
# Test production progress/cancellation state without an iOS scheduler or signing.
set -eu
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
trap 'exit 130' HUP INT TERM
xcrun swiftc -swift-version 5 -emit-library -emit-module -module-name ios_system \
    tests/long-commands-runtime.swift -o "$scratch/libios_system.dylib"
xcrun swiftc -swift-version 5 -I "$scratch" -L "$scratch" -lios_system \
    -Xlinker -rpath -Xlinker "$scratch" \
    a-Shell/ContinuedProcessing.swift a-Shell-LongCommands/ProgressCommand.swift \
    tests/continued-processing.swift -o "$scratch/tests"
"$scratch/tests"
