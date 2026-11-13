#!/usr/bin/env python3
"""Build the upstream cvxopt package for a-Shell's device or Simulator Python."""
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
VERSION = '1.3.3'
URL = 'https://files.pythonhosted.org/packages/3f/b7/0e6ecb45c152029310a0cf7594e518f3591b363d4e06638526efc7872cb8/cvxopt-1.3.3.tar.gz'
SHA256 = '8059cef41f1f115c87bc9b75fec9f86db95e7f0afcf03a52d619ba433e443bcb'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--relink', action='store_true', help='Reuse compiled objects and relink framework libraries')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / f'cvxopt-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('cvxopt source checksum mismatch')
    source = base / f'cvxopt-{VERSION}'
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
    # Match the checksum-pinned SuiteSparse version used by CVXOPT's own builds.
    suite_archive = base / 'SuiteSparse-7.11.0.tar.gz'
    if not suite_archive.exists():
        urllib.request.urlretrieve('https://codeload.github.com/DrTimothyAldenDavis/SuiteSparse/tar.gz/refs/tags/v7.11.0', suite_archive)
    if hashlib.sha256(suite_archive.read_bytes()).hexdigest() != '93ed4c4e546a49fc75884c3a8b807d5af4a91e39d191fbbc60a07380b12a35d1':
        raise SystemExit('SuiteSparse source checksum mismatch')
    suite = base / 'SuiteSparse-7.11.0'
    if not suite.exists():
        with tarfile.open(suite_archive) as package:
            package.extractall(base, filter='data')
    shutil.copy2(suite / 'LICENSE.txt', source / 'src/python/LICENSE-SuiteSparse.txt')
    for component in ('AMD', 'CHOLMOD', 'COLAMD', 'UMFPACK', 'SuiteSparse_config'):
        license_file = suite / component / 'Doc/License.txt'
        if license_file.exists():
            shutil.copy2(license_file, source / ('src/python/LICENSE-' + component + '.txt'))
    shutil.copy2(base / 'fftw-3.3.11/COPYING', source / 'src/python/LICENSE-FFTW.txt')
    openblas = base / ('openblas-simulator-install' if args.simulator else 'openblas-ios-install') / 'lib'
    fftw = base / ('fftw-simulator-install' if args.simulator else 'fftw-device-install')
    runtime = base / ('flang-runtime-simulator' if args.simulator else 'flang-runtime-ios') / 'lib/clang/23/lib/ios/libflang_rt.runtime.a'
    env = dict(os.environ, SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang',
               CFLAGS=flags, CPPFLAGS=flags, IOS_NUMPY_INCLUDE=str(numpy_include),
               LDSHARED=linker, LDCXXSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name,
               CVXOPT_BLAS_LIB='openblas', CVXOPT_LAPACK_LIB='openblas',
               CVXOPT_BLAS_LIB_DIR=str(openblas), CVXOPT_LAPACK_LIB_DIR=str(openblas),
               CVXOPT_BUILD_FFTW='1', CVXOPT_FFTW_LIB_DIR=str(fftw / 'lib'),
               CVXOPT_FFTW_INC_DIR=str(fftw / 'include'), CVXOPT_SUITESPARSE_SRC_DIR=os.path.relpath(suite, source),
               CVXOPT_BLAS_EXTRA_LINK_ARGS=str(runtime) + ';-lc++')
    # Recompute the manifest: SuiteSparse paths depend on this checkout.
    (source / 'cvxopt.egg-info/SOURCES.txt').unlink(missing_ok=True)
    build = base / ('cvxopt-' + platform + '-build')
    if args.relink:
        for binary in build.glob('lib.*/**/*.so'):
            binary.unlink()
    else:
        for source_file in source.rglob('*.pyx'):
            source_file.touch()
    dist = build / 'dist'
    with (base / ('cvxopt-' + platform + '-build.log')).open('w') as log:
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
