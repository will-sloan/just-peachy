# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
"""
generate input and output test vectors for checking the C implemetentation
"""
import sys
from pathlib import Path
from doa_smoothing import smooth_doa
import numpy as np
from random import random, randrange


LENGTH = 100  # xsim test with 100 iterations takes 30s

def generate_doa_inputs():
    """
    Generate 3 random beams and a 4th beam which is always
    equal to one of the other beams
    """
    slow_beams = np.zeros((LENGTH, 2))
    for i in range(1, LENGTH):
        # slowly move the slow beams 
        degrees5 = (np.pi * 5 / 180)
        slow_beams[i, 0] = (slow_beams[i-1, 0] + (random()-0.5) * degrees5) % (2*np.pi)
        slow_beams[i, 1] = (slow_beams[i-1, 1] + (random()-0.5) * degrees5) % (2*np.pi)

    # fast beam is random
    fast_beam = np.random.rand(LENGTH, 1) * (2*np.pi)
    beams = np.append(slow_beams, fast_beam, 1)

    # selected must be one of the others and sticks
    # to one beam for a while before changing
    selection = np.zeros(LENGTH)
    curr = 0
    for i in range(LENGTH):
        # 20% chance of selected beam changing
        if random() < 0.2:
            curr = randrange(3)
        selection[i] = curr
    selection = np.stack((selection == 0, selection == 1, selection ==2), axis=1)
    selected = np.reshape(beams[:,:3][selection], (LENGTH, 1))
    return np.append(beams, selected, 1)

def generate_spenergy_inputs():
    """
    random spenergy data which is 0 alot of the time and approx.
    the right scale
    """
    zeros = np.random.rand(LENGTH, 4) < 0.95
    non_zeros = np.random.rand(LENGTH, 4) * 1e6
    non_zeros[zeros] = 0
    return non_zeros

def generate_inputs():
    doa = generate_doa_inputs()
    spenergy = generate_spenergy_inputs()
    inputs = np.zeros((LENGTH, 4 + 4 + 1)) # 4 each of doa and spenergy plus an unused index row
    inputs[:, 1::2] = doa
    inputs[:, 2::2] = spenergy
    return inputs, doa, spenergy


if __name__ == "__main__":
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    inputs, doa, spenergy = generate_inputs()

    np.savetxt(input_path, inputs)

    rt_smooth_rad, vad_flag = smooth_doa(doa, spenergy)

    np.savetxt(output_path, rt_smooth_rad)
