#!/usr/bin/env python3
"""Build the upstream pyproj package for a-Shell's device or Simulator Python."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = '3.8.0'
URL = 'https://files.pythonhosted.org/packages/c8/29/6598570c90cbfc84ddefc3ccac4aa412bf51a527d72c74cc4fe64a5e6f24/pyproj-3.8.0.tar.gz'
SHA256 = 'efa59725bba68bf97fa808b61302df32934acdceb6a5c92a8dd0e71dc266a876'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--relink', action='store_true', help='Reuse compiled objects and relink framework libraries')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / f'pyproj-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('pyproj source checksum mismatch')
    source = base / f'pyproj-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/pyproj-ios-link.patch')]
    if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
        subprocess.run([*patch, '--forward'], cwd=source, check=True)
    elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
        raise SystemExit('QuTiP iOS patch does not match source')
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
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system', '-framework', 'libproj', '-lc++'])
    proj = base / ('proj-' + platform + '-install')
    env = dict(os.environ, PROJ_DIR=str(proj), PROJ_VERSION='9.4.1', SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang', CXX=f'xcrun --sdk {sdk_name} clang++', CFLAGS=flags, CPPFLAGS=flags,
               CXXFLAGS=flags + ' -std=c++17', IOS_NUMPY_INCLUDE=str(numpy_include),
               IOS_CYTHON_INCLUDE=str(base / platform / 'Library/lib/python3.13/site-packages'),
               LDSHARED=linker, LDCXXSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / ('pyproj-' + platform + '-build')
    if args.relink:
        for binary in build.glob('lib.*/**/*.so'):
            binary.unlink()
    else:
        for source_file in source.rglob('*.pyx'):
            source_file.touch()
    dist = build / 'dist'
    with (base / ('pyproj-' + platform + '-build.log')).open('w') as log:
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
    # pyproj discovers its read-only, bundled database relative to its package.
    site = base / platform / 'Library/lib/python3.13/site-packages'
    shutil.copytree(proj / 'share/proj', site / 'pyproj/proj_dir/share/proj', dirs_exist_ok=True)


if __name__ == '__main__':
    main()
