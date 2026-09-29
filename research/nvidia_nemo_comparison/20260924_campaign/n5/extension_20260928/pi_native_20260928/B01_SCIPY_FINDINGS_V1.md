# B01 native retained-E0 memory and passage findings V1

Updated September29 2026,11:07UTC. These are native functional/resource/lifecycle
observations with the existing rc5 app active. No speech, identity, WER or DER accuracy
was measured. No capture/playback/enrollment/download occurred. N4/N5 release
acceptance remains incomplete; accepted new release profiles remain zero.

## The tested memory repair

The actual saved-file controller eagerly imported SciPy signal through two unused
rate-conversion helpers, bringing in additional SciPy/native libraries even though
all admitted source audio was already16kHz. In a fresh source derivative, only the
`resample_poly` imports in vendor `audio.py` and `enrollment.py` moved inside their
actual conversion branches. Source AST review confirms identical code after removing
those import nodes, and every other application file except the explicit backend
manifest is byte-identical to the qualified parent. ReDimNet's original eager load,
model/options, 0.5–2second exact contiguous windows, normalization and all D1/ASR/PnC
work remain unchanged. This is not a new resampler or a different embedding policy.

Application-import virtual size fell from265.141MiB in the preceding lazy-E0
instrumented attempt to116.5625MiB here (148.578MiB difference); these sequential
observations identify startup overhead, not a whole-app throughput benchmark.
SciPy was absent from sys.modules at import and completion. The2GB target's original
app, OS/swap settings, CPU budget and hard768MiB virtual limit were unchanged.

**Important scope:** later48kHz live input/rate conversion can load SciPy again.
This saving qualifies only the tested already16kHz saved-file route. Do not advertise
live-route memory fit or delete/replace SciPy without separately testing that route.

## Reviewed results

| Check | 12second constructed prefix | Original44.6954375second file |
|---|---:|---:|
| Source/ASR/D1 samples retained |192000|715127|
| D1 frames x8 |1201|4470|
| D1 maximum absolute reference difference |0|0|
| Actual retained ReDimNet calls |7|19|
| First text publication from source start |5.639s|5.639s|
| First D1 probabilities |14.365s (EOF)|25.509s|
| First label revision |15.279s|26.767s|
| EOF-to-completion drain |3.399s|12.456s|
| Sampled virtual peak |692.094MiB|709.578MiB|
| Sampled RSS peak |511.016MiB|533.922MiB|
| Kernel ru_maxrss peak |510.109MiB|533.906MiB|
| Natural process exit / app, consumer, archive drain |pass|pass|

Both runs loaded Sherpa and E0 once, retained one ordered delayed D1 stream, used a
fresh empty research gallery, published actual captions/label revisions and did not
invent personal names. Full D1 arrays match the earlier native full-source delayed
reference exactly under the unchanged1e-5 gate. Short arrays match the short reference;
1201native frames do not redefine original full-file frame accounting. Learned
punctuation ran; terminal period heuristics remain explicit (one short/two full).
First text includes source silence and is not per-word latency. Delayed labels are
coarse revision-window associations, not phonetic alignment or validated names.

Full native D1 update compute totaled17.999s and E0 embedding calls2.065s. These
numbers exclude some host/controller and setup costs and overlap the ASR lane; do
not sum them as total elapsed, call the pipeline sustained real time, or infer a
speedup from sparse source activity. The first26.767s label and12.456s final drain
remain actual latency costs. Full sampled virtual headroom58.422MiB (kernel VmPeak
headroom57.906MiB) is promising but does not establish long-run fit.

A separate fresh standalone ONNX CPU session recomputed all26exact waveform windows
twice:52calls. Independent NPY/WAV and event/hash review found application/reference
and repeat max-absolute differences exactly0, unchanged input bytes and finite L2
192D vectors. This supplements the immutable passage reviews whose status correctly
said E0_REFERENCE_PENDING at the time. It proves numerical correspondence for these
windows, not speaker identification accuracy, enrollment or persistent naming.

## Preserved failed hypothesis

The first-use E0 load derivative delayed ReDimNet until after D1 output. It produced
1201D1 frames but failed model loading with std::bad_alloc and zero embeddings.
Its handled failed session drained workers/handles, controller and archive and exited
naturally1. It is not accepted B01, and does not clear the older combined ORT exit-handler
hang. The failure and its smaps led to the separate SciPy dependency investigation.
All earlier numerical/allocation/native-abort attempts and their source hashes remain.

## Reproduction and next gates

Use README_B01_LAZY_E0_V1.md / README_B01_LAZY_REVIEW_V1.md for the preserved failure;
README_B01_DEFER_SCIPY_V1.md and README_B01_DEFER_SCIPY_FULL_V1.md for native passage;
README_B01_SCIPY_REVIEW_V1.md, README_B01_E0_REFERENCE_V1.md and
README_B01_E0_REFERENCE_REVIEW_V1.md for independent evidence. All private evidence is
under local/n5/research-extension-20260928/pi-native-20260928. CHECK_SUMMARY_V12.json
binds reviews. Source prototype: shared-app-b01-defer-scipy-v1/prototype; original
n2_pipeline SHA6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491;
n2_models SHAd00c24ad71d6f2c0cf193425e01b489aecceeb85d47006a52f63770fca9cba05;
backend manifest sha256:f8992d25c29658428e87b0defb03c43677793f8f39a5ffa7e3bfdc2a72ab6eef.
The current B05 user preview remains its separately qualified immutable source.

Next: early Stop then full-file same-process restart on this retained-E0 source;
actual shared native UI/label/control/archive coverage; explicit guarded B01 preview
only after its own checks. Then bounded sustained workload and user-ready live route,
including whether resampling reintroduces SciPy memory. Do not silently replace B01
with B05, claim a ready B01 GUI from controller passage, or repeat unchanged passes.
The earlier1GiB trial remains unanswered/unexecuted; no cap increase was needed for
these saved-file checks. B02/native ASR and wider acceptance remain open.

Closure:73exact owned identities closed; original boot/install/app identities
unchanged; no b05-preview-user-* run found. Combined host/target745059976bytes of1GiB;
available targetRAM1633910784bytes, disk19842695168bytes,53.45C,throttle0x0.
Global swap128in/28771out pages of16KiB is contextual, not per-job or swap-free proof.
