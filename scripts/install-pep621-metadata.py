#!/usr/bin/env python3
"""Preserve upstream distribution metadata when packaging Meson native builds."""
import argparse
import base64
import configparser
import csv
import hashlib
from pathlib import Path
import re
import shutil
import tomllib

from pyproject_metadata import StandardMetadata
from python_packaging_utils import install_console_scripts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--simulator', action='store_true')
    parser.add_argument('--package', action='append', default=[])
    parser.add_argument('--version', help='Version resolved by the upstream build')
    parser.add_argument('--require', action='append', default=[], help='Runtime dependency selected by this build variant')
    args = parser.parse_args()
    data = tomllib.loads((args.source / 'pyproject.toml').read_text())
    if args.version:
        data['project']['version'] = args.version
        data['project']['dynamic'] = [key for key in data['project'].get('dynamic', []) if key != 'version']
    if args.require:
        data['project']['dependencies'] = list(data['project'].get('dependencies', [])) + args.require
    metadata = StandardMetadata.from_pyproject(data, project_dir=args.source)
    if metadata.version is None:
        raise SystemExit('Resolve the upstream dynamic version before installing metadata')
    name = re.sub(r'[-_.]+', '_', metadata.name)
    directory = args.site / (name + '-' + str(metadata.version) + '.dist-info')
    for previous in args.site.glob(name + '-*.dist-info'):
        if previous != directory:
            shutil.rmtree(previous)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'METADATA').write_bytes(metadata.as_rfc822().as_bytes())
    platform = 'iphonesimulator' if args.simulator else 'iphoneos'
    (directory / 'WHEEL').write_text('Wheel-Version: 1.0\nGenerator: a-shell\nRoot-Is-Purelib: false\n'
                                   + 'Tag: cp313-cp313-ios_15_0_arm64_' + platform + '\n')
    (directory / 'INSTALLER').write_text('a-shell\n')
    for pattern in ['LICENSE*', 'COPYING*', 'NOTICE*', *data['project'].get('license-files', [])]:
        for license_path in args.source.glob(pattern):
            destination = directory / 'licenses' / license_path.relative_to(args.source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if license_path.is_dir():
                shutil.copytree(license_path, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(license_path, destination)
    entrypoints = configparser.ConfigParser(interpolation=None)
    entrypoints.optionxform = str
    for group, values in metadata.entrypoints.items():
        entrypoints[group] = values
    if metadata.scripts:
        entrypoints['console_scripts'] = metadata.scripts
    if metadata.gui_scripts:
        entrypoints['gui_scripts'] = metadata.gui_scripts
    install_console_scripts(metadata.scripts | metadata.gui_scripts, args.site.parents[2])
    if entrypoints.sections():
        with (directory / 'entry_points.txt').open('w') as output:
            entrypoints.write(output)
    files = list(directory.rglob('*'))
    for package in args.package or [name]:
        path = args.site / package
        files.extend(path.rglob('*') if path.is_dir() else [path])
    with (directory / 'RECORD').open('w', newline='') as output:
        writer = csv.writer(output)
        for path in sorted(set(files)):
            if not path.is_file() or path.name == 'RECORD' or '__pycache__' in path.parts:
                continue
            content = path.read_bytes()
            digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
            writer.writerow([str(path.relative_to(args.site)), 'sha256=' + digest, len(content)])
        writer.writerow([str((directory / 'RECORD').relative_to(args.site)), '', ''])


if __name__ == '__main__':
    main()
