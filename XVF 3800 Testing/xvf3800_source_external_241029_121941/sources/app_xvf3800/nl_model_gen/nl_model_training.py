# Copyright 2017-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
#!/usr/bin/env python3

"""
This script is used for the training of the Non-Linear Echo Suppression model. The host device that this script is run on acts as the audio
host as well as the control host to the XVF3800 device that is connected to it.

MacOS, Windows and Linux (Raspberry Pi4 as well as generic Linux) host systems are supported.
Both XVF3800 INT and UA device variants are supported.

If using a XVF3800 INT device to tune the NL model, this script can only run on a Raspberry Pi with either I2C or SPI control protocol used for sending commands to the device.
If using a XVF3800 UA device to tune the NL model, this script can run on all supported host systems and only USB control protocol is used for sending
control commands to the device.

Usage: python3 nl_model_training.py <host_app_bin> <--protocol [i2c|spi|usb]>

Example, python3 nl_model_training.py Downloads/archive/xvf3800_bin_external_230530_131747/host_v1.0.0/rpi/xvf_host -p i2c

Before running the script, ensure the following:
  1. The host app package is available. This can be found in the release package.
  2. XVF3800 device is flashed with the appropriate FW.
     When using I2C or SPI control, flash the XVF3800 with the application_xvf3800_intdev-lr16-lin-i2c.xe or application_xvf3800_intdev-lr16-lin-spi.xe respectively.
     When using USB control, flash the XVF3800 with application_xvf3800_ua-io16-lin.xe FW executable.
  3. XVF3800 must be configured as the default microphone input and speaker output device on the host system running this script. There is one exception for this;
  when running on a Linux host, the user need not set the default device, instead, this script will find the XVF3800 device from the list of audio devices and play and record from it.
  4. When running with Windows as the host, sox is installed and present in the path.

When running, the script performs the following operations:
  1. Sends SHF control commands to the XVF3800 device via the selected control interface and plays some specific audio files to the XVF3800 device
  2. Retrieves the Non-Linear model coefficients from the device over the control interface, stores them in a .bin file, plot the NL model and saves the plot image file.
     The --output and --output-dir options can be used to change the name of the output binary file and the output directory. The plot image file name is derived
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
import argparse
import os
from nlmodel_tuning import tuning_utils
from pathlib import Path

def parse_arguments():
    parser = argparse.ArgumentParser(description='XMOS BeClear Non-Linear Model Tuning script')
    parser.add_argument('host_app',
        type = str,
        help = 'Host app that will be used for issuing control commands while running this script')
    parser.add_argument('--protocol', '-p',
        type = str.lower,
        default = 'usb',
        action = 'store',
        choices = ['i2c','spi', 'usb'],
        help = 'Communication protocol used to control the device, default: usb')
    parser.add_argument('--output', '-o', type=str, default='nlmodel_buffer_override.bin', 
                        help=('Output NL model bin file name specified as <filename>.bin. Default, nlmodel_buffer_override.bin. If'
                              ' providing a name different from nlmodel_buffer_override.bin, application cmake file '
                              '<Device Software release package>/sources/app_xvf3800/CMakeLists.txt will need to be modified to build with the new file'))
    parser.add_argument('--output-dir', '-d', type=str, default='src.autogen', help='Directory where output files are stored')
    parser.add_argument('--quick-test', '-q', action="store_true", help="Run a quick sanity test. Only for testing. Shouldn't be used during the actual tuning process")

    args = parser.parse_args()
    return args

if __name__ == '__main__':
    # Parse the command line parameters
    args = parse_arguments()

    # Normalize path to support Windows platforms
    host_bin_file = Path(args.host_app)
    host_bin_file = os.path.normpath(host_bin_file) # For Windows apparently
    control_protocol = args.protocol.lower()

    audio_obj = tuning_utils.nl_tuning_audio_player(protocol=control_protocol, product_name="XVF3800")
    control_obj = tuning_utils.nl_tuning_control(host_bin_file, control_protocol=control_protocol)
    pwd = Path(__file__).parent
    wavs = tuning_utils.TuningWavFiles(
            first = pwd / "audio_files" / "nlaec0_16k_stereo.wav",
            second = pwd / "audio_files" / "nlaec12_16k_stereo.wav",
            third = pwd / "audio_files" / "nlaec12_16k_stereo.wav")
    tuning_utils.run_nl_model_tuning_3800(audio_obj, 
                                          control_obj, 
                                          args.output_dir, 
                                          args.output,
                                          wavs,
                                          args.quick_test)
