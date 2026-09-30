# Original startup and isolated source interface: native fake-device pass

September30 02:05UTC. Independent review: **PASS_NATIVE_ACTUAL_STARTUP_AND_FACADE_FIVE_FAKE_DEVICE_CASES_ONLY**.

The new parent interface exposes Start, request_stop, read and finalize separately. Stop requests no longer imply that accepted buffers may be discarded: consumption continues until the child's terminal receipt. Premature finalization and invalid lifecycle calls reject explicitly. This interface is implemented and checked, but is not yet wired into the production controller.

The actual immutable XVFLiveSource.start method ran in fresh Pi child processes. It performed its original initialization, inventory and explicit ALSA endpoint selection, buffer allocation, stream-start/route/settling and beam startup paths against fake PortAudio/control objects. No real sounddevice library, microphone, hardware commands, models or GUI ran. A fresh private fixture lease was used. This adds startup evidence beyond the earlier pre-started callback checks; it does not establish physical routing or PortAudio fit.

| Case | Accepted model samples | Result |
|---|---:|---|
| Stop with queued raw audio | 15,360 | 41 raw blocks pending at Stop, then all accepted audio delivered and zero pending at finalization |
| Empty Stop | 0 | Clean source and process closure |
| Callback flag2 | 960 | Explicit LIVE_SOURCE_GAP after accepted audio; rejected block size480, upstream loss unknown |
| Restoration mismatch | 15,360 | 89 pending blocks drained; restoration failure remains explicit |
| Route failure during startup | 0 | Original startup cleanup restored fake routing before stream close and lease release |

Each started case discarded exactly480 priming frames before route readiness. Full LiveBlock fields, source/native offsets, epoch and bytes survived IPC; an independent direct97tap FIR reader matched exactly at the existing1e-7 amplitude limit. This does not alter D1's1e-5 state/probability gates. All five child terminal messages were acknowledged and owners exited naturally, with expected failure exits preserved. Fake cleanup order was clock/lease-held route restoration, stream stop, close, lease release. Start failure and callback/restoration faults do not become successful sessions.

The complete protocol took1.163s. Main and maximum child peak RSS were each32.672MiB, separate measurements rather than an aggregate peak. Actual main768MiB/child128MiB virtual,1MiB stacks,CPU2/3,total200%,Tasks64 and300s service limits were reviewed. The128MiB child result does not qualify a real PortAudio process. Private target74files/462,500bytes were hash-verified on backup; target plus host receipts/backup were1,026,554bytes under32MiB combined reservation. Baseline code/config/install and prior sources are unchanged.

ClosureV92: all204Pi/48isolatedhost identities closed, capture closed and both research/hardware leases free. Combined output4,415,554,387/5GiB; fixed32GBPi free17,873,047,552bytes and availableRAM1,585,070,080bytes. Temperature52.9C/throttle0x0. Global swap3062in/35519out at16KiB pages is context only.

Next bind a fresh authority-backed quiet child factory and measured PortAudio resource envelope, then check actual route restoration and accepted-tail drainage before a changed combined B01 run. Production controller integration must adopt the explicit request-Stop/drain/finalize contract rather than reuse its stop-event loop unchanged. Sequential ASR GUI and alternate-D1 arithmetic work remain parallel priorities. No complete live B01, physical GUI, field release, N4/N5, endurance or speech-quality acceptance follows.

[Run instructions](README_SOURCE_STARTUP_V1.md), [independent review/backup](README_REVIEW_SOURCE_STARTUP_V1.md). Private source-startup-v1-evidence/REVIEW.json and BACKUP.json preserve detailed evidence. No existing preview or failure was overwritten.
