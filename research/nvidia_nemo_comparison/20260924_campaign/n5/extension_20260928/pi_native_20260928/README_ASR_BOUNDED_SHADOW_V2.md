# Bounded ASR shadow metadata v2 — unintegrated

Purpose: address v1's indefinitely growing diagnostic lists before longer ASR-guided diarizer research. Existing B01 models, previews, admissions and v1 evidence are unchanged. This standalone derivative is not wired into any model and never skips audio. The user deferred microphone testing; all work here is model-free and capture/playback-free.

Inputs are float32 blocks of1–320samples at16kHz with contiguous sample indices, positive ASR source intervals and actual cue availability through a supplied clock, and successful ASR completion/failure/finish events. Positive ASR support remains±1s; positive energy remains-55dBFS with0.2s pre/0.4s post support. Expiry stays3s and quiet proposals need ASR completion through an additional1s. Completion/no words is not speech truth. Every action remains KEEP_ALL_SHADOW, including pressure and EOF.

Bounds:48000audio samples/192000payload bytes **and**256pending entries;128merged ASR support intervals,128energy intervals,512recent decisions,32progress entries. Obsolete support is pruned after no pending audio can need it. Scalars, hashes and fixed reason counters preserve aggregate coverage. These are collection/payload bounds, not an exact total Python/RSS byte guarantee. Reports intentionally expose history retirement. Overflow makes metadata uncertainty sticky and retains audio. A late cue that could intersect retired quiet proposals marks audit incomplete and keeps future audio; its exact historical overlap is no longer reconstructible. It never rewrites or claims exhaustive old per-frame audit. Closed sessions reject more input and require a new instance.

`check_asr_bounded_shadow_v2.py` runs12 native constructed cases: seven exact old/new short-decision comparisons (quiet, missing/failed health, padding, energy, bursts, late cues), tiny-block metadata pressure, disjoint future-cue overflow, late support after history retirement, a60-minute **logical-time** trace executed as fast as possible, and invalid/closed/fresh-session checks. The future-cue flood is an adversarial metadata stress, not actual ASR output. The long trace contains generated constants, not speech, and does not run models or wait60minutes. It cannot qualify real-time behavior,30/60minute native endurance, accuracy or speedup. Its hash/coverage, bounded collections and process RSS are the narrow evidence.

Outputs: private `asr-bounded-shadow-v2[-evidence]` admission, exact owners, logs, RESULT and independent REVIEW, with aggregate counts and bounded recent metadata only. No new audio file, vectors, model weights, capture, playback, training, downloads, GUI or personal data. Scope is model-free state handling; whole D1 chunk/cache/FIFO/source-clock/discontinuity/flush preservation and real quiet/overlap/returning-speaker recognition remain open. No application integration should be inferred.

Dispatch reuses the existing strict SSH, source checks and research lease. CPUs2/3,total200%,one native numerical thread,Tasks64,hard768MiB virtual,1MiB stacks,180s service;>=850MiB RAM/5GiBdisk. Host coordinatorCPU14,C>=50GiB/G>=75GiB. Only8MiB output is reserved within the existing1GiB combined allowance, preserving room for the later real B01 trial. The full snapshot must be younger than15minutes. Never overwrite a failed/completed fixed run.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_asr_bounded_shadow_v2.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V31.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_asr_bounded_shadow_v2.py
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`, then the same interpreter/script arguments without `&`, using double quotes around the interpreter path. Existing Python/NumPy are reused; no activation/install. Reader checks bound sources, exact owners, normal unit exit, all12case receipts, independently reconstructed long-input hash, coverage and declared collection bounds. Private receipts are exclusive-write; preserve failures and use a fresh version for corrections.
