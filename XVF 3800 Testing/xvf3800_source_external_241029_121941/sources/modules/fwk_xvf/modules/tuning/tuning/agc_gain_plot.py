# Copyright 2017-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

"""
This script is used to plot the AGC gain values in dB and store the values in the agcgain.dat file.
Optionally a given input .dat file can be plotted
Usage: python agc_gain_plot.py <host_app>  [--protocol {usb|i2c|spi}] [--file-to-plot <filename.dat>]
Return values:
     0: No Error
     1: Not supported platform
     2: Missing host bin file
     3: Error running BeClear command via xvf_host
     4: Wrong input parameters
     5: Missing .dat file
"""

import sys, time, math, argparse, os
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.ticker
from pathlib import Path

from host_utils import basic_xvf_host


DAT_FILE_NAME = "agcgain.dat"


def plot_agc_gain(time_list, agc_gain_list, agc_max_gain):
    plt.figure(1)
    plt.clf()
    plt.ion()
    ax_db = plt.subplot(1, 1, 1)

    agc_max_gain_db = 20*np.log10(np.abs(agc_max_gain))
    agc_gain_list_db = 20*np.log10(np.abs(agc_gain_list))

    # set the ticks and limits of the dB y-axes,
    # limit to 6, 10 or 20 dB steps depending on the max gain to avoid having
    # too many lines
    if (int(agc_max_gain_db) + 6) // 6 < 15:
        plt.yticks(range(0, int(agc_max_gain_db) + 6, 6))
    elif (int(agc_max_gain_db) + 10) // 10 < 15:
        plt.yticks(range(0, int(agc_max_gain_db) + 10, 10))
    else:
        plt.yticks(range(0, int(agc_max_gain_db) + 20, 20))

    ax_db.set_ylim(0, int(agc_max_gain_db) + 6)

    ax_db.set_title("AGC Gain values")
    ax_db.set_ylabel("AGC Gain (dB)")
    ax_db.set_xlabel("Time (s)")
    ax_db.plot(time_list, agc_gain_list_db, label="Current AGC")
    ax_db.plot(time_list, [agc_max_gain_db for t in time_list], "r--", label="MAX AGC")

    ax_db.legend(loc="upper right")

    # duplicate y-axis to show scalar values in a logarithmic scale
    ax_log = ax_db.twinx()

    # set the ticks in the scalar y-axis, approximate them by 1 decimal cipher
    ticks = [round(math.pow(10, float(y) / 20), 1) for y in ax_db.get_yticks()]
    plt.yticks(ticks)

    # set the limit in the scalar y-axis
    limits = [math.pow(10, float(y) / 20) for y in ax_db.get_ylim()]
    ax_log.set_ylim(limits)

    # set the new y-axes as logarithmic scale
    plt.yscale("log")

    # set the tick labels in the scalar y-axis
    ax_log.set_yticks(ticks)
    ax_log.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())

    ax_log.set_ylabel("AGC Gain (scalar)")

    plt.grid(True)

    plt.show()


def plot_from_file(args: argparse.Namespace):
    file_to_plot = args.file_to_plot.resolve()

    print(f"File to plot set as {str(file_to_plot)}")
    if not file_to_plot.exists():
        print(f"Error: file {str(file_to_plot)} not present")
        exit(5)

    # load the values fromm the .dat file
    values = np.loadtxt(file_to_plot)
    # the first value of the array is the max AGC gain
    plot_agc_gain(
        np.arange(0, values.size - 1, 1), np.array(values[1:]), np.amax(values)
    )
    plt.ioff()
    plt.show()
    exit(0)


def plot_from_device(args: argparse.Namespace):
    # Normalize path to support Windows platforms
    host_bin_file = Path(args.host_app)
    host_bin_file = os.path.normpath(host_bin_file) # For Windows apparently
    protocol = args.protocol.lower()
    control_obj = basic_xvf_host(host_bin_file, control_protocol=protocol)

    print("Enabling AGC gain")
    control_obj.set_control_command("PP_AGCONOFF", "1")
    time.sleep(1)

    print("Close the plot to interrupt the graph plotting")

    agc_gain_list = []
    time_list = [0]
    agc_max_gain = 0
    delay_in_sec = 1

    print("Retrieving the max AGC gain")
    agc_max_gain = control_obj.get_control_command("PP_AGCMAXGAIN")
    agc_max_gain = float(agc_max_gain)
    agc_max_gain_db = 20 * math.log(agc_max_gain, 10)
    print(f"The max AGC gain is {agc_max_gain}, {agc_max_gain_db:.2f} dB")


    # save agc_max_gain in a .dat file
    with open(DAT_FILE_NAME, "w") as dat_f:
        dat_f.write("%.2f" % agc_max_gain)

    print("Retrieving the AGC gain")

    try:
        plt.figure(1)
        while plt.fignum_exists(1):
            plt.clf()
            plt.ion()
            _ = plt.subplot(1, 1, 1)

            agc_gain = control_obj.get_control_command("PP_AGCGAIN")
            agc_gain = float(agc_gain)
            agc_gain_db = 20 * math.log(agc_gain, 10)
            agc_gain_list.append(agc_gain)

            print(f"{agc_gain}, {agc_gain_db:.2f} dB")
            sys.stdout.flush()

            plot_agc_gain(time_list, agc_gain_list, agc_max_gain)
            time_list.append(time_list[-1] + delay_in_sec)

            # save data in a .dat file
            with open(DAT_FILE_NAME, "a") as dat_f:
                dat_f.write(f"\t{agc_gain_list[-1]:.2f}")

            plt.pause(delay_in_sec)

    except KeyboardInterrupt:
        pass

    # save data in a .dat file
    with open(DAT_FILE_NAME, "w") as dat_f:
        values_to_store = ["%.2f" % agc_max_gain]
        for val in agc_gain_list:
            values_to_store.append("%.2f" % val)
        dat_f.write("\t".join(values_to_store))

    # replot with test ended
    plot_agc_gain(time_list[:-1], agc_gain_list, agc_max_gain)

    input("Press Enter to terminate the test and close the plot")

    exit(0)


if __name__ == "__main__":
    # parse the command line parameters
    argparser = argparse.ArgumentParser(
        description="XMOS XVF38xx AGC gain plotting script"
    )

    argparser.add_argument('host_app',
        type = str,
        help = 'Host app that will be used for issuing control commands while running this script')

    argparser.add_argument('--protocol', '-p',
        type = str.lower,
        default = 'usb',
        action = 'store',
        choices = ['i2c','spi', 'usb'],
        help = 'Communication protocol used to control the device, default: usb')

    argparser.add_argument(
        "--file-to-plot",
        "-i",
        type=Path,
        default=None,
        action="store",
        help="If provided, plots values from this file rather than from the device",
    )

    try:
        args = argparser.parse_args()
    except SystemExit:
        exit(4)

    if args.file_to_plot is not None:
        plot_from_file(args)
    else:
        plot_from_device(args)
