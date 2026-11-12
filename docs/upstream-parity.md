# Restoring full upstream a-Shell

The requested deliverable is the full upstream package/tool set with continued
background processing. TestFlight build 608 is the earlier reduced build; it is
not the completed upstream-parity deliverable.

Current verified components:

| Component | Version/source | Validation |
| --- | --- | --- |
| cryptography | 3.4.8, matching upstream's recipe | Fernet encrypt/decrypt and repeated interpreter launches on arm64 iOS Simulator |
| CFFI | 1.17.1, iOS wheels | Used by the cryptography runtime checks |
| NumPy | 2.3.1, pinned upstream patched submodule | iOS and Simulator source builds; linear solve, FFT, random generation, repeated launches |
| Pico | 5.09 / Alpine 2.26 | Three architecture slices; 20 edit/save, UTF-8, descriptor and signal-handler checks |

SciPy and the remaining scientific, geospatial, imaging, and terminal components
are still being restored. Do not declare parity from a successful reduced-target
build.

## Build inputs and checks

`scripts/python-upstream-native-wheels.json` records the publisher URLs and
SHA-256 values for the CFFI/cryptography iOS wheels. The wheel installer verifies
the hash, creates framework-based import stubs, and packages separate native
libraries for the `Python` and `pythonA` interpreter instances. Install the pure
Python dependencies as well; CFFI requires pycparser.

`scripts/build-upstream-numpy.py` builds the pinned NumPy fork, consolidates its
extensions as upstream does, and packages both interpreter copies. It uses the
iOS Python headers through a target-specific pkg-config file, not the build
Mac's Python headers. Build prerequisites are Xcode, host Python 3.13, Ninja,
pkg-config, and a build environment at `build/upstream-parity/venv` containing
Cython 3.1.6, meson-python, pybind11, packaging, and host NumPy 2.3.1. Initialize
NumPy's vendored Meson, pocketfft, pythoncapi-compat, and highway submodules.
The source-built Python frameworks must already be staged under
`build/upstream-parity/device/Frameworks` (or `simulator/Frameworks`).

```sh
python3 scripts/build-upstream-numpy.py
python3 scripts/build-upstream-numpy.py --simulator
bash scripts/build-pico.sh
```

Pico statically links checksum-pinned ncurses terminfo. The adapter keeps error
exits and output inside the current ios_system command, and uses the hexadecimal
directory layout of the bundled terminfo database. The build rejects imports of
the system terminfo functions that failed Apple's validation.

The parity audit reads the original full-target dependency and command lists.
It has no reduced-profile exclusion list and exits unsuccessfully for missing
frameworks, commands, or native import stubs:

```sh
python3 scripts/audit-upstream-parity.py --target a-Shell --app /path/to/a-Shell.app \
  --output build/upstream-parity/app-audit.json
```

The isolated Python integration harness is `tests/python-runtime-smoke.m`.
It writes command results to `Documents/python-results.txt` in its test app.
Full app validation and internal TestFlight delivery follow restoration of the
remaining components.
