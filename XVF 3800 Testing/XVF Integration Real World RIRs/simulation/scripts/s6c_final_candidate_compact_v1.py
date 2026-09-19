"""Compact complete candidate overlay; README_S6C_FINAL_CANDIDATE_COMPACT_V1.md."""
import argparse,csv,hashlib,io,json,zlib
from pathlib import Path
PIN='8283a245fced3dd4be45b0b6b988cca2145b48cbe108a9961a34b5be89ddf1f0'
FIELDS='candidate_id origin family registered_parent recipe_id registered_title registered_routes original_registration_row_json original_registration_row_sha256 original_registration_disposition exact_route_settings_provenance_json final_scientific_disposition final_supported_interpretation_and_gaps final_operating_presets_json'.split()
def binding(p,raw):return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def convert(rows):
 assert len({r['candidate_id'] for r in rows})==len(rows)
 out=[]
 for i,r in enumerate(rows):
  ids=json.loads(r['final_supported_interpretation_and_gaps'])['evidence_ids'];assert len(ids)==len(set(ids))
  out.append([r[k] for k in FIELDS]+[hashlib.sha256(canonical(r)).hexdigest(),'FULL_FINAL_CANDIDATE_EVIDENCE','/'+str(i)])
 values=[FIELDS+['full_candidate_row_sha256','local_dependency_id','full_route_evidence_pointer']]+out;buf=io.StringIO(newline='');csv.writer(buf,lineterminator='\n').writerows(values);raw=buf.getvalue().encode();assert list(csv.reader(io.StringIO(raw.decode())))==values
 return raw
def tests():
 r={k:'' for k in FIELDS};r.update(candidate_id='C083',final_scientific_disposition='EXACT_ALIAS_NOT_EXECUTED',final_supported_interpretation_and_gaps=json.dumps(dict(evidence_ids=['a'],limitations=['no own execution'],interpretation='alias')),final_operating_presets_json='[{"status":"NOT_SELECTED_FOR_OPERATION"}]')
 d=list(csv.DictReader(io.StringIO(convert([r]).decode())))[0];assert d['candidate_id']=='C083' and d['final_scientific_disposition']==r['final_scientific_disposition'] and d['full_candidate_row_sha256']==hashlib.sha256(canonical(r)).hexdigest()
 try:convert([r,r])
 except AssertionError:pass
 else:raise AssertionError('Duplicate candidate admitted')
 return dict(status='PASS',checks=4)
def run(receipt):
 p=Path(receipt).resolve();raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==PIN;d=json.loads(raw);assert d['candidate_count']==240 and d['whole_study_complete'] is False
 b=next(x for x in d['outputs'] if x['path'].endswith('CANDIDATE_DISPOSITION_FINAL.csv'));q=Path(b['path']);buf=q.read_bytes();assert binding(q,buf)==b;csv.field_size_limit(32*1024*1024);rows=list(csv.DictReader(io.StringIO(buf.decode())));assert len(rows)==240
 data=convert(rows);out=p.parent/'CANDIDATE_DISPOSITION_COMPACT.csv'
 with out.open('xb') as f:f.write(data)
 proof=dict(status='COMPLETE_COMPACT_ALL240_CANDIDATE_EXPORT',rows=240,columns=len(FIELDS)+3,full_assembly_receipt=binding(p,raw),full_candidate_csv=b,full_route_evidence=next(x for x in d['outputs'] if x['path'].endswith('FINAL_ROUTE_EVIDENCE.json')),output=binding(out,data),local_dependency_id='FULL_FINAL_CANDIDATE_EVIDENCE',source=binding(Path(__file__),Path(__file__).read_bytes()),readme=binding(Path(__file__).with_name('README_S6C_FINAL_CANDIDATE_COMPACT_V1.md'),Path(__file__).with_name('README_S6C_FINAL_CANDIDATE_COMPACT_V1.md').read_bytes()),tests=tests(),zlib9_size_bytes=len(zlib.compress(data,9)),whole_study_complete=False,scope='Exact all240 selected-column export; original160 registration rows and route settings provenance retained, final interpretation/limits and complete evidence ID lists retained. Large per-evidence source-row bodies remain in exact local CSV/JSON with full candidate-row digest and JSON pointer. No new metrics, disposition changes, execution inference or acceptance.',new_models_or_scores=0)
 dest=p.parent/'COMPACT_EXPORT_RECEIPT.json'
 with dest.open('x',encoding='utf-8') as f:json.dump(proof,f,indent=2);f.write('\n')
 print(json.dumps(binding(dest,dest.read_bytes())))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--receipt',required=True);run(p.parse_args().receipt)
