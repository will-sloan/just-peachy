# Assigned seats (task 05)

`seats.py` holds a bounded (16 person UUID) session layout, template validation,
manual motion stub and the existing causal XVF adapter with raw-field provenance.
`seat_identity.py` implements direction-only assumptions and C088 voice naming with
the actual retained S6C joint scorer for a qualified but ambiguous voice margin.
`seat_controller.py` owns safe Apply epochs, separate templates and invalidation.
`seat_ui.py` supplies the touch editor; no device or model calls occur in widgets.

## Run

From the repository root in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Use Mode → either Assigned seats entry. Tap a name then the arc, or drag a name
onto it / drag an assigned point. Fine controls adjust angle or region by 1°.
Default region is ±25° from the retained direction match setting, **not** the
manual RIR ±5° uncertainty. Overlapping regions require explicit acknowledgement;
their intersection yields an ambiguous direction, never a tie-breaking identity.
Apply anchors at the present location and starts a safe processing epoch if live.
Cancel/Clear affect the draft only. Save template writes a reusable, unanchored
layout; Load changes the draft only. Stop, app restart, natural source end or
Tablet moved invalidate the physical anchor. Apply is required before next Start.

Hybrid exposes soft C079 / strong C060 parent settings (0.60 / 0.90 spatial weight).
Direction-only always retains its C079 gate/association settings; developer
identity/weight overrides are inactive in that mode.
Existing Advanced overrides are effective and logged; Reset restores the chosen
parent. Direction-only does not compare a personal gallery. It retains the shared
native segmentation/embedding lanes for existing speech gates and caption ownership;
**no inference saving is claimed**. Hybrid never trains or adapts a personal
reference, keeps C088 voice floor / unique-duration / disjoint-support gates and
allows Unknown. An explicit voice-only fallback is reported when spatial evidence
is missing or conflicting. Strong current voice disagreement releases involved
seat priors until manual re-anchor; it does not change personal profiles.

## Inputs / outputs

Inputs: existing enrolled UUIDs, manual board-relative projected degrees and
tolerance, fresh existing segmentation/ReDimNet evidence and read-only live XVF
receipts. A private `seat_template.json` lives under the configured data root,
normally `C:\Users\amiri\JustPeachy\data`. It cannot authorize a new physical anchor.
Layouts are session state, not person attributes. Output names carry
`seat_assumed`, `spatial_supported`, `accepted`, `ambiguous`, `unavailable` or
`rejected` diagnostics; raw ASR words remain unchanged. Configurations, decisions,
native radians/degrees, clock mapping and motion events are in the existing bounded
native/linked session logs. No WAV archive is enabled by this feature.

The guide-matched readbacks are `AEC_AZIMUTH_VALUES` (four beam radians),
`AEC_SPENERGY_VALUES` (four speech-energy fields), and
`AUDIO_MGR_SELECTED_AZIMUTHS` (processed index 0; auto-select index 1).
See the [XMOS v3.2.1 command appendix](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/AA_control_command_appendix.html).
The processed direction is selected using fixed-beam speech energy. Seat naming
also requires the existing model speech gate, non-overlap, recent matching energy,
and no clearly separated simultaneously active fixed bearings. Receipt age and
callback mapping are availability bounds, not calibrated DSP source timestamps.
The retained 0.25-second cue admission bound uses original model-evidence
availability; the scheduler's later watermark release does not change that stamp.
A separate existing 0.75-second display freshness bound rejects directions that
have expired by the actual policy decision. Both ages are logged; no timestamps
are clamped or fabricated to satisfy either gate.
Music/singing can fool speech detectors; beams are not a count of real people.

The native linear 0–180° frame folds front/back. No manual placement steers a
firmware beam. The motion stub only consumes explicit events; camera/IMU/GPIO are
unconfigured. Future rotation needs coordinate hypotheses before projection;
subtracting yaw from the folded value is invalid.

Checks and commands: `tests/README_SEATS.md`; native helper: `tools/README_SEATS.md`.
