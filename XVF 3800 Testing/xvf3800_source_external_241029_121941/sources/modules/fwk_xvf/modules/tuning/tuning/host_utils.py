# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
"""
Host app class with basic functionality
"""

import os
import subprocess
import sys
import time
from pathlib import Path
import traceback
import numpy as np

class xvf_host_error_codes:
    XVFHOST_SUCCESS = 0
    XVFHOST_UNSUPPORTED_PLATFORM = 1
    XVFHOST_INVALID_HOSTAPP = 2
    XVFHOST_CONTROL_ERROR = 3

class basic_xvf_host:
    """
    Class containing functions for running control commands using the xvf_host
    """
    def __init__(self, host_app_bin, control_protocol="i2c"):
        self.error_obj = xvf_host_error_codes()
        supported_platforms = ["linux", "linux2", "darwin", "win32"]
        # check if the current platform is supported
        if sys.platform not in supported_platforms:
            print("Error: platform " + sys.platform + " not supported")
            print("Supported platforms: {supported_platforms}.")
            exit(self.error_obj.XVFHOST_UNSUPPORTED_PLATFORM)
        # set the different parameters for the supported platforms
        if sys.platform == "darwin":
            self.bin_prefix = ""
            self.bin_suffix = ""
        elif sys.platform == "linux2" or sys.platform == "linux":
            self.bin_prefix = "sudo "
            self.bin_suffix = ""
        elif sys.platform == "win32":
            self.bin_prefix = ""
            self.bin_suffix = ".exe"
        else:
            print("Error: platform " + sys.platform + " not supported")
            print("Supported platforms: " + ", ".join(supported_platforms))
            exit(self.error_obj.XVFHOST_UNSUPPORTED_PLATFORM)

        # add bin suffix if required
        host_app_bin = Path(host_app_bin)
        if host_app_bin.suffix != self.bin_suffix:
            host_app_bin = host_app_bin.parent / (host_app_bin.name + self.bin_suffix)

        if os.path.isfile(host_app_bin):
            self.host_bin_file = host_app_bin
        else:
            print("Error: file " + str(host_app_bin) + " not present")
            exit(self.error_obj.XVFHOST_INVALID_HOSTAPP)
        self.control_protocol = control_protocol

    def cleanup():
        return

    def run_control_command(self, cmd, verbose=False):
        """Do it all generic control command, no fancy stuff"""
        if verbose:
            print("Setting " + cmd)
        if sys.platform == "win32":
            # Avoid shell=True: spaces in Windows release paths otherwise split xvf_host.exe.
            cmd_full = [str(self.host_bin_file), "-u", self.control_protocol, *str(cmd).split()]
        else:
            cmd_full = f"{self.bin_prefix}{self.host_bin_file} -u {self.control_protocol} {cmd}"
        try:
            output = None
            for attempt in range(3):
                output = subprocess.run(cmd_full, shell=False if sys.platform == "win32" else True, capture_output=True)
                if output.returncode == 0:
                    break
                if attempt < 2:
                    print(f"Control command retry {attempt + 1}/2 after exit code {output.returncode}")
                    time.sleep(2.0)
            output.check_returncode()
        except subprocess.CalledProcessError:
            traceback.print_exc()
            print("Tried setting " + cmd)
            print(output.stderr.decode("utf-8"))
            exit(self.error_obj.XVFHOST_CONTROL_ERROR)

        return output.stdout.decode("utf-8")

    def set_control_command(self, cmd, val, check=True, verbose=False):
        """
        Set control command to value, check it returns the new value.
        Values can be passed as int/float/str, and will be converted to str before sending.
        If setting multiple values, these can be passed as a single string or a list.
        Note certain commands cannot be checked as they either reset the device
        or do not return in the same format as setting.

        Examples:
        control_obj.set_control_command("AUDIO_MGR_MIC_GAIN", "1.0")
        control_obj.set_control_command("USB_BIT_DEPTH", "16 16", check=False)
        control_obj.set_control_command("AUDIO_MGR_OP_ALL", [12, 0, 3, 0, 3, 2, 6, 3, 3, 1, 3, 3], check=False)

        """
        if isinstance(val, list):
            val_str = ' '.join(str(x) for x in val)
            cmd_val = f"{cmd} {val_str}"
        else:
            cmd_val = f"{cmd} {val}"

        if verbose:
            print("Setting " + cmd_val)

        stdout = self.run_control_command(cmd_val)

        if check:
            stdout = self.run_control_command(cmd)
            # Search for values in the last line of the console output
            returned_vals = (stdout.splitlines()[-1].strip()).split()
            sent_vals = str(val).strip().split()

            # This will check that the right command is returned
            assert returned_vals[0] == cmd, f"{returned_vals[0]} == {cmd}"

            for sent_val, returned_val in zip(sent_vals, returned_vals[1:]):
                assert np.isclose(float(sent_val), float(returned_val)), f"failed to read back the written values - got {returned_val}, sent {sent_val}"

        return stdout

    def get_control_command(self, cmd, verbose=False):
        """Get the values returned by a control command, stripping off the command itself"""

        stdout = self.run_control_command(cmd)
        # Search for the values in the last line of the console output
        returned_vals = (stdout.splitlines()[-1].strip()).split()

        # This will check that the right command is returned
        assert returned_vals[0] == cmd, f"{returned_vals[0]} == {cmd}"

        # strip the command, just return the values
        if len(returned_vals) == 2:  # cmd and 1 value
            return returned_vals[1]
        return returned_vals[1:]  # list of just returned values

    def set_bit_depth(self, in_bit_depth, out_bit_depth, verbose=False):
        if self.control_protocol == "usb":
            if verbose:
                print(f"Setting bit_depth to {in_bit_depth} {in_bit_depth}")
            # check does not work for setting bit depth
            return self.set_control_command("USB_BIT_DEPTH", f"{in_bit_depth} {out_bit_depth}", check=False)
