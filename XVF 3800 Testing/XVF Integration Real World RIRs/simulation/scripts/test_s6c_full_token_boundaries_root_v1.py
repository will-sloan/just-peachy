"""Independent aggregate/CSV review; see README_TEST_S6C_FULL_TOKEN_BOUNDARIES_ROOT_V1.md."""
from pathlib import Path
import csv
import io
import importlib.util
import json
from datetime import datetime, timezone
import hashlib

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/S6C/20260910T123540Z'
PIN = '444b05dcca471fde78bee9f63a46955d0306a5a9016afc6cb120024cdba19cd6'
def binding(p):
    raw = p.read_bytes()
    return dict(path=str(p), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def main():
    helper = Path(__file__).with_name('s6c_full_token_boundaries_v1.py')
    assert binding(helper)['sha256'] == PIN
    spec = importlib.util.spec_from_file_location('boundary_review_target', helper)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    normalize, layout, edits, _ = m.api()
    checks = []
    def check(label, condition):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
    def rejects(label, fn):
        try:
            fn()
        except ValueError:
            checks.append(label)
        else:
            raise AssertionError(label)
    fields = ['profile_id','stream','identity_tap','case_id','population','normalized_final_text','duration_sec','family_id']
    def encoded(rows):
        output=io.StringIO()
        w=csv.DictWriter(output,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
        return output.getvalue().encode()
    source=dict(slot='n01',routes=[['C065','O0','O0']],declared_table_rows=4,receipt={},scene_table={})
    def scene(cid, words, complete=True):
        segs=[] if words is None else [dict(kind='utterance',speaker_key='p',transcript=words,source_start_sample=0,source_stop_sample=16000)]
        return dict(case_id=cid,family_id='f',segments=segs,all_speaker_reference_complete=complete,transcript_valid=complete,overlap_intervals=[])
    scenes={x['case_id']:x for x in [scene('edge','begin middle end'),scene('single','one'),scene('empty',None),scene('partial','partial words',False)]}
    hypotheses=dict(edge='middle',single='',empty='noise noise',partial='partial words extra')
    rows=[dict(profile_id='C065',stream='O0',identity_tap='O0',case_id=k,population=layout(v)['population'],normalized_final_text=hypotheses[k],duration_sec='1',family_id='f') for k,v in scenes.items()]
    selected=m.selected_rows(encoded(rows),source,list(scenes),normalize)
    cells=[m.cell_result(key,item,source,scenes[key[3]],layout,edits) for key,item in selected.items()]
    bycase={c['case_id']:c for c in cells}
    check('both different boundary words deleted but middle retained', bycase['edge']['token_alignment']['errors']==2 and bycase['edge']['first_reference_token_deleted'] and bycase['edge']['last_reference_token_deleted'])
    check('single missing word counted as one deletion', bycase['single']['token_alignment']['deletions']==1)
    check('single word has two boundary indicators', bycase['single']['first_reference_token_deleted'] and bycase['single']['last_reference_token_deleted'])
    a={x['population']:x for x in m.aggregate(cells)}
    primary=a['PRIMARY_NONOVERLAP']
    check('aggregate boundaries do not double total word deletions',primary['requested_scenes']==2 and primary['boundary_eligible_scenes']==2 and primary['deletions']==3 and primary['first_token_deletion_scenes']==2 and primary['last_token_deletion_scenes']==2)
    empty=a['STRICT_EMPTY_REFERENCE']
    check('empty has zero reference words and two observed insertions',empty['reference_words']==0 and empty['insertions']==2 and empty['alignment_available_scenes']==1)
    check('empty boundaries unavailable with explicit zero eligibility',empty['boundary_eligible_scenes']==0 and empty['first_token_deletion_scenes'] is None and empty['last_token_deletion_scenes'] is None)
    partial=a['INCOMPLETE_REFERENCE']
    check('incomplete retains output count without full edits',partial['hypothesis_words_all_scenes']==3 and partial['errors'] is None and partial['alignment_unavailable_scenes']==1)
    check('all finite mixed-population rows retained',sum(x['requested_scenes'] for x in a.values())==4)
    # A changed output can remain full-reference-unscored; it must not become zero loss.
    other=dict(bycase['partial'],profile_id='C067',normalized_final_text_sha256='different')
    pair=m.compare_cells([bycase['partial'],other],[dict(left=['C065','O0','O0'],right=['C067','O0','O0'])],['partial'])[0]
    check('changed incomplete text has no invented edit delta',pair['normalized_final_text_changed'] and not pair['alignment_available'] and pair['right_minus_left'] is None)
    rejects('paired duration contradiction rejected',lambda:m.compare_cells([bycase['partial'],dict(other,duration_sec=2)],[dict(left=['C065','O0','O0'],right=['C067','O0','O0'])],['partial']))
    outsider=dict(rows[0],profile_id='unselected')
    badsource=dict(source,declared_table_rows=6)
    rejects('duplicate unselected rows cannot evade whole-table accounting',lambda:m.selected_rows(encoded(rows+[outsider,outsider]),badsource,list(scenes),normalize))
    truncated=encoded(rows).decode().splitlines()
    truncated[-1]=','.join(truncated[-1].split(',')[:-1])
    rejects('truncated nontext field cannot silently disappear',lambda:m.selected_rows(('\n'.join(truncated)+'\n').encode(),source,list(scenes),normalize))
    require_header=encoded(rows).decode().splitlines()
    require_header[0]=require_header[0]+',case_id'
    rejects('duplicate header rejected',lambda:m.selected_rows(('\n'.join(require_header)+'\n').encode(),source,list(scenes),normalize))
    draft=REPORT/'full_token_boundaries_v1/draft_v1/SPEC.json'
    assert binding(draft)['sha256']=='30d21752bb3747495fd77da12357a3e1c495c453470ff6960cb41c9118cddb77'
    d=json.loads(draft.read_bytes())
    actual_scenes=m.validate_spec(d)
    check('actual finite draft has 240 cases and 18 requested routes',len(actual_scenes)==240 and d['requested_routes']==18 and sum(len(x['routes']) for x in d['sources'])==18)
    check('three actual future authorities remain unresolved',{x['slot'] for x in d['sources'] if x['receipt'] is None}=={'n08_n10','n12','cross'})
    check('16 same-ASR matched comparisons retained',len(d['pairs'])==16 and all(x['left'][1]==x['right'][1] for x in d['pairs']))
    output=REPORT/'independent_review/full_token_boundary_root_v1'
    output.mkdir(exist_ok=False)
    receipt=dict(status='PASS_SOURCE_AND_FINITE_AGGREGATION_CHECKS',utc=datetime.now(timezone.utc).isoformat(),count=len(checks),checks=checks,helper=binding(helper),helper_readme=binding(helper.with_name('README_S6C_FULL_TOKEN_BOUNDARIES_V1.md')),reviewer=binding(Path(__file__)),reviewer_readme=binding(Path(__file__).with_name('README_TEST_S6C_FULL_TOKEN_BOUNDARIES_ROOT_V1.md')),draft=binding(draft),scope='Tiny mixed-population constructed CSVs and actual finite draft/source metadata. No original score table, prediction, native event, audio, vector or model read; no actual diagnostic result or full-study acceptance.',models_started=0,actual_score_tables_read=False,review_notes=['Inherited pure token aligner is unchanged; this review focuses on new aggregation/coverage boundaries.','SHA-bound draft and later exact plan are the execution authorities; final pending source receipts and all actual output totals require separate review.'])
    p=output/'REVIEW_RECEIPT.json'
    with p.open('x',encoding='utf-8') as f:
        json.dump(receipt,f,indent=2)
        f.write('\n')
    print(json.dumps(binding(p)))
if __name__=='__main__':
    main()

