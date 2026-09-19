"""Package the analysis-first pre-playback checkpoint; never imply physical proof."""
import argparse,csv,json,time,zipfile
from pathlib import Path
from s0_common import ROOT,SIM,HashCache,save,now

def run(report):
    report=Path(report);assert not list(report.glob('hardware_*')),'Use a physical-results report after any hardware attempt'
    packet=report/'preflight_packet';packet.mkdir(exist_ok=False);cache=HashCache()
    inputs=json.loads((report/'inputs_manifest.json').read_text());pre=json.loads((report/'preflight.json').read_text())
    checks=json.loads((report/'offline_transport_checks.json').read_text())
    run_id=report.name;reason='Explicit confirmation that every analog monitor is off/disconnected has not yet been received.'
    def md(name,text):(packet/name).write_text(text.strip()+'\n',encoding='utf-8')
    rows=[{'case_id':c,'status':'NOT_TESTED','physical_playback_s':0,'payload_mismatches':'','reason':reason} for c in inputs['planned_physical_attempts']]
    with (packet/'per_case_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    metrics={'schema_version':'1.0','metric_definition_version':'s3-preflight-v1','stage':'S3','run_id':run_id,'status':'BLOCKED',
        'scope':'Preflight checkpoint, not completed physical S3','observed_utc':now(),
        'test_population':{'planned_physical_cases':6,'attempted_physical_cases':0,'completed_physical_cases':0,'prepared_distinct_speakers':2,'prepared_distinct_rirs':3,'planned_repeat_count':2},
        'software':{'status':'PASS','official_pack_and_negative_checks_passed':8,'official_pack_and_negative_checks_total':8,'recapture_integrity_checks_passed':checks['checks_passed'],'recapture_integrity_checks_total':checks['checks_total'],
            'definition':'Deterministic offline array/file checks. Their denominator is software checks, not physical recordings.','sources':['inputs_manifest.json#/offline_checks','offline_transport_checks.json']},
        'transport':{'status':'NOT_TESTED','negotiated_rate_hz':None,'negotiated_bit_depth':None,'payload_mismatch_count':None,'unexpected_gap_samples':None,'common_offset_samples':None,'level_error_db_by_mic':None,'pairwise_delay_error_samples':None,'null_reason':reason,'predeclared_tolerances':inputs['predeclared_transport_tolerances']},
        'outputs':{'status':'NOT_TESTED','O0_verified':None,'O1_verified':None,'simultaneous_capture':None,'audio_delay_ms':None,'latency_uncertainty_ms':None,'null_reason':reason},
        'telemetry':{'status':'LIMITED','snapshot_AEC_fields_read':True,'optional_selected_azimuth_command_available':True,'streaming_rates_hz':None,'gaps_s':None,'speech_handoff_lag_s':None,'null_reason':'Only snapshot getters ran; no timed speech or persistent logger capture.','device_sample_timestamp_available':False,'source':'preflight.json and initial_params_dump.txt'},
        'H2_smoke':{'status':'NOT_TESTED','mono_streams_evaluated':[],'dropped_frames':None,'null_reason':'No captured O0/O1 exists; unchanged H2 smoke depends on physical capture.','accuracy_qualification':False,'naming_qualification':False},
        'restoration':{'status':'NOT_NEEDED','setters_issued':0,'audio_streams_opened':0,'hardware_lease_released':pre['hardware_lease_released'],'after_readback':None,'null_reason':'Read-only preflight did not alter settings; physical runner and restoration are not yet exercised.'},
        'resources':{'physical_playback_s':0,'planned_physical_playback_s':123,'free_space_at_preparation':inputs['resources'],'minimum_C_reserve_gib':50,'elapsed_s':time.time()-1788904154},
        'unresolved':[reason,'Current task model/effort could not be changed or verified through available tools.'],
        'limitations':['No physical transport, gain/delay, output, timing, repeatability or H2 interoperability result exists.','Input geometry is operator-labelled, including a +/-5 degree estimate; no independent spatial calibration.','Native linear-array direction is folded 0-180 degrees and cannot establish front/back discrimination.','No output winner, enrollment naming, moving-person or CM5 qualification.'],
        'source_level_policy':inputs['source_level_policy']}
    save(packet/'metrics.json',metrics)
    save(packet/'restoration.json',metrics['restoration'])
    save(packet/'relevant_settings.json',{'observed_utc':pre['observed_utc'],'identity':pre['identity'],'settings':pre['settings'],
        'intended_S3_settings':{'USB_BIT_DEPTH':[24,24],'I2S_INPUT_PACKED':[1],'AUDIO_MGR_MIC_GAIN':[1],'AUDIO_MGR_REF_GAIN':[1],'AUDIO_MGR_SYS_DELAY':[0],'AEC_ASROUTONOFF':[1],'AEC_ASROUTGAIN':[1],
        'AUDIO_MGR_OP_ALL':[3,0,3,2,7,3,3,1,3,3,6,3]},'planned_not_applied':True})
    save(packet/'offline_checks.json',{'packing_checks':inputs['offline_checks'],'integrity_checks':checks})
    bindings=[cache.bind(report/n) for n in ['preflight.json','inputs_manifest.json','offline_transport_checks.json','input_bindings.json']]
    code=[cache.bind(SIM/'scripts'/n) for n in ['s3_preflight.py','s3_prepare.py','s3_hardware.py','s3_checks.py','s3_checkpoint.py','README_S3.md']]
    save(packet/'run_manifest.json',{'schema_version':'1.0','run_id':run_id,'created_utc':now(),'status':'BLOCKED','reason':reason,'inputs':bindings,'code':code,
        'canonical_rir_manifest':inputs['rir_manifest'],'consumed_rirs':[{'role':r['role'],'run_id':r['run_id'],'file':r['file']} for r in inputs['selected_rirs']],
        'speech_fixtures':inputs['speech_fixtures'],'rights':inputs['rights'],'reserved_development_speaker_keys':inputs['reserved_development_speaker_keys'],
        'git_policy':'No commit, push, H2 changes, training, RIR regeneration or full campaign. Main repository tracked state remained unchanged.',
        'model_request':'User requested Astra Extra High. Available tools do not expose a current-turn settings switch; selection not claimed.',
        'code_validation_limit':'Hardware runner passes offline failure checks but has not yet executed any physical attempt or restoration.'})
    md('START_HERE.md',f'''# S3 preflight checkpoint — BLOCKED

**Physical S3 is not complete.** The explicit analog-monitor safety confirmation is pending. No audio playback, setters, USB-width changes or resets have occurred.

Completed: Revision 6 workbook and S3 pack bound; current 3.2.1 ua-io48-lin device read under the existing lock; three canonical RIRs bound; two development speakers/three utterances selected; five vectors prepared for six physical cases; 17/17 offline checks passed. C: had 90.90 GiB and G: 449.30 GiB free at preparation.

Next decision: confirm that the KRK and every analog speaker connected to XVF LINE OUT is powered off or physically disconnected. Keep the XVF powered. Then continue the bounded S3 proof in this task, using the prepared files and fresh live settings. Select Astra / Extra High in the task UI if required; it was not programmatically changed.

Read S3_REPORT.md, metrics.json and REPORT_SECTION.md. NEXT_PHASE_INPUTS.md gives the exact resume inputs. This packet is a checkpoint, not authority to begin a scene bank. Full local evidence: `{report}`.

No claims are made about an O0/O1 winner, naming, moving people, model accuracy, or CM5 readiness.''')
    md('S3_REPORT.md',f'''# S3 physical XVF proof — preflight checkpoint

Status: **BLOCKED before playback**. This is an analysis-first checkpoint dated {now()}. The user-required confirmation that the KRK and all other analog monitors are off/disconnected remains pending. A software mute cannot establish this condition because it may corrupt the packed carrier.

## Observations

| Capability | Status | Evidence and denominator |
|---|---|---|
| Pack/master input binding | PASS | S3 checksum entries and exact Revision 6 workbook SHA-256 checked |
| Current device discovery | PASS | One XVF WDM-KS input/output pair; firmware 3.2.1, linear, four mics |
| Offline packing/integrity | PASS | 8 pack/equivalence checks plus 9 recapture/failure checks |
| Physical transport and unity/zero replay | NOT_TESTED | 0/6 physical cases attempted |
| O0/O1 processed routing | NOT_TESTED | No captured output |
| Speech telemetry behavior | NOT_TESTED | Snapshot availability only |
| Repeatability and timeline alignment | NOT_TESTED | No repeat captures |
| Unchanged H2 O0/O1 smoke | NOT_TESTED | No physical mono output files |
| Restoration | NOT_NEEDED | Zero setters/streams; byte-range lease released |

The live USB width is 16/16. Existing mic gain 10, reference gain 1.5, SYS_DELAY -32, packed input 0 and ASR output disabled were preserved. Snapshot telemetry getters responded, including the optional selected-azimuth command; NaN in the no-speech selected field is not a failure. Snapshot responses establish neither an achieved logging rate nor telemetry freshness. The intended 24/24 packed transport is not yet negotiated or physically qualified.

The selected Library Conference Room / Square Table End / flat-clear RIRs are front R01 (0°, 1.70 m), left R12 (+75°, 0.74 m), and right R04 (-80°, 0.90 m). All three exact hashes match the S3 bindings and belong to S2's HIL-input-eligible subset. The deferred clock-sensitive low-table R13 is absent. No earlier test, RETAKE, excluded Loeb Caf or additional measurement is introduced. S2's broader 121-record results are reused, not re-audited or upgraded by S3.

LibriSpeech dev-clean utterances 1272-128104-0000 (5.855 s), 1272-128104-0003 (9.900 s), and 1462-170138-0006 (8.580 s) were checked against exact local audio and transcript files. Speaker keys 1272 and 1462 are distinct in the dataset. Both identities and all three utterances are reserved as development fixtures. The local corpus license states CC BY 4.0; attribution and alteration details are in run_manifest.json. No speech or private enrollment audio is bundled.

## Prepared method and interpretation

The fixed source drive is original clean PCM times 0.25 (-12.0412 dB). Four-channel convolution uses the canonical Category 3 RIRs without another -6 dB factor, division by gain 10, delay compensation, independent normalization or alignment. All speech cases share one headroom factor; its value is 1.0 because additional attenuation was unnecessary. RIR pre-onset of about 50 ms remains, and no guessed distance/c delay is inserted.

Input slots are [zero far-end, zero ignored, MIC0, MIC1, MIC2, MIC3]. Each width is quantized directly from the numerical vector once to its available payload grid (23 bits for PCM24, 15 for PCM16). Both offline packings match the supplied XMOS implementation. Negative tests detect sign flips, channel swaps, an individual-mic delay, single-sample corruption, missing/duplicate groups and bad interior framing. Common-offset recovery permits no per-mic lag/gain fitting. Passing these software checks cannot establish a working physical transport.

The planned output mux is 3 0 / 3 2 / 7 3 / 3 1 / 3 3 / 6 3, in L_PK0/L_PK1/L_PK2/R_PK0/R_PK1/R_PK2 argument order. Unpacking produces MIC0, MIC1, MIC2, MIC3, O0 ASR-auto, O1 postprocessed-auto. This ordering follows the supplied implementation; simultaneous physical capture remains to be demonstrated. Expected physical tolerances are zero payload mismatches and zero interior marker errors after comparison to the quantized vector, with only one common integer offset. Boundary padding is reported separately.

The six planned cases take 123 seconds: tagged transport 8 s, front/left/right 13 s each, and two 38 s A-left/B-right/A-left conversations. Conversation source starts are exactly 3, 12 and 24 seconds, with full tails and surrounding silence. There is no reset between turns; resets and complete frozen settings apply between independent cases. The runner stops at an integrity failure. One diagnosed retry is available, with failed attempts retained and total playback below 15 minutes.

## Limits and next gate

Fresh device ownership and 50 GiB reserve checks are enforced on physical execution. The existing persistent telemetry logger records native radians/energy and host transaction bounds; subsequent analysis must keep source, recaptured input, processed audio and telemetry timelines separate. No device sample timestamp or causal audio/metadata alignment has been proven. Linear-array front/rear ambiguity and operator-estimated ±5° labels remain.

The initial static configuration will be snapshotted and restored with readback. Adaptive DSP history cannot be reconstructed from settings. That restoration path has not yet run, so this checkpoint is not a restoration proof. The existing H2 file path must receive explicitly isolated mono O0 and O1 only after all board handles close, using empty profile roots and unchanged assets/configuration. No H2 invocation was made here.

The safety confirmation is the immediate gate. After it arrives, continue S3 and replace this checkpoint with actual per-attempt findings and the compact final handoff. Do not start training, change H2, regenerate RIRs, select a production output, or launch the full simulation campaign.''')
    narrative='''# Proposed workbook S3 progress insertion — preflight only

S3 has reached a reproducible preflight checkpoint, but the physical proof is not yet complete. The stage remains blocked before playback because explicit confirmation that the KRK and every other analog monitor connected to the XVF LINE OUT is powered off or disconnected has not been received. This gate comes directly from the S3 instructions. Packed transport is not ordinary listenable stereo, and changing a software volume control can alter its payload. No audio stream, playback, device reset or configuration setter was used in this checkpoint.

The current master workbook was bound to the expected Revision 6 file hash, and the extracted S3 pack passed its supplied checksums. Existing S0 and S2 evidence was reused. A read-only inspection acquired the recorder's existing hardware lease, found a unique XVF WDM-KS input/output pair and confirmed firmware 3.2.1 ua-io48-lin with four microphones. The board currently reports USB 16/16, microphone gain 10, reference gain 1.5, SYS_DELAY -32 and packed input disabled. ASR output was also disabled. These are observed initial values, not the intended S3 replay settings. The lease was released after inspection.

| Evidence | Observed result | Scope |
|---|---|---|
| E-S3-INPUT | Three exact RIR bindings and three clean utterances checked | Selected development inputs only |
| E-S3-SOFTWARE | 17 of 17 offline checks passed | Software packing/integrity checks |
| E-S3-LIVE | Firmware and current configuration read successfully | Read-only device snapshot |
| E-S3-PHYSICAL | Zero of six physical cases attempted | Proof remains NOT_TESTED |

The selected RIRs represent front, left and right positions in the same Library Conference Room, Square Table End, flat-clear setup. Their labels are 0° at 1.70 m, +75° at 0.74 m and -80° at 0.90 m. All three exact hashes match the S3 input context, and all are eligible for the bounded hardware proof under S2. The clock-sensitive deferred low-table record is not used. No RIR was regenerated, and the broader library's status was not upgraded by these selected-file checks. Operator-estimated angle uncertainty and unresolved absolute timing remain.

Three transcript-labelled LibriSpeech dev-clean utterances were selected from two distinct dataset speaker identities. Their durations are 5.855, 9.900 and 8.580 seconds. Exact audio and transcript files were checked, and the local corpus license identifies CC BY 4.0. The speaker identities and utterances are reserved for development and should be excluded from any later untouched evaluation set. Raw audio remains on the desktop. Transcript boundaries are source-file labels; no word alignment or exact phonetic-onset claim was added.

Prepared vectors preserve the canonical signal contract. Original clean samples are multiplied by a fixed numerical drive scalar of 0.25, then convolved with the four Category 3 RIR channels. There is no second acquisition gain, -6 dB factor, per-channel normalization or separate microphone alignment. A shared headroom rule is applied consistently across all speech cases; its factor is 1.0 for these inputs. About 50 ms of RIR pre-onset remains, without adding a guessed distance-based propagation delay. Far-end and ignored input slots are zero throughout.

The local XMOS packer and the prepared implementation agree for both 16-bit and 24-bit carriers. Each format is quantized independently from the numerical vector, once. Additional checks successfully reject swapped microphones, a sign flip, a one-microphone delay, individual payload corruption, missing and duplicate groups, and interior framing errors. These tests support the checking software; they are not evidence that the physical board recovered a payload correctly.

The bounded physical plan is unchanged: an eight-second tagged case, three thirteen-second single-seat speech cases, and two identical thirty-eight-second A-left/B-right/A-left conversations. Planned playback is 123 seconds. The runner will use one exclusive owner, explicit XVF endpoints, a frozen configuration between independent cases and no reset between conversation turns. It will stop on input-integrity failure and preserve every attempt. The original exposed static configuration and USB width must be restored with readback; adaptive DSP history cannot be restored from parameter values.

Storage is adequate for this bounded work: preparation observed 90.90 GiB free on C: and 449.30 GiB on the G: SSD, above the 50 GiB working reserve. There are no physical payload, output-level, latency, speech-telemetry, repeatability or H2 results yet. No figures are proposed because no measured physical time series exists. The next gate is the operator's speaker-safety confirmation, followed by S3 execution and analysis. Production output selection, naming accuracy, moving-person behavior, model training, a full scene campaign and CM5 qualification remain outside this checkpoint.'''
    assert 500<=len(narrative.split())<=900,len(narrative.split());md('REPORT_SECTION.md',narrative)
    commands=f'''PowerShell (from `{ROOT}`):

```powershell
& 'C:\\Users\\amiri\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' simulation\\scripts\\s3_hardware.py --report simulation\\reports\\S3\\{run_id} --speaker-safety-receipt simulation\\reports\\S3\\{run_id}\\speaker_safety.json
```

Anaconda Prompt / Command Prompt: use the same executable and arguments without PowerShell's leading `&`. Exact setup commands and inputs/outputs are in `{SIM/'scripts/README_S3.md'}`.'''
    md('NEXT_PHASE_INPUTS.md',f'''# Resume bounded S3, not the next simulation phase

First receive the explicit analog-monitor confirmation. Save the actual user response and UTC time in speaker_safety.json; never invent a confirmation. The physical runner requires `all_analog_monitors_off_or_disconnected: true` and nonempty `user_confirmation_text`.

Input manifest: `{report/'inputs_manifest.json'}`

SHA-256: `{cache.bind(report/'inputs_manifest.json')['sha256']}`

Canonical manifest: `{inputs['rir_manifest']['path']}`

SHA-256: `{inputs['rir_manifest']['sha256']}`

Exact selected RIR, speech, code and expected-vector bindings are in run_manifest.json and the local input manifest. Keep all prepared scales and hashes. Re-read live endpoints/settings when ownership is acquired. The hardware runner is implemented and offline-tested; its physical path is untested.

{commands}

After valid physical captures and restored settings, analyze four timelines, O0/O1 routing/levels, telemetry rate/gaps/held values and the two conversation repeats. Then run one paired mono O0/O1 case through unchanged H2 with isolated empty profile roots. No physical capture exists yet; do not substitute old recordings or the dry input for this smoke.

Return the completed compact S3 handoff with every attempted case, restoration readback, metrics, up to four plots and a revised workbook section. No output winner, enrollment or moving-person accuracy, or CM5 claims. No new RIRs, H2 edits, training or full campaign.''')
    artifacts=[]
    for p in report.rglob('*'):
        if p.is_file() and packet not in p.parents:artifacts.append({**cache.bind(p),'role':'prepared_fixture' if 'inputs' in p.parts else 'preflight_evidence'})
    artifacts.extend({**b,'role':'implementation'} for b in code)
    save(packet/'LOCAL_ARTIFACT_INDEX.json',{'schema_version':'1.0','artifacts':artifacts,'physical_raw_captures':[],'reconstruction':'See README_S3.md. Use a new run directory for preflight/prepare. No physical attempt can be reconstructed without recording it.'})
    inventory=[{'path':p.name,'bytes':p.stat().st_size,'sha256':cache.bind(p)['sha256']} for p in sorted(packet.iterdir()) if p.is_file()]
    save(packet/'FILE_INVENTORY.json',{'files':inventory,'excludes':['FILE_INVENTORY.json','SHA256SUMS.txt'],'no_circular_zip_hash':True})
    (packet/'SHA256SUMS.txt').write_text(''.join(cache.bind(p)['sha256']+'  '+p.name+'\n' for p in sorted(packet.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
    archive=SIM/'handoffs'/f'S3_CHATGPT_HANDOFF_{run_id}_PREFLIGHT.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(packet.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for line in z.read('SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1)
            import hashlib
            assert hashlib.sha256(z.read(name)).hexdigest()==digest
        count=len(z.namelist());assert count<=20
    assert archive.stat().st_size<=15*2**20
    receipt={'status':'BLOCKED_PREFLIGHT_CHECKPOINT','zip':cache.bind(archive),'files':count,'crc_and_hash_validation':'PASS','report_section_words':len(narrative.split()),'physical_playback_s':0}
    save(report/'preflight_package_receipt.json',receipt);cache.flush();print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
