# XVF3800 measurement data handoff

Prepared 7 September 2026. This package preserves the laptop measurement project and the supplied reference documents for analysis on another Windows desktop. All acquisition statuses and original audio are retained. `VERIFICATION_REPORT.json` records archive-content verification; `USB_VERIFICATION_REPORT.json` must say COMPLETE to confirm the USB copy. This guide alone is not proof that the archive or transfer is complete.

## Restore on the desktop

1. Copy this entire USB package folder to a local folder on the desktop computer. Keep every package file together.
2. Double-click `Restore-XVF.cmd`. Windows PowerShell restores `XVF_Restored` beside the package and verifies each file. Allow at least 16 GB of free disk space for the restored data, in addition to the compressed package.
3. Wait for the final success message and `RESTORE_VERIFICATION.json`. Do not open an archive object as audio: `XVF_DATA.zip` stores each identical file once, by its SHA-256 hash. The restore script recreates the original names and separate copies without changing any bytes.
4. Begin with `RECORDINGS_INDEX.csv`, this guide, and `XVF_Restored/project/PROJECT_CONTEXT.md`. Copy the restored folder to your preferred analysis directory after restoration finishes.

This is a lossless transfer, not audio compression to MP3 or a denoising operation. Laptop originals are retained. Files previously deleted by the user are excluded; the Windows Recycle Bin was not recovered. Empty project directories are preserved. Filesystem permissions and NTFS/OneDrive features are not needed for the measurements and are not reproduced as those features on FAT32.

## Dataset inventory

The archive contains **166 named JPXVF measurement/pilot runs across six room/table labels**, plus 13 request-bearing diagnostic takes and additional hardware/recovery evidence. `RECORDINGS_INDEX.csv` indexes 179 request-bearing folders, including incomplete/failed evidence. Room labels are operator entries; they are not a claim of six independent physical buildings or sites.

| Room / table label | Named runs |
|---|---:|
| Arise Kitchen Main Table | 48 |
| Arise 5th floor low table | 28 |
| Upper Loeb | 14 |
| Loeb Caf | 16 |
| Arise Floor 2 Kitchen | 21 |
| Library Conference Room | 39 |

The 179 indexed folders retain these acquisition labels: 141 REVIEW, 23 RETAKE, 10 INVESTIGATE, and 5 PASS. These totals include pilots and diagnostics. They are not counts of scientifically approved RIRs. The CSV contains run ID, UTC recording timestamp where available, label, phase, room/table, recorder position, speaker distance and angle, pose, obstruction, signal domain, playback scalar, excitation filename, and relative folder path. Blank values mean missing/not applicable, not zero.

## Restored folder layout

```text
XVF_Restored/
  project/
    XVF_MEASUREMENT_WORK/
      experiments/
        JPXVF_.../                 Named measurements, pilots and failed takes
          request.json            Requested settings and geometry
          result.json             Trial outcome and individual pass summaries
          REPORT.txt              Human-readable acquisition report
          SHA256SUMS.txt           Original frozen-file hashes
          00_admin/
            trial_metadata.json   Trial ID, source/receiver metadata, planned passes
          01_photos/              Placeholders/references; do not assume photos exist
          02_raw/
            pass_01_amplified/     Typical Category 3 measurement
              MIC0.wav ... MIC3.wav
              microphones_4ch.wav
              native_packed.wav
              decoded_six_channels.wav
              processed_auto.wav
              excitation_original.wav
              usb_playback.wav
              request.json, result.json, quality.json, REPORT.txt
              capture.json, playback.json, signal_timing.json
              identity.json, capture_configuration.json, gain/delay readbacks
              telemetry/
                received_telemetry.jsonl
                result.json
                native/, source/, stdout.bin, stderr.bin
              commands/, source/, SHA256SUMS.txt
          03_derived/             Byte-identical mic/channel copies and provenance
          04_hil_exports/         Reserved; no automatic HIL product implied
          05_analysis/            Reserved; no automatic final RIR implied
        TAKE_.../                 Earlier diagnostic recordings
        INSPECT_.../, AUTO_USB24_.../ and other hardware evidence
      raw_audio/, telemetry/, logs/, configs/, device_inventory/
    measurement_app/             Local GUI/server source, assets, profiles, tests
      static/recording_reviews.json
    validation/                  Pilot, noise and software verification reports
    planning/                    Experiment and reference-microphone notes
    tools/                       Control executables, analysis helpers, bundled deps
    tests/, tmp/, .git/           Preserved project development/support material
    MEASUREMENT_GUI_GUIDE.md
    PROJECT_CONTEXT.md
    SECTION_6_NEXT_STEPS.md
    Start-XVF-Measurement.cmd
    Prepare-XVF-24bit.cmd
  reference_documents/           Supplied Word workbook, context, PDFs and ZIP packs
```

