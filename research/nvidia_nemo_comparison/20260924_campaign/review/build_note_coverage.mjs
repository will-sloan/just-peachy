// Flat research catalogue; see README.md for purpose, inputs, outputs and run steps.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { Workbook } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const campaign = path.dirname(here);
const relativeCampaign = 'research/nvidia_nemo_comparison/20260924_campaign/';
const local = 'G:/Just_Peachy_N1/20260924_campaign/local/';
const fullSuite = local + 'checks/full-suite-v1/tests.json';
const coreSuite = local + 'checks/final-core-01/tests.json';
const base = 'prototype/tests/';
const rows = [];
const add = (section, item, nature, existing, action, status, evidence, limitation='Source/interface checks do not establish acoustic accuracy or physical hardware behavior.') =>
  rows.push([String(section), item, nature, existing, action, status, evidence, limitation]);
const ran = (file, core=false) => `${base}${file}; ${core ? coreSuite : fullSuite}`;
const cp = file => relativeCampaign + file;

add(1,'Fixed live caption region','OBSERVATION_AND_REQUEST','Compact captions existed; active content shared scrolling history','Added anchored 184px live pane and separate transcript history','ACTUALLY_RUN',ran('test_n1_frontend.py',true));
add(1,'Append or revise stable suffix','REQUEST','Earlier rows retained marks but active partial updates were not separately anchored','ActiveCaptionPane updates changed suffix and retains unchanged marks','ACTUALLY_RUN',ran('test_n1_frontend.py',true));
add(1,'Smaller selectable caption font','REQUEST','Compact/Normal/Large/Extra large choices already implemented','Retained 21/25/31/37px caption sizes and Compact default','ACTUALLY_RUN',`prototype/config/ui.json; ${ran('test_caption_display.py')}`);
add(1,'Tighter default fonts and gaps','REQUEST','Compact spacing and 17px body/14px small font existed','Preserved compact gaps while adding common backend control and anchored pane','ACTUALLY_RUN',`prototype/app/ui.py; ${ran('test_caption_display.py')}`);
add(1,'Bounded pending names','OBSERVATION_AND_REQUEST','IdentityLabels already bounds pending state and handles segment replacement','Verified bounds survive jitter and active-pane presentation','ACTUALLY_RUN',ran('test_caption_display.py'));
add(1,'Developer scores and honest legends','REQUEST','Score/margin diagnostic page existed','Retained raw cosine, threshold and margin; no calibrated percentage invented','ACTUALLY_RUN',ran('test_roster_ui.py'));
add(1,'Active navigation highlight','REQUEST','Existing navigation context highlights current section','Preserved active navigation across caption/people/settings routes','ACTUALLY_RUN',ran('test_caption_display.py'));
add(1,'Conditional full-caption rescue','REQUEST','Show all recovery existed where display filtering applies','Retained reachable rescue only in filtering context without a permanent large strip','ACTUALLY_RUN',ran('test_n1_frontend.py',true));
add(1,'480x800 portrait and independent comfort zoom','EXPLICIT_N1_REQUIREMENT','Toolkit layout and comfort zoom existed','Verified 480x800 logical client and zoom layouts in private desktop','ACTUALLY_RUN',ran('test_n1_frontend.py',true),'Private-desktop rendering is Windows evidence. Pi panel, DPI/controller and touch hardware are not tested.');

