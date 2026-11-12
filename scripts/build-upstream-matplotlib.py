#!/usr/bin/env python3
"""Build Matplotlib with upstream a-Shell's interpreter-safe pybind11 fork."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
REVISION = '800b7346261205457cf5aa990ee890fd2eab0e9e'


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
    source = ROOT / 'cpython/packages/matplotlib'
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise SystemExit('Unexpected upstream Matplotlib revision: ' + revision)
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    payload = base / platform
    flags = ['-target', triple, '-isysroot', sdk, '-I' + str(config),
             '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include')]
    link = ['-target', triple, '-isysroot', sdk, '-F' + str(payload / 'Frameworks'),
            '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system']
    numpy_prefix = base / ('numpy-simulator-install' if args.simulator else 'numpy-ios-install')
    numpy_include = next(numpy_prefix.rglob('site-packages/numpy/_core/include'))
    pc = [str(base / (platform + '-pkgconfig')),
          str(base / 'pybind11-host/pybind11/share/pkgconfig')]
    cross = base / ('matplotlib-' + platform + '.ini')
    cross.write_text('[binaries]\nc = ' + repr(['xcrun', '--sdk', sdk_name, 'clang'])
                     + '\ncpp = ' + repr(['xcrun', '--sdk', sdk_name, 'clang++'])
                     + '\npython = ' + repr(str(python))
                     + '\npkg-config = ' + repr(shutil.which('pkg-config'))
                     + "\n[host_machine]\nsystem = 'ios'\ncpu_family = 'aarch64'\ncpu = 'armv8'\nendian = 'little'"
                     + '\n[properties]\nnumpy-include-dir = ' + repr(str(numpy_include))
                     + '\npkg_config_libdir = ' + repr(pc)
                     + '\nneeds_exe_wrapper = true\n[built-in options]\nc_args = ' + repr(flags)
                     + '\ncpp_args = ' + repr(flags) + '\nc_link_args = ' + repr(link)
                     + '\ncpp_link_args = ' + repr(link) + '\n')
    build = base / ('matplotlib-' + platform)
    prefix = base / ('matplotlib-' + platform + '-install')
    meson = ROOT / 'cpython/packages/numpy/vendored-meson/meson/meson.py'
    command = [str(python), str(meson), 'setup']
    if (build / 'meson-private/coredata.dat').exists():
        command.append('--wipe')
    command += [str(build), str(source), '--cross-file', str(cross), '--prefix', str(prefix), '-Dbuildtype=release', '-Dmacosx=false']
    with (base / ('matplotlib-' + platform + '-build.log')).open('w') as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        zconf = source / 'subprojects/freetype-2.6.1/src/gzip/zconf.h'
        text = zconf.read_text()
        text = text.replace('!defined(MACOS) && !defined(TARGET_OS_MAC)', '1')
        zconf.write_text(text)
        subprocess.run(['ninja', '-C', str(build), '-j' + str(args.jobs)], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run([str(python), str(meson), 'install', '-C', str(build), '--no-rebuild'], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    installed = next(prefix.rglob('site-packages/matplotlib/__init__.py')).parent
    site = payload / 'Library/lib/python3.13/site-packages'
    shutil.copytree(installed.parent, site, dirs_exist_ok=True)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    for binary in (site / 'matplotlib').rglob('*.so'):
        module = 'matplotlib.' + binary.name.split('.')[0]  # Upstream flattens backend framework names.
        stub = binary.with_name(binary.name.split('.')[0] + '.cpython-313-' + sdk_name + '.fwork')
        stub.write_text('Frameworks/Python-' + module + '.framework/Python-' + module + '\n')
        for prefix_name, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
            name = prefix_name + module
            packaging.framework(name, binary, payload / 'Frameworks', interpreter,
                                'iPhoneSimulator' if args.simulator else 'iPhoneOS')
            (payload / 'Frameworks' / (name + '.framework') / (name + '.origin')).write_text(
                'Library/lib/python3.13/site-packages/' + str(stub.relative_to(site)) + '\n')
            for license_path in [source / 'subprojects/freetype-2.6.1/docs/FTL.TXT',
                                 source / 'subprojects/freetype-2.6.1/docs/LICENSE.TXT',
                                 source / 'subprojects/qhull-8.0.2/COPYING.txt']:
                if license_path.exists():
                    shutil.copy2(license_path, payload / 'Frameworks' / (name + '.framework') / license_path.name)
            shutil.copy2(ROOT / 'cpython/packages/pybind11/LICENSE',
                         payload / 'Frameworks' / (name + '.framework') / 'pybind11-LICENSE')
        binary.unlink()
    # Meson installs package files, while distribution metadata is supplied by
    # meson-python during wheel building. Preserve that metadata separately.
    version = json.loads((build / 'meson-info/intro-projectinfo.json').read_text())['version']
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site), '--version', version, '--package', 'matplotlib',
                    '--package', 'mpl_toolkits', '--package', 'pylab.py']
                   + (['--simulator'] if args.simulator else []), check=True)
    print('Packaged Matplotlib ' + version + ' for ' + platform)


if __name__ == '__main__':
    main()
