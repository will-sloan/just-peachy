# Copyright 2022-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

"""
Generate artefacts from nmodel bin files. Includes plots and C files. If this module is run as follows:

    python -m nlmodel_tuning.gen_nlmodel_c_file

Then it can be used directly by cmake for code generation.
"""

import numpy as np
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import re
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import argparse
import glob

pkg_dir = Path(__file__).parent


def _parse_bin_file_name(path):
    """Filename is of the form nlmodel.bin.r16.c40. Parse the number of rows and cols from this_filepath"""
    fname = Path(path).name
    m = re.match(r'.*\.r([0-9]+)\.c([0-9]+)', fname)
    if m is None:
        raise ValueError(f"File {path} does not have the expected file name format")
    rows = int(m.group(1))
    cols = int(m.group(2))
    return rows, cols


def plot_nlmodel(output_dir, bin_files):
    for model_bin_file in bin_files:
        data = np.fromfile(model_bin_file, dtype=np.float32)
        rows, cols = _parse_bin_file_name(model_bin_file)
        xnlaec = data.reshape(rows, cols)
        fig = plt.figure()
        ax = fig.add_subplot(111,projection='3d')
        X,Y = np.meshgrid(np.arange(0,xnlaec.shape[1],1),np.arange(0,xnlaec.shape[0]-1,1))
        with_level_correction = True
        if with_level_correction:
            mat = xnlaec[:-1,:]*np.repeat(np.expand_dims(xnlaec[-1,:15],-1),cols,-1)
        else:
            mat = xnlaec[:-1,:]
        pcm = ax.plot_surface( X, Y, mat,norm=colors.LogNorm(vmin=max(1e-4, np.min(mat)),vmax=max(2.2, np.max(mat))), cmap='RdYlBu_r')
        vmin=np.min(mat)
        vmax=np.max(mat)

        ax.set_xlabel("Frequency bin")
        ax.set_ylabel("level")
        fig.colorbar( pcm, ax=ax)
        plt.tight_layout()
        prefix = Path(model_bin_file).name
        print(f"Saving {output_dir}/{prefix}_plot.png")
        plt.savefig(f"{output_dir}/{prefix}_plot.png", bbox_inches='tight')


def gen_nlmodel_c_file(output_file, append_str="", files=[]):
    if len(files) == 0:
        # Pick up files from predefined locations
        files = glob.glob(f"{pkg_dir}/nlmodel_bin/*.bin.*")
        print(files)

    for model_bin_file in files:
        data = np.fromfile(model_bin_file, dtype=np.float32)
        rows, cols = _parse_bin_file_name(model_bin_file)

        # Load template
        env = Environment(
            loader=FileSystemLoader(f"{pkg_dir}/../templates"),
            autoescape=select_autoescape(),
            trim_blocks=True
        )
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as fh:
            template = env.get_template("nlmodel.h.jinja")
            fh.write(template.render(rows=rows, cols=cols, buffer=data, append_str=append_str))

def parse_arguments():
    """ Parse command line arguments """

    parser = argparse.ArgumentParser(description='Generate nl model .c files from the nlmodel .bin files output from the host app')
    parser.add_argument('--input', '-i', type=str, default=None,
                        help="Input nl model binary file, must have a .rN.cM suffix where N and M are numbers indicating the shape of the model")
    parser.add_argument('--out-file', '-o', type=str, help="output directory")
    parser.add_argument('--save-plot', '-sp', action="store_true", help='Plot nl model and save the plot. False by default')
    parser.add_argument('--append-str', help='String appended to function and file which differentiates between input bin')
    parser.add_argument('--gen-c-file', '-gc', action="store_false", help='Generate the NL model .c file from the NL model .bin file. True by default')
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
                                str(Path(__file__).parent.parent / "templates" / "nlmodel.h.jinja"),
                                str(Path(args.input).resolve())]))




if __name__ == "__main__":
    args = parse_arguments()
    gen_nlmodel_c_file(args.out_file, files=[args.input], append_str=args.append_str)

    if args.depfile:
        gen_dep_file(args)
