#!/usr/bin/env python3
"""Run Cython and repair its 3.1 module-state memoryview traversal expression."""
from pathlib import Path
import re
import subprocess
import sys


def main():
    result = subprocess.run([sys.executable, '-m', 'cython', *sys.argv[1:]])
    if result.returncode:
        raise SystemExit(result.returncode)
    output = None
    arguments = sys.argv[1:]
    for index, argument in enumerate(arguments):
        if argument in {'-o', '--output-file'}:
            output = Path(arguments[index + 1])
        elif argument.startswith('--output-file='):
            output = Path(argument.split('=', 1)[1])
    if output is None:
        return
    text = output.read_text()
    # Cython 3.1.6 Code.py appends "->memview" for cached memoryview
    # constants, although these module-state fields are structs, not pointers.
    corrected = re.sub(r'(Py_VISIT\(traverse_module_state->[A-Za-z_0-9]+)->memview\)',
                       r'\1.memview)', text)
    # Cython's divmod error sentinel is header-local but lacks static in C.
    # Keep it local when multiple extension objects share one framework.
    corrected = re.sub(r'^const (.+ __Pyx_divmod_ERROR_VALUE_[A-Za-z_0-9]+ =)',
                       r'static const \1', corrected, flags=re.MULTILINE)
    if corrected != text:
        output.write_text(corrected)


if __name__ == '__main__':
    main()
