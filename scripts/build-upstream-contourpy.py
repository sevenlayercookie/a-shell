#!/usr/bin/env python3
"""Build ContourPy with upstream a-Shell's interpreter-safe pybind11 fork."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://files.pythonhosted.org/packages/58/01/1253e6698a07380cd31a736d248a3f2a50a7c88779a1813da27503cadc2a/contourpy-1.3.3.tar.gz'
SHA256 = '083e12155b210502d0bca491432bb04d56dc3432f95a979b429f2848c3dbe880'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    python = base / 'venv/bin/python'
    spec = importlib.util.spec_from_file_location('ios_pybind', ROOT / 'scripts/prepare-ios-pybind11.py')
    pybind = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pybind)
    env = pybind.environment(python)
    archive = base / 'contourpy-1.3.3.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('ContourPy source checksum mismatch')
    source = base / 'contourpy-1.3.3'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    payload = base / platform
    flags = ['-target', triple, '-isysroot', sdk, '-I' + str(config),
             '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include')]
    link = ['-target', triple, '-isysroot', sdk, '-F' + str(payload / 'Frameworks'),
            '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system']
    pc = [str(base / (platform + '-pkgconfig')),
          str(base / 'pybind11-host/pybind11/share/pkgconfig')]
    cross = base / ('contourpy-' + platform + '.ini')
    cross.write_text('[binaries]\nc = ' + repr(['xcrun', '--sdk', sdk_name, 'clang'])
                     + '\ncpp = ' + repr(['xcrun', '--sdk', sdk_name, 'clang++'])
                     + '\npython = ' + repr(str(python))
                     + '\npkg-config = ' + repr(shutil.which('pkg-config'))
                     + "\n[host_machine]\nsystem = 'ios'\ncpu_family = 'aarch64'\ncpu = 'armv8'\nendian = 'little'"
                     + '\n[properties]\npkg_config_libdir = ' + repr(pc)
                     + '\nneeds_exe_wrapper = true\n[built-in options]\nc_args = ' + repr(flags)
                     + '\ncpp_args = ' + repr(flags) + '\nc_link_args = ' + repr(link)
                     + '\ncpp_link_args = ' + repr(link) + '\n')
    build = base / ('contourpy-' + platform)
    prefix = base / ('contourpy-' + platform + '-install')
    meson = ROOT / 'cpython/packages/numpy/vendored-meson/meson/meson.py'
    command = [str(python), str(meson), 'setup']
    if (build / 'meson-private/coredata.dat').exists():
        command.append('--wipe')
    command += [str(build), str(source), '--cross-file', str(cross), '--prefix', str(prefix), '-Dbuildtype=release']
    with (base / ('contourpy-' + platform + '-build.log')).open('w') as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(['ninja', '-C', str(build), '-j' + str(args.jobs)], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run([str(python), str(meson), 'install', '-C', str(build), '--no-rebuild'], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    installed = next(prefix.rglob('site-packages/contourpy/__init__.py')).parent
    site = payload / 'Library/lib/python3.13/site-packages'
    shutil.copytree(installed, site / 'contourpy', dirs_exist_ok=True)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    for binary in (site / 'contourpy').rglob('*.so'):
        module = 'contourpy.' + binary.name.split('.')[0]
        stub = binary.with_name(binary.name.split('.')[0] + '.cpython-313-' + sdk_name + '.fwork')
        stub.write_text('Frameworks/Python-' + module + '.framework/Python-' + module + '\n')
        for prefix_name, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
            name = prefix_name + module
            packaging.framework(name, binary, payload / 'Frameworks', interpreter,
                                'iPhoneSimulator' if args.simulator else 'iPhoneOS')
            (payload / 'Frameworks' / (name + '.framework') / (name + '.origin')).write_text(
                'Library/lib/python3.13/site-packages/' + str(stub.relative_to(site)) + '\n')
            shutil.copy2(source / 'LICENSE', payload / 'Frameworks' / (name + '.framework') / 'ContourPy-LICENSE')
            shutil.copy2(ROOT / 'cpython/packages/pybind11/LICENSE',
                         payload / 'Frameworks' / (name + '.framework') / 'pybind11-LICENSE')
        binary.unlink()
    # Meson installs package files, while distribution metadata is supplied by
    # meson-python during wheel building. Preserve that metadata separately.
    version = json.loads((build / 'meson-info/intro-projectinfo.json').read_text())['version']
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site), '--version', version]
                   + (['--simulator'] if args.simulator else []), check=True)
    print('Packaged ContourPy ' + version + ' for ' + platform)


if __name__ == '__main__':
    main()
