#!/usr/bin/env python3
"""Build GDAL for a-Shell with GEOS, PROJ, SQLite, TIFF and curl support."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://download.osgeo.org/gdal/3.9.3/gdal-3.9.3.tar.gz'
SHA256 = 'f293d8ccc6b98f617db88f8593eae37f7e4b32d49a615b2cba5ced12c7bebdae'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    archive = base / 'gdal-3.9.3.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('GDAL source checksum mismatch')
    source = base / 'gdal-3.9.3'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/gdal-ios-libpng.patch')]
    if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
        subprocess.run([*patch, '--forward'], cwd=source, check=True)
    elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
        raise SystemExit('GDAL libpng iOS patch does not match source')
    build = base / ('gdal-' + platform + '-build')
    install = base / ('gdal-' + platform + '-install')
    frameworks = base / platform / 'Frameworks'
    deps = base / ('proj-deps-' + platform)
    geos = base / ('geos-' + platform + '-install')
    proj = base / ('proj-' + platform + '-install')
    options = ['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
               '-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_OSX_SYSROOT=' + sdk_name,
               '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0',
               '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(install),
               '-DBUILD_SHARED_LIBS=ON', '-DBUILD_TESTING=OFF', '-DBUILD_APPS=OFF',
               '-DGDAL_FIND_PACKAGE_PROJ_MODE=MODULE', '-DPROJ_INCLUDE_DIR=' + str(proj / 'include'),
               '-DPROJ_LIBRARY=' + str(frameworks / 'libproj.framework/libproj'),
               '-DGEOS_CONFIG=' + str(geos / 'bin/geos-config'),
               '-DGEOS_INCLUDE_DIR=' + str(geos / 'include'),
               '-DGEOS_LIBRARY=' + str(frameworks / 'libgeos_c.framework/libgeos_c'),
               '-DTIFF_INCLUDE_DIR=' + str(deps / 'include'), '-DTIFF_LIBRARY=' + str(deps / 'lib/libtiff.a'),
               '-DJPEG_INCLUDE_DIR=' + str(deps / 'include'), '-DJPEG_LIBRARY=' + str(deps / 'lib/libjpeg.a'),
               '-DSQLite3_INCLUDE_DIR=' + sdk + '/usr/include', '-DSQLite3_LIBRARY=' + sdk + '/usr/lib/libsqlite3.tbd',
               '-DCURL_INCLUDE_DIR=' + str(base / 'curl-8.1.2/include'),
               '-DCURL_LIBRARY=' + str(frameworks / 'curl_ios.framework/curl_ios'),
               '-DCMAKE_CXX_STANDARD_LIBRARIES=' + str(deps / 'lib/libjpeg.a') + ' -lz']
    with (base / ('gdal-' + platform + '-build.log')).open('w') as log:
        subprocess.run(options, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--build', str(build), '--parallel', str(args.jobs)], stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['cmake', '--install', str(build)], stdout=log, stderr=subprocess.STDOUT, check=True)
    binary = (install / 'lib/libgdal.dylib').resolve()
    expected = 'IOSSIMULATOR' if args.simulator else 'IOS'
    info = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], text=True)
    if 'platform ' + expected not in info:
        raise SystemExit('Unexpected GDAL Mach-O platform')
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    packaging.framework('libgdal', binary, frameworks, platform='iPhoneSimulator' if args.simulator else 'iPhoneOS')
    bundle = frameworks / 'libgdal.framework'
    shutil.copy2(source / 'LICENSE.TXT', bundle / 'LICENSE-GDAL.txt')
    shutil.copytree(install / 'share/gdal', base / platform / 'Library/share/gdal', dirs_exist_ok=True)
    print('Packaged GDAL 3.9.3 and data for ' + platform)


if __name__ == '__main__':
    main()
