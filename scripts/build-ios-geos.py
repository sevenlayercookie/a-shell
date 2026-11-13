#!/usr/bin/env python3
"""Build the GEOS geometry libraries for a-Shell on iOS and the Simulator."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://github.com/libgeos/geos/releases/download/3.11.0/geos-3.11.0.tar.bz2'
SHA256 = '79ab8cabf4aa8604d161557b52e3e4d84575acdc0d08cb09ab3f7aaefa4d858a'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk = 'iphonesimulator' if args.simulator else 'iphoneos'
    archive = base / 'geos-3.11.0.tar.bz2'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('GEOS source checksum mismatch')
    source = base / 'geos-3.11.0'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    build = base / ('geos-' + platform + '-build')
    install = base / ('geos-' + platform + '-install')
    log_path = base / ('geos-' + platform + '-build.log')
    with log_path.open('w') as log:
        subprocess.run(['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
                        '-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_OSX_SYSROOT=' + sdk,
                        '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0',
                        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF', '-DBUILD_SHARED_LIBS=ON',
                        '-DCMAKE_INSTALL_PREFIX=' + str(install)], stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--build', str(build), '--parallel', str(args.jobs)], stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--install', str(build)], stdout=log, stderr=subprocess.STDOUT, check=True)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    frameworks = base / platform / 'Frameworks'
    expected = 'IOSSIMULATOR' if args.simulator else 'IOS'
    for name in ('libgeos', 'libgeos_c'):
        binary = (install / 'lib' / (name + '.dylib')).resolve()
        info = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], text=True)
        if 'platform ' + expected not in info:
            raise SystemExit('Unexpected GEOS Mach-O platform: ' + str(binary))
        packaging.framework(name, binary, frameworks, platform='iPhoneSimulator' if args.simulator else 'iPhoneOS')
        destination = frameworks / (name + '.framework')
        shutil.copy2(source / 'COPYING', destination / 'LICENSE-GEOS.txt')
        if name == 'libgeos_c':
            target = destination / name
            dependencies = subprocess.check_output(['xcrun', 'otool', '-L', str(target)], text=True).splitlines()[1:]
            for line in dependencies:
                old = line.strip().split(' ', 1)[0]
                if Path(old).name.startswith('libgeos.'):
                    subprocess.run(['xcrun', 'install_name_tool', '-change', old,
                                    '@rpath/libgeos.framework/libgeos', str(target)], check=True)
    print('Packaged GEOS 3.11.0 for ' + platform)


if __name__ == '__main__':
    main()
