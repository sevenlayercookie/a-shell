#!/usr/bin/env python3
"""Build the isolated UIKit harness against the staged native Python packages."""
import argparse
import importlib.util
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
IDENTIFIER = 'sevenlayercookie.a-Shell-mini.PythonSmoke'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packages', nargs='+',
                        help='build from the shipping Resources_mini payload plus only these staged native distributions')
    parser.add_argument('--commands', type=Path, help='command list replacing the built-in checks')
    args = parser.parse_args()
    base = ROOT / 'build/python/smoke-simulator'
    app = base / 'PythonSmoke.app'
    shutil.rmtree(app, ignore_errors=True)
    frameworks = app / 'Frameworks'
    frameworks.mkdir(parents=True)
    stage = ROOT / 'build/upstream-parity'
    if args.packages:
        shutil.copytree(ROOT / 'Resources_mini/Library', app / 'Library')
        subprocess.run([sys.executable, str(ROOT / 'scripts/stage-python-native-packages.py'), '--stage',
                        str(stage / 'simulator'), '--resources', str(app), '--packages-only',
                        '--packages', *args.packages],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        for platform in ['device', 'simulator']:
            shutil.copytree(stage / platform / 'Library', app / 'Library', dirs_exist_ok=True)
    installed = ROOT / 'build/python/simulator-install/Frameworks'
    for path in (installed / 'lib/python3.13').glob('_sysconfigdata*.py'):
        shutil.copy2(path, app / 'Library/lib/python3.13' / path.name)
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    for name in ['Python', 'pythonA']:
        packaging.framework(name, installed / 'Python.framework/Python', frameworks, name, 'iPhoneSimulator')
    for framework in (stage / 'simulator/Frameworks').glob('*.framework'):
        if not args.packages and framework.name not in {'Python.framework', 'pythonA.framework', 'ios_system.framework'}:
            shutil.copytree(framework, frameworks / framework.name)
    deps = ROOT / 'build/python/simulator-deps'
    shutil.copytree(deps / 'ios_system.framework', frameworks / 'ios_system.framework')
    commands = plistlib.loads((ROOT / 'Resources_mini/commandDictionary.plist').read_bytes())
    commands['pythonA'] = ['pythonA.framework/pythonA', 'Py_BytesMain', '3bBc:dEhiJm:OQ:RsStuUvVW:xX?', 'file']
    (app / 'commandDictionary.plist').write_bytes(plistlib.dumps(commands))
    if args.commands:
        shutil.copy2(args.commands, app / 'smoke-commands.txt')
    info = {
        'CFBundleIdentifier': IDENTIFIER, 'CFBundleExecutable': 'PythonSmoke',
        'CFBundleName': 'PythonSmoke', 'CFBundlePackageType': 'APPL',
        'CFBundleVersion': '1', 'CFBundleShortVersionString': '1.0',
        'CFBundleSupportedPlatforms': ['iPhoneSimulator'], 'MinimumOSVersion': '15.0',
        'UIDeviceFamily': [1, 2], 'UILaunchScreen': {},
        'UIApplicationSceneManifest': {'UIApplicationSupportsMultipleScenes': False,
            'UISceneConfigurations': {'UIWindowSceneSessionRoleApplication': [
                {'UISceneConfigurationName': 'Default', 'UISceneDelegateClassName': 'PythonSmokeDelegate'}]}},
    }
    (app / 'Info.plist').write_bytes(plistlib.dumps(info))
    sdk = subprocess.check_output(['xcrun', '--sdk', 'iphonesimulator', '--show-sdk-path'], text=True).strip()
    subprocess.run(['xcrun', 'clang', '-target', 'arm64-apple-ios15.0-simulator', '-isysroot', sdk,
                    '-fobjc-arc', '-framework', 'UIKit', '-framework', 'Foundation', '-F' + str(deps),
                    '-framework', 'ios_system', '-Wl,-rpath,@executable_path/Frameworks',
                    str(ROOT / 'tests/python-runtime-smoke.m'), '-o', str(app / 'PythonSmoke')], check=True)
    for framework in frameworks.glob('*.framework'):
        subprocess.run(['codesign', '--force', '--sign', '-', str(framework)], capture_output=True, check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', str(app)], capture_output=True, check=True)
    print(app)


if __name__ == '__main__':
    main()
