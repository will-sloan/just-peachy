# Identity and Mode integration repair

Purpose: repair the shared handoff from actual speaker evidence to Mode policy,
caption projection and display filtering in a new derivative of build28. The
immutable installed release, embeddings, enrollment vectors and original numeric
gates are inputs. They are never edited, converted or recalibrated by this code.

`identity_modes.py` wraps the pinned N2 name resolver, records bounded actual
query diagnostics, supplies closed display assumptions when voice is unavailable,
and bridges same-label D0 identity metadata revisions inside the original source
overlap, expiry, active-text horizon and revision-count limits. Inputs are the
actual resolver/gallery, actual encoder namespace, selected voice event and
caption row. Outputs are a decision with an explicit name revision, a detached
caption policy row, small GUI explanations and a bounded diagnostic snapshot.
It performs no embedding, gallery query beyond the delegate, reference write or
calibration fit. Closed assumptions have `voice_identity_verified=False`, no
acoustic confidence, no adaptation eligibility and no projected biometric
`profile_id`. The baseline retained C088 closed resolver also keeps its original
math but publishes its forced roster winner as `closed_assumption` before either
caption or spatial consumers see it. A verified `profile_id` and a displayed `display_profile_id` are
different fields. Display roster membership never changes the matching roster.

`d1_spatial_policy.py` connects the four generic spatial Modes on both Nemotron
profiles to the actual pinned `S6CTracker` using the effective C079/C060 settings.
Inputs are genuine native singleton activity windows, their delivered 192D voice
embeddings, the retained source-window beam reader and BMI pose provider. Outputs
are a shared anonymous track decision, source-clock cue diagnostics, and coarse
caption revisions that preserve the native activity slot as provenance. Native
activity remains the caption boundary gate. Mixed/overlapping activity is not
assigned to a majority speaker. Missing, stale, future, unsafe or different-frame
cues fall back to the original voice association; directions do not verify names.

The tracker clock for D1 is the actual waveform window end, and its cue reader is
called with `(source_start, source_end, source_end)`. Observed model availability
and the full native processing delay are reported separately. This does not claim
DSP acoustic synchronization or the person's current position. Live provider
motion-generation checks reject old frames; `MotionFrameTracker` clears spatial
memory while preserving voice tracks. Rich saved replay enters the pinned guarded
source-pose context, using recorded beam/BMI/callback evidence. Plain saved WAVs
still cannot run spatial Modes. Assigned-seat Modes keep their separate existing
source-clock adapter, freshness, anchor, conflict and calibration gates.

The candidate engine also composes the caption agent's `SegmentedAsrMixin`
from `asr_segment_runtime.py`. The helper admits only the exact original
runtime/model source hashes and retains the internal native resource reset.
`InstalledSession._caption` reads the helper's actual boundary metadata after
late-label projection, then preserves it in every atomic caption part. The first
part carries the supplied BPE continuation joiner; following parts use a space.
Recognition pieces retain their words and source evidence. Provenance identifies
the actual parent engine separately from the mixin. The endpoint helper's
purpose, inputs, outputs, run commands and native limits are maintained in its
own README; these caption contracts do not establish native recognition quality.

`personal_gallery.py` preserves independent encoder stores and fresh session
loading. ReDimNet now explicitly carries its actual representation namespace,
as TitaNet already does. Both writable personal stores explicitly declare
`UNCALIBRATED_PERSONAL_DOMAIN`; adding metadata does not create a gate. The
Pyannote/ReDimNet baseline retains its original C088 resolver and thresholds.
The other five rows keep biometric naming blocked until independently calibrated
for the exact model, query domain and roster. Their voice queries can execute and
their closed-group display assumptions can work despite that restriction. Model
namespace, gallery ID/count, compatible references, eligible/unique voice time,
query execution/count, current and aggregate raw cosines, acceptance/rejection
reason and calibration status are retained in actual decision/session evidence.
Raw cosine is not a probability. No vectors are included in these new diagnostics.

`installed_engine.py` applies the actual resolver's caption policy for every named
Mode, preserves per-span `timing_kind`, and atomically replaces the latest exact
parent caption partition with `SessionStore.replace_caption_projection`. It uses
the positive producer `display_version` to reject stale source rows and a monotone
partition counter to include policy expiry revisions. Exact repeats use the same
durable version; the normally-zero user `view_revision` is a separate counter.
Single-D1 late-label expiry reprojects its retained canonical parent through the
same atomic API, never adding a stale summary parent beside the current children.
`application_controller.py` filters with
`display_profile_id`, exposes the personal-domain calibration blocker, and uses
complete explicit `discard` with verified durable-intent retry. Runtime outputs
remain source-ordered caption rows, historical decision events and private session
artifacts. Paragraph grouping is the separate GUI presentation module.

## Running the deterministic contract checks

