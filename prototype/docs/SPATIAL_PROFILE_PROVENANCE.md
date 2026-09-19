# Spatial modes: existing method reuse

The prototype exposes two experimental field-test compositions of existing
S6C/S7 implementations. It does not introduce a new tracker, train a model,
optimize thresholds, or claim that a live composition reproduced a simulation
result. Spatial evidence helps anonymous association; an angle is never an
enrolled person's identity credential.

## Exact retained parents

The frozen source directory, relative to the Just Peachy repository, is
`XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S6C/20260910T123540Z/profiles/`.

| Prototype mode | Exact parent file copied into `config` | Tracker and spatial settings |
| --- | --- | --- |
| Spatial-assisted | `C079/O0_ASR_O0_ID.json` → `parent_C079.json` | Complete retained C079 `normalized_joint` tracker and `tracking_only` XVF policy |
| Strongly spatial-assisted | `C060/O0_ASR_O0_ID.json` → `parent_C060.json` | Complete registered `strong_direction real cues` tracker and `tracking_only` XVF policy |

Original file SHA256 values:

- C079: `4e4a67ae25d8b107909f376e890812f0e6dfddcacdf4f5e78bc6fc1883c86aa3`
- C060: `c175035c8279f2158808e5601d27a9c43ed1edd2e40d52c261aef4568074ef8f`

The only differences between these two complete tracker configurations are
`joint_spatial_weight` 0.60 → 0.90, `direction_change_deg` 35 → 45, and
`direction_persistence_sec` 0.75 → 1.0. Thus Strongly spatial-assisted increases
the maximum spatial score contribution by 50%; it is deliberately more willing
to favor a recent seat when voice evidence is ambiguous. It does not always
select the nearest angle, and it does not promise better accuracy.

Both use the existing `S6CTracker` from
`vendor/edge_speech_pipeline/research_tracking_v3.py`. They retain the same
severe voice exclusion at cosine <0.20, strong voice threshold 0.65, spatial
scale 0.10 on strong voice, 25° bearing match width, 0.25 s maximum cue age,
0.20 spatial reliability floor, 12 s exponential position decay, and location
learning rate 0.65. Clear voice can retain an identity through an angle change
and update its stored direction; the existing `strong_voice_relocation` event
records this. There is no tablet motion sensor or world-coordinate conversion.
Movement recovery follows fresh voice/beam evidence and decay. Missing,
stale, unreliable or unmatched telemetry supplies no angle contribution.

Track lifecycle remains bounded: 64 live tracks, 128 archived tracks, dormancy
after 5 s, provisional retirement after 10 s, committed retirement after 30 s,
and conservative archive return using voice evidence. Location is not preserved
as a permanent seat-to-person lookup. The optional sensor-quarantine switch is
off in both exact parents; this release does not silently enable another
variant or present quarantine as an active safeguard.

## Composition with recipes and names

`app/pipeline.py:effective_profile` copies the selected parent's **entire**
`tracker` and `xvf` sections. Balanced keeps the C065 short/mature frontend;
Patient keeps the C067/N03 longer mature frontend. Both spatial modes use the
unchanged C088 post-association enrolled-name resolver, just as Conversation +
Names does. Compatible personal enrollment is optional: an empty admitted
gallery keeps anonymous continuity. The name resolver receives actual voice
embeddings and clean waveform support. Spatial preference can change which
anonymous track carries name memory, so this indirect identity influence is a
real tradeoff; location alone cannot pass a new enrolled-name voice query.

This is explicitly an experimental composition: C079 supplies the retained
real-cue method, C060 supplies a previously investigated stronger parameter
neighborhood, and C088 supplies naming. Historical C060 used the N00 frontend;
the live prototype deliberately retains the current Balanced/Patient frontend
instead of resurrecting that older evidence timing. The S6C N00 clean-support
admission issue and weak spatial outcomes do not establish a positive result
for this combined live path. Neither new mode receives a simulation-supported
badge based solely on having appeared in a registry. No threshold was fitted
to these implementation fixtures or to new people.

Captions, Enrolled Names, Anonymous, Conversation + Names and Selected Focus
keep their prior behavior. Fast remains caption-only; Classic remains the
actual B36 anonymous tracker with captions/anonymous modes. Balanced and
Patient support the two added spatial modes. Same-tap O0 and O1 choices remain
explicit; no extra inference engine or beam waveform is mixed in by enabling
these modes. Spatial mode does not steer the hardware beam or enable new
endpoint advice.

## Live adapter and display boundaries

`PrototypeEngine` passes the live provider to the existing causal scheduler,
binds its origin to the same capture epoch, and attaches it before live source
startup. The live bridge forwards arrived audio block timing before publishing
the block into the journal. The provider and scheduler's bounded window hook
admit only delivered telemetry compatible with the current audio window;
absence of eligible telemetry leaves a voice-only decision. Driver/host
timestamps are not an acoustic calibration claim.

The main spatial display can show current beam evidence and explicitly stale
or last-known positions. It uses telemetry and already emitted speaker/name
decisions, not another model. A beam can follow music or noise. An associated
name is the pipeline's current voice-backed hypothesis, not proof from angle.
Stored positions decay even if the display is hidden. File input without a
matching telemetry source does not borrow a live microphone angle.

## Run and verify

Inputs: prepared shared ASR/ReDimNet assets, the existing personal profile
store (optional), and direct XVF microphone/telemetry input for live spatial
evidence. Output: captions, anonymous/optional enrolled names, and optional
spatial diagnostics under the same retention settings as the existing app.

PowerShell, from the repository root:

```powershell
& '.\prototype\Start-Prototype.ps1'
& '.\.edge-speech-env\python.exe' -B -m unittest discover -s '.\prototype\tests' -p 'test_spatial_profiles.py' -v
```

Command Prompt or Anaconda Prompt, from the repository root:

```bat
prototype\Start-Prototype.cmd
".edge-speech-env\python.exe" -B -m unittest discover -s "prototype\tests" -p "test_spatial_profiles.py" -v
```

Select Balanced or Patient, choose either spatial mode, choose the matching
O0/O1 route, then Start. The same Python application is exported for Windows
and CM5; use the export's existing setup instructions and native XMOS utility
requirements. Model-free regression commands for an exported installation and
the limitations of the synthetic checks are in
`../tests/README_SPATIAL_PROFILES.md`. Physical CM5 and real-person naming remain
field validation, not claims derived from those checks.
