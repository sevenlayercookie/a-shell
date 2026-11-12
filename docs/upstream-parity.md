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
| SciPy | 1.16.1, upstream version with static OpenBLAS/Flang | Linear solve, quadrature, special functions, statistics, HiGHS, ARPACK, all four PROPACK types, repeated imports on arm64 Simulator |
| PyCryptodome / Cryptodomex | 3.23.0, checksum-pinned source | AES round trip, SHA-256, RSA key export/import, repeated commands on arm64 iOS Simulator |
| Pillow | 13.0.0, publisher iOS wheels | PNG/JPEG round trips, font metrics, repeated commands; upstream ImageShow adapter retained |
| Kiwi | 1.5.1, publisher iOS wheels | Constraint solver runtime check |
| Pico | 5.09 / Alpine 2.26 | Three architecture slices; 20 edit/save, UTF-8, descriptor and signal-handler checks |

The remaining scientific, geospatial, and terminal components are still being restored. Do not declare parity from a successful reduced-target
build.

## Build inputs and checks

`scripts/python-upstream-native-wheels.json` records the publisher URLs and
SHA-256 values for the CFFI, cryptography, Pillow, and Kiwi iOS wheels. The wheel installer verifies
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

`scripts/build-upstream-pycryptodome.py` verifies the source archive and builds
both `Crypto` and `Cryptodome`, including all 40 native modules in each namespace.
The packager routes native loads to the signed framework for the current Python
interpreter. Build each platform with:

```sh
python3 scripts/build-upstream-pycryptodome.py
python3 scripts/build-upstream-pycryptodome.py --simulator
```

Pillow preserves the upstream consolidated framework name through a native
re-export facade. Its child frameworks must also be embedded in the final app.
These staged components still require full-target integration and validation.

The scientific toolchain uses Flang 23.1.5 and checksum-pinned OpenBLAS 0.3.34.
It builds device and Simulator static libraries without the private GNU Fortran
runtime paths in the old prebuilt OpenBLAS artifact. SciPy retains its numerical
APIs; Pythran acceleration is disabled. These scripts require CMake and the
Homebrew LLVM/Flang tools in addition to the Python build prerequisites:

```sh
python3 scripts/build-ios-scientific-toolchain.py
python3 scripts/build-upstream-scipy.py
python3 scripts/build-ios-scientific-toolchain.py --simulator
python3 scripts/build-upstream-scipy.py --simulator
```

The Cython module-state patch handles a retained extension module after
`Py_Finalize` clears its dictionary and a new main interpreter reuses its ID.
NumPy and SciPy use per-module state and recreate finalized modules. The combined
23-command Simulator integration run passes, including interpreter reentry,
package operations, pip installation, IPython and HTTPS. Both device packages
also compile; this is not a claim of physical-device runtime validation.
