# Completed post-run UI review

Purpose: independently review the field-postrun-v2 installed v7 candidate, copied recording Save/Open, explicit simulated state views, actual envelope/closure and exact private backup. Inputs are the immutable admission/results, v5/source archive manifests and retained source audio hashes. Outputs are private REVIEW.json, BACKUP.json, target backup and a separately recorded visual review. It opens no models, audio devices or GUI.

The executed protocol is **field_postrun_protocol_v2.py**. The bound README_FIELD_POSTRUN_V2.md retained a V1 protocol filename in its descriptive paragraph; its dispatcher/reader commands already name V2 correctly. V1 protocol/reader and release v6 remain failed evidence. V2 uses the unchanged field_caption_state_v1.py and field_run_reporting_v1.py helpers. The latter handles optional counters and durable epoch reporting; it does not retroactively change or qualify the failed live harness.

PowerShell, from `G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928`:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_postrun_v2.py
```

CMD / Anaconda Prompt (existing environment, no installation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_postrun_v2.py
```

These commands document the already completed run. Do not rerun or overwrite its backup. A changed review or experiment requires a fresh derivative/destination. Full dispatcher inputs and resource limits are in README_FIELD_POSTRUN_V2.md. Both original failures and success evidence remain unchanged; this reader's pending-visual status is supplemented by FIELD_POSTRUN_VISUAL_REVIEW_V1.json and FIELD_POSTRUN_FINDINGS_V1.md. Five images were inspected for readable state text at480x800. No pixel-equality gate, physical touch, new recording/inference or acoustic accuracy was tested.
