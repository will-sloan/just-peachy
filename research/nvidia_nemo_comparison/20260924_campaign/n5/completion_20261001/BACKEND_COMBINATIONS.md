# Backend combinations

Current build35 scope: build35 is activated through the Just Peachy shortcut.
Opening stays idle with capture off. Choose one of six backend combinations,
Live microphone or Saved WAV, then Open Application and a Mode. Eleven Mode
policies are visible; backend, identity policy and calibration are separate.

Ordinary Pyannote + ReDimNet Start captured 12.5 s and completed Stop and the
selected full Discard in normal03. That whole check FAILED its later Settings
observer. Separate exit-only05 passed idle Open Application, Settings and Exit
with no Start, capture, models or worker launch. These are distinct scopes.
Live53 passed quiet capture after one verified recovery; Saved54 processed C24
speech with 137 indexed parts, 40 text rows and 117 embedding queries.

Hour08 completed 3600 s / 57.6M samples and all 20 source/model/closure gates.
Backlog grew to 495.360 s; source-to-EOF took 4090.959 s. Completion passed,
but sustainable real-time operation did not. Speech/name accuracy, natural
conversation and biometric calibration remain unqualified or UNCALIBRATED.

Normal live uses manual Stop and storage capacity without arbitrary duration,
recording, people, reference or slot counts, or a fixed ordinary backlog cutoff.
Actual memory/AS/free-space, finite capacity-derived file/drain allowances,
bounded queues, source/lease/owner, I/O and cleanup guards remain. Individual
lane delay labels are unavailable; aggregate backlog remains in health metadata.
Model geometry, thresholds and calibration math are unchanged.

## The six ordinary chooser rows

Choose Live microphone or Saved WAV independently, then Open Application.
Sherpa ASR/PnC, XVF acquisition, retained portrait UI and source clocks are
shared. ReDimNet and TitaNet galleries remain separate.

| Chooser label | Operator ID | Diarizer configuration | Encoder |
| --- | --- | --- | --- |
| Pyannote + ReDimNet | pyannote_redimnet | Retained Pyannote | ReDimNet2-B2 FP32 |
| Pyannote + TitaNet | pyannote_titanet | Retained Pyannote | TitaNet-Large FP32 |
| Nemotron Delayed + ReDimNet | delayed_redimnet | CurrentDelayed: cache264/FIFO0/chunk264/right1/left1/update188 | ReDimNet2-B2 FP32 |
| Nemotron Delayed + TitaNet | delayed_titanet | Same CurrentDelayed | TitaNet-Large FP32 |
| Nemotron Chunk52 2T + ReDimNet | chunk52_2t_redimnet | cache264/FIFO80/chunk52/right1/left0/update40; two native graph threads | ReDimNet2-B2 FP32 |
| Nemotron Chunk52 2T + TitaNet | chunk52_2t_titanet | Same separately pinned two-thread Chunk52 | TitaNet-Large FP32 |

Geometry is in 80 ms encoder frames. The two-thread variant changes its actual
native graph descriptor, not OS/BLAS thread settings or the shared two-core
envelope. Compact/official low-latency/anonymous profiles remain historical or
internal configurations, not extra ordinary chooser rows.

One collapsed Advanced attribution control offers Standard, Sparse clean turns,
Late labels and Sparse + late for named Nemotron choices. It selects existing
single-primary policies, not a new model or parallel refiner. Component
availability does not constitute a whole-application native admission.

## What changes across the rows

Pyannote supplies retained powerset speech/overlap activity and voice tracking.
CurrentDelayed supplies native delayed activity windows; nominal buffering is
21.20 seconds before compute/queue/association delay. Chunk52/two threads uses
4.24 seconds nominal buffering with its exact variant pins. These are diarizer
buffers, not a delay imposed on shared immediate ASR partials.

All rows use the same bounded caption repair: internal native resource resets,
actual BPE continuation joiners, spoken-group closure at pause/Stop, bounded PnC,
atomic source-ordered partitions and delayed identity revisions. Neither a
native activity slot nor presentation paragraph is a biometric identity. Mixed
activity is not assigned by a majority-speaker shortcut. Coarse source/token
windows remain honest; no phonetic alignment is fabricated.

Only Pyannote/ReDimNet retains original C088 naming gates. Its personal-domain
accuracy is still not established here. The other five rows keep biometric
naming blocked without independent exact encoder/query-domain/roster calibration.
Voice queries and closed-group display assumptions can function while that
blocker remains. Cues support voice association; directions cannot calibrate a
name. Plain WAV cannot supply spatial cues; rich replay uses recorded beams/BMI.

## Capacity and preservation

Ordinary recording/history availability depends on measured storage capacity,
not a small recording count or duration-derived metadata quota. Activated build35 also removes inherited People, roster, reference, snapshot and export totals. Segmented files, bounded queues,
individual payloads, paged reads and finite capacity-derived SQLite allowances
protect working memory and physical storage. Stop/Discard must report real
I/O errors rather than hiding them behind quota bookkeeping.

The physical reserve plus 8 MiB SQLite admission edge remains: below that
headroom a writable connection can block deletion validation. See recovery.
Qualified raw is four physical 16 kHz PCM32 channels; processed XVF input/replay
is not called raw. Kept model input remains exact mono float32; convenience
PCM16 WAV is a separate representation.

## Historical measurements keep their original release scope

| Preserved scope | Observed result and interpretation |
| --- | --- |
| CurrentDelayed | Approximately 21.3 s first regular diarizer output in the retained baseline; different from first ASR text. |
| Chunk52 component | Short component RTF about 1.08; not sustained real time. |
| Chunk52/two-thread component hour | Average RTF 0.88445, late bins about 0.94, peak 85.35 C; component/cooling scope, not a complete-app hour. |
| Official low/very-low/ultra-low prefixes | RTF 4.819/5.791/8.119 with safe prefix failures; no full-input pass. |
| Compact 3.04 s context | Short component RTF 0.8568; quality and sustained behavior unqualified. |
| Whole-application hour04 | FAILED before EOF at 3,584.955/3,600 seconds; owner closure/backup did not pass the run. |
| Preserved build26 CHECK21/28 | Pyannote/ReDimNet 60.4 s speech/Save and matched rich replay; not build29 naming or six-row speech qualification. |
| Preserved build28 CHECK32/33 | Quiet first-Start continuation/normal next Start, 12.1/ 12.2999375 s with closure; zero indexed captions. |

No component RTF becomes whole-app throughput. Nominal buffering excludes
compute. Numerical agreement is not ground-truth speaker accuracy. 4/8 GB RAM
may help residency when memory limits, but no larger-board measurement is
available and extra RAM cannot by itself cure native graph work/heat/backlog.

Host storage 23, caption 36, identity 28 and caption-handoff 5 passed their declared fixtures. Later native findings retain their exact release and pipeline scopes. Calibration, natural-input accuracy and sustainable whole-app real-time remain unqualified; historical measurements are not new build35 acceptance.
## Selected source and current release scope

Use [Mode guide](MODE_GUIDE.md) for the eleven visible policies, assumptions and
calibration. The runtime [pipeline notes](../extension_20260928/pi_native_20260928/live_runtime_20261003/CORE_REPAIR_PIPELINE_NOTES.md)
describe all six rows without transferring measurements or calibration.
The final handoff identifies selected current source in
[current_build35/SOURCE_MAP](../extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/current_build35/SOURCE_MAP.md).