Use paths relative to the restored root. Some archived JSON fields, manifests, documentation links and launchers contain the old laptop's absolute `C:/Users/amiri/...` paths. Those strings are provenance and were not rewritten. Use the corresponding relative path inside this archive to locate a file on the desktop.

## Audio formats and primary RIR inputs

- Primary campaign recordings are the four simultaneous onboard linear-array microphone signals, **Category 3, after fixed microphone gain and system delay**. Typical campaign readback: microphone gain 10 (+20 dB), SYS_DELAY -32 samples. Check each pass's saved readbacks rather than assuming the setting for every early pilot.
- In the formal USB24 campaign, `MIC0.wav` through `MIC3.wav` are mono 16 kHz PCM24 WAVs. `microphones_4ch.wav` contains those four channels on their common time base. Earlier USB16 diagnostics can have PCM16 WAVs; inspect the WAV header and saved configuration. User-stated order is MIC0, MIC1, MIC2, MIC3 from left to right as viewed while seated. Onboard spacing is nominally 33.3 mm; preserve documented geometry and photographs for spatial interpretation.
- Campaign native USB transport is 48 kHz stereo PCM24 with packed 16 kHz internal signals and framing bits. Its 24-bit words provide 23 payload bits in this mode. `native_packed.wav` is transport evidence, **not ordinary stereo microphone audio**. Use the saved decoder/source and configuration if re-decoding it. Early diagnostics may have 16-bit USB transport; inspect per-pass metadata.
- `decoded_six_channels.wav` contains the decoded six-channel transport payload. The campaign decoder uses columns 2–5 (zero-based) as the four physical microphones; inspect saved configuration/source to interpret the other channels. Use `microphones_4ch.wav` for ordinary array analysis.
- `processed_auto.wav` is an extra DSP-processed diagnostic channel. It may have clipping or adaptive processing even when the physical microphone channels are unclipped. It is not the canonical four-microphone RIR input.
- `03_derived` holds convenient byte-identical channel copies and QC, with `provenance.json`. These are **not deconvolved RIRs**. Do not count raw and derived copies as independent measurements.
- The raw and amplified domains cannot be assumed simultaneous across an eight-microphone vector. If a trial requests both, inspect its planned passes: the software records consecutive passes.
- The exact played source is archived in `excitation_original.wav`; playback gain and device route are in `playback.json`/`request.json`. The standard source has 48 kHz PCM16, a 20 ms starting marker, a 10 s 80–7500 Hz exponential sweep, post-sweep decay and two final markers. Use each `signal_timing.json`; do not infer timing from WAV duration alone.

Preserve relative microphone amplitudes and timing. Do not normalize each channel independently, substitute a processed channel, discard a channel for being quieter, or shift individual microphones to make peaks line up. Those changes can remove the spatial information needed for simulation.

## Speaker, geometry and metadata

Formal campaign source: **KRK GoAux 4, wired**. Working settings were software -6 dB, user-reported Windows volume 70%, KRK volume maximum, Windows Voice Clarity off and speaker enhancements off. Earlier level pilots intentionally used other software levels and processing states. Speaker EQ/ARC and missing metadata must not be invented; consult each run and project notes. No calibrated SPL or automatic speaker correction is implied.

The Dayton EMM-6 was optional and was not used for normal campaign measurements. The original Word workbook is included as a reference; later explicit hardware decisions in `PROJECT_CONTEXT.md` supersede older Edifier/reference-mic assumptions.

`setup.room_name` is room plus table name when applicable. `setup.position_name` names the **recorder/array position**, not the speaker position. Source distance is metres from the array acoustic centre to the operator's source reference point. Source angle is operator-entered degrees under the room convention. Flat/upright pose is independent of obstruction; flat and obstructed is valid. Pose is manually entered; no IMU measurement was recorded.

