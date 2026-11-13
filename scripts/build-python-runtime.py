#!/usr/bin/env python3
"""Build the pinned CPython iOS interpreter and terminal-only Python payload."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
HASHES = {
    'crypto': '6c33a6d30bf066ca2628cbcc5bab859d082c2ac8c8663dc0a20bb04af3a364d3',
    'openssl': 'd4faf1387c33b23abdbd7b7378e841b2b5cc0b1f2e9e0442cc781a46faa52c04',
    'libffi': 'd49a147798654c331c7f12e39b5da124291451bc2c39318023e28a350debd089',
    'liblzma': '6176c9900ba27297c9a532ea894efdde2cb3164afce3f067110e2fb97634caf7',
}

def download(url, path, checksum):
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
        raise SystemExit('Checksum mismatch: ' + str(path))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-python', default=shutil.which('python3.13'))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--skip-compile', action='store_true', help='Reuse an already installed interpreter')
    args = parser.parse_args()
    if not args.build_python:
        parser.error('Python 3.13 is required on the build Mac')
    base = ROOT / 'build/python'
    deps = base / 'deps'
    deps.mkdir(parents=True, exist_ok=True)
    for name, checksum in HASHES.items():
        archive = deps / (name + '.xcframework.zip')
        download('https://github.com/holzschu/Python-aux/releases/download/1.0/' + archive.name, archive, checksum)
        if not (deps / (name + '.xcframework')).exists():
            with zipfile.ZipFile(archive) as source:
                source.extractall(deps)
        device = deps / (name + '.xcframework/ios-arm64')
        headers = deps / 'include' / {'libffi': 'ffi', 'liblzma': 'lzma'}.get(name, name)
        shutil.copytree(device / 'Headers', headers, dirs_exist_ok=True)
        (deps / 'lib').mkdir(exist_ok=True)
        for library in device.glob('*.a'):
            shutil.copy2(library, deps / 'lib' / library.name)
    download('https://raw.githubusercontent.com/holzschu/ios_system/7658fcf551935b42d6bb5bedc9315d8f53f760c4/ios_error.h',
             deps / 'include/ios_error.h', '51d46b912eb30399cbb5c36c8c8f15eb1a44adcfc9ee581304ac9d3739a84716')
    ios = ROOT / 'xcfs/.build/artifacts/xcfs/ios_system/ios_system.xcframework/ios-arm64/ios_system.framework'
    if not ios.exists():
        raise SystemExit('Resolve the xcfs Swift package in Xcode first: missing ' + str(ios))
    shutil.copytree(ios, deps / 'ios_system.framework', dirs_exist_ok=True)
    patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/cpython-preserve-type-version-tags.patch')]
    if subprocess.run([*patch, '--forward', '--dry-run'], cwd=ROOT / 'cpython', capture_output=True).returncode == 0:
        subprocess.run([*patch, '--forward'], cwd=ROOT / 'cpython', check=True)
    elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=ROOT / 'cpython', capture_output=True).returncode:
        raise SystemExit('CPython reentry patch does not match the pinned source')
    if not args.skip_compile:
        build = base / 'ios'
        (build / 'Modules').mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'cpython/Modules/Setup_iOS.local', build / 'Modules/Setup.local')
        sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
        target = f'-arch arm64 -miphoneos-version-min=15.0 -isysroot {sdk}'
        flags = f'{target} -I{deps}/include -I{deps}/include/ffi/ffi -I{deps}/include/lzma -DPYEXPATNS_H'
        env = dict(os.environ, CC='clang', CXX='clang++', CPP='clang -E', AR='ar',
                   CFLAGS=flags, CPPFLAGS=flags, CXXFLAGS=flags, PLATFORM='iphoneos', OPT='-O2', PKG_CONFIG='/usr/bin/false',
                   LDFLAGS=f'{target} -L{deps}/lib -F{deps} -framework ios_system -lssl -lcrypto -lffi -llzma -lz -lbz2 -lsqlite3 -ldbm')
        configure = [str(ROOT / 'cpython/configure'), '--prefix=' + str(base / 'install/Library'),
                     '--host=arm64-apple-ios15.0', '--build=' + subprocess.check_output([str(ROOT / 'cpython/config.guess')], text=True).strip(),
                     '--with-build-python=' + args.build_python, '--enable-framework=' + str(base / 'install/Frameworks'),
                     '--with-openssl=' + str(deps), '--with-pkg-config=no', '--without-computed-gotos', '--with-ensurepip=no', '--with-readline=editline']
        configure += ['ac_cv_file__dev_ptmx=no', 'ac_cv_file__dev_ptc=no']
        configure += ['ac_cv_func_' + function + '=no' for function in
                      ['getentropy', 'sendfile', 'setregid', 'setreuid', 'setsid', 'setpgid', 'setpgrp', 'setuid', 'forkpty', 'openpty', 'clock_settime']]
        with (base / 'runtime-build.log').open('w') as log:
            subprocess.run(configure, cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            makefile = build / 'Makefile'
            makefile.write_text(re.sub(r'(?m)^(CONFIGURE_LDFLAGS=.+)$', r'\1 Modules/_hacl/libHacl_Hash_SHA2.a Modules/_decimal/libmpdec/libmpdec.a Modules/expat/libexpat.a', makefile.read_text()))
            subprocess.run(['make', f'-j{args.jobs}'], cwd=build, stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(['make', f'-j{args.jobs}', 'install', f'COMPILEALL_OPTS=-j{args.jobs}'], cwd=build, stdout=log, stderr=subprocess.STDOUT, check=True)
    site = base / 'payload/Library/lib/python3.13/site-packages'
    subprocess.run([args.build_python, '-m', 'pip', 'install', '--only-binary=:all:', '--platform', 'any',
                    '--python-version', '3.13', '--implementation', 'py', '--no-compile', '--upgrade', '--require-hashes',
                    '--target', str(site), '-r', str(ROOT / 'scripts/python-terminal-requirements.txt')], check=True)
    subprocess.run([args.build_python, str(ROOT / 'scripts/package-python-runtime.py'), '--install-resources'], check=True)

if __name__ == '__main__':
    main()
