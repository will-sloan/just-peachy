# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf


truth = (np.array([-90, 90, 0, -90, 90, -90, 90, -90, 0, 90, 90])) % 360
truth_times = np.array([0, 9.422, 23.877, 43.071, 52.266, 53.169, 55.876, 65.802, 75.753, 80.728, 85.606])
TWO_PI = 2*np.pi


def spenergy_vad(in_spenergy):

    # tuning parameters
    peak_spenergy_alpha = 0.999  # long term average rate
    spenergy_alpha = 0.9  # how quickly to decay after speech
    spenergy_threshold = 0.002  # energy threshold for a NaN relative to peak energy
    spenergy_absolute_threshold = 50000  # this should be set so the VAD does not return 1 in silence
    spenergy_absolute_max = 1e6  # this is fixed to avoid tapping the mics causing a giant energy spike
    hold_threshold = 20  # control how long VAD stays 1 after energy is below threshold, stops toggling states rapidly

    # static counters etc.
    # smooth_spenergy = 0
    peak_spenergy = 0
    hold_timer = 0

    n = 0

    selected_spenergy = in_spenergy[:, 3]
    smooth_spenergy = np.zeros_like(selected_spenergy)
    vad_out = np.zeros_like(selected_spenergy, dtype=bool)
    for this_spenergy in selected_spenergy:

        smooth_spenergy[n] *= spenergy_alpha
        if this_spenergy > smooth_spenergy[n]:
            smooth_spenergy[n] = this_spenergy

        peak_spenergy *= peak_spenergy_alpha
        if smooth_spenergy[n] > peak_spenergy:
            peak_spenergy = smooth_spenergy[n]
        if peak_spenergy > spenergy_absolute_max:
            peak_spenergy = spenergy_absolute_max

        if ((smooth_spenergy[n] > spenergy_threshold*peak_spenergy and
             smooth_spenergy[n] > spenergy_absolute_threshold)):
            hold_timer = hold_threshold
        else:
            hold_timer -= 1

        if hold_timer <= 0:
            vad_out[n] = False
            hold_timer = 1  # don't overflow if this lasts forever
        else:
            vad_out[n] = True

        n += 1

    return vad_out, smooth_spenergy


def spenergy_vad_ref(in_spenergy):
    peak_spenergy_alpha = 0.999  # long term average rate
    spenergy_alpha = 0.9  # how quickly to decay after speech
    spenergy_threshold = 0.002  # energy threshold for a NaN relative to peak energy
    spenergy_absolute_threshold = 50000  # this should be set so the VAD does not return 1 in silence
    spenergy_absolute_max = 1e6  # this is fixed to avoid tapping the mics causing a giant energy spike
    hold_threshold = 20  # control how long VAD stays 1 after energy is below threshold, stops toggling states rapidly

    smooth_spenergy = np.copy(in_spenergy)
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


def beam_selection(beam_gates, beam_spenergy):
    """Select the beam with the highest spenergy"""
    spenergy_absolute_threshold = 50000  # this should be set so the VAD does not return 1 in silence
    last_beam = 0
    for n in range(len(beam_gates)):
        if beam_gates[n, 0] and beam_gates[n, 1]:
            other_beam = int(not last_beam)
            if (beam_spenergy[n, other_beam] > beam_spenergy[n, last_beam] and
                 beam_spenergy[n, other_beam] > spenergy_absolute_threshold):
                # if the spenergy is below the absolute threshold, the
                # gate could be open between words, so don't switch beams 
                beam_gates[n, last_beam] = 0
                last_beam = other_beam

            else:
                # otherwise, keep the same beam
                beam_gates[n, other_beam] = 0
                last_beam = last_beam
    return beam_gates


def process_wav(in_signal, beam_gates):
    """"Apply gate to beams"""
    beam_0 = in_signal[:, 0]
    beam_1 = in_signal[:, 1]

    for n in range(len(beam_gates)):
        idx = np.arange(n*256, (n+1)*256)
        if beam_gates[n, 0] == 0:
            beam_0[idx] = 0
        if beam_gates[n, 1] == 0:
            beam_1[idx] = 0
    
    out_audio = np.stack((beam_0, beam_1), axis=1)

    return out_audio


def fixed_beam_gating(in_spenergy, in_signal):
    # gate beams based on spenergy
    beam_gate_0 = spenergy_vad_ref(in_spenergy[:, 0])
    beam_gate_1 = spenergy_vad_ref(in_spenergy[:, 1])

    # select most energetic beam
    beam_gates = np.stack((beam_gate_0, beam_gate_1), axis=1)
    beam_gates = beam_selection(beam_gates, in_spenergy[:, 0:2])

    # apply gates to beams
    out_audio = process_wav(in_signal, beam_gates)

    return out_audio


def plot_fixed_beams(input_csv, input_wav, plot=True, ignore_real_orientation=False):

    in_data = np.genfromtxt(input_csv, dtype=float)

    in_azimuths = in_data[:, 1::2]
    if not ignore_real_orientation:
        in_azimuths = (in_azimuths) % TWO_PI

    in_spenergy = in_data[:, 2::2]

    # gate beams based on spenergy
    beam_gate_0 = spenergy_vad_ref(in_spenergy[:, 0])
    beam_gate_1 = spenergy_vad_ref(in_spenergy[:, 1])

    # select most energetic beam
    beam_gates = np.stack((beam_gate_0, beam_gate_1), axis=1)
    beam_gates = beam_selection(beam_gates, in_spenergy[:, 0:2])

    # example usage
    in_audio, fs = sf.read(input_wav)
    out_audio = fixed_beam_gating(in_spenergy, in_audio)
    sf.write("out.wav", out_audio, fs)


    if plot:
        fig, ax = plt.subplots(4, 1, sharex=True, sharey=False, constrained_layout=True)

        time_buf = np.arange(len(in_spenergy))*256/16000
        for n in [0]:
            ax[n].step(truth_times, truth, linestyle='--', where="post", label="truth")
            ax[n].plot(time_buf, np.rad2deg(in_azimuths[:, 0]), label="beam0")
            ax[n].plot(time_buf, np.rad2deg(in_azimuths[:, 1]), label="beam1")
            ax[n].plot(time_buf, np.rad2deg(in_azimuths[:, 2]), label="fast_beam")
            ax[n].plot(time_buf, np.rad2deg(in_azimuths[:, 3]), label="selected_beam")

            ax[n].grid(True)
            ax[n].set_xlim([0, time_buf[-1]])
            ax[n].set_ylim([0, 360])
            ax[n].legend()

        for n in [1]:
            ax[n].plot(time_buf, in_spenergy[:, 0], label="beam_0")
            ax[n].plot(time_buf, in_spenergy[:, 1], label="beam_1")

            ax[n].grid(True)
            ax[n].set_xlim([0, time_buf[-1]])
            ax[n].legend()

        for n in [2]:
            ax[n].plot(time_buf, beam_gates[:,0], label="gate_0")
            ax[n].plot(time_buf, beam_gates[:, 1], label="gate_1")
            ax[n].grid(True)
            ax[n].set_xlim([0, time_buf[-1]])
            ax[n].legend()

        plt.show()

    return


if __name__ == "__main__":
    dir_path = os.path.dirname(r".\\fixed_beams\\")
    plot_fixed_beams(Path(dir_path, "doa_ecc.dat"), Path(dir_path, "outcom_ecc.wav"))
