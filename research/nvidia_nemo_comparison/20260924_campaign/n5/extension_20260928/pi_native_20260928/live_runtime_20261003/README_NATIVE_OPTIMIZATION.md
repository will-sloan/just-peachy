# Native compute investigation and prepared thread variant

Purpose: identify the measured D1 bottleneck and prepare narrowly scoped
experiments using the retained model/compiler/runtime assets. The new compact
profile and two-thread source are experimental. Source preparation and the
isolated `native-threads2-build-01` native compilation are complete; see the
[actual build receipt](README_NATIVE_THREADS_BUILD.md). Numerical comparison,
quality and sustained performance of the thread variant remain separate work.

## Measured evidence, 2026-10-03

The 2 GB CM5 Chunk52 component accepted all 715,127 samples / 44.6954375 seconds,
produced all 4,470 eight-column frames, and matched the retained same-geometry
reference exactly. Its component RTF was 1.08129, but the last three regular graph
calls each took about 6.44 seconds for 4.16 seconds of new audio: about 1.55 RTF
after context filled. Its 437 non-output pushes totaled only 0.2364 seconds.
The native adapter accounted for about 48.3166 of 48.3286 component seconds.

Official low failed safely at its drain deadline, preserving 558,400 samples and
3,456 frames; its 4.81915 RTF applies only to that prefix. The last native graph
log reports 6,988.73 ms compute, 0.52 ms allocation, 0.18 ms input and 0.05 ms
output, for 720 ms of new audio. Feature extraction was about 0.5 ms per push.
Available RAM remained high. This supports a compute investigation, not a claim
that physical RAM capacity or Python copies caused the backlog. It also shows
why early first-output latency cannot establish sustainable throughput.

Exact private reviews are under
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/{chunk52-02,official-low-01}-review-01/REVIEW.json`.
The official timing log is
`official-low-01-monitor-01/closed-output/native.log` under that same root.
See [NATIVE_RESULTS](NATIVE_RESULTS.md) for current native outcomes.

## Source behavior and limits of possible reuse

Source root:
`G:/Just_Peachy_N1/20260924_campaign/local/assets/source/NeMo-Speech.cpp-97a15afa5caa9bce5baaa86c1184103877af4101`.
The retained build archive, receipts and modified-source pins take precedence
over the upstream checkout where they differ.

* `src/asr/diar/diar_pipeline.cpp`: incremental mel production and retained AOSC /
  FIFO pre-encoded features already avoid redoing old feature extraction.
* `src/asr/diar/sortformer_model.cpp`: the V3 feature stack processes new audio,
  then the encoder runs over the combined cached context and new chunk. The
  final encoder/projection/head processes this context at each emitted chunk.
* `src/asr/encoder/rope_transformer.cpp`: attention is unmasked over the supplied
  context. Reusing deep encoder outputs while changing the context would change
  the mathematics. A KV-cache rewrite is not a safe copy-elision optimization.
* The batcher has avoidable single-batch vector copies, but the measured phase
  costs do not support those copies as the main throughput fix. No claimed
  speedup is assigned to a speculative copy rewrite.

The explicit `candidate_3_compact` profile uses cache128/FIFO40/chunk37/right1/
update40, giving 3.04 seconds nominal input buffering and maximum sequence206,
versus Chunk52's397. It reuses the retained LRU8 library and all model weights.
Reducing context changes diarization behavior and requires quality evaluation;
it is not numerically equivalent to Chunk52. See its
[profile instructions](pipelines/candidate_3_compact.md).

## Exact thread provenance

The upstream session source has a helper argument4, but the retained build source
has argument1. The following verified chain resolves that distinction:

| Input / stage | SHA256 |
|---|---|
| Retained `bundle.tar.gz` | `58780becc87dfc0d2dc985bb7a6e338af6e7a0e6bb12422e3417be66171f24fb` |
| Original retained `session.cpp` | `9583306947a8a0cb92d68da94c1803cb5caa064e112face5123e1f94e959251a` |
| Scheduler8192 source | `b88e2ba3e4bd4f55a909e9898f5580fc559c222f3e9a257387540a21366a60c3` |
| Retained metadata2048 / arenas8MiB source | `679ce2e01202723e7f94233df362ad38751f5380882a6e0964db63270dac4726` |
| Prepared same source with helper argument2 | `9d83b3c063f7cd0c56362648f0b8f8b5a9962e884f9a533631074c59f47c895c` |
| Retained LRU8 core library | `fa8ecbb66124b62fced485d45dd2ec6018634a35d39dbc143e221b9f7230b622` |
| Retained Cortex-A76 CPU backend | `f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557` |

The build provenance lives in `metadata-native-v1-receipts/BUILD_RESULT.json`,
`d1-lru-build-v1-evidence/BUILD_RESULT.json` and `cpu-a76-v4/BUILD_RESULT.json`
under the private parent root. The selected Chunk52 descriptor pins the listed
A76 backend. Its actual compile/link flags omit `GGML_USE_OPENMP`, `-fopenmp`
and libgomp. GGML's pthread path therefore matters. The real helper resolves
`ggml_backend_set_n_threads` through the backend registry; the CPU registration
maps it to `ggml_backend_cpu_set_n_threads`. CPU graphs stay on that scheduler
path. No public D1 C-ABI thread field or setter exists.

The retained source requests one native graph thread. This is stronger than
inferring a count from `OMP_NUM_THREADS=1`, but is still distinct from sampled
active workers. Whole-process CPU/wall near one is consistent with one average
busy CPU; it does not measure worker membership. New receipts keep requested,
environment and observed concepts separate. The frozen results are not edited.

## Host-only source preparation

`prepare_native_threads.py` accepts the exact retained archive, an explicit
`--native-threads 1` or `2` (default1), and a fresh private output directory.
It verifies the archive and source pins, reproduces both retained patches exactly,
then changes only the helper integer for the two-thread variant. It writes
`REGISTERED_OWNER.json`, `session.cpp` and `SOURCE_VARIANT.json`. It does not
compile, load a model, contact the Pi or alter the archive/installed files.

PowerShell, after replacing the code/private paths only if the workspace moved:

```powershell
$env:JP_NATIVE_CODE='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$env:JP_NATIVE_PRIVATE='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928'
$code=@'
import psutil
psutil.Process().cpu_affinity([14])
import os,json,sys,uuid,runpy
from pathlib import Path
b=Path(os.environ['JP_NATIVE_PRIVATE'])
o=b/'live-runtime-20261003'/('presets-preparation-thread-'+uuid.uuid4().hex);o.mkdir()
p=psutil.Process()
with (o/'REGISTERED_OWNER.json').open('x') as f:
 json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()),f);f.flush();os.fsync(f.fileno())
