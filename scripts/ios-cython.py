#!/usr/bin/env python3
"""Run Cython and repair its 3.1 module-state memoryview traversal expression."""
from pathlib import Path
import re
import os
import subprocess
import sys


def main():
    include = os.environ.get('IOS_CYTHON_INCLUDE')
    options = ['-I', include] if include and '--version' not in sys.argv else []
    result = subprocess.run([sys.executable, '-m', 'cython', *options, *sys.argv[1:]])
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
    # PyType_FromSpec replaces an instance __doc__ descriptor with the type doc.
    # Restore the generated getset, as Cython already does for __module__.
    corrected = corrected.replace('strcmp(getset->name, "__module__") == 0)',
                                  '(strcmp(getset->name, "__module__") == 0 || strcmp(getset->name, "__doc__") == 0))')
    corrected = corrected.replace('static int __Pyx_fix_up_extension_type_from_spec(PyType_Spec *spec, PyTypeObject *type) {\n#if __PYX_LIMITED_VERSION_HEX > 0x030900B1',
                                  'static int __Pyx_fix_up_extension_type_from_spec(PyType_Spec *spec, PyTypeObject *type) {\n#if CYTHON_COMPILING_IN_LIMITED_API && __PYX_LIMITED_VERSION_HEX > 0x030900B1')
    if corrected != text:
        output.write_text(corrected)


if __name__ == '__main__':
    main()
