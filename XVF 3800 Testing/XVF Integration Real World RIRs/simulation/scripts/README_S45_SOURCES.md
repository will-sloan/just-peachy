# S4.5 speech source preparation

This adapter discovers only the installed original CMU ARCTIC, HiFiTTS v0 and English Common Voice 26 sources. L2-ARCTIC is excluded by the user's request. No hardware, model inference, downloaded program, training or reserve task scoring is used. Original source audio, S4 artifacts and the historical 413-contributor exclusion remain unchanged.

Inputs are the three native datasets under `Software Validation from Datasets\Raw Datasets (Not formatted)`, the frozen S4 source/split manifests and existing read-only CV SQLite/native TSV metadata. Small official CMU metadata/notices are fetched from the publisher's working HTTP endpoint; its HTTPS endpoint was unavailable. No speech archive is downloaded. HiFi's installed CC BY 4.0 license and native reader/book/quality metadata are retained. Additional CMU speakers without a separate installed voice notice are explicitly identified; family permission evidence does not fabricate a missing notice or automatically clear future training.

`freeze` writes the 44-identity target and exact candidate roles before waveform QC: CMU14 development/4 reserve, HiFi8/2 with two clean-capable development readers and one clean reserve reader, CV12/4 preserving S4's six development and three reserve contributors. CMU/CV normalized prompt groups stay in one split and enrollment/probe role. HiFi parent books stay in one split and role. Cross-corpus text coincidence and uncertain human aliases are disclosed; avoid simultaneous cross-corpus casts without resolved identities. No global unseen-text or biometric-person claim is made.

`prepare` decodes the frozen shortlist into mono16k FLOAT WAVs on verified G:. It reuses S4's antialiased `scipy.signal.resample_poly` and unchanged20ms activity estimator. It does not denoise or select clips by ASR success. A peak/activity/DC/rail check can reject a clip without changing its frozen role. Low pause contrast is a review flag, especially for short utterances. No arbitrary waveform cuts are made: subsecond candidates are whole released files with sentence-final native text and explicitly estimated source boundaries, not spontaneous responses or manually verified word alignments.

The output interface is `simulation\staging\s45_sources\SOURCE_AND_SPLIT_MANIFEST.json`. `people` contains dataset-qualified identity, development/downstream_reserve split, documented metadata, aliases and accepted counts. `sources` contains S4-compatible source/decoded bindings, transcript plus normalized text, samples/duration, native rate/crop, book/prompt groups, quality activity ranges and rights. `usage` is `probe` or `enrollment_reference` for both splits; **inspect split independently**. Enrollment references must never become probes, and reserve references must not be enrolled/scored in S4.5.

Decoded WAVs remain at original gain (`source_gain_applied=1`). The renderer applies `preparation_gain` exactly once before RIR convolution: `min(10**(-24/20)/active_rms, 0.5/peak)`, rejecting a requested RMS boost above12dB. `postgain_peak_fs` is available for headroom planning. The source level is numerical, not SPL or equal perceived effort. `quality.active_ranges_samples_estimated` is only estimated activity, not phonetic truth. Original files and decoded bindings remain intact.

Outputs on C: are the immutable roster/selection freeze, source manifest, QC and verification receipts, plus small publisher metadata snapshots. Decoded source payloads are under `G:\Just_Peachy_S4_5\20260909T031300Z\sources\decoded_16k`. No large copy of original corpora is made. Existing manifest reruns verify bound bytes; they do not silently replace a frozen selection. Interrupted preparation can reuse identical decoded files. Missing/unqualified clips remain explicit gaps; it never borrows reserve/enrollment clips to satisfy a quota.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_sources
& 'C:\Users\amiri\anaconda3\python.exe' s45_sources.py freeze
& 'C:\Users\amiri\anaconda3\python.exe' s45_sources.py prepare
& 'C:\Users\amiri\anaconda3\python.exe' s45_sources.py verify
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_sources
"C:\Users\amiri\anaconda3\python.exe" s45_sources.py freeze
"C:\Users\amiri\anaconda3\python.exe" s45_sources.py prepare
"C:\Users\amiri\anaconda3\python.exe" s45_sources.py verify
```

`verify` checks selected native CV identity/transcript/age/gender rows, all accepted source/decoded byte hashes, and exact pre-QC role/group assignments. CMU native prompt and HiFi native JSON row hashes are recorded during freezing. The focused tests cover short-clip handling, gain/peak limits, frozen text/role grouping, source rails and forbidden enrollment substitution. These tests do not certify the recordings as anechoic or validate future XVF task performance.

The completed new-source freeze produced794 usable clips from816 candidates and43 usable probe identities from44 planned. The fourth newly selected CV reserve contributor's clips all exceed the frozen12dB requested-boost limit; this remains an explicit gap, with no substitute identity. There are44 whole subsecond probe files and106 whole1–2second probe files across the accepted pool. These totals include reserve input preparation and do not claim every source is scheduled in the final bank.

The coordinator separately authorized minimal reuse of existing **S4 development probes only** where a preserved CV development contributor has fewer than3 distinct new probes. `s45_legacy_sources.py` creates `staging\s45_sources\LEGACY_DEVELOPMENT_PROBES.json`, preserving original source/decoded bindings, probe role and exact S4 frozen scalar. It selects by source-ID order, not task performance. This list is separate from the immutable new-source freeze and flags historical development reuse. S4 enrollment and reserve sources are excluded. The renderer can append this list's `sources` while retaining its binding and reuse flags.

PowerShell, from the directory above:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s45_legacy_sources.py
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" s45_legacy_sources.py
```
