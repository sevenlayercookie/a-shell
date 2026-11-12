#!/usr/bin/env python3
"""Use upstream a-Shell's pybind11 fork without modifying the host environment."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
REVISION = '86eaeb338d7211c6d687ad27a66eae55855bd6ad'


def environment(python):
    source = ROOT / 'cpython/packages/pybind11'
    if not (source / 'include/pybind11/pybind11.h').exists():
        raise SystemExit('Initialize the pinned cpython/packages/pybind11 submodule first')
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise SystemExit('Unexpected upstream pybind11 revision: ' + revision)
    prefix = ROOT / 'build/upstream-parity/pybind11-host'
    stamp = prefix / '.ashell-source-revision'
    if not stamp.exists() or stamp.read_text().strip() != REVISION:
        with (prefix.parent / 'pybind11-host-build.log').open('w') as log:
            subprocess.run([str(python), '-m', 'pip', 'install', '--upgrade', '--no-deps',
                            '--no-build-isolation', '--target', str(prefix), str(source)],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        stamp.write_text(REVISION + '\n')
    return dict(os.environ, PATH=str(prefix / 'bin') + ':' + str(python.parent) + ':' + os.environ['PATH'],
                PYTHONPATH=str(prefix) + (':' + os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else ''))


if __name__ == '__main__':
    python = ROOT / 'build/upstream-parity/venv/bin/python'
    env = environment(python)
    subprocess.run([str(python), '-c', 'import pybind11; print(pybind11.__version__, pybind11.get_include())'],
                   env=env, check=True)
