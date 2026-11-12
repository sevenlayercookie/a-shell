#!/usr/bin/env python3
"""Build all vendored Argon2 primitives and the upstream CFFI binding for iOS."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://files.pythonhosted.org/packages/0b/43/bb8b6e8708d49a5ab36781333af092d9f483b198a2710d01281204640055/argon2_cffi_bindings-26.1.0.tar.gz'
SHA256 = '63505c71542a44b68b1e38060450fb006404170da375feb31af153e7f9c6205d'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / 'argon2_cffi_bindings-26.1.0.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('Argon2 source checksum mismatch')
    source = base / 'argon2_cffi_bindings-26.1.0'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    payload = base / platform
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    python = base / 'venv/bin/python'
    project = base / ('argon2-' + platform + '-project')
    project.mkdir(parents=True, exist_ok=True)
    native = ['src/_argon2_cffi_bindings/_ffi.c']
    native += ['extras/libargon2/src/' + name for name in [
        'argon2.c', 'blake2/blake2b.c', 'core.c', 'encoding.c', 'ref.c', 'thread.c']]
    cmake = ['cmake_minimum_required(VERSION 3.20)', 'project(ashell_argon2 C)',
             'find_package(Threads REQUIRED)', 'add_library(_ffi SHARED']
    cmake += ['  "' + str(source / name) + '"' for name in native]
    cmake += [')', 'set_target_properties(_ffi PROPERTIES PREFIX "" SUFFIX ".so")',
              'target_compile_definitions(_ffi PRIVATE _CFFI_NO_LIMITED_API)',
              'target_include_directories(_ffi PRIVATE "' + str(config) + '" "' + str(ROOT / 'cpython/Include')
              + '" "' + str(source / 'extras/libargon2/include') + '" "' + str(ROOT / 'build/python/deps/include') + '")',
              'target_link_libraries(_ffi PRIVATE Threads::Threads)',
              'target_link_options(_ffi PRIVATE "-F' + str(payload / 'Frameworks') + '" "SHELL:-framework Python"'
              + ' "-F' + str(deps) + '" "SHELL:-framework ios_system" "SHELL:-undefined error")']
    (project / 'CMakeLists.txt').write_text('\n'.join(cmake) + '\n')
    build = base / ('argon2-' + platform)
    with (base / ('argon2-' + platform + '-build.log')).open('w') as log:
        subprocess.run(['cmake', '-S', str(project), '-B', str(build), '-G', 'Ninja',
                        '-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_OSX_ARCHITECTURES=arm64',
                        '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0', '-DCMAKE_OSX_SYSROOT=' + sdk,
                        '-DCMAKE_BUILD_TYPE=Release'], stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--build', str(build), '-j4'], stdout=log, stderr=subprocess.STDOUT, check=True)
    site = payload / 'Library/lib/python3.13/site-packages'
    package = site / '_argon2_cffi_bindings'
    shutil.copytree(source / 'src/_argon2_cffi_bindings', package, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.c', '*.cdef.txt'))
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    stub = package / ('_ffi.cpython-313-' + sdk_name + '.fwork')
    stub.write_text('Frameworks/Python-_argon2_cffi_bindings._ffi.framework/Python-_argon2_cffi_bindings._ffi\n')
    for prefix, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
        name = prefix + '_argon2_cffi_bindings._ffi'
        packaging.framework(name, build / '_ffi.so', payload / 'Frameworks', interpreter,
                            'iPhoneSimulator' if args.simulator else 'iPhoneOS')
        framework = payload / 'Frameworks' / (name + '.framework')
        (framework / (name + '.origin')).write_text('Library/lib/python3.13/site-packages/' + str(stub.relative_to(site)) + '\n')
        for license_path in [source / 'LICENSE', source / 'extras/libargon2/LICENSE']:
            shutil.copy2(license_path, framework / (license_path.parent.name + '-LICENSE'))
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site), '--version', '26.1.0', '--package', '_argon2_cffi_bindings']
                   + (['--simulator'] if args.simulator else []), check=True)


if __name__ == '__main__':
    main()
