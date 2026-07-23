#! python
# Copyright 2022-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
"""
Wrapper around pip-tools to make life easy, python for portability
"""
import os
import sys
import subprocess as sp
from pathlib import Path

python_versions_text = f"# python_version {sys.version_info.major}.{sys.version_info.minor}\n# pip_version 23.*"

def main():
    # configure pip-tools header comment
    os.environ["CUSTOM_COMPILE_COMMAND"] = f"./tools/update-requirements.py"

    requirements_path = Path(__file__).parent
    repo_root = requirements_path.parent
    
    # make requirements_path relative for nicer output
    requirements_path = requirements_path.relative_to(repo_root)

    if repo_root.resolve() != Path(".").resolve():
        print("Error: must run from repo root!")
        sys.exit(1)

    print("### Compiling main requirements")
    sp.run(f"pip-compile {requirements_path/'requirements.in'}  -o{repo_root/'requirements.txt'}".split(), check=True)
    (repo_root/'requirements.txt').write_text(python_versions_text + '\n' + (repo_root/'requirements.txt').read_text())


if __name__ == "__main__":
    main()

