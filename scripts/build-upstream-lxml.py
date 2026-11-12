#!/usr/bin/env python3
"""Build the upstream lxml package for a-Shell's device or Simulator Python."""
import argparse
import hashlib
import os
import importlib.util
import shutil
from pathlib import Path
import shlex
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VERSION = '6.1.3'
URL = 'https://files.pythonhosted.org/packages/23/ad/28ecd7cb894d172f3c9c80a075eeeb2017ac62e3632cee05a5f9493547eb/lxml-6.1.3.tar.gz'
SHA256 = '45222d94ddd511536f3b2f7d9deae3b2339b4ce0f075f1ca25703b07cad9dd21'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator', action='store_true')
    args = parser.parse_args()
    base = ROOT / 'build/upstream-parity'
    archive = base / f'lxml-{VERSION}.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit('lxml source checksum mismatch')
    source = base / f'lxml-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(base, filter='data')
    sdk_name = 'iphonesimulator' if args.simulator else 'iphoneos'
    platform = 'simulator' if args.simulator else 'device'
    triple = 'arm64-apple-ios15.0' + ('-simulator' if args.simulator else '')
    sdk = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path'], text=True).strip()
    python = base / 'venv/bin/python'
    config = ROOT / ('build/python/simulator' if args.simulator else 'build/python/ios')
    deps = ROOT / ('build/python/simulator-deps' if args.simulator else 'build/python/deps')
    flags = shlex.join(['-target', triple, '-isysroot', sdk, '-I' + str(config),
                        '-I' + str(ROOT / 'cpython/Include'), '-I' + str(ROOT / 'build/python/deps/include'), '-O2', '-DCYTHON_PEP489_MULTI_PHASE_INIT=1', '-DCYTHON_USE_MODULE_STATE=1', '-DCYTHON_USE_TYPE_SPECS=1',
                        '-DCYTHON_USE_DICT_VERSIONS=0', '-DCYTHON_USE_PYTYPE_LOOKUP=0'])
    linker = shlex.join(['xcrun', '--sdk', sdk_name, 'clang', '-target', triple, '-isysroot', sdk,
                         '-dynamiclib', '-undefined', 'error', '-F' + str(base / platform / 'Frameworks'),
                         '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system',
                         '-llzma', '-liconv', '-lz'])
    env = dict(os.environ, SDKROOT=sdk, CC=f'xcrun --sdk {sdk_name} clang', CFLAGS=flags, CPPFLAGS=flags,
               LDSHARED=linker, _PYTHON_HOST_PLATFORM='ios-15.0-arm64-' + sdk_name)
    subprocess.run([str(python), str(ROOT / 'scripts/prepare-cython-reentry.py'), '--python', str(python)], check=True)
    build = base / ('lxml-' + platform + '-build')
    build.mkdir(parents=True, exist_ok=True)
    xml = base / ('xml-' + platform + '-install')
    if not (xml / 'lib/libxslt.a').is_file():
        raise SystemExit('Build scripts/build-ios-xml.py for this platform first')
    tools = [xml / 'bin/xml2-config', xml / 'bin/xslt-config']
    for temporary in build.glob('temp.*'):
        shutil.rmtree(temporary)
    for source_file in (source / 'src/lxml').rglob('*'):
        if source_file.suffix in {'.pyx', '.py'}:
            source_file.touch()
    dist = build / 'dist'
    with (base / ('lxml-' + platform + '-build.log')).open('w') as log:
        subprocess.run([str(python), 'setup.py', 'build', '--build-base', str(build),
                        'build_ext', '--force', '--with-cython', '--with-xml2-config=' + str(tools[0]),
                        '--with-xslt-config=' + str(tools[1]), 'bdist_wheel', '--plat-name', 'ios_15_0_arm64_' + sdk_name,
                        '--dist-dir', str(dist)], cwd=source, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    wheel = next(dist.glob('*.whl'))
    subprocess.run([str(python), str(ROOT / 'scripts/install-ios-python-wheel.py'), str(wheel),
                    '--sha256', hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    '--library', str(base / platform / 'Library'),
                    '--frameworks', str(base / platform / 'Frameworks'),
                    '--consolidated-module', 'lxml.lxml']
                   + (['--simulator'] if args.simulator else []), check=True)
    # One library must own the XML callbacks shared by all lxml extensions.
    # Re-exporting independently linked extension libraries does not isolate
    # libxml2's callbacks between the two Python runtimes.
    objects = list(build.glob('temp.*/**/*.o'))
    combined = build / 'lxml.so'
    command = ['xcrun', '--sdk', sdk_name, 'clang', '-target', triple, '-isysroot', sdk,
               '-dynamiclib', '-undefined', 'error', '-F' + str(base / platform / 'Frameworks'),
               '-framework', 'Python', '-F' + str(deps), '-framework', 'ios_system',
               *map(str, objects), str(xml / 'lib/libexslt.a'), str(xml / 'lib/libxslt.a'),
               str(xml / 'lib/libxml2.a'), '-lz', '-llzma', '-liconv', '-lm', '-o', str(combined)]
    with (base / ('lxml-' + platform + '-consolidate.log')).open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    symbols = subprocess.check_output(['xcrun', 'nm', '-gU', str(combined)], text=True)
    with zipfile.ZipFile(wheel) as package:
        required = {'_PyInit_' + Path(name).name.split('.')[0]
                    for name in package.namelist() if name.endswith('.so')}
    missing = required - {line.split()[-1] for line in symbols.splitlines() if line.split()}
    if missing:
        raise SystemExit('Consolidated lxml is missing extension entry points: ' + ', '.join(sorted(missing)))
    spec = importlib.util.spec_from_file_location('python_packaging', ROOT / 'scripts/package-python-runtime.py')
    packaging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packaging)
    frameworks = base / platform / 'Frameworks'
    for prefix, interpreter in [('Python-', 'Python'), ('PythonA', 'pythonA')]:
        packaging.framework(prefix + 'lxml.lxml', combined, frameworks, interpreter,
                            'iPhoneSimulator' if args.simulator else 'iPhoneOS')
        for name in ['libxml2-2.9.13', 'libxslt-1.1.35']:
            license_path = base / name / 'Copyright'
            if license_path.exists():
                shutil.copy2(license_path, frameworks / (prefix + 'lxml.lxml.framework') / (name + '-Copyright'))
    with zipfile.ZipFile(wheel) as package:
        for name in package.namelist():
            if not name.endswith('.so'):
                continue
            relative = Path(name)
            module = '.'.join((*relative.parts[:-1], relative.name.split('.')[0]))
            for prefix in ['Python-', 'PythonA']:
                shutil.rmtree(frameworks / (prefix + module + '.framework'))
    # lxml moved this upstream API into a separate pure Python distribution.
    clean_wheel = base / 'wheels/lxml_html_clean-0.4.6-py3-none-any.whl'
    if not clean_wheel.exists():
        urllib.request.urlretrieve('https://files.pythonhosted.org/packages/f5/36/4898b5e3951635846ed0e445e042fadf02b7c5e811a9e43da5b3557bc8d2/lxml_html_clean-0.4.6-py3-none-any.whl', clean_wheel)
    if hashlib.sha256(clean_wheel.read_bytes()).hexdigest() != 'cc037270ba500a65e7235409dcddcae8ef37300f26dea826b61d917bf0236880':
        raise SystemExit('lxml_html_clean wheel checksum mismatch')
    with zipfile.ZipFile(clean_wheel) as package:
        if any(name.endswith(('.so', '.dylib')) for name in package.namelist()):
            raise SystemExit('Expected a pure Python HTML cleaner wheel')
        package.extractall(base / platform / 'Library/lib/python3.13/site-packages')
    print('Packaged consolidated lxml with interpreter-local XML libraries')


if __name__ == '__main__':
    main()
