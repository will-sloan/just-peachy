# S4.5 metadata coverage and compact exports

`s45_coverage.py` joins the frozen 240-scene bank to speech, noise, measured geometry and authoritative capture receipts. It creates compact handoff tables without opening audio, models, hardware or reserve task results. It does not rerender scenes, alter source choices, enroll voices, or perform ASR/diarization scoring.

Inputs are the frozen `scene_bank\s45_v2_20260909T031300Z\SCENE_MANIFEST.json` (current `BANK` in `s45_common.py`), `staging\s45_sources\SOURCE_AND_SPLIT_MANIFEST.json`, separately authorized `LEGACY_DEVELOPMENT_PROBES.json`, `staging\s45_noise\NOISE_CATALOG.json`, and canonical `rir_library\v1\RIR_MANIFEST.json`. The unused v1 input bank and its initial exports were archived before any physical capture after an F09 input-energy-window issue; source/split roles remain unchanged. Optional references come from the separate `REFERENCE_SCENE_MANIFEST.json`, copied unchanged into v2. Actual captures come only from `reports\S4_5\20260909T031300Z\ACCEPTED_CAPTURES.json` and optional `REFERENCE_CAPTURES.json`, with each accepted case-result JSON hash verified and joined to its canonical input SHA, PASS audio/telemetry and frozen-recipe marker. Prepared reference files alone never count as captured. Source and waveform hashes are joined from existing receipts; the coverage program does not rehash large audio payloads.

Outputs in `reports\S4_5\20260909T031300Z`:

- `SOURCE_COVERAGE.csv`: every frozen roster identity, documented demographics/quality metadata, prepared versus actually scheduled probes, duration bins, scene/partner/path support, source gaps and separate optional references.
- `NOISE_CATALOG.csv`: prepared noise segments, parent IDs, split, speech-content/rights metadata and actual scene usage, including unused segments.
- `SCENE_MANIFEST_COMPACT.json`: 240 rows containing scene split, timing totals, source/RIR IDs, dependencies, canonical hash and truth-availability flags. Full transcripts and media are omitted.
- `ACCEPTED_CAPTURES_COMPACT.json`: accepted canonical captures and optional references in separate objects, with preserved failed-attempt receipt pointers and explicit pending counts.
- `RIGHTS_AND_SPLITS.json`: speech rights variants, noise parent provenance, frozen contributor roles, exclusions and downstream-use limitations. This is an evidence summary, not a new blanket training/redistribution clearance.
- `COVERAGE_SUMMARY.json`: actual counts, source gaps, corpus/family/split/short-duration tables, used/unused measured paths, matched scene dependencies and bindings for all five other exports.

Run after the final canonical bank exists. It is safe to rerun the exporter while captures accumulate; outputs are current metadata snapshots and should be regenerated after final optional captures. Normal execution atomically refreshes only these six report files. `--validate-only` performs the same joins without writing them. Missing required bank/source metadata prints `PENDING_REQUIRED_INPUTS`, writes nothing and exits 2. A metadata/role/hash violation prints `INVALID_INPUT_OR_BINDING` and exits 1. Valid partial captures return 0 with `COVERAGE_VALID_CAPTURE_PENDING`; all 240 accepted canonical cases return `COVERAGE_COMPLETE`, while optional-reference counts remain separately explicit.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_coverage
& 'C:\Users\amiri\anaconda3\python.exe' s45_coverage.py --validate-only
& 'C:\Users\amiri\anaconda3\python.exe' s45_coverage.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_coverage
"C:\Users\amiri\anaconda3\python.exe" s45_coverage.py --validate-only
"C:\Users\amiri\anaconda3\python.exe" s45_coverage.py
```

Only the Python standard library and existing path/receipt helpers are needed. There are no numerical worker threads or package downloads. Do not use Python `-O` for the surrounding project receipt tools.

Coverage counts use actual `segments`, not `snr_reference_segments`: a hypothetical SNR speech reference in a noise-only case is not played speech. A conversation means more than one documented contributor has an actual utterance in that scene; an isolated speech scene has one contributor and no environmental-noise segment. Unless a column explicitly says development, its source-usage counts span all canonical splits. In particular, `isolated_speech_scene_count`, `distinct_partners` and `measured_position_count` include protected acoustic-reserve scenes containing development sources; they are not development-only support counts. Use the compact scene split when making that distinction. These support counts do not assert successful diarization or name recognition. Whole-utterance duration bins are `<1`, `[1,2)`, `[2,3)`, `[3,5]`, and `>5` seconds. Short recorded passages are not claimed spontaneous conversational replies.

Upper Loeb acoustic reserve deliberately uses development speech/noise; new-source and joint reserve use downstream-reserve speech and reserve noise parents. All reserve scenes prohibit task scoring. Canonical speech must retain its frozen probe role; enrollment-reference clips remain outside the 240 cases. Angles and distances must equal the validated source geometry, every used RIR must be PASS/REVIEW qualified, and every distance must be within `(0,5]` metres. These joins check metadata integrity, not a new physical angle calibration. Cross-corpus identities, voice age/gender and source anechoic quality are not inferred. Shared people, utterances, prompt/books, noise parents, RIRs and matched conditions prevent interpreting scene counts as independent population samples.

The offline unit tests cover duration boundaries, calibration-only exclusion, enrollment/probe separation, invalid angles/distances/acquisition status, speaker reserve leakage, identity and crop mismatches, prohibited L2 speech, parent-group leakage, strict F12 nonspeech and SHA-bound capture acceptance. Fixtures contain no real speech audio or reserve task metrics.
