#!/usr/bin/env python3
"""Rebuild existing iOS Python configurations with persistent type-cache IDs."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    patch = ['patch', '--batch', '-p1', '-i', str(ROOT / 'patches/cpython-preserve-type-version-tags.patch')]
    source = ROOT / 'cpython'
    if subprocess.run([*patch, '--forward', '--dry-run'], cwd=source, capture_output=True).returncode == 0:
        subprocess.run([*patch, '--forward'], cwd=source, check=True)
    elif subprocess.run([*patch, '--reverse', '--dry-run'], cwd=source, capture_output=True).returncode:
        raise SystemExit('CPython reentry patch does not match source')
    base = ROOT / 'build/python'
    build = base / ('simulator' if args.simulator else 'ios')
    installed = base / ('simulator-install' if args.simulator else 'install') / 'Frameworks/Python.framework/Python'
    subprocess.run(['make', '-C', str(build), '-j2'], check=True)
    shutil.copy2(build / 'Python.framework/Python', installed)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    stage = ROOT / 'build/upstream-parity' / ('simulator' if args.simulator else 'device') / 'Frameworks'
    for name in ['Python', 'pythonA']:
        packaging.framework(name, installed, stage, name, 'iPhoneSimulator' if args.simulator else 'iPhoneOS')


if __name__ == '__main__':
    main()
