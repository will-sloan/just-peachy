# A2 A76 full-source comparison V1

Purpose: test the already-built lane-preserving A76 CPU kernels with Nemotron ASR A2, without borrowing D1 scheduler/metadata/cache limits. This is a fresh numerical runtime candidate, not a silent replacement or new model download. Retain existing A2 Q8 weights,16MiB metadata,8192scheduler/95%guard,original executable cache,ASR library and adapter. Only the three libggml-cpu.so aliases change to the previously built A76 hash f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557. Shared ggml-base/ggml library hashes match exactly; ABI equality alone is not numerical acceptance. Verify actual loaded CPU mapping.

Inputs: fresh V5 host census, exact current Pi owners/boot/units/RAM/disk; original a2-native-full-v1 binding/RESULT/87canonical events; existing699872960-byte A2 Q8 asset, original715127sample16k saved file. No copy of weights or full checkpoint. Saved material is functional/timing evidence only.

Protocol: original full file, resident reset/repeat, exact canonical event equality to retained generic output and between repeats, EOF idempotence/postfinish rejection, explicit destruction/natural closure. All available_at_monotonic fields are excluded exactly as in the original comparison. Mismatch fails without new WER/accuracy scoring or tolerance relaxation. This does not establish independent logits parity, forced-endpoint or malformed-reader equivalence, B02 fit, GUI, live speech or endurance. Timings are conditional with rc5 still active and compare prior sequential observations under the same CPU/thread/RAM envelope, not simultaneous uncontended benchmarking.

Limits: isolated1536MiB hard virtual,initial1408MiB available;sampled stop below192MiB available or above1152MiB RSS (not hardRSS enforcement). CPU2/3,total200%,one native model thread,GPUoff,Tasks64,1MiB stacks,600second service/590alarm/10second stop,5GiB free disk.64MiB combined output admission32target+32host; all earlier usage/reservations retained. No baseline/OS/swap changes. Exact live systemd properties before transient collection; research lock held through closure.

Outputs: fresh a2-a76-full-v1 libs/source manifest/CPU_DERIVATIVE/BINDING/admission/owners/envelope, private canonical events and run metrics, failures retained. Independently compare loaded mapping, all input/library hashes, full/reference/repeat/closure and actual resource bounds before performance claims.

The gate samples aggregate target output every0.25s and stops before the32MiB ceiling minus2MiB final-receipt reserve; this is sampled enforcement, not an atomic filesystem quota. Individual files are limited to4MiB and JSON writes to2MiB. Final independent review checks actual aggregate bytes, including staged libraries and receipts.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/a2_a76_full_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V72.json
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\a2_a76_full_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V72.json
```
Use a fresh unused census if older than15minutes; dispatcher recomputes target-inclusive64MiB budget from current usage. Run ID cannot be reused. Worker/gate modes are internal; no automatic failed-variant retry.