The fixture test is `test_identity_modes.py`. It requires Python 3.10+ and the
standard library only. It imports no native module, speech model, device, network
client or private speaker store. Inputs are declared fake resolver/provider/track
objects and short source intervals; outputs are unittest pass/fail results. These
fixtures establish field flow and conservative boundaries, not recognition
quality, live sensor quality or sustained qualification. Run only after the
current guarded native inspection permits Python work; do not run concurrently
with a native owner experiment.

PowerShell:

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
Set-Location -LiteralPath $repairDir
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -m unittest -v test_identity_modes
```

CMD or Anaconda Prompt (no new environment or package install):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -m unittest -v test_identity_modes
```

`test_identity_pinned.py` is a separate fresh-process test of the actual pinned
N2 name-map and S6C math, including C079/C060 profile loading, original audio and
duplicate-window gates, unique-duration accounting and motion-memory invalidation.
It requires the existing NumPy environment. Its input is the read-only original
prototype release named in `DEFAULT_RELEASE`, whose exact manifest and loaded
math/profile files are verified before use. A package shell bypasses package
`__init__` so no `PipelineEngine`, model, audio device or native owner is loaded.
Declared synthetic vectors stay in memory and are never printed or persisted.
Output is unittest pass/fail; this is actual policy math with synthetic inputs,
not speech quality or calibration evidence. Run alone, after native preread:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' test_identity_pinned.py -v
```

```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe test_identity_pinned.py -v
```

These commands use the same candidate directory selected above. On a different
host, set `JUST_PEACHY_PINNED_RELEASE` to the exact independently verified mirror;
the manifest pin remains mandatory. No file from a current editable prototype
can silently substitute for the installed source. The test process uses no SSH.

`test_installed_caption_projection.py` is a standard-library-only fixture of the
actual candidate engine's caption/expiry methods extracted without importing the
model graph. Inputs are declared parent revisions, projected children and expiry
patches. Outputs are assertions on the atomic storage API, preserved words/timing,
monotone producer/policy revisions and absence of legacy parent writes. The
storage-focused suite separately validates real SQLite retirement/no-op behavior.
From the same directory in PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -m unittest -v test_installed_caption_projection
```

CMD or Anaconda Prompt:

```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -m unittest -v test_installed_caption_projection
```

Runtime modules are loaded by the separately versioned candidate launcher. They
are not standalone microphone/model commands. The staged package must include
`identity_modes.py` and `d1_spatial_policy.py` alongside the three repaired runtime
modules, plus `asr_segment_runtime.py` and its `asr_segment_contract.py` dependency.
Gallery listing/snapshot capacity uses `gallery_snapshot_io.py`; its maintained
purpose, inputs/outputs and focused run commands are in `README_GALLERY_CAPACITY.md`.
Follow `README_CORE_REPAIR.md` and the candidate dispatcher README for
the launcher/build commands; do not replace files in the installed rollback.

