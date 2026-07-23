# Copyright 2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

"""
pan pot lut gen script


usage:
    python pan_pot.py <N> <FILE>

example:
    python pat_pot.py 10 pan_pot_lut.c

will generate a pan pot lut with 10 entries in the file pan_pot_lut.c

The pan_pot_lut is a lookup table approach to the -4.5 dB pan algorithm for the left
channel only. This outputs 1 for θ=0 and 0 for θ=π.

L(θ) = sqrt(1 - (θ/π)cos(θ/2))

The right channel can be computed using L(π - θ) as the output is symmetrical
around π/2.
"""


from pathlib import Path
import numpy
from functools import partial

class Lut:
    """
    Generates look up table for -4.5 dB panning algorithm and contains method
    for generating the C source to use it.
    """
    def __init__(self, n_points):
        self.input, self.input_step = numpy.linspace(0, numpy.pi, n_points, retstep=True)
        self.lut = pan_45db_left(self.input)

    def as_c(self):
        return f"""
        #include "pan_pot_lut.h"
        #include <math.h>

        // Max output diff to real val with this lut: {lut_diff_max(self)}
        float pan_pot_lut(float angle_rad) {{
            static const float lut[] = {{ {",".join(str(v) for v in self.lut)} }};
            static const int lut_len = {self.input.shape[0]} - 1;
            static const float angle_to_index_ratio = ((float)lut_len) / M_PI;

            if(angle_rad >= M_PI) {{
                return 0;
            }}
            
            const float lower_index_f = angle_rad * angle_to_index_ratio;
            const int lower_index = (int)lower_index_f;

            // lut counts down, so lower val at higher index
            const float lower_val = lut[lower_index + 1];
            const float upper_val = lut[lower_index];

            const float interpolate_ratio = lower_index_f - lower_index;
            return upper_val + ((lower_val - upper_val) * interpolate_ratio);
        }}
        """

def pan_45db_left(angle_rad):
    """
    -4.5 dB left channel algorithm

    Returns:
        multiplier to apply to channel for left sample
    """
    return numpy.sqrt((1 - (angle_rad / numpy.pi)) * numpy.cos(angle_rad / 2))


def angle_from_lut(angle_rad, lut):
    """calculate output ratio for a given angle using a lut"""
    if angle_rad >= numpy.pi:
        return 0
    lut_len = lut.lut.shape[0] - 1
    lower_index_f = angle_rad * (lut_len/numpy.pi)
    lower_index = int(lower_index_f)
    lower_val = lut.lut[lower_index + 1]
    upper_val = lut.lut[lower_index]

    interpolate_ratio = lower_index_f - lower_index
    return upper_val + ((lower_val - upper_val) * interpolate_ratio)

def lut_diff_max(lut):
    """
    Find the maximum difference between the actual -4.5 dB result and the output
    of the LUT.
    """
    input = numpy.linspace(0, numpy.pi, 10000)
    expected = pan_45db_left(input)

    lut_f = numpy.vectorize(partial(angle_from_lut, lut=lut))
    actual = lut_f(input)
    diff = numpy.max(numpy.abs(expected - actual))
    return diff


def main(args):
    lut = Lut(int(args[0]))
    Path(args[1]).write_text(lut.as_c())

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if 2 != len(args):
        print(__doc__)
        exit(1)
    main(sys.argv[1:])

