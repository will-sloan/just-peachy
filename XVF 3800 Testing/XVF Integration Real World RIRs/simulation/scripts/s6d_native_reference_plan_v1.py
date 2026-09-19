"""Evaluator-only concatenated reference preparation; README_S6D_NATIVE_REFERENCE_PLAN_V1.md."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import s6d_native_evidence_v1 as E

PINS = {
    'composition': 'bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3',
    'input_index': '97b20d821c671794b24b1f8a4a9d4049fd192767bd0a093309887c279b48e70d',
    'bank': '69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18',
    'q': '8bef70a50354b9cafc43a3410259f4a757f3fbd1748862b1a86a11336fe12895',
    'support_helper': '4ecc9240d897598005719b00b803ea5f1f137bba4b66f1e970b1d098a47a68b5'}


def prepare(sim, output, case_id=None, tap='O0'):
    sim = sim.resolve()
    s6c = sim/'reports/S6C/20260910T123540Z'
    paths = dict(composition=s6c/'long_session/v1/COMPOSITION.json',
                 input_index=sim/'reports/S6B/20260909T230840Z/INPUT_INDEX.json',
                 bank=sim/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json',
                 q=sim/'staging/s6c/20260910T123540Z/source_inventory/v2/Q_OCCURRENCES.json',
                 support_helper=sim/'scripts/s6a_support_metrics.py')
    bindings = {k:E.binding(p) for k,p in paths.items()}
    for k,b in bindings.items(): E.need(b['sha256'] == PINS[k], 'Exact historical authority differs: '+k)
    values = {}
    for k,p in paths.items():
        if k != 'support_helper':
            values[k], actual = E.read_json(p)
            E.need(actual == bindings[k], 'Authority changed during read')
    spec = importlib.util.spec_from_file_location('s6d_exact_support_reference', paths['support_helper'])
    support_api = importlib.util.module_from_spec(spec); spec.loader.exec_module(support_api)
    E.need(E.binding(paths['support_helper']) == bindings['support_helper'], 'Support helper changed')
    composition = values['composition']
    E.need(composition['duration_samples'] == 29238826 and composition['source_count'] == 38
           and composition['duration_sec'] == 1827.426625, 'Exact existing whole composition required')
    inputs = {(r['case_id'],r['stream']):r for r in values['input_index']['rows']}
    bank = {r['case_id']:r for r in values['bank']['scenes']}
    queries = {(r['case_id'],r['segment_index']):r for r in values['q']['rows']}
    E.need(len(inputs) == len(values['input_index']['rows']) == 480
           and len(bank) == len(values['bank']['scenes']) == 240
           and len(queries) == len(values['q']['rows']) == 777, 'Historical denominator differs')
    if case_id is not None:
        item=inputs[case_id,tap]; frames=E.frame(item['duration_sec'])
        composition=dict(duration_samples=frames,duration_sec=item['duration_sec'],source_count=1,
            audio={tap:item['audio']},sequence=[dict(index=0,case_id=case_id,family_id=bank[case_id]['family_id'],
            start_sample=0,end_sample=frames,samples=frames,gap_before_samples=0,inputs={tap:item['audio']})])
    E.need(tap in composition['audio'],'Source tap absent')
    pieces = []; support_bindings = []
    for item in composition['sequence']:
        case = item['case_id']; scene = bank[case]; row = inputs[case,tap]
        E.need(row['audio'] == item['inputs'][tap] and E.frame(row['duration_sec']) == item['samples'],
               'Composition piece differs from admitted input')
        support_doc, sb = E.read_json(row['support']['path']); E.need(sb == row['support'], 'Support bytes differ')
        support_bindings.append(sb); support = support_doc['support']; support_api.validate_support(scene, support)
        shift = support['output_mappings'][tap]['source_with_rir_to_output_offset_samples']
        turns = []
        for t in support['turns']:
            truth = queries[case,t['segment_index']]
            E.need(truth['source_id'] == t['source_id'] and truth['identity'] == t['speaker_key'], 'Q/support occurrence identity differs')
            ranges = {k:support_api.mapped_ranges(t[k], shift, item['samples']) if shift is not None else None
                      for k in ('file_support','active_ranges')}
            turns.append(dict(segment_index=t['segment_index'], source_id=t['source_id'],
                         metadata_identity=truth['identity'], transcript=truth['transcript'], normalized_text=truth['normalized_text'],
                         role=t['role'], whole_clip_bin=t['whole_clip_bin'], activity_available=t['activity_available'],
                         quality_disposition=truth['quality_disposition'], **ranges))
        for t in turns:
            t['sole'] = support_api.subtract(t['active_ranges'], support_api.union([r for o in turns if o is not t for r in o['active_ranges']])) if shift is not None else None
        pieces.append(dict(index=item['index'], case_id=case, family_id=item['family_id'], start_sample=item['start_sample'],
                           end_sample=item['end_sample'], samples=item['samples'], gap_before_samples=item['gap_before_samples'],
                           all_reference_complete=bool(scene['all_speaker_reference_complete']),
                           transcript_valid=scene['transcript_valid'], task_scoring_allowed=scene['task_scoring_allowed'],
                           support_mapping=support['output_mappings'][tap], source=item['inputs'][tap], support=sb,
                           mapped_turns=turns))
    projected = E.shift_reference_pieces(pieces, composition['duration_samples'])
    incomplete = [p['case_id'] for p in pieces if not p['all_reference_complete'] or not p['transcript_valid'] or not p['task_scoring_allowed']]
    result = dict(schema='s6d-host-reference-input-plan.v1', status='PREPARED_EVALUATOR_INPUTS_ONLY',
                  input_audio=composition['audio'][tap],source_tap=tap,source_case_id=case_id,
                  sources=bindings, support_sources=support_bindings, helper=E.binding(__file__), evidence_helper=E.binding(E.__file__),
                  composition_frames=composition['duration_samples'], composition_seconds=composition['duration_sec'],
                  pieces=pieces, projected_turns=projected, occurrence_count=len(projected),
                  distinct_metadata_identities=len({r['metadata_identity'] for r in projected}),
                  population_counts=dict(Counter('COMPLETE' if r['all_reference_complete'] else 'INCOMPLETE_REFERENCE' for r in projected)),
                  incomplete_or_disallowed_cases=incomplete, full_session_all_speaker_wer_eligible=not incomplete,
                  gaps_samples=sum(p['gap_before_samples'] for p in pieces),
                  rule='Saved approximate output mapping once, clip within each actual whole capture, then add exact concatenation start. No word timings, RIR regeneration, waveform copying or new alignment fit.',
                  scope='Reference preparation only. No native result, word/name score or opportunity success is asserted. Incomplete-reference population cannot become a complete-session WER denominator. Q metadata is evaluator-only and must never enter runtime.')
    for k,b in bindings.items(): E.need(E.binding(paths[k]) == b, 'Authority changed before projection commit')
    output.mkdir(parents=True, exist_ok=False)
    with (output/'HOST_REFERENCE_INPUTS.json').open('x', encoding='utf-8') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    compact = {k:result[k] for k in ('schema','status','composition_frames','composition_seconds','occurrence_count',
                 'distinct_metadata_identities','population_counts','incomplete_or_disallowed_cases','full_session_all_speaker_wer_eligible','gaps_samples')}
    compact['reference_projection'] = E.binding(output/'HOST_REFERENCE_INPUTS.json')
    with (output/'REFERENCE_PREPARATION_RECEIPT.json').open('x',encoding='utf-8') as f:
        json.dump(compact,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(compact))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sim',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case-id');p.add_argument('--tap',choices=('O0','O1'),default='O0')
    a=p.parse_args();prepare(a.sim,a.output,a.case_id,a.tap)
