# Copyright 2017-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

"""
This script is used to plot the azimuth values
Usage: python doa_plot.py <host_app>  [--protocol {usb|i2c|spi}] [--plot_ambiguities]

Return values:
     0: No Error
     1: Not supported platform
     2: Missing host bin file
     3: Error running BeClear command via xvf_host
     4: Wrong input parameters
     5: Unsupported mic array geometry
"""

import argparse, os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib as mpl

import numpy as np
from pathlib import Path

from host_utils import basic_xvf_host


def get_better_doa(control_obj: basic_xvf_host):
    output = control_obj.get_control_command("AUDIO_MGR_SELECTED_AZIMUTHS")
    better_doa = float(output[0])
    return better_doa


def get_azimuths(control_obj: basic_xvf_host):
    raw_azimuth = control_obj.get_control_command("AEC_AZIMUTH_VALUES")
    azimuths = np.array(raw_azimuth[0::3], dtype=float)
    return azimuths


def plot_from_device(args: argparse.Namespace):
    # print CLI parameter info
    print("Communication protocol set to " + args.protocol.upper())
    print("Close the plot to interrupt the graph plotting")

    # Normalize path to support Windows platforms
    host_bin_file = Path(args.host_app)
    host_bin_file = os.path.normpath(host_bin_file) # For Windows apparently
    protocol = args.protocol.lower()
    control_obj = basic_xvf_host(host_bin_file, control_protocol=protocol)

    print("Retrieving the array type")
    array_type = control_obj.get_control_command("AEC_MIC_ARRAY_TYPE")

    if int(array_type) == 1:
        print("Mic array type: linear")
        array_type = "linear"
    elif int(array_type) == 2:
        print("Mic array type: squarecular")
        array_type = "squarecular"
    else:
        print("Error: array type 0 unsupported:\n" + array_type)
        exit(5)

    print("Retrieving the initial azimuths")
    # check if the output is correct
    azimuths = get_azimuths(control_obj)
    print(f"The azimuths are:")
    print(np.array2string(np.rad2deg(azimuths), precision=2))

    better_azimuth = get_better_doa(control_obj)

    print("Retrieving the live azimuths")

    try:
        # general figure settings
        mpl.rcParams['toolbar'] = 'None'
        plt.ion()
        fig = plt.figure(1)
        ax = plt.axes(projection='polar')
        plt.title("XVF38xx Voice Processor")

        # array types define zero in different locations
        if array_type == 'squarecular':
            ax.set_theta_zero_location('E')
        elif array_type == 'linear':
            ax.set_theta_zero_location('W')

        ax.set_yticklabels([])

        # plot outline of board
        board = patches.Polygon(#np.stack(([0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.35, 0.6], [0.35, 0.55], [0.4, 0.55]))
                                np.stack(([0.4, 0.4], [0.65, 0.4], [0.65, 0.45], [0.6, 0.45], [0.6, 0.6], [0.4, 0.6])),
                                 fill=True, facecolor='g', edgecolor='k', linewidth=1,
                                 transform=ax.transAxes, zorder=2)
        ax.add_patch(board)

        # plot and label the beams
        azimuths = np.append(azimuths[:3], better_azimuth if not np.isnan(better_azimuth) else 0)
        bar = ax.bar(azimuths, np.ones(4),  width=0.1, color=['b', 'g', 'r', 'm'], alpha=0.2)
        bar[3].set_alpha(1.0)

        # do the same thing for the linear array ambiguities
        if array_type == "linear" and args.plot_ambiguities:
            bar_lin = ax.bar(-azimuths, np.ones(4),  width=-0.1, color=['b', 'g', 'r', 'm'], alpha=0.2)

        bar[0].set_label("slow_1")
        bar[1].set_label("slow_2")
        bar[2].set_label("free")
        bar[3].set_label("processed")

        legend_angle = np.deg2rad(-30)
        ax.legend(loc="upper left",
                  bbox_to_anchor=(.5 + np.cos(legend_angle)/2, .5 + np.sin(legend_angle)/2))

        while plt.fignum_exists(1):

            azimuths = get_azimuths(control_obj)

            better_azimuth = get_better_doa(control_obj)
            azimuths = np.append(azimuths[:3], better_azimuth if not np.isnan(better_azimuth) else 0)

            # update the bar locations, reset transparancy
            for n in range(3):
                bar[n].set_x(azimuths[n])
                bar[n].set_alpha(0.2)

            # highlight selected beam
            if not np.isnan(better_azimuth):
                bar[3].set_x(azimuths[3])
                bar[3].set_alpha(1.0)
            else:
                bar[3].set_alpha(0.0)

            for n in range(3):
                ax.draw_artist(bar[n])

            # do the same thing for the linear array ambiguities
            if array_type == 'linear' and args.plot_ambiguities:
                for n in range(4):
                    bar_lin[n].set_x(-azimuths[n])
                    bar_lin[n].set_alpha(0.2)

                if not np.isnan(better_azimuth):
                    bar_lin[3].set_alpha(1.0)
                else:
                    bar_lin[3].set_alpha(0.0)

                for n in range(4):
                    ax.draw_artist(bar_lin[n])

            fig.canvas.flush_events()

    except KeyboardInterrupt:
        pass

    exit(0)


if __name__ == "__main__":
    # parse the command line parameters
    argparser = argparse.ArgumentParser(
        description="XMOS XVF38xx azimuth gain plotting script"
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
        "--plot_ambiguities",
        "-a",
        default=False,
        action="store_true",
        help='If provided, plots the DOA ambiguities of a linear array',
    )

    args = argparser.parse_args()

    plot_from_device(args)
