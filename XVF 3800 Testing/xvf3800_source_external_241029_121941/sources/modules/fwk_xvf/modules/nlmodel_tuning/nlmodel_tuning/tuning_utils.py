# Copyright 2017-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
#!/usr/bin/env python

"""
File to store the common functions
"""

import os, sys, re, subprocess, time, matplotlib
from datetime import datetime
from pathlib import Path
from collections import namedtuple
from . import gen_nlmodel_c_file
import time
import traceback
from tuning.host_utils import basic_xvf_host


MATPLOTLIB_VERSION_MIN = "3.0.2"

"""
Class containing NL tuning process return error codes
"""
class nl_tuning_error_codes:
    NL_TUNING_SUCCESS = 0
    NL_TUNING_UNSUPPORTED_PLATFORM = 1
    NL_TUNING_INVALID_HOSTAPP = 2
    NL_TUNING_CONTROL_ERROR = 3
    NL_TUNING_MISSING_AUDIO_FILE = 4
    NL_TUNING_AUDIO_FILE_PLAYBACK_ERROR = 5
    NL_TUNING_AUDIO_FILE_RECORDING_ERROR = 6

"""
Class containing functions for playing audio to the device during NL Model tuning
"""
class nl_tuning_audio_player:
    def __init__(self, protocol="usb", product_name="XVF3800"):
        self.error_obj = nl_tuning_error_codes()
        self.product_name = product_name
        supported_platforms = ["darwin", "win32", "linux", "linux2"]

        # check if the current platform is supported
        if sys.platform not in supported_platforms:
            print("Error: platform " + sys.platform + " not supported")
            print("Supported platforms: " + ", ".join(supported_platforms))
            exit(self.error_obj.NL_TUNING_UNSUPPORTED_PLATFORM)

        # set the different parameters for the supported platforms
        if sys.platform == "darwin":
            self.audio_play_cmd = "afplay {}"
            self.audio_rec_cmd = "rec"
        elif sys.platform == "linux2" or sys.platform == "linux":
            if protocol == "usb": # On a Pi, USB device is not the default play and record device, so we need to get the XVF38xx UA alsa device details and then play/record on it.
                output = subprocess.check_output("arecord -l".split()).decode("utf-8").split('\n')
                self.dev_rec = self.find_alsa_device(output, product_name)
                output = subprocess.check_output("aplay -l".split()).decode("utf-8").split('\n')
                self.dev_play = self.find_alsa_device(output, product_name)
                self.audio_play_cmd = "aplay {} " + f"-D hw:{self.dev_play[0]},{self.dev_play[1]}"
                self.audio_rec_cmd = f"arecord -D hw:{self.dev_rec[0]},{self.dev_rec[1]} -c 2 -f S16_LE -r 16000"
                self.enable_io_expander(False)
            else: # On the Pi, INT device is the default device so we play/record without specifying the -D argument
                self.audio_play_cmd = "aplay {}"
                self.audio_rec_cmd = f"arecord"
                self.enable_io_expander(True)

        elif sys.platform == "win32":
            self.audio_play_cmd = "sox {} -t waveaudio 0"
            self.audio_rec_cmd = "sox -t waveaudio 0"

    # Enable or disable the IO expander on the Pi. Relevant only when running on RPi host.
    def enable_io_expander(self, enable):
        output = subprocess.check_output("uname -a".split()).decode('utf-8')
        if "raspberrypi" in output:
            if enable:
                setup_io_exp_and_dac = subprocess.check_output(f"find /home/ -name setup_io_exp_and_dac.py".split()).decode("utf-8").split('\n')[0]
                if setup_io_exp_and_dac:
                    subprocess.run(f"python {setup_io_exp_and_dac} {self.product_name.lower()}-intdev".split(), check=True)
            else:
                # Only import when we know we are on a pi
                from . import disable_io_exp
                disable_io_exp.clear_io_expander()

    # Find ALSA XVF38xx UA device details. Relevant only for linux
    def find_alsa_device(self, alsa_output, vendor_str_search):
        """ Looks for the vendor_str_search in aplay or arecord output """
        vendor_str_found = False
        for line in alsa_output:
            if vendor_str_search not in line:
                continue
            vendor_str_found = True
            card_num = int(line[len('card '):line.index(':')])
            dev_str = line[line.index('device'):]
            dev_num = int(dev_str[len('device '):dev_str.index(':')])
        if not vendor_str_found:
            raise RuntimeError(
                f'Could not find "{vendor_str_search}"" in alsa output:\n'
                f"{alsa_output}"
            )
        return card_num, dev_num

    # Function to play an audio file
    def play_audio_file(self, audio_file, quick_play=False):
        print("Playing audio file " + audio_file)
        if os.path.isfile(audio_file):
            temp_file = Path("temp.wav")
            rec_command = f"{self.audio_rec_cmd} {temp_file}"
            rec_process = subprocess.Popen(rec_command.split())

            audio_playback_error = False
            try:
                aplay_cmd = self.audio_play_cmd.format(audio_file)

                play_process = subprocess.Popen(aplay_cmd.split())
                if not quick_play:
                    play_process.wait()
                else:
                    time.sleep(5)
                    play_process.kill()

            except Exception as e:
                print(e)
                audio_playback_error = True

            if rec_process.poll():
                # subprocess exited with non-zero return code
                exit(self.error_obj.NL_TUNING_AUDIO_FILE_RECORDING_ERROR)
            if sys.platform == "win32":
                # On some Windows systems the parent process is not killed by suprocess, so force the kill operation
                subprocess.run(f"taskkill /F /im {rec_command.split()[0]}*".split(), capture_output=True)
            else:
                rec_process.kill()
                rec_process.wait()
            time.sleep(1)
            Path(temp_file).unlink()

            if audio_playback_error:
                exit(self.error_obj.NL_TUNING_AUDIO_FILE_PLAYBACK_ERROR)
        else:
            print("Error: file " + audio_file + " not present")
            exit(self.error_obj.NL_TUNING_MISSING_AUDIO_FILE)

