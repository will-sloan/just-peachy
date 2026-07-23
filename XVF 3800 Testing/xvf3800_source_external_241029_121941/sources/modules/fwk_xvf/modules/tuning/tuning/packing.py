#!/usr/bin/env python3
# Copyright 2022-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

"""
This module contains helper functions to generate or decompose a packed 48kHz signal from/to multiple 16kHz signals compatible with the XVF38xx.
"""

import sys
import numpy as np
import soundfile as sf
import argparse

def invert_dict(x: dict): return {val: key for key, val in x.items()}

MAX_UNPACK_ERRORS = 50
SUBTYPE_TO_BITRES = {
    'PCM_U8' : 8,
    'PCM_16' : 16,
    'PCM_24' : 24,
    'PCM_32' : 32
}
BITRES_TO_SUBTYPE = invert_dict(SUBTYPE_TO_BITRES)

def pack(input_wav_fn, output_wav_fn, output_bitres=32, double_sample_packing=False, debug=False):

    output_sample_rate = 48000
    output_channel_count = 2

    if double_sample_packing:
        output_bitres = 32 # We always read a 16b file and output a 32b file

    with sf.SoundFile(str(input_wav_fn)) as input_wav:
        input_sample_rate = input_wav.samplerate
        input_channel_count = input_wav.channels
        input_sample_count = input_wav.frames
        input_subtype = input_wav.subtype

        # This always left-aligns
        input_data = input_wav.read(dtype='int32', always_2d=True)

    try:
        input_bitres = SUBTYPE_TO_BITRES[input_subtype]
    except KeyError:
        input_bitres = 32

    try:
        output_subtype = BITRES_TO_SUBTYPE[output_bitres]
    except KeyError:
        output_subtype = 'PCM_32'

    shift = 32 - output_bitres
    mark_mask = 1 << shift
    if not double_sample_packing:
        sample_mask_with_clear_lsb = ((1 << output_bitres) - 2) << shift
    else:
        sample_mask_with_clear_lsb = ((1 << (output_bitres // 2)) - 2) << (32 - output_bitres // 2) # We want this as a half-width sample mask

    if input_sample_rate != 16000 and not double_sample_packing:
        print(f"Please provide a file with a 16 kHz sample rate; this file has a {input_sample_rate} kHz sample rate.")
        sys.exit(1)
    elif input_sample_rate != 32000 and double_sample_packing:
        print(f"Please provide a file with a 32 kHz sample rate; this file has a {input_sample_rate} kHz sample rate.")
        sys.exit(1)

    if input_channel_count < 2 or input_channel_count > 6:
        print(f"Please provide a file with between 2 and 6 channels; this file has {input_channel_count}.")
        sys.exit(2)

    if not double_sample_packing and input_bitres not in (8, 16, 24, 32):
        print("This module can only process 8-, 16-, 24- or 32-bit resolution inputs.")
        sys.exit(3)
    elif double_sample_packing and input_bitres != 16:
        print("Double sample packing can only process 16-bit resolution inputs.")
        sys.exit(3)

    if not double_sample_packing and output_bitres not in (8, 16, 24, 32):
        print("This module can only produce 8-, 16-, 24- or 32-bit resolution outputs.")
        sys.exit(4)

    if "PCM" not in input_subtype:
        print("This module can only process PCM wave files. Other format schemes, including FLOAT, are unsupported.")
        sys.exit(5)

    if double_sample_packing:
        # https://xmosjira.atlassian.net/wiki/spaces/CONF/pages/3671851510/XVF3800+Audio+Manager+Detailed+design#Super-Wide-Band%2C-Mono-(XVF3820)
        input_sample_count = input_sample_count - (input_sample_count % (12 // input_channel_count)) # Only blocks of 12 allowed so round down to that
        output_sample_count = int(input_sample_count * 1.5) # This will always be a whole number due to the above
        output_data = np.zeros((output_sample_count, output_channel_count), dtype=np.int32)
        input_data = input_data[:input_sample_count, :]

        for channel_number in range(input_channel_count):
            input_channel = input_data[:, channel_number].view(np.uint32) & sample_mask_with_clear_lsb # clear LSB

            input_evens = input_channel[::2]
            input_odds = input_channel[1::2] >> 16
            input_comb = input_evens | input_odds

            output_channel_number = channel_number % output_channel_count
            output_slot_number = channel_number // output_channel_count
            output_data[output_slot_number::3, output_channel_number] = input_comb.view(np.int32)

        for channel in range(output_channel_count):
            output_data[1::3, channel] |= mark_mask
            output_data[2::3, channel] |= mark_mask

    else:
        output_sample_count = input_sample_count * 3
        output_data = np.zeros((output_sample_count, output_channel_count), dtype=np.int32)

        for channel_number in range(input_channel_count):
            output_channel_number = channel_number % output_channel_count
            output_slot_number = channel_number // output_channel_count
            output_data[output_slot_number::3, output_channel_number] = input_data[:, channel_number] & sample_mask_with_clear_lsb

        for channel in range(output_channel_count):
            output_data[1::3, channel] |= mark_mask
            output_data[2::3, channel] |= mark_mask

    with sf.SoundFile(str(output_wav_fn), 'w',
                      samplerate=output_sample_rate,
                      channels=output_channel_count,
                      subtype=output_subtype,
                      endian='LITTLE',
                      format="WAV") as output_wav:
        output_wav.write(output_data)

    if debug:
        log_prefix = "log_pack"
        print("---------------------")
        print(f"Input sample rate:    {input_sample_rate}")
        print(f"Input channel count:  {input_channel_count}")
        print(f"Input sample count:   {input_sample_count}")
        print(f"Input subtype:        {input_subtype}")
        print(f"Input bitdepth:       {input_bitres}")
        print("---------------------")
        print(f"Output sample rate:   {output_sample_rate}")
        print(f"Output channel count: {output_channel_count}")
        print(f"Output sample count:  {output_sample_count}")
        print(f"Output subtype:       {output_subtype}")
        print(f"Output bitdepth:      {output_bitres}")
        print("---------------------")

        input_binary_data = np.vectorize(np.binary_repr)(input_data, width=32)

        input_log_file = f"{log_prefix}_input.txt"
        with open(input_log_file, "w") as file:
            for datum in input_binary_data:
                file.write(f"{datum}\n")

        print(f"Input data log complete, saved to {input_log_file}. This will be 32b left-aligned.")
        print("---------------------")

        output_binary_data = np.vectorize(np.binary_repr)(output_data, width=32)
        output_log_file = f"{log_prefix}_output.txt"
        with open(output_log_file, "w") as file:
            for datum in output_binary_data:
                file.write(f"{datum}\n")

        print(f"Output data log complete, saved to {output_log_file}. This will be 32b left-aligned.")
        print("---------------------")

def unpack(input_wav_fn, output_wav_fn, output_bitres=32, skip_leading_zeros=False, double_sample_packing=False, debug=False):

    output_channel_count = 6

    if double_sample_packing:
        output_bitres = 16 # We always read a 32b file and output a 16b file

    with sf.SoundFile(str(input_wav_fn)) as input_wav:
        input_sample_rate = input_wav.samplerate
        input_channel_count = input_wav.channels
        input_sample_count = input_wav.frames
        input_subtype = input_wav.subtype

        # This always left-aligns
        input_data = input_wav.read(dtype='int32', always_2d=True)

    try:
        input_bitres = SUBTYPE_TO_BITRES[input_subtype]
    except KeyError:
        input_bitres = 32

    try:
        output_subtype = BITRES_TO_SUBTYPE[output_bitres]
    except KeyError:
        output_subtype = 'PCM_32'

    shift = 32 - input_bitres
    mark_mask = 1 << shift

    if input_sample_rate != 48000 or input_channel_count != 2:
        print(f"Please provide a 48 kHz stereo file; this file has a {input_sample_rate} kHz sample rate and {input_channel_count} channels.")
        sys.exit(1)

    if double_sample_packing and input_bitres != 32:
        print("Double word packing from 32kHz is only supported on 32b 48kHz stereo input files.")
        sys.exit(1)

    input_data_0 = input_data[:, 0]
    input_data_1 = input_data[:, 1]

    if skip_leading_zeros:
        input_data_0 = np.trim_zeros(input_data_0)
        input_data_1 = np.trim_zeros(input_data_1)
        # If the lengths are off by 1, add an extra 0 since we might have removed an actual zero sample
        if(len(input_data_0) == len(input_data_1)-1):
            input_data_0 = np.insert(input_data_0,0,0)

    frame_start_indices_0 = np.argwhere(~input_data_0 & mark_mask)
    frame_start_indices_1 = np.argwhere(~input_data_1 & mark_mask)

    if frame_start_indices_0.size == 0 or frame_start_indices_1.size == 0:
        print("Error: No markers found in this file; please ensure a correctly marked packed output is provided")
        sys.exit(1)

    if frame_start_indices_0.shape != frame_start_indices_1.shape or not np.all(frame_start_indices_0 == frame_start_indices_1):
        # This shouldn't happen with the XVF38xx
        print("Error: frame indices between channels 0 and 1 don't match, creating a union...")
        frame_start_indices = np.union1d(frame_start_indices_0.flatten(), frame_start_indices_1.flatten())
    else:
        frame_start_indices = frame_start_indices_0

    frame_start_index_diffs = np.diff(frame_start_indices.flatten())
    incorrect_indices = np.argwhere(frame_start_index_diffs != 3)

    if incorrect_indices.size > MAX_UNPACK_ERRORS:
        print(f"Over {MAX_UNPACK_ERRORS} markers incorrectly spaced so giving up.")
        sys.exit(1)
    else:
        for index in incorrect_indices:
            print(f"Frame corrupted at time {index[0]/input_sample_rate:.2f}s, frame number {index[0]}, diff {frame_start_index_diffs[index][0]}. Continuing...")

    # Make sure frame_start_indices never exceeds audio length
    if any(bad_idx := frame_start_indices + 2 >= input_data_0.shape[0]):
        print(f"Warning: Bad indices: {np.argwhere(bad_idx)}")
        frame_start_indices = frame_start_indices[:-1]

    if double_sample_packing:
        # Extract the hi/low short word signals
        signals = np.zeros((len(frame_start_indices), output_channel_count), dtype=np.int32)
        input_data = np.stack((input_data_0, input_data_1))
        output_sample_count = len(frame_start_indices) * 2

        output_data = np.zeros((output_sample_count, output_channel_count), dtype=np.int16)

        for i in range(output_channel_count):
            channel = i % input_channel_count
            indicies_offset = i // 2
            signals[:, i] = input_data[channel][frame_start_indices + indicies_offset].flatten()

            output_data[0::2, i] = (signals[:, i] >> 16).flatten()
            output_data[1::2, i] = (signals[:, i] & 0xffff).flatten()

        output_data &= 0xfffe # clear LSB
        output_sample_rate = 32000

    else:
        # separate the channels and clear the packing bit
        a = input_data_0[frame_start_indices] & ~mark_mask
        b = input_data_1[frame_start_indices] & ~mark_mask
        c = input_data_0[frame_start_indices + 1] & ~mark_mask
        d = input_data_1[frame_start_indices + 1] & ~mark_mask
        e = input_data_0[frame_start_indices + 2] & ~mark_mask
        f = input_data_1[frame_start_indices + 2] & ~mark_mask

        signals = (a, b, c, d, e, f)

        trim_length = min((len(x) for x in signals))

        output_data = np.column_stack([x[:trim_length, :] for x in signals])
        output_sample_rate = 16000
        output_sample_count = trim_length

    with sf.SoundFile(str(output_wav_fn), 'w',
                      samplerate=output_sample_rate,
                      channels=output_channel_count,
                      subtype=output_subtype,
                      endian='LITTLE',
                      format="WAV") as output_wav:
        output_wav.write(output_data)

    print("Unpacking complete.")
    print("If the AUDIO_MGR_OP_ALL command was used to set the output from the device, the channel order in the resultant .wav will be (1,3,5,2,4,6); i.e. the first argument to _OP_ALL will be in channel 1, the second in channel 3, etc.")
    print("If each output was set individually using the AUDIO_MGR_OP_(L|R)_PK(0|1|2) commands, the channel order in the resultant .wav will be (L_PK0, R_PK0, L_PK1, R_PK1, L_PK2, R_PK2)")

    if debug:
        log_prefix = "log_unpack"
        print("---------------------")
        print(f"Input sample rate:    {input_sample_rate}")
        print(f"Input channel count:  {input_channel_count}")
        print(f"Input sample count:   {input_sample_count}")
        print(f"Input subtype:        {input_subtype}")
        print(f"Input bitdepth:       {input_bitres}")
        print("---------------------")
        print(f"Output sample rate:   {output_sample_rate}")
        print(f"Output channel count: {output_channel_count}")
        print(f"Output sample count:  {output_sample_count}")
        print(f"Output subtype:       {output_subtype}")
        print(f"Output bitdepth:      {output_bitres}")
        print("---------------------")

        input_binary_data = np.vectorize(np.binary_repr)(input_data, width=32)

        input_log_file = f"{log_prefix}_input.txt"
        with open(input_log_file, "w") as file:
            for datum in input_binary_data:
                file.write(f"{datum}\n")

        print(f"Input data log complete, saved to {input_log_file}. This will be 32b left-aligned.")
        print("---------------------")

        output_binary_data = np.vectorize(np.binary_repr)(output_data, width=32)
        output_log_file = f"{log_prefix}_output.txt"
        with open(output_log_file, "w") as file:
            for datum in output_binary_data:
                file.write(f"{datum}\n")

        print(f"Output data log complete, saved to {output_log_file}. This will be 32b left-aligned.")
        print("---------------------")


# When invoked as main program, invoke the profiler on a script
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A script for packing and unpacking 6 channel audio from/to 2 channels at 3x the frequency, or 6 channel 16b audio from/to 2 32b channels at 1.5x the frequency.')
    parser.add_argument("command", help="unpack or pack.")
    parser.add_argument("input_wav", help="Input wav file to be packed or unpacked.")
    parser.add_argument("output_wav", help="Output wav file from packing or unpacking operation.")
    parser.add_argument("-b", "--bitres", type=int, help="Expected or desired bit resolution of the packing word. Only valid in 3x mode and ignored otherwise.", default=32)
    parser.add_argument("-s", "--skip-leading-zeros", action='store_true', help="Skip any leading zeros before unpacking.")
    parser.add_argument("-d", "--double-sample-packing", action='store_true', help="Use 2x 16b samples per 32b word at 1.5x the rate.")
    parser.add_argument("-v", "--verbose", action='store_true', help="Activate logging of both input and output, as well as diagnostic prints.")
    args = parser.parse_args()

    if 'unpack' in args.command:
        unpack(args.input_wav, args.output_wav, args.bitres, args.skip_leading_zeros, args.double_sample_packing, args.verbose)
    elif 'pack' in args.command:
        pack(args.input_wav, args.output_wav, args.bitres, args.double_sample_packing, args.verbose)
    else:
        raise NameError("Please provide valid packing command")
