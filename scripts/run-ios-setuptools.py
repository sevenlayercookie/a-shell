#!/usr/bin/env python3
"""Run setup.py using target NumPy headers and corrected Cython traversal."""
import os
from pathlib import Path
import re
import runpy
import sys

import numpy

numpy.get_include = lambda: os.environ['IOS_NUMPY_INCLUDE']
# Setuptools invokes Cython in-process, so apply the same generated-C repair
# used by ios-cython.py after each compiler invocation.
from Cython.Compiler import Main

original_compile_single = Main.compile_single

def compile_single(*args, **kwargs):
    include = os.environ.get('IOS_CYTHON_INCLUDE')
    options = args[1] if len(args) > 1 else kwargs['options']
    if include and include not in options.include_path:
        options.include_path.append(include)
    result = original_compile_single(*args, **kwargs)
    if result.c_file and not result.num_errors:
        output = Path(result.c_file)
        text = output.read_text()
        corrected = re.sub(r'(Py_VISIT\(traverse_module_state->[A-Za-z_0-9]+)->memview\)',
                           r'\1.memview)', text)
        # PyType_FromSpec replaces an instance __doc__ descriptor with the type doc.
        # Restore the generated getset, as Cython already does for __module__.
        corrected = corrected.replace('strcmp(getset->name, "__module__") == 0)',
                                      '(strcmp(getset->name, "__module__") == 0 || strcmp(getset->name, "__doc__") == 0))')
        corrected = corrected.replace('static int __Pyx_fix_up_extension_type_from_spec(PyType_Spec *spec, PyTypeObject *type) {\n#if __PYX_LIMITED_VERSION_HEX > 0x030900B1',
                                      'static int __Pyx_fix_up_extension_type_from_spec(PyType_Spec *spec, PyTypeObject *type) {\n#if CYTHON_COMPILING_IN_LIMITED_API && __PYX_LIMITED_VERSION_HEX > 0x030900B1')
        if corrected != text:
            output.write_text(corrected)
    return result

Main.compile_single = compile_single
sys.argv[0] = 'setup.py'
runpy.run_path('setup.py', run_name='__main__')
