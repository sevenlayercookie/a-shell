#!/usr/bin/env python3
"""Build both PyCryptodome namespaces for a-Shell's iOS Python runtime."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = '3.23.0'
URL = 'https://files.pythonhosted.org/packages/8e/a6/8452177684d5e906854776276ddd34eca30d1b1e15aa1ee9cefc289a33f5/pycryptodome-3.23.0.tar.gz'
SHA256 = '447700a657182d60338bab09fdb27518f8856aecd80ae4c6bdddb67ff5da44ef'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    base.mkdir(parents=True, exist_ok=True)
    archive = base / f'pycryptodome-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('PyCryptodome source checksum mismatch')
    source = base / f'pycryptodome-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    python = base / 'venv/bin/python'
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    flags = f'-target {triple} -isysroot {sdk} -I{config} -I{ROOT}/cpython/Include -I{ROOT}/build/python/deps/include -O2'
    linker = (f'xcrun --sdk {sdk_name} clang -target {triple} -isysroot {sdk} '
              f'-dynamiclib -undefined error -F{base}/{platform}/Frameworks -framework Python '
              f'-F{deps} -framework ios_system')
    env = dict(os.environ, PATH=str(python.parent) + ':' + os.environ['PATH'],
               CC=f'xcrun --sdk {sdk_name} clang', CXX=f'xcrun --sdk {sdk_name} clang++',
               CFLAGS=flags, CPPFLAGS=flags, CXXFLAGS=flags, LDSHARED=linker,
               _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    marker = source / '.separate_namespace'
    try:
        for namespace in ['Crypto', 'Cryptodome']:
            if namespace == 'Cryptodome':
                marker.touch()
            else:
                marker.unlink(missing_ok=True)
            build = base / (namespace.lower() + '-' + platform + '-build')
            with (base / (namespace.lower() + '-' + platform + '-build.log')).open('w') as log:
                subprocess.run([str(python), 'setup.py', 'build', '--build-base', str(build),
                                'build_ext', '-j' + str(args.jobs)], cwd=source, env=env,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
    finally:
        marker.unlink(missing_ok=True)
    subprocess.run([str(python), str(ROOT / 'scripts/package-upstream-pycryptodome.py')]
                   + (['--simulator'] if args.simulator else []), check=True)


if __name__ == '__main__':
    main()