add(2,'Mode naming and same logical modes','REQUEST','Roster/transcription/open-conversation/spatial modes implemented','Kept logical modes independent of new backend selector','ACTUALLY_RUN',ran('test_roster_ui.py'));
add(2,'All enrolled versus selected enrolled roster','REQUEST','UUID-based matching rosters already implemented','Verified unselected best-match identity excluded; rename preserves UUID selection','ACTUALLY_RUN',ran('test_roster_policy.py'));
add(2,'Closed roster versus filtering','REQUEST_AND_ASSUMPTION','Closed assumptions and display filtering were separate operations','Verified forced closed labels remain assumptions and filtering leaves matching roster unchanged','ACTUALLY_RUN',ran('test_roster_policy.py'),'Closed membership never certifies recognition or adaptation data.');
add(2,'Generic Unknown default','REQUEST','Constant Unknown already distinct from numbered display','Retained generic Unknown behavior and default false numbered preference','ACTUALLY_RUN',ran('test_roster_ui.py'));
add(2,'Numbered Unknown in Advanced','REQUEST','Numbered modes already restricted to Advanced','Verified legacy numbered toggle cannot override Constant Unknown mode','ACTUALLY_RUN',ran('test_roster_ui.py'));
add(2,'Independent visible BACKEND selector','EXPLICIT_N1_REQUIREMENT','No independent backend selector at initial inspection','Implemented immutable composition IDs, capability reasons and selection separate from MODE/tap','ACTUALLY_RUN',ran('test_n1_frontend.py',true),'Only baseline is executable through the N1 common app. Staged candidates remain honestly unavailable until adapters pass.');
add(2,'One shared interface and capacity metadata','EXPLICIT_N1_REQUIREMENT','One prototype toolkit/codebase existed','Added immutable backend manifests; unavailable mode reasons stay visible','ACTUALLY_RUN',ran('test_backend_catalog.py',true),'Manifest capabilities are not measured model performance. Never load several stacks automatically in 2 GB profile.');

add(3,'Preserve existing spatial and assigned-seat choices','PROPOSAL_AND_EXISTING_FEATURE','Existing spatial/seat modes and saved telemetry interfaces implemented','Retained choices and explicit unavailable reasons across backend selection','ACTUALLY_RUN',ran('test_backend_catalog.py',true));
add(3,'Matching recorded telemetry only','EXPLICIT_N1_BOUNDARY','Saved telemetry binding already used by spatial adapters','Required matching telemetry rather than ground-truth labels/seat positions','ACTUALLY_RUN',ran('test_seats.py'),'N1 source fixtures verify guards. Acoustic spatial efficacy and live IMU observations are not established.');
add(3,'Static seat labels remain assumptions','PROPOSAL_AND_ASSUMPTION','Seat mode labels distinguish assumed and voice-supported attribution','Verified outsiders, overlap, missing/stale directions do not self-certify identity','ACTUALLY_RUN',ran('test_seats.py'));
add(3,'No new spatial algorithm or IMU truth','PROPOSAL_DEFERRED','Existing features retained','New spatial research deferred; absent sensors remain unavailable','NOT_TESTED',ran('test_imu.py'),'Simulation of sensor schema/guards is not connected hardware or range/position measurement.');

add(4,'Paragraph must not own speaker identity','OBSERVATION_REPRODUCED','Initial source fixture reproduced A/B/A collapsing inside one paragraph','Implemented token/span owners; paragraph now groups independently owned spans','ACTUALLY_RUN',ran('test_n1_spans.py',true));
add(4,'Stable token IDs and timestamped source windows','EXPLICIT_N1_REQUIREMENT','Baseline had caption-wide ownership and no exact word alignment','Retains unchanged prefix IDs; rewritten hypotheses retire old IDs; source revision windows recorded','ACTUALLY_RUN',ran('test_n1_spans.py',true),'Timing is ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT. Exact per-word acoustic boundaries are null.');
add(4,'A/B/A and short interruptions','EXPLICIT_N1_REQUIREMENT','Bug observed in initial EVENT fixture','Source-only fixtures preserve A/B/A and 50ms interruption ownership','ACTUALLY_RUN',ran('test_n1_spans.py',true),'Synthetic EVENT times test logic, not synthesized acoustic evaluation scenes.');
add(4,'Simultaneous updates and overlapping captions','EXPLICIT_N1_REQUIREMENT','Independent utterance IDs existed','Verified simultaneous windows remain separately visible and owned','ACTUALLY_RUN',ran('test_n1_frontend.py',true));
add(4,'Late corrections preserve first and committed labels','EXPLICIT_N1_REQUIREMENT','Caption-level label revisions existed','Explicit target token IDs/current revision required to change committed owners; retired histories retained','ACTUALLY_RUN',ran('test_n1_spans.py',true),'First event label and actual GUI presentation label are separately scoped; no physical receipt is inferred.');
add(4,'Scrolling and large paragraphs','EXPLICIT_N1_REQUIREMENT','History scrolling/grouping existed','Verified retained scroll position, 2001 unique token IDs and accessible long caption suffixes','ACTUALLY_RUN',ran('test_n1_frontend.py',true));
add(4,'Wrong names and evidence availability versus cosine','HYPOTHESIS_FOR_COMPARISON','Raw identity scores and event clocks available','Preserve score/margin/availability provenance; comparative wrong-name analysis belongs N2/N4','NOT_TESTED',cp('data/METRIC_LIMITATIONS.md'),'No model ranking or new confidence calibration in N1.');

