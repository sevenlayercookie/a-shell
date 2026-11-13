#!/usr/bin/env python3
"""Build checksum-pinned static FFTW in all three precisions with pthreads."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://fftw.org/fftw-3.3.11.tar.gz'
SHA256 = '5630c24cdeb33b131612f7eb4b1a9934234754f9f388ff8617458d0be6f239a1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / 'fftw-3.3.11.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('FFTW source checksum mismatch')
    source = base / 'fftw-3.3.11'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    prefix = base / ('fftw-' + platform + '-install')
    env = dict(os.environ, CC=shlex.join(['xcrun', '--sdk', sdk_name, 'clang', '-target', triple]),
               CFLAGS=shlex.join(['-isysroot', sdk, '-O2', '-fPIC']),
               LDFLAGS=shlex.join(['-isysroot', sdk]), AR='/usr/bin/ar', RANLIB='/usr/bin/ranlib')
    for precision in ['double', 'single', 'long-double']:
        build = base / ('fftw-' + platform + '-' + precision)
        build.mkdir(exist_ok=True)
        configure = [str(source / 'configure'), '--host=aarch64-apple-darwin',
                     '--prefix=' + str(prefix), '--enable-static', '--disable-shared',
                     '--enable-threads', '--disable-fortran', '--disable-mpi']
        if precision == 'single':
            configure.append('--enable-float')
        elif precision == 'long-double':
            configure.append('--enable-long-double')
        with (base / ('fftw-' + platform + '-' + precision + '.log')).open('w') as log:
            subprocess.run(configure, cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['make', '-j2'], cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['make', 'install'], cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    licenses = prefix / 'licenses'
    licenses.mkdir(exist_ok=True)
    import shutil
    shutil.copy2(source / 'COPYING', licenses / 'FFTW-COPYING')
    print('Built static FFTW for ' + platform)


if __name__ == '__main__':
    main()
