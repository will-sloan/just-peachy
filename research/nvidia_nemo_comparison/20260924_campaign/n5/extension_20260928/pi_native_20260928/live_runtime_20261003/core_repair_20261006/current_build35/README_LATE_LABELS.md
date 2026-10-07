# ASR-first text with delayed single-D1 speaker attribution

`late_labels.py` supplies an explicit presentation contract for one continuous
Nemotron context. ASR text appears as soon as the installed text path publishes
it. An already-supported speaker label can appear immediately; otherwise the
label is Unknown until genuine D1 evidence arrives. Later evidence revises the
same caption/span IDs within a configurable window, default 30 seconds. This is
ASR-first delayed speaker attribution, not a fast diarizer or dual-worker model.

The helper loads no model, starts no thread and waits for no inference. It consumes
the exact installed N2/S7 presentation's already-admitted rows. Evidence comes
from `word_spans[].speaker_history`, including native `n2-caption:` event IDs,
identity versions, tracker IDs and overlapping source-evidence intervals. Existing
clean-turn embeddings can provide names through that upstream decision. No label
is copied from an unrelated earlier turn. DOA/angle metadata alone does not name
a person; it remains diagnostic unless the existing upstream policy already
admits genuine voice evidence for the interval.

When D1 has not processed a new interval, its clean-turn embeddings are also not
available yet. This mode honestly displays Unknown in that case. It does not
invent a faster initial identity or satisfy the separate dual-diarizer refinement
requirement. The injected `RefinementCoordinator` still has no admitted native
dual-worker integration, and that experimental option remains unavailable.

## Inputs, integration and outputs

Select `speaker_attribution='single_d1_late_labels'` in `RuntimeSelection` with
`diarizer='nemotron'` and `allow_experimental=True`. Any of the three embedding
choices is allowed. `speaker_attribution='retained'` is the unchanged default.
`revision_window_seconds` accepts 1–300 seconds. Input source and geometry remain
independent selections.

Create the helper after obtaining the actual installed engine's session ID and
the exact source identity (saved WAV pin or live session stream identity):

```python
from late_labels import SingleD1LateLabels
view = SingleD1LateLabels(selection, session_id, source_id)

# Inside the existing serialized caption consumer:
shown = view.project(installed_s7_row, now=time.perf_counter())
if shown is not None:
    persist_and_display_same_caption_key(shown)

# Inside the controller's regular health tick, under the same serialization:
for patch in view.expire(now=time.perf_counter()):
    update_existing_caption_status_without_replacing_text(patch)
```

The integration functions in this example describe the caller's existing storage
and notification operations; they are not exports from this module. Never call
`project` on a synthetic dictionary and describe it as native evidence. Use the
normal serialized caption/health consumer so observations share a monotonic clock.

`project` returns an unchanged `text`, `display_text`, `caption_key`, utterance ID
and source interval, plus `speaker`, `label`, `provisional`, `speaker_supported`,
`fully_attributed`, `attribution_status` and `attribution_spans`. `None` means the
projected result is a duplicate or an already-retired caption. It does not mean
the caller should delete text. Store/upsert by the existing caption key.

Every attribution span contains exact half-open 16 kHz samples, its native
evidence event/version and evidence interval, and its revision deadline. Timing
remains `ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT`; no word alignment is inferred.
`speaker_supported` reports actual evidence, so it can drive first-speaker timing
without treating "Pending identity" as a speaker. `provisional` means some
displayed span still awaits attribution; supported labels may nevertheless be
revised within the configured window. Native Unknown can retract an earlier label
before expiry. After expiry, an existing supported label or Unknown is retained.
`expire` supplies compact status patches, not replacement text.

State is bounded to 128 caption entries and 512 spans per entry by default.
Retired source intervals cannot resurrect captions. If a row exceeds the span
evidence capacity, all text is still emitted and the output explicitly sets
`evidence_capacity_exceeded`; no complete-attribution claim is made. Text rewrites
retain expired evidence for unchanged stable span IDs and give genuinely new
spans their own bounded window. Caller-owned outputs cannot mutate retained
evidence. The original native event log is preserved even for rejected late
presentation changes.

## PowerShell configuration and tests

Use the existing Anaconda Python and installed `psutil`; no download is needed.
The wrapper pins CPU14 and durably registers numeric process identity before
reading project files. This command runs only synthetic presentation tests.

```powershell
$env:JP_PIPELINE_CODE = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$env:JP_PIPELINE_PRIVATE = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$taskCode = @'
import psutil
psutil.Process().cpu_affinity([14])
import json, os, sys, uuid, unittest
from pathlib import Path
out = Path(os.environ['JP_PIPELINE_PRIVATE']) / ('presets-preparation-late-labels-' + uuid.uuid4().hex)
out.mkdir()
p = psutil.Process()
with (out / 'REGISTERED_OWNER.json').open('x') as f:
    json.dump(dict(pid=p.pid, create_time=p.create_time(), affinity=p.cpu_affinity()), f)
    f.flush(); os.fsync(f.fileno())
sys.path.insert(0, os.environ['JP_PIPELINE_CODE'])
r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_late_labels'))
sys.exit(0 if r.wasSuccessful() else 1)
'@
& 'C:/Users/amiri/anaconda3/python.exe' -B -c $taskCode
```

To print the configuration without executing models, replace the last two Python
lines with:

```python
from profiles import RuntimeSelection
print(json.dumps(RuntimeSelection(diarizer='nemotron', embedding='redimnet', input_source='saved', nemotron_profile='current_delayed', allow_experimental=True, speaker_attribution='single_d1_late_labels', revision_window_seconds=30).validate(), indent=2))
```

## Command Prompt or Anaconda Prompt

```bat
set "JP_PIPELINE_CODE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003"
set "JP_PIPELINE_PRIVATE=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
"C:\Users\amiri\anaconda3\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import os,json,sys,uuid,unittest; from pathlib import Path; o=Path(os.environ['JP_PIPELINE_PRIVATE'])/('presets-preparation-late-labels-'+uuid.uuid4().hex); o.mkdir(); p=psutil.Process(); f=(o/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); sys.path.insert(0,os.environ['JP_PIPELINE_CODE']); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_late_labels')); sys.exit(0 if r.wasSuccessful() else 1)"
```

The synthetic fixtures are the only inputs. Outputs are the console test report
and early owner receipt in a fresh private preparation directory. Six focused
presentation contracts passed; together with benchmark, sparse and core checks,
31 tests passed on 2026-10-03. Receipt:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-late-ram-tests-92462418ee134dde9b24669ca486badc/RESULT.json`.
This is contract evidence only. Native pipeline performance, recognition quality
and physical display timing require actual measurements.

Prepared anonymous-track correction (2026-10-04): actual build13 research06 preserved all 4470x8 native probabilities and the final ASR word sequence, but this view showed no supported speaker because it treated an Unknown enrolled name as an Unknown native track. The derivative `admitted_identity.py` now accepts only the same existing anonymous label from an exact admitted S7 segment, with matching token, target revision, event, identity version, track and source interval. Null-track Unknown remains a retraction. Captured-row host replay produced 30 supported publications instead of zero while preserving text, caption IDs and clocks; it also passed eight negative boundary cases, expiry and duplicate/retraction checks. This is prepared source with host evidence, not a new native pass. See [identity correction instructions](README_IDENTITY_CORRECTION.md). Optional parallel refinement is unchanged and needs its separate admission and measurement.
