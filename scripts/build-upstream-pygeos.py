#!/usr/bin/env python3
"""Build the upstream pygeos package for a-Shell's device or Simulator Python."""
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
VERSION = '0.14'
URL = 'https://files.pythonhosted.org/packages/ca/1f/07cda42b8a478ddfeb8b0bb328a10b2759ae75f8a60026238c0e33c9ef80/pygeos-0.14.tar.gz'
SHA256 = '30fbc17f64844200b85133b885fcfb65541b8779531f6ef4f8fe467d3fba7623'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--relink', action='store_true', help='Reuse compiled objects and relink framework libraries')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / f'pygeos-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('pygeos source checksum mismatch')
    source = base / f'pygeos-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    # Apply the upstream a-Shell port, including its NumPy and iOS changes.
    for src, dst in [('setup_pygeos.py', 'setup.py'), ('pygeos_io.py', 'pygeos/io.py'),
                     ('pygeos_versioneer.py', 'versioneer.py'), ('pygeos_src_ufuncs.c', 'src/ufuncs.c'),
                     ('pygeos_geos.pyx', 'pygeos/_geos.pyx')]:
        shutil.copy2(ROOT / 'cpython/packages' / src, source / dst)
    setup = source / 'setup.py'
    text = setup.read_text().replace('from pkg_resources import parse_version',
                                     'from packaging.version import parse as parse_version')
    setup.write_text(text)
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
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system', '-framework', 'libgeos_c', '-lc++'])
    geos = base / ('geos-' + platform + '-install')
    env = dict(os.environ, GEOS_INCLUDE_PATH=str(geos / 'include'), GEOS_LIBRARY_PATH=str(geos / 'lib'), SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang', CXX=f'xcrun --sdk {sdk_name} clang++', CFLAGS=flags, CPPFLAGS=flags,
               CXXFLAGS=flags + ' -std=c++17', IOS_NUMPY_INCLUDE=str(numpy_include),
               IOS_CYTHON_INCLUDE=str(base / platform / 'Library/lib/python3.13/site-packages'),
               LDSHARED=linker, LDCXXSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / ('pygeos-' + platform + '-build')
    if args.relink:
        for binary in build.glob('lib.*/**/*.so'):
            binary.unlink()
    else:
        for source_file in source.rglob('*.pyx'):
            source_file.touch()
    dist = build / 'dist'
    with (base / ('pygeos-' + platform + '-build.log')).open('w') as log:
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
