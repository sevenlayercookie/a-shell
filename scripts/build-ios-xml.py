#!/usr/bin/env python3
"""Build static XML/XSLT libraries so lxml interpreters own separate callbacks."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ('libxml2', '2.9.13', '276130602d12fe484ecc03447ee5e759d0465558fbc9d6bd144e3745306ebf0e'),
    ('libxslt', '1.1.35', '8247f33e9a872c6ac859aa45018bc4c4d00b97e2feac9eebc10c93ce1f34dd79'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    platform = 'simulator' if args.simulator else 'device'
    sdk = Path(subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip())
    prefix = base / ('xml-' + platform + '-install')
    lzma_include = ROOT / 'build/python/deps/include/lzma'
    common = ['-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_SYSTEM_NAME=iOS',
              '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0',
              '-DCMAKE_OSX_SYSROOT=' + str(sdk), '-DBUILD_SHARED_LIBS=OFF', '-DCMAKE_MACOSX_BUNDLE=OFF',
              '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_PREFIX_PATH=' + str(prefix),
              '-DLibXml2_DIR=' + str(prefix / 'lib/cmake/libxml2-2.9.13'),
              '-DIconv_INCLUDE_DIR=' + str(sdk / 'usr/include'),
              '-DIconv_LIBRARY=' + str(sdk / 'usr/lib/libiconv.2.tbd'),
              '-DZLIB_INCLUDE_DIR=' + str(sdk / 'usr/include'),
              '-DZLIB_LIBRARY=' + str(sdk / 'usr/lib/libz.1.tbd'),
              '-DLIBLZMA_INCLUDE_DIR=' + str(lzma_include),
              '-DLIBLZMA_LIBRARY=' + str(sdk / 'usr/lib/liblzma.5.tbd')]
    for name, version, checksum in SOURCES:
        archive = base / f'{name}-{version}.tar.xz'
        if not archive.exists():
            series = '.'.join(version.split('.')[:2])
            urllib.request.urlretrieve(f'https://download.gnome.org/sources/{name}/{series}/{archive.name}', archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
            raise SystemExit('XML source checksum mismatch: ' + str(archive))
        source = base / f'{name}-{version}'
        if not source.exists():
            with tarfile.open(archive) as package:
                package.extractall(base, filter='data')
        if name == 'libxml2':
            patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/libxml2-cmake-version.patch')]
            if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
                subprocess.run([*patch, '--forward'], cwd=source, check=True)
            elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
                raise SystemExit('libxml2 version patch does not match the source')
        build = base / (name + '-' + platform)
        options = (['-DLIBXML2_WITH_PYTHON=OFF', '-DLIBXML2_WITH_PROGRAMS=OFF', '-DLIBXML2_WITH_TESTS=OFF']
                   if name == 'libxml2' else ['-DLIBXSLT_WITH_PYTHON=OFF', '-DLIBXSLT_WITH_TESTS=OFF'])
        with (base / (name + '-' + platform + '-build.log')).open('w') as log:
            subprocess.run(['cmake', '-S', str(source), '-B', str(build), *common, *options],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['cmake', '--build', str(build), '-j' + str(args.jobs)],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['cmake', '--install', str(build)], stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == '__main__':
    main()
