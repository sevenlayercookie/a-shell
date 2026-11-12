#!/usr/bin/env python3
"""Repair legacy frameworks and normalize signed distribution archive metadata."""
import argparse
import plistlib
import re
import subprocess
from pathlib import Path


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--identity', required=True, help='Installed distribution signing identity')
    args = parser.parse_args()
    metadata = plistlib.loads((args.archive / 'Info.plist').read_bytes())
    app = args.archive / 'Products' / metadata['ApplicationProperties']['ApplicationPath']
    app_info = plistlib.loads((app / 'Info.plist').read_bytes())
    # Xcode can preserve the signature identifier of an unsigned framework binary
    # (for example "pico") instead of its framework's CFBundleIdentifier.
    # Re-sign the framework bundle with its declared identifier explicitly.
    framework = app / 'Frameworks/libssh2.framework'
    binary = framework / 'libssh2'
    info_path = framework / 'Info.plist'
    info = plistlib.loads(info_path.read_bytes())
    build = run('xcrun', 'vtool', '-arch', 'arm64', '-show-build', str(binary))
    sdk = re.search(r'^\s+sdk\s+([0-9.]+)\s*$', build, re.MULTILINE)
    minimum = re.search(r'^\s+minos\s+([0-9.]+)\s*$', build, re.MULTILINE)
    if not sdk or not minimum:
        raise RuntimeError('Cannot determine libssh2 SDK and deployment target; archive was not changed')
    architectures = run('xcrun', 'lipo', '-archs', str(binary)).split()
    if 'arm64e' in architectures and int(sdk[1].split('.')[0]) < 26:
        temporary = binary.with_suffix('.arm64')
        subprocess.run(['xcrun', 'lipo', str(binary), '-remove', 'arm64e', '-output', str(temporary)], check=True)
        temporary.replace(binary)
        print('Removed unsupported legacy arm64e slice; retained arm64')
    if info.get('MinimumOSVersion') == 'ios_version_min':
        info['MinimumOSVersion'] = minimum[1]
        info_path.write_bytes(plistlib.dumps(info))
        print('Set libssh2 MinimumOSVersion to its binary deployment target:', minimum[1])
    for bundle in sorted((app / 'Frameworks').glob('*.framework')):
        info = plistlib.loads((bundle / 'Info.plist').read_bytes())
        subprocess.run(['codesign', '--force', '--sign', args.identity,
                        '--identifier', info['CFBundleIdentifier'],
                        '--preserve-metadata=entitlements,flags',
                        '--generate-entitlement-der', str(bundle)], check=True)
    for bundle in sorted(app.rglob('*.appex')):
        path = bundle / 'Info.plist'
        info = plistlib.loads(path.read_bytes())
        info['CFBundleShortVersionString'] = app_info['CFBundleShortVersionString']
        info['CFBundleVersion'] = app_info['CFBundleVersion']
        path.write_bytes(plistlib.dumps(info))
        subprocess.run(['codesign', '--force', '--sign', args.identity,
                        '--preserve-metadata=identifier,entitlements,flags',
                        '--generate-entitlement-der', str(bundle)], check=True)
    subprocess.run(['codesign', '--force', '--sign', args.identity,
                    '--preserve-metadata=identifier,entitlements,flags',
                    '--generate-entitlement-der', str(app)], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    for bundle in sorted((app / 'Frameworks').glob('*.framework')):
        declared = plistlib.loads((bundle / 'Info.plist').read_bytes())['CFBundleIdentifier']
        signed = subprocess.run(['codesign', '-d', '--verbose=2', str(bundle)],
                                capture_output=True, text=True, check=True).stderr
        if not re.search(r'^Identifier=' + re.escape(declared) + r'$', signed, re.MULTILINE):
            raise RuntimeError('Framework signature identifier mismatch: ' + str(bundle))
    print('Archive signatures verified')


if __name__ == '__main__':
    main()
