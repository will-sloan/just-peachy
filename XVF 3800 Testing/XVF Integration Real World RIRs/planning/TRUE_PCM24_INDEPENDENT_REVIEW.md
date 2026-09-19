# Independent review of PCM24 raw/amplified domain capture

2026-09-05. Offline review only. No hardware commands were issued.

**PASS for the tested 24-bit packed capture and Category 1/3 relationship on MIC0, MIC1 and MIC2.** I independently read the native three-byte PCM WAV with Python's `wave`, reconstructed signed counts from bytes, found the common marker phase, removed the LSB markers, and compared the result to the saved decoded WAV. I did not call the application decoder or fit routine.

| Check | Independent result |
|---|---|
| Transport | 576,000 stereo PCM24 frames at 48 kHz; 12 seconds received |
| First complete packed collection | Native frame 4,011, after 83.5625 ms startup exclusion |
| Valid decoded recording | 190,663 six-channel frames at 16 kHz, 11.9164375 seconds |
| Marker errors in retained region | 0; one common 0,1,1 phase on both channels |
| Decoder agreement | Independently decoded arrays exactly equal the saved `decoded.wav` |
| USB readback in receipt | 24-bit IN and OUT |
| Low audio byte | Nonzero in 99.20-99.25% of samples, excluding marker bit; not merely 16-bit samples padded with zeroes |
| Clipping | Zero rails across all six slots |
| Callback bookkeeping | Empty flag/error lists; callback frame total equals 576,000 |

All three simultaneous microphone pairs have **Category 3 delayed by 32 samples (2 ms)** and **gain 10 (+20 dB)** within the expected output quantization. Independent affine fits were 10.000028, 9.999996 and 9.999983. At exactly gain 10, `amplified[n+32] - 10*raw[n]` lay between **0 and 18 PCM24 counts**, as expected when each branch is separately truncated to an even integer by the 1-bit packing marker rule. The approximately 9-count mean residual is quantization bias, not evidence of a microphone gain fault. Pair correlations exceeded 0.9999975.

This validates the source-described fixed gain/delay contract for these three microphones and provides strong evidence that the capture path is carrying real low-order information at the configured USB24 precision. Payload width is 23 bits because packing consumes one transported bit; this is not a claim of 23-bit acoustic effective resolution. This pair test did not include MIC3, a known digital continuity sentinel, sweep-level headroom/linearity or speaker calibration. Clean markers and callback bookkeeping alone do not prove that no entire six-channel collection was repeated or omitted. The previous PCM16 sentinel qualification remains a separate result; any PCM24 continuity proof needs its own known signal.

The initial request for an int24 host container while the device still reported USB16 is not a failed board and is not evidence of true PCM24 recording. Preserving it as a format-mismatch take is correct. Likewise, the earlier JSON serialization exception after a PCM16 acquisition is a software evidence-writing issue; it must not be merged into the successful PCM24 result.

Evidence: [native capture](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/XVF_MEASUREMENT_WORK/experiments/CAPABILITIES_20260905T221801_419147Z/TRUE_PCM24_DOMAIN_PAIRS/native.wav>), [independent numerical receipt and hashes](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/TRUE_PCM24_INDEPENDENT_REVIEW.json>), [independent review script](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/review_true_pcm24_independent.py>).
