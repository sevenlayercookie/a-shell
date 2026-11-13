#!/usr/bin/env python3
"""Build the upstream cartopy package for a-Shell's device or Simulator Python."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.26.0'
URL = 'https://files.pythonhosted.org/packages/a3/a2/ae348fc400e73fd5b589919ab5f13aece4feb31cd5cc78ab54773018563b/cartopy-0.26.0.tar.gz'
SHA256 = 'b87a35835f30333760cc46194bd90b6a4958d12f488f50131d4c4c0962ad9c3c'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--relink', action='store_true', help='Reuse compiled objects and relink framework libraries')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / f'cartopy-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('cartopy source checksum mismatch')
    source = base / f'cartopy-{VERSION}'
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
    linker = shlex.join(['xcrun', '--sdk', sdk_name, 'clang++', '-target', triple, '-isysroot', sdk,
                         '-dynamiclib', '-undefined', 'error', '-F' + str(base / platform / 'Frameworks'),
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system', '-lc++'])
    env = dict(os.environ, FORCE_CYTHON='1', SETUPTOOLS_SCM_PRETEND_VERSION_FOR_CARTOPY='0.26.0', SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang', CXX=f'xcrun --sdk {sdk_name} clang++', CFLAGS=flags, CPPFLAGS=flags,
               CXXFLAGS=flags + ' -std=c++17', IOS_NUMPY_INCLUDE=str(numpy_include),
               IOS_CYTHON_INCLUDE=str(base / platform / 'Library/lib/python3.13/site-packages'),
               LDSHARED=linker, LDCXXSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / ('cartopy-' + platform + '-build')
    if args.relink:
        for binary in build.glob('lib.*/**/*.so'):
            binary.unlink()
    else:
        for source_file in source.rglob('*.pyx'):
            source_file.touch()
    dist = build / 'dist'
    with (base / ('cartopy-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(python), str(ROOT / 'scripts/run-ios-setuptools.py'), 'build', '--build-base', str(build),
                        'build_ext', *([] if args.relink else ['--force']), '-j2', 'bdist_wheel', '--plat-name', 'ios_15_0_arm64_' + sdk_name,
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
