# Copyright 2022-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

"""
Generate artefacts from equalization filter bin files, including C files. If this module is run as follows:

    python -m eq_filter_tuning.gen_eq_filter_c_file

Then it can be used directly by cmake for code generation.
"""

import numpy as np
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import re
import argparse
import glob

pkg_dir = Path(__file__).parent

FLOAT_SIZE = 4;

def _parse_bin_file_name(path):
    """Filename is of the form eq_filter.bin. Read the file size and return the number of float values"""
    file_size = Path(path).stat().st_size
    if file_size == 0:
        raise ValueError(f"The size of file {path} is 0")
    if file_size%FLOAT_SIZE != 0:
        raise ValueError(f"The size of file {path} is not a multiple of {FLOAT_SIZE}")
    return file_size // FLOAT_SIZE

def gen_eq_filter_c_file(output_file, append_str="", files=[]):
    if len(files) == 0:
        # Pick up files from predefined locations
        files = glob.glob(f"{pkg_dir}/eq_filter_bin/*.bin")
        print(files)

    for model_bin_file in files:
        data = np.fromfile(model_bin_file, dtype=np.float32)
        bands = _parse_bin_file_name(model_bin_file)

        # Load template
        env = Environment(
            loader=FileSystemLoader(f"{pkg_dir}/../templates"),
            autoescape=select_autoescape(),
            trim_blocks=True
        )
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as fh:
            template = env.get_template("eq_filter.h.jinja")
            fh.write(template.render(bands=bands, buffer=data, append_str=append_str))

def parse_arguments():
    """ Parse command line arguments """

    parser = argparse.ArgumentParser(description='Generate equalization filter .c files from the equalization filter .bin files output from the host app or the ploteq.py script')
    parser.add_argument('--input', '-i', type=str, default=None,
                        help="Input equalization filter binary file")
    parser.add_argument('--out-file', '-o', type=str, help="output directory")
    parser.add_argument('--append-str', help='String appended to function and file which differentiates between input bin')
    parser.add_argument('--gen-c-file', '-gc', action="store_false", help='Generate the equalization filter .c file from the EQ filter .bin file. True by default')
    parser.add_argument('--depfile', default="", help="depfile can be used by cmake to track deps of the generated C file")
    args = parser.parse_args()
    return args

def gen_dep_file(args):
    """
    Create a file containing the makefile dependency rule for the output. This can be used
    by cmake to determine which files to track
    """
    with open(args.depfile, 'w') as depfile:
        depfile.write(" ".join([str(Path(args.out_file).resolve()),
                                ":" ,
                                __file__,
                                str(Path(__file__).parent.parent / "templates" / "eq_filter.h.jinja"),
                                str(Path(args.input).resolve())]))


if __name__ == "__main__":
    args = parse_arguments()
    gen_eq_filter_c_file(args.out_file, files=[args.input], append_str=args.append_str)

    if args.depfile:
        gen_dep_file(args)
