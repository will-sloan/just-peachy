# USB RIGHT continuity stimulus and the AEC reference

For the official XVF3800 3.2.1 firmware data path reviewed here, normal unpacked stereo USB input contributes only its LEFT channel to the AEC. The RIGHT continuity stimulus remains available for native-reference readback without entering that AEC reference. This conclusion requires `I2S_DAC_DSP_ENABLE=0`, normal unpacked host-to-device input, and the reviewed firmware rather than an altered custom build. It is a source-supported routing conclusion; it does not claim that a different firmware, input-packing mode or external DAC loopback is equivalent.

The source chain is explicit:

1. `src/data_plane/shf_wrapper.h:30` fixes `BECLEAR_NUMBER_OF_FAR` at 1. The SHF input buffer therefore holds one reference channel.
2. `src/data_plane/i2s_task.c:417–442` (`i2s_receive_ua_3to1`) keeps USB channel 0 and channel 1 separate. When DAC DSP loopback is disabled, each `far_end_samples_to_audio` entry receives the corresponding USB channel. The uncompressed collection assembly at lines 354–356 preserves those channel indices.
3. `src/data_plane/audio_task.c:250–280` downsamples each collection independently using its collection index. There is no stereo sum. `MUX_FAR_END` retains both channels, while `MUX_FAR_END_SYSDELAY` and `MUX_FAR_END_W_GAIN` have only one element (lines 754–757).
4. The positive-delay path uses a delay state initialized with one channel (line 794); the zero/negative-delay path copies exactly one element (line 925). `sample_delay.h` processes only its configured `n_channels`. Both paths select channel 0; neither reaches channel 1.
5. Conversion, reference gain and `push_samps_to_shf` operate on that one-element buffer (`audio_task.c:929–946`, `184–193`). Thus USB RIGHT does not become a second AEC reference.

The standard app's `src/user_dsp/far_end_dsp.c` defaults `USE_FAR_END_DSP` to 0 and implements a no-op in that branch. Its optional example EQ loops over the single FAR channel and contains no cross-channel mixing. The DSP callback acts on the DAC sample array; the normal USB reference path is separately assigned. The standard board DAC initialization (`modules/bsp/dac/dac3101/dac3101.c:205–207`) writes `DAC_DAT_PATH=0xD8` and explicitly configures the right output to contain LEFT data. That DAC setting is independent of retaining USB RIGHT as a digital readback signal.

Evidence was read from the user's official `XVF3800-Software_v3_2_1.zip`, containing `xvf3800_source_external_241029_121941.tar`. Data-plane sources are extracted under `tmp/hardware_research/sources/modules/fwk_xvf/modules/xvf/`; the app DSP and DAC sources were freshly extracted with paths preserved under `tmp/right_reference_review/verified/sources/`. The take `TAKE_20260905T224047_423999Z_f5997b/before_params.txt` records `AUDIO_MGR_FAR_END_DSP_ENABLE 0`, `I2S_DAC_DSP_ENABLE 0`, and `AUDIO_MGR_SYS_DELAY -32`.

For ordinary phone-speech recordings in this configuration, the app sends silent USB LEFT and the continuity sequence on USB RIGHT, while holding the unused analog DAC in reset. The single AEC reference is consequently silent. Same-clock LINE OUT measurements deliberately place the acoustic excitation on LEFT; that excitation then is the AEC reference. Raw microphone recording remains available separately from processed output.

Preflight should preserve and verify the reference-source and unpacked-input invariants for every acquisition path. The continuous readback sequence is a transport test, and an exact match does not prove the separate Realtek acoustic output had no gaps.
