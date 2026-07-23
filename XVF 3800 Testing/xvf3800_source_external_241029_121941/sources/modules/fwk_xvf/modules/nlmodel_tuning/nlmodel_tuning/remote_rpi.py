# Copyright 2022-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
"""
Functions and classes for interacting with a remote rpi, otheriwise known as a test rig
"""
import sys
import asyncio
import asyncssh
import subprocess
import shutil
from enum import Enum, auto
from time import sleep
from pathlib import Path

# audio device created by vocalfusion-rpi-setup which
# can dynamically change sample_rate
I2S_AUDIO_DEVICE = "hw:sndrpisimplecar,0"


class _MclkState(Enum):
    """available mclk states, used below to determine if mclk is enabled"""
    UNKNOWN = auto()
    ENABLED = auto()
    DISABLED = auto()


# Class to manipulate a remote RPI using ssh/scp commands
# First add the host public key to the target's allowed SSH keys. Note you must enable SSH on the target.
# https://www.raspberrypi.org/documentation/remote-access/ssh/passwordless.md
class remote_pi_access:
    def __init__(self, server_ip, dest_working_dir, username="pi"):
        self.username           = username
        self.server_ip          = server_ip
        self._dest_working_dir   = dest_working_dir
        self.sample_rate = 0
        self._mclk_state = _MclkState.UNKNOWN

    def _make_scp_remote_path(self, file):
        path = self.server_ip + ":" + self.dest_working_dir + "/" + file
        return path

    def _do_scp(self, src, dst, recurse):
        async def run_client():
            await asyncssh.scp(src, dst, username=self.username, recurse=recurse)
        try:
            asyncio.run(run_client())
        except (OSError, asyncssh.Error) as exc:
            print('SFTP operation failed: ' + str(exc), file=sys.stderr)

    @property    
    def dest_working_dir(self):
        return self._dest_working_dir

    @dest_working_dir.setter
    def dest_working_dir(self, new_dir):
        self._dest_working_dir = new_dir

    def cmd(self, cmd, verbose=True, _bg=False, timeout_s=None, check=False, return_exception=False):
        """
        Run a command on the remote device over ssh
        
        Args:
            cmd: str, the command to run
            verbose: bool, cat the output
            _bg: not used
            timeout_s: [int, float, None], time for client to wait 
            check: bool, assert exit status
        """
        if verbose:
            print(f'Connecting to "{self.server_ip}" with command "{cmd}"')

        async def run_client():
            async with asyncssh.connect(self.server_ip, username=self.username) as conn:
                return await conn.run(cmd, check=True, timeout=timeout_s)

        try:
            result = asyncio.run(run_client())
            if verbose:
                print("Command returned:",result.stdout)
            if check:
                assert 0 == result.exit_status, "Command returned non-zero"
            if return_exception:
                return result.stdout, None
            else:
                return result.stdout

        except Exception as exc:
            print('SSH connection failed executing:', cmd, file=sys.stderr)
            print('OS Error code:', str(exc))
            print(type(exc), exc.stdout, exc.stderr, file=sys.stderr)
            if check:
                raise
            if return_exception:
                return None, str(exc.stderr)

    def reboot(self):
        rpi_connected = False
        INITIAL_PAUSE_S = 10
        POST_PAUSE_S = 5 # ensure SSH service and others have come up after successful ping
        RETRY_TIMEOUT_S = 1
        MAX_NUMBER_RETRIES = 30

        # Reboot the Raspberry Pi before starting the test
        reboot_script_file = "reboot.sh"
        with open(reboot_script_file, "wt") as script_file:
            script_file.write("sudo shutdown -r now")

        self.send_file(str(reboot_script_file))
        self.cmd(f"sh {self.dest_working_dir}/{reboot_script_file}", verbose=True)
        # Wait few seconds for the Raspberry to shutdown and go offline
        sleep(INITIAL_PAUSE_S)
        # Wait for the Raspberry Pi to reconnect
        for i in range(MAX_NUMBER_RETRIES):
            # Check if ping command is successful
            result = subprocess.run(f"ping -c 1 {self.server_ip}".split(), capture_output=True)

            if result.returncode == 0:
                sleep(POST_PAUSE_S)
                print(f"Raspberry Pi at {self.server_ip} reconnected after {INITIAL_PAUSE_S+RETRY_TIMEOUT_S*i+POST_PAUSE_S} seconds")
                rpi_connected = True
                break

            sleep(RETRY_TIMEOUT_S)
            print(f"Wait {RETRY_TIMEOUT_S} seconds for {self.server_ip} to reconnect")
   
        assert rpi_connected, f"Error: Raspberry Pi {self.server_ip} not found after {INITIAL_PAUSE_S+RETRY_TIMEOUT_S*MAX_NUMBER_RETRIES} seconds"

    # send a file from the host to the remote device. If no dst is specified then the src file name is used
    def send_file(self, src, dst=None, recurse=False):
        if not dst:
            dst = self._make_scp_remote_path(src)
        else:
            dst = self._make_scp_remote_path(dst)
        self._do_scp(src, dst, recurse)

    # fetch a file from the the remote device to the host. If no src is specified then the dst file name is used
    def fetch_file(self, dst, src=None, recurse=False):
        if not src:
            src = self._make_scp_remote_path(dst)
        else:
            src = self._make_scp_remote_path(src)
        self._do_scp(src, dst, recurse)

    def ready_for_samplerate(self, rate: int):
        """Determine if this pi is ready to play the requested sample rate"""
        return (self._mclk_state == _MclkState.DISABLED 
                or (self.sample_rate == rate and self._mclk_state == _MclkState.ENABLED))

    def update_mclk_state(self, enabled: bool):
        """
        Change the mclk state, does nothing if it is currently in the correct state.
        Otherwise it sets the mclk drive state on the pi.
        """
        if ((enabled and (self._mclk_state != _MclkState.ENABLED))
            or ((not enabled) and (self._mclk_state != _MclkState.DISABLED))):

            # This section enables/disables the level shifter between Pi and XVF3800
            enable_mclk = self.cmd(f"find /home/{self.username} -name setup_io_exp_and_dac.py").split()[0].strip()
            assert enable_mclk, "setup_io_exp_and_dac.py not found on this pi"
            
            cmd = f"python {enable_mclk}"
            if enabled:
                cmd += " xvf3800-intdev-extmclk"
            else:
                cmd += " xvf3800-intdev"

            self.cmd(cmd, check=True)

            # This section enables/disables the drive of mclk from the Pi
            setup_mclk = self.cmd(f"find /home/{self.username} -name setup_mclk").split()[0].strip()
            assert setup_mclk, "setup_mclk not found on this pi"
            
            cmd = f"sudo {setup_mclk}"
            if not enabled:
                cmd += " --disable"

            self.cmd(cmd, check=True)
            self._mclk_state = _MclkState.ENABLED if enabled else _MclkState.DISABLED

    def prepare_for_sample_rate(self, sample_rate):
        """
        A sneaky hack to make the clocks work. This function takes a very short recording
        at the desired sample rate. This updates the raspberry pi's I2S kernel module to think
        it has correctly configured the clocks and won't do it again until a different rate
        is requested.
        After this, run setup_blk which manually hacks the PCM_CLK register in the raspberry pi's
        clk control registers to run at the desired rate (phase locked with the MCLK). After calling
        this function experimentation has shown that arecord/aplay will behave correctly so 
        long as the specified rate is used.
        Note: on an rpi 4b this is not necessary because it's clock rate of 750Mhz has 0 ppm divider
        values for all of our desired frequencies, so the underlying driver reliably picks these values
        (for 16kHz and 48kHz audio only)
        """

        # Hunt for the exe so this "just works" 
        setup_bclk = self.cmd(f"find /home/{self.username} -name setup_bclk").split()[0].strip()
        assert setup_bclk, "setup_bclk not found on this pi"

        if sample_rate == 48000:
            setup_bclk_rate = ""
        elif sample_rate == 16000:
            setup_bclk_rate = "16000"
        else:
            assert False, "bad rate"
        self.cmd(f"arecord -c2 -fS32_LE -r{sample_rate} -s1 -D{I2S_AUDIO_DEVICE} /dev/null")
        self.cmd(f"sudo {setup_bclk} {setup_bclk_rate}")
        self.sample_rate = sample_rate

