#!/usr/bin/env python3
"""Build upstream SciPy with iOS Python, OpenBLAS, and the Flang runtime."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://files.pythonhosted.org/packages/f5/4a/b927028464795439faec8eaf0b03b011005c487bb2d07409f28bf30879c4/scipy-1.16.1.tar.gz'
SHA256 = '44c76f9e8b6e8e488a586190ab38016e4ed2f8a038af7cd3defa903c0a2238b3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--skip-build', action='store_true')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    simulator = args.simulator
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if simulator else 'device'
    sdk_name = 'iphonesimulator' if simulator else 'iphoneos'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if simulator else '')
    build_name = 'scipy-simulator' if simulator else 'scipy-ios'
    b = base / build_name
    payload = base / platform
    deps = ROOT / ('build/python/simulator-deps' if simulator else 'build/python/deps')
    config = ROOT / ('build/python/simulator' if simulator else 'build/python/ios')
    openblas = base / ('openblas-simulator-install' if simulator else 'openblas-ios-install')
    runtime_dir = base / ('flang-runtime-simulator' if simulator else 'flang-runtime-ios') / 'lib/clang/23/lib/ios'
    python = base / 'venv/bin/python'
    meson = ROOT / 'cpython/packages/numpy/vendored-meson/meson/meson.py'
    source = base / 'scipy-1.16.1'
    env = dict(os.environ, PATH=str(python.parent) + ':' + os.environ['PATH'])
    if not args.skip_build:
        for required in [openblas / 'lib/libopenblas.a', runtime_dir / 'libflang_rt.runtime.a']:
            if not required.is_file():
                raise SystemExit('Build the iOS scientific toolchain first: missing ' + str(required))
        archive = base / 'scipy-1.16.1.tar.gz'
        if not archive.exists():
            urllib.request.urlretrieve(URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise SystemExit('SciPy source checksum mismatch')
        if not source.exists():
            with tarfile.open(archive) as package:
                package.extractall(base, filter='data')
        patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/scipy-consolidation-ios.patch')]
        check = subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True)
        if check.returncode == 0:
            subprocess.run([*patch, '--forward'], cwd=source, check=True)
        elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
            raise SystemExit('SciPy consolidation patch does not match the source')
        subprocess.run([str(python), str(ROOT / 'scripts/prepare-cython-reentry.py'), '--python', str(python)], check=True)
        sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
        flags = ['-target', triple, '-isysroot', sdk, '-I' + str(config),
                 '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'),
                 '-DCYTHON_PEP489_MULTI_PHASE_INIT=1', '-DCYTHON_USE_MODULE_STATE=1',
                 '-DCYTHON_USE_DICT_VERSIONS=0', '-DCYTHON_USE_PYTYPE_LOOKUP=0']
        link = ['-target', triple, '-isysroot', sdk, '-F' + str(payload / 'Frameworks'),
                '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system',
                '-L' + str(runtime_dir), '-lc++']
        ff = ['-target', triple, '--sysroot=' + sdk]
        fl = ff + ['-L' + str(runtime_dir), '-Wl,-F' + str(payload / 'Frameworks'),
                   '-Wl,-framework,Python', '-Wl,-F' + str(deps), '-Wl,-framework,ios_system', '-lc++']
        pc = base / (platform + '-pkgconfig')
        pc.mkdir(parents=True, exist_ok=True)
        shutil.copy2(openblas / 'lib/pkgconfig/openblas.pc', pc / 'openblas.pc')
        text = (pc / 'openblas.pc').read_text()
        # The static Fortran runtime is linked explicitly by the final native library.
        text = text.replace(' -lgfortran', '').replace(' -lquadmath', '')
        runtime_flags = f' -L{runtime_dir} -lFortranRuntime -lFortranDecimal -lc++ -lm'
        text = '\n'.join(line + runtime_flags if line.startswith(('Libs:', 'Libs.private:')) else line
                         for line in text.splitlines()) + '\n'
        (pc / 'openblas.pc').write_text(text)
        python_pc = ('Name: Python\nDescription: a-Shell iOS Python\nVersion: 3.13.1\nCflags: '
                     + ' '.join(flag for flag in flags if flag.startswith('-I')) + '\nLibs: '
                     + ' '.join(link[4:]) + '\n')
        for name in ['python-3.13', 'python-3.13-embed', 'python3']:
            (pc / (name + '.pc')).write_text(python_pc)
        numpy_prefix = base / ('numpy-simulator-install' if simulator else 'numpy-ios-install')
        numpy_include = next(numpy_prefix.rglob('site-packages/numpy/_core/include'))
        cross = base / (build_name + '.ini')
        cross.write_text('[binaries]\nc = ' + repr(['xcrun', '--sdk', sdk_name, 'clang'])
                         + '\ncpp = ' + repr(['xcrun', '--sdk', sdk_name, 'clang++'])
                         + '\nfortran = ' + repr([str(python), str(ROOT / 'scripts/ios-flang.py')])
                         + '\npython = ' + repr(str(python))
                         + '\npkg-config = ' + repr(shutil.which('pkg-config'))
                         + "\n[host_machine]\nsystem = 'ios'\ncpu_family = 'aarch64'\ncpu = 'armv8'\nendian = 'little'"
                         + '\n[properties]\nnumpy-include-dir = ' + repr(str(numpy_include))
                         + '\npkg_config_libdir = ' + repr(str(pc))
                         + "\nneeds_exe_wrapper = true\nlongdouble_format = 'IEEE_DOUBLE_LE'"
                         + '\n[built-in options]\nc_args = ' + repr(flags) + '\ncpp_args = ' + repr(flags)
                         + '\nc_link_args = ' + repr(link) + '\ncpp_link_args = ' + repr(link)
                         + '\nfortran_args = ' + repr(ff) + '\nfortran_link_args = ' + repr(fl) + '\n')
        command = [str(python), str(meson), 'setup']
        if (b / 'meson-private/coredata.dat').exists():
            command.append('--wipe')
        command += [str(b), str(source), '--cross-file', str(cross), '--prefix', str(base / (build_name + '-install')),
                    '-Dblas=openblas', '-Dlapack=openblas', '-Duse-pythran=false', '-Dbuildtype=release']
        with (base / ('scipy-' + platform + '-configure.log')).open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        with (base / ('scipy-' + platform + '-build.log')).open('w') as log:
            subprocess.run(['ninja', '-C', str(b), '-j' + str(args.jobs)], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    consolidate(base, b, payload, deps, openblas, simulator, sdk_name, triple, platform)
    subprocess.run([str(python), str(ROOT / 'scripts/package-upstream-scipy.py')]
                   + (['--simulator'] if simulator else []), check=True)


def consolidate(base, build, payload, deps, openblas, simulator, sdk_name, triple, platform):
    # These modules can share a native library. The six Cython capsule/ufunc
    # libraries in package-upstream-scipy.py remain separate, as in upstream.
    roots = {'_lib', 'cluster', 'fft', 'fftpack', 'integrate', 'interpolate',
             'io', 'linalg', 'ndimage', 'odr', 'signal', 'sparse', 'spatial', 'stats'}
    optimize = ('_zeros.', '_bglu_dense.', '_direct.', '_group_columns.',
                '_lbfgsb.', '_lsap.', '_minpack.', '_moduleTNC.', '_pava_pybind.', '_slsqplib.')
    special = ('_comb.', '_specfun.', 'cython_special.', '_test_internal.')
    objects = []
    for path in (build / 'scipy').rglob('*.o'):
        relative = path.relative_to(build / 'scipy')
        parts = relative.parts
        if parts[0].startswith('_cyutility.'):
            objects.append(str(path))
            continue
        if parts[0] not in roots | {'optimize', 'special'}:
            continue
        if parts[0] == 'optimize':
            selected = (parts[1].startswith(optimize) or parts[1] in {'_lsq', '_trlib'}
                        or (parts[1] == '_highspy' and not parts[2].endswith('.a.p')))
            if not selected:
                continue
        if parts[0] == 'special' and not parts[1].startswith(special):
            continue
        if any(part.endswith('.a.p') for part in parts):
            continue
        if parts[0] == 'stats' and path.name == '.._libnpyrandom_distributions.c.o':
            continue
        text = str(relative)
        # f2py generates identical wrappers in both fixed/free-form inputs.
        if ('meson-generated_' in path.name and path.name.endswith('-f2pywrappers.f.o')
                and any(name in text for name in ['_propack/', 'integrate/_dop.',
                                                 'integrate/_lsoda.', 'integrate/_vode.'])):
            continue
        if '_test_internal.' in text and path.name == 'dd_real_wrappers.cpp.o':
            continue
        objects.append(str(path))
    libraries = [str(path) for path in (build / 'scipy').rglob('*.a')]
    libraries.append(str(build / 'subprojects/qhull_r/liblibqhull_r.a'))
    numpy = base / ('numpy-simulator' if simulator else 'numpy-ios')
    runtime = (base / ('flang-runtime-simulator' if simulator else 'flang-runtime-ios')
               / 'lib/clang/23/lib/ios/libflang_rt.runtime.a')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    command = ['xcrun', 'clang++', '-target', triple, '-isysroot', sdk, '-dynamiclib',
               '-undefined', 'error', '-F' + str(payload / 'Frameworks'), '-framework', 'Python',
               '-F' + str(deps), '-framework', 'ios_system', *objects, *libraries,
               str(openblas / 'lib/libopenblas.a'), str(runtime),
               str(numpy / 'numpy/_core/libnpymath.a'), str(numpy / 'numpy/random/libnpyrandom.a'),
               '-lz', '-lm', '-o', str(build / 'scipy.so')]
    with (base / ('scipy-' + platform + '-consolidate.log')).open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    print('Consolidated SciPy native modules')


if __name__ == "__main__":
    main()
