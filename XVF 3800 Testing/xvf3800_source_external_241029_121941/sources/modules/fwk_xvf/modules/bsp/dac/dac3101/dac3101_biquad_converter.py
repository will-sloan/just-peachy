import numpy as np


# It is recommended that filter functions are taken from Robert
# Bristow-Johnson's Audio EQ Cookbook:
# https://www.musicdsp.org/en/latest/_downloads/3e1dc886e7849251d6747b194d482272/Audio-EQ-Cookbook.txt

def low_shelf(f0, dBgain, S, Fs):
    """
    A low shelf biquad with adjustable slope, taken from Robert
    Bristow-Johnson's Audio EQ Cookbook

    Parameters
    ----------
    f0 : float
        corner frequency of the shelf
    dBgain : float
        gain of the shelf in decibels
    S : float
        shelf slope steepness
    Fs : float
        sampling frequency

    Returns
    -------
    b : list
        list of numerator coefficients
    a : list
        list of denominator coefficients

    """

    w0 = 2*np.pi*f0/Fs
    A  = 10**(dBgain/40)
    alpha = np.sin(w0)/2 * np.sqrt( (A + 1/A)*(1/S - 1) + 2)

    b0 =    A*( (A+1) - (A-1)*np.cos(w0) + 2*np.sqrt(A)*alpha)
    b1 =  2*A*( (A-1) - (A+1)*np.cos(w0))
    b2 =    A*( (A+1) - (A-1)*np.cos(w0) - 2*np.sqrt(A)*alpha)
    a0 =        (A+1) + (A-1)*np.cos(w0) + 2*np.sqrt(A)*alpha
    a1 =   -2*( (A-1) + (A+1)*np.cos(w0))
    a2 =        (A+1) + (A-1)*np.cos(w0) - 2*np.sqrt(A)*alpha

    return [b0, b1, b2], [a0, a1, a2]


def normalise(b, a):
    """
    Normalise filter coefficients into the TI format defined in step 6 of TI's
    "Configure the Coefficients for Digital Biquad Filters in TLV320AIC3xxx Family"
    https://www.ti.com/lit/an/slaa447/slaa447.pdf

    Parameters
    ----------
    b : list
        list of numerator coefficients
    a : list
        list of denominator coefficients

    Returns
    -------
    ba : list
        list of numerator and denominator coefficients

    """

    assert isinstance(b, list) and len(b) == 3, \
        "b must be a 3 element list of biquad coefficients"
    assert isinstance(a, list) and len(a) == 3, \
        "a must be a 3 element list of biquad coefficients"

    [b0, b1, b2] = b
    [a0, a1, a2] = a

    # normalise by a0
    b0 /= a0
    b1 /= a0
    b2 /= a0
    a1 /= a0
    a2 /= a0
    a0 /= a0

    # TI spec these to be halved
    a1 /= 2
    b1 /= 2

    # normalise by max numerator
    factor = np.max([b0, b1, b2])
    b0 = b0 / factor
    b1 = b1 / factor
    b2 = b2 / factor

    a1 = -a1
    a2 = -a2

    for coeff in [b0, b1, b2, a0, a1, a2]:
        assert coeff <= 1

    # scale to 16bit
    b0 = np.round(b0 * (2**15 - 1)).astype(np.int16)
    b1 = np.round(b1 * (2**15 - 1)).astype(np.int16)
    b2 = np.round(b2 * (2**15 - 1)).astype(np.int16)
    a0 = np.round(a0 * (2**15 - 1)).astype(np.int16)
    a1 = np.round(a1 * (2**15 - 1)).astype(np.int16)
    a2 = np.round(a2 * (2**15 - 1)).astype(np.int16)

    return [b0, b1, b2, a0, a1, a2]


def twos_comp(val):
    """
    calculate the 16 bit 2's complement
    see https://stackoverflow.com/questions/1604464/twos-complement-in-python
    """

    # check the int16 sign bit
    if (val & (1 << (16 - 1))):
        # compute negative value. This may produce a value grater than 32767,
        # but it will overflow to the correct binary value during printing
        val = abs(abs(val) - (1 << 16))

    return val


def print_dac3101_biquad(b, a):
    """
    Prints a set of biquad coefficients in the required format for setting
    the TI DAC3101 registers. These values can be pasted into the biquad
    register settings in dac3101.c. Separate calls are required for each biquad.

    Parameters
    ----------
    b : list
        list of numerator coefficients
    a : list
        list of denominator coefficients

    Returns
    -------
    none

    """

    assert isinstance(b, list) and len(b) == 3, \
        "b must be a 3 element list of biquad coefficients"
    assert isinstance(a, list) and len(a) == 3, \
        "a must be a 3 element list of biquad coefficients"

    # normalise the TI 3101 way, taking 2's complement
    ba_n = normalise(b, a)
    ba_n_2c = [twos_comp(coeff) for coeff in ba_n]

    # normalisation means D0 is not set
    ba_n_2c = ba_n_2c[0:3] + ba_n_2c[4:]
    names = ["N0", "N1", "N2", "D1", "D2"]

    # print in hex for inserting into dac3101.c
    for coeff, name in zip(ba_n_2c, names):
        these_bytes = format(coeff, '04x')
        print('%s HI: 0x' % name + these_bytes[:2].upper())
        print('%s LO: 0x' % name + these_bytes[2:].upper())


if __name__ == "__main__":
    Fs = 48000

    # example low shelf for removing desk bump
    b, a = low_shelf(280, -6, 1.3, Fs)

    print_dac3101_biquad(b, a)
