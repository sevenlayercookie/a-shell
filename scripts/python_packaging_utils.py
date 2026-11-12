"""Shared packaging helpers for a-Shell's embedded Python distribution."""
from pathlib import Path


def install_console_scripts(entrypoints, library):
    directory = Path(library) / 'bin'
    directory.mkdir(parents=True, exist_ok=True)
    for name, target in entrypoints.items():
        if Path(name).name != name:
            raise ValueError('Invalid entry point name: ' + name)
        script = directory / name
        script.write_text('#!/usr/bin/env python3\nimport sys\n'
                          'from importlib.metadata import EntryPoint\n'
                          'if __name__ == "__main__":\n'
                          + '    sys.exit(EntryPoint(' + repr(name) + ', ' + repr(target)
                          + ', "console_scripts").load()())\n')
        script.chmod(0o755)
