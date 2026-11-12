#!/usr/bin/env python3
"""Build the upstream wordcloud package for a-Shell's device or Simulator Python."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = '1.9.6'
URL = 'https://files.pythonhosted.org/packages/6f/04/a3d3c4b94a35586ddb97c6a3c508913159161cd558b34f315b382b924bf7/wordcloud-1.9.6.tar.gz'
SHA256 = 'df17c468ff903bd0aba4f87c6540745d13a4931220dd4937cb363ad85a4771b9'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / f'wordcloud-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('wordcloud source checksum mismatch')
    source = base / f'wordcloud-{VERSION}'
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
    numpy_prefix = base / ('numpy-simulator-install' if args.simulator else 'numpy-ios-install')
    numpy_include = next(numpy_prefix.rglob('site-packages/numpy/_core/include'))
    subprocess.run([str(python), str(ROOT / 'scripts/prepare-cython-reentry.py'), '--python', str(python)], check=True)
    flags = shlex.join(['-target', triple, '-isysroot', sdk, '-I' + str(config),
                        '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'), '-O2', '-I' + str(numpy_include), '-DCYTHON_PEP489_MULTI_PHASE_INIT=1',
                        '-DCYTHON_USE_MODULE_STATE=1', '-DCYTHON_USE_TYPE_SPECS=1', '-DCYTHON_USE_DICT_VERSIONS=0', '-DCYTHON_USE_PYTYPE_LOOKUP=0'])
    linker = shlex.join(['xcrun', '--sdk', sdk_name, 'clang', '-target', triple, '-isysroot', sdk,
                         '-dynamiclib', '-undefined', 'error', '-F' + str(base / platform / 'Frameworks'),
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system'])
    env = dict(os.environ, SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang', CFLAGS=flags, CPPFLAGS=flags,
               LDSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / ('wordcloud-' + platform + '-build')
    for source_file in source.rglob('*.pyx'):
        source_file.touch()
    dist = build / 'dist'
    with (base / ('wordcloud-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(python), 'setup.py', 'build', '--build-base', str(build),
                        'build_ext', '--force', 'bdist_wheel', '--plat-name', 'ios_15_0_arm64_' + sdk_name,
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
