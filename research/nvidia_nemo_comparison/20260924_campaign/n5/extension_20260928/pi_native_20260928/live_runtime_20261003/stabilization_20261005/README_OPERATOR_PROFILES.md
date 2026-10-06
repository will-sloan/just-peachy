# Focused operator backend chooser

Purpose: present six concise named backend choices while retaining all historical
internal profiles. This is a small presentation/configuration module for the
next versioned runtime; it does not admit capture or claim native qualification.
The existing portrait app, source, models, receipts, manual Stop and recording
manager remain responsible for runtime behavior.

## Operator selections

| UI name | Internal profile | Embedder |
|---|---|---|
| Pyannote + ReDimNet | Pyannote | ReDimNet |
| Pyannote + TitaNet | Pyannote | TitaNet |
| Nemotron Delayed + ReDimNet | `current_delayed` | ReDimNet |
| Nemotron Delayed + TitaNet | `current_delayed` | TitaNet |
| Nemotron Chunk52 2T + ReDimNet | `chunk52_threads2` | ReDimNet |
| Nemotron Chunk52 2T + TitaNet | `chunk52_threads2` | TitaNet |

Live microphone and Saved WAV are independent controls. All rows use the
existing `balanced` application default: `classic` is unsuitable as a common
named default because the existing application contract restricts it to the
original Pyannote continuity/caption workflows. Recipe selection remains an
application concern; it is not multiplied into backend choices.

Exact retained geometries in order chunk/right/left/FIFO/cache/update:

- CurrentDelayed: 264/1/1/0/264/188, `v3-offline`, GPU -1.
- Chunk52 2T: 52/1/0/80/264/40, `v3-streaming`, GPU -1; the descriptor still
  requires `chunk52-native-threads2` and the separately pinned graph thread count2.
- Hidden Compact3s: 37/1/0/40/128/40, `v3-streaming`, GPU -1.

The module rejects geometry/thread-selection drift instead of silently using a
different profile. Geometry validation and a catalogue row are not model,
microphone, speech, identity-quality or sustainable real-time evidence.

`hidden_compact_candidates()` returns the two Compact3s encoder candidates only
for review. Neither is selectable through `selection_for` or `choose`. Promote
them only through a subsequent reviewed change after actual current-release
Live application success, including ASR/diarizer/selected-encoder execution,
backlog observations, manual Stop and complete closure. A component RTF alone
does not satisfy this requirement. No receipt is fabricated here.

Standalone anonymous entries, Streaming, one-thread Chunk52, official low/very
low/ultra-low and other intermediate geometries are excluded from this chooser.
Their original implementations remain untouched. Internal anonymous speaker
tracking remains in the selected named pipelines. Sparse clean-turn embeddings
and single-D1 late labels remain valid internal selection options; the older
parallel refiner and provisional second diarizer remain disabled.

## Advanced attribution without extra backend rows

The chooser's Advanced attribution control is collapsed by default and available
only for named Nemotron backends. Its single dropdown selects:

| Preset | Embedding schedule | Speaker attribution |
|---|---|---|
| Standard | `continuous` | `retained` |
| Sparse clean turns | `sparse_clean_turn` | `retained` |
| Late labels | `continuous` | `single_d1_late_labels` |
| Sparse + late | `sparse_clean_turn` | `single_d1_late_labels` |

These are the existing single-diarizer functions. No second worker, provisional
parallel mode, thresholds or model settings are introduced. Refresh remains2s
and the bounded revision window remains30s. Choosing Pyannote disables and
collapses this control and restores Standard. The six backend names and eight
backend/source radio values remain unchanged. The mature application does not
shrink or acquire a new page; this compact control lives only in the chooser.

`attribution_options(preset, diarizer)` returns the two existing selection fields
and rejects a sparse/late preset for Pyannote. `selection_for` still performs the
full original `RuntimeSelection.validate`. Sparse/late CurrentDelayed explicitly
sets the existing experimental flag; Chunk52 2T already has that flag. Each
advanced combination/source must match the release's actual allowed selections.
An absent admission produces a visible error, never an implicit downgrade.

## Integration and API

Place `operator_profiles.py` beside the existing runtime `profiles.py` in the
new package. In its reviewed `classic_frontend.choose` derivative delegate to:

```python
from operator_profiles import choose as choose_operator_backend
return choose_operator_backend(root, manager, config,
                               fullscreen_after_map=fullscreen_after_map)
```

Keep `classic_frontend.show` responsible for chooser → portrait application
handoff and startup error handling. `choose` returns a validated
`RuntimeSelection` or `None` for Exit. It never destroys the window, launches a
process, opens the microphone or calls a model. It uses wrapped touch rows within
480×800, displays experimental status inline, and has no investigation
acknowledgement popup. A production selection must still match the exact
release's allowed selections; unavailable source combinations stay in the
chooser with a visible error. Session admission and assets are independently
checked by the existing manager/worker.

Pure APIs:

```python
from operator_profiles import catalog, selection_for, hidden_compact_candidates
rows = catalog()  # six dictionaries, with exact original profile descriptors
live = selection_for('chunk52_2t_titanet', 'live')
saved = selection_for('delayed_redimnet', 'saved')
late = selection_for('delayed_titanet', 'live',
                     embedding_schedule='sparse_clean_turn',
                     speaker_attribution='single_d1_late_labels')
```

Inputs: a known operator ID, independent `live`/`saved` source, existing optional
scheduling fields; for UI, the existing root/manager/theme and post-map
fullscreen helper. Outputs: configuration dictionaries or a complete
`RuntimeSelection`. Neither creates a runtime policy or changes duration,
model/library pins, thresholds, galleries or sensor behavior.

## Host configuration check

Use the project Python with CPU14 and an early actual host-owner receipt **before
project imports or source reads**. New output paths are required for every run.
Back up and independently restore these two new source files before checking or
using them. No native/SSH/GUI/model action is part of these commands.

PowerShell (run from this directory):

```powershell
$env:PYTHONPATH='../full_application_20261004;..'
$env:JP_OPERATOR_CHECK_OUT='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operator-profile-check-YOUR_UNIQUE_LABEL'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -c "import psutil,os,json,pathlib,runpy; p=psutil.Process(); p.cpu_affinity([14]); out=pathlib.Path(os.environ['JP_OPERATOR_CHECK_OUT']); out.mkdir(); (out/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()))); import sys; sys.argv=['operator_profiles.py','--check']; runpy.run_path('operator_profiles.py',run_name='__main__')" > "$env:JP_OPERATOR_CHECK_OUT-stdout.json"
```

Command Prompt or Anaconda Prompt (same working directory):

```bat
set PYTHONPATH=../full_application_20261004;..
set JP_OPERATOR_CHECK_OUT=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operator-profile-check-YOUR_UNIQUE_LABEL
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -c "import psutil,os,json,pathlib,runpy; p=psutil.Process(); p.cpu_affinity([14]); out=pathlib.Path(os.environ['JP_OPERATOR_CHECK_OUT']); out.mkdir(); (out/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()))); import sys; sys.argv=['operator_profiles.py','--check']; runpy.run_path('operator_profiles.py',run_name='__main__')" > "%JP_OPERATOR_CHECK_OUT%-stdout.json"
```

Expected output: `PASS_OPERATOR_SELECTION_INVARIANTS`, twelve independent source
selections, eighteen backend/Advanced preset selections, three hidden-profile
rejections, preserved internal late/sparse
features, native_execution=false and gui_execution=false. Omit `--check` to
print the catalogue instead. These commands do not prove portrait rendering or
current native startup; the parent integration must perform those focused tests.