`run_host_identity_checks.py` runs the same focused checks with early Windows
CPU14 registration before project imports, finite 120-second/128-MiB host scope,
C50/G75-GiB actual filesystem floors, source backup and independent restore,
bounded logs and exact source-unchanged/fixture-closure receipts. Inputs are this
candidate's listed source files and a fresh private output directory. Outputs are
the source pins/copies, `TEST_OUTPUT.txt`, `RESULT.json`, `HOST_EXIT.json` and owner
receipts; a caller verifies actual process exit after `HOST_EXIT.json`. It runs
no models, SSH, GUI or production media. Run the two suites sequentially in fresh
processes, after other registered test/native owners are closed. PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' run_host_identity_checks.py --suite contracts --output 'G:/PRIVATE-FRESH-OUTPUT/identity-contracts'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' run_host_identity_checks.py --suite pinned --output 'G:/PRIVATE-FRESH-OUTPUT/identity-pinned'
```

CMD or Anaconda Prompt:

```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe run_host_identity_checks.py --suite contracts --output G:\PRIVATE-FRESH-OUTPUT\identity-contracts
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe run_host_identity_checks.py --suite pinned --output G:\PRIVATE-FRESH-OUTPUT\identity-pinned
```

Use a real private existing parent in place of `PRIVATE-FRESH-OUTPUT`; each child
output directory must not exist. The earlier commands establish the candidate
working directory. The contracts suite includes the separately documented
gallery-capacity fixture. These run commands and owner fields remain maintained
alongside changes to the test scope or source allowlist.

Verified on 2026-10-06: the registered contracts process passed 24 tests, and a
separate registered process passed all four actual pinned policy-math tests.
Neither suite skipped a test. Both retained source backups and independent
restores, verified source stability, closed all fixtures and naturally returned
zero; the caller independently verified the exact recorded Windows owners had
closed. Receipts are under the private runtime root's
`audit-preparation/identity-host-contracts-20261006-a00bee7bd3784ea4981d549c13a1535d`
and `audit-preparation/identity-host-pinned-20261006-01cd043e3a8242b2897f05d78d031499`.
The complete tested source pins are in each `SOURCE_CLOSED.json`. This establishes
the declared field flow and policy math, not native speech quality, live sensor
quality, personal-domain calibration or sustained qualification.

The optional `--suite caption` runs only the five actual caption-method fixtures
under the same owner, source-backup and closure protocol. Replace `contracts`
with `caption` in either PowerShell/CMD/Anaconda command above and choose a fresh
output directory. This is appropriate after a narrow storage handoff change.
Atomic projection now receives `projection_source_start_sample` from the exact
native parent row. Storage uses that stable parent anchor and token order while
each child's actual coarse/aligned clock stays intact; a late child's fallback
clock cannot reorder the parent's lexical range.

## Functional integration matrix and remaining evidence

The six rows remain Pyannote, CurrentDelayed and Chunk52/two native threads, each
with ReDimNet2-B2 FP32 or TitaNet-Large FP32. Sherpa ASR/PnC remain shared. All twelve
visible Modes retain their distinct contracts. The compact expected matrix is:

| Mode family | All six rows: required functional outcome |
| --- | --- |
| Transcription | words, neutral label, no personal lookup |
| Anonymous | separate anonymous continuity, no fabricated personal identity |
| All/selected/open naming | selected encoder gallery only; actual gate accepts or explicit Unknown reason |
| Selected closed | source-linked current/recent roster winner or first roster fallback, visibly assumed when unverified |
| Four generic spatial Modes | actual C079/C060 voice/cue association; missing cues use voice; names keep their independent gates |
| Direction seats | fresh unique anchored seat is an explicit assumption; invalidation never inherits old seat certainty |
| Hybrid seats | exact calibrated voice gate plus original spatial/seat conflict policy; blocker visible |

The deterministic checks cover caption-before-voice, current/recent/future roster
choice, assumption versus verified state, rejection revisions, same-label state
changes, display-only selection, empty/mismatched calibration metadata, delayed
source-window cues, future cues, recorded pose context, audio gates, shared-track
caption linkage, mixed activity and exact-repeat no-op. Actual model/gallery
loading, eligible duration accumulation, cosine quality and full Mode runs need
native-independent speaker validation and native speech/sensor evidence next.

Required native evidence: fresh encoder-specific enrollment and restart; actual
model/frontend pins; nonempty compatible-gallery receipt; actual clean speech
window/query/score records; caption-before/final-before-late identity revisions;
distinct unseen voices and explicit rejection; closed one-person/multi-person
assumptions; rich saved spatial replay; live valid/stale/motion/conflict cases;
save/discard/reopen and ownership closure; and integrated sustained behavior. An
independent speaker calibration/evaluation must use separate participants or
sessions/roles and preserve exact model/domain/roster provenance. No C088 threshold
is transferred to TitaNet or Nemotron. This patch claims no calibrated speaker
accuracy or live endurance from the fixtures.

## Exact encoders and primary references

The installed ReDimNet asset is **ReDimNet2-B2 FP32**,
`redimnet2_b2_fp32.onnx`, 192D L2, mono float32 at 16 kHz, minimum 8,000 samples.
Its model SHA256 is
`5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609`.
The installed artifact does not provide a training/upstream revision; none is
inferred from the current repository. The original [ReDimNet paper](https://arxiv.org/abs/2407.18223)
and [implementation](https://github.com/IDRnD/ReDimNet) describe the family;
the deployed ReDimNet2 family has its [official implementation](https://github.com/PalabraAI/redimnet2).

TitaNet is **TitaNet-Large FP32**, 192D L2, 16 kHz mono, minimum 8,000 samples,
from `nvidia/speakerverification_en_titanet_large` revision
`0dc382f40121a5fbd34db10a2bb04d826c2be6a8`, checkpoint SHA256
`e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3`.
The deployed NeMo preprocessing revision is
`cf724ac337d1ebc7d0dda1e23fb80916f52927a5`, namespace
`nemo-cf724ac3-mel80-16k-eval-v1`, with ONNX SHA256
`86b64bc03a7b151231f59745a8d36619fbc68b739a4abb253bd0d9ce0c350610`
and frontend SHA256
`582f92d2fa2a29be70f6fdc13d67fc1376083ca66cb35401f8335ed85c4115b6`.
See [NeMo speaker recognition documentation](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/speaker_recognition/intro.html),
the [exact model revision](https://huggingface.co/nvidia/speakerverification_en_titanet_large/tree/0dc382f40121a5fbd34db10a2bb04d826c2be6a8),
and [exact NeMo feature implementation](https://github.com/NVIDIA-NeMo/Speech/blob/cf724ac337d1ebc7d0dda1e23fb80916f52927a5/nemo/collections/asr/parts/preprocessing/features.py).
Historical desktop export parity checks are representation checks; they do not
establish personal-domain speaker acceptance/rejection quality or ARM64 quality.
