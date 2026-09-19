# Diagnostic-only paired journal closure

`s6d_beam_native_run_diagnostic_v2.py` is an additive diagnostic-only copy of the accepted frozen beam execution runner6f716290. The underlying fixed app, model profile, gallery, native execution loop, source pacing and clocks are unchanged. Original C12/core runners and pins remain unchanged. The new wrapper accepts only `stream_diagnostics` / `stream_diagnostic`; it changes input/evidence validation and completion metadata.

The actual mono diagnostic path calls the frozen `PipelineEngine.start_file` then `start_paired_files(path,path)`, which writes separate `audio_spool.pcm16` and `identity_audio_spool.pcm16`. The earlier wrapper verified only the ASR spool. The new wrapper first joins job audio, PCM hash, both frame declarations and one raw-stream proof to the exact already-qualified physical stream. After native completion it hashes both closed spools, requires their exact session paths, bytes/full frames and identical admitted PCM hash, and retains all existing actual finalization, dispatch, drain, observer and STOP gates.

Inputs remain an exact reviewed `s6d-beam-execution.v1` manifest, actual per-case qualified MAIN/SCAN capture admission, fixed model/profile/gallery/source bindings, and the root supervisor environment. `runner_helper` must bind this exact new wrapper. `FULL_MULTISTREAM_AUDIT.json` gains `diagnostic_pair`, with stream/source identity, full frame count, source PCM hash and both actual spool bindings. COMPLETION gains `diagnostic_dual_journal_evidence_validated=true` only after every gate succeeds. Missing, truncated, changed or foreign-session identity spools reject. The inner RESULT remains separate and insufficient.

`s6d_beam_queue_prepare_diagnostic_v2.py` makes a held proposal only after exact diagnostic input binding and source review. It requires this new wrapper and adds literal expected artifact predicates for both journal hashes/lengths, stream, source and full frames. It creates no approved hashes or execution. The existing parallel partition helper can later split that held queue in original index modulo4 order, preserving the fixed528 membership and global four-worker limit. Do not run the old C parallel queues.

This closure repair retains protocol874d and runnerV4/40GiB. The separately accepted future80GiB authority is not automatic: a new reviewed source/metadata epoch must migrate protocol pin, queue builder/runner binding and exact exception/contract/forecast/prior-runner guards. It must not alter active physical40GiB or existing C/core sources. Actual first48 MAIN/SCAN catalog, successful48 matching auto controls, root worker allocation and final literal approval remain absent prerequisites, not assumed results.

Purpose of `s6d_beam_diagnostic_checks_v2.py`: reproduce the old diagnostic-specific omission and verify only affected source, paired-spool and completion gates. It uses deterministic32kB PCM byte fixtures, no model/audio session or production waveform reads. It extracts only the existing pure completion dictionary constructor and does not repeat the original three-focus tests. Outputs are fresh G fixture files, old adverse observation and a receipt.

PowerShell fixtures:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_beam_diagnostic_checks_v2.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_v2\checks_v1'
```

Anaconda Prompt / CMD fixtures:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_beam_diagnostic_checks_v2.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_v2\checks_v1"
```

Choose a fresh output suffix. After actual input/source review, held metadata command: `python -B s6d_beam_queue_prepare_diagnostic_v2.py --manifest EXACT_MANIFEST.json --manifest-sha256 SHA256 --output FRESH_R_RUNNER_DIRECTORY`. The future supervisor-only native argv is `python s6d_beam_native_run_diagnostic_v2.py --manifest EXACT_MANIFEST.json --manifest-sha256 SHA256 --job-id EXACT_DECLARED_ID`; it requires actual root queue admission and `S6D_*` ownership/STOP/heartbeat environment. Do not invoke as an unsupervised launch.

The diagnostic results describe fixed-stream text/voice performance under their recorded allocation. Four concurrent workers share CPU affinity12–15 with one thread per backend; they do not certify serial latency, causal availability, GUI render or physical scanout. C calibration and core selected association remain serial and separately admitted. No normalization, per-beam alignment, new weights, truth-triggered work or Q threshold fitting is introduced.
