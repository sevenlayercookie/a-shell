#!/usr/bin/env python3
"""Build the upstream astronomy packages for both a-Shell interpreters."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    'pyerfa': ('2.0.1.5', '17d6b24fe4846c65d5e7d8c362dcb08199dc63b30a236aedd73875cc83e1f6c0'),
    'astropy': ('8.0.2', 'e6af35823099ad6a40b57dbe5ff845f577374ea131925c9fa4b49eeab06c5310'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', choices=SOURCES)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    name = args.package
    version, checksum = SOURCES[name]
    base = ROOT / 'build/upstream-parity'
    archive = base / f'{name}-{version}.tar.gz'
    if not archive.exists():
        metadata = json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json'))
        entry = next(e for e in metadata['urls'] if e['packagetype'] == 'sdist')
        urllib.request.urlretrieve(entry['url'], archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
        raise SystemExit(name + ' source checksum mismatch')
    source = base / f'{name}-{version}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    if name == 'astropy':
        patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/astropy-ios-directories.patch')]
        if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
            subprocess.run([*patch, '--forward'], cwd=source, check=True)
        elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
            raise SystemExit('Astropy iOS directory patch does not match source')
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    platform = 'simulator' if args.simulator else 'device'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    python = base / 'venv/bin/python'
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    payload = base / platform
    numpy_prefix = base / ('numpy-simulator-install' if args.simulator else 'numpy-ios-install')
    numpy_include = next(numpy_prefix.rglob('site-packages/numpy/_core/include'))
    subprocess.run([str(python), str(ROOT / 'scripts/prepare-cython-reentry.py'), '--python', str(python)], check=True)
    flags = shlex.join(['-target', triple, '-isysroot', sdk, '-I' + str(config),
                       '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'),
                       '-I' + str(numpy_include), '-O2', '-DCYTHON_PEP489_MULTI_PHASE_INIT=1',
                       '-DCYTHON_USE_MODULE_STATE=1', '-DCYTHON_USE_TYPE_SPECS=1',
                       '-DCYTHON_USE_DICT_VERSIONS=0', '-DCYTHON_USE_PYTYPE_LOOKUP=0'])
    link = ['xcrun', '--sdk', sdk_name, 'clang', '-target', triple, '-isysroot', sdk,
            '-dynamiclib', '-undefined', 'error', '-F' + str(payload / 'Frameworks'),
            '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system', '-lz', '-lm']
    env = dict(os.environ, SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang',
               CXX=f'xcrun --sdk {sdk_name} clang++', CFLAGS=flags, CPPFLAGS=flags,
               CXXFLAGS=flags + ' -std=c++17', LDSHARED=shlex.join(link),
               IOS_NUMPY_INCLUDE=str(numpy_include), _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / (name + '-' + platform + '-build')
    # Regenerate Cython sources using the patched compiler instead of upstream's
    # pre-generated files, whose static type state cannot survive reentry.
    for pyx in source.rglob('*.pyx'):
        pyx.touch()
    with (base / (name + '-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(python), str(ROOT / 'scripts/run-ios-setuptools.py'), 'build',
                        '--build-base', str(build), 'build_ext', '--force', '-j2'],
                       cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    package_name = 'erfa' if name == 'pyerfa' else 'astropy'
    installed = next(build.glob('lib.*/' + package_name))
    site = payload / 'Library/lib/python3.13/site-packages'
    shutil.copytree(installed, site / package_name, dirs_exist_ok=True)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    binaries = list((site / package_name).rglob('*.so'))
    if not binaries:
        raise SystemExit('No astronomy extension modules were built')
    if name == 'astropy':
        combined = build / 'astropy.so'
        objects = list(build.glob('temp.*/**/*.o'))
        subprocess.run([*link, *map(str, objects), '-lc++', '-o', str(combined)], check=True)
        symbols = subprocess.check_output(['xcrun', 'nm', '-gU', str(combined)], text=True)
        required = {'_PyInit_' + b.name.split('.')[0] for b in binaries}
        if required - {line.split()[-1] for line in symbols.splitlines() if line.split()}:
            raise SystemExit('Missing consolidated Astropy entry points')
    packaged = set()
    for binary in binaries:
        relative = binary.relative_to(site)
        module = str(relative.parent / binary.name.split('.')[0]).replace('/', '.')
        native_module = 'astropy.astropy' if name == 'astropy' else module
        stub = binary.with_name(binary.name.split('.')[0] + '.cpython-313-' + sdk_name + '.fwork')
        origin = str(Path('Library/lib/python3.13/site-packages') / stub.relative_to(site))
        for prefix, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
            framework_name = prefix + native_module
            if framework_name in packaged:
                continue
            packaged.add(framework_name)
            packaging.framework(framework_name, combined if name == 'astropy' else binary,
                                payload / 'Frameworks', interpreter,
                                'iPhoneSimulator' if args.simulator else 'iPhoneOS')
            (payload / 'Frameworks' / (framework_name + '.framework') / (framework_name + '.origin')).write_text(origin + '\n')
        stub.write_text('Frameworks/Python-' + native_module + '.framework/Python-' + native_module + '\n')
        binary.unlink()
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site), '--version', version, '--package', package_name]
                   + (['--simulator'] if args.simulator else []), check=True)
    print('Packaged ' + name + ' ' + version + ' for ' + platform)


if __name__ == '__main__':
    main()
