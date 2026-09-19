# S6D listening and pacing helper

Purpose: publish all 240 accepted historical scenes as safe mono O0/O1 listening pairs, with transcripts, source timing and a bounded pacing audit. It performs no playback, device I/O, model inference, waveform mutation, normalization or resampling. It reuses the already prepared PCM16 journal WAVs. About 15 MiB of metadata is expected; zero audio payload is copied. Dependencies are the existing native Python 3.11 interpreter, NumPy and soundfile. No environment or package installation is required.

Inputs: the S4.5 final ACCEPTED_CAPTURES_COMPACT manifest and each accepted case_result; the scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST; S6B INPUT_INDEX and its bound prepared mono/accepted raw/receipt/support files; the S6D pack expected index; source-level policy. Original C: and G: volumes must remain mounted at their recorded paths. Expected case selection is exactly 240 unique manifest rows, never a WAV glob. The original 60 reserve task_scoring_allowed=false flags are retained as historical metadata; S6D V2 explicitly authorizes all 240 for current comparisons and listening. The initial build's overly restrictive legacy-flag assertion was corrected before any publication; its failure log remains local.

Validation reads SHA256 and actual headers/frames of 480 raw and 480 prepared mono files; checks admission, recipe, source and per-case bindings; and independently regenerates historical gain-once bytes in memory: raw float32 decode → float64 multiply → float32 adapter → clip [-1,0.999969], multiply 32768, NumPy round and little-endian int16. O0 uses 10^(3/20) once, O1 unity. This reproduces s4_h2_run.py, which is hash-bound in the receipt. The second pre-publication audit caught an initially simplified float32 multiplication; the helper was corrected to historical float64 multiplication and its failed log preserved. It does not write those in-memory samples. Already bound 50 ms RIR origin is not reapplied; approximate timeline annotations add only the saved source-with-RIR to output offset.

Outputs: listening/index.html, SCENE_AUDIO_INDEX.csv/JSON, AUDIO_VERIFICATION.csv, two full playlists, a chronological balanced paired starter, empty LISTENING_NOTES.csv and LISTENING_README.md. report/listening holds the compact delivery index and validation receipt. report/pacing holds PACING_AUDIT.json and per-scene/turn/gap/reuse tables. The HTML uses local files only, no autoplay or external requests; player volume begins at 15% and audio is 1×. Transcript timing is approximate, not phonetic ground truth.

The output folder must not exist. A completed validation receipt in the chosen report is also immutable. Choose the next suffix/report on a deliberate rerun. A failed pre-publication run creates no listening folder; inspect the error, preserve its log, and correct only the helper if appropriate. Existing raw/prepared evidence is never overwritten.

PowerShell, from any directory:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$pack = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\Just_Peachy_S6D_Expanded_Capture_Pack_V2\Just_Peachy_S6D_Expanded_Capture_Pack_V2'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6d_listening_v1.py" --sim "$sim" --pack "$pack" --report "$sim\reports\S6D\20260913T195357Z" --output "$sim\listening\S45_all240_v1"
```

Anaconda Prompt or Command Prompt (uses the same interpreter; no conda activation required):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6D_PACK=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\Just_Peachy_S6D_Expanded_Capture_Pack_V2\Just_Peachy_S6D_Expanded_Capture_Pack_V2"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_listening_v1.py" --sim "%SIM%" --pack "%S6D_PACK%" --report "%SIM%\reports\S6D\20260913T195357Z" --output "%SIM%\listening\S45_all240_v1"
```

Once the `LISTENING_READY` JSON line appears, open its index path in Explorer. The pacing audit follows without waiting for listening feedback. Full output is appropriate for a local build log; the helper emits only one progress line per 40 cases. Runtime safety fixtures cover interval union, half-open boundary ties, unique-actor overlap, three-way overlap and empty support; format/hash/gain checks run on all actual files. No human ratings or exact acoustic-silence percentages are inferred.
