fwk_xvf change log
==================

1.2.0
-----

  * CHANGED: lib_xshf updated from v2.2.0 to v2.4.0.
  * CHANGED: lib_sw_pll updated from v1.1.0 to v2.1.0.
  * CHANGED: fwk_io updated from v3.5.0 to v3.5.1.
  * CHANGED: fwk_rtos updated from v3.1.0 to v3.2.0.
  * CHANGED: Control interface requires WinUSB drivers instead of libusb-win32.
  * CHANGED: HID Report ID 1 (MISC_BUTTONS): top-level collection now has usage
             Phone from the Telephony page rather than usage Headset. In
             addition, bits 0 to 3 of byte 1 (the Keypad index) now has an
             enclosing Usage Page of Telephony, rather than the Button Usage
             Page it previously held.
  * ADDED: Support for Microsoft OS 2.0 Descriptors so the Control interface
           enumerates as a WinUSB interface on Windows.
  * ADDED: PID constants for all current XVF38xx products and sample rates.
  * ADDED: Support for fixing beams in a certain direction.
  * ADDED: Support for REBOOT control command; issuing it reboots the device.
  * ADDED: Support for I2S_DAC_DSP_ENABLE control command. This command, in the
           UA build, instructs the device to source the far-end reference signal
           from I2S rather than over USB; this is useful where e.g. the DAC in
           use modifies the reference signal before sending to the amplifier for
           the loudspeakers, which would require this modified signal to
           then be sent back to the XVF3800 to use as the input to the 
           echo-cancellation algorithm. Further information on this feature
           has been added to the relevant sections of the documentation.
  * ADDED: Support for DFU over I2C by use of control commands. [This feature 
           was added in v1.1.0]
  * FIXED: Removed redundant argument in DFU functions.

1.1.0
-----

  * ADDED: pan_pot module for panning mono audio channels to stereo.
  * FIXED: Removed linker warnings for unused tinyUSB functions.
  * FIXED: Replace xcore_math functions with correct ones from API.
  * ADDED: packed_recorder script for packed output/input playback and recording.
  * CHANGED: Enabled HID interface.
  * FIXED: Fixed bug preventing DFU downloads from being reattempted without
    rebooting the device.
  * ADDED: Teams specific HID reports.
  * ADDED: Support for processing HID reports.
  * ADDED: Support for equalization filter.
  * CHANGED: fwk_core updated from v1.0.1 to v1.0.2.
  * CHANGED: fwk_io updated from v3.2.0 to v3.4.0.
  * CHANGED: fwk_rtos updated from v3.0.4 to v3.1.0.
  * CHANGED: lib_xshf updated from v2.0.0 to v2.2.0.
  * ADDED: Extended HID support to IO Expander buttons and LEDs.
  * CHANGED: Adjust AEC_FAR_EXTGAIN to match the USB output volume settings.
  * ADDED: Support for Microsoft OS 2.0 Descriptors so the DFU interface
           enumerates as a WinUSB interface on Windows.
  * ADDED: Several tuning scripts that were originally located in the sw_xvf3800 repo

1.0.0
-----

  * ADDED: fwk_xvf created as a fork of sw_xvf3800 after v2.0.0.
  * ADDED: 16 and 24 bit packing support for USB on linux, just 24 bit on other
    platforms.
  * ADDED: Application, platform and test changes to support sw_xvf3820.
  * RESOLVED: Assorted documentation enhancements to improve readability.
  * ADDED: Windows testing of sw_xvf3800 application.
  * CHANGED: NL Model tuning scripts refactored into python package to enable
    multiple projects to use it. This change requires adding the directory
    modules/nlmodel_tuning to each project's python requirements.
  * CHANGED: Python scripts used to generate sources and documentation from YAML
    refactored into a python package. This involved moving and slightly changing
    the YAML config files. Any changes to the supplied YAML files will need to
    be updated to match the new format. Projects using this feature will need to
    add the yaml_autogen package to their python requirements.
  * CHANGED: Function prototype for post SHF DSP function updated so that
    smoother DOA and speech energy values can be passed in.
  * ADDED: Smoother DoA calculated and passed into post SHF DSP function.
  * CHANGED: fwk_core updated from v1.0.0 to v1.0.1
  * CHANGED: fwk_io updated from v3.0.1 to v3.2.0
  * CHANGED: Sample rate conversion extracted to lib_src which is now a
    submodule pinned to v2.3.0
  * CHANGED: qspi_fast_read updated from untagged commit 494e2c7 to v1.0.0
  * CHANGED: lib_xshf updated from v1.9.0 to v2.0.0
  * CHANGED: xmos_cmake_toolchain updated from untagged commit e577fbc to v1.0.0
  * CHANGED: reduce SHF reference level by 6dB before downsampling
  * CHANGED: DAC configuration updated to drop the right channel and play the left channel on both
    outputs.
  * CHANGED: Update paths of generated host command maps to match the ones used
    by host_xvf_control v2.0.1
