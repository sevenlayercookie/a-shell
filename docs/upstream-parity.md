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
| lxml | 6.1.3; static libxml2 2.9.13 and libxslt 1.1.35 | XPath, XSLT, objectify, HTML cleaning and three interpreter launches |
| regex | 2026.11.9 | Unicode and recursive patterns over three launches |
| ContourPy | 1.3.3 with pinned upstream pybind11 fork | Contour generation over three launches |
| Matplotlib | pinned upstream 800b734626; 3.10.0.dev18 | Nine native extensions; PNG/SVG/PDF, fonts, contours and triangulation across three launches |
| WordCloud | 1.9.6 | PNG rendering and three launches; command-line help |
| psutil | upstream iOS fork 7.0.0 | CPU, system memory, current-process RSS and disk usage across three launches |
| Argon2 | bindings 26.1.0; argon2-cffi 25.1.0 | Password hash/verify and raw Argon2id across three launches |
| PyZMQ | 27.3.0; ZeroMQ 4.3.5; libsodium 1.0.22 | Encrypted CURVE loopback and multipart messages across three launches |
| pandas | 2.3.1, compatible with pinned upstream Matplotlib | CSV/JSON, groupby, nullable integers, DST timezones, rolling windows and plotting across three launches |
| ERFA | pyerfa 2.0.1.5 | Calendar conversion and vectorized spherical coordinates across three launches |
| Astropy | 8.0.2 | Units, time, coordinates, FITS, tables, WCS and convolution across three launches |
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
59-command Simulator integration run passes, including interpreter reentry,
package operations, pip installation, IPython and HTTPS. Both device packages
also compile; this is not a claim of physical-device runtime validation.

`build-upstream-lxml.py` builds a single native library with all seven extension
entry points. It statically links the XML libraries so each Python interpreter
owns its XML callbacks, preserves HTML cleaning through `lxml_html_clean`, and
checks all entry points before packaging. Build the dependencies first:

```sh
python3 scripts/build-ios-xml.py
python3 scripts/build-upstream-lxml.py
python3 scripts/build-ios-xml.py --simulator
python3 scripts/build-upstream-lxml.py --simulator
python3 scripts/build-upstream-regex.py
python3 scripts/build-upstream-regex.py --simulator
python3 scripts/build-upstream-contourpy.py
python3 scripts/build-upstream-contourpy.py --simulator
```

ContourPy requires the pinned `cpython/packages/pybind11` submodule. Its upstream
thread-local internals fix is essential: the prebuilt ContourPy wheel crashed
on the third interpreter launch. `prepare-ios-pybind11.py` installs that fork
into an isolated build prefix, leaving the host package environment intact.

`install-pep621-metadata.py` preserves upstream package versions, dependencies
and entry points for Meson builds, so pip recognizes the bundled native packages.
The Cython reload fix handles both cleared dictionaries and fully cleared
modules. Use `python-upstream-build-requirements.txt` for the host Python venv.

Build the isolated Simulator test app from the staged payload with:

```sh
python3 scripts/prepare-python-simulator-smoke.py
xcrun simctl install booted build/python/smoke-simulator/PythonSmoke.app
xcrun simctl launch booted sevenlayercookie.a-Shell-mini.PythonSmoke
```

Read `Documents/python-results.txt` in the test app's data container. Each launch
clears the previous log. This harness does not replace physical-device or full
app verification.

## Additional package builds

```sh
python3 scripts/install-upstream-pure-wheels.py
python3 scripts/build-upstream-matplotlib.py
python3 scripts/build-upstream-wordcloud.py
python3 scripts/build-upstream-psutil.py
python3 scripts/build-upstream-argon2.py
python3 scripts/build-upstream-pyzmq.py
```

Each native builder also accepts `--simulator`. The pure-wheel installer stages
both platforms from the SHA-pinned manifest. It includes the plotting and
password-hashing dependencies and preserves their console entry points.
`f2py -v` and `wordcloud_cli --help` are part of the runtime suite.

All source-built Cython packages use per-module state **and heap types**
(`CYTHON_USE_TYPE_SPECS=1`). Static Cython types retain mutated method dictionaries
after interpreter shutdown; the longer suite exposed that problem in SciPy's
shared utility module. The 59-command suite passes with fresh heap types.

The psutil iOS port's current-process memory query now uses matching
`MACH_TASK_BASIC_INFO` structure and count values. Other-process queries remain
restricted by the iOS port. No extra process-inspection entitlement is needed.

ZeroMQ statically includes the complete libraries and CURVE support. The iOS
package selects the CFFI backend, matching upstream's framework layout. Native
frameworks link directly to the matching `Python` or `pythonA` runtime.

Pandas uses C++17, target NumPy headers and local C helper linkage when its
extensions are consolidated. `ios-cython.py` corrects Cython 3.1.6's cached
memoryview traversal and gives generated divmod sentinels local linkage.
The astronomy builder applies the same traversal correction to setuptools
builds and preserves upstream's Documents-based writable directory behavior.

CPython's static type version counter now survives `Py_Finalize`/`Py_Initialize`.
Some extension types retain their old version tags; resetting the counter could
assign the same tag to another type and return an unrelated attribute descriptor.
The 59-command run includes the NumPy masked-array lookup that exposed this
collision after pandas was added. Both device and Simulator runtimes rebuild
with `patches/cpython-preserve-type-version-tags.patch`.

```sh
python3 scripts/build-upstream-pandas.py
python3 scripts/build-upstream-pandas.py --simulator
python3 scripts/build-upstream-astronomy.py pyerfa
python3 scripts/build-upstream-astronomy.py pyerfa --simulator
python3 scripts/build-upstream-astronomy.py astropy
python3 scripts/build-upstream-astronomy.py astropy --simulator
python3 scripts/build-upstream-pyyaml.py
python3 scripts/rebuild-python-reentry.py
python3 scripts/rebuild-python-reentry.py --simulator
```

PyYAML retains the portable backend used by upstream's Python package layout.
Astropy IERS tables and pandas timezone data are checksum-pinned in the pure
wheel manifest. Full app integration and the remaining packages/tools are still
pending; TestFlight 608 remains the earlier reduced build.

## Additional scientific packages

The device and Simulator builds include FFTW 3.3.11 and PyFFTW 0.15.1,
scikit-learn 1.9.1, QuTiP 5.3.1, statsmodels 0.15.0, and CVXOPT 1.3.3.
CVXOPT uses its upstream-pinned SuiteSparse 7.11.0 and includes SuiteSparse
and FFTW license texts. Their checksum-pinned build scripts are in `scripts/`.

The 80-command Simulator run passed numerical transforms, model fitting,
quantum evolution, optimization, sparse solves and three parallel random
forest runs in each of the two bundled interpreters, as well as repeated
Python interpreter launches. The iOS NumPy
port now lets worker threads access the initialized state of their own bundled
interpreter; `patches/numpy-worker-shared-state.patch` preserves separate
state for the two NumPy frameworks. Cython module-state lookups acquire the
interpreter lock when generated code calls them without it.

These tests exercise the Simulator payload. The full app still needs its
remaining upstream packages, commands, resources, integration and device
validation before an updated TestFlight release.

GEOS 3.11.0 is built from its released source for device and arm64 Simulator;
upstream's older GEOS artifacts have no arm64 Simulator slice. Shapely 2.2.0
uses those libraries. An 84-command Simulator run passed geometry predicates,
union, WKB, and spatial-index queries across repeated launches and both Python
runtimes, alongside the earlier numerical and threaded checks.
