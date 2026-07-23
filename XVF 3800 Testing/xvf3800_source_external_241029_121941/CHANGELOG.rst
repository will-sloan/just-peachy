sw_xvf3800 change log
=====================

3.2.1
-----

  * REMOVED: Reference in build system to spurious component

3.2.0
-----

  * CHANGED: fwk_xvf updated to v1.2.0.
  * CHANGED: Control interface requires WinUSB drivers instead of libusb-win32.
  * CHANGED: HID Report ID 1 (MISC_BUTTONS): top-level collection now has usage
    Phone from the Telephony page rather than usage Headset. In addition, bits 0
    to 3 of byte 1 (the Keypad index) now has an enclosing Usage Page of
    Telephony, rather than the Button Usage Page it previously held.
  * CHANGED: Memory reserved for user application code on tile[1] reduced from
    19 kB to 17 kB.
  * ADDED: Support for fixing focused beams in a certain direction.
  * ADDED: Support for separate YAML files with default values for each product
    specifier.
  * ADDED: Support for different PID values depending on interface sample rate.
  * ADDED: Support for Microsoft OS 2.0 Descriptors so the Control interface
    enumerates as a WinUSB interface on Windows.
  * ADDED: Support for REBOOT control command; issuing it reboots the device.
  * ADDED: Support for I2S_DAC_DSP_ENABLE control command. This command, in the
    UA build, instructs the device to source the far-end reference signal from
    I2S rather than over USB; this is useful where e.g. the DAC in use modifies
    the reference signal before sending to the amplifier for the loudspeakers,
    which would require this modified signal to then be sent back to the XVF3800
    to use as the input to the echo-cancellation algorithm. Further information
    on this feature has been added to the relevant sections of the
    documentation.
  * ADDED: Support for DFU over I2C by use of control commands. [This feature
    was added in v3.1.0]

3.1.0
-----

  * ADDED: "Spatial" output build configuration.
  * CHANGED: fwk_xvf updated to v1.1.0.
  * CHANGED: Enabled HID interface.
  * ADDED: Support for ASR output.
  * ADDED: Support for processing HID reports.
  * ADDED: Support for IO expander buttons and LEDs.
  * ADDED: Support for equalization filter.
  * ADDED: xvf_tools.py script to simplify the use of other XVF scripts.
  * CHANGED: Recommended Python version to 3.10 or higher.

3.0.0
-----

  * CHANGED: Datasheet updates; power consumption and latency values
  * ADDED: AEC_SPENERGY_VALUES command to read out the current speech energy
    levels for each of the 4 beams.
  * CHANGED: Post SHF DSP functions take additional spenergy parameter and the
    default implementation of post SHF DSP provides processed DOA value which is
    smoother and more likely to be pointing at a speaker. This processed DoA
    value is available using the AUDIO_MGR_SELECTED_AZIMUTHS command.
  * CHANGED: Updated xmos_cmake_toolchain to v1.0.0.
  * CHANGED: Updated host_xvf_control to v2.0.1.
  * CHANGED: fwk_xvf (located in the modules directory) is now shared with other
    projects and therefore will maintain it's own changelog and versions. This
    release will use v1.0.0 of fwk_xvf and all changes since v2.0.0 of
    sw_xvf3800 are described in modules/fwk_xvf/CHANGELOG.rst.
  * ADDED: agc_gain_plot.py and doa_plot.py to enable visualisation of these
    features.

2.0.0
-----

  * ADDED: Support for UA configuration based on TinyUSB implementation
  * ADDED: Support for DFU over USB
  * CHANGED: Directory restructure to enable future development
  * CHANGED: Increased pll lock range from +-250ppm to +-1000ppm
  * ADDED: Added idle time check commands for SHF
  * ADDED: Separate define for AEC_COEFF_CHUNK_SIZE
  * CHANGED: Switched to the VPU-optimised Sample Rate Converter
  * CHANGED: Recommended windows cmake generator from NMake to Ninja
  * CHANGED: Location of some tuning and test scripts
  * CHANGED: Updated lib_shf to version 1.9.0
  * CHANGED: Updated fwk_io to version 3.0.1
  * CHANGED: Updated fwk_rtos to version 3.0.4
  * CHANGED: Updated lib_sw_pll to version 1.1.0

1.0.1
-----

  * CHANGED: Fix cmake toolchain for Windows

1.0.0
-----

  * Re-organize framework components

0.4.0
-----

  * CHANGED: Update tools version to 15.2.1
  * ADDED: Check value ranges of the parameters in the host app
  * ADDED: Check for the shared device code compatibility between the device and
    the host app
  * ADDED: Script used for tuning the NL echo suppression model
  * CHANGED: Freeing logic for done packets in the servicer - resource packet
    queue
  * CHANGED: Handling of default parameters for main product build
  * CHANGED: Updated lib_sw_pll to version 0.2.0 improving I2S idle time
  * ADDED: YAML file for storing device enums
  * ADDED: Support to the device command map for printing enum string for read
    commands that return an enum value
  * CHANGED: Optimised data plane providing more cycles for user DSP
  * CHANGED: Fixed polarity of INT_N GPO pin

0.3.0
-----

  * CHANGED: SHF library version 1.7.0
  * CHANGED: Post processing api to allow external set/get of channels and
    reading of chosen channels azimuths.
  * ADDED: Commands AUDIO_MGR_SELECTED_AZIMUTHS and AUDIO_MGR_SELECTED_CHANNELS
  * CHANGED: xcore_sdk version which contains a fix in the SPI Slave driver to
    stop it from crashing if a control command is issued in the middle of driver
    start up.
  * ADDED: Support for boot over SPI Slave interface
  * ADDED: Support for setting the NL model in the device at boot time
  * ADDED: Error check for exceeding special command buffer size when writing to
    it
  * CHANGED: Mechanism for signalling between io config servicer and main tile1
    task
  * ADDED: Support for running without external MCLK on int-dev builds (default)
    using sw_pll and control command I2S_CLOCK_STATUS
  * ADDED: Far-end DSP example
  * CHANGED: Moved sysdelay out of SHF and into audio task to allow configurable
    memory usage.
  * ADDED: Packing/unpacking script.

0.2.0
-----

  * ADDED: Runtime configurable audio paths. This includes bypassing SHF
    BeClear, as well as commands to provide fine grain control over which
    internal audio sources should be output to I2S.
  * CHANGED: Update user dsp API to pass in AEC residuals and current Azimuths
    of the channels.
  * CHANGED: SHF library version 1.4.1
  * CHANGED: Set default mic gain to 80 (~38 dB)
  * ADDED: Support for I2C or SPI based control of DSP and application
    parameters. All control features supported by the example host app.
  * ADDED: Configurable general purpose output pin control using I2C/SPI with
    PWM support.
  * ADDED: Configurable general purpose input pin control using I2C/SPI.
  * ADDED: Support XVF3800 OTP keys.
  * CHANGED: AGC Fast default 0.6 -> 0.1 and DT Sensitive default 0 -> 12
  * ADDED: Dynamically controlled burn to allow testing of worst case timing

0.1.0
-----

  * ADDED: Initial app_xvf3800 app: I2S Slave at 16 or 48kHz, no control or DFU
    functionality
  * ADDED: SHF library version 1.1.0