"""
Class containing functions for running control commands on
the same device where the NL model tuning script is running.
"""
class nl_tuning_control(basic_xvf_host):
    def read_nl_model_from_device(self, output_dir, output_name, band=0):
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        nlmodel_bin_file = Path(output_dir) / Path(output_name)
        # Read NL model from the device
        cmd = f'-gn {nlmodel_bin_file}'
        if band:
            cmd += f" --band {band}"
        stdout = self.run_control_command(cmd)
        m = None
        for line in stdout.splitlines():
            m = re.match(r"^\s*Filename\s*=\s*(\S*\.r[0-9]+\.c[0-9]+)", line.strip())
            if m:
                break
        assert(m != None)
        binfile_name = m.group(1)
        print(f"\nNL model saved in output directory {output_dir}")
        print(f"Output NL model binary file = {binfile_name}")
        # Plot the NL model and save the plot file
        gen_nlmodel_c_file.plot_nlmodel(output_dir, bin_files=[binfile_name])


"""
Class containing functions for running control commands remotely
on an RPi which is connected to the device.
"""
class nl_tuning_control_remote_pi:
    def __init__(self, pi_ip_addr, host_bin_path, control_protocol="i2c"):
        self.error_obj = nl_tuning_error_codes()
        from . import remote_rpi

        # Connect to the Pi
        self.dir_name = f"/tmp/sw_xvf38xx-{datetime.now().strftime('%Y%d%m-%H%M%S%f')}"

        rpi = remote_rpi.remote_pi_access(pi_ip_addr, self.dir_name, "pi")
        assert rpi.cmd("whoami").strip() == rpi.username, f"Failed to connected to pi at {rpi.username}@{rpi.server_ip}"

        rpi.cmd(f"mkdir {self.dir_name}", check=True)
        self.rpi = rpi

        self.host_bin_path = Path(host_bin_path)
        if not self.host_bin_path.is_dir():
            print(f"Invalid host app package path {self.host_bin_path}")
            exit(self.error_obj.NL_TUNING_INVALID_HOSTAPP)

        self.control_protocol = control_protocol
        self.host_app = self.get_host_app()
        rpi.cmd(f"chmod a+x {rpi.dest_working_dir}/xvf_host")

    def cleanup(self):
        if self.rpi:
            self.rpi.cmd(f"rm -rf {self.dir_name}")

    def get_host_app(self):
        host_bin = "xvf_host"
        command_map_lib = "libcommand_map.so"
        i2c_lib = f"libdevice_i2c.so"
        spi_lib = f"libdevice_spi.so"
        host_app = self.host_bin_path/host_bin
        command_map_lib_path = self.host_bin_path/command_map_lib
        i2c_lib_path = self.host_bin_path/i2c_lib
        spi_lib_path = self.host_bin_path/spi_lib

        assert Path(host_app).is_file()
        assert Path(command_map_lib_path).is_file()
        assert Path(i2c_lib_path).is_file()
        assert Path(spi_lib_path).is_file()

        # Send the host app and dynamic lib to the temp dir in PI
        self.rpi.send_file(host_app, host_bin)
        self.rpi.send_file(command_map_lib_path, command_map_lib)
        self.rpi.send_file(i2c_lib_path, i2c_lib)
        self.rpi.send_file(spi_lib_path, spi_lib)

        return self.rpi.dest_working_dir + "/" + host_bin

    def run_control_command(self, cmd, verbose=False):
        command_str = f"sudo {self.host_app} -u {self.control_protocol} {cmd}"
        stdout = self.rpi.cmd(command_str, check=True)

        # Return the last line of the console output
        return stdout

    def read_nl_model_from_device(self, output_dir, output_name, band=0):
        os.makedirs(output_dir, exist_ok=True)

        command_str = f"--get-nlmodel-buffer {self.rpi.dest_working_dir}/{output_name}"
        if band:
            cmd += f" --band {band}"
        stdout = self.run_control_command(command_str)
        m = None
        for line in stdout.splitlines():
            m = re.match(r"^\s*Filename\s*=\s*(\S*\.r[0-9]+\.c[0-9]+)", line.strip())
            if m:
                break
        assert(m != None)
        binfile_name = Path(m.group(1)).name

        local_filename = Path(f"{output_dir}/{binfile_name}")
        self.rpi.fetch_file(f"{local_filename}", src=binfile_name)
        assert local_filename.is_file()
        gen_nlmodel_c_file.plot_nlmodel(output_dir, bin_files=[f"{local_filename}"])

        print(f"\nNL model saved in output directory {output_dir}")
        print(f"Output NL model binary file = {local_filename}")

    def set_bit_depth(self, in_bit_depth, out_bit_depth):
        if self.control_protocol == "usb":
            print(f"Setting bit_depth to {in_bit_depth} {in_bit_depth}")
            return self.run_control_command(f"USB_BIT_DEPTH {in_bit_depth} {out_bit_depth}")

