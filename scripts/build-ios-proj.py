#!/usr/bin/env python3
"""Build PROJ with its database, TIFF grid support and upstream curl framework."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    'proj-9.4.1.tar.gz': ('https://download.osgeo.org/proj/proj-9.4.1.tar.gz', 'ffe20170ee2b952207adf8a195e2141eab12cda181e49fdeb54425d98c7171d7'),
    'curl-8.1.2.tar.xz': ('https://curl.se/download/curl-8.1.2.tar.xz', '31b1118eb8bfd43cd95d9a3f146f814ff874f6ed3999b29d94f4d1e7dbac5ef6'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    for name, (url, checksum) in SOURCES.items():
        archive = base / name
        if not archive.exists():
            urllib.request.urlretrieve(url, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
            raise SystemExit(name + ' source checksum mismatch')
        directory = base / name.removesuffix('.tar.gz').removesuffix('.tar.xz')
        if not directory.exists():
            with tarfile.open(archive) as package:
                package.extractall(base, filter='data')
    frameworks = base / platform / 'Frameworks'
    artifacts = ROOT / 'xcfs/.build/artifacts/xcfs'
    for name in ('curl_ios', 'openssl', 'libssh2'):
        xcframework = artifacts / name / (name + '.xcframework')
        if not xcframework.exists():
            raise SystemExit('Resolve xcfs Swift packages before building PROJ: ' + str(xcframework))
        slice_name = 'ios-arm64_x86_64-simulator' if args.simulator else ('ios-arm64_arm64e' if name == 'libssh2' else 'ios-arm64')
        src = xcframework / slice_name / (name + '.framework')
        dst = frameworks / (name + '.framework')
        shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        binary = dst / name
        arch = subprocess.check_output(['xcrun', 'lipo', '-archs', str(binary)], text=True).split()
        if 'arm64' not in arch:
            raise SystemExit('No arm64 slice in ' + str(binary))
        if len(arch) > 1:
            thin = binary.with_name(name + '.thin')
            subprocess.run(['xcrun', 'lipo', str(binary), '-thin', 'arm64', '-output', str(thin)], check=True)
            thin.replace(binary)
    source = base / 'proj-9.4.1'
    deps = base / ('proj-deps-' + platform)
    build = base / ('proj-' + platform + '-build')
    install = base / ('proj-' + platform + '-install')
    curl = frameworks / 'curl_ios.framework/curl_ios'
    sqlite = Path(sdk) / 'usr/lib/libsqlite3.tbd'
    options = ['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
               '-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_OSX_SYSROOT=' + sdk_name,
               '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0',
               '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_TESTING=OFF', '-DBUILD_APPS=OFF',
               '-DBUILD_SHARED_LIBS=ON', '-DENABLE_TIFF=ON', '-DENABLE_CURL=ON',
               '-DCMAKE_INSTALL_PREFIX=' + str(install), '-DEXE_SQLITE3=/usr/bin/sqlite3',
               '-DSQLite3_INCLUDE_DIR=' + sdk + '/usr/include', '-DSQLite3_LIBRARY=' + str(sqlite),
               '-DTIFF_INCLUDE_DIR=' + str(deps / 'include'), '-DTIFF_LIBRARY=' + str(deps / 'lib/libtiff.a'),
               '-DCURL_INCLUDE_DIR=' + str(base / 'curl-8.1.2/include'), '-DCURL_LIBRARY=' + str(curl),
               '-DCMAKE_CXX_STANDARD_LIBRARIES=' + str(deps / 'lib/libjpeg.a') + ' -lz']
    with (base / ('proj-' + platform + '-build.log')).open('w') as log:
        subprocess.run(options, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--build', str(build), '--parallel', str(args.jobs)], stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--install', str(build)], stdout=log, stderr=subprocess.STDOUT, check=True)
    binary = (install / 'lib/libproj.dylib').resolve()
    info = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], text=True)
    expected = 'IOSSIMULATOR' if args.simulator else 'IOS'
    if 'platform ' + expected not in info:
        raise SystemExit('Unexpected PROJ Mach-O platform')
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    packaging.framework('libproj', binary, frameworks, platform='iPhoneSimulator' if args.simulator else 'iPhoneOS')
    bundle = frameworks / 'libproj.framework'
    for src, name in [(source / 'COPYING', 'LICENSE-PROJ.txt'),
                      (base / 'tiff-4.6.0/LICENSE.md', 'LICENSE-TIFF.txt'),
                      (base / 'libjpeg-turbo-3.0.4/LICENSE.md', 'LICENSE-JPEG.txt'),
                      (base / 'libjpeg-turbo-3.0.4/README.ijg', 'LICENSE-IJG.txt')]:
        shutil.copy2(src, bundle / name)
    library = base / platform / 'Library'
    shutil.copytree(install / 'share/proj', library / 'share/proj', dirs_exist_ok=True)
    print('Packaged PROJ 9.4.1, grids database and network support for ' + platform)


if __name__ == '__main__':
    main()
