# Five prepared continuous saved-file sessions

Purpose: run the five already prepared O0 continuous sessions serially, using their unchanged original commands: C065, C067, C088, C091 on epoch4 fastV2, then original S6B B36 on its continuous fastV1 wrapper. Each uses the existing 1827.426625-second, 29,238,826-sample composition. This is execution preparation, not selection of operating profiles, hardware qualification or a new experiment.

Inputs are the five exact manifest path/SHA pairs embedded in s6c_long_dispatch_v1.py, the held original helpers and maintained READMEs, a fresh queue preparation output, and a later root authority binding that exact queue and this dispatcher. The source uses held paced dispatcher V3 in a private namespace. Its original subprocess launch, PID/creation checks, no-kill behavior, immutable heartbeats, deadline/stop conditions and immutable final outcome stay unchanged. The only run-body changes are output/schema/README names, the original helper-specific quiet payload, and one pre-launch full-source time/fresh-namespace check. Original modules/globals are never patched. No original manifest is rewritten.

The inherited `cells` counter counts one continuous session per item here: five requested sessions, not five canonical scenes. Source duration sums to 9127.133125 seconds across five separate sessions. Runs are not independent source captures; each uses the same composition and fixed condition. Scientific diagnostics, full native source verification and final inventory remain separate.

## Inputs, outputs and boundaries

Preparation reads only the exact small manifests and code/README files. It verifies fixed order, O0 routes, original source/timeout/reserve fields, and absence of prior invocation/native output. It creates QUEUE.json and PREPARATION.json in the supplied fresh directory; it never invokes model, PCM, storage-scanner or native admission routines. The exact original helper performs its own full input/asset/resource admission when root later launches it.

Root's separate JSON authority must have schema `s6c-serial-long-authority.v1`, status `AUTHORIZED_SERIAL_QUIET_LONG`, exact `queue` and `dispatcher` path/bytes/SHA bindings, both `all_other_model_hil_work_stopped` and `all_heavy_analysis_stopped` true, and an aware `expires_utc` at or before 2026-09-13T11:35:40Z. These are required inputs; preparation does not supply or manufacture this authority.

The runner writes REPORT/serial_long_dispatcher/five_prepared_long_v1 with admission, exact subprocess launch, per-item root-derived quiet admission, parent exit and transition proof, immutable heartbeat snapshots and final RESULT.json. Run is fresh-only: any prior invocation or native attempt stops execution and requires root resolution. A nonzero helper exit, incomplete native result, live/unknown owner, unverified lease, observer error or other IO error stops the queue before another session. The dispatcher never kills a process, removes a lease or repairs an original outcome.

Original C minimum start reserve is source + 600-second lane drain + 180 seconds; its 7200-second bound and finalization stay in the original wrapper. Original B36 minimum reserve is source + 120-second execution margin + 25-second owned cleanup + 60 seconds; its original worker remains exact. The stage deadline and existing closure reserve are unchanged. The dispatcher may stop with a still-live child after a deadline/IO failure; root must resolve the exact recorded PID/creation before anything else starts.

After each helper exits zero, transition admission checks its exact original admission/outcome/closure and released lease byte lineage; original native result/source/profile metadata; current recorded owners; and a successful final observer record. C uses its actual paired journal declarations and finalization metadata. B36 uses the exact original validate_worker_result function extracted from its pinned source, plus its original continuous child outcome and closed-descendant list. Journal bytes/hashes remain declarations at this boundary; no audio/events are reread. Broader payload/diagnostic/inventory admission remains separate.

To locate C's run observer record without rereading prior observations, the dispatcher saves a bounded filename-only OBSERVER_BASELINE.json before launching that session; completion requires exactly one newly emitted record. B36 uses its own prepared namespace. Old baseline files are not read as observations. Root must keep competing model/analysis work stopped during the authority interval.

Heartbeats reuse V3's exclusive-write, flush/fsync immutable layout `heartbeats/000/HEARTBEAT_00001.json`: 20 blocks of at most 1000 files, 20,000 total, 16KiB per file, one about every15 seconds. Readers inspect the newest block and highest complete JSON; older snapshots are never replaced. Do not poll original mutable wrapper heartbeat files, which remain under their original IO semantics.

## Commands

Use the existing EDGE interpreter directly; no Conda activation/install or altered environment is required. Source tests are model-free and are covered by this README. Every test/preparation output must be fresh.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$edgePy = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edgePy -B test_s6c_long_dispatch_v1.py --output '..\reports\S6C\20260910T123540Z\serial_long_dispatcher\source_checks_v1'
# Metadata only, after source review:
& $edgePy -B s6c_long_dispatch_v1.py prepare --output '..\reports\S6C\20260910T123540Z\serial_long_dispatcher\preparation_v1'
# Only root launches after independent acceptance and an exact separate quiet authority:
& $edgePy -B s6c_long_dispatch_v1.py run --queue 'ABSOLUTE_QUEUE.json' 'EXACT_QUEUE_SHA256' --authority 'ABSOLUTE_ROOT_AUTHORITY.json' 'EXACT_AUTHORITY_SHA256'
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_long_dispatch_v1.py --output "..\reports\S6C\20260910T123540Z\serial_long_dispatcher\source_checks_v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_long_dispatch_v1.py prepare --output "..\reports\S6C\20260910T123540Z\serial_long_dispatcher\preparation_v1"
rem Root only, with actual reviewed input paths and hashes:
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_long_dispatch_v1.py run --queue "ABSOLUTE_QUEUE.json" "EXACT_QUEUE_SHA256" --authority "ABSOLUTE_ROOT_AUTHORITY.json" "EXACT_AUTHORITY_SHA256"
```

The placeholders are not authorizations. This source and its test must stay bound to this maintained README. Tests use private synthetic closures and original small prepared metadata, never real session output or models.

The first two private fixture attempts stopped before receipt publication: a test variable reused a temporary path name, then the synthetic B36 object omitted a required original instrumentation flag. Both test-only versions and failure notes are preserved under STAGING/long_dispatch. These were not native/session failures. A subsequent source reread before first use corrected the B36 observer expectation to its actual long status NATIVE_COMPLETE (paced wrappers use COMPLETE), and made the original child admission/argv and lease kind checks explicit. The held prior draft/test/README/40-check receipt are preserved under before_original_long_schema_repair_v1; an actual original shared-execute roundtrip with a stub native result verifies this schema without launching anything.
