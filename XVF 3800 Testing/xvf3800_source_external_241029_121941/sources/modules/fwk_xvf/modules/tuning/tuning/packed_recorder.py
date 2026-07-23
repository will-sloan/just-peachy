# Copyright 2017-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

"""
This script is used to record  audio from a 38xx device while playing
back a regular audio file. The recorded audio can be packed, in which case it
will also unpack the resulting recording.
Instead of a playback file, a recording length can be specified.
If a playback file is provided, this will be truncated/padded to the recording length.
The playback file can be a packed audio file, indicated by using the --packed_input flag.
If a playback file is not provided, zeros will be played back for the recording length.

Usage: python packed_recorder.py <host_app> [--playback_file <filename.wav>] [--packed_output]
       python packed_recorder.py <host_app> [--playback_file <packed_recording.wav>] [--packed_input]
       python packed_recorder.py <host_app> [--recording_length <time in seconds>] [--packed_output]

Return values:
     0: No Error
     1: Not supported platform
     2: Missing host bin file
     3: Error running BeClear command via xvf_host
     4: Wrong input parameters
     5: Playback file and recording length not provided
     6: Packed input expected, but input file could not be unpacked
     7: Portaudio Error (audio device not found)
"""

import sys, argparse
from time import sleep
from pathlib import Path
import shutil
import os
import contextlib
import tempfile

import numpy as np
import soundfile as sf
import sounddevice as sd

from tuning import packing
from tuning.host_utils import basic_xvf_host

SUPPORTED_PROTOCOLS = ("usb")


def set_packing(args: argparse.Namespace):

    host_bin_file = Path(args.host_app)
    host_bin_file = os.path.normpath(host_bin_file) # For Windows apparently
    protocol = args.protocol.lower()
    control_obj = basic_xvf_host(host_bin_file, control_protocol=protocol)

    if args.bit_depth == 32 and sys.platform() != "linux":
        raise ValueError("32 bit audio is only supported on Linux hosts. Please use 24 or 16 bit.")

    if args.packed_input:
        # get packed audio bit depth
        with sf.SoundFile(str(args.playback_file)) as input_wav:
            input_subtype = input_wav.subtype

        try:
            input_bitres = packing.SUBTYPE_TO_BITRES[input_subtype]
        except KeyError:
            input_bitres = 32

        try:
            print("Checking input file can be unpacked")
            temp_dir = tempfile.TemporaryDirectory()
            temp_output = Path(temp_dir.name, "output.wav")
            # suppress prints from subfunction
            with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
                packing.unpack(args.playback_file, temp_output, skip_leading_zeros=True)
        except Exception as err:
            print("Input cannot be unpacked!")
            print(err)
            exit(6)
        finally:
            shutil.rmtree(temp_dir.name)
        print("Input unpacked sucessully")

        if input_bitres != args.bit_depth:
            args.bit_depth = input_bitres
            print("Warning: Packed input file bit depth != requested bit depth, using packed input bit depth")

    else:
        input_bitres = args.bit_depth

    if args.protocol == 'usb':
        # set sounddevice default bit depths
        sd.default.dtype = ["int%d" % input_bitres, "int%d" % args.bit_depth]

        # USB_BIT_DEPTH reboots the device. Avoid an unnecessary reboot when
        # the requested packed depth already matches the active firmware.
        current_bit_depth = control_obj.get_control_command("USB_BIT_DEPTH")
        requested_bit_depth = [str(input_bitres), str(args.bit_depth)]
        if [str(value) for value in current_bit_depth] != requested_bit_depth:
            control_obj.set_bit_depth(input_bitres, args.bit_depth)
        else:
            print(f"USB bit depth already set to {input_bitres} {args.bit_depth}")
    else:
        # if not setting bit depth, do a core burn to reset everything
        control_obj.run_control_command("TEST_CORE_BURN")

    # wait for the device to reset, restart sounddevice to avoid PortAudio problems
    print("Waiting for audio restart")
    sd._terminate()
    # WDM-KS can take longer than five seconds to re-enumerate after
    # PortAudio is restarted on Windows.
    sleep(10)
    sd._initialize()

    if args.packed_output:
        print("Setting packed output")
        control_obj.set_control_command("AUDIO_MGR_OP_PACKED", "1 1")

        if args.asr_output:
            print("Enabling automatic speech-recognition output")
            control_obj.set_control_command("AEC_ASROUTONOFF", "1")

        # This sets which audio is packed. Each channel is a tuple of `category source`, as defined in Table 3.2 of the
        # User Guide. It is probable desireable to take the microphones and far end reference with gain and delay.
        #
        # For quick reference:
        #
        # Category                            Source
        # ----------------------------------------------------------------------------------
        # 3: Mic with gain and delay    [0, 1, 2, 3]: Mic channel post gain and system delay
        # 6: Processed output                 [0, 1]: Slow beam output,
        #                                        [2]: Fast beam output,
        #                                        [3]: Autoselect beam output.
        # 7: AEC residual/ASR output          [0..3]: one output per beam;
        #                                        with AEC_ASROUTONOFF=1 this is
        #                                        the ASR-processed output.
        # 12: Far end with gain and delay        [0]: Far end reference with gain and delay
        #
        # The channel order in the AUDIO_MGR_OP_ALL command is: (L_PK0 L_PK1 L_PK2 R_PK0 R_PK1 R_PK2).
        # Note these will be unpacked into separate channels in the order (L_PK0, R_PK0, L_PK1, R_PK1, L_PK2, R_PK2)
        if args.op_all:
            control_obj.set_control_command("AUDIO_MGR_OP_ALL", args.op_all, check=False)
        else:
            control_obj.set_control_command("AUDIO_MGR_OP_ALL", "12 0  3 0  3 2  6 3  3 1  3 3", check=False)

    if args.packed_input:
        print("Setting packed input")
        control_obj.set_control_command("I2S_INPUT_PACKED", "1")
        control_obj.set_control_command("AUDIO_MGR_MIC_GAIN", "1.0")
        control_obj.set_control_command("AUDIO_MGR_REF_GAIN", "1.0")
        control_obj.set_control_command("AUDIO_MGR_SYS_DELAY", "0")

    return


