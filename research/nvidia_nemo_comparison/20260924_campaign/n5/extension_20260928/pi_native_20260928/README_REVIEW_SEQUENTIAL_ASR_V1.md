# Independent sequential ASR review

Purpose: standard-library review of the closed native sequential-asr-v1 candidate, without rerunning any model. Inputs are exact admissions, source and installed asset hashes, retained generic A2/Sherpa canonical references, both child event/result files, coordinator events/state artifacts, actual unit properties, process identities and sampled resources. Private transcripts are never printed or committed.

Require715127source samples for each phase and canonical events exactly equal to retained references (only availability clocks excluded); separate immutable primary/refinement artifacts; publication order and actual coordinator delivery; primary process reaped before A2 launch; natural exits/closed exact owners; four explicit successful states and retained five negative state checks. Verify1536MiB main/A2 and768MiB Sherpa virtual caps,1MiB stacks,CPU2/3/200%,Tasks64,300s/10s unit, sampled1152MiB aggregate RSS guard,16MiB target output and baseline/config/install/capture/leases unchanged. The five negative checks are implementation tests, not independent evidence of GUI behavior. No waveforms, model outputs or source are modified.

Outputs: new private host and target REVIEW.json with scoped PASS_NATIVE_SEQUENTIAL_SHERPA_A2_SAVED_SOURCE_ONLY or an exception preserving failed evidence. A collected result or exit0 alone is not acceptance. No GUI/D1/B02/live/endurance/accuracy qualification and no faster-real-time claim. Source/reader versions refuse receipt overwrite.

PowerShell from the campaign worktree:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_sequential_asr_v1.py
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_sequential_asr_v1.py
```
Wait for the exact run to close before reviewing. The host coordinator pinsCPU14; the read-only target reader pinsCPU3 with128MiB virtual/60s alarm. Back up all private evidence with verified hashes afterwards.
