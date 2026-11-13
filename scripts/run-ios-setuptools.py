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
    result = original_compile_single(*args, **kwargs)
    if result.c_file and not result.num_errors:
        output = Path(result.c_file)
        text = output.read_text()
        corrected = re.sub(r'(Py_VISIT\(traverse_module_state->[A-Za-z_0-9]+)->memview\)',
                           r'\1.memview)', text)
        if corrected != text:
            output.write_text(corrected)
    return result

Main.compile_single = compile_single
sys.argv[0] = 'setup.py'
runpy.run_path('setup.py', run_name='__main__')
