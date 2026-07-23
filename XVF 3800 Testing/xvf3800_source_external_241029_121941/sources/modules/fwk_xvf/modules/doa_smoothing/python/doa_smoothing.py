# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt


# compensate for board orientation
offset = 90 + 45
truth_offset = offset - 45

truth = (np.array([-15, 0, 15, -15, 0, -15, 0, -15, 15, 0, 0]) + truth_offset) % 360
truth_times = np.array([0, 9.422, 23.877, 43.071, 52.266, 53.169, 55.876, 65.802, 75.753, 80.728, 85.606])
TWO_PI = 2*np.pi


def smooth_doa_real_time(in_azimuths, vad_flag):
    out_azimuth = np.zeros(len(in_azimuths))

    # tuning parameters
    count_thresh = 10
    alpha = 0.825

    # static counters etc.
    count = 0
    last_az = 0
    smoothed_az = 0
    n = 0

    for these_input_azimuths in in_azimuths:
        this_az = these_input_azimuths[3]

        # Restrict selection to slow beams
        # only use selected DOA
        if this_az != these_input_azimuths[0] and this_az != these_input_azimuths[1]:
            this_az = last_az

        # counter to remove sudden jumps, but allow drifting
        if np.abs(this_az - last_az) > np.deg2rad(5):
            count += 1
            if vad_flag[n] and count > count_thresh:
                last_az = this_az
                count = 0
            else:
                this_az = last_az
        else:
            last_az = this_az
            count = 0

        # exponentially weighted moving average
        # if we are going to smooth over zero degrees, add 360 to the smaller
        # value and take the modulus
        if this_az < np.pi/2 and smoothed_az > (3*np.pi/2):
            this_az += TWO_PI
        elif this_az > (3*np.pi/2) and smoothed_az < np.pi/2:
            smoothed_az += TWO_PI

        # do the actual ewm
        smoothed_az = alpha*(smoothed_az) + (1 - alpha)*this_az
        smoothed_az = smoothed_az % TWO_PI

        out_azimuth[n] = smoothed_az
        n += 1

    return out_azimuth


def smooth_doa_ref(in_azimuths, vad_flag):
    # tuning parameters
    count_thresh = 10
    alpha = 0.825

    az_selected = np.copy(in_azimuths[:, 3])

    for n in range(len(az_selected)):
        if az_selected[n] != in_azimuths[n, 0] and az_selected[n] != in_azimuths[n, 1]:
            az_selected[n] = az_selected[n - 1]

    az_count = np.copy(az_selected)
    count = 0
    for n in range(1, len(in_azimuths)):
        if np.abs(az_count[n] - az_count[n-1]) > np.deg2rad(5):
            count += 1
            if vad_flag[n] and count > count_thresh:
                count = 0
            else:
                az_count[n] = az_count[n - 1]
        else:
            count = 0

    az_smooth = np.zeros_like(az_count)
    complex_az_smooth = np.zeros_like(az_count, dtype=np.cdouble)
    for n in range(1, len(in_azimuths)):
        complex_az_count = np.cos(az_count[n]) + 1j*np.sin(az_count[n])
        complex_az_smooth[n] = alpha*complex_az_smooth[n-1] + (1 - alpha)*complex_az_count
        az_smooth[n] = (np.angle(complex_az_smooth[n]) + TWO_PI) % TWO_PI

    return az_selected, az_count, az_smooth


def spenergy_vad(in_spenergy):

    # tuning parameters
    peak_spenergy_alpha = 0.999  # long term average rate
    spenergy_alpha = 0.9  # how quickly to decay after speech
    spenergy_threshold = 0.02  # energy threshold for a NaN relative to peak energy
    spenergy_absolute_threshold = 5000  # this should be set so the VAD does not return 1 in silence
    spenergy_absolute_max = 1e6  # this is fixed to avoid tapping the mics causing a giant energy spike

    hold_threshold = 10  # control how long VAD stays 1 after energy is below threshold, stops toggling states rapidly

    # static counters etc.
    smooth_spenergy = 0
    peak_spenergy = 0
    hold_timer = 0

    n = 0

    selected_spenergy = in_spenergy[:, 3]
    vad_out = np.zeros_like(selected_spenergy, dtype=bool)
    for this_spenergy in selected_spenergy:

        smooth_spenergy *= spenergy_alpha
        if this_spenergy > smooth_spenergy:
            smooth_spenergy = this_spenergy

        peak_spenergy *= peak_spenergy_alpha
        if smooth_spenergy > peak_spenergy:
            peak_spenergy = smooth_spenergy
        if peak_spenergy > spenergy_absolute_max:
            peak_spenergy = spenergy_absolute_max

        if ((smooth_spenergy > spenergy_threshold*peak_spenergy and
             smooth_spenergy > spenergy_absolute_threshold)):
            hold_timer = hold_threshold
        else:
            hold_timer -= 1

        if hold_timer <= 0:
            vad_out[n] = False
            hold_timer = 1  # don't overflow if this lasts forever
        else:
            vad_out[n] = True

        n += 1

    return vad_out