add(5,'Paragraph Done requires usable input','REQUEST','Usable-duration/quality-gated Paragraph Done already implemented','Verified short/silent/clipped/overlap/corrupt input cannot save as usable enrollment','ACTUALLY_RUN',ran('test_paragraph_enrollment.py'));
add(5,'Unique enrollment material and honest progress','REQUEST','Duplicate source support checks and usable-time accounting existed','Verified duplicates do not count again and progress cannot extrapolate speech','ACTUALLY_RUN',ran('test_paragraph_enrollment.py'));
add(5,'Enrollment persistence and cancellation','REQUEST','People UUIDs and save/cancel/export/import implemented','Isolated tests cover backend/domain compatibility, commit rollback and cleanup','ACTUALLY_RUN',`${ran('test_people.py')}; ${base}test_enrollment_cleanup.py`,'Personal gallery remains untouched; no human enrollment session performed.');
add(5,'Independent E/C/Q reference groups','EXPLICIT_N1_REQUIREMENT','S6C clean references and accepted S6D captures existed','Bound disjoint source/PCM/text groups, durations and rosters before model outputs','ACTUALLY_RUN',`${cp('data/ECQ_PLAN.md')}; ${cp('data/ECQ_AUDIT.json')}`,'Undocumented transformed aliases/unique-human re-identification not exhaustively ruled out. Three same-book E/C cases have different chapters and are declared.');
add(5,'Same-device and clean-source references separated','EXPLICIT_N1_REQUIREMENT','Existing disjoint processed E captures and clean E/C references found','Created person/duration/domain capability matrices and processed-C admission limits','ACTUALLY_RUN',`${cp('data/ENROLLMENT_CAPABILITY_MATRIX.csv')}; ${cp('data/PROCESSED_C_AUDIT.json')}`,'Processed C is collection-only evidence until C-only projection reviewed. Same-device is not identical query room/configuration.');
add(5,'Model-specific galleries and personal data','EXPLICIT_N1_REQUIREMENT','Personal ReDimNet vectors are model-specific','No TitaNet reuse of ReDimNet vectors; future E re-extraction keyed to encoder; personal gallery untouched','IMPLEMENTED',`${cp('data/ECQ_PLAN.md')}; ${cp('assets/model_manifest.json')}`,'TitaNet embedding/export execution remains NOT_TESTED. No private personal recording accessed.');
add(5,'Script-aware references','PROPOSAL_AND_EXISTING_FEATURE','Script evidence sidecars and optional text alignment existed','Verified wrong/skipped/repeated script and unknown timing do not change original quality','ACTUALLY_RUN',ran('test_script_evidence.py'),'Script estimates are not phonetic alignment. Optional script preparation belongs N3.');
add(5,'Phonetic neural adaptation','HYPOTHESIS_DEFERRED','No authorized acoustic/neural retraining in this campaign','Keep models frozen; do not reinterpret script coverage as trained phonetic correction','NOT_TESTED',cp('data/METRIC_LIMITATIONS.md'),'Outside N1 and current saved-audio comparison scope.');

add(6,'Progressive adaptation primary OFF','PROPOSAL_AND_EXISTING_FEATURE','Optional low-weight personal adaptation bank existed and defaults off','Retained default-off primary comparison and exact baseline scoring','ACTUALLY_RUN',ran('test_adaptation.py'),'Any controlled optional N4 adaptation remains a separately declared condition.');
add(6,'Forced names and seats cannot certify learning','EXPLICIT_N1_BOUNDARY','Adaptation provenance/consent gates already implemented','Verified wrong seat, forced label, weak/different winner cannot self-bootstrap','ACTUALLY_RUN',ran('test_adaptation.py'));
add(6,'Protect anchors and rollback','REQUEST','Atomic promotion, capped bank and undo mechanisms existed','Verified anchor changes invalidate bank; promotion/undo/restart preserve identity state','ACTUALLY_RUN',ran('test_adaptation.py'));
add(6,'Frozen neural weights and domain separation','EXPLICIT_N1_BOUNDARY','Adaptation uses compatible additional templates, not model training','Kept neural weights unchanged and domains/windows distinct','ACTUALLY_RUN',ran('test_adaptation.py'),'Source tests verify data policy; no acoustic adaptation efficacy claim.');

