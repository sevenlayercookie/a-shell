#!/usr/bin/env python3
"""Stage selected native Python packages and the patched interpreter into the app resources."""
import argparse
import configparser
import csv
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = 'lib/python3.13/site-packages'
# The scoped profile: pure Python plus these distributions and their dependencies.
DEFAULT = ['numpy', 'cryptography', 'cffi', 'pycparser']

def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()

def replace(source, destination):
    if destination.is_dir():
        shutil.rmtree(destination)
    elif destination.exists():
        destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__'))
    else:
        shutil.copy2(source, destination)

def frameworks_for(stubs):
    """Each import stub names the Python framework; pythonA uses the PythonA twin."""
    names = set()
    for stub in stubs:
        name = Path(stub.read_text().strip()).name
        names.add(name)
        if name.startswith('Python-'):
            names.add('PythonA' + name[len('Python-'):])
    return names

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, default=ROOT / 'build/upstream-parity/device')
    parser.add_argument('--packages', nargs='+', default=DEFAULT)
    parser.add_argument('--resources', nargs='+', default=['Resources_mini', 'Resources'])
    parser.add_argument('--packages-only', action='store_true', help='leave the interpreter frameworks unchanged')
    args = parser.parse_args()
    stage = args.stage.resolve()
    site = stage / 'Library' / SITE
    entries, scripts, versions = set(), set(), {}
    for package in args.packages:
        found = [d for d in site.glob('*.dist-info')
                 if normalize(d.name[:-len('.dist-info')].rsplit('-', 1)[0]) == normalize(package)]
        if len(found) != 1:
            raise SystemExit(f'Expected one staged distribution for {package}, found {len(found)}')
        info = found[0]
        versions[package] = info.name[:-len('.dist-info')].rsplit('-', 1)[1]
        with (info / 'RECORD').open(newline='') as stream:
            for row in csv.reader(stream):
                top = Path(row[0]).parts[0]
                if top == '..':
                    continue
                # Native modules are installed as framework import stubs.
                top = re.sub(r'\.(so|dylib)$', '.fwork', top)
                if (site / top).exists():
                    entries.add(top)
        points = configparser.ConfigParser()
        points.read(info / 'entry_points.txt')
        if points.has_section('console_scripts'):
            scripts.update(points['console_scripts'])
    stubs = [stub for entry in entries for stub in
             ([site / entry] if entry.endswith('.fwork') else (site / entry).rglob('*.fwork'))]
    core = stage / 'Library/lib/python3.13/lib-dynload'
    frameworks = frameworks_for(stubs)
    if not args.packages_only:
        frameworks |= frameworks_for(core.glob('*.fwork')) | {'Python.framework', 'pythonA.framework'}
    frameworks = {name if name.endswith('.framework') else name + '.framework' for name in frameworks}
    missing = sorted(name for name in frameworks if not (stage / 'Frameworks' / name).is_dir())
    if missing:
        raise SystemExit('Staged frameworks missing: ' + ', '.join(missing))
    for resource in args.resources:
        base = ROOT / resource
        for entry in sorted(entries):
            replace(site / entry, base / 'Library' / SITE / entry)
        for script in sorted(scripts):
            replace(stage / 'Library/bin' / script, base / 'Library/bin' / script)
        for name in sorted(frameworks):
            replace(stage / 'Frameworks' / name, base / 'Frameworks' / name)
    print(json.dumps({'packages': versions, 'frameworks': sorted(frameworks),
                      'scripts': sorted(scripts), 'resources': args.resources}, indent=2))

if __name__ == '__main__':
    main()