def spenergy_vad_ref(in_spenergy):
    peak_spenergy_alpha = 0.999  # long term average rate
    spenergy_alpha = 0.9  # how quickly to decay after speech
    spenergy_threshold = 0.02  # energy threshold for a NaN relative to peak energy
    spenergy_absolute_threshold = 5000  # this should be set so the VAD does not return 1 in silence
    spenergy_absolute_max = 1e6  # this is fixed to avoid tapping the mics causing a giant energy spike
    hold_threshold = 10  # control how long VAD stays 1 after energy is below threshold, stops toggling states rapidly

    smooth_spenergy = np.copy(in_spenergy[:, 3])
    for n in range(1, len(smooth_spenergy)):
        if smooth_spenergy[n] > smooth_spenergy[n-1]:
            pass
        else:
            smooth_spenergy[n] = smooth_spenergy[n-1]*spenergy_alpha

    peak_spenergy = np.copy(smooth_spenergy)
    for n in range(1, len(peak_spenergy)):
        if peak_spenergy[n] > peak_spenergy[n-1]:
            pass
        else:
            peak_spenergy[n] = peak_spenergy[n-1]*peak_spenergy_alpha
        if peak_spenergy[n] > spenergy_absolute_max:
            peak_spenergy[n] = spenergy_absolute_max

    spenergy_flag = np.zeros_like(smooth_spenergy, dtype=bool)
    hold_timer = 0
    for n in range(len(smooth_spenergy)):
        if ((smooth_spenergy[n] > spenergy_threshold*peak_spenergy[n] and
             smooth_spenergy[n] > spenergy_absolute_threshold)):
            hold_timer = hold_threshold
        else:
            hold_timer -= 1

        if hold_timer <= 0:
            spenergy_flag[n] = False
            hold_timer = 1  # don't overflow if this lasts forever
        else:
            spenergy_flag[n] = True

    return spenergy_flag


def smooth_doa(in_azimuths, in_spenergy):

    vad_flag_rt = spenergy_vad(in_spenergy)
    rt_smooth_rad = smooth_doa_real_time(in_azimuths, vad_flag_rt)
    rt_smooth_rad[np.where(vad_flag_rt == False)] = np.NaN

    return rt_smooth_rad, vad_flag_rt


def plot_smooth_doa_vs_ref(input_csv, plot=True, ignore_real_orientation=False):

    in_data = np.genfromtxt(input_csv, dtype=float)

    in_azimuths = in_data[:, 1::2]
    if not ignore_real_orientation:
        in_azimuths = (in_azimuths + np.deg2rad(offset)) % TWO_PI

    in_spenergy = in_data[:, 2::2]

    # reference vectory method
    vad_flag_ref = spenergy_vad_ref(in_spenergy)
    az_selected_rad, az_count_rad, az_smooth_rad = smooth_doa_ref(in_azimuths, vad_flag_ref)
    az_smooth_rad[np.where(vad_flag_ref == False)] = np.NaN

    # real time method
    rt_smooth_rad = smooth_doa(in_azimuths, in_spenergy)

    rt_smooth = np.rad2deg(rt_smooth_rad)
    az_selected = np.rad2deg(az_selected_rad)
    az_count = np.rad2deg(az_count_rad)
    az_smooth = np.rad2deg(az_smooth_rad)

    if plot:
        fig, ax = plt.subplots(4, 1, sharex=True, sharey=False, constrained_layout=True)
        # time_buf = np.arange(len(complex_az_smooth))  # np.linspace(0, truth_times[-1], len(complex_az_smooth))
        # time_buf = np.linspace(0, truth_times[-1], len(az_smooth))
        time_buf = np.arange(len(az_smooth))*256/16000
        for n in [0]:
            ax[n].step(truth_times, truth, linestyle='--', where="post", label="truth")
            ax[n].plot(time_buf, np.rad2deg(in_azimuths[:, 3]), label="original")
            ax[n].plot(time_buf, az_selected, label="selector")
            ax[n].grid(True)
            # ax[n].set_yticks(np.arange(-90, 90+45, 45))
            ax[n].set_xlim([0, time_buf[-1]])
            ax[n].set_ylim([0, 180])
            ax[n].legend()

        # for n in [1]:
        #     ax[n].step(truth_times, truth, linestyle='--', where="post", label="truth")
        #     next(ax[n]._get_lines.prop_cycler)
        #     ax[n].plot(time_buf, az_selected, label="selector")
        #     ax[n].plot(time_buf, az_count, label="count")

        #     ax[n].grid(True)
        #     ax[n].set_xlim([0, time_buf[-1]])
        #     ax[n].legend()

        # for n in [2]:
        #     ax[n].step(truth_times, truth, linestyle='--', where="post", label="truth")
        #     next(ax[n]._get_lines.prop_cycler)
        #     next(ax[n]._get_lines.prop_cycler)
        #     ax[n].plot(time_buf, az_count, label="count")
        #     ax[n].plot(time_buf, az_smooth, label="smooth")

        #     ax[n].grid(True)
        #     ax[n].set_xlim([0, time_buf[-1]])
        #     ax[n].legend()

        for n in [1]:
            ax[n].step(truth_times, truth, linestyle='--', where="post", label="truth")
            ax[n].plot(time_buf, az_smooth, linestyle='-', label="ref")
            ax[n].plot(time_buf, rt_smooth, linestyle='-', label="real_time")
            ax[n].grid(True)
            ax[n].set_xlim([0, time_buf[-1]])
            ax[n].legend()
            ax[n].set_ylim([0, 180])

        for n in [2]:
            ax[n].step(time_buf, in_spenergy[:, 3], where="post", label="in_spenergy")
            ax[n].plot(time_buf, vad_flag_ref*np.max(in_spenergy[:, 3]), linestyle='-', label="vad_flag ref")
            ax[n].plot(time_buf, vad_flag_rt*np.max(in_spenergy[:, 3]), linestyle='--', label="vad_flag rt")

            ax[n].grid(True)
            ax[n].set_xlim([0, time_buf[-1]])
            ax[n].legend()

        plt.show()

    return


if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.realpath(__file__))
    # smooth_doa("cafe_doa.dat")
    # smooth_doa(Path(dir_path, "no_noise_doa_spe.dat"))
    plot_smooth_doa_vs_ref(Path(dir_path, "cafe_noise_doa_spe.dat"))
