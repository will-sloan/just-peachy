# Assigned-seat semantics and field boundaries

These are two additional experimental product modes in the current pipeline,
not a new research sweep. Manual seats are bounded session state (16 UUIDs),
kept separately from immutable personal reference files. The reusable private
`seat_template.json` always says `valid: false`; loading it only fills a draft.
People may share display names; matching and seat membership use UUIDs.

The UI displays the native folded 0–180° frame, 0° toward MIC3, 180° toward MIC0.
Front and back hypotheses can have the same bearing. Region half-width is 25°
by default (the retained tracker match setting), adjustable from 1° to 45°.
Changing region size is an explicit manual assumption, not confidence tuning.
The historical ±5° manual RIR uncertainty is not applied to runtime telemetry.
Region intersections yield no direction-only person. Hybrid can distinguish by
qualified voice, with the spatial ambiguity explicitly recorded.

## Evidence and clocks

The existing live owner supplies three read-only native fields. No second device
owner, gain/routing change, packed injection or fixed-beam steering is introduced.
The adapter retains raw radians and their native degrees, individual host receipt
times, callback delivery mapping, selected index and reliability. Input-causal cue
admission remains 0.25s with reliability ≥0.2; post-scheduler direction age must
also be ≤0.75s at the actual observed decision. These are separate checks on real
stamps. They do not imply known DSP receptive time or microphone-to-angle latency.

`AUDIO_MGR_SELECTED_AZIMUTHS[0]` is the retained S6A processed direction for both
O0/O1 association. Fresh fixed-beam energy and compatible bearings are additionally
required for a seating assumption. More than one active fixed bearing separated
by >25° is treated conservatively as ambiguous; the number of beam arrows is
never claimed to be the number of people. The existing model speech/non-overlap
gate is also required. Music with a false speech detection, singing, reverberation
and closely aligned simultaneous people remain field risks, not solved cases.

Semantics checked against the [XMOS v3.2.1 command appendix](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/AA_control_command_appendix.html)
and [host guide, microphone orientation and DoA](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/03_using_the_host_application.html).
The application matches its existing linear-board configuration; no firmware
changes or arbitrary latest command maps were substituted.

## Naming policies

Direction-only runs no personal gallery queries. It keeps the current native
speech/embedding/tracking lanes for speech evidence and coarse caption ownership;
the embedding values do not select the seat identity. This implementation does
not claim a processing or memory saving. A unique eligible region produces
`assignment=seat_assumed`, never verified identity. Missing/expired direction,
overlap, non-speech, outside-region or unresolved collision leaves words present
and the identity unavailable/ambiguous. No person is trained from direction.

Hybrid runs native C088 voice naming against the assigned roster. Clear accepted
voice can survive a missing/conflicting spatial cue, with an explicit fallback
reason. Strong current voice (retained 0.65 cosine / existing name margin) that
disagrees with a seat releases the involved spatial priors until re-anchor.
Neither the saved seat positions nor personal enrollments are rewritten.

For a qualified voice that fails only the name-margin comparison, the adapter
uses the **actual** `S6CTracker._joint_scores` implementation on temporary seat
hypotheses. C079/C060 weights are 0.60/0.90, normalized voice scale 0.15, spatial
Gaussian width 25°, joint margin 0.10, and strong-voice spatial scale 0.10.
Unknown/new remain competitors. C088's original 0.5128856897354127 voice floor,
2.0s unique support, two disjoint observations and voice-consistency gate still
apply. This adaptation to enrolled seat hypotheses is experimental; retained
anonymous-tracker simulation results do not validate its seat-recognition accuracy.
The extra work is bounded gallery dot products/scoring, not another neural pass.

Soft/strong controls select the complete retained tracker parent while Balanced/
Patient preserve their existing frontend timing. Existing deliberate developer
overrides are exported and logged, and Reset restores the selected parent.
Direction-only keeps fixed C079 settings and ignores identity/weight overrides.

## Motion, words and diagnostics

Manual/stub motion immediately invalidates the anchor and current seat-location
associations without stopping the active source or clearing native voice memory.
Direction labels become unavailable; hybrid voice fallback is explicit. Applying
a re-anchor starts the existing safe processing epoch. The motion service is a
stub: physical IMU/camera/GPIO remain unconfigured. Future rotation must transform
coordinate hypotheses before folding; subtracting yaw from 0–180° is invalid.

Caption evidence IDs link names to actual seat/voice decisions. Seat assumptions
carry a visible suffix; all original words survive an identity failure. Historical
caption spans are not word-aligned proof of who spoke. The score page explains
voice/spatial/assumption basis, ages, released trust and raw uncalibrated scores.
Raw/full diagnostics stay private; compact handoff/screenshots use corpus fixtures.
