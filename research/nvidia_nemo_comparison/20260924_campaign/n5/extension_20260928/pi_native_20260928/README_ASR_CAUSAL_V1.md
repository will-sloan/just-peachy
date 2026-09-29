# Native causal ASR shadow buffer v1

Purpose: implement and test an actual bounded audio shadow queue and successful-ASR-completion progress on the CM5. It observes unchanged B01 models and captions; it never gates the diarizer or discards source audio. Existing application/previews and their hashes remain unchanged. This is a fresh diagnostic, not a delivered optimized mode.

## Inputs, outputs and policy

Input is the admitted original44.6954375-second saved16k source, constructed to48k by repeating samples and converted by the qualified97-tap FIR. This is a constructed diagnostic, not a real recording or accuracy evaluation. The harness runs seven model-free scheduling cases, then early Stop/full restart with the existing B01 models and withdrawn Tk. New observation hooks record contiguous successful ASR accepted samples (including tail), finish/failure, ASR-positive publication availability and conservative energy support. Model calls, source pacing, D1 stream and E0 windows are unchanged.

`asr_causal_buffer_v1.py` holds at most48,000float32 samples (192,000bytes,3seconds). It copies20ms blocks, verifies source continuity, and releases copies in original order. The3s horizon is the declared2s cue wait plus1s pre-roll; this changes only shadow decisions, not current D1/caption latency. ASR cues protect±1s; positive energy uses-55dBFS with0.2s pre/0.4s post support. Quiet proposals require healthy ASR completed through an additional1s of source. Completion means processed, not proof of silence or settled future hypotheses. Missing/failed progress, queue pressure and EOF retain audio. Late positives remain visible and never rewrite old decisions. Every decision is KEEP_ALL_SHADOW. Input/output hashes prove that the shadow queue itself also preserves every sample.

The audio queue is bounded; per-event diagnostic metadata is retained only within this short admitted job. No30/60minute/endurance memory claim. Sparse-scene proposals are not real-world savings, and whole native chunk/cache/FIFO/EOF skip semantics remain unqualified. Prior post-session shadow proposal output is retained separately for comparison; it must not be confused with the new online queue.

Private outputs: target and local `b01-asr-causal-v1[-evidence]` admission, owner identities, logs, model/lifecycle results, SHADOW_EARLY/FULL.json with decisions/progress, source-probability reference checks and REVIEW.json. No microphone, playback, enrollment, personal names, downloads, new accuracy scores or visible UI.

## Commands

PowerShell, from the campaign worktree, with a fresh comprehensive census (<15minutes):

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/dispatch_asr_causal_v1.py" --run-id b01-asr-causal-v1 --census <fresh-census.json>
& $py -B "$p/review_asr_causal_v1.py"
```

CMD or Anaconda Prompt uses the same existing interpreter, without activation/installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928"
"%PY%" -B "%P%/dispatch_asr_causal_v1.py" --run-id b01-asr-causal-v1 --census <fresh-census.json>
"%PY%" -B "%P%/review_asr_causal_v1.py"
```

Run/review once; failures and completed runs are immutable. Corrections require fresh versions and admissions. The dispatcher stages only small diagnostic files and reuses the qualified app/models. It rechecks all exact recorded owners and units, shared research lease, original app/install, source hashes, host/target storage and RAM. CPU2/3,total200%,one native thread,hard768MiB address space,1MiB stacks,Tasks64,180sservice,40MiB new-output reservation,existing checkpoint and1GiB combined allowance remain. No new dependency is needed.

## Independent review

`review_asr_causal_v1.py` preserves previous exact filtered D1/E0 reference, source coverage, Stop/restart, actual withdrawn widgets and clean shutdown gates at unchanged1e-5. Additionally it reconstructs each decision using only cues/energy/progress available at the decision time, checks progress never outruns source,3s expiry,±1s padding, late positive flags, EOF retention, queue count/hash closure and192k audio cap. Seven native constructed cases cover missing health, failed health, late cues, lenient padding, dense energy, burst overflow/EOF and discontinuity/fresh-session reset. They are not tests of quiet/overlap/returning-speaker recognition quality. Frozen consented real-world tests are still needed; no skipped inference or speedup is established by this diagnostic.