sys.argv=['prepare_native_threads.py','--bundle',str(b/'bundle.tar.gz'),'--output',str(o/'threads2'),'--native-threads','2']
runpy.run_path(str(Path(os.environ['JP_NATIVE_CODE'])/'prepare_native_threads.py'),run_name='__main__')
'@
& 'C:/Users/amiri/anaconda3/python.exe' -B -c $code
```

Command Prompt / Anaconda Prompt use the existing interpreter and the same
CPU14 registration sequence:

```bat
set "JP_NATIVE_CODE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003"
set "JP_NATIVE_PRIVATE=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928"
"C:\Users\amiri\anaconda3\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import os,json,sys,uuid,runpy; from pathlib import Path; b=Path(os.environ['JP_NATIVE_PRIVATE']); o=b/'live-runtime-20261003'/('presets-preparation-thread-'+uuid.uuid4().hex); o.mkdir(); p=psutil.Process(); f=(o/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); sys.argv=['prepare_native_threads.py','--bundle',str(b/'bundle.tar.gz'),'--output',str(o/'threads2'),'--native-threads','2']; runpy.run_path(str(Path(os.environ['JP_NATIVE_CODE'])/'prepare_native_threads.py'),run_name='__main__')"
```

Host verification reproduced the exact retained metadata pin with default1,
confirmed the thread2 source differs by exactly one byte, and rejected changed
source / invalid thread requests. Receipt:
`live-runtime-20261003/presets-preparation-thread-variant-eb37d7a89310458481a111af003f0ad1/RESULT.json`.
The compact profile / benchmark contracts passed20 tests in
`presets-preparation-compact-threads-b9974040fa11457290ef67580388f32d/RESULT.json`.
These are source/host contracts, not native numerical or timing results.

## Native comparison plan

An independent build must compile the prepared source with the retained compiler
recipe, replace only its runtime object, retain the exact LRU8 Sortformer source
and reuse the pinned A76 backend. Give the resulting core a new SHA256 and isolated
descriptor. Existing hard-pinned bindings must not silently accept a new library.
Keep CPU2/3, aggregate200%, finite AS/task/time/output budgets and all numerical
library environment values1. This experiment changes native graph concurrency,
not BLAS/OpenMP environment settings or the safety envelope.

Compare thread2 Chunk52 against the complete existing thread1 reference on the
same pinned715,127 samples. Check every8-column probability, frame/sample origin,
EOF and closure, reporting max/RMS error and any changed decisions without
assuming bitwise equivalence across thread reductions. Record graph phases,
CPU/wall, task observations, memory, backlog and mature-context timing. Only then
measure ASR/embedding competition: component headroom cannot admit a whole
pipeline or a dual worker on its own.

Retain the user's explicit coverage of the three official presets and small
1.2/2/3/4.48-second candidates. For clearly overloaded geometries, a separately
pinned matched shorter source may provide a finite comparison; declare its exact
interval and EOF, and do not label a failed long prefix as a complete short run.
Use the full44.7-second source for selected candidates and the compact-context
tradeoff. Do not repeat already healthy unchanged runs merely for another badge.

## Native phase logging bound

`NEMO_SPEECH_TIMING=1` emits C `fprintf(stderr,...)` lines, so Python stream
replacement alone does not capture them. Each actual session graph emits one
scheduled or direct timing line, never both. FE emits one line per FE call.
For the pinned44.7-second source /1600-sample blocks, at most448 FE calls plus63
official-low graph calls give511 timing lines. `GGML_MAX_NAME=64`; a conservative
2048 bytes per timing line is below1MiB for this case. This is not a bound on all
other native diagnostics. Use OS-fd redirection and separately reserved finite
files enforced by `RLIMIT_FSIZE`; retain failed-prefix/logs at the limit. An hour
requires a separate log/output reservation. The next benchmark's8192-byte call
records at100ms require more than256MiB for an hour, so that envelope needs an
explicit larger block (for example3200 samples), not an unrecorded cap increase.
