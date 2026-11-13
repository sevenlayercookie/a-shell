#!/usr/bin/env python3
"""Build iOS JPEG and TIFF libraries used by PROJ's grid support."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    'libjpeg-turbo-3.0.4': ('https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.0.4/libjpeg-turbo-3.0.4.tar.gz', '99130559e7d62e8d695f2c0eaeef912c5828d5b84a0537dcb24c9678c9d5b76b'),
    'tiff-4.6.0': ('https://download.osgeo.org/libtiff/tiff-4.6.0.tar.gz', '88b3979e6d5c7e32b50d7ec72fb15af724f6ab2cbf7e10880c360a77e4b5d99a'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk = 'iphonesimulator' if args.simulator else 'iphoneos'
    prefix = base / ('proj-deps-' + platform)
    options = ['-G', 'Ninja', '-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_OSX_SYSROOT=' + sdk,
               '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_SYSTEM_PROCESSOR=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0',
               '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
               '-DCMAKE_INSTALL_PREFIX=' + str(prefix)]
    for name, (url, checksum) in SOURCES.items():
        archive = base / (name + '.tar.gz')
        if not archive.exists():
            urllib.request.urlretrieve(url, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
            raise SystemExit(name + ' source checksum mismatch')
        source = base / name
        if not source.exists():
            with tarfile.open(archive) as package:
                package.extractall(base, filter='data')
        if name.startswith('libjpeg'):
            patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/jpeg-ios-cmake.patch')]
            if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
                subprocess.run([*patch, '--forward'], cwd=source, check=True)
            elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
                raise SystemExit('JPEG CMake patch does not match source')
        build = base / (name + '-' + platform + '-build')
        if name.startswith('libjpeg'):
            extra = ['-DENABLE_SHARED=OFF', '-DENABLE_STATIC=ON', '-DWITH_TURBOJPEG=OFF']
        else:
            extra = ['-DBUILD_SHARED_LIBS=OFF', '-Dtiff-tools=OFF', '-Dtiff-tests=OFF',
                     '-Dtiff-contrib=OFF', '-Dtiff-docs=OFF', '-Djpeg=ON', '-Dzlib=ON',
                     '-DJPEG_INCLUDE_DIR=' + str(prefix / 'include'),
                     '-DJPEG_LIBRARY=' + str(prefix / 'lib/libjpeg.a')]
        with (base / (name + '-' + platform + '-build.log')).open('w') as log:
            subprocess.run(['cmake', '-S', str(source), '-B', str(build), *options, *extra],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['cmake', '--build', str(build), '--parallel', str(args.jobs)],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['cmake', '--install', str(build)], stdout=log, stderr=subprocess.STDOUT, check=True)
    print('Built JPEG and TIFF for ' + platform)


if __name__ == '__main__':
    main()
