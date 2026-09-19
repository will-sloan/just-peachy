# S4.5 deterministic scene bank

The active bank is version2. Version1 and all of its unplayed canonical WAVs are preserved as a source-only input-QC attempt, indexed by `INPUT_REVISION_RECEIPT.json`. Its F09 background began too late for one SIR window, causing excessive gain and a very low family headroom. Version2 aligns the first target and background longest estimated active intervals before convolution; it preserves the same source/RIR/split roles and full utterances. No physical corpus capture or H2 job existed before this revision. Only version2 is authorized for final capture.

`s45_bank.py` reads the frozen speech/noise catalogues, the canonical 120 eligible HIL RIR records and the supplied 12-family allocation. It writes 240 scene rows (180 development, 60 protected reserve), full source/reference/split bindings, 24 predeclared development sentinels and a future-training provenance index. It does not train or score reserve outcomes.

Each source receives its recorded S4-style preparation scalar exactly once before convolution. Each interferer uses its own compatible four-channel measured RIR. Noise SNR is measured over all four microphones on the estimated target-active window; one scalar applies to the complete interferer. Matching noise-only and speech/noise cases reuse the exact noise component. One headroom scalar per family, shared across its contrasts, keeps canonical peak at or below 0.25 FS. There is no per-microphone normalization, additional distance law or generic reverb.

Short noise events are repeated at up to three declared target turns. For a metadata-labelled transient stored in a longer file, an explicit excerpt of at most two seconds is first selected around its largest dry absolute sample, retaining 250 ms before the event where available. The original planned interval, exact excerpt and dry peak sample remain recorded. Its convolved four-microphone energy peak is aligned to the center of each turn's longest estimated active interval. All choices follow the frozen parent roles and precede device/model output. This prevents a brief sound ending before the SNR measurement window. Longer stationary/ambience/music retains continuous placement. F10 uses documented stationary/appliance or transient parents, with an explicit ambience fallback only if those categories are unavailable; it does not use music. Its development rows form five matched 20/10/0-dB SNR triples. Future-training rows retain each selected parent's actual rights and attribution object; no training is authorized.

Four workers each use one numerical thread. The first render measures numerical headroom and full float64 hashes; a second independent render must match every raw hash before writing FLOAT32 four-channel WAVs on G:. The source/plan/renderer freeze precedes final capture. Existing compatible files are verified and reused; incompatible inputs are not overwritten. Whole clips provide transcript validity; short-turn coverage reflects actual durations, with no arbitrary crops. Common Voice, CMU and HiFi casts stay within each corpus to avoid unresolved cross-corpus identity assumptions.

PowerShell, after source/noise catalogues are complete:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' s45_bank.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s45_bank.py
```

Inputs: `simulation/staging/s45_sources/SOURCE_AND_SPLIT_MANIFEST.json`, `staging/s45_noise/NOISE_CATALOG.json`, `rir_library/v1/RIR_MANIFEST.json`, and the supplied pack `SCENE_PLAN.csv`. Outputs: `scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json`, frozen plan, future-training JSONL, `reports/S4_5/20260909T031300Z/scene_validation.json`, sentinel plan and 240 WAVs under `G:\Just_Peachy_S4_5\20260909T031300Z\canonical_v2`. Frozen source/reference truth never enters H2 or device selection.

`LEGACY_DEVELOPMENT_PROBES.json` contributes exactly two separately bound original S4 development probes for an existing contributor with insufficient unused clips. Their roles and preparation scalars remain unchanged. The new source roster remains frozen separately. Development F01 uses five matched quiet/nominal/louder triples; F05 uses nearby/separated pairs, and pose/obstruction sentinel choices preserve both matched members. Near/distant speech uses declared microphone-domain SIR separately from noise SNR. Strict F12 controls require documented speech-free parents. Ordinary turns prefer whole2–7-second files where available; F03 selects genuine whole short releases.

Regression command from the same scripts directory: PowerShell `& 'C:\Users\amiri\anaconda3\python.exe' test_s45_bank.py`; Anaconda/CMD `"C:\Users\amiri\anaconda3\python.exe" test_s45_bank.py`. Seven groups cover 240-row/split counts, frozen development sentinels, source/whole-clip roles, matched comparisons, receiver/distance/angle contracts, microphone-domain SNR/SIR and exact paired noise, and reserve protection. Test noise metadata is explicitly a fixture; only the final real-noise catalogue/render receipts establish downloaded-noise coverage.
