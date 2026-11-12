#!/usr/bin/env python3
"""Install an iOS wheel and wrap native extensions for both a-Shell interpreters."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--library', required=True, type=Path)
    parser.add_argument('--frameworks', required=True, type=Path)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    if hashlib.sha256(args.wheel.read_bytes()).hexdigest() != args.sha256:
        parser.error('wheel checksum mismatch')
    target = 'iphonesimulator' if args.simulator else 'iphoneos'
    if 'arm64_' + target not in args.wheel.name:
        parser.error('wheel does not match the requested arm64 iOS platform')
    site = args.library.resolve() / 'lib/python3.13/site-packages'
    frameworks = args.frameworks.resolve()
    site.mkdir(parents=True, exist_ok=True)
    frameworks.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ashell-wheel-') as directory:
        unpacked = Path(directory)
        with zipfile.ZipFile(args.wheel) as archive:
            archive.extractall(unpacked)
        native = list(unpacked.rglob('*.so'))
        if list(unpacked.rglob('*.dylib')):
            parser.error('wheel has auxiliary dylibs; package their dependencies explicitly first')
        for binary in native:
            relative = binary.relative_to(unpacked)
            module = '.'.join((*relative.parts[:-1], relative.name.split('.')[0]))
            base = relative.name.split('.')[0]
            stub = relative.parent / (base + '.cpython-313-' + target + '.fwork')
            (binary.parent / stub.name).write_text('Frameworks/Python-' + module + '.framework/Python-' + module + '\n')
            for prefix, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
                name = prefix + module
                packaging.framework(name, binary, frameworks, interpreter,
                                    'iPhoneSimulator' if args.simulator else 'iPhoneOS')
                (frameworks / (name + '.framework') / (name + '.origin')).write_text(
                    'Library/lib/python3.13/site-packages/' + str(stub) + '\n')
            binary.unlink()
        for path in unpacked.iterdir():
            if path.is_dir():
                shutil.copytree(path, site / path.name, dirs_exist_ok=True)
            else:
                shutil.copy2(path, site / path.name)
    print(args.wheel.name + ': installed ' + str(len(native)) + ' native modules for both interpreters')

if __name__ == '__main__':
    main()
