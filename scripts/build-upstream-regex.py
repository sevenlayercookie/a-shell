#!/usr/bin/env python3
"""Build the upstream regex package for a-Shell's device or Simulator Python."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = '2026.11.9'
URL = 'https://files.pythonhosted.org/packages/61/27/a5afeb952577b84ee5fe48b8b9ce47ae662dbb69cc5b76c28eff98f83b1e/regex-2026.11.9.tar.gz'
SHA256 = '316a70fbd70e999c9664681cb0eb5b4982b2cc0f623c7c86a8a112e1bd4c6277'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / f'regex-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('regex source checksum mismatch')
    source = base / f'regex-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    platform = 'simulator' if args.simulator else 'device'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    python = base / 'venv/bin/python'
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    flags = shlex.join(['-target', triple, '-isysroot', sdk, '-I' + str(config),
                        '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'), '-O2'])
    linker = shlex.join(['xcrun', '--sdk', sdk_name, 'clang', '-target', triple, '-isysroot', sdk,
                         '-dynamiclib', '-undefined', 'error', '-F' + str(base / platform / 'Frameworks'),
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system'])
    env = dict(os.environ, SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang', CFLAGS=flags, CPPFLAGS=flags,
               LDSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / ('regex-' + platform + '-build')
    dist = build / 'dist'
    with (base / ('regex-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(python), 'setup.py', 'build', '--build-base', str(build),
                        'bdist_wheel', '--plat-name', 'ios_15_0_arm64_' + sdk_name,
                        '--dist-dir', str(dist)], cwd=source, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    wheel = next(dist.glob('*.whl'))
    subprocess.run([str(python), str(ROOT / 'scripts/install-ios-python-wheel.py'), str(wheel),
                    '--sha256', hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    '--library', str(base / platform / 'Library'),
                    '--frameworks', str(base / platform / 'Frameworks')]
                   + (['--simulator'] if args.simulator else []), check=True)


if __name__ == '__main__':
    main()