Names such as `JPXVF_P1_R06_T01_D01_S01_F00_NAT_C2_R13` encode phase, room ID, table ID, device placement, recorder position ID, pose, source-facing code, clutter/obstruction and repeat. `UPR` is upright and `F00` flat; `C2` indicates obstruction, `CU` unknown clutter, `C0` clear, `C1` normal. Refer to JSON for full geometry: the filename does not include speaker distance or angle. P1 is a protocol phase, not proof that final RIR qualification passed. Repeat numbers apply within each condition and may have been reused after deletion; bind references to recording timestamp and hashes as well as name.

## Direction/energy telemetry

`telemetry/received_telemetry.jsonl` is the authoritative complete reply log, one JSON object per line. Default commands are `AEC_AZIMUTH_VALUES` and `AEC_SPENERGY_VALUES`; selected-angle logging may additionally be enabled in some runs. Direction values are in radians; energy is the XVF's native metric and is not calibrated SPL. These four-value algorithm outputs must not be treated as one independent physical microphone bearing per value without consulting the programming guide.

Telemetry timing is based on host receipt or transaction completion (backend-dependent), not device sample timestamps. Preserve `sequence`, `cycle`, command, values, units, parse/finite flags, raw reply and host monotonic timestamps. Read each telemetry `result.json` for actual per-field rate/intervals and errors. Do not assume an exact sample rate, an atomic direction-energy snapshot, fresh DSP values at every query, or sample-accurate alignment to audio. Native linear-array front/rear ambiguity and the transform to operator-entered room angles remain unresolved.

## QC labels and background noise

Capture checks include nonzero/varying microphones, clipping, packed framing, a known continuity sequence, callback integrity, telemetry coverage, playback completion and restoration. Acoustic marker checks are a separate provisional review gate. REVIEW means coarse acquisition/marker checks passed and acoustic review remains necessary. RETAKE indicates failed acoustic-marker confidence/timing in the relevant captures. INVESTIGATE means capture/configuration or other errors require inspection. PASS in diagnostic/reference workflows does not imply a final scientifically qualified RIR.

Five Loeb Caf recordings were explicitly annotated **Background noise present**. They are retained unchanged. Annotation files are `project/validation/LAST_FIVE_NOISE_REVIEW_20260907/noise_annotations.json` and the GUI copy at `project/measurement_app/static/recording_reviews.json`. Read `NOISE_REVIEW.md` in that validation folder. Annotations bind run IDs, timestamps and original hashes. They apply to those five reviewed recordings only; other takes may also contain noise.

For later noise processing, use the annotated initial background window and inspect the late-window candidate for residual ringing. The room decay between sweep end and final markers is desired RIR content, not automatically background-only audio. Estimate per-channel noise spectra; do not subtract an unrelated background waveform sample-for-sample. Nonstationary speech and masked late decay may not be recoverable. Resolve acoustic timing first. Keep original waveforms and untreated RIRs, and save any denoised RIR as a separate derivative with processing parameters and before/after checks. No denoising or final RIR generation has been performed by this transfer.

An offline regression check reproduced the same marker results on ten captures without the GUI; the delete-last button was not implicated. The existing marker detector may still be conservative with noise, room coloration and side-angle arrivals. Do not convert RETAKE to PASS simply because file hashes are valid.

## Integrity and further analysis

`RESTORE_MANIFEST.json` lists every restored file, size, timestamp and SHA-256. The original per-run `SHA256SUMS.txt` files remain inside the restored folders. Transfer verification establishes byte identity and completeness against the transfer inventory, not scientific correctness. Never edit frozen takes in place; put new RIRs, plots, QC and notes in a new analysis directory outside the archived trial folders.

The archive includes the GUI source and locally bundled audio/USB dependencies, but it is **not a standalone desktop installer**. The supplied launcher points at the laptop's Python 3.12 path. On a different PC, install/configure an appropriate Python environment and update a separate launcher; audio devices and hardware tools also require setup. Existing recordings can be read and analysed without an attached XVF board. Do not use the restored GUI's delete function or start acquisition until the desktop installation and device selections have been checked.