add(7,'Original versus normalized words','REQUEST','Text assistance and session archives preserve raw text separately','Verified raw hash/text and token owners survive a separate formatting suggestion','ACTUALLY_RUN',`${cp('review/NOTE_EXAMPLE_TESTS.json')}; ${ran('test_text_assistance.py')}`);
add(7,'WD-40 exact spelling preservation','SUPPLIED_EXAMPLE','Existing text layer retains original alphanumeric source','New source fixture verifies WD-40 remains original text with no automatic reconstruction','ACTUALLY_RUN',cp('review/NOTE_EXAMPLE_TESTS.json'),'Text fixture only; no recognition/normalization accuracy claim.');
add(7,'WD-40 spoken-form normalization','PROPOSAL_DEFERRED','Existing vocabulary accepts letters/apostrophes and same-count mappings; WD-40 rule rejected','New fixture confirms unavailable rule instead of silently claiming support; implement/evaluate in N3 if authorized there','UNAVAILABLE',cp('review/NOTE_EXAMPLE_TESTS.json'),'The frozen N1 prototype does not normalize double u dee forty into WD-40.');
add(7,'Amir approved spelling example','SUPPLIED_EXAMPLE','Approved contextual Amir/emir rule and person linkage existed','New fixture confirms approved context works while absent context, ambiguous Emir and protected numerals abstain','ACTUALLY_RUN',cp('review/NOTE_EXAMPLE_TESTS.json'),'Orthographic heuristic only. Never identity or acoustic evidence.');
add(7,'PnC and ITN separated','PROPOSAL_AND_EXISTING_FEATURE','Existing final-only PnC; source-backed formatting retained','Preserve P0; A2/A3 native PnC staged, standalone P2 not verified; ITN separate','IMPLEMENTED',cp('assets/MODEL_ACCESS_MATRIX.md'),'Comparative PnC/ITN tests belong N3. No independent conversational punctuation gold was found.');
add(7,'Wider contextual reconstruction','HYPOTHESIS_DEFERRED','No new deep language model added','No unsupported filling of missing acoustic content; retain bounded review suggestions','NOT_TESTED',ran('test_text_assistance.py'),'General reconstruction outside N1. Existing ASR hotword route unavailable for baseline tokenizer.');

add(8,'Saved processed inputs and quality diagnostics','REQUEST','Prepared O0/O1 capture pairs and quality partitions existed','Bound all 240 scenes/480 cells and reference limitations without input replacement','ACTUALLY_RUN',cp('data/DATA_AUDIT_SUMMARY.json'),'Quality analysis across candidate outputs belongs N4.');
add(8,'No denoiser comparison or new noise acquisition','EXPLICIT_N1_BOUNDARY','Optional legacy noise code exists but is outside this campaign','Retained baseline route and staged no denoiser or dataset payload','IMPLEMENTED',`${cp('assets/download_receipts.json')}; ${cp('data/DATA_AUDIT_SUMMARY.json')}`,'Legacy mocked noise tests do not mean a denoiser model was run.');
add(8,'No raw-minus-processed noise inference','HYPOTHESIS_REJECTED_AS_UNVALIDATED','Captured processed outputs are authoritative inputs','No raw/processed subtraction used and raw microphone files are not a prerequisite','IMPLEMENTED',cp('data/METRIC_LIMITATIONS.md'),'No removed-noise signal or denoising efficacy claim.');
add(8,'Low quality versus calibrated confidence','REQUEST','Quality/identity diagnostics are distinct','Retained reference flags and raw score/margin labels','ACTUALLY_RUN',`${ran('test_buffers_quality.py')}; ${base}test_roster_ui.py`,'Confidence calibration is unavailable unless separately measured on disjoint C data.');