# Container for the paths used in nlmodel tuning
TuningWavFiles = namedtuple("TuningWavFiles", ["first", "second", "third"])

def tuning_start_common(control_obj):
    print("\nRunning NL model tuning script")
    cmd = "VERSION"
    stdout = control_obj.run_control_command(cmd)
    print(f"Running FW version v{'.'.join(stdout.splitlines()[-1].split()[1:])}\n")

    if sys.platform == "linux2" or sys.platform == "linux":
        # On linux, we specify the device in the aplay and arecord command line instead of using the default device,
        # since the default device is the I2S device on RPi, so the aparams settings need to exactly match the audio files
        # that are played to the device. The audio files are 16bit, so change the usb bit depth to 16bit otherwise we get the
        # aplay: set_params:1343: Sample format non available error.
        control_obj.set_bit_depth(16, 16)
        time.sleep(10) # Wait for device to re-enumerate



def run_nl_model_tuning_3800(audio_obj, control_obj, output_dir, output_name, wavs: TuningWavFiles, quick_test=False):
    """ Run NL Model tuning steps for 3800. This uses the WB algorithm so only generates a single binary file"""
    tuning_start_common(control_obj)

    # Initialise SHF
    control_obj.run_control_command('PP_ECHOONOFF 0')
    control_obj.run_control_command('PP_NLATTENONOFF 0')
    control_obj.run_control_command('PP_AGCONOFF 0')

    # set initilization BeClear parameters
    control_obj.run_control_command('PP_NLATTENONOFF 1')
    control_obj.run_control_command('PP_NLAEC_MODE 0')

    audio_obj.play_audio_file(str(wavs.first), quick_play=quick_test)
    control_obj.run_control_command('PP_NLAEC_MODE 1') # set NLAEC mode to train first part of the non-linear model

    audio_obj.play_audio_file(str(wavs.second), quick_play=quick_test)
    control_obj.run_control_command('PP_NLAEC_MODE 2') # set NLAEC mode to train second part of the non-linear model

    audio_obj.play_audio_file(str(wavs.third), quick_play=quick_test)
    control_obj.run_control_command('PP_NLAEC_MODE 0') # reset NLAEC mode

    # Read the NL model from the device
    control_obj.read_nl_model_from_device(output_dir, output_name)

def run_nl_model_tuning_3820(audio_obj, control_obj, output_dir, output_name, wavs: TuningWavFiles, quick_test=False):
    """
    Run NL Model tuning steps for 3820, uses BeClearSWB. Generates 2 models, one for high band and
    one for low
    """
    tuning_start_common(control_obj)

    # Initialise SHF
    control_obj.run_control_command('PP_ECHOONOFF 0')
    control_obj.run_control_command('PP_NLATTENONOFF 0')
    control_obj.run_control_command('AEC_AGCONOFF 0')

    # set initilization BeClear parameters
    control_obj.run_control_command('PP_NLATTENONOFF 1')
    control_obj.run_control_command('PP_NLAEC_MODE 0')

    audio_obj.play_audio_file(str(wavs.first), quick_play=quick_test)
    control_obj.run_control_command('PP_NLAEC_MODE 1') # set NLAEC mode to train first part of the non-linear model

    audio_obj.play_audio_file(str(wavs.second), quick_play=quick_test)
    control_obj.run_control_command('PP_NLAEC_MODE 2') # set NLAEC mode to train second part of the non-linear model

    audio_obj.play_audio_file(str(wavs.third), quick_play=quick_test)
    control_obj.run_control_command('PP_NLAEC_MODE 0') # reset NLAEC mode

    # Read the NL model from the device
    control_obj.read_nl_model_from_device(output_dir, output_name + ".low", band=0)
    control_obj.read_nl_model_from_device(output_dir, output_name + ".high", band=1)
