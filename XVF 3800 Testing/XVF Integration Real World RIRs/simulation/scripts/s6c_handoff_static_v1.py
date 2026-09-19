"""Bounded source/reference appendix; see README_S6C_HANDOFF_STATIC_V1.md."""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import string
import tempfile

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S6C/20260910T123540Z'
PINS = {
 'reports/S6B/20260909T230840Z/LOCAL_ARTIFACT_INDEX.json': '2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e',
 'reports/S6C/20260910T123540Z/enrollment_inventory/v2/SOURCE_RESULTS_SUMMARY_V1.json': '064cc98ee766ce344caaa5af4bf695582308f303932e0e94d02046f0a4516dce',
 'reports/S6C/20260910T123540Z/enrollment/ENROLLMENT_RESULTS_SUMMARY_V1.json': 'a4f25cbbcbbf8154675fed76acd8b63dd23bbcec73e02e3d8f424efebfb8ee03',
 'reports/S6C/20260910T123540Z/enrollment/common30_v1/COMMON30_GALLERY_COMPLETION.json': '3acdf09a67893e74d2d85d7d80704f9e63301b89f8d29d3294aea057f20c2ed7',
 'rir_library/v1/RIR_MANIFEST.json': '468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546',
 'reports/S2/20260908T203309Z/RESULTS.json': 'de94ed9010fc04b0508cfc3977afebcc256289c11c483a18c3e906fc737b7793',
 'reports/S0/20260908T181703Z/metadata_corrections.json': '469832e0547549788fce35fa1ae39276e3e2a7a46e1a52c8f0307a08db846169',
 'reports/S0/20260908T181703Z/validation_results.json': '9fe0f86116e4b266991081fd5fb3d0b62a4d11e342dc346931b178a2d61918af',
 'scripts/s6a_text_metrics.py': 'c7614c33c04cba1f47660c10235198c8cd697963eb42b12a3656b503a8c884cd',
 'scripts/s4_h2_analysis.py': '0b5d8a227ca87c4dcee48db8118de35444fb32217291bf022feb458f0982d1a0',
}

def need(ok, message):
    if not ok: raise ValueError(message)

