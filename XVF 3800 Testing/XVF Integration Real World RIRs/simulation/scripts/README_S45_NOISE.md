# S4.5 noise intake

Purpose: acquire only official MUSAN/DEMAND data within the 16 GiB / 90 minute active-network-wait bounds and prepare a byte-bound 16 kHz mono noise catalogue. This code opens no audio device and runs no models. Existing source datasets are read-only. New large files are under `G:\Just_Peachy_S4_5\20260909T031300Z\noise`; small manifests are in `simulation\staging\s45_noise`.

Inputs: verified official URL, expected length and official checksum where published; per-directory licenses/annotations; frozen parent/split/segment choices before waveform QC. Unknown/present speech is never strict no-speech truth. Preserve source level; the scene renderer sets SNR after four-channel RIR convolution.

Outputs: `NOISE_CATALOG.json`, `CATALOG_SCHEMA.json`, download ledger and 15-second status heartbeat, archive receipt and new payload files. An absent official checksum is explicit; locally calculated SHA256 is not represented as an upstream digest.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\anaconda3\python.exe'
& $py "$sim\scripts\s45_noise.py" --initialize
& $py "$sim\scripts\s45_noise.py" --download-musan
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s45_noise.py --initialize
"C:\Users\amiri\anaconda3\python.exe" s45_noise.py --download-musan
```

Downloads resume a partial file only when the server honors its exact byte range; at most three attempts. Existing completed targets are size/hash inspected and preserved. Free-space floors are 50 GiB on C: and 75 GiB on G:. The official MUSAN checksum document is saved as `staging/s45_noise/MUSAN_checksum.txt`; its expected archive MD5 is `0c472d4fc0c5141eca47ad1ffeb2a7df`. The catalogue also records a locally computed SHA256 and complete gzip CRC verification. DEMAND rights remain unverified while its official endpoints time out.


## Metadata, frozen selection and prepared audio

After the archive finishes, `--index-musan` verifies the official MD5, computes SHA256, checks all member paths and the gzip trailer, and saves `MUSAN_INDEX.json` plus the original README/LICENSE/ANNOTATIONS files. It does not extract the speech branch. `NOISE_SELECTION_PLAN.json` is a metadata-based parent roster with explicit rights, original attribution, category evidence, no-vocals/speech evidence, parent source groups, development/reserve assignments and the fixed first-up-to-120-second crop rule. Freeze this before decoding for waveform QC. Do not replace failed reserve parents with development parents.

The frozen plan is immutable. `--extract-selected` copies only its selected original WAV parents into the approved G: root. `--prepare` preserves original channel 0 and numerical level, resamples once with SciPy polyphase Kaiser-5 antialiasing if necessary, and emits 16-kHz mono FLOAT32 WAVs. It records clipping/near-rail/DC/faintness as quality flags and rejects empty/digital-silent/nonfinite data. No peak normalization, denoising, model selection or reserve task scoring occurs. Transient files may be short; a scene renderer must explicitly record any event repetition or schedule instead of pretending they are new parents. Parent groups and all derivatives retain the frozen split.

PowerShell (after download and metadata-based selection planning):

```powershell
& $py "$sim\scripts\test_s45_noise.py"
& $py "$sim\scripts\s45_noise.py" --index-musan
& $py "$sim\scripts\s45_noise.py" --freeze-selection "$sim\staging\s45_noise\NOISE_SELECTION_PLAN.json"
& $py "$sim\scripts\s45_noise.py" --extract-selected
& $py "$sim\scripts\s45_noise.py" --prepare
```

Anaconda Prompt / Command Prompt, from the scripts directory above:

```bat
"C:\Users\amiri\anaconda3\python.exe" test_s45_noise.py
"C:\Users\amiri\anaconda3\python.exe" s45_noise.py --index-musan
"C:\Users\amiri\anaconda3\python.exe" s45_noise.py --freeze-selection "..\staging\s45_noise\NOISE_SELECTION_PLAN.json"
"C:\Users\amiri\anaconda3\python.exe" s45_noise.py --extract-selected
"C:\Users\amiri\anaconda3\python.exe" s45_noise.py --prepare
```

`NOISE_CATALOG.json` exposes `parents` and `prepared_segments`. Every segment includes parent/split/category/rights/speech flags, prepared path/SHA256/sample count, native crop/channel, conversion/scalar and quality flags. `strict_nonspeech_eligible` is false for present or unknown speech. An opaque noise filename alone never certifies a kitchen/cutlery class or absence of speech. Music may qualify only from the original no-vocals annotation and applicable rights. Do not feed DEMAND array channels directly as XVF microphones: if acquired later, one original channel is an environmental surrogate with compounded room transfer and unknown/speech-containing references.

Eleven focused offline regression groups validate path safety, selected-channel and amplitude preservation, antialiasing, invalid data rejection, transient Windows publication failure, immutable parent/split freeze, strict no-speech/rights eligibility, existing official-digest checks, bounded/resumable transport behavior, and transfer-cutoff/completed-byte accounting. The recorded run is in `NOISE_REGRESSIONS.json`.

## Transfer ETA and cutoff ledger

In a separate Anaconda/PowerShell process, `s45_noise.py --watch-download` reads the downloader-owned ledger without modifying it and refreshes `TRANSFER_TIME_LEDGER.json` every 30 seconds. It records exact remaining response-body bytes and active-wait budget at the stated measurement time, the conditional UTC cutoff if transfer continues, the overall 11:13 UTC run deadline and 10:43 UTC closeout reserve. ETA is explicitly a throughput-based estimate/range, not a guaranteed time. Once the downloader has published its completed archive receipt, this watcher runs official-checksum/CRC indexing automatically. It stops after its bounded timeout or exhausted active budget. `--time-status` writes one snapshot without waiting.

After archive receipt publication, the time ledger retains the completed transfer count even when the general status file advances to extraction or preparation. Its hypothetical transfer cutoff becomes null. The active-wait charge conservatively also includes small local publication/hash work inside a request invocation; it does not understate elapsed transfer time.

```powershell
& $py "$sim\scripts\s45_noise.py" --watch-download
```

```bat
"C:\Users\amiri\anaconda3\python.exe" s45_noise.py --watch-download
```

## Completed S4.5 intake (2026-09-09 UTC)

The official archive is complete: 11,086,114,085 bytes; expected MD5, locally computed SHA256, all member paths and full gzip CRC passed. SHA256 is `86d1061c7e15b5c9e906777685c519701df51bfde3001e1070dcc9ffac955ee1`. `DOWNLOAD_LEDGER.json` records 11,086,169,719 response-body bytes and 3,485.872 seconds of conservatively charged active transfer/wait. The initial request ended after a Windows metadata publication sharing error; the successful request resumed at byte 450,887,680 without discarding or duplicating that payload. HTTP headers and research browser-page traffic are not measured in this body counter; the remaining body budget exceeds 5 GiB. No extra audio mirror was used.

The immutable metadata roster preceded waveform decoding. `NOISE_CATALOG.json` is COMPLETE: 32 parents and 32 prepared segments, 24 development / 8 reserve, zero failed source decodes, and 918.555875 prepared seconds. Parent/source-group assignments and decoded waveform identities are disjoint across splits. All selected files were already 16 kHz; channel 0 and numerical amplitude were preserved. These are prepared-pool counts; actual usage belongs to the frozen scene manifest.

| Category | Development | Reserve |
| --- | ---: | ---: |
| `stationary_appliance_noise` | 3 | 1 |
| `transient_event_noise` | 13 | 3 |
| `environmental_ambience` | 4 | 2 |
| `instrumental_music` | 4 | 2 |

Category labels come from actual SoundBible titles retained in the official MUSAN LICENSE: dishwasher, frying chicken, record-player static/electronic buzz, footsteps, squeaking door, paper/metal events and named ambience. The stationary category includes continuous cooking/electronic proxies; neither measured stationarity nor a specific HVAC identity is inferred from a title. Explicit fan/HVAC, chair movement and general cutlery-clatter classes remain gaps. Knife sharpening is present and retains that precise label.

All 26 environmental parents retain `speech_content=unknown`; no-speech and ordinary all-speaker text accuracy are unavailable when these uncertain backgrounds are present. Six music parents have original `vocals=N` annotations, four Jason Shaw development parents under CC BY 3.0 US and two Quiet Music for Tiny Robots reserve parents under CC BY 4.0. This is annotation-supported instrumental eligibility, not human listening or a per-frame phonetic absence guarantee. Artist groups do not cross splits. Live-concert candidates and ambiguous music license-version entries were excluded before waveform QC.

Per-parent rights use the authoritative `rights` object, containing `license_name`, `license_url`, `status`, `source_declared_license`, `source_origin_url`, `source_exact_block`, `metadata_evidence`, `obligations` and `scope`; there is no `effective_license` alias. Preserve this object and the `attribution` text in downstream exports. `NOISE_ATTRIBUTIONS.md` provides a readable list. Source-asserted Public Domain and CC attribution entries support the documented evaluation scope; no universal downstream release or training clearance is asserted.

Each prepared parent retains one near-rail sample as distributed, with no attenuation or clipping repair. The reserve electronic Buzz additionally retains a DC flag. `PREPARED_NOISE_QC_SUMMARY.json` lists exact durations, peak/RMS and flags. This source level is not calibrated sound pressure. Scene SNR/headroom remains the renderer's responsibility; short/long transient excerpts or repeats must preserve their exact parent and sample schedule.

The optional DEMAND named field subset remains `BLOCKED_NETWORK_METADATA_UNVERIFIED`: official record/API/export/file checks timed out, so no definitive license/checksum or alternative mirror was invented. `NOISE_INTAKE_RECEIPT.json` binds transfer, checksum/CRC, parent freeze, actual prepared content, rights/category gaps and storage. It does not claim that all prepared parents were used by the eventual bank.
