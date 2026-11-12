#!/usr/bin/env python3
"""Build and package upstream's reinitialization-safe NumPy for a-Shell."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--skip-build', action='store_true', help='Package an existing successful build')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    build_name = 'numpy-simulator' if args.simulator else 'numpy-ios'
    build = base / build_name
    source = ROOT / 'cpython/packages/numpy'
    python = base / 'venv/bin/python'
    meson = source / 'vendored-meson/meson/meson.py'
    payload = base / platform
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    config_build = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    env = dict(os.environ, PATH=str(python.parent) + ':' + os.environ['PATH'], PLATFORM=sdk_name)
    if not args.skip_build:
        subprocess.run([str(python), str(ROOT / 'scripts/prepare-cython-reentry.py'),
                        '--python', str(python)], check=True)
        flags = ['-target', triple, '-isysroot', sdk, '-I' + str(config_build),
                 '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'),
                 '-DCYTHON_PEP489_MULTI_PHASE_INIT=1', '-DCYTHON_USE_MODULE_STATE=1', '-DCYTHON_USE_DICT_VERSIONS=0',
                 '-DCYTHON_USE_PYTYPE_LOOKUP=0']
        link = ['-target', triple, '-isysroot', sdk, '-F' + str(payload / 'Frameworks'),
                '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system']
        pc = base / (platform + '-pkgconfig')
        pc.mkdir(parents=True, exist_ok=True)
        text = ('Name: Python\nDescription: a-Shell iOS Python\nVersion: 3.13.1\nCflags: '
                + ' '.join(value for value in flags if value.startswith('-I')) + '\nLibs: '
                + ' '.join(link[4:]) + '\n')
        for name in ['python-3.13', 'python-3.13-embed', 'python3']:
            (pc / (name + '.pc')).write_text(text)
        cross = base / (build_name + '.ini')
        cross.write_text("[binaries]\nc = " + repr(['xcrun', '--sdk', sdk_name, 'clang'])
                         + '\ncpp = ' + repr(['xcrun', '--sdk', sdk_name, 'clang++'])
                         + '\npkg-config = ' + repr(shutil.which('pkg-config'))
                         + '\npython = ' + repr(str(python))
                         + "\n[host_machine]\nsystem = 'ios'\ncpu_family = 'aarch64'\ncpu = 'armv8'\nendian = 'little'"
                         + '\n[properties]\npkg_config_libdir = ' + repr(str(pc))
                         + "\nneeds_exe_wrapper = true\nlongdouble_format = 'IEEE_DOUBLE_LE'"
                         + '\n[built-in options]\nc_args = ' + repr(flags) + '\ncpp_args = ' + repr(flags)
                         + '\nc_link_args = ' + repr(link) + '\ncpp_link_args = ' + repr(link) + '\n')
        command = [str(python), str(meson), 'setup']
        if (build / 'meson-private/coredata.dat').exists():
            command.append('--wipe')
        command += [str(build), str(source), '--cross-file', str(cross),
                    '--prefix', str(base / (build_name + '-install')), '-Dblas=accelerate',
                    '-Dlapack=accelerate', '-Dcpu-dispatch=none', '-Ddisable-highway=true',
                    '-Ddisable-intel-sort=true', '-Dbuildtype=release']
        with (base / (build_name + '-configure.log')).open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        with (base / (build_name + '-build.log')).open('w') as log:
            subprocess.run(['ninja', '-C', str(build), '-j' + str(args.jobs)], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    with (base / (build_name + '-install.log')).open('w') as log:
        subprocess.run([str(python), str(meson), 'install', '-C', str(build), '--no-rebuild'], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    # Consolidate exactly as upstream does, avoiding duplicate helper objects.
    objects = []
    for path in build.rglob('*.o'):
        relative = str(path.relative_to(build))
        if 'lapack_lite.cpython' in relative and (path.name.startswith('lapack_lite_f2c') or path.name == 'lapack_lite_python_xerbla.c.o'):
            continue
        if '_umath_linalg.cpython' in relative and path.name == 'lapack_lite_python_xerbla.c.o':
            continue
        if 'libnpyrandom.a.p/' in relative and path.name == 'src_distributions_distributions.c.o':
            continue
        if any(name in relative for name in ['_multiarray_tests.cpython', '_umath_tests.cpython', '_simd.cpython']) and path.name.startswith('src_common_'):
            continue
        objects.append(str(path))
    binary = build / 'numpy.so'
    command = ['xcrun', 'clang', '-target', triple, '-isysroot', sdk, '-dynamiclib', '-undefined', 'error',
               '-F' + str(payload / 'Frameworks'), '-framework', 'Python', '-F' + str(deps),
               '-framework', 'ios_system', '-framework', 'Accelerate', '-lz', '-lm', '-lc++', *objects,
               '-L' + str(build / 'numpy/random'), '-lnpyrandom', '-L' + str(build / 'numpy/_core'),
               '-lnpymath', '-o', str(binary)]
    with (base / (build_name + '-consolidate.log')).open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    options = json.loads((build / 'meson-info/intro-buildoptions.json').read_text())
    prefix = Path(next(value['value'] for value in options if value['name'] == 'prefix'))
    installed = next(prefix.rglob('site-packages/numpy/__init__.py')).parent
    site = payload / 'Library/lib/python3.13/site-packages'
    site.mkdir(parents=True, exist_ok=True)
    shutil.copytree(installed, site / 'numpy', dirs_exist_ok=True)
    for info in installed.parent.glob('numpy-*.dist-info'):
        shutil.copytree(info, site / info.name, dirs_exist_ok=True)
    for path in (site / 'numpy').rglob('*.so'):
        stub = path.with_name(path.name.split('.')[0] + '.cpython-313-' + sdk_name + '.fwork')
        stub.write_text('Frameworks/Python-numpy.numpy.framework/Python-numpy.numpy\n')
        path.unlink()
    for path in list((site / 'numpy').rglob('__pycache__')):
        shutil.rmtree(path)
    origin = 'Library/lib/python3.13/site-packages/numpy/numpy.cpython-313-' + sdk_name + '.fwork'
    (site / 'numpy' / Path(origin).name).write_text('Frameworks/Python-numpy.numpy.framework/Python-numpy.numpy\n')
    for name, interpreter in [('Python-numpy.numpy', 'Python'), ('PythonAnumpy.numpy', 'pythonA')]:
        packaging.framework(name, binary, payload / 'Frameworks', interpreter,
                            'iPhoneSimulator' if args.simulator else 'iPhoneOS')
        (payload / 'Frameworks' / (name + '.framework') / (name + '.origin')).write_text(origin + '\n')
    for path in (prefix / 'bin').glob('*'):
        if path.is_file():
            text = path.read_text()
            if text.startswith('#!'):
                text = '#!/usr/bin/env python3\n' + text.split('\n', 1)[1]
            destination = payload / 'Library/bin' / path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text)
            destination.chmod(0o755)
    subprocess.run([str(python), str(ROOT / 'scripts/install-pep621-metadata.py'), str(source),
                    '--site', str(site)] + (['--simulator'] if args.simulator else []), check=True)
    print('Packaged upstream NumPy 2.3.1 for ' + platform)

if __name__ == '__main__':
    main()
