#!/usr/bin/env python3
"""Package upstream's consolidated SciPy layout and both interpreter copies."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SPECIALS = {'optimize/cython_optimize/_zeros', 'special/_ellip_harm_2',
            'special/_gufuncs', 'special/_special_ufuncs', 'special/_ufuncs_cxx', 'special/_ufuncs'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    build = base / ('scipy-simulator' if args.simulator else 'scipy-ios')
    if not (build / 'scipy.so').is_file():
        raise SystemExit('Build and consolidate SciPy first: ' + str(build))
    python = base / 'venv/bin/python'
    env = dict(os.environ, PATH=str(python.parent) + ':' + os.environ['PATH'])
    meson = ROOT / 'cpython/packages/numpy/vendored-meson/meson/meson.py'
    with (base / ('scipy-' + platform + '-install.log')).open('w') as log:
        subprocess.run([str(python), str(meson), 'install', '-C', str(build), '--no-rebuild'],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    options = json.loads((build / 'meson-info/intro-buildoptions.json').read_text())
    prefix = Path(next(item['value'] for item in options if item['name'] == 'prefix'))
    installed = next(prefix.rglob('site-packages/scipy/__init__.py')).parent
    payload = base / platform
    site = payload / 'Library/lib/python3.13/site-packages'
    shutil.copytree(installed, site / 'scipy', dirs_exist_ok=True)
    for info in installed.parent.glob('scipy-*.dist-info'):
        shutil.copytree(info, site / info.name, dirs_exist_ok=True)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    modules = [('scipy.scipy', build / 'scipy.so')]
    for name in sorted(SPECIALS):
        stem = build / 'scipy' / name
        modules.append(('scipy.' + name.replace('/', '.'), next(stem.parent.glob(stem.name + '.cpython*.so'))))
    for module, binary in modules:
        relative = Path(*module.split('.'))
        stub = relative.parent / (relative.name + '.cpython-313-' + sdk_name + '.fwork')
        for prefix, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
            name = prefix + module
            directory = payload / 'Frameworks'
            packaging.framework(name, binary, directory, interpreter,
                                'iPhoneSimulator' if args.simulator else 'iPhoneOS')
            framework = directory / (name + '.framework')
            (framework / (name + '.origin')).write_text('Library/lib/python3.13/site-packages/' + str(stub) + '\n')
            for license_path in [base / 'OpenBLAS-0.3.34/LICENSE', base / 'llvm-project/flang-rt/LICENSE.TXT']:
                if license_path.is_file():
                    shutil.copy2(license_path, framework / (license_path.parent.name + '-LICENSE.txt'))
    for binary in (site / 'scipy').rglob('*.so'):
        relative = binary.relative_to(site / 'scipy')
        stem = str(relative.with_name(binary.name.split('.')[0]))
        module = 'scipy.' + stem.replace('/', '.') if stem in SPECIALS else 'scipy.scipy'
        stub = binary.with_name(binary.name.split('.')[0] + '.cpython-313-' + sdk_name + '.fwork')
        stub.write_text('Frameworks/Python-' + module + '.framework/Python-' + module + '\n')
        binary.unlink()
    (site / 'scipy' / ('scipy.cpython-313-' + sdk_name + '.fwork')).write_text(
        'Frameworks/Python-scipy.scipy.framework/Python-scipy.scipy\n')
    for path in list((site / 'scipy').rglob('__pycache__')):
        shutil.rmtree(path)
    print('Packaged SciPy 1.16.1 for ' + platform)

if __name__ == '__main__':
    main()
