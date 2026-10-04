# Configuration command matrix

Purpose: inspect available settings and validate an explicit independent
backend/source selection without loading any model. Inputs are the flags below;
output is JSON on stdout. These are configuration commands, not native execution
or launch receipts. The native runtime must separately admit the selected assets,
resource envelope and source. Actual `raw-qualification-07` passed, and build08 completed a live300 raw/processed GUI workflow. Reviewed derivatives retain that exact source proof; it does not establish this selected model combination's accuracy or throughput. Raw capture eligibility remains separately pinned. See [raw-capture contract](../README_RAW_CAPTURE.md).

Saved external WAV input is mono PCM16 at 16 kHz; kept History replay uses exact mono `FLOAT32_LE` segments instead of the PCM16 convenience WAV. Qualified raw capture is four physical 16 kHz channels of signed interleaved `PCM_S32LE`, stored separately from the processed mono stream. Ordinary source policy is 1 through 300 seconds; the longer developer policy must explicitly reserve at least 3600 seconds. These formats and boundaries are independent of geometry and embedding choice.

Choose one argument string:

| Configuration | `JP_PIPELINE_ARGS` |
| --- | --- |
| All geometry descriptions | `--catalog` |
| Pyannote + ReDimNet, live | `--diarizer pyannote --embedding redimnet --source live` |
| Pyannote + TitaNet, saved | `--diarizer pyannote --embedding titanet --source saved` |
| Pyannote anonymous, live | `--diarizer pyannote --embedding anonymous --source live` |
| CurrentDelayed + ReDimNet | `--diarizer nemotron --profile current_delayed --embedding redimnet --source live` |
| Streaming + TitaNet | `--diarizer nemotron --profile streaming --embedding titanet --source saved --experimental` |
| Chunk52 two-thread explicit | `--diarizer nemotron --profile chunk52_threads2 --embedding redimnet --source live --experimental` |
| Chunk52 anonymous | `--diarizer nemotron --profile chunk52 --embedding anonymous --source live --experimental` |
| Official low | `--diarizer nemotron --profile official_low --experimental` |
| Official very low | `--diarizer nemotron --profile official_very_low --experimental` |
| Official ultra low | `--diarizer nemotron --profile official_ultra_low --experimental` |
| Intermediate 1.20 s | `--diarizer nemotron --profile candidate_1_2 --experimental` |
| Intermediate 2.00 s | `--diarizer nemotron --profile candidate_2 --experimental` |
| Intermediate 3.04 s | `--diarizer nemotron --profile candidate_3 --experimental` |
| Intermediate 4.48 s | `--diarizer nemotron --profile candidate_4_5 --experimental` |
| Compact context 3.04 s | `--diarizer nemotron --profile candidate_3_compact --experimental` |
| Sparse clean-turn identity | `--diarizer nemotron --profile current_delayed --experimental --embedding redimnet --embedding-schedule sparse_clean_turn --embedding-refresh 2` |
| ASR-first delayed attribution | `--diarizer nemotron --profile current_delayed --experimental --speaker-attribution single_d1_late_labels --revision-window 30` |
| Configurable provisional/correction | `--diarizer nemotron --profile official_very_low --experimental --provisional --refinement-profile current_delayed --revision-window 30 --refinement-period 5` |
| Explicit one-hour developer policy | `--diarizer nemotron --profile current_delayed --duration 3600 --developer-soak --drain 600 --backlog 120` |

Every Nemotron row independently accepts `--source live` or `--source saved` and
`--embedding redimnet`, `titanet` or `anonymous`. Defaults are live/ReDimNet and
300 seconds. The developer row configures an hour; it does not run an hour or
claim resource admission. Provisional correction is configuration/component code;
the controller's dual-native-model route remains not admitted without CM5 proof.

PowerShell (edit the argument string on the third line):

```powershell
$env:JP_PIPELINE_CODE = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$env:JP_PIPELINE_PRIVATE = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$env:JP_PIPELINE_ARGS = '--diarizer nemotron --profile official_low --source saved --experimental'
$code = @'
import psutil
psutil.Process().cpu_affinity([14])
import json, os, sys, uuid, runpy, shlex
from pathlib import Path
out = Path(os.environ['JP_PIPELINE_PRIVATE']) / ('presets-preparation-config-' + uuid.uuid4().hex)
out.mkdir(parents=True)
me = psutil.Process()
with (out / 'REGISTERED_OWNER.json').open('x') as f:
    json.dump(dict(pid=me.pid, create_time=me.create_time(), affinity=me.cpu_affinity()), f)
    f.flush(); os.fsync(f.fileno())
source = Path(os.environ['JP_PIPELINE_CODE']) / 'profiles.py'
sys.argv = [str(source)] + shlex.split(os.environ['JP_PIPELINE_ARGS'])
runpy.run_path(str(source), run_name='__main__')
'@
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c $code
```

Command Prompt or Anaconda Prompt:

```bat
set "JP_PIPELINE_CODE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003"
set "JP_PIPELINE_PRIVATE=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
set "JP_PIPELINE_ARGS=--diarizer nemotron --profile official_low --source saved --experimental"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import os,json,sys,uuid,runpy,shlex; from pathlib import Path; o=Path(os.environ['JP_PIPELINE_PRIVATE'])/('presets-preparation-config-'+uuid.uuid4().hex); o.mkdir(parents=True); p=psutil.Process(); f=(o/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); s=Path(os.environ['JP_PIPELINE_CODE'])/'profiles.py'; sys.argv=[str(s)]+shlex.split(os.environ['JP_PIPELINE_ARGS']); runpy.run_path(str(s),run_name='__main__')"
```

These commands use the existing qualified .edge-speech-env interpreter from PowerShell, CMD or Anaconda Prompt, pin CPU14, register the
owner before reading project code and create only a fresh private owner receipt.
See [README_PIPELINES](../README_PIPELINES.md) for test commands and all outputs.

Shared clocks, powerset, embedding, cache and motion mathematics: [architecture and math](../ARCHITECTURE_AND_MATH.md).

## RAM and execution scope

Printing a valid configuration performs no native memory admission. The exact 2 GB target has 2,108,473,344 bytes MemTotal; per-process address-space limits, sampled physical RSS/PSS and system-available RAM are different quantities. The completed two-thread D1 component hour does not admit an hour of the full application. The repaired full-application hour04 failed before source EOF at 3,584.955 seconds; its watchdog closure/full mirror is not a completed hour. Actual14 optional Followup02 completed live300/window60 and Research07 completed the matched sparse/late-label comparison. Their exact reviewed scope is available in production16; neither proves quality or a completed whole-application hour. The247 permitted selections are not247 native tests. Duration flags configure policy; they do not prove elapsed source coverage.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).


The controlled build13 source candidate adds bounded100ms saved/repeated/kept replay appends and numeric append-time/source-wall-lag metrics; see the [source-only batching contract](../README_SAVED_SOURCE_METRICS.md). It also includes the reviewed optional activity-handoff repair. Production16 is now activated through the consolidated launcher; actual build13/14 matched45s optional/research trials exercised that changed saved path. Research07 retained exact processedF32, all4,470 x8 native floats and final ASR, while adding30 supported/partial late-label publications. This is not a claim that batching fixes the failed hour04: external5Hz output-tree checks and1Hz fsynced resource sampling are other unmeasured overhead candidates, and their guards remain unchanged. The research comparison reuses baseline04, requires exact processed float32/sample-clock agreement, and compares all4470×8native D1 probabilities by hash and maximum absolute difference with an explicit1e-5 tolerance. No additional baseline, hour or geometry sweep is prescribed.
