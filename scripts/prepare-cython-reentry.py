#!/usr/bin/env python3
"""Apply a-Shell's Cython module-state reload fix to the build environment."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def prepare(python):
    location = subprocess.check_output(
        [str(python), '-c', 'import Cython; print(Cython.__path__[0])'], text=True).strip()
    parent = Path(location).parent
    for name in ('cython-reinitialize-module-state.patch', 'cython-module-state-nogil.patch'):
        patch = ROOT / 'patches' / name
        command = ['patch', '--batch', '-p1', '-i', str(patch)]
        check = subprocess.run([*command, '--forward', '--dry-run'], cwd=parent,
                               capture_output=True, text=True)
        if check.returncode == 0:
            subprocess.run([*command, '--forward'], cwd=parent, check=True)
        else:
            reverse = subprocess.run([*command, '--reverse', '--dry-run'], cwd=parent,
                                     capture_output=True, text=True)
            if reverse.returncode:
                raise SystemExit('Cython patch does not match this build environment: ' + name + '\n' + check.stdout + check.stderr)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, default=ROOT / 'build/upstream-parity/venv/bin/python')
    prepare(parser.parse_args().python)
