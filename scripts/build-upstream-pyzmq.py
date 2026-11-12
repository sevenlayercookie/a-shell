#!/usr/bin/env python3
"""Build upstream's CFFI ZeroMQ backend, including CURVE support, for iOS."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ('pyzmq-27.3.0', 'https://files.pythonhosted.org/packages/e2/e1/ea46ab0d707219c098065a37d2add5b53d3b124241aa19429bcd0863e5b4/pyzmq-27.3.0.tar.gz', 'bbedb3d1d99babc625f1dd9d7438acefd442b36b75073fd6bc1ef7c0a4b96d56'),
    ('zeromq-4.3.5', 'https://github.com/zeromq/libzmq/releases/download/v4.3.5/zeromq-4.3.5.tar.gz', '6653ef5910f17954861fe72332e68b03ca6e4d9c7160eb3a8de5a5a913bfab43'),
    ('libsodium-1.0.22', 'https://download.libsodium.org/libsodium/releases/libsodium-1.0.22.tar.gz', 'adbdd8f16149e81ac6078a03aca6fc03b592b89ef7b5ed83841c086191be3349'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    for name, url, checksum in SOURCES:
        archive = base / url.rsplit('/', 1)[-1]
        if not archive.exists():
            urllib.request.urlretrieve(url, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
            raise SystemExit('ZeroMQ source checksum mismatch: ' + archive.name)
        if not (base / name).exists():
            with tarfile.open(archive) as package:
                package.extractall(base, filter='data')
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    python = base / 'venv/bin/python'
    source = base / 'pyzmq-27.3.0'
    sodium_source = base / 'libsodium-1.0.22'
    prefix = base / ('zmq-' + platform + '-install')
    sodium_build = base / ('sodium-' + platform)
    sodium_build.mkdir(parents=True, exist_ok=True)
    flags = ['-target', triple, '-isysroot', sdk]
    env = dict(os.environ, SDKROOT=sdk,
               CC=shlex.join(['xcrun', '--sdk', sdk_name, 'clang', *flags]),
               CXX=shlex.join(['xcrun', '--sdk', sdk_name, 'clang++', *flags]),
               CFLAGS=shlex.join(flags + ['-O2']), LDFLAGS=shlex.join(flags),
               PATH=str(python.parent) + ':' + os.environ['PATH'],
               PKG_CONFIG_LIBDIR=str(prefix / 'lib/pkgconfig'))
    with (base / ('sodium-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(sodium_source / 'configure'), '--host=aarch64-apple-darwin',
                        '--prefix=' + str(prefix), '--with-pic', '--disable-shared', '--enable-static'],
                       cwd=sodium_build, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['make', '-j' + str(args.jobs)], cwd=sodium_build, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['make', 'install'], cwd=sodium_build, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    project = base / ('pyzmq-' + platform + '-project')
    project.mkdir(parents=True, exist_ok=True)
    generated = project / '_cffi.c'
    with (base / ('pyzmq-' + platform + '-cffi.log')).open('w') as log:
        subprocess.run([str(python), str(source / 'buildutils/build_cffi.py'), str(generated)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    payload = base / platform
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    cmake = ['cmake_minimum_required(VERSION 3.20)', 'project(ashell_pyzmq C CXX)',
             'set(CMAKE_POLICY_VERSION_MINIMUM 3.5)', 'set(BUILD_SHARED OFF CACHE BOOL "" FORCE)',
             'set(BUILD_STATIC ON CACHE BOOL "" FORCE)', 'set(BUILD_TESTS OFF CACHE BOOL "" FORCE)',
             'set(WITH_DOC OFF CACHE BOOL "" FORCE)', 'set(WITH_DOCS OFF CACHE BOOL "" FORCE)',
             'set(ENABLE_CURVE ON CACHE BOOL "" FORCE)', 'set(WITH_LIBSODIUM ON CACHE BOOL "" FORCE)',
             'set(WITH_LIBSODIUM_STATIC ON CACHE BOOL "" FORCE)',
             'set(ENABLE_LIBSODIUM_RANDOMBYTES_CLOSE OFF CACHE BOOL "" FORCE)',
             'set(LIBZMQ_PEDANTIC OFF CACHE BOOL "" FORCE)', 'set(LIBZMQ_WERROR OFF CACHE BOOL "" FORCE)',
             'set(SODIUM_INCLUDE_DIRS "' + str(prefix / 'include') + '" CACHE PATH "" FORCE)',
             'set(SODIUM_LIBRARIES "' + str(prefix / 'lib/libsodium.a') + '" CACHE FILEPATH "" FORCE)',
             'include(CheckCXXSymbolExists)',
             'check_cxx_symbol_exists(kqueue "sys/types.h;sys/event.h;sys/time.h" HAVE_KQUEUE)',
             'if(HAVE_KQUEUE)', '  set(POLLER kqueue CACHE STRING "" FORCE)', 'endif()',
             'add_subdirectory("' + str(base / 'zeromq-4.3.5') + '" libzmq)',
             'add_library(_cffi SHARED "' + str(generated) + '")',
             'set_target_properties(_cffi PROPERTIES PREFIX "" SUFFIX ".so")',
             'target_compile_definitions(_cffi PRIVATE ZMQ_STATIC=1 _CFFI_NO_LIMITED_API)',
             'target_include_directories(_cffi PRIVATE "' + str(config) + '" "' + str(ROOT / 'cpython/Include')
             + '" "' + str(ROOT / 'build/python/deps/include') + '" "' + str(source / 'zmq/utils') + '")',
             'target_link_libraries(_cffi PRIVATE libzmq-static)',
             'target_link_options(_cffi PRIVATE "-F' + str(payload / 'Frameworks') + '" "SHELL:-framework Python"'
             + ' "-F' + str(deps) + '" "SHELL:-framework ios_system" "SHELL:-undefined error")']
    (project / 'CMakeLists.txt').write_text('\n'.join(cmake) + '\n')
    build = base / ('pyzmq-' + platform)
    with (base / ('pyzmq-' + platform + '-build.log')).open('w') as log:
        subprocess.run(['cmake', '-S', str(project), '-B', str(build), '-G', 'Ninja',
                        '-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_OSX_ARCHITECTURES=arm64',
                        '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0', '-DCMAKE_OSX_SYSROOT=' + sdk,
                        '-DCMAKE_BUILD_TYPE=Release'], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--build', str(build), '-j' + str(args.jobs)], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    site = payload / 'Library/lib/python3.13/site-packages'
    shutil.copytree(source / 'zmq', site / 'zmq', dirs_exist_ok=True)
    backend = site / 'zmq/backend/__init__.py'
    text = backend.read_text().replace('import platform\n', 'import platform\nimport sys\n')
    text = text.replace("if platform.python_implementation() == 'PyPy':",
                        "if platform.python_implementation() == 'PyPy' or sys.platform == 'ios':")
    backend.write_text(text)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    module = 'zmq.backend.cffi._cffi'
    stub = site / 'zmq/backend/cffi' / ('_cffi.cpython-313-' + sdk_name + '.fwork')
    stub.write_text('Frameworks/Python-' + module + '.framework/Python-' + module + '\n')
    for prefix_name, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
        name = prefix_name + module
        packaging.framework(name, build / '_cffi.so', payload / 'Frameworks', interpreter,
                            'iPhoneSimulator' if args.simulator else 'iPhoneOS')
        framework = payload / 'Frameworks' / (name + '.framework')
        (framework / (name + '.origin')).write_text('Library/lib/python3.13/site-packages/' + str(stub.relative_to(site)) + '\n')
        for directory in [source, sodium_source, base / 'zeromq-4.3.5']:
            license_path = directory / ('LICENSE.md' if directory == source else 'LICENSE')
            shutil.copy2(license_path, framework / (directory.name + '-LICENSE'))
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site), '--package', 'zmq', '--require', 'cffi>=1.17.1']
                   + (['--simulator'] if args.simulator else []), check=True)
    print('Packaged PyZMQ 27.3.0 with CURVE for ' + platform)


if __name__ == '__main__':
    main()
