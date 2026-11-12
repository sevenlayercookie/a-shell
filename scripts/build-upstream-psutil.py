#!/usr/bin/env python3
"""Build the upstream psutil package for a-Shell's device or Simulator Python."""
import argparse
import hashlib
import os
import shutil
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent.parent
REVISION = 'eda9a5a6b34163d07ea1cc57fd4f2501aa3f94f3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    original = ROOT / 'cpython/packages/psutil'
    revision = subprocess.check_output(['git', '-C', str(original), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise SystemExit('Unexpected upstream psutil revision: ' + revision)
    source = base / 'psutil-ios-source'
    shutil.copytree(original, source, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.git', 'build', '__pycache__', '*.egg-info'))
    subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(ROOT / 'patches/psutil-cross-ios.patch')],
                   cwd=source, check=True)
    subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(ROOT / 'patches/psutil-ios-task-info.patch')],
                   cwd=source, check=True)
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    platform = 'simulator' if args.simulator else 'device'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    python = base / 'venv/bin/python'
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    flags = shlex.join(['-target', triple, '-isysroot', sdk, '-I' + str(config),
                        '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'), '-O2'])
    linker = shlex.join(['xcrun', '--sdk', sdk_name, 'clang', '-target', triple, '-isysroot', sdk,
                         '-dynamiclib', '-undefined', 'error', '-F' + str(base / platform / 'Frameworks'),
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system'])
    env = dict(os.environ, SDKROOT=sdk, ASHELL_CROSS_IOS='1',
               ASHELL_SIMULATOR='1' if args.simulator else '0', CC=f'xcrun --sdk {sdk_name} clang', CFLAGS=flags, CPPFLAGS=flags,
               LDSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    build = base / ('psutil-' + platform + '-build')
    dist = build / 'dist'
    with (base / ('psutil-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(python), 'setup.py', 'build', '--build-base', str(build),
                        'build_ext', '--force', 'bdist_wheel', '--plat-name', 'ios_15_0_arm64_' + sdk_name,
                        '--dist-dir', str(dist)], cwd=source, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    wheel = next(dist.glob('*.whl'))
    subprocess.run([str(python), str(ROOT / 'scripts/install-ios-python-wheel.py'), str(wheel),
                    '--sha256', hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    '--library', str(base / platform / 'Library'),
                    '--frameworks', str(base / platform / 'Frameworks')]
                   + (['--simulator'] if args.simulator else []), check=True)


if __name__ == '__main__':
    main()