add(9,'Linked audio inputs and transcripts','REQUEST','Session event/audio indices and source slices existed','Verified raw immutability, joined source clocks and exact saved slice linkage','ACTUALLY_RUN',ran('test_sessions.py'),'Only saved input/test fixtures used; private full transcripts remain outside Git/handoff.');
add(9,'Explicit new session','REQUEST','New session preserves draft and avoids model reload','Verified session state transitions without opening hardware','ACTUALLY_RUN',ran('test_sessions.py'));
add(9,'Save/delete with data protection','REQUEST','Saved sessions, quota protection and consented exports existed','Verified session deletion never touches people/gallery and saved sessions survive quota pressure','ACTUALLY_RUN',ran('test_sessions.py'));
add(9,'CPU/RAM/VRAM resource logs','REQUEST','Resource indices existed','Measured host CPU/RAM/GPU/volumes; worker progress/resource checks persisted','ACTUALLY_RUN',`${cp('assets/environment_receipt.json')}; ${ran('test_sessions.py')}`,'Host resource inventory is not isolated model memory or CM5 performance.');
add(9,'Truthful availability/source clocks','REQUEST','Live timing contracts and source-index provenance existed','Retained event availability, processing and GUI receipt clocks separately','ACTUALLY_RUN',`${ran('test_live_timing.py')}; ${cp('data/METRIC_LIMITATIONS.md')}`,'Accelerated file inference is not source-speed live latency. 50ms RIR convention is not measured hardware latency.');
add(9,'GUI idle and no microphone during campaign','LATEST_USER_INSTRUCTION','Saved auto-start preferences could open hardware on ordinary launch','N1 safe launch opens idle; test harness disables physical audio APIs','ACTUALLY_RUN',`${ran('test_n1_safe_start.py',true)}; ${local}checks/full-suite-v1/hardware_guard.json`,'User work/calls remain on input desktop. No device probing, default playback changes or Pi access.');

add(10,'Unassigned sensor pins/axes/bus/driver','PROPOSAL_DEFERRED','Mockable hardware schema and disabled/unassembled handling existed','Preserved unknown configuration and prevented invalid observations from providing direction','ACTUALLY_RUN',ran('test_imu.py'),'GPIO/address/display-controller/BMI270/camera/button wiring awaits user hardware details.');
add(10,'Acceleration does not prove translation/range','HYPOTHESIS_UNVALIDATED','Motion gates invalidate stale spatial assumptions','Verified no out-of-order restore or position claim in source fixture','ACTUALLY_RUN',ran('test_motion.py'),'No drift-free translation, absolute range or hardware calibration claim.');
add(10,'Future physical spatial calibration','PROPOSAL_DEFERRED','No connected sensor in campaign','Retain schema and future setup instructions for N5; no hardware operation now','NOT_TESTED',ran('test_imu.py'),'Pi remains powered off and disconnected for entire campaign, per current user instruction.');

add(11,'Four-day comparison supersedes old no-campaign context','LATEST_USER_INSTRUCTION','Older notes had conflicting context','Use one campaign start and 96h target; finish when scope complete','IMPLEMENTED',`${local}supervision/campaign.json; ${cp('supervision/README.md')}`,'96h is a target, not a minimum runtime or guarantee.');
add(11,'Prototype-first common UI freeze','EXPLICIT_N1_REQUIREMENT','Launchable Windows/source/Pi-saved baseline recovered','Frozen common frontend version for paired candidate comparisons','ACTUALLY_RUN',cp('FRONTEND_FREEZE.json'),'Later critical changes require a new version and affected paired checks.');
add(11,'Portable 2GB priority and runnable variants','EXPLICIT_N1_REQUIREMENT','Baseline retained; native candidate routes staged','Prioritize D1 hybrid, compact ASR/enrollment, 600M, optional overlap/PnC; package variants in later stages','IMPLEMENTED',cp('assets/model_manifest.json'),'Windows native build proves no ARM64 speed/RAM result. No multiple automatic stacks in 2GB profile.');

