# Optional isolated enrollment-reference inputs

`s45_references.py` prepares one unused development enrollment-reference clip per eligible S4.5 contributor. These inputs are separate from the240 canonical scene bank. The script does not open hardware, run H2, enroll anyone, score names, or access reserve task outputs. The coordinator may capture them only after all240 canonical scenes, if the shared pass/playback/storage/deadline budget allows. Prepared files are not completed captures.

Inputs are the frozen `staging\s45_sources\SOURCE_AND_SPLIT_MANIFEST.json`, canonical RIR v1 manifest and source WAVs. Selection uses the content-key ordering of eligible whole enrollment files. Probes and reserve clips cannot substitute for missing enrollment files. The coordinator separately authorized the original unused S4 enrollment candidate for `CV_0ec4d6799c8c83a9a047`, which has no accepted new enrollment clip. Its original development role/source/decoded hashes and historical provenance remain explicit. Its scalar is computed with the unchanged frozen S4 level formula; it had never received a rendered scalar in S4. No historical source file is rewritten.

Each scene has three seconds of leading digital silence, the whole clip through one valid FLAT/clear four-microphone RIR, and at least five seconds after the full convolved tail. Scene duration is20–25seconds. Paths rotate through the main table and three other non-Upper-Loeb measured rooms at actual distances≤2m. All references share one headroom scalar `min(1,0.25/maximum_unscaled_reference_peak)`. The existing source-preparation gain is applied exactly once before convolution. No per-microphone/RIR normalization, extra inverse-distance gain, artificial reverb, or additional50ms waveform shift is applied. The existing RIR time convention remains in its coefficients; estimated activity metadata accounts for that convention separately.

The original preparation froze `scene_bank\s45_v1_20260909T031300Z\REFERENCE_SOURCE_PLAN.json` before its first render and wrote `REFERENCE_SCENE_MANIFEST.json` after exact second-render checks. Canonical four-channel16k FLOAT WAVs are at `G:\Just_Peachy_S4_5\20260909T031300Z\canonical_references`. Scene IDs are `S45_REF_01` onward; fields match the ordinary S4.5 scene format and explicitly mark optional capture, pending state, zero task scoring and exclusion from the240 canonical count. The manifest binds all selected source and RIR bytes, code and shared headroom. Missing identities are listed as gaps without source-role reassignment.

The coordinator subsequently froze the main canonical bank as `s45_v2_20260909T031300Z` after a pre-hardware F09 input-QC correction. Reference audio, selection and geometry were unaffected: the completed reference manifest was copied unchanged into v2, retaining its original source-plan provenance. `s45_common.py` now selects BANK v2, so the commands below verify that current copy and the same existing reference payload; they do not regenerate the historical references.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_references
& 'C:\Users\amiri\anaconda3\python.exe' s45_references.py
& 'C:\Users\amiri\anaconda3\python.exe' s45_references.py --verify
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_references
"C:\Users\amiri\anaconda3\python.exe" s45_references.py
"C:\Users\amiri\anaconda3\python.exe" s45_references.py --verify
```

Existing completed output is hash-verified rather than overwritten. An interrupted preparation reuses identical files after comparing expected samples. Incompatible frozen plans or outputs fail. The four offline tests cover forbidden source roles, start/full-tail timing, exactly-once source gain with four distinct channels and preservation of the convolution tail.
