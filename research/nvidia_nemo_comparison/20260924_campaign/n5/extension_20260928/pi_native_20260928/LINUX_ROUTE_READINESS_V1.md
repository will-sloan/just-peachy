# Linux XVF route: read-only readiness audit

September29,2026. No device stream, microphone capture, playback, control-tool command or DSP setting change was initiated.

The connected Pi exposes XMOSDevice through ALSA I2S: card2, capture pcm1, hardware endpoint hw:2,1. Its procfs capture status is closed. USB sysfs currently lists only host controllers; no USB audio/XMOS peripheral is enumerated. USB is not required by this configured route.

The original app data/live_config.json explicitly selects `XMOSDevice: 1f000a0000.i2s-dir-hifi dir-hifi-1 (hw:2,1)`, ALSA, control_protocol=i2c,48kHz, O0 and expected linear array type1. The matching configured xvf_host executable exists and its hash is retained privately. I2C device nodes exist. Neither presence nor configuration proves firmware, permissions, active sample format or route correctness.

Source inspection confirms the fresh application supports explicitly named ALSA hardware endpoints with I2C control, serialized bounded host-tool commands and the shared hardware lease. Start opens an input-only48kHz/two-channel stream, discards pre-route priming, applies/verifies/restores owned routing, then admits audio. Some control readbacks require an active audio loop; this audit did not call them. It also did not enumerate/open PortAudio or use check_input_settings.

The qualified saved-input FIR diagnostic covers conversion/counts and downstream B01 memory/lifecycle/parity. It does not cover the live ring, stereo channel selection, O0 host+3dB gain, actual device callback/ADC clock, route/control readback, startup settling, restoration, overflow/discontinuity or capture resource fit. Do not infer those from saved-file parity. Current user previews remain capture-off.

## Next user-ready session

Prepare a fresh bounded live diagnostic using the configured I2S/I2C route and original shared hardware lease, preserving the installed app/data. Recheck boot, exact app/research identities, endpoint, configuration/tool hashes, RAM/disk and time/output admission. Start only when the user is physically ready; a scheduled wakeup must not start capture.

First verify quiet-route startup/readback, actual rate/channels, stable callbacks/counts/source-clock bounds and clean Stop/restoration. Then a short consented spoken passage can establish actual transcription/label delivery and observed latency/resource behavior. No naming/enrollment is implied. User-selected restaurant babble, steady noise and impact comparisons come after the actual reference/processed tap support is established. Use matched chronology/settings/listening gain; do not call constructed clips real conversations.

Private ROUTE_PREFLIGHT_V1.json and ROUTE_CONFIG_AUDIT_V1.json bind this audit. Original rc5 app/install/autostart/config and microphone state stayed unchanged. This is configuration/source inspection, not live qualification or a runnable capture launcher.
