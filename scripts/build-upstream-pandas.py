#!/usr/bin/env python3
"""Build compatible pandas with upstream consolidated iOS framework layout."""
import argparse
import hashlib
import importlib.util
import json
import shlex
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://files.pythonhosted.org/packages/d1/6f/75aa71f8a14267117adeeed5d21b204770189c0a0025acbdc03c337b28fc/pandas-2.3.1.tar.gz'
SHA256 = '0a95b9ac964fe83ce317827f80304d37388ea77616b1425f0ae41c9d2d0d7bb2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--resume', action='store_true', help='Reuse configured objects after a failed build')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    python = base / 'venv/bin/python'
    env = dict(os.environ, PATH=str(python.parent) + ':' + os.environ['PATH'])
    subprocess.run([str(python), str(ROOT / 'scripts/prepare-cython-reentry.py'), '--python', str(python)], check=True)
    archive = base / 'pandas-2.3.1.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('pandas source checksum mismatch')
    source = base / 'pandas-2.3.1'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    for filename in ['pandas-target-numpy.patch', 'pandas-local-helpers.patch']:
        patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches' / filename)]
        if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
            subprocess.run([*patch, '--forward'], cwd=source, check=True)
        elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
            raise SystemExit(filename + ' does not match the source')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    payload = base / platform
    flags = ['-target', triple, '-isysroot', sdk, '-I' + str(config),
             '-I' + str(source / 'pandas/_libs/include/pandas'),
             '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'),
             '-DCYTHON_PEP489_MULTI_PHASE_INIT=1', '-DCYTHON_USE_MODULE_STATE=1',
             '-DCYTHON_USE_TYPE_SPECS=1', '-DCYTHON_USE_DICT_VERSIONS=0', '-DCYTHON_USE_PYTYPE_LOOKUP=0']
    link = ['-target', triple, '-isysroot', sdk, '-F' + str(payload / 'Frameworks'),
            '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system']
    pc = [str(base / (platform + '-pkgconfig'))]
    numpy_prefix = base / ('numpy-simulator-install' if args.simulator else 'numpy-ios-install')
    numpy_include = next(numpy_prefix.rglob('site-packages/numpy/_core/include'))
    cross = base / ('pandas-' + platform + '.ini')
    cross.write_text('[binaries]\nc = ' + repr(['xcrun', '--sdk', sdk_name, 'clang'])
                     + '\ncpp = ' + repr(['xcrun', '--sdk', sdk_name, 'clang++'])
                     + '\npython = ' + repr(str(python))
                     + '\ncython = ' + repr([str(python), str(ROOT / 'scripts/ios-cython.py')])
                     + '\npkg-config = ' + repr(shutil.which('pkg-config'))
                     + "\n[host_machine]\nsystem = 'ios'\ncpu_family = 'aarch64'\ncpu = 'armv8'\nendian = 'little'"
                     + '\n[properties]\nnumpy-include-dir = ' + repr(str(numpy_include))
                     + '\npkg_config_libdir = ' + repr(pc)
                     + '\nneeds_exe_wrapper = true\n[built-in options]\nc_args = ' + repr(flags)
                     + '\ncpp_args = ' + repr(flags) + '\nc_link_args = ' + repr(link)
                     + '\ncpp_link_args = ' + repr(link) + "\ncpp_std = 'c++17'\n")
    native = base / 'pandas-native.ini'
    native.write_text('[binaries]\ncython = ' + repr([str(python), str(ROOT / 'scripts/ios-cython.py')]) + '\n')
    build = base / ('pandas-' + platform)
    prefix = base / ('pandas-' + platform + '-install')
    meson = ROOT / 'cpython/packages/numpy/vendored-meson/meson/meson.py'
    command = [str(python), str(meson), 'setup']
    if (build / 'meson-private/coredata.dat').exists():
        command.append('--reconfigure' if args.resume else '--wipe')
    command += [str(build), str(source), '--cross-file', str(cross), '--native-file', str(native), '--prefix', str(prefix), '-Dbuildtype=release']
    with (base / ('pandas-' + platform + '-build.log')).open('w') as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['ninja', '-C', str(build), '-j' + str(args.jobs)], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run([str(python), str(meson), 'install', '-C', str(build), '--no-rebuild'], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    installed = next(prefix.rglob('site-packages/pandas/__init__.py')).parent
    site = payload / 'Library/lib/python3.13/site-packages'
    shutil.copytree(installed, site / 'pandas', dirs_exist_ok=True)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    # Deduplicate C helpers compiled into multiple upstream extension modules,
    # retaining every generated module initializer.
    objects = []
    seen_sources = set()
    for command_info in json.loads((build / 'compile_commands.json').read_text()):
        input_path = Path(command_info['file'])
        if not input_path.is_absolute():
            input_path = (build / input_path).resolve()
        arguments = shlex.split(command_info['command'])
        output = Path(arguments[arguments.index('-o') + 1])
        if not output.is_absolute():
            output = build / output
        if output.suffix != '.o' or not output.exists() or input_path in seen_sources:
            continue
        seen_sources.add(input_path)
        objects.append(str(output))
    combined = build / 'pandas.so'
    with (base / ('pandas-' + platform + '-consolidate.log')).open('w') as log:
        subprocess.run(['xcrun', 'clang++', '-target', triple, '-isysroot', sdk, '-dynamiclib',
                        '-undefined', 'error', '-F' + str(payload / 'Frameworks'), '-framework', 'Python',
                        '-F' + str(deps), '-framework', 'ios_system', *objects, '-lm', '-lz',
                        '-o', str(combined)], stdout=log, stderr=subprocess.STDOUT, check=True)
    binaries = list((site / 'pandas').rglob('*.so'))
    symbols = subprocess.check_output(['xcrun', 'nm', '-gU', str(combined)], text=True)
    required = {'_PyInit_' + binary.name.split('.')[0] for binary in binaries}
    missing = required - {line.split()[-1] for line in symbols.splitlines() if line.split()}
    if missing:
        raise SystemExit('Missing pandas initializers: ' + ', '.join(sorted(missing)))
    module = 'pandas.pandas'
    origin = 'Library/lib/python3.13/site-packages/pandas/pandas.cpython-313-' + sdk_name + '.fwork'
    for prefix_name, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
        name = prefix_name + module
        packaging.framework(name, combined, payload / 'Frameworks', interpreter,
                            'iPhoneSimulator' if args.simulator else 'iPhoneOS')
        (payload / 'Frameworks' / (name + '.framework') / (name + '.origin')).write_text(origin + '\n')
    for binary in binaries:
        stub = binary.with_name(binary.name.split('.')[0] + '.cpython-313-' + sdk_name + '.fwork')
        stub.write_text('Frameworks/Python-pandas.pandas.framework/Python-pandas.pandas\n')
        binary.unlink()
    (site / 'pandas' / ('pandas.cpython-313-' + sdk_name + '.fwork')).write_text(
        'Frameworks/Python-pandas.pandas.framework/Python-pandas.pandas\n')
    # Meson installs package files, while distribution metadata is supplied by
    # meson-python during wheel building. Preserve that metadata separately.
    version = json.loads((build / 'meson-info/intro-projectinfo.json').read_text())['version']
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site), '--version', version]
                   + (['--simulator'] if args.simulator else []), check=True)
    print('Packaged pandas ' + version + ' for ' + platform)


if __name__ == '__main__':
    main()
