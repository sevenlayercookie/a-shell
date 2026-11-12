#!/usr/bin/env python3
"""Package both upstream Crypto namespaces as native iOS frameworks."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    platform = 'simulator' if args.simulator else 'device'
    target = 'iphonesimulator' if args.simulator else 'iphoneos'
    source = base / 'pycryptodome-3.23.0'
    payload = base / platform
    site = payload / 'Library/lib/python3.13/site-packages'
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    for namespace in ['Crypto', 'Cryptodome']:
        build = base / (namespace.lower() + '-' + platform + '-build')
        if not build.exists() and namespace == 'Crypto':
            build = base / ('pycryptodome-' + platform + '-build')
        installed = next(build.rglob(namespace + '/__init__.py')).parent
        shutil.copytree(installed, site / namespace, dirs_exist_ok=True)
        for binary in (site / namespace).rglob('*.so'):
            relative = binary.relative_to(site)
            module = '.'.join((*relative.parts[:-1], binary.name.split('.')[0]))
            stub = binary.with_name(binary.name.split('.')[0] + '.cpython-313-' + target + '.fwork')
            stub.write_text('Frameworks/Python-' + module + '.framework/Python-' + module + '\n')
            for prefix, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
                name = prefix + module
                frameworks = payload / 'Frameworks'
                packaging.framework(name, binary, frameworks, interpreter,
                                    'iPhoneSimulator' if args.simulator else 'iPhoneOS')
                (frameworks / (name + '.framework') / (name + '.origin')).write_text(
                    'Library/lib/python3.13/site-packages/' + str(stub.relative_to(site)) + '\n')
            binary.unlink()
        api = site / namespace / 'Util/_raw_api.py'
        text = api.read_text()
        text = text.replace('    split = name.split(".")', '''    if sys.platform == "ios":
        executable = os.path.basename(sys.orig_argv[0])
        suffix = executable[len("python"):] if executable.startswith("python") else ""
        prefix = "Python" + suffix if suffix.isalpha() else "Python-"
        framework = prefix + name
        path = os.path.join(os.path.dirname(sys.prefix), "Frameworks", framework + ".framework", framework)
        return load_lib(path, cdecl)
    split = name.split(".")''')
        api.write_text(text)
        marker = source / '.separate_namespace'
        if namespace == 'Cryptodome':
            marker.touch()
        else:
            marker.unlink(missing_ok=True)
        python = base / 'venv/bin/python'
        with (base / (namespace.lower() + '-' + platform + '-metadata.log')).open('w') as log:
            subprocess.run([str(python), 'setup.py', 'dist_info', '--output-dir', str(site)], cwd=source,
                           env=dict(os.environ, PATH=str(python.parent) + ':' + os.environ['PATH']),
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        for path in list((site / namespace).rglob('__pycache__')):
            shutil.rmtree(path)
        print('Packaged ' + namespace + ' 3.23.0 for ' + platform)

if __name__ == '__main__':
    main()