add(12,'Inspect queued improvements rather than assuming execution','EXPLICIT_N1_REQUIREMENT','Initial inspection identified working fixes and paragraph-identity defect','Read current code and tests; preserve existing behavior; repair demonstrated gap','ACTUALLY_RUN',`${ran('test_n1_spans.py',true)}; ${cp('FRONTEND_FREEZE.json')}`);
add(12,'UI first then novel components and comparison','REVISED_IMPLEMENTATION_ORDER','Historical task order superseded by N1-N5 campaign','N1 freezes interface/data/assets/supervisor; later stages own model ranking','IMPLEMENTED',`${cp('FRONTEND_FREEZE.json')}; ${cp('assets/model_manifest.json')}`,'Do not interpret seeded backend choices as functioning adapters or compared models.');
add(12,'Baseline paired-screen acceptance','EXPLICIT_N1_REQUIREMENT','Historical baseline retained with exact model hashes','Predeclared 48-scene two-tap panel and repaired-core runner; acceptance reported by root worker receipt','IMPLEMENTED',`${cp('data/SCREEN_48.json')}; ${cp('data/run_baseline_screen.py')}`,'Coverage catalogue does not promote a still-running or failed worker to completed acceptance. Final handoff owns the run result.');

add(13,'Self-contained prompts and source authority','REQUEST','N1 attachment supplies full campaign contract','Treat user request as authority; supplied note summary wording identified honestly','IMPLEMENTED',cp('review/README.md'),'Underlying original raw note document was not attached. This catalogue maps the 13-section supplied summary plus explicit N1 items.');
add(13,'Current reasoning preference','LATEST_USER_INSTRUCTION','Attachment recommends Extra High except bounded Ultra need','Current user requested Astra Ultra/Normal speed; parent task records preference','IMPLEMENTED','C:/Users/amiri/Downloads/Codex_N1_Foundation_UI_Data_and_Supervision.md','No tool-run receipt is invented for a model/reasoning setting that a child agent cannot independently verify.');
add(13,'Licensed no-charge access and exact revisions','EXPLICIT_N1_REQUIREMENT','Seed candidates had planned access only','Verified six public repos; five core artifacts downloaded and hashed; terms/code dependencies recorded','ACTUALLY_RUN',`${cp('assets/download_receipts.json')}; ${cp('assets/terms_receipts.json')}`,'A1/E1 NeMo runtime/export setup still required; optional X1 deferred; P2 unverified. No paid services or credential collection.');
add(13,'OS check-ins at 10/15/30 minutes','EXPLICIT_N1_REQUIREMENT','No N1 supervision active at inspection','Registered phase-specific OS tasks; one setup scheduled trigger succeeded','ACTUALLY_RUN',`${local}supervision/scheduler-register.json; ${local}supervision/scheduler-test-trigger.json`,'Logged-out/asleep host is not supervised; no wake/reboot. Numerical workers run independently.');
add(13,'Locks, failure/resume/cleanup and durable status','EXPLICIT_N1_REQUIREMENT','Needed new campaign runner','Implemented OS-held writer/worker locks, progress/ETA/status and bounded review deltas; dedicated tests retained','IMPLEMENTED',`${cp('supervision/test_supervisor.py')}; ${local}checks/supervisor-final-v3.txt`,'Root supervisor acceptance report records overlap, failure, resume and cleanup results.');
add(13,'No unchanged healthy LLM check or competing resume','EXPLICIT_N1_REQUIREMENT','Installed CLI continuation cannot prove atomic idle/queue guard','Unchanged checks stay cheap; changes queue exact-session review request; automatic Codex continuation unavailable','UNAVAILABLE',cp('supervision/README.md'),'Manual Codex resume is required. Never claim autonomous LLM check-ins or use ambiguous --last.');
add(13,'Git branch backup and sanitized handoff','EXPLICIT_N1_REQUIREMENT','Existing authorized public repository/remote preserved with visibility unchanged','One root integration writer commits/pushes reviewed files; payloads/personals excluded','IMPLEMENTED',`${cp('assets/EVIDENCE_HASHES.json')}; ${cp('FRONTEND_FREEZE.json')}`,'Final Git/push/ZIP receipt belongs root handoff; this catalogue does not assert a push before verification.');
add(13,'Master workbook update proposal only','EXPLICIT_N1_REQUIREMENT','Master workbook is not an N1 editing target','Prepared WORKBOOK_UPDATE.md proposal for final handoff','IMPLEMENTED',cp('WORKBOOK_UPDATE.md'),'This catalogue and proposal do not rewrite the master workbook.');
add(13,'Saved Pi evidence and later ARM64 preparation','LATEST_USER_INSTRUCTION','Saved Pi deployment matches baseline; physical Pi is off','No SSH, flash, remote control or hardware session; preserve later deployment path','NOT_TESTED',cp('assets/environment_receipt.json'),'Physical CM5 2GB acceptance deferred until user connects it after campaign.');

