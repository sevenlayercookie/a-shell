#!/usr/bin/env python3
"""Forward Darwin framework flags from native-extension builds to Flang's linker."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

def main():
    compiler = os.environ.get('ASHELL_FLANG') or shutil.which('flang')
    if not compiler:
        candidate = Path('/opt/homebrew/opt/flang/bin/flang')
        if candidate.is_file():
            compiler = str(candidate)
        else:
            raise SystemExit('Flang is required; set ASHELL_FLANG to its executable')
    result = []
    arguments = iter(sys.argv[1:])
    for argument in arguments:
        if argument in ['-framework', '-weak_framework', '-undefined', '-install_name']:
            value = next(arguments, None)
            if value is None:
                raise SystemExit('Missing value for ' + argument)
            result.append('-Wl,' + argument + ',' + value)
        elif argument == '-F':
            value = next(arguments, None)
            if value is None:
                raise SystemExit('Missing framework search path')
            result.append('-Wl,-F,' + value)
        elif argument.startswith('-F'):
            result.append('-Wl,' + argument)
        elif argument in ['-dynamiclib', '-bundle']:
            result.append('-shared')
        else:
            result.append(argument)
    if '-shared' in result and not any(flag in result for flag in ['-c', '-E', '-S']):
        target = ' '.join(result)
        if '-apple-ios' in target:
            resource = Path(subprocess.check_output(['xcrun', 'clang', '--print-resource-dir'], text=True).strip())
            platform = 'iossim' if '-simulator' in target else 'ios'
            builtins = resource / 'lib/darwin' / ('libclang_rt.' + platform + '.a')
            if not builtins.is_file():
                raise SystemExit('Missing iOS compiler runtime: ' + str(builtins))
            result.append(str(builtins))
    os.execv(compiler, [compiler, *result])

if __name__ == '__main__':
    main()