def binding(path, raw):
    return dict(path=str(Path(path).resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

class Reader:
    def __init__(self): self.rows = {}; self.cache = {}
    def raw(self, declared):
        p = Path(declared['path']).resolve()
        need(p.suffix.lower() in {'.json', '.csv', '.py', '.md'}, 'Metadata/code only: '+str(p))
        key = str(p)
        if key not in self.cache:
            need(p.stat().st_size <= 32 * 1024**2, 'Unexpected large metadata input')
            self.cache[key] = p.read_bytes()
        raw = self.cache[key]; actual = binding(p, raw)
        need(actual['sha256'] == declared['sha256'], 'Changed declared bytes: '+key)
        if 'bytes' in declared: need(actual['bytes'] == declared['bytes'], 'Changed declared length')
        self.rows[key] = actual
        return raw
    def json(self, declared): return json.loads(self.raw(declared))
    def pinned(self, rel): return self.json(dict(path=str(SIM/rel), sha256=PINS[rel]))

def selected_function(reader, rel, name, namespace):
    raw = reader.raw(dict(path=str(SIM/rel), sha256=PINS[rel]))
    tree = ast.parse(raw.decode('utf-8-sig'))
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    need(len(fn) == 1, 'Exactly one inherited pure function required')
    # Execute only the two hash-pinned pure reference helpers, never module imports/scorers/models.
    exec(compile(ast.Module(body=fn, type_ignores=[]), str(SIM/rel), 'exec'), namespace)
    return namespace[name]

def grid(rows, scenes):
    keys = [(r['case_id'], r['stream']) for r in rows]
    want = {(cid, tap) for cid in scenes for tap in ('O0', 'O1')}
    need(len(keys) == len(set(keys)) and set(keys) == want, 'Exact unique all-scene two-tap input grid required')
    return {k:r for k,r in zip(keys, rows)}

def save_new(path, raw):
    with Path(path).open('xb') as f: f.write(raw)

def json_bytes(value): return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')

def collect(out):
    need(not out.exists(), 'Use a new output directory; existing audit is immutable')
    rd = Reader()
    idx = rd.pinned('reports/S6B/20260909T230840Z/LOCAL_ARTIFACT_INDEX.json')
    sealed = {r['entry_id']:r for r in idx['artifacts']}
    inputs = rd.json(sealed['L0119']); bank = rd.json(sealed['L0159'])
    historical = rd.json(inputs['source_reference_audit_reused'])
    rd.raw(historical['coverage_csv'])
    ss = rd.pinned('reports/S6C/20260910T123540Z/enrollment_inventory/v2/SOURCE_RESULTS_SUMMARY_V1.json')
    es = rd.pinned('reports/S6C/20260910T123540Z/enrollment/ENROLLMENT_RESULTS_SUMMARY_V1.json')
    for b in ss['sources'] + es['sources']: rd.raw(b)
    ecq_binding = next(b for b in ss['sources'] if Path(b['path']).name == 'ECQ_MANIFEST.json')
    ecq = rd.json(ecq_binding)
    prep = rd.json(ecq['preparation_code_admission'])
    inventory = rd.json(prep['original_inventory_receipt'])
    for b in prep['metadata_executor_snapshot'].values(): rd.raw(b)
    rights = rd.json(inventory['authorities']['rights'])
    queries = rd.json(inventory['outputs']['query_manifest'])['rows']
    rd.raw(inventory['authorities']['reference_manifest'])
    capture_reference = rd.json(inventory['authorities']['reference_captures'])
    need(inventory['authorities']['s6b_index']['sha256'] == PINS['reports/S6B/20260909T230840Z/LOCAL_ARTIFACT_INDEX.json'], 'S6B authority mismatch')
    need(ecq['query_manifest'] == inventory['outputs']['query_manifest'], 'Query authority mismatch')
    ns = {'string':string, 'defaultdict':defaultdict}
    normalize = selected_function(rd, 'scripts/s4_h2_analysis.py', 'normalize', ns)
    layout = selected_function(rd, 'scripts/s6a_text_metrics.py', 'reference_layout', ns)
    scenes = {s['case_id']:s for s in bank['scenes']}
    need(len(scenes) == len(bank['scenes']) == 240, '240 unique scenes required')
    by_input = grid(inputs['rows'], scenes)
    qby = defaultdict(list)
    for q in queries: qby[q['case_id']].append(q)
    need(set(qby) <= set(scenes), 'Query outside canonical bank')
    qkeys = [(q['case_id'],q['segment_index']) for q in queries]
    need(len(qkeys) == len(set(qkeys)) == 777, '777 unique scheduled source occurrences required')
    rows = []; support_bindings = []
    for cid, scene in sorted(scenes.items()):
        lo = layout(scene); a = by_input[cid,'O0']; b = by_input[cid,'O1']
        need(a['support'] == b['support'], 'Two taps must share exact source reference support')
        support = rd.json(a['support'])['support']; support_bindings.append(a['support'])
        need(support['case_id'] == cid, 'Support case mismatch')
        utterances = [(i,s) for i,s in enumerate(scene['segments']) if s.get('kind') == 'utterance']
        qrows = {q['segment_index']:q for q in qby[cid]}
        need(set(qrows) == {i for i,s in utterances}, 'Source occurrence/utterance mismatch')
        for i,s in utterances:
            q = qrows[i]
            need((q['source_id'],q['identity'],q['normalized_text']) ==
                 (s['source_id'],s['speaker_key'],normalize(s['transcript'])), 'Query reference mismatch')
        for r in (a,b): need(r['already_gained'] is True and r['input_gain'] == 1, 'Inherited once-gained route required')
        incomplete = lo['population'] == 'INCOMPLETE_REFERENCE'
        complete_nonempty = lo['population'] in {'PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'}
        target = ' '.join(normalize(t['transcript']) for t in sorted(scene.get('target_references',[]), key=lambda x:x['start_sample']))
        rows.append(dict(case_id=cid, family_id=scene['family_id'], historical_split=scene['split'],
          source_partition=scene['source_partition'], population=lo['population'],
          complete_all_speaker_reference=lo['complete'], scheduled_overlap=lo['overlap'],
          scheduled_source_occurrences=len(utterances), reference_metadata_ids=sorted(lo['streams']),
          normalized_reference_words=len(lo['reference'].split()), target_only_reference_words=len(target.split()) if incomplete else None,
          primary_word_denominator=len(lo['reference'].split()) if lo['population']=='PRIMARY_NONOVERLAP' else 0,
          complete_word_denominator=len(lo['reference'].split()) if complete_nonempty else 0,
          lexical_metric_scope='target_only_diagnostic' if incomplete else 'overlap_mimo_diagnostic' if lo['overlap'] else 'primary' if lo['reference'] else 'strict_empty_insertions_only',
          attributed_complete_text_valid=complete_nonempty,
          reference_problems=lo['problems'], inherited_coverage_limitations=scene['coverage_limitations'],
          estimated_activity_only_for_scoring=scene['estimated_activity_only_for_scoring'],
          nominal_source_duration_sec=scene['duration_s'], O0_capture_duration_sec=a['duration_sec'], O1_capture_duration_sec=b['duration_sec'],
          support_sha256=a['support']['sha256'], O0_inherited_pcm_sha256=a['audio_pcm_sha256'],O1_inherited_pcm_sha256=b['audio_pcm_sha256'],
          O0_inherited_gain=a['historical_gain_applied_once'],O1_inherited_gain=b['historical_gain_applied_once'],
          canonical_rir_ids=sorted({s['rir_id'] for i,s in utterances})))
    pop = Counter(r['population'] for r in rows)
    need(pop == dict(PRIMARY_NONOVERLAP=156,COMPLETE_OVERLAP=47,INCOMPLETE_REFERENCE=26,STRICT_EMPTY_REFERENCE=11), 'Population drift')
    need(sum(r['primary_word_denominator'] for r in rows)==4560, 'Primary reference denominator drift')
    need(sum(r['complete_word_denominator'] for r in rows)==6016, 'Complete reference denominator drift')
    need(historical['status']=='PASS' and historical['scheduled_instances']==777 and historical['all_scene_count']==240, 'Historical reference audit incomplete')
    need(historical['populations']==dict(primary_nonoverlap=156,overlap_complete=47,ambient_incomplete=26,strict_empty=11), 'Historical population mismatch')
    people = {q['identity'] for q in queries}; sourceids={q['source_id'] for q in queries}
    need(len(people)==43 and len(sourceids)==449, 'Canonical source roster drift')
    accepted = ecq['accepted_sources']; role_counts=Counter(r['s6c_role'] for r in accepted)
    need(len(accepted)==752 and role_counts=={'E':385,'C':367}, 'E/C role accounting drift')
    need(all(not v for v in ecq['leakage_audit']['exact_intersections'].values()), 'Reported E/C/Q exact intersection nonempty')
    need(rights['L2_ARCTIC']=='EXCLUDED_BY_USER_REQUEST', 'L2 exclusion drift')
    corpus = []
    for dataset in sorted({q['dataset'] for q in queries}):
        qr=[q for q in queries if q['dataset']==dataset]; ar=[r for r in accepted if r['dataset']==dataset]
        corpus.append(dict(dataset=dataset,Q_occurrences=len(qr),Q_unique_sources=len({q['source_id'] for q in qr}),
          Q_metadata_ids=len({q['identity'] for q in qr}),E_clips=sum(r['s6c_role']=='E' for r in ar),
          C_clips=sum(r['s6c_role']=='C' for r in ar), E_available_tiers=[r for r in ss['tiers'] if r['dataset']==dataset],
          inherited_rights=rights['speech'][dataset]))
    lib=rd.pinned('rir_library/v1/RIR_MANIFEST.json'); s2=rd.pinned('reports/S2/20260908T203309Z/RESULTS.json')
    corrections=rd.pinned('reports/S0/20260908T181703Z/metadata_corrections.json')
    s0=rd.pinned('reports/S0/20260908T181703Z/validation_results.json')
    recordmap={r['run_id']:r for r in lib['records']}
    need(len(recordmap)==lib['count']==121 and all(r['original_acquisition_status'] in {'PASS','REVIEW'} for r in recordmap.values()), 'Canonical RIR eligibility drift')
    excluded={r['run_id'] for r in lib['exclusions']['historical_exclusions']} | set(lib['exclusions']['scope_excluded_ids'])
    need(not (set(recordmap)&excluded), 'Excluded measurement entered canonical library')
    need(set(bank['selected_rirs']) <= set(recordmap), 'Bank uses noncanonical RIR')
    for rid, r in recordmap.items():
        g=r['geometry']; need(0<g['source_distance_m_effective']<=5, 'Distance outside user range')
        need(g['speaker_angle_deg_original']==g['speaker_angle_deg_effective'], 'Angle silently changed')
    need(len(corrections['corrections'])==2 and corrections['angle_corrections']==[], 'Unexpected correction overlay')
    for c in corrections['corrections']:
        need(c['original_value']==100 and c['effective_value']==1 and c['original_files_modified'] is False, 'Human correction drift')
        need(recordmap[c['run_id']]['geometry']['source_distance_m_effective']==1, 'Correction not active in library')
    common = rd.pinned('reports/S6C/20260910T123540Z/enrollment/common30_v1/COMMON30_GALLERY_COMPLETION.json')
    need(common['status']=='COMPLETE','Common-cohort enrollment not complete')
    commonplan=rd.json(common['plan'])
    common_outputs=[rd.json(b) for b in common['outputs']]
    audit=dict(schema='s6c-static-source-transcript-audit.v1',status='PASS_STATIC_SOURCE_AND_REFERENCE_ACCOUNTING',
      created_utc=datetime.now(timezone.utc).isoformat(),scope='Sealed metadata and inherited validation only; no audio/model reread, prediction quality, live runtime or final S6C completion claim.',
      canonical=dict(scenes=240,tap_views=480,scheduled_Q_occurrences=777,unique_Q_sources=449,corpus_qualified_metadata_ids=43,
        populations=dict(pop),primary_scenes=156,primary_reference_words=4560,complete_nonempty_scenes=203,complete_reference_words=6016,
        incomplete_scenes=26,strict_empty_scenes=11,families=len({r['family_id'] for r in rows})),
      E_C_Q=dict(accepted_whole_clips=752,role_counts=dict(role_counts),corpus_rows=corpus,tiers=ss['tiers'],
        calibration_people_30seconds=ss['calibration_people30seconds'],calibration_people_smaller=ss['calibration_people_smaller'],
        calibration_people_none=ss['calibration_people_none'],rejected_candidates=ss['rejected'],
        optional_reference_clips_used=ss['optional_reference_clips_used'],optional_physical_reference_captures=inventory['optional_reference_captures'],
        leakage_audit=ecq['leakage_audit'],native_enrollment=es['native'],calibration=es['calibration'],limitations=es['limitations'],
        common_cohort_addition=dict(completion=common['status'],output_bindings=common['outputs'],plan=common['plan'],
          scope='Six fixed common-cohort gallery assignments reuse existing templates. No new source decoding, enrollment model or Q measurement is claimed here.'),
        historical_exclusion_reason_counts_nonexclusive=inventory['exclusion_reason_counts_nonexclusive']),
      measurement_provenance=dict(scope='Revalidated canonical metadata and bound inherited acquisition/extraction evidence; raw captures/RIR WAVs are not rehashed.',
        canonical_RIRs=121,bank_selected_RIRs=len(bank['selected_rirs']),original_status_counts=dict(Counter(r['original_acquisition_status'] for r in recordmap.values())),
        extraction_outcomes=lib['outcome_counts'],historical_exclusions=len(lib['exclusions']['historical_exclusions']),additional_scope_exclusions=len(lib['exclusions']['scope_excluded_ids']),
        effective_distance_range_m=[min(r['geometry']['source_distance_m_effective'] for r in recordmap.values()),max(r['geometry']['source_distance_m_effective'] for r in recordmap.values())],
        user_confirmed_corrections=corrections,original_acquisition_validation=s0,carried_S2_limits={k:s2[k] for k in ['limitation_counts','spatial_hil_deferred_ids','independent_acoustic_validation']},
        angle_scope='Original signed central labels retained; user-estimated +/-5 degrees is not calibrated accuracy. Linear-array front/rear ambiguity and nominal native transform remain. No new sign correction or exact geometry proof.',
        context=lib['context']),
      metric_validity=dict(primary='156 complete, nonoverlap scenes: 4560 normalized reference words once per tap/profile; WER/CER primary scope.',
        complete='203 complete nonempty scenes: 6016 reference words. Includes47 overlap scenes; inherited MIMO/cp text diagnostics do not establish time-resolved overlap recall or DER.',
        incomplete='26 environmental scenes retain only target-text diagnostic where available; no complete all-speaker WER/cp denominator.',
        empty='11 intentional empty-reference scenes: raw insertions/rate only; zero denominator is not WER=0.',
        naming='Anonymous mapped speaker accuracy is separate from enrolled known-name accuracy. Gallery/source absence remains explicit.',
        support='Activity windows are numerical estimates, not phonetic/word timing truth. Both taps share one source support binding; exact capture offset stays in bound support.'),
      bindings=list(rd.rows.values()),carried_payload_authorities_not_rehashed=dict(input_index_audio_and_native_fields='Contained in sealed L0119',
        raw_source_and_decoded_bindings='Contained in sealed transcript coverage receipt, Q manifest and ECQ manifest',
        source_inventory_authorities=inventory['authorities'],preparation_code_aliases=prep.get('alias_resolution',[])),
      collector=binding(__file__,Path(__file__).read_bytes()),readme=binding(Path(__file__).with_name('README_S6C_HANDOFF_STATIC_V1.md'),Path(__file__).with_name('README_S6C_HANDOFF_STATIC_V1.md').read_bytes()))
    out.mkdir(parents=True)
    buf=io.StringIO(newline=''); w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader()
    for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    csvraw=buf.getvalue().encode('utf-8'); csvpath=out/'ALL240_REFERENCE_COVERAGE.csv';save_new(csvpath,csvraw)
    audit['coverage_csv']=binding(csvpath,csvraw)
    summary=render_summary(audit)
    sp=out/'SOURCE_COVERAGE_RIGHTS_AND_DOMAINS.md';save_new(sp,summary.encode('utf-8'));audit['summary']=binding(sp,summary.encode('utf-8'))
    save_new(out/'SOURCE_AND_TRANSCRIPT_AUDIT.json',json_bytes(audit))
    print(json.dumps(dict(status=audit['status'],output=str(out),canonical=audit['canonical'],metadata_files_verified=len(rd.rows))))

def render_summary(a):
    lines=['# Source and transcript evidence for the S6C handoff','',a['scope'],'',
      'The canonical bank contains **240 scenes, 480 tap views, 777 scheduled source occurrences, 449 unique source clips and 43 corpus-qualified metadata identities**. Corpus identifiers do not prove unique biological people across datasets.','',
      '| Population | Scenes | Reference words | Valid interpretation |','|---|---:|---:|---|',
      '| Primary nonoverlap |156|4560|Primary WER/CER|','| Complete overlap |47|1456|Inherited MIMO/cp text diagnostics|',
      '| Incomplete environmental reference |26|Not pooled|Target-only text diagnostic|','| Intentional empty reference |11|0|Insertion counts/rates; WER undefined|','',
      'The complete nonempty union is **203 scenes / 6016 reference words**. Counts are once per source scene; O0/O1 and repeated candidates do not create independent reference material. Old development/reserve tags are preserved, and all240 use is explicitly authorized for this research.','',
      '| Corpus | Q occurrences | Unique Q clips | Metadata IDs | E clips | C clips |','|---|---:|---:|---:|---:|---:|']
    for r in a['E_C_Q']['corpus_rows']: lines.append(f"|{r['dataset']}|{r['Q_occurrences']}|{r['Q_unique_sources']}|{r['Q_metadata_ids']}|{r['E_clips']}|{r['C_clips']}|")
    lines += ['', 'E is enrollment, C is calibration, and Q is the unchanged query bank. **752 whole E/C clips (385 E, 367 C)** passed the inherited source preparation. E tiers have **37/30/28 available identities at 5/15/30 seconds**. CMU contributes18 and HiFiTTS10 at every tier; Common Voice contributes9/2/0. C has28 identities with30seconds,8 with less, and7 with none. Unavailable material is not filled with another speaker.', '',
      'Native enrollment produced95 templates:73 PASS and22 REVIEW_LOW_CONSISTENCY retained. The original2,169 gallery condition/tier/case rows include344 explicit empty rows. Six additive fixed common-cohort assignments reuse templates. The inherited1976 ReDim calls belong to enrollment/C fitting, not new work by this collector. C fitting uses known members of each roster; it is not unknown-stranger validation.', '',
      'The two excluded E/C candidates are CV26_common_voice_en_18596 and HIFI_11614_littleminister_40_barrie_0071 (source rail/overrange). L2 ARCTIC remains excluded. All777 Q occurrences remain. Exact checked E/C/Q source-ID, byte, normalized-text and prompt intersections are empty. Three HiFiTTS identities (11697,6671,9136) use different chapters of the same non-Q book for E and C. This is shared-book dependence, not independent-session evidence. Transformed aliases, unknown crops and cross-corpus biological identity were not exhaustively ruled out.', '',
      'Rights statements below are inherited local audit assertions, with exact notice/source bindings in the JSON; this appendix performs no new legal clearance. CMU ARCTIC is recorded as permissive with attribution/notices and missing per-voice notices disclosed. HiFiTTS is recorded as CC-BY-4.0 with NVIDIA/authors and LibriVox/Gutenberg source attribution. Common Voice is recorded as CC0 with its release binding and prohibition on contributor identification. Training, redistribution and voice-synthesis consent are not automatically cleared by this study.', '',
      'Enrollment uses clean source clips; Q uses simulated room convolution followed by captured XVF outputs. This is a clean-to-processed domain mismatch. The33 optional reference clips used are source material; no optional physical reference capture was performed. No private/default profile gallery is used.', '',
      'The inherited canonical RIR library has121 records (95 EXTRACTED,26 EXTRACTED_WITH_LIMITATIONS), acquired only from PASS/REVIEW formal measurements.52 historical pilot/diagnostic/ineligible measurements and6 later scope exclusions stay excluded. Effective distances are0.46–4.07m. The two +20-degree low-table R05 records retain raw100m alongside the user-confirmed1.00m effective correction. Signed angle centers are unchanged. Manual +/-5-degree labels and nominal native-angle transforms are not independent acoustic calibration; front/rear ambiguity remains.', '',
      'The machine-readable CSV has one row per scene. Identifiers, family and historical split/source partition come from the canonical bank; population/word counts use the unchanged inherited normalization/reference-layout functions. `normalized_reference_words` is observed annotated text even when incomplete; only `primary_word_denominator` and `complete_word_denominator` enter their stated populations. Zero in either denominator means ineligible for that pool, not error-free recognition. Blank `target_only_reference_words` means not applicable. List fields are JSON strings; booleans are literal True/False. `reference_problems` and `inherited_coverage_limitations` retain actual exclusions. Nominal source duration and measured O0/O1 capture durations are separate. PCM hashes/gains are inherited bindings, not a new audio hash audit. `support_sha256` binds the exact source support/offset; activity remains estimated. `canonical_rir_ids` lists scheduled utterance RIRs.','',
      'Source bindings form a finite DAG: this audit binds its CSV/summary and consumed metadata/code; it does not bind itself or final S6C results. Raw sources, WAVs, models and native journals are not opened. No accuracy, runtime-finalist, full-campaign completion or new physical validation is asserted.','']
    return '\n'.join(lines)

def self_test():
    checks=0
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'x.json';raw=b'{"v":1}';p.write_bytes(raw);b=binding(p,raw)
        need(Reader().json(b)=={'v':1},'Exact buffer read');checks+=1
        p.write_bytes(b'{"v":2}')
        try:Reader().json(b)
        except ValueError:checks+=1
        else:raise AssertionError('Changed same-length bytes accepted')
        try:save_new(p,b'x')
        except FileExistsError:checks+=1
        else:raise AssertionError('Overwrite allowed')
    r=[dict(case_id='x',stream=t) for t in ('O0','O1')];grid(r,{'x'});checks+=1
    for bad in (r+[r[0]],r[:1],r+[dict(case_id='y',stream='O0')]):
        try:grid(bad,{'x'})
        except ValueError:checks+=1
        else:raise AssertionError('Invalid grid accepted')
    return dict(status='PASS',checks=checks,models_called=0)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=REPORT/'handoff_static_v1');ap.add_argument('--self-test',action='store_true');a=ap.parse_args()
    if a.self_test:print(json.dumps(self_test()))
    else:collect(a.output.resolve())

if __name__=='__main__':main()
