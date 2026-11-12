#!/usr/bin/env python3
"""Audit a full a-Shell app against upstream project inputs, without exclusions."""
import argparse
import json
import plistlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['a-Shell', 'a-Shell-mini'], default='a-Shell')
    parser.add_argument('--app', type=Path, help='Audit a built app instead of source framework inputs')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    project = json.loads(subprocess.check_output(['plutil', '-convert', 'json', '-o', '-',
                         str(ROOT / 'a-Shell.xcodeproj/project.pbxproj')]))
    objects = project['objects']
    target = next(x for x in objects.values() if x.get('isa') == 'PBXNativeTarget' and x.get('name') == args.target)
    required = {}
    for key in target['buildPhases']:
        phase = objects[key]
        if phase['isa'] != 'PBXCopyFilesBuildPhase':
            continue
        for key in phase.get('files', []):
            ref = objects.get(objects[key].get('fileRef'), {})
            path = Path(ref.get('path', ''))
            if path.suffix not in ['.framework', '.xcframework']:
                continue
            name = path.stem + '.framework'
            required[name] = str(path)
    resource = 'Resources' if args.target == 'a-Shell' else 'Resources_mini'
    expected_commands = plistlib.loads((ROOT / resource / 'commandDictionary.plist').read_bytes())
    app = args.app.resolve() if args.app else None
    missing_frameworks = [name for name, path in sorted(required.items())
                          if not ((app / 'Frameworks' / name) if app else ROOT / path).exists()]
    missing_commands = []
    missing_module_stubs = []
    if app:
        commands = plistlib.loads((app / 'commandDictionary.plist').read_bytes())
        missing_commands = [name for name, value in expected_commands.items() if commands.get(name) != value]
        # Every upstream native module needs its import stub as well as a framework.
        modules = [name.removeprefix('Python-').removesuffix('.framework') for name in required if name.startswith('Python-')]
        library = app / 'Library/lib/python3.13'
        for module in modules:
            relative = Path(*module.split('.'))
            candidates = [library / 'site-packages' / relative, library / 'lib-dynload' / relative]
            if not any(list(path.parent.glob(path.name + '*.fwork')) for path in candidates):
                # Upstream sometimes combines extension entry points in one framework.
                binaries = list((library / 'site-packages').rglob('*.fwork'))
                if not any(module in p.read_text() for p in binaries):
                    missing_module_stubs.append(module)
    report = {'target': args.target, 'app': str(app) if app else None,
              'requiredFrameworks': required, 'requiredCommandCount': len(expected_commands),
              'missingFrameworks': missing_frameworks, 'missingCommands': missing_commands,
              'missingModuleStubs': missing_module_stubs}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'requiredFrameworks'}, indent=2))
    raise SystemExit(bool(missing_frameworks or missing_commands or missing_module_stubs))

if __name__ == '__main__':
    main()
