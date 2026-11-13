#!/usr/bin/env python3
"""Build full Shapely for a-Shell device or Simulator Python."""
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
URL = 'https://files.pythonhosted.org/packages/f3/ab/924b6e202f796d270a3041a230151f7908db5ea48c74effe6f8023e9bd05/shapely-2.2.0.tar.gz'
SHA256 = 'e8865e553d874a1ec4a032057ea81fca9def37b188cd8fb550af3b3480b3f88c'


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
    archive = base / 'shapely-2.2.0.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('shapely source checksum mismatch')
    source = base / 'shapely-2.2.0'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    payload = base / platform
    env['IOS_CYTHON_INCLUDE'] = str(payload / 'Library/lib/python3.13/site-packages')
    flags = ['-target', triple, '-isysroot', sdk, '-I' + str(config),
             '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'),
             '-DCYTHON_PEP489_MULTI_PHASE_INIT=1', '-DCYTHON_USE_MODULE_STATE=1',
             '-DCYTHON_USE_TYPE_SPECS=1', '-DCYTHON_USE_DICT_VERSIONS=0', '-DCYTHON_USE_PYTYPE_LOOKUP=0']
    link = ['-target', triple, '-isysroot', sdk, '-F' + str(payload / 'Frameworks'),
            '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system']
    pc_dir = base / (platform + '-pkgconfig')
    geos_prefix = base / ('geos-' + platform + '-install')
    (pc_dir / 'geos.pc').write_text('prefix=' + str(geos_prefix) + '\n'
                                  'Name: GEOS\nDescription: GEOS geometry library\nVersion: 3.11.0\n'
                                  'Cflags: -I${prefix}/include\nLibs: -F' + str(payload / 'Frameworks') + ' -framework libgeos_c\n')
    pc = [str(pc_dir)]
    numpy_prefix = base / ('numpy-simulator-install' if args.simulator else 'numpy-ios-install')
    numpy_include = next(numpy_prefix.rglob('site-packages/numpy/_core/include'))
    pc.append(str(numpy_include.parent / 'lib/pkgconfig'))
    cross = base / ('shapely-' + platform + '.ini')
    cross.write_text('[binaries]\nc = ' + repr(['xcrun', '--sdk', sdk_name, 'clang'])
                     + '\ncpp = ' + repr(['xcrun', '--sdk', sdk_name, 'clang++'])
                     + '\npython = ' + repr(str(python))
                     + '\ncython = ' + repr(str(ROOT / 'scripts/ios-cython.py'))
                     + '\npkg-config = ' + repr(shutil.which('pkg-config'))
                     + "\n[host_machine]\nsystem = 'ios'\ncpu_family = 'aarch64'\ncpu = 'armv8'\nendian = 'little'"
                     + '\n[properties]\nnumpy-include-dir = ' + repr(str(numpy_include))
                     + '\npkg_config_libdir = ' + repr(pc)
                     + '\nneeds_exe_wrapper = true\n[built-in options]\nc_args = ' + repr(flags)
                     + '\ncpp_args = ' + repr(flags) + '\nc_link_args = ' + repr(link)
                     + '\ncpp_link_args = ' + repr(link) + "\ncpp_std = 'c++17'\n")
    native = base / 'shapely-native.ini'
    native.write_text('[binaries]\ncython = ' + repr(str(ROOT / 'scripts/ios-cython.py')) + '\n')
    build = base / ('shapely-' + platform)
    prefix = base / ('shapely-' + platform + '-install')
    meson = base / 'venv/bin/meson'
    command = [str(meson), 'setup']
    if (build / 'meson-private/coredata.dat').exists():
        command.append('--reconfigure' if args.resume else '--wipe')
    command += [str(build), str(source), '--cross-file', str(cross), '--native-file', str(native), '--prefix', str(prefix), '-Dbuildtype=release']
    with (base / ('shapely-' + platform + '-build.log')).open('w') as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['ninja', '-C', str(build), '-j' + str(args.jobs)], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run([str(meson), 'install', '-C', str(build), '--no-rebuild'], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    installed = next(prefix.rglob('site-packages/shapely/__init__.py')).parent
    site = payload / 'Library/lib/python3.13/site-packages'
    shutil.copytree(installed, site / 'shapely', dirs_exist_ok=True)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    binaries = list((site / 'shapely').rglob('*.so'))
    if not binaries:
        raise SystemExit('No Shapely extensions built')
    for binary in binaries:
        relative = binary.relative_to(site)
        module = str(relative.parent / binary.name.split('.')[0]).replace('/', '.')
        stub = binary.with_name(binary.name.split('.')[0] + '.cpython-313-' + sdk_name + '.fwork')
        origin = str(Path('Library/lib/python3.13/site-packages') / stub.relative_to(site))
        for prefix_name, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
            name = prefix_name + module
            packaging.framework(name, binary, payload / 'Frameworks', interpreter,
                                'iPhoneSimulator' if args.simulator else 'iPhoneOS')
            (payload / 'Frameworks' / (name + '.framework') / (name + '.origin')).write_text(origin + '\n')
        stub.write_text('Frameworks/Python-' + module + '.framework/Python-' + module + '\n')
        binary.unlink()
    # Meson installs package files, while distribution metadata is supplied by
    # meson-python during wheel building. Preserve that metadata separately.
    version = json.loads((build / 'meson-info/intro-projectinfo.json').read_text())['version']
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site), '--version', version, '--package', 'shapely']
                   + (['--simulator'] if args.simulator else []), check=True)
    print('Packaged shapely ' + version + ' for ' + platform)


if __name__ == '__main__':
    main()