// Execution states are refreshed only from completed receipts, never a clock,
// a running progress counter or the intended final N1 acceptance status.
const completionBindings = [];
async function optionalReceipt(file) {
  try {
    const bytes = await fs.readFile(file);
    const value = JSON.parse(bytes.toString('utf8').replace(/^\uFEFF/,''));
    return {value,binding:{path:file,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length}};
  } catch(error) { if (error.code === 'ENOENT') return null; throw error; }
}
function refresh(item,action,status,evidence,limitation) {
  const row=rows.find(row=>row[1]===item);
  if (!row) throw new Error('Unknown note item '+item);
  row.splice(4,4,action,status,evidence,limitation);
}
const finalBaseline=await optionalReceipt(path.join(campaign,'data','BASELINE_ANALYSIS_SUMMARY.json'));
const finalRegression=await optionalReceipt(path.join(campaign,'data','REGRESSION_ANALYSIS_SUMMARY.json'));
const finalGui=await optionalReceipt('G:/Just_Peachy_N1/20260924_campaign/evidence/frontend/baseline_full_gui_v1/GUI_REPLAY_REPORT.json');
if (finalBaseline?.value.status==='PASS' && finalBaseline.value.completed_cells===96
    && finalBaseline.value.complete_paired_scenes===48 && finalRegression?.value.status==='PASS'
    && finalRegression.value.completed_cells===8 && finalGui?.value.status==='COMPLETE'
    && finalGui.value.rendered===96 && !finalGui.value.failed.length && !finalGui.value.allow_partial) {
  refresh('Baseline paired-screen acceptance',
    'Completed 48-scene/96-cell paired baseline, eight supplemental cells and 96 frozen-GUI final-snapshot renders',
    'ACTUALLY_RUN',`${cp('data/BASELINE_ANALYSIS_SUMMARY.json')}; ${cp('data/REGRESSION_ANALYSIS_SUMMARY.json')}; ${finalGui.binding.path}`,
    'Final-state GUI rendering is separate from source-paced inference; it does not measure online GUI latency, physical scanout or Pi performance.');
  completionBindings.push(finalBaseline.binding,finalRegression.binding,finalGui.binding);
}
const git=await optionalReceipt(path.join(campaign,'GIT_RECEIPT.json'));
if (git?.value.verified_source_commit && git.value.source_remote_refs?.sha256) {
  refresh('Git branch backup and sanitized handoff',
    git.value.verified_payload_commit ? 'Source and reviewed report payload commits have verified remote refs; existing repository visibility unchanged'
      : 'Baseline/common source commits and tags verified on existing remote; final reviewed report payload backup is still pending',
    'ACTUALLY_RUN',cp('GIT_RECEIPT.json'),
    'Push status is limited to the verified refs in GIT_RECEIPT.json. ZIP completion/integrity is separately recorded in HANDOFF_PACKAGE.json; no private speech or model payload is admitted.');
  completionBindings.push(git.binding);
}
const supervisorLog=path.join(local,'checks','supervisor-final-v3.txt');
try {
  const bytes=await fs.readFile(supervisorLog);
  const content=bytes.toString('utf8').replace(/^\uFEFF/,'');
  if (/Ran 10 tests in [\d.]+s/.test(content) && /^OK\s*$/m.test(content)) {
    refresh('Locks, failure/resume/cleanup and durable status',
      'Ten supervisor tests passed, including STARTING watchdog, live/uncertain child guards, PID reuse, resume ETA, overlap, failure and cleanup',
      'ACTUALLY_RUN',`${cp('supervision/test_supervisor.py')}; ${supervisorLog}`,
      'Tests use isolated state and harmless child processes. An uncertain legacy orphan requires manual recovery; no competing Codex resume is launched.');
    completionBindings.push({path:supervisorLog,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length});
  }
} catch(error) { if(error.code!=='ENOENT') throw error; }

