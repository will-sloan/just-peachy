# Native B01 ASR/energy shadow V1

Purpose: observe actual fast-ASR positive cue intervals and their arrival times on the Pi, alongside converted-source20ms energy, while the unchanged B01 diarizer receives every sample. The native harness observes cues online; causal decision evaluation occurs after each session using only cues available by each declared deadline. This is online cue collection plus post-session shadow-policy replay, not implemented online skipping, a buffering controller or measured speedup.

Candidate: ASR support±1second, merged by interval union; conservative energy support -55dBFS with0.2s pre/0.4s post. A two-second decision delay reserves the proposed1second pre-roll plus1second cue wait. The128000byte float32 audio buffer is a theoretical lower bound only and is not allocated/qualified here. Actual ASR health/watermark is absent; missing/uncertain health would retain audio. ASR-only absence is a negative control. Energy low+no known positive ASR produces a diagnostic proposal only, not proof of silence. All decisions record KEEP_ALL_SHADOW.

Report fine20ms proposals and supported current delayed21.12s whole-chunk proposals separately. Late positive cues, actual cue arrival/end lag, observer cost, post-session policy cost and allaudio parity are logged. No model savings, speech-loss rates or accuracy scores follow. Different geometry, applied gaps, cache/returning-speaker/context, source clocks, EOF, overload and real-world quality need further gates.

Files: asr_shadow_v1.py holds the bounded observer/policy; b01_asr_shadow_v1.py attaches it after the actual N2 text publication and to the saved producer, keeping original models/controller/qualified FIR source; dispatch_asr_shadow_v1.py binds fresh admission; b01_asr_shadow_gate_v1.py shares preview lease. review_asr_shadow_v1.py reconstructs energy/support/causality/counts from independent saved-array and native event evidence, checks full D1/E0 against qualified filtered references, and verifies closure. No capture/playback/enrollment and no visible Tk. Original app and existing previews unchanged.

Input: previous original44.695s16k saved PCM expanded by repetition to constructed48k, actual converter, B01 and retained E0; earlyStop/fullrestart. Output is private SHADOW_EARLY/FULL.json, session evidence, admissions, exact owners and independent review. Raw audio/captions/arrays stay out ofGit. The synthetic source is not independent real-world material.

Limits: CPUs2/3,total200%,one native thread/model,768MiB address cap,1MiBstacks,Tasks64,180sservice/140sharness,40MiB reserved newoutput. Fresh census<15minutes,>=850MiBavailableRAM,5GiBdisk; existing1GiBcombined allowance and checkpoint retained.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
$c='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V25.json'
& $py -B "$p/dispatch_asr_shadow_v1.py" --run-id b01-asr-shadow-v1 --census $c
& $py -B "$p/review_asr_shadow_v1.py"
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928"
set "C=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V25.json"
"%PY%" -B "%P%/dispatch_asr_shadow_v1.py" --run-id b01-asr-shadow-v1 --census "%C%"
"%PY%" -B "%P%/review_asr_shadow_v1.py"
```
Single-use runID; preserve failures. No user-visible launch or appliedgate is enabled by this diagnostic.