def play_and_record_remote( testrig, 
                            in_file,
                            out_file,
                            sample_rate,
                            post_play_command=None,
                            temp_io_dir="/dev/shm",
                            output_device=None,
                            input_device=None):
    """
    simultaneously play an audio file while recording from the mics on a remote raspberry
    pi.

    This function will assert if overrun is detected in the recording

    Args:
        testrig: an instance of remote_pi_access
        in_file: str, file name with no dir. This file will be copied from the current working
                 directory to the pi for playing. It will be played to completion.
        outfile: str, Name of file that will be created from the recording, it must not have a directory
                 part
        sample_rate: int, rate to record at
        post_play_command: str, command line to run on this machine after play has started and before record
        temp_io_dir: directory on the pi that will be used to play from and record to. /dev/shm is the default
                     however this is a ram disk so the audio file is limited in size by available memory (max 1GB, 
                     ~43 minutes of stereo, 32 bit, 48kHz audio, on the raspberry pi I checked). Set
                     to whatever you like but there is a risk that slow disks will cause buffer overruns.
                     Recording is done with the mmap interface and some experimentation shows that this solves the
                     problem for writing to the SD card, but overruns are least likely in RAM disks.
        output_device: Specify specific audio device to play to if different from default (I2S)
        input_device: Specify specific audio device to record from if different from default (I2S)
    """
    assert testrig.ready_for_samplerate(sample_rate), "remote_pi_access instance has not been prepared for this sample rate"

    if input_device is None:
        input_device = I2S_AUDIO_DEVICE
    if output_device is None:
        output_device = I2S_AUDIO_DEVICE

    sox = shutil.which("sox")
    sox = sox + " --info" if sox else shutil.which("soxi")
    if not sox:
        raise FileNotFoundError("Executable sox or soxi not on path")
    in_length = float(subprocess.run(f"{sox} -D {in_file}".split(), capture_output=True).stdout)
    out_length = int(in_length)
    testrig.send_file(in_file)
    testrig.cmd(
        "killall -q -KILL aplay arecord"
    )  # stop existing aplay background tasks if running
    play_file = testrig.dest_working_dir + "/" + in_file
    new_play_file = Path(temp_io_dir) / in_file
    testrig.cmd(f"mv {play_file} {new_play_file}")

    testrig.cmd(
        f"nohup aplay -c 2 -f S32_LE -r {sample_rate} -D {output_device} {new_play_file} &> /dev/null &"
    )
    rec_file = Path(temp_io_dir) / out_file

    sleep(1)  # Wait a second for aplay to start

    if post_play_command is not None:
        subprocess.run(post_play_command.split())

    # run arecord, use mmap as it reduces likely hood of having buffer overruns, pipe
    # stderr to stdout to enable capturing overruns
    record_out = testrig.cmd(
        f"arecord --verbose --mmap -c 2 -d {out_length} -f S32_LE -r {sample_rate} -D {input_device} {rec_file} 2>&1"
    )
    testrig.cmd(
        "killall -q aplay"
    )  # stop existing aplay background task if still running
    testrig.cmd(
        f"mv {rec_file} {testrig.dest_working_dir}"
    )
    testrig.fetch_file(out_file)
    # Move file to original position so that it can be later removed
    testrig.cmd(f"mv {new_play_file} {play_file}")

    assert "overrun" not in record_out, f"rpi recording overrun writing to {rec_file}, test invalid"
    
