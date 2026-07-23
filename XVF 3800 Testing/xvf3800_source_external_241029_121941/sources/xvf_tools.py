# Copyright 2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import sys
import argparse
from pathlib import Path
from subprocess import run

# Available error codes
XVF_TOOLS_INVALID_COMMAND = 0x80
XVF_TOOLS_INVALID_PATH    = 0x81

# List of directories containing the scripts
BOOT_SPI_SLAVE_SCRIPTS_DIR = "modules/fwk_xvf/modules/boot_spi_slave/scripts/"
EQ_FILTER_TUNIG_SCRIPTS_DIR = (
    "modules/fwk_xvf/modules/eq_filter_tuning/eq_filter_tuning/"
)
NL_MODEL_GEN_SCRIPTS_DIR = "app_xvf3800/nl_model_gen/"
TUNING_SCRIPTS_DIR = "modules/fwk_xvf/modules/tuning/tuning/"

# List of available commands and the corresponding path to the script
COMMAND_LIST = {
    "agc_gain_plot":            TUNING_SCRIPTS_DIR + "agc_gain_plot.py",
    "coherence":                TUNING_SCRIPTS_DIR + "coherence.py",
    "doa_plot":                 TUNING_SCRIPTS_DIR + "doa_plot.py",
    "generate_image":           BOOT_SPI_SLAVE_SCRIPTS_DIR + "generate_image.py",
    "mic_ref_correlate":        TUNING_SCRIPTS_DIR + "mic_ref_correlate.py",
    "nl_model_training":        NL_MODEL_GEN_SCRIPTS_DIR + "nl_model_training.py",
    "packing":                  TUNING_SCRIPTS_DIR + "packing.py",
    "packed_recorder":          TUNING_SCRIPTS_DIR + "packed_recorder.py",
    "ploteq":                   EQ_FILTER_TUNIG_SCRIPTS_DIR + "ploteq.py",
    "read_aec_filter":          TUNING_SCRIPTS_DIR + "read_aec_filter.py",
    "remote_nl_model_training": NL_MODEL_GEN_SCRIPTS_DIR + "remote_nl_model_training.py",
    "send_image_from_rpi":      BOOT_SPI_SLAVE_SCRIPTS_DIR + "send_image_from_rpi.py",
}

# Parse the CLI arguments
parser = argparse.ArgumentParser(
    description='User interface to run XVF scripts. Type "python xvf_tools.py help" to see the list of available commands',
    usage="%(prog)s [--help] command_name [--command-help] [command_args ...]",
)
parser.add_argument("command_name", help=f"The name of the command to execute")
parser.add_argument(
    "command_args",
    nargs="*",
    help="A variable number of arguments to pass to the command",
)
parser.add_argument(
    "--command-help",
    "-ch",
    action="store_true",
    help="Display the help message for the command",
)

# Parse CLI arguments and split them between known and unknown arguments
# Unknown arguments are passed to the command script
args, unknown_args = parser.parse_known_args()

# Convert command into a path to the corresponding script
try:
    script = Path(__file__).resolve().parent / COMMAND_LIST[args.command_name]
    if not script.exists():
      print("Error: could not find script", script)
      exit(XVF_TOOLS_INVALID_PATH)
except KeyError:
    # if the command is invalid, print the help menu and a list of valid commands
    parser.print_help()
    print("\nAvailable commands:\n   ", "\n    ".join(COMMAND_LIST.keys()))
    exit(XVF_TOOLS_INVALID_COMMAND)

if args.command_help:
    # If --command-help is specified, run the script with --help
    ret = run([sys.executable, script, "--help"])
else:
    # Otherwise, run the command with the provided arguments
    ret = run([sys.executable, script, *args.command_args, *unknown_args])
# Return the return code of the script
sys.exit(ret.returncode)
