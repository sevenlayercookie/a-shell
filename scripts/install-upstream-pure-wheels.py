#!/usr/bin/env python3
"""Install checksum-pinned pure Python upstream dependencies into both payloads."""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

from python_packaging_utils import install_console_scripts

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=ROOT / 'scripts/python-upstream-pure-wheels.json')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    cache = base / 'wheels'
    cache.mkdir(parents=True, exist_ok=True)
    for entry in json.loads(args.lock.read_text())['wheels']:
        wheel = cache / entry['filename']
        if not wheel.exists():
            urllib.request.urlretrieve(entry['url'], wheel)
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != entry['sha256']:
            raise SystemExit('Pure wheel checksum mismatch: ' + wheel.name)
        if not wheel.name.endswith('-none-any.whl'):
            raise SystemExit('Expected a pure Python wheel: ' + wheel.name)
        with zipfile.ZipFile(wheel) as package:
            if any(name.endswith(('.so', '.dylib')) for name in package.namelist()):
                raise SystemExit('Unexpected native code in pure wheel: ' + wheel.name)
            metadata = next(name.split('/')[0] for name in package.namelist() if name.endswith('.dist-info/METADATA'))
            project = metadata.removesuffix('.dist-info').rsplit('-', 1)[0]
            for platform in ['device', 'simulator']:
                library = base / platform / 'Library'
                site = library / 'lib/python3.13/site-packages'
                for previous in site.glob(project + '-*.dist-info'):
                    if previous.name != metadata:
                        shutil.rmtree(previous)
                package.extractall(site)
                config = configparser.ConfigParser(interpolation=None)
                config.optionxform = str
                config.read(site / metadata / 'entry_points.txt')
                for group in ['console_scripts', 'gui_scripts']:
                    if config.has_section(group):
                        install_console_scripts(dict(config[group]), library)
        print('Installed ' + entry['name'] + ' ' + entry['version'])


if __name__ == '__main__':
    main()
