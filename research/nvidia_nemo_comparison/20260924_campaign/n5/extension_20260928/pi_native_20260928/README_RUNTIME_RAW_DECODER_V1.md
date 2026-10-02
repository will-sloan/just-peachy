# Strict physical microphone packing decoder
Purpose: decode actual XVF3800 I2S48kHz stereo S32LE into six synchronous16kHz channels. Uses the existing vendor packing layout; rejects every left/right marker mismatch or wrong0,1,1 sequence. It never tolerates a dropped/corrupted frame or invents raw audio from processed WAV.
Inputs: bytes from a verified packed-route capture,24bytes..32MiB, whole8byte stereo frames. Caller must bind actual mux route and capture clocks.
Outputs: dictionary with exact PCM32 samples (packing marker LSB cleared),16000Hz,frame count,channel names,prefix/suffix trimming<3transportframes and error count0. channel_bytes(result,(2,3,4,5)) extracts four pre-gain raw microphones; channel0 is auto-ASR,1 processedauto-select.
The firmware raw tap is16kHz. This is not48kHz ADC data, original ADC bit-perfectness, equal acoustic/DSP delay, quality or inference accuracy. Decode opens no files/devices and does not capture or change routes.
PowerShell example from this source directory, using a PRIVATE recorded file:
    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "from pathlib import Path; from field_runtime_raw_decoder_v1 import decode; d=decode(Path(r'<private-packed-file>').read_bytes()); print(d['frames'], d['channels'])"
CMD / Anaconda Prompt:
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "from pathlib import Path; from field_runtime_raw_decoder_v1 import decode; d=decode(Path(r'<private-packed-file>').read_bytes()); print(d['frames'], d['channels'])"
API: decode(raw_bytes); channel_bytes(decoded,tuple_of_channel_indices). No dependency install required. Native producer integration and exact PC readback must independently pass before enabling a recording mode.
Reference: https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/programming_guide/04_testing_the_software.html