const headers = ['section','item','observation_vs_hypothesis','existing_status','change_or_test_or_deferral','final_status','evidence_path','limitation'];
const sections = [...new Set(rows.map(r => Number(r[0])))].sort((a,b) => a-b);
if (JSON.stringify(sections) !== JSON.stringify(Array.from({length:13},(_,i)=>i+1))) throw new Error('Missing note section');
if (new Set(rows.map(r=>r[0]+'|'+r[1])).size !== rows.length || rows.some(r=>r.length!==headers.length || r.some(v=>typeof v!=='string'||!v))) throw new Error('Invalid note rows');
const wb = Workbook.create();
const sheet = wb.worksheets.add('Note coverage');
const all = [headers, ...rows];
sheet.getRange(`A1:H${all.length}`).values = all;
sheet.getRange(`A1:H${all.length}`).format.font = {name:'Arial',size:11};
sheet.getRange('A1:H1').format = {fill:'#273444',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'}};
sheet.getRange(`A1:H${all.length}`).format.wrapText = true;
sheet.getRange(`A1:H${all.length}`).format.verticalAlignment = 'top';
sheet.getRange('A:A').format.columnWidthPx = 85;
sheet.getRange('B:B').format.columnWidthPx = 290;
sheet.getRange('C:C').format.columnWidthPx = 260;
sheet.getRange('D:H').format.columnWidthPx = 360;
sheet.getRange('A1:H1').format.rowHeightPx = 44;
sheet.getRange(`A2:H${all.length}`).format.rowHeightPx = 100;
sheet.freezePanes.freezeRows(1);
sheet.showGridLines = false;
wb.recalculate();
const inspection = await wb.inspect({kind:'table',range:'Note coverage!A1:H4',include:'values',tableMaxRows:4,tableMaxCols:8,maxChars:2500});
// CSV export is a flat serialization of the documented range.values getter.
// No formulas/styles are part of the requested machine-readable CSV contract.
const values = sheet.getRange(`A1:H${all.length}`).values;
const escape = value => '"' + String(value).replaceAll('"','""') + '"';
const csv = values.map(row=>row.map(escape).join(',')).join('\r\n')+'\r\n';
await fs.writeFile(path.join(campaign,'NOTE_COVERAGE.csv'),csv,'utf8');
const imported = await Workbook.fromCSV(csv,{sheetName:'Roundtrip'});
const back = imported.worksheets.getItemAt(0).getRange(`A1:H${all.length}`).values;
if (JSON.stringify(back) !== JSON.stringify(all)) throw new Error('CSV round-trip changed values');
const preview = await wb.render({sheetName:'Note coverage',range:'A1:D5',scale:1,format:'png'});
const previewPath = path.join(local,'checks','note_coverage_preview.png');
await fs.mkdir(path.dirname(previewPath),{recursive:true});
await fs.writeFile(previewPath,new Uint8Array(await preview.arrayBuffer()));
const audit = {created_at_utc:new Date().toISOString(),status:'PASS',rows:rows.length,columns:headers,sections,
  source_scope:'Supplied NOTE_COVERAGE.md 13-section summary plus explicit N1 attachment; full original notes not supplied',
  source_files:['C:/Users/amiri/Downloads/NOTE_COVERAGE.md','C:/Users/amiri/Downloads/Codex_N1_Foundation_UI_Data_and_Supervision.md'],
  unique_keys:true,csv_roundtrip_exact:true,csv_sha256:crypto.createHash('sha256').update(csv).digest('hex'),
  preview_path:previewPath,inspection:inspection.ndjson,completion_receipts:completionBindings,
  status_counts:Object.fromEntries([...new Set(rows.map(r=>r[5]))].map(s=>[s,rows.filter(r=>r[5]===s).length]))};
await fs.writeFile(path.join(here,'NOTE_COVERAGE_AUDIT.json'),JSON.stringify(audit,null,2)+'\n');
console.log(JSON.stringify({status:audit.status,rows:rows.length,sections:sections.length,csv_sha256:audit.csv_sha256}));
