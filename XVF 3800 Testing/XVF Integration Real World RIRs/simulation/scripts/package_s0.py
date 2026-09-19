"""Assemble S0 findings and compact evidence only. Never begins a later phase."""
import argparse, collections, csv, hashlib, shutil, subprocess, sys, time, zipfile
from s0_common import *
from verify_s0 import verify

def run(report, started_utc):
    report=Path(report);run_id=report.name;cache=HashCache();started=datetime.fromisoformat(started_utc.replace('Z','+00:00'))
    c=read(report/'input_catalog.json');b=read(report/'baseline_manifest.json');resources=read(report/'resource_observations.json')
    datasets=read(report/'dataset_inventory_details.json');sources=read(report/'source_bindings.json');device=read(report/'xvf_read_only_inventory.json')
    original_metrics=sorted(report.glob('catalogue_attempt_*.json'))
    first=read(original_metrics[0]) if original_metrics else read(report/'catalogue_metrics.json')
    checks=verify(report);save(report/'validation_results.json',checks)
    readiness='READY_WITH_LIMITATIONS' if checks['passed'] else 'BLOCKED'
    rows=c['recordings'];smoke=b['smoke'];tele=smoke['session_summary']['telemetry']
    events=[json.loads(l) for l in (Path(tele['session_dir'])/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    clusters=sorted({e['payload'].get('anonymous_label') for e in events if e.get('event_type')=='speaker_decision'})
    runtime=(datetime.now(timezone.utc)-started).total_seconds()
    plan={'schema_version':'jp_s0_resource_plan_v1','observations':resources,
        'actual_cpu_differs_from_user_report':'5700X3D observed; 5800X3D was user-reported',
        'S1':{'scope':'12-record offline extraction qualification only; not executed by S0',
            'cpu_workers_initial':4,'cpu_workers_max_without_reprofile':4,'inner_threads':1,
            'environment':{'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'},
            'fft_workers':1,'ram_application_cap_gib':16,'minimum_available_ram_gib':16,
            'gpu_workers':0,'cuda_install_required':False,'scratch_root':str(SIM/'cache/S1'),
            'scratch_hard_cap_gib':5,'minimum_free_disk_gib_before_and_during_run':50,
            'immutable_inputs_read_in_place':True,'copy_corpus_or_archive':False,
            'heartbeat_sec':15,'max_in_flight_records':4,'resume_key':'canonical + excitation + sidecar + code + configuration SHA256',
            'estimated_local_input_bytes_12_canonical':12*350647*4*3,
            'runtime_forecast':'Unknown until S1 synthetic fixture and first pilot timing; no RIR extraction rate measured in S0'},
        'storage_policy_departure':'Pack 200 GiB cache / 15% reserve is provisional and cannot fit current C/G free space. Use a bounded 5 GiB S1 cap and 50 GiB absolute reserve; reconsider storage before S2/S4 expansion.',
        'future_gpu':'One owner only if existing compatible provider is qualified; leave at least 2 GiB VRAM. H2 currently CPU only.',
        'future_hardware':'One XVF owner; physical real-time replay is later HIL bottleneck; S0 has no HIL throughput result.',
        'excluded_storage':'D nearly full, F low-space HDD; no artifacts placed there',
        'deployment_target_only':{'CM5_ram_gb':2,'emmc_gb':32,'wireless':False,'qualified':False}}
    save(report/'resource_plan.json',plan)
    rights={'AMI':'Mixed local versions: Array1-* CC BY-NC-SA 2.5; newer annotation manual CC BY 4.0. Resolve per-file scope.',
        'CHiME_6':'Local root LICENSE states CC BY-SA 4.0; downstream use/scope not adjudicated.',
        'CMU_Arctic':'No licence document found in bounded local scan; rights UNKNOWN.',
        'HiFiTTS':'Local LICENSE states CC BY 4.0; README discusses written speaker consent for TTS sample selection.',
        'LibriSpeech':'Local split LICENSE files state CC BY 4.0.',
        'VOiCES':'No licence document found in bounded local scan; rights UNKNOWN.'}
    with (report/'dataset_inventory.csv').open(encoding='utf-8-sig',newline='') as f: inventory=list(csv.DictReader(f))
    for row in inventory:row['rights_status']=rights[row['dataset']]
    with (report/'dataset_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(inventory[0]));w.writeheader();w.writerows(inventory)
    failures=[
        {'stage':'discovery','status':'RECOVERED','detail':'Broad H2 smoke-WAV filename walk was stopped; existing session source_started receipt supplied the exact fixture path. Only the owned search process was interrupted.'},
        {'stage':'dataset_inventory','status':'RECOVERED','detail':'One atomic status-file replace hit transient Windows PermissionError. Added bounded rename retry; dataset inventory completed on rerun.'},
        {'stage':'xvf_read_only','status':'RECOVERED','detail':'First attempt used H2 Python 3.11 with recorder dependency directory built for bundled Python; numpy import failed before any device query. Retried using the documented recorder Python; 11 getters succeeded.'}]
    save(report/'execution_issues.json',failures)
    units=(report/'unit_tests.txt').read_text(encoding='utf-8-sig')
    unit_ok='Ran 8 tests' in units and '\nOK' in units
    save(report/'test_results.json',{'unit_tests_passed':8 if unit_ok else None,'unit_tests_status':'PASSED' if unit_ok else 'UNKNOWN','integration':checks,
        'historical_h2_tests_reused_as_new':False,'h2_offline_fixture_runs_this_S0':1})
    metrics=[
        {'name':'eligible_records','value':127,'unit':'records','definition':'Explicit audit allowlist length','population':'formal campaign'},
        {'name':'excluded_records','value':52,'unit':'records','definition':'Explicit exclusions; includes noise use','population':'179 indexed campaign runs'},
        {'name':'local_bound_records','value':c['counts']['bound'],'unit':'records','definition':'All required hashes, correction identity, central angle and WAV headers match','population':'127 eligible records'},
        {'name':'pilot_bound_records','value':12,'unit':'records','definition':'Unchanged proposed subset with local bindings','population':'12 proposed pilot records'},
        {'name':'fresh_catalogue_hash_bytes','value':first['bytes_hashed'],'unit':'bytes','definition':'Unique newly consumed canonical and required reference bytes read for SHA256','population':'initial S0 catalogue pass'},
        {'name':'first_catalogue_elapsed','value':first['elapsed_sec'],'unit':'seconds','definition':'First binding pass including output preparation','population':'127 records and references'},
        {'name':'h2_smoke_wall','value':smoke['wall_sec'],'unit':'seconds','definition':'Fresh CLI subprocess wall duration including startup; accelerated source is 4x paced','population':'one existing 8.8975625-second WAV'},
        {'name':'h2_dropped_frames','value':tele['audio_frames_dropped'],'unit':'frames','definition':'Runtime reported journal capture drops','population':'one offline smoke'},
        {'name':'task_wall_before_packaging','value':runtime,'unit':'seconds','definition':'From recorded task start through inventory, implementation and final evidence preparation; excludes final ZIP validation seconds','population':'S0 task'},
        {'name':'rir_extractions','value':0,'unit':'records','definition':'S0 does not extract or qualify RIRs','population':'127 eligible recordings'}]
    save(report/'metrics.json',{'metrics':metrics,'catalogue_cache_rerun':read(report/'catalogue_metrics.json'),
        'smoke_event_counts':smoke['event_counts'],'anonymous_labels_observed':clusters,'recovered_execution_issues':len(failures)})
    git_after={}
    for name,root in [('main',REPO),('nested',ROOT)]:
        result=subprocess.run(['git','-C',str(root),'status','--porcelain=v1'],capture_output=True,text=True)
        git_after[name]={'root':str(root),'status':result.stdout.splitlines()}
    save(report/'git_after.json',git_after)
    reporttext=f'''# S0 evidence handback — {run_id}

**{readiness}.** The 127 eligible recordings, their required extraction references, both distance corrections and the proposed 12-record pilot are bound locally. There are no critical RIR-input blockers in the inspected set. S1 may be requested next, but has not been started. RIR usability, precise direction, movement and CM5 operation remain unqualified.

## Authority and scope

The actual supplied workbook is `C:\\Users\\amiri\\Downloads\\XVF_Measurement_V5.docx`, SHA256 `c9a6badcd83065ae9f865de841c077f00668a480e1f0170c115c514e30a99db6` (1,321,341 bytes). Its title identifies master workbook Revision 5, 8 September 2026. This resolves the difference from the name in the pasted request; no older workbook was substituted. It was read as context and not rewritten. Its extracted text is included. Historical DOC sections describe plans where they differ from the audit/current instruction.

The existing intentionally nested reference pack remains at `{PACK}`. Sixteen consumed pack documents were checked against its SHA256SUMS; the sums file itself and the current user request were fingerprinted. Original pack, audit, recordings, metadata and Word documents were not edited. The current user request supersedes the old percentage wording. User-provided AGENTS instructions require this implementation's updated run README; no additional AGENTS file was found in the inspected project/H2 ancestors and source trees.

## Input and geometry contract

All 179 indexed records reconcile: **127 eligible formal REVIEW**, **52 excluded**. Eligibility comes only from `eligible_recordings.json`. The exclusions comprise 31 early pilots/diagnostics and 21 formal records (16 RETAKE, 5 INVESTIGATE); no excluded noise windows are admitted. The five historical PASS records are diagnostics, not eligible formal captures.

The initial bounded pass hashed {first['unique_files_hashed']:,} unique consumed files ({first['bytes_hashed']:,} bytes) in {first['elapsed_sec']:.2f} s. It verified canonical MIC0–MIC3 files, the exact archived excitation, parent SHA manifests, request/result/trial metadata, playback/timing and capture configuration/gain/identity/quality sidecars. It did not rehash every nested manifest or repeat packed carrier decoding and transport continuity analysis. The archive capture audit remains the authority for those checks. A subsequent catalogue formatting/cache check reused all 1,670 receipts and hashed zero source bytes.

Each canonical WAV header matches four channels, 16 kHz, PCM24 and 350,647 frames (21.9154375 s). Original capture domain remains Category 3, microphone gain 10, SYS_DELAY −32 (a 32-sample microphone delay). All inspected playback summaries retain separate Realtek playback/capture clocks and −6 dB software gain. Digital continuity is not evidence of a shared acoustic clock.

Both corrected rows retain original 100 m and effective 1.00 m. Each correction is checked against exact run ID, recorded UTC, parent-manifest hash and original request value, then assigned once rather than rescaled. The rows are flat `JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R05` and upright `JPXVF_P1_R02_T01_D01_S02_UPR_NAT_CU_R05`, low table / Opening Behind Listener / +20°. Effective distances are **0.46–4.07 m**, all positive and <=5 m; physical distances are still operator-reported, not independently surveyed.

`user_context_overlay.v2.json` records **approximately ±4–5 degrees or less**, with a conservative 5° half-width, authority `user_clarification`, and `independently_calibrated=false`. Central labels/signs are unchanged. Circular intervals wrap correctly at ±180°. The old percentage/denominator fields survive only in a named superseded-history object. ±10°/±20° are labelled future artificial robustness tests, never assumed measurement uncertainty. These are placement/label estimates, not DoA performance, a standard deviation, confidence interval or hard algorithm-error bound. Native radians remain distinct from laboratory degrees and linear-array front/rear ambiguity remains.

Prior sign evidence is carried forward: 109 informative sweep-side checks supported the entered side; 18 near-axis cases were inconclusive. This S0 did not rerun that acoustic analysis or claim precise angular calibration. Unknown XYZ, heights, yaw, pitch, roll and photographs remain unknown. User-reported source-facing-tablet context and the unresolved Carlton Library alias are retained without changing NAT tokens or inventing yaw.

All 12 proposed pilot IDs and their hashes match the allowlist; order and difficult/noisy selections are retained. There are no unchanged same-condition repeats; Rxx suffixes, pose changes and obstruction changes are not repeatability evidence. All records remain `rir_qualification=NOT_EXTRACTED`, `qualified_rir_available=false`, `simulation_ready=false`.

No unmanifested newer files were found in the eligible records' 03_derived/04_hil_exports/05_analysis directories. A filename inventory of project validation/tmp/planning found only existing packing fixtures, not qualified RIR outputs. This is a project-scoped search, not a claim about all files on the desktop. Archived 03_derived microphone copies and analysis placeholders are not RIRs.

## Actual H2 baseline and one fresh smoke

Main repository: commit `830009cc9fa9ef996e4668f53441c2b858ce6b42`, branch `codex/edge-component-expansion`. No tracked H2 edits were present initially or made by S0. Two pre-existing untracked XVF directories remain. The measurement folder is also a nested unborn Git repository on `master`, with its existing contents untracked; S0 adds `simulation/`. No commit, add, push, stash, reset or history operation was performed. Before/after receipts and source hashes are included.

The established launcher selects `{EDGE_PYTHON}` (Python {b['python_version']}). Active runtime is Sherpa-ONNX {b['versions']['sherpa-onnx']} and ONNX Runtime {b['versions']['onnxruntime']}; available ORT providers are {', '.join(b['onnxruntime_available_providers'])}. Active inference uses CPU. No model, threshold, provider or global dependency was changed.

| Active component | SHA256 |
| --- | --- |
'''
    for a in b['assets']:reporttext+=f"| {a['component_id']} | `{a['sha256']}` |\n"
    reporttext+=f'''
All eight actual assets passed the unmodified runtime's checksum validation before this fresh inference. Configuration and model source/export manifests are separately fingerprinted in `baseline_manifest.json`. Export provenance points to ReDimNet `b2-vox2-lm.pt` and Pyannote segmentation-3.0; no resolver-selected newly fine-tuned path was identified. The user-reported earlier tuning benefit is preserved as context, not independently established checkpoint ancestry. S0 retained the active bytes; it did not revert anything based on older no-training text.

Audio is float32 mono at 16 kHz after existing channel averaging/resampling, then PCM16 journal storage with independent consumer cursors. This 16 kHz mono fixture did not exercise resampling. Sherpa uses 80-dimensional features and greedy decoding; token and punctuation BPE files are hash-bound. Pyannote uses 10 s windows / 0.75 s hop and 0.46/0.45 onset/offset; ReDimNet uses 0.5 s / 0.25 s windows and normalized 192-dimensional vectors. Exact endpoint/thread parameters are in the manifest.

Anonymous memory is a session-local normalized running centroid, cosine threshold 0.35. Enrollment uses the same ReDimNet backend, checkpoint hash and vector-shape gate. Names require score 0.5128856897, margin 0.03 and 2 s evidence; tentative naming can occur before the evidence threshold. Evidence is elapsed time since the cluster first appeared, not calibrated independent speech duration. There was one existing profile metadata/vector pair; personal names, vectors and audio were not exported or changed. The smoke used a new empty profile directory through the existing EDGE_SPEECH_DATA_ROOT override.

Exact command (working directory `{H2}`):

```powershell
$env:EDGE_SPEECH_DATA_ROOT = '{report / 'smoke_data'}'
$env:PYTHONDONTWRITEBYTECODE = '1'
& '{EDGE_PYTHON}' -m app.edge_speech_pipeline file '{smoke['fixture']['path']}' --accelerated
```

The existing 8.8975625-second mono WAV completed in **{smoke['wall_sec']:.3f} s subprocess wall time**; runtime telemetry reports {tele['elapsed_wall_sec']:.3f} s. `--accelerated` feeds the source at four times real time; these times are not pure model compute benchmarks. Both consumers reached 8.8975625 s, dropped frames and residual cursor lag were zero. The speaker analysis stops at 8.75 s, leaving a reported 0.1475625 s short tail. Fresh events: 21 partials, one final transcript, 11 segmentation events, 27 speaker decisions. Learned punctuation completed, with one terminal-period fallback and zero punctuation inference failures. The expected repeated phrase was emitted; no corpus WER/DER was calculated.

The tracker produced {len(clusters)} anonymous cluster labels on this short concatenated fixture. Completion does not establish correct speaker count or identity continuity. Enrollment/name accuracy, GUI behavior, live capture, XVF audio effects, spatial fusion and CM5 performance were not exercised. Historical test counts were not reported as newly passed.

## Local datasets and identity/rights limits

Counts below are current index counts, not a recursive validation of every audio file. The first five distinct paths per indexed audio-path field were checked and existed. Three sample enrollment/probe pairs for each promising clean corpus were bound to local hashes; no embeddings were calculated and no split was frozen.

| Dataset | Indexed recordings / utterances | Indexed speaker keys | Clean-source use |
| --- | --- | --- | --- |
| CMU Arctic | 15,583 / 15,583 | 18 | All indexed utterances are candidates; 18 IDs have multiple distinct files |
| LibriSpeech | 292,367 / 292,367 | 2,484 total | 137,876 clean rows; 1,252 clean speaker IDs with separate files |
| HiFiTTS | 323,978 / 323,978 | 10 total | 126,439 clean rows; only 3 clean reader IDs with separate files |
| AMI | 2,034 / 834,429 | 190 | Already recorded room/meeting audio; not dry speech by default |
| CHiME-6 | 540 / 98,432 | 48 recording-table IDs | Real conversations; not clean speech or noise-only by default |
| VOiCES | 19,200 / 19,200 | 300 | Deduplicate source branch; distant branch already has acoustics |

CMU speaker_id/speaker_code, LibriSpeech speaker_id/chapter/utterance and HiFiTTS reader_id permit within-corpus scene identity separation and disjoint enrollment/probe files. Namespacing prevents identifier collisions but does not prove different humans across corpora. LibriSpeech, HiFiTTS and VOiCES source provenance can overlap; reserve identities and deduplicate utterances before combining them. CMU's README logs 20 extra WAVs lacking per-speaker transcripts; these are outside the emitted normalized transcript set. HiFiTTS's large historical warning count concerns metadata gaps and must not be equated automatically with corrupted audio.

AMI has a 1,207,406-row word-timing table. The other five indexes have no word-timing table; utterance start/end fields do not establish word times. AMI has 742,873 nonempty indexed transcript rows and CHiME-6 98,431; the three clean candidates have nonempty text for all emitted rows. Full path/hash/schema/group details are in `dataset_inventory_details.json`.

Local licence statements: LibriSpeech and HiFiTTS say CC BY 4.0; CHiME-6 says CC BY-SA 4.0. AMI contains older CC BY-NC-SA 2.5 audio/annotation copies and a newer CC BY 4.0 annotation manual; per-file applicability must be resolved. No CMU Arctic or VOiCES licence was found in the bounded local scan, so their rights are UNKNOWN here. These observations are not a clearance decision for later redistribution or voice synthesis. HiFiTTS's local README also discusses speaker consent for TTS sample selection.

No independently qualified noise-only source bank was established. Campaign pre-excitation windows must first pass S1 timing/stationarity/contamination checks; excluded recordings remain prohibited. AMI/CHiME/VOiCES mixtures are not automatically ambience. Common Voice and MIT RIR raw roots exist but are not in this six-dataset normalized inventory and were not recursively inventoried.

## Resources and connected XVF

Observed CPU is **Ryzen 7 5700X3D**, 8 cores / 16 logical processors; this corrects the reported 5800X3D. RAM visible is {resources['memory']['TotalVisibleMemorySize']/1024**2:.2f} GiB, with {resources['memory']['FreePhysicalMemory']/1024**2:.2f} GiB available at snapshot. RTX 3080 has 10,240 MiB VRAM, about 7,032 MiB free at snapshot, driver 610.62. Existing Conda paths are recorded; base has parquet tooling and the H2 environment has the needed CPU inference packages. No CUDA installation was attempted.

| Drive | Volume | Free GiB at snapshot |
| --- | --- | --- |
'''
    for d in resources['drives']:reporttext+=f"| {d['DeviceID']} | {d['VolumeName']} | {d['FreeSpace']/1024**3:.2f} |\n"
    reporttext+=f'''
Use C: for the small S1 pilot with inputs read in place, four CPU workers, one inner BLAS/FFT thread, 16 GiB application RAM cap and at least 16 GiB available RAM. Cap temporary cache at 5 GiB and stop before free disk drops below 50 GiB. G: is the second 2 TB SSD, but it also lacks capacity for the proposed 200 GiB broad cache. D: is effectively full; F: is a low-space HDD. This deliberately replaces the pack's provisional cache/reserve proposal for the bounded pilot; storage must be reconsidered before larger stages. No S1 extraction ETA is justified until its first cases are timed.

Read-only control reused `measurement_app.core.Control`, its existing Windows byte-range hardware lock and `tools/xvf321/binary/host_v3.0.0/win32/xvf_host.exe`; raw getter receipts are included. Eleven getter calls succeeded with no setters, streams, reset or flash. Current board: firmware 3.2.1 `ua-io48-lin`, array type 1, four microphones at native x positions −0.04995, −0.01665, +0.01665, +0.04995 m; gain 10, reference gain 1.5, delay −32, packed input 0, DAC DSP enable 0. **Current USB_BIT_DEPTH is 16/16**, distinct from the archived 24-bit capture state. S3 must explicitly qualify the desktop format/configuration later; S0 left it untouched.

Fresh WASAPI endpoint observations identify output index 22 and input index 25, each with two-channel capacity and default 48 kHz. These are inventory observations, not permanent indexes or a negotiated stream format. Other APIs expose different host API IDs/defaults. Re-enumerate at S3 and bind by device/API identity. Initial read-only probing with the H2 environment hit an incompatible recorder dependency import before any device command; the established bundled recorder Python resolved it without installation.

## Validation, execution issues and handoff boundary

Eight fresh failure-oriented unit checks passed (hash mismatch/missing file, cache invalidation, path escape, duplicate manifest, correction identity/idempotence, invalid distance and angular wrap). {checks['passed_checks']}/{checks['total_checks']} integration contract checks passed. The compact ZIP is independently checked for CRC, file inventory, all listed SHA256 hashes and forbidden heavy artifacts after assembly.

Task wall time through this evidence preparation: **{runtime/60:.2f} min**; catalogue and smoke timings above isolate actual automated work. `package_receipt.json` records final elapsed time through ZIP validation. Most time was bounded inspection, implementation and evidence review, not numerical processing. One broad fixture-discovery search was stopped and replaced by its known session receipt; one transient report-file lock and one wrong-runtime import were recovered. Details/earlier attempt receipts are preserved. No unrelated Python process was terminated; the device lock was released. No extraction, denoising, source EQ, scene synthesis, HIL, cue fusion, training or deployment ran.

No user decision is required to resolve an S1 input blocker. The next prompt should authorize only the unchanged 12-record timing/RIR/noise pilot. Independently calibrated angles/distances, missing geometry, no same-condition repeats, noisy Loeb responses and separate acoustic clocks constrain interpretation but do not prevent trying that bounded method. Dataset rights/splits, active checkpoint training ancestry, current USB width, native-to-lab mapping, enrolled identity accuracy, motion evidence and CM5 qualification affect later stages and remain explicit limitations.

Read `NEXT_PHASE_INPUTS.md` for exact accepted artifact paths/hashes and the S1 stopping boundary. S0 stops after this package.
'''
    (report/'S0_REPORT.md').write_text(reporttext,encoding='utf-8')
    (report/'PHASE_SUMMARY.md').write_text(reporttext,encoding='utf-8')
    (SIM/'CONTEXT.md').write_text(f'''# Active post-measurement context

Latest completed stage: S0, run `{run_id}`, {readiness}. See `reports/S0/{run_id}/S0_REPORT.md` and `NEXT_PHASE_INPUTS.md`. S1 has not started.

Authority order: current user corrections; recorded audit facts; matching XMOS interface documentation; current V5 workbook for goals/plans. Workbook resolved to `C:\\Users\\amiri\\Downloads\\XVF_Measurement_V5.docx`, SHA256 c9a6badcd83065ae9f865de841c077f00668a480e1f0170c115c514e30a99db6.

Use only the explicit 127 formal REVIEW allowlist and preserve 52 exclusions including their noise windows. Both original 100 m entries are bound by exact identity to effective 1.00 m. Never rescale the effective field twice.

Active angle context is `config/user_context_overlay.v2.json`: approximately ±4–5 degrees or less, conservative half-width 5 degrees, user_clarification, independently_calibrated=false. This replaces the percentage/denominator question. Preserve signed centers, native radians separately, circular wrap and linear front/rear ambiguity. No precise angle ground truth is established. ±10/20 are only possible future artificial robustness tests.

Preserve user-reported source-facing-tablet context, unresolved library alias, NAT tokens and unknown XYZ/height/yaw/photos. Do not fabricate geometry or enforce delays to match labels. Preserve Category 3 gain 10/delay −32 and separate Realtek acoustic clock. No qualified RIR exists in the audited/inspected project outputs.

Keep the current eight H2 assets exactly as bound. Active model ancestry and user-reported earlier tuning benefits are different kinds of evidence; do not swap to parent weights based on older prose. Current board read-only state is USB 16/16; no setters were sent. Physical format and HIL qualification belong to S3.

S1 recommended resources: 4 workers, inner threads 1, CPU only, 16 GiB RAM budget, 5 GiB scratch cap, >=50 GiB free disk. Larger cache plans do not fit observed C/G capacity. No automatic later-phase execution.
''',encoding='utf-8')
    (SIM/'DECISIONS.md').write_text(f'''# Decision log

2026-09-08 / S0 {run_id}

1. User clarification supersedes ±4–5% with approximately ±4–5 degrees or less. Applied conservative half-width 5° as a versioned context overlay; no raw central angle edit or calibration claim.
2. Bind the supplied current V5 at its actual attached filename, retaining its hash and extracted context. Keep the reference pack and prior audit immutable.
3. Both distance corrections assign 1.00 m only after exact original-record and manifest checks. Original 100 m evidence remains.
4. Preserve supplied 12-case pilot including difficult conditions. All 127 allowlisted inputs remain captured-valid / locally-bound / RIR-unqualified / simulation-not-ready.
5. Preserve current H2 assets and thresholds. One offline empty-gallery smoke completed; enrolled names and spatial integration remain untested.
6. Desktop CPU is 5700X3D. Replace provisional broad cache plan with bounded 5 GiB S1 scratch and 50 GiB free-space floor; no broad storage action.
7. Current physical board is firmware 3.2.1, USB 16/16. Inventory only; leave settings unchanged until S3 authorization.
8. READY_WITH_LIMITATIONS for a later S1 prompt. Stop after S0 packaging.
''',encoding='utf-8')
    # Small source/context snapshots make review possible without shipping vendors or weights.
    evidence=report/'evidence';(evidence/'h2_source').mkdir(parents=True,exist_ok=True);(evidence/'reference_context').mkdir(exist_ok=True)
    for source in b['source_bindings']:
        path=Path(source['path'])
        if path.is_file():shutil.copyfile(path,evidence/'h2_source'/path.name)
    for rel in ['phase_briefs/S0.md','phase_briefs/S1.md','RIR_AND_NOISE_PROTOCOL.md','CONTEXT.md',
                'reference/audit/audit_summary.json','reference/audit/CHATGPT_SIMULATION_HANDOFF.md','planning/proposed_rir_pilot.json']:
        shutil.copyfile(PACK/rel,evidence/'reference_context'/Path(rel).name)
    vendor=[]
    for name in ['audio_cmds.yaml','application_cmds.yaml','aec_cmds.yaml']:
        path=ROOT/'tools/xvf321/source/sources/app_xvf3800/autogeneration/yaml_files/control_commands'/name
        vendor.append(cache.bind(path))
    save(report/'xvf_interface_reference_bindings.json',vendor)
    accepted=[cache.bind(report/n) for n in ['input_catalog.json','resolved_pilot.json','metadata_corrections.json','user_context_overlay.v2.json','baseline_manifest.json','resource_plan.json']]
    nexttext=f'''# Accepted S0 inputs for a separately requested S1

S0 status: {readiness}. No critical RIR-input blockers. Authorize only the supplied 12-record timing/RIR/noise qualification pilot; stop before S2 library expansion or S3 hardware work.

| Artifact (absolute local path) | SHA256 |
| --- | --- |
'''
    for a in accepted:nexttext+=f"| `{a['path']}` | `{a['sha256']}` |\n"
    nexttext+='''
The catalogue contains exact local canonical audio, original excitation and needed sidecar paths with saved/observed hashes for every allowed record. The pilot is unchanged and all 12 rows are BOUND. Use its four-channel 16 kHz PCM24 files and the exact archived 48 kHz PCM16 excitation with SHA256 `cba5b09d4d3963d508340711210804d2dd80cf62741a60a2544120e60acbf488`; apply recorded −6 dB playback scalar once. Do not regenerate or replace the excitation with a 16 kHz variant.

S1 should test the extractor first on inexpensive known-FIR synthetic fixtures with known delay/gain/clock mismatch/noise; then run only the 12 selected measurements. Compare common no-drift and justified clock-mapping variants, preserving all intermicrophone timing and levels. Use the same four-channel mapping/taper, do not individually align microphones, force label agreement, remove source EQ, or reinterpret Category 3 gain/delay. Preserve diagnostic untrimmed estimates and uncertainty. A reconstruction residual is internal consistency, not independent acoustic proof.

Select noise windows using acoustic timing evidence; post-sweep decay and end markers are not automatically noise-only. Assess noisy Loeb cases with explicit limited-use/failure states; do not replace them or require every case to become full-band. Preserve all excluded records/noise exclusions. Define usable band/tail, alignment residual, common clock uncertainty, six mic delays, gain ratios, pre-arrival ringing, reconstruction residual and decay/noise limits. Thresholds/policy should be justified from this pilot before expansion.

Use ±5° only as user-estimated label half-width, preserve centers and signs, and keep native radians separate. No independent exact angle/distance, XYZ, yaw, heights, photos, unchanged repeats or recorded IMU exist. These are limitations, not fields to synthesize.

Use four CPU workers at most, one inner thread, a 16 GiB application budget, 5 GiB scratch cap and 50 GiB minimum free disk. Read inputs in place. Reuse unchanged hash receipts with stat checks. Report item progress/elapsed/throughput and 15-second heartbeat; estimate runtime only after measuring the first fixtures/cases.

No additional user input is necessary for the RIR-input binding. The next prompt must choose/authorize the S1-only implementation scope and require a compact report/plots/metrics/manifest/next-input handback. Later concerns (not S1 input blockers): dataset licence/identity split review; active checkpoint training ancestry; anonymous over-clustering and enrollment validation; desktop USB currently 16/16 and unqualified injection; native-to-lab calibration; motion evidence; CM5 deployment.

Current V5 workbook: C:\\Users\\amiri\\Downloads\\XVF_Measurement_V5.docx, SHA256 c9a6badcd83065ae9f865de841c077f00668a480e1f0170c115c514e30a99db6. Matching copied phase/context references are under evidence/reference_context; they guide a future request and do not themselves authorize execution.
'''
    (report/'NEXT_PHASE_INPUTS.md').write_text(nexttext,encoding='utf-8')
    commands=[f'"{BASE_PYTHON}" "{SIM / "scripts/s0_catalog.py"}" --report "{report}" --workbook "C:\\Users\\amiri\\Downloads\\XVF_Measurement_V5.docx"',
        f'"{EDGE_PYTHON}" "{SIM / "scripts/s0_baseline.py"}" --report "{report}"',
        f'"{BASE_PYTHON}" "{SIM / "scripts/s0_datasets.py"}" --report "{report}"',
        f'"C:\\Users\\amiri\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" -X utf8 "{SIM / "scripts/s0_device.py"}" --report "{report}"',
        f'"{BASE_PYTHON}" -m unittest discover -s "{SIM / "tests"}" -v',
        f'"{BASE_PYTHON}" "{SIM / "scripts/package_s0.py"}" --report "{report}" --started-utc "{started_utc}"']
    save(report/'run_manifest.json',{'schema_version':'jp_phase_result_v1','stage_id':'S0','run_id':run_id,'status':'COMPLETE' if checks['passed'] else 'FAILED',
        'readiness':readiness,'started_utc':started_utc,'finished_utc':now(),'actual_commands':commands,
        'command_notes':'Initial Git/resources were collected with equivalent PowerShell statements before code creation; capture_inventory.ps1 is their reusable equivalent. Catalogue executed twice, second reused hashes; device had one failed pre-query environment attempt. See execution_issues.json.',
        'code_commit':read(report/'git_before.json')['main']['commit'],'inputs':[{'path':x['path'],'sha256':x['sha256']} for x in sources],
        'metrics':metrics,'failures':failures,'resources':plan['S1'],'artifacts':accepted,
        'next_phase':{'ready':checks['passed'],'stage':'S1','automatically_started':False,'unresolved_questions':[
            'Extraction clock policy/useful band/tail must be selected from pilot evidence, not guessed in S0',
            'Independent geometry/angle calibration and unchanged repeatability remain unavailable'],
            'accepted_artifact_paths':[x['path'] for x in accepted]}})
    save(report/'status.json',{'stage':'S0','status':'COMPLETE' if checks['passed'] else 'FAILED','readiness':readiness,'run_id':run_id,
        'updated_utc':now(),'items_completed':127,'items_total':127,'failed_bindings':127-c['counts']['bound'],
        'next_stage_started':False,'elapsed_sec_before_zip':runtime})
    (report/'CHANGE_SUMMARY.md').write_text('''# S0 local changes

Added simulation/scripts (catalogue, baseline smoke wrapper, dataset inventory, read-only device wrapper, receipts, validation and packaging), eight focused tests, README, active context/decision log, angle overlay and this evidence run. No tracked H2 code or model edits. Original acquisition/Word/reference-pack files remain in place. Existing untracked measurement directories and nested unborn repository were preserved. Git status before/after is included. Local cache receipts and the H2 smoke journal stay outside the ZIP.

No automatic commit or push. No later phase has started.
''',encoding='utf-8')
    package=SIM/'handoffs'/f'S0_CHATGPT_HANDOFF_{run_id}.zip';members=[]
    for folder in [report,SIM/'scripts',SIM/'tests',SIM/'config']:
        for p in folder.rglob('*'):
            if p.is_file() and not any(part in ['__pycache__','smoke_data'] for part in p.parts) and p.suffix not in ['.pyc','.tmp'] and p.name not in ['package_receipt.json','package_validation.json']:
                members.append(p)
    members += [SIM/'README.md',SIM/'CONTEXT.md',SIM/'DECISIONS.md']
    filelist=[]
    for p in sorted(set(members),key=lambda x:x.as_posix()):
        binding=cache.bind(p)
        filelist.append({'archive_path':p.relative_to(SIM).as_posix(),'bytes':binding['bytes'],'sha256':binding['sha256']})
    listing=(json.dumps(filelist,indent=2)+'\n').encode()
    sums=''.join(x['sha256']+'  '+x['archive_path']+'\n' for x in filelist)
    sums+=hashlib.sha256(listing).hexdigest()+'  FILE_LIST_AND_HASHES.json\n'
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(set(members),key=lambda x:x.as_posix()):z.write(p,p.relative_to(SIM).as_posix())
        z.writestr('FILE_LIST_AND_HASHES.json',listing);z.writestr('SHA256SUMS.txt',sums)
    package_checks=verify(report,package);save(report/'package_validation.json',package_checks)
    if not package_checks['passed']:raise RuntimeError('Package verification failed')
    receipt={'path':str(package),'sha256':cache.bind(package)['sha256'],'bytes':package.stat().st_size,
        'file_count':len(filelist)+2,'validation':package_checks,'completed_utc':now(),
        'actual_task_wall_sec_through_package_validation':(datetime.now(timezone.utc)-started).total_seconds(),
        'scope':'Package receipt is external to avoid self-referential hashes; internal FILE_LIST_AND_HASHES and SHA256SUMS cover payload.'}
    save(report/'package_receipt.json',receipt);save(package.with_suffix('.receipt.json'),receipt);cache.flush()
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--started-utc',required=True)
    a=p.parse_args();run(a.report,a.started_utc)
