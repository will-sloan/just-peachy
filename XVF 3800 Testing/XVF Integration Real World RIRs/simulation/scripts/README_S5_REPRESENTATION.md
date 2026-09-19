# S5 oracle-window representation diagnostic

`s5_representation.py` prepares and runs the optional, bounded S5 representation diagnostic. It compares the unchanged ReDimNet2 representation on reference-selected development O0/O1 windows. It does not run ASR, segmentation, tracking, enrollment, live audio or hardware. It does not modify H2, canonical recordings, source/scene manifests, gains or thresholds. Results describe oracle-window cosine distributions, not online identity accuracy or speaker naming.

Inputs: frozen S5 `SCORING_PROTOCOL.json`, `execution_contract.json` and `JOB_MANIFEST.json`; the SHA-bound S4.5 v2 scene and source/legacy manifests; development accepted capture results and saved audio timing; and, only during `--run`, exact bound PCM24 O0/O1 files and the existing ReDimNet2 asset. All paths resolve from these records, not WAV globs. Development permission is checked before timing, waveform or model access. Parsing source/scene reserve metadata does not authorize reserve task access. Existing Common Voice/source rights and identity caveats continue to apply.

Outputs are under `simulation\reports\S5\20260909T130308Z\representation`: immutable `WINDOW_PLAN.json` with input/code/README bindings and source/condition distributions; `RUN_RECEIPT.json` with attempted calls, exact PCM16 window hashes, timings, memory and failures; `RESULTS.json` with paired cosine distributions and balanced genuine-minus-impostor separation; `RESERVE_ACCESS.json`; and `vectors_local_only.npz`. Vectors remain local and are excluded from the compact handoff. No vector, source identity or oracle activity is fed to canonical H2. The report coordinator may copy compact numeric summaries into its existing four-figure allocation; this script creates no extra figures.

Prepare and validate without loading any model or output waveform:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s5_representation -v
& 'C:\Users\amiri\anaconda3\python.exe' s5_representation.py --prepare
& 'C:\Users\amiri\anaconda3\python.exe' s5_representation.py --validate-plan
```

Anaconda Prompt or Windows command line:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s5_representation -v
"C:\Users\amiri\anaconda3\python.exe" s5_representation.py --prepare
"C:\Users\amiri\anaconda3\python.exe" s5_representation.py --validate-plan
```

`--prepare` refuses to replace an existing plan. `--validate-plan` checks immutable metadata and code bindings, with no audio or inference. Preserve a failed preparation/result as evidence; never refreeze or replace windows after inspecting cosines. All tests use synthetic fixtures and temporary files. No package installation is needed.

The coordinator must schedule the actual model invocation after reviewing the plan and fresh resources. Use the exact existing H2 Python, never Anaconda Python for inference:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s5_representation.py --run
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s5_representation.py --run
```

The command refuses an existing run receipt, enforces a ten-minute launch allowance before the S5 cleanup cutoff, checks C/G storage and OS headroom, and limits this process to2GiB sampled RSS with at least8GiB available OS RAM. The existing CPU session uses two speaker threads. It checks frozen H2 source hashes, full scientific configuration, exact Python path, NumPy/SciPy/SoundFile/ONNX Runtime versions and the ReDimNet2 asset checksum before loading the model. Only the native ReDimNet2 session is instantiated with `_ort_session`; it uses the exact existing `SpeakerModels.embed` method. The unused Pyannote and ASR models are not loaded. No session/profile directories are created. The16MB model size suggests a modest memory footprint, but the run receipt records actual sampled RSS and compute time rather than claiming the estimate was measured.

Each raw PCM24 crop follows the exact existing adapter float32-to-float64 scalar-to-float32 conversion, applying O0's1.4125375446227544 or O1's1.0 once. The unchanged `AudioJournal.append` method writes to an in-memory byte stream to perform the exact native PCM16 clamp/round conversion. The embedding receives those decoded PCM16 floats. This preserves preprocessing without a second gain, resampling, EQ, loudness normalization or clipping repair. Existing raw rails remain part of the recipe. A specific missing input/format/backend failure preserves the partial receipt and stops this optional diagnostic, without replacing windows or restarting the main campaign.

Selection is frozen before embeddings/cosines. It requires complete all-speaker references and real estimated active ranges; it does not substitute a whole-clip fallback. Each active interval is trimmed by20ms plus the larger saved O0/O1 lag spread. Every other utterance's complete convolution envelope, expanded by the same margin, is excluded. The midpoint of the longest remaining0.5s-compatible interval is one candidate per utterance. Source-relative, RIR-shifted and per-output sample intervals are retained separately. The activity already includes the800-sample RIR convention; no second shift is added. Missing saved lag/spread makes the scene ineligible. These numerical margins are conservative selections, not calibrated phonetic-boundary certainty.

Candidates are deterministically hash ordered within each corpus-qualified speaker and selected in round-robin order. There is at most one selected window per original source PCM and source ID across the whole panel, at most four per participant/scene and at most1000 paired windows. This removes duplicate clip/RIR/level copies from nominal trial counts, while disclosing the resulting condition imbalance. Whole-clip duration bins describe the source recording, not the fixed0.5s analysis crop. A window may lie in a scene containing other turns, but its local interval excludes every other utterance envelope.

Genuine comparisons pair disjoint selected windows from the same corpus-qualified identity with different source IDs, PCM and normalized prompts. Deterministic pairing prefers similar room/family/quality/RIR/level/noise conditions. Each genuine anchor receives one different-person comparison from the same corpus and matching second-window quality where available; endpoint reuse is minimized before condition similarity and fixed hash tie breaking. Missing compatible impostors, unequal eligible counts and endpoint reuse are reported. Same-person corpus IDs are not biometric verification; cross-corpus aliasing and pretraining exposure remain unknown.

Results retain planned and completed denominators, output-paired comparisons, distributions by corpus/quality/room/family/RIR, and matched-anchor cosine separation. No thresholds, EER or identity accuracy are fitted. Shared anchors and reused sources/rooms across other parts of S5 prevent treating these comparisons as independent population trials. This diagnostic can reveal representation separation under oracle timing; it cannot separate all online gating, clustering, memory or reconciliation errors, prove a causal postprocessing effect, or authorize using the vectors in S6.

Job identity `contract_sha256` is the established sorted compact parsed-JSON semantic hash. The plan separately records the execution-contract file-byte SHA-256 binding; these are distinct hashes and both are checked in their correct roles.
