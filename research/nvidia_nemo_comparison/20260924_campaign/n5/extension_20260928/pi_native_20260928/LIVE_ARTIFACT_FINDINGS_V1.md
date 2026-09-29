# Native bounded journals and reopenable PCM

Fresh live-artifact-replay-v1 independently passes **stored event reconstruction, saved-source PCM, byte/frame rejection and synthetic callback-to-journal passage only**. It opens no microphone, stream, GUI or model. Original rc5/install/config, prior journals, failures and user-only previews remain unchanged. The new helpers are not yet integrated into B01.

| Preserved journal | Original bytes | Compact bytes | Events reconstructed exactly | Display patches |
|---|---:|---:|---:|---:|
|Session events|19,989,354|3,546,400|2628|144|
|Archive epoch events|14,104,757|3,730,251|2672|115|

All event values, including source/session/span IDs, raw/formatted text, timing, labels and revisions, reconstruct exactly against the two original journals. Combined size falls34,094,111to7,276,651bytes, about78.7% less. This is storage evidence, not a measured live speedup or explanation of the old input fault. Compression remains an explicit new format with an independent decoder; current application archive readers have not been changed.

Native replay took1.512/1.045seconds. Measured serialization took0.800/0.549seconds and file-write calls0.0117/0.0108seconds; replay elapsed also includes reading/parsing/diff/ownership work. These are short saved-log observations with the original app running, not per-callback deadlines, speech processing or sustained performance. Whole protocol peak39.65625MiBRSS. Actual systemd envelope confirms768MiBhard virtual,1MiBstack,CPU2/3,total200%,one native thread,Tasks64,300seconds/10sstop and8MiBper-file cap. NoMEMCG/RSS enforcement or per-job swap claim.

Each journal has an8MiB total including a reserved terminal marker and1MiB full-record bound. At most two display payloads are kept; patches preserve list chronology. Byte/record limit fixtures reject before writing the rejected event, retain an explicit failure footer, and remain within1024byte test caps. The helper is for an ordered consumer thread; it performs no file I/O inside the callback. Outer process/directory monitoring is still sampled, distinct from the sink's before-write checks.

A WAV reconstructed from the original saved16kHz/715127sample source reopens with identical PCM bytes. This is now a verified listenable **saved-source** artifact, not a microphone recording from the failed live attempt or a new quiet trial. A frame-limit test closes the accepted three-frame prefix before rejecting a two-frame block; conversion clipping is explicit and counted. Five malformed/discontinuous/post-close PCM operations are rejected. All WAV headers, rates/counts and accepted bytes are independently checked.

Two new synthetic cases exercise the actual source callback plus the unchanged detailed-fault subclass through the bounded journal: a normal block and input-overflow flag2. The recorded480frames are the rejected block, and upstream loss remains unknown. ADC/current timestamps and exact status flags survive reconstruction. No real stream is constructed; the original failed trial's flags remain unrecoverable. This fresh768MiB/10s envelope fixes admission consistency for these new cases without rewriting or requalifying the older762/768MiB mismatch.

Target output8,866,605bytes (including review) was backed up privately with exact hashes; original target files remain. The64MiB combined admission reserves32MiB each for target and host copies. ClosureV60 finds all149Pi/44host research identities closed, original app unchanged, captureclosed and both leasesfree. Combined research usage4,146,445,841/5GiB. The fixed32GBPi remains above its5GiB free floor; see CHECK_SUMMARY_V37.json for current RAM/disk/thermal/global-swap observations. No new model assets or dependency downloads.

Next: integrate the sinks and corresponding reader into a fresh source-bound application version, retaining original archive compatibility and explicit failure behavior. Validate that combined real application event paths stay bounded, restore/save/reopen correctly and keep audio/source/frame mapping intact, then perform a newly admitted autonomous quiet trial. A helper replay alone is not a fixed live callback, successful full B01 live run, physical GUI, endurance, speech quality or field release. Alternate D1's cached-embedding mismatch and A2 optimized/sequential work remain separate active priorities.

Run and review instructions: README_BOUNDED_LIVE_ARTIFACTS_V1.md. Private evidence live-artifact-replay-v1-evidence contains the independent REVIEW, exact target backup and lifecycle/admission receipts. Private data never enters Git.
