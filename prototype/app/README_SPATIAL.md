# Live spatial field modes

CM5 motion update (September 22, 2026): the installed BMI270 supplies a
three-dimensional relative startup frame; see [README_IMU.md](README_IMU.md).
Reference/unsafe generation changes exclude old cues and clear only location
memory on the tracker dispatcher via `MotionFrameTracker`. Voice tracks and
enrolled identities remain. Offline microphone access can be preapproved in
Settings. Older planning statements below about pending CM5 hardware are
superseded by the deployment handoff.

`live_spatial.py` bridges the existing XVF telemetry worker into the retained
S6C tracker and a small S7 GUI projection. It adds no model, training, source
separation, beam steering, or ASR endpoint changes. Both new modes are available
for field testing and marked experimental, regardless of their research rank.

Inputs are actual callback sample counts/high-resolution timestamps; the three
existing read-only XVF getters; actual ReDimNet/speech/identity decisions; and
the unchanged C079/C060 parameters. Outputs are causal spatial observations for
the existing tracker, bounded counters, and estimated speaker/location display
state. No personal profile is generated from an angle. C088 performs naming
after anonymous association, using compatible voice references.

## Run

From the repository root in PowerShell:

```powershell
& .\.edge-speech-env\python.exe .\prototype\main.py gui --mode spatial_assisted --recipe balanced
& .\.edge-speech-env\python.exe .\prototype\main.py gui --mode strongly_spatial_assisted --recipe patient
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe prototype\main.py gui --mode spatial_assisted --recipe balanced
.edge-speech-env\python.exe prototype\main.py gui --mode strongly_spatial_assisted --recipe patient
```

Choose either command, grant Start's XVF microphone consent, and enable
Settings → Live spatial display if wanted. The ordinary launcher supports
selection inside the GUI. On the prepared CM5, replace the Windows interpreter
with its compatible `python3` and supply its native ALSA/XMOS configuration.
The same code is packaged for both platforms; CM5 hardware remains untested.

## Existing methods and bounded live adaptation

Spatial-assisted uses the exact C079 tracker/XVF settings; Strongly
spatial-assisted uses exact C060 settings (joint spatial weight .90 versus .60).
Balanced and Patient retain their current audio/embedding frontends. Both
spatial variants retain the .25 second cue age, .2 severe voice-conflict floor,
strong-voice reduction of spatial influence, and 12 second position decay.
See `../docs/SPATIAL_PROFILE_PROVENANCE.md` for exact sources and limitations.

Fusion follows the S6A historical shared cue: selected-processed angle[0] for
both O0 and O1, compared with selected-auto angle[1] for engineering reliability.
Latest independently fresh auto energy can qualify the cue; it is not a VAD
probability. A NaN processed direction is unavailable; another beam is not
silently substituted. The display separately highlights the selected O0 auto
or O1 processed direction, so its selected arrow need not equal the fusion cue.

Receipts enter a 256-item pending queue and are mapped to the first containing
or later actual callback, as in S6A. A 1024-item history retains delivery bounds,
not invented DSP observation times. Queue loss is counted and cannot refresh
older data. A minimal optional scheduler hook supplies the actual embedding
window end; no post-window angle may be borrowed during slow inference. Both
sample-window overlap and original .25 second delivery age must pass. Delayed
audio cannot rejuvenate an old receipt. Missing/stale cues fall back to voice.

Spatial modes, or an enabled main spatial display, use at most five finite
three-getter groups per second, sharing the existing serialized control owner.
Ordinary modes with the display off retain low-rate diagnostics. Slow requests
cannot create catch-up bursts, and every query is off the audio callback and
model threads. The UI renders at most four times per second. Getter failure
disables cue use without disabling voice recognition. Stop joins the worker
before device routing restoration.

Display associations come from actual clean voice decisions matched to a causal
cue. `≈` means estimated voice-to-position association, not S6D's separately
verified multibeam person-direction evidence. Names require confirmed voice
matches and retain S6D's two-second naming age. Only the latest fresh voice
decision can be shown as speaking; other positions become last-known and expire.
Speech indication reuses existing segmentation where available; Captions adds
no speech model and therefore shows beam/energy with speech unconfirmed.
This speech flag describes the selected mono input, not independent VAD or
speaker confirmation for every hardware beam. Energy values are raw DSP units.

## Checks

From PowerShell in the repository root:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\run_unit_checks.py --output-dir "$env:TEMP\just-peachy-spatial-unit-check"
```

From CMD/Anaconda Prompt use the same command without `&`, replacing
`$env:TEMP` with `%TEMP%`. Input fixtures are synthetic; output is a bounded
test log/JSON and source bindings. These checks do not access a microphone.
Separate native/physical checks must keep their evidence scope explicit.
