#!/usr/bin/env python3
"""Generate Python-enabled app targets with the terminal-first dependency profile."""
import hashlib
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    source = ROOT / 'a-Shell.xcodeproj'
    destination = ROOT / 'a-Shell-Python.xcodeproj'
    build = ROOT / 'build/python'
    build.mkdir(parents=True, exist_ok=True)
    for required in ['Resources_mini/Frameworks/Python.framework/Python',
                     'Resources_mini/Frameworks/pythonA.framework/pythonA',
                     'Resources_mini/Library/lib/python3.13/site-packages/IPython/__init__.py']:
        if not (ROOT / required).is_file():
            raise SystemExit('Missing Python payload: ' + required + '; run the Python build/package scripts first')
    raw = subprocess.check_output(['plutil', '-convert', 'json', '-o', '-', str(source / 'project.pbxproj')])
    project = json.loads(raw)
    objects = project['objects']
    parent = {child: key for key, obj in objects.items() if obj.get('isa') in ['PBXGroup', 'PBXVariantGroup']
              for child in obj.get('children', [])}
    def location(key):
        obj = objects.get(key, {})
        if obj.get('sourceTree') in ['SDKROOT', 'BUILT_PRODUCTS_DIR']:
            return None
        relative = Path(obj.get('path', ''))
        direct = ROOT / relative
        if relative != Path('.') and direct.exists():
            return direct
        if obj.get('sourceTree') == 'SOURCE_ROOT':
            return direct
        group = parent.get(key)
        return (location(group) or ROOT) / relative if group else direct
    removed = {}
    for obj in objects.values():
        if obj.get('isa') not in ['PBXCopyFilesBuildPhase', 'PBXFrameworksBuildPhase', 'PBXResourcesBuildPhase']:
            continue
        retained = []
        for build_file in obj.get('files', []):
            reference = objects.get(build_file, {}).get('fileRef')
            file = objects.get(reference, {})
            path = location(reference)
            if path and not path.exists() and (file.get('path', '').endswith(('.framework', '.xcframework')) or file.get('path') == 'Resources/proj'):
                removed[build_file] = str(path.relative_to(ROOT))
            else:
                retained.append(build_file)
        obj['files'] = retained
    # Embed staged Python frameworks the target does not declare upstream (mini has no NumPy entry).
    added = {}
    for target in list(objects.values()):
        if target.get('isa') != 'PBXNativeTarget' or target.get('name') not in ['a-Shell', 'a-Shell-mini']:
            continue
        resource = 'Resources' if target['name'] == 'a-Shell' else 'Resources_mini'
        phase = next(objects[key] for key in target['buildPhases']
                     if objects[key]['isa'] == 'PBXCopyFilesBuildPhase' and objects[key].get('name') == 'Embed Frameworks')
        declared = {location(objects[file].get('fileRef')) for file in phase['files']}
        for staged in sorted((ROOT / resource / 'Frameworks').glob('*.framework')):
            if staged in declared:
                continue
            relative = str(staged.relative_to(ROOT))
            reference, build_file = [hashlib.sha1((kind + relative).encode()).hexdigest()[:24].upper()
                                     for kind in ['reference:', 'embed:']]
            objects[reference] = {'isa': 'PBXFileReference', 'lastKnownFileType': 'wrapper.framework',
                                  'name': staged.name, 'path': relative, 'sourceTree': 'SOURCE_ROOT'}
            objects[build_file] = {'isa': 'PBXBuildFile', 'fileRef': reference,
                                   'settings': {'ATTRIBUTES': ['CodeSignOnCopy', 'RemoveHeadersOnCopy']}}
            phase['files'].append(build_file)
            added.setdefault(target['name'], []).append(staged.name)
    # Hide commands whose optional native framework is absent from this profile.
    profiles = {}
    for target in objects.values():
        if target.get('isa') != 'PBXNativeTarget' or target.get('name') not in ['a-Shell', 'a-Shell-mini']:
            continue
        embedded = set()
        for phase in target['buildPhases']:
            item = objects[phase]
            if item['isa'] != 'PBXCopyFilesBuildPhase':
                continue
            for file in item.get('files', []):
                ref = objects.get(file, {}).get('fileRef')
                path = location(ref)
                if path:
                    embedded.add(path.stem + '.framework')
        resource = 'Resources' if target['name'] == 'a-Shell' else 'Resources_mini'
        dictionary = plistlib.loads((ROOT / resource / 'commandDictionary.plist').read_bytes())
        unavailable = []
        for name, entry in list(dictionary.items()):
            if isinstance(entry, list) and entry and '.framework/' in entry[0]:
                framework = entry[0].split('/', 1)[0]
                if framework not in embedded and framework != 'ios_system.framework':
                    unavailable.append(name)
                    del dictionary[name]
        folder = build / 'profiles' / target['name']
        folder.mkdir(parents=True, exist_ok=True)
        generated = folder / 'commandDictionary.plist'
        generated.write_bytes(plistlib.dumps(dictionary))
        for obj in objects.values():
            if obj.get('isa') == 'PBXFileReference' and obj.get('path') == resource + '/commandDictionary.plist':
                obj['path'] = str(generated.relative_to(ROOT))
                obj['sourceTree'] = 'SOURCE_ROOT'
        profiles[target['name']] = {'unavailableCommands': sorted(unavailable), 'embeddedFrameworks': sorted(embedded)}
        for command in ['python', 'python3', 'python3.13']:
            if command not in dictionary:
                raise SystemExit(target['name'] + ': required Python command missing: ' + command)
    manifest = {'profile': 'python-terminal', 'python': '3.13.1+',
                'deferred': 'Only the staged native Python extensions are included; install pure Python packages with pip.',
                'omittedFrameworks': sorted(set(removed.values())), 'addedFrameworks': added, 'targets': profiles}
    for resource in ['Resources', 'Resources_mini']:
        (ROOT / resource / 'Library/python-terminal-profile.json').write_text(json.dumps(manifest, indent=2) + '\n')
    destination.mkdir(exist_ok=True)
    (destination / 'project.pbxproj').write_bytes(plistlib.dumps(project))
    schemes = source / 'xcshareddata/xcschemes'
    output = destination / 'xcshareddata/xcschemes'
    shutil.copytree(schemes, output, dirs_exist_ok=True)
    for scheme in output.glob('*.xcscheme'):
        scheme.write_text(scheme.read_text().replace('container:a-Shell.xcodeproj', 'container:a-Shell-Python.xcodeproj'))
    (build / 'terminal-profile.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Generated', destination.name, 'with', len(set(removed.values())), 'deferred framework paths')
    for name, info in profiles.items():
        print(name, ':', len(info['embeddedFrameworks']), 'embedded frameworks;',
              len(info['unavailableCommands']), 'unavailable optional commands omitted')

if __name__ == '__main__':
    main()
