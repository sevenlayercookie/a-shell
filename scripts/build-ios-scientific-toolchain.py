#!/usr/bin/env python3
"""Build static OpenBLAS/LAPACK and Flang runtime for native iOS packages."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
LLVM_REVISION = '392dfff97d29b59d77e5cac6d4b6ef2585fe7117'
BLAS_URL = 'https://github.com/OpenMathLib/OpenBLAS/archive/refs/tags/v0.3.34.tar.gz'
BLAS_SHA256 = 'cd7e129868320cc2d033afa920e31202dfe0b8066a5b66661900ccc0f197dfed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--flang', type=Path, default=Path('/opt/homebrew/opt/flang/bin/flang'))
    parser.add_argument('--llvm', type=Path, default=Path('/opt/homebrew/opt/llvm'))
    args = parser.parse_args()
    if not args.flang.is_file():
        raise SystemExit('Install Flang 23.1.5 or pass --flang')
    version = subprocess.check_output([str(args.flang), '--version'], text=True)
    if '23.1.5' not in version:
        raise SystemExit('This toolchain is pinned to Flang 23.1.5')
    base = ROOT / 'build/upstream-parity'
    base.mkdir(parents=True, exist_ok=True)
    source = base / 'llvm-project'
    if not source.exists():
        subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout',
                        'https://github.com/llvm/llvm-project.git', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'sparse-checkout', 'set', 'flang-rt', 'runtimes',
                        'cmake', 'llvm/cmake', 'llvm/include/llvm/Config', 'llvm/include/llvm/Support',
                        'flang/include', 'flang/cmake', 'flang/lib/Decimal', 'libc/shared', 'libc/cmake'], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', LLVM_REVISION], check=True)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != LLVM_REVISION:
        raise SystemExit('Unexpected LLVM source revision: ' + revision)
    patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/flang-runtime-ios.patch')]
    if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
        subprocess.run([*patch, '--forward'], cwd=source, check=True)
    elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
        raise SystemExit('Flang runtime patch does not match the source')
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    suffix = 'simulator' if args.simulator else 'ios'
    runtime = base / ('flang-runtime-' + suffix)
    command = ['cmake', '-S', str(source / 'runtimes'), '-B', str(runtime), '-G', 'Ninja',
               '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_SYSTEM_NAME=iOS',
               '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0',
               '-DCMAKE_OSX_SYSROOT=' + sdk, '-DCMAKE_Fortran_COMPILER=' + str(args.flang),
               '-DCMAKE_Fortran_COMPILER_TARGET=' + triple, '-DLLVM_ENABLE_RUNTIMES=flang-rt',
               '-DLLVM_BINARY_DIR=' + str(args.llvm), '-DLLVM_DIR=' + str(args.llvm / 'lib/cmake/llvm'),
               '-DLLVM_INCLUDE_TESTS=OFF', '-DFLANG_RT_INCLUDE_TESTS=OFF',
               '-DFLANG_RT_ENABLE_STATIC=ON', '-DFLANG_RT_ENABLE_SHARED=OFF']
    with (base / ('flang-runtime-' + suffix + '-build.log')).open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--build', str(runtime), '-j' + str(args.jobs)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    libraries = runtime / 'lib/clang/23/lib/ios'
    for name in ['libFortranRuntime.a', 'libFortranDecimal.a']:
        link = libraries / name
        link.unlink(missing_ok=True)
        link.symlink_to('libflang_rt.runtime.a')
    archive = base / 'OpenBLAS-0.3.34.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(BLAS_URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != BLAS_SHA256:
        raise SystemExit('OpenBLAS source checksum mismatch')
    # Separate source trees avoid mixing device and Simulator object files.
    parent = base / ('openblas-' + suffix + '-source')
    blas = parent / 'OpenBLAS-0.3.34'
    if not blas.exists():
        parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as package:
            package.extractall(parent, filter='data')
    cc = shlex.join(['xcrun', '--sdk', sdk_name, 'clang', '-target', triple, '-isysroot', sdk])
    fc = shlex.join([str(args.flang), '-target', triple, '--sysroot=' + sdk])
    options = ['TARGET=ARMV8', 'BINARY=64', 'OSNAME=Darwin', 'HOSTCC=xcrun --sdk macosx clang',
               'CC=' + cc, 'FC=' + fc, 'AR=/usr/bin/ar', 'RANLIB=/usr/bin/ranlib',
               'F_COMPILER=FLANGNEW', 'CROSS=1', 'USE_THREAD=0', 'NO_AFFINITY=1',
               'NO_SHARED=1', 'DYNAMIC_ARCH=0', 'NUM_THREADS=1']
    prefix = base / ('openblas-' + suffix + '-install')
    env = dict(os.environ, ASHELL_FLANG=str(args.flang))
    with (base / ('openblas-' + suffix + '-build.log')).open('w') as log:
        subprocess.run(['make', '-j' + str(args.jobs), *options, 'libs', 'netlib'], cwd=blas,
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['make', *options, 'PREFIX=' + str(prefix), 'install'], cwd=blas,
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == '__main__':
    main()
