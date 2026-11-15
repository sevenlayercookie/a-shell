#!/usr/bin/env python3
"""Build upstream Fiona or rasterio against a-Shell's GDAL and Python."""
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
SOURCES = {
    'fiona': ('1.10.1', 'https://files.pythonhosted.org/packages/51/e0/71b63839cc609e1d62cea2fc9774aa605ece7ea78af823ff7a8f1c560e72/fiona-1.10.1.tar.gz', 'b00ae357669460c6491caba29c2022ff0acfcbde86a95361ea8ff5cd14a86b68'),
    'rasterio': ('1.5.2', 'https://files.pythonhosted.org/packages/51/90/bd0a124e164f5fe776084c9731b43ab136b31281a18608e617cdb5f2be70/rasterio-1.5.2.tar.gz', 'e65a15b7bd22ce8f8ce8159856669dc9fafabf66cde6156e8f8e71d55abcd515'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', choices=SOURCES)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--relink', action='store_true')
    args = parser.parse_args()
    name = args.package
    version, url, checksum = SOURCES[name]
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    archive = base / f'{name}-{version}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(url, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
        raise SystemExit(name + ' source checksum mismatch')
    source = base / f'{name}-{version}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    patch = ['patch', '--batch', '-p1', '-i', str(ROOT / ('patches/' + name + '-ios-cxx.patch'))]
    if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
        subprocess.run([*patch, '--forward'], cwd=source, check=True)
    elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
        raise SystemExit(name + ' C++ patch does not match source')
    python = base / 'venv/bin/python'
    subprocess.run([str(python), str(ROOT / 'scripts/prepare-cython-reentry.py'), '--python', str(python)], check=True)
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    prefix = base / ('gdal-' + platform + '-install')
    proj = base / ('proj-' + platform + '-install')
    frameworks = base / platform / 'Frameworks'
    if not (frameworks / 'libgdal.framework/libgdal').exists():
        raise SystemExit('Build GDAL for ' + platform + ' first')
    numpy_prefix = base / ('numpy-simulator-install' if args.simulator else 'numpy-ios-install')
    numpy_include = next(numpy_prefix.rglob('site-packages/numpy/_core/include'))
    config_script = base / ('gdal-config-' + platform + '.py')
    answers = {'--cflags': '-I' + str(prefix / 'include'),
               '--libs': '-F' + str(frameworks) + ' -framework libgdal',
               '--datadir': str(prefix / 'share/gdal'), '--version': '3.9.3'}
    config_script.write_text('#!/usr/bin/env python3\nimport sys\nvalues = ' + repr(answers) + '\nprint(values[sys.argv[1]])\n')
    config_script.chmod(0o755)
    flags = shlex.join(['-target', triple, '-isysroot', sdk, '-I' + str(config),
                        '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'),
                        '-I' + str(numpy_include), '-O2', '-DCYTHON_PEP489_MULTI_PHASE_INIT=1',
                        '-DCYTHON_USE_MODULE_STATE=1', '-DCYTHON_USE_TYPE_SPECS=1',
                        '-DCYTHON_USE_DICT_VERSIONS=0', '-DCYTHON_USE_PYTYPE_LOOKUP=0'])
    linker = shlex.join(['xcrun', '--sdk', sdk_name, 'clang++', '-target', triple, '-isysroot', sdk,
                         '-dynamiclib', '-undefined', 'error', '-F' + str(frameworks),
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system',
                         '-framework', 'libgdal', '-lc++'])
    env = dict(os.environ, SDKROOT=sdk, GDAL_CONFIG=str(config_script), GDAL_VERSION='3.9.3',
               CC=f'xcrun --sdk {sdk_name} clang', CXX=f'xcrun --sdk {sdk_name} clang++',
               CFLAGS=flags, CPPFLAGS=flags, CXXFLAGS=flags + ' -std=c++17',
               IOS_NUMPY_INCLUDE=str(numpy_include), IOS_CYTHON_INCLUDE=str(base / platform / 'Library/lib/python3.13/site-packages'),
               LDSHARED=linker, LDCXXSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / (name + '-' + platform + '-build')
    if args.relink:
        for binary in build.glob('lib.*/**/*.so'):
            binary.unlink()
    else:
        for pyx in source.rglob('*.pyx'):
            pyx.touch()
    dist = build / 'dist'
    with (base / (name + '-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(python), str(ROOT / 'scripts/run-ios-setuptools.py'), 'build', '--build-base', str(build),
                        'build_ext', *([] if args.relink else ['--force']), '-j2', 'bdist_wheel',
                        '--plat-name', 'ios_15_0_arm64_' + sdk_name, '--dist-dir', str(dist)],
                       cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    wheel = next(dist.glob('*.whl'))
    subprocess.run([str(python), str(ROOT / 'scripts/install-ios-python-wheel.py'), str(wheel),
                    '--sha256', hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    '--library', str(base / platform / 'Library'), '--frameworks', str(frameworks)]
                   + (['--simulator'] if args.simulator else []), check=True)
    site = base / platform / 'Library/lib/python3.13/site-packages' / name
    shutil.copytree(prefix / 'share/gdal', site / 'gdal_data', dirs_exist_ok=True)
    shutil.copytree(proj / 'share/proj', site / 'proj_data', dirs_exist_ok=True)


if __name__ == '__main__':
    main()