def playrec_packed(playback_filepath, out_filepath, recording_length=None, fs=48000, bit_depth=24, exit_on_failure=True):

    print("Playing and recording audio")

    if playback_filepath:
        playback_signal, playback_fs = sf.read(playback_filepath, dtype='int32', always_2d=True)
        assert fs == playback_fs
        if recording_length:
            rec_len_samples = int(fs*recording_length)
            if playback_signal.shape[0] > rec_len_samples:
                playback_signal = playback_signal[:rec_len_samples, :]
            else:
                pad_len = rec_len_samples - playback_signal.shape[0]
                playback_signal = np.concatenate(playback_signal, np.zeros((pad_len, playback_signal.shape[1])))
    else:
        if recording_length is None:
            print("Error, playback file and recording length cannot both be None")
            exit(5)

        playback_signal = np.zeros((int(fs*recording_length), 2))

    try:
        if sys.platform != 'win32':
            # for mac and linux, we should only get 1 device with 2 in and 2 out
            playback_device = sd.query_devices(device="XVF38")['index']
            recording_device = playback_device

        elif sys.platform == 'win32':
            # for Windows we have to spec API and input or output. WDM seems to work better than WASAPI,
            # especially for 24b
            playback_device = sd.query_devices(device="XVF38 WDM", kind="output")['index']
            recording_device = sd.query_devices(device="XVF38 WDM", kind="input")['index']
    except sd.PortAudioError as err:
        print("PortAudioError")
        print(err)
        print("Unique 38xx device not found")
        if exit_on_failure:
            exit(7)
        else:
            raise

    playback_channels = [1, 2]
    recording_channels = [1, 2]

    # duplicate mono input signals
    if playback_signal.shape[1] == 1:
        playback_signal = np.tile(playback_signal, [1, 2])

    try:
        mic = sd.playrec(playback_signal,
                         fs,
                         blocking=True,
                         channels=len(recording_channels),
                         device=(recording_device, playback_device),
                         input_mapping=recording_channels,
                         output_mapping=playback_channels,
                         dtype='int32',
                         dither_off=True)
    except sd.PortAudioError as err:
        print("PortAudioError")
        print(err)
        print("Make sure device is flashed with %d sample rate, or change recording sample rate" % fs)
        if exit_on_failure:
            exit(7)
        else:
            raise

    if out_filepath:
        sf.write(out_filepath, mic, fs, subtype="PCM_%d" % bit_depth)

    return


def main(args: argparse.Namespace):

    set_packing(args)
    if args.packed_output:
        playrec_packed(args.playback_file, args.packed_output_file,
                       args.recording_length, 48000, args.bit_depth)

        print("Unpacking")
        packing.unpack(args.packed_output_file, args.unpacked_output_file, skip_leading_zeros=True)
    else:
        # if not packed output, save to unpacked_rec.wav, no need to unpack
        playrec_packed(args.playback_file, args.unpacked_output_file,
                       args.recording_length, 48000, args.bit_depth)

    return


def set_argparser(argparser: argparse.ArgumentParser):

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
        "--bit_depth",
        "-b",
        type=int,
        default=24,
        action="store",
        help="Packed audio recording bit depth",
    )

    argparser.add_argument(
        "--playback_file",
        "-pb",
        type=Path,
        default=None,
        action="store",
        help="Path to the file to be played back",
    )

    argparser.add_argument(
        "--packed_input",
        "-pin",
        default=False,
        action="store_true",
        help="Set input audio to packed",
    )

    argparser.add_argument(
        "--packed_output",
        "-pout",
        default=False,
        action="store_true",
        help="Set output audio to unpacked",
    )

    argparser.add_argument(
        "--asr_output",
        default=False,
        action="store_true",
        help="Enable the automatic speech-recognition output before packed capture",
    )

    argparser.add_argument(
        "--recording_length",
        "-l",
        type=float,
        default=None,
        action="store",
        help="Recording length in seconds",
    )

    argparser.add_argument(
        "--packed_output_file",
        "-po",
        type=Path,
        default=Path("packed_rec.wav"),
        action="store",
        help="Save path for the packed audio",
    )

    argparser.add_argument(
        "--unpacked_output_file",
        "-upo",
        type=Path,
        default=Path("unpacked_rec.wav"),
        action="store",
        help="Save path for the unpacked audio",
    )

    argparser.add_argument(
        "--op_all",
        "-oa",
        type=str,
        default="12 0  3 0  3 2  6 3  3 1  3 3",
        action="store",
        help='Specify packed input channels for AUDIO_MGR_OP_ALL command. Defaults to "%(default)s"'
    )

    return argparser


if __name__ == "__main__":

    # parse the command line parameters
    argparser = argparse.ArgumentParser(
        description="XMOS XVF38xx packed data recorder"
    )

    argparser = set_argparser(argparser)

    args = argparser.parse_args()

    main(args)
