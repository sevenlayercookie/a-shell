# Python terminal build

The terminal profile builds the real `a-Shell-mini` and `a-Shell` targets with
CPython 3.13, pip, IPython, requests, and the available terminal frameworks.
SciPy, scikit-learn, and other missing native scientific extensions are deferred.
The generated command dictionary removes commands whose frameworks are absent.
`Library/python-terminal-profile.json` records exactly what each app contains.

Use the Python revision pinned by the `cpython` submodule. Install a host Python
3.13 and resolve the `xcfs` package in Xcode, then run from the repository root:

```sh
git submodule update --init cpython
python3 scripts/build-python-runtime.py
python3 scripts/prepare-python-terminal-project.py
xcodebuild -project a-Shell-Python.xcodeproj -scheme a-Shell-mini \
  -configuration Release -destination 'generic/platform=iOS' \
  -jobs 4 CODE_SIGNING_ALLOWED=NO build
```

Use `-scheme a-Shell` for the full terminal target. The generated project leaves
the upstream scientific dependency declarations intact in the original project.
It is local build output and should not be committed. Available optional tools
are included when their frameworks exist; build pico/openrsync with the existing
scripts before generating the project. Other optional tools use the upstream
framework locations declared in the original project.

The runtime script verifies downloaded dependency hashes, builds CPython from
source, installs hash-pinned pure Python wheels, and packages both interpreter
instances plus framework-based extension modules. `--skip-compile` regenerates
the payload using an existing interpreter installation. Compiler output is in
`build/python/runtime-build.log`. Console scripts use the on-device interpreter.

For signing, pass your local `-xcconfig Configuration.xcconfig` and the existing
`ASHELL_CODE_SIGN_*`, `ASHELL_PROVISIONING_PROFILE_SPECIFIER`, and
`ASHELL_INFOPLIST_FILE` overrides. Keep extension deployment targets at their
project values; do not globally override `IPHONEOS_DEPLOYMENT_TARGET`.
Run `scripts/prepare-testflight-archive.py` after archiving and before exporting
with the existing internal-only TestFlight export settings.

## Validation

Both Python-enabled targets have passed device Release compilation. The isolated
UIKit harness in `tests/python-runtime-smoke.m` runs the embedded interpreter
through `ios_system`, testing standard modules, pip, IPython, HTTPS, package
installation, and repeated interpreter launches. It writes command output and
exit statuses to `Documents/python-results.txt`. Run it in a separate test app
with the generated Library, Python/pythonA frameworks, ios_system framework,
and the generated `build/python/profiles/a-Shell-mini/commandDictionary.plist`. Its scene manifest must name `PythonSmokeDelegate`.
Use a native simulator build of CPython and its dependencies for simulator runs;
the packaged device binaries cannot run in the simulator.

Background progress/cancellation checks:

```sh
sh tests/continued-processing.sh
```

On the iPhone, try:

```sh
python3 --version
pip --version
ipython --quick --no-banner -c 'print("IPython works")'
background python3 -c 'import time; print("started", flush=True); time.sleep(60); print("finished", flush=True)'
```

Send the app to the background after starting the last command. iOS controls
continued-processing availability; the app reports a rejected request in the
terminal. Internal TestFlight delivery uses the existing fork bundle identity.
The private distribution profile omits the restricted user-font entitlement;
bundled fonts still work.
