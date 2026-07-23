# Copyright 2023-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
"""
This script is used for the training of the Non-Linear Echo Suppression model. The same device that the script is run on is used
for playing audio into the XVF3800. Control is run on a remote RPi that is connected to the device. The IP address of the remote RPi is
given as an input argument to the script.

Usage: python3 remote_nl_model_training.py <Remote RPi IP address> <Path to the host app binaries>
eg. python3 remote_nl_model_training.py 192.168.68.59 ~/Downloads/xvf3800_bin_external_230222_190451/host_v0.2.0/rpi/

Python requirements for running the script:
  1. python3
  2. matplotlib
  3. asyncssh

Before running the script, ensure the following:
  1. The host app binaries are available
  2. ssh is enabled on the remote RPi and passwordless access to it from the machine running the script is enabled.
  3. sox is installed on the machine connected to the xvf3800 device.
  4. XVF3800 must be configured as the default microphone input and speaker output device.

When running, the script does the following:
  1. Run the SHF commands via the selected interface on the remote RPi and play and record audio from the XVF3800 device.
  2. Retrieve the Non-Linear model coefficients, store them in a .bin file, plot the NL model and save the plot image file. The --output and
     --output-dir options can be used to change the name of the output binary file and the output directory. The plot image file name is derived
     from the output binary file name and is stored in the same directory as the binary file.

After running this script, the following steps need to be done manually.
  1. Copy the generated .bin file to <Device Software release package>/sources/app_xvf3800/nl_model_gen/nlmodel_bin/ and rerun the build process.
  2. By default, the output NL model .bin file name is called nlmodel_buffer_override.bin.r16.c40, where the .r16.c40 extension indicates that there are
     16 rows and 40 columns in the NL model matrix. When specifying a different file name using the --output option,
     in addition to copying the generated .bin file in <Device Software release package>/sources/app_xvf3800/nl_model_gen/nlmodel_bin/, the
     <Device Software release package>/sources/app_xvf3800/CMakeLists.txt file would also need changing to include this new file in the build process.

Return values:
     Refer to tuning_utils.nl_tuning_error_codes class for return error codes
"""

from nlmodel_tuning import tuning_utils
from pathlib import Path
import argparse


def parse_arguments():
    parser = argparse.ArgumentParser("remote nlmodel training script")
    parser.add_argument('pi_ip_address', type=str, help="IP address of the Pi to connect to")
    parser.add_argument('host_bin_path', type=str, help="Host app package directory. When using the release package, this will be, <Device bin release package>/host_vX.Y.Z/rpi")
    parser.add_argument('--quick-test', '-q', action='store_true', help='run quick test')
    parser.add_argument('--protocol', '-p',
        type = str.lower,
        default = 'i2c',
        action = 'store',
        choices = ['i2c','spi'],
        help = 'Communication protocol used to control the device, default: i2c')
    parser.add_argument('--output', '-o', type=str, default='nlmodel_buffer_override.bin', help='Output NL model bin file name specified as <filename>.bin. Default, nlmodel_buffer_override.bin. If providing a name different from nlmodel_buffer_override.bin, application cmake file <Device Software release package>/sources/app_xvf3800/CMakeLists.txt will need to be modified to build with the new file')
    parser.add_argument('--output-dir', '-d', type=str, default='src.autogen', help='Directory where output files are stored')
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_arguments()
    control_protocol = args.protocol.lower()

    control_obj = tuning_utils.nl_tuning_control_remote_pi(args.pi_ip_address, args.host_bin_path, control_protocol=control_protocol) # Control run on a remote Pi
    audio_obj = tuning_utils.nl_tuning_audio_player(protocol=control_protocol, product_name="XVF3800")

    pwd = Path(__file__).parent
    wavs = tuning_utils.TuningWavFiles(
            first = pwd / "audio_files" / "nlaec0_16k_stereo.wav",
            second = pwd / "audio_files" / "nlaec12_16k_stereo.wav",
            third = pwd / "audio_files" / "nlaec12_16k_stereo.wav")
    tuning_utils.run_nl_model_tuning_3800(audio_obj, control_obj, args.output_dir, args.output, wavs, args.quick_test)
    control_obj.cleanup()
