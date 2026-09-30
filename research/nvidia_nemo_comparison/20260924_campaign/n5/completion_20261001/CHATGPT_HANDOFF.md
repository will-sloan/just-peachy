# ChatGPT handoff: Just Peachy offline Pi

Snapshot September30 2026,17:42UTC. **IN_PROGRESS; offline field release not accepted yet.** Deadline October1 17:42:44UTC /13:42:44Toronto. Start with START_HERE and ACCEPTANCE, then the newest verified CHECK_SUMMARY and current STATUS. Current verified implementation commit `2e64b792536bbf35309ff5e1497e6ec82ecae8ce`, branch `codex/n1-foundation-20260924`.

## Objective and architecture

Touch-first480x800 offline CM5/2GB/32GB-eMMC prototype: local microphone or saved source -> ordered source-clock stream -> independent captions and diarizer -> provisional anonymous/identity evidence -> bounded history/audio store -> GUI. Original rc5 is the recoverable running baseline; the installed v12 research candidate is separate. B01 combines Sherpa/PnC captions, native D1 and retained compatible ReDimNet; B05 is explicit anonymous operation. Nemotron-3-Diarization is D1, an eight-slot activity model, not an enrollment encoder. TitaNet is retired from the first field candidate. No personal-name claim from an empty gallery; no silent fallback.

D1 geometries: delayed264/1/1/0/264/188; streaming13/1/0/80/264/40; experimentalChunk52=52/1/0/80/264/40. Exact libraries, adapter, weights, catalogue and CABI are pinned. Libraries remain mapped after model close: one run/mode per fresh process. Set an independent session on an empty stream before samples. Stop or ERROR does not release ownership until workers join and model/source closure is verified.

## Exploration and outcomes

| Area | What happened and what the evidence means | Entry point |
|---|---|---|
| Native D1 mode factory/binding | All three actual modes passed scoped saved passages. Matched pre-EOF reference outputs were exact; new EOF tails have accounting, not matched-reference accuracy credit | V85-V89; D1_MODE_CATALOG_V1 and findings |
| Saved application modes | StreamingV3, Chunk52V4 and DelayedV5 each passed actual installed Controller/withdrawn UI selection/Start/Stop and independent session/ownership closure. Separate admissions, not unrestricted launcher | V91-V93; D1_APPLICATION_SAVED_FINDINGS_V2/V3/V4 |
| Endpoint failures | V1 invoked a Tk holder incorrectly; V2 expected120frames from19200samples but native emitted121. V3 bound source/object/build/link/header lineage to0empty or floor(N/160)+1nonempty. Earlier failures remain failed | V90-V91; endpoint contractsV1-V3 |
| Method controls | V94 bound fixed A76/resource profiles and unavailable methods. V95 integrated actual app details/Back/Start, rejected GPU=true before worker creation, then ran68800samples/431frames and closed all owners | V94-V95; D1_METHOD_APPLICATION_FINDINGS_V1 |
| Native speed | Retained44.695s same-geometry generic->repairedA76 wall-work reductions:23.47%delayed,24.49%streaming,24.33%Chunk52, with exact reference agreement. One file, rc5 concurrent. Current delayedLRU1main differs from that earlier comparison main | D1_METHOD_CONTROLS_FINDINGS_V1; not new app/sustained speedup |
| Resource methods | Executable graphLRU1delayed/8others; delayedmetadata2MiB;1MiBstacks; one native thread/GPUoff. Speaker/FIFO history unchanged. No separate measured speedup assigned to resource bounds | V85catalogue /V94methodcontract |
| Live and storage | Short quiet/source/GUI trials provide scoped function evidence. V65planned120s failed60s archive/~115s journal limits. Later writer components passed; full corrected sustained composition remains open | FIELD_SUSTAINED_FINDINGS_V1; later component findings |
| Alternate ONNX D1 | Whole-waveform cache parity fails unchanged1e-5 gate (~2.346e-4 original). Projection localization and one OpenBLAS alternative did not fix it. Frontend/ordered-state scoped passes are not full runtime acceptance | V45/V46/V51 and later STATUS |
| Nemotron ASR | Qualified generic A2 component and sequential saved UI pass; faster A76candidate fails exact revision/timing gates. Field integration unavailable and secondary | V52 /sequential findings |
| Display | User confirmed ribbon shift fixed blank display. Requested90->270 rotation applied/persisted with exact backup/restore-copy;480x800 retained. No physical-touch/reboot-persistence claim | README_DISPLAY_ORIENTATION_V1 and private receipts |
| Campaign coverage | N1-N3 have separate scoped handoffs. Original closure preserved; N4full240cell panel and fullN5 incomplete. Specified/model-free/Windows/native/held-out evidence stays distinct | Stage handoffs,34methodcatalogue, latest summaries |

## Current evidence and next action

V95 closure203:374recordedPi/48priorisolatedhost identities closed, plus2fieldworkers/1consolehelper separately verified; research/hardware leases free, capture closed, original rc5 unchanged.64files230698B exact private backup and remote Git verified. These readings are historical; recheck before dispatch.

V95 Chunk52 retained416pre-EOFframes with maxabs0<=1e-5 and15unmatchedEOFframes.6.947747s total includes UI/pacing/startup/cleanup, not a speed benchmark. Dedicated D1 recovery was observed. Source inspection finds generic Controller state/status remains unset by the recovery path after ERROR; that generic field was not independently recorded. Fix it before claiming whole-app recovery.

Follow COMPLETION_PLAN: coherent mode launcher/recovery, corrected full source/model/storage composition, visible controls, offline acceptance, release freeze, final documentation/backup. Do not rerun healthy suites for activity. Keep unavailable methods unavailable. No new download/training/enrollment/playback or requested speech; quiet/background checks establish function/resources only.

## Preservation and final handoff

PATHS_AND_BACKUPS lists exact locations. Keep failed attempts/raw evidence and immutable sources/admissions/policies/releases. Never manually alter closed ledgers or reset storage accounting. All host Python coordinators setCPU14 before reading. Use strict SSH checking and the existing key; no secrets in this pack. Before active app changes, verify backup/restore and exact boot/PID/start identities. Preserve display270 and personal data.

At deadline close research and pause automation. Desired final state is a verified field app idle with capture off. If required gates fail, leave a recoverable baseline and explicitly report incomplete delivery. Final version must replace this snapshot with actual active release, exact launcher/health/rollback commands, offline evidence, coverage gaps, final manifests/backups and a concise resume instruction.
