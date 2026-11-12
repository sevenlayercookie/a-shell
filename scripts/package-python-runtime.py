#!/usr/bin/env python3
"""Package the source-built iOS Python runtime for a-Shell's terminal profile."""
import argparse
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def command(*args):
    subprocess.run([str(a) for a in args], check=True, stdout=subprocess.DEVNULL)

def framework(name, binary, directory, python_library='Python', platform='iPhoneOS'):
    dest = directory / (name + '.framework')
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, dest / name)
    info = {'CFBundleExecutable': name, 'CFBundleName': name,
            'CFBundleIdentifier': 'org.ashell.' + name.replace('_', '-'),
            'CFBundlePackageType': 'FMWK', 'CFBundleVersion': '1',
            'CFBundleShortVersionString': '3.13.1', 'MinimumOSVersion': '15.0',
            'CFBundleSupportedPlatforms': [platform]}
    (dest / 'Info.plist').write_bytes(plistlib.dumps(info))
    command('xcrun', 'install_name_tool', '-id', f'@rpath/{name}.framework/{name}', dest / name)
    if python_library != 'Python':
        command('xcrun', 'install_name_tool', '-change', '@rpath/Python.framework/Python',
                f'@rpath/{python_library}.framework/{python_library}', dest / name)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT / 'build/python')
    parser.add_argument('--install-resources', action='store_true')
    args = parser.parse_args()
    build = args.build.resolve()
    payload = build / 'payload'
    library = payload / 'Library'
    frameworks = payload / 'Frameworks'
    frameworks.mkdir(parents=True, exist_ok=True)
    installed = build / 'install/Frameworks'
    shutil.copytree(installed / 'lib/python3.13', library / 'lib/python3.13', dirs_exist_ok=True)
    framework('Python', installed / 'Python.framework/Python', frameworks)
    framework('pythonA', installed / 'Python.framework/Python', frameworks, 'pythonA')
    dynload = library / 'lib/python3.13/lib-dynload'
    for binary in (installed / 'lib/python3.13/lib-dynload').glob('*.so'):
        module = binary.name.split('.')[0]
        framework('Python-' + module, binary, frameworks)
        framework('PythonA' + module, binary, frameworks, 'pythonA')
        (dynload / binary.name.replace('.so', '.fwork')).write_text(
            f'Frameworks/Python-{module}.framework/Python-{module}\n')
        for prefix in ['Python-', 'PythonA']:
            name = prefix + module
            (frameworks / (name + '.framework') / (name + '.origin')).write_text(
                'Library/lib/python3.13/lib-dynload/' + binary.name.replace('.so', '.fwork') + '\n')
        (dynload / binary.name).unlink(missing_ok=True)
    # Console entry points must resolve the on-device interpreter, not the build Mac.
    bindir = library / 'bin'
    bindir.mkdir(exist_ok=True)
    source_bin = library / 'lib/python3.13/site-packages/bin'
    if source_bin.exists():
        for file in source_bin.iterdir():
            if file.is_file():
                text = file.read_text()
                if text.startswith('#!'):
                    text = '#!/usr/bin/env python3\n' + text.split('\n', 1)[1]
                (bindir / file.name).write_text(text)
                (bindir / file.name).chmod(0o755)
        shutil.rmtree(source_bin)
    for path in list(library.rglob('__pycache__')):
        shutil.rmtree(path)
    if args.install_resources:
        for resource in ['Resources_mini', 'Resources']:
            shutil.copytree(library, ROOT / resource / 'Library', dirs_exist_ok=True)
            shutil.copytree(frameworks, ROOT / resource / 'Frameworks', dirs_exist_ok=True)
    print(json.dumps({'python': '3.13.1+', 'frameworks': len(list(frameworks.glob('*.framework'))),
                      'payload': str(payload)}, indent=2))

if __name__ == '__main__':
    main()
