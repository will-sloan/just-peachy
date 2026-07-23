#!/usr/bin/env python3
# Copyright 2019-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
"""
This script generates a binary file to be loaded on an XVF38xx board via SPI slave.
It requires an .xe file as input parameter and it outputs the generated binary
in the 'output' subfolder.
The generate binary file has the suffix '_spi_slave.bin'.
This script will perform the following steps:
    1. extract the binary content of the given .xe file
    2. build the loader for new binary
    3. build the composer executable to include the loader.bin into the new binary
    4. generate the final binary using the composer executable
"""

import os
import shutil
import argparse
import re
import subprocess
import traceback
from contextlib import contextmanager
from pathlib import Path

pkg_dir = Path(__file__).parent
LOADER_PATH = pkg_dir / "../loader"
COMPOSER_PATH = pkg_dir / "../composer"
SCRIPTS_PATH = pkg_dir
BUILD_PATH = pkg_dir / "build"
OUTPUT_PATH = pkg_dir / "output"

STR_DELIMITER = "\n--------------------------------------------\n"

def run_cmd(cmd_to_run, verbose):
    """
    Function to run a command on the terminal and print some delimiter strings.
    If the command fail, it causes the exit from the program.

    Args:
        cmd_to_run: command to run given as a string

    Returns:
        None

    Raises:
        subprocess.CalledProcessError: if command call fails
    """
    try:
        if verbose:
            print(STR_DELIMITER)
            subprocess.check_call(cmd_to_run.split(" "))
            print(STR_DELIMITER)
        else:
            subprocess.check_output(cmd_to_run.split(" "))
    except subprocess.CalledProcessError:
        traceback.print_exc()
        if not verbose:
            print("Run again with --verbose for full error")
        exit(1)

@contextmanager
def pushd(new_dir):
    last_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(last_dir)

def convert_xe(xe_filename, verbose=False):
    """
    Convert xe file into a SPI bootable binary

    Args:
        xe_filename: name of the .xe file
        verbose:     print debug information

    Returns:
        None
    """
    xe_path = Path(xe_filename).resolve()
    s = re.match(r".*\.xe$", str(xe_path))
    if s is None:
        print("Error: wrong input file name: {}".format(xe_path))
        exit(1)
    if not xe_path.is_file():
        print("Error: input file {} not found".format(xe_path))
        exit(1)

    # delete build folder
    if BUILD_PATH.is_dir():
        shutil.rmtree(BUILD_PATH)
    os.makedirs(BUILD_PATH, exist_ok=True)

    # create output if it doesn't exist
    if not OUTPUT_PATH.is_dir():
        os.makedirs(OUTPUT_PATH, exist_ok=True)

    print("Extract the binaries from the .xe file")
    with pushd(BUILD_PATH):
        cmd = f"xobjdump --strip --split {xe_path}"
        run_cmd(cmd, verbose)

    print("Build the loader exe")
    with pushd(LOADER_PATH):
        run_cmd("xmake", verbose)
        run_cmd("xmake", verbose)

    print("Build the composer exe")
    with pushd(COMPOSER_PATH):
        run_cmd("xmake", verbose)

        print("Generate the image to load")
        output_filename = xe_path.name.replace('.xe', f'_spi_boot.bin')
        cmd = "./composer {} {} {} {}".format(LOADER_PATH / "loader.bin",
                                              BUILD_PATH / "image_n0c0_2.bin",
                                              BUILD_PATH / "image_n0c1_2.bin",
                                              OUTPUT_PATH / output_filename)
        run_cmd(cmd, True)

    print("Remove .xb file")
    with pushd(SCRIPTS_PATH):
        os.remove(str(xe_path).replace('.xe', '.xb'))

    print("\nOutput saved:")
    print(OUTPUT_PATH / output_filename)
    return OUTPUT_PATH / output_filename

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate an image to load via SPI slave')
    parser.add_argument('xe_filename', help='xe file name')
    parser.add_argument('--verbose', action="store_true", help='Print tools output')

    args = parser.parse_args()

    convert_xe(args.xe_filename, args.verbose)
