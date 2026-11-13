#!/usr/bin/env python3
"""Build upstream's portable PyYAML backend and install it in both payloads."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://files.pythonhosted.org/packages/05/8e/961c0007c59b8dd7729d542c61a4d537767a59645b82a0b521206e1e25c2/pyyaml-6.0.3.tar.gz'
SHA256 = 'd76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f'


def main():
    base = ROOT / 'build/upstream-parity'
    archive = base / 'pyyaml-6.0.3.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('PyYAML source checksum mismatch')
    source = base / 'pyyaml-6.0.3'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    python = base / 'venv/bin/python'
    dist = base / 'pyyaml-pure-dist'
    subprocess.run([str(python), 'setup.py', '--without-libyaml', 'bdist_wheel',
                    '--dist-dir', str(dist)], cwd=source, env=dict(os.environ, PYYAML_FORCE_LIBYAML='0'), check=True)
    wheel = next(dist.glob('*-none-any.whl'))
    lock = base / 'pyyaml-pure-wheel.json'
    lock.write_text(json.dumps({'wheels': [dict(name='PyYAML', version='6.0.3',
                    filename=wheel.name, url=wheel.as_uri(),
                    sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())]}))
    subprocess.run([str(python), str(ROOT / 'scripts/install-upstream-pure-wheels.py'),
                    '--lock', str(lock)], check=True)


if __name__ == '__main__':
    main()
