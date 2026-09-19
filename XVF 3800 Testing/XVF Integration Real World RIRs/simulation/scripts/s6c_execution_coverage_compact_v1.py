"""Complete compact attempt CSV; README_S6C_EXECUTION_COVERAGE_COMPACT_V1.md."""
import argparse,csv,hashlib,io,json,zlib
from pathlib import Path
PIN="db85900c955f1d0cf4634f7a4a41d68e7fd999f4225bc5f13715c6b8eeb21ccd"
FIELDS="physical_id candidate_id profile_id recipe_id case_id asr_tap identity_tap repetition branch epoch execution_mode status classification session_evidence native_session_complete closed_cell_analysis_eligible protected_functions_restored pid creation_time alive started_utc finished_utc elapsed_sec native_elapsed_sec process_cpu_sec audio_duration_sec worker_model_bundle_loads gallery_cache_hit real_gallery_load_observed cue_condition gallery_condition enrollment_tier source_kind error source_row_pointer source_row_sha256".split()
def binding(p,raw):return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(b):
 p=Path(b['path']);raw=p.read_bytes();assert binding(p,raw)==b;return json.loads(raw)
def value(x):
 if x is None:return ''
 if isinstance(x,bool):return str(x).lower()
 assert isinstance(x,(str,int,float));return str(x)
def convert(rows):
 assert len({r['physical_id'] for r in rows})==len(rows)
 out=[]
 for i,r in enumerate(rows):
  assert r['source_row_pointer']=='/'+str(i) and len(r['source_row_sha256'])==64
  missing=[k for k in FIELDS if k in r['missing_original_fields']]
  out.append([value(r[k]) for k in FIELDS]+['FULL_PHYSICAL_SOURCE',json.dumps(missing,separators=(',',':'))])
 header=FIELDS+['local_dependency_id','missing_original_fields_json'];buf=io.StringIO(newline='');csv.writer(buf,lineterminator='\n').writerows([header]+out);raw=buf.getvalue().encode()
 assert list(csv.reader(io.StringIO(raw.decode())))==[header]+out
 return raw
def tests():
 r={k:None for k in FIELDS};r.update(physical_id='attempt',source_row_pointer='/0',source_row_sha256='a'*64,missing_original_fields=['native_session_complete'],status='FAILED',error='original\nerror',alive=False)
 raw=convert([r]);d=list(csv.DictReader(io.StringIO(raw.decode())))[0]
 assert d['status']=='FAILED' and d['error']=='original\nerror' and d['alive']=='false' and d['native_session_complete']=='' and json.loads(d['missing_original_fields_json'])==['native_session_complete']
 try:convert([r,r])
 except AssertionError:pass
 else:raise AssertionError('duplicate ID admitted')
 return dict(status='PASS',checks=7)
def run(result):
 p=Path(result).resolve();raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==PIN;d=json.loads(raw);rows=read(d['outputs']['physical_rows']);assert len(rows)==d['row_count']==5891
 data=convert(rows);out=p.parent/'EXECUTION_COVERAGE_COMPACT.csv'
 with out.open('xb') as f:f.write(data)
 receipt=dict(status='COMPLETE_COMPACT_ALL_ATTEMPTS_EXPORT',rows=len(rows),columns=len(FIELDS)+2,projection_result=binding(p,raw),full_physical_projection=d['outputs']['physical_rows'],local_dependency_id='FULL_PHYSICAL_SOURCE',output=binding(out,data),source=binding(Path(__file__),Path(__file__).read_bytes()),readme=binding(Path(__file__).with_name('README_S6C_EXECUTION_COVERAGE_COMPACT_V1.md'),Path(__file__).with_name('README_S6C_EXECUTION_COVERAGE_COMPACT_V1.md').read_bytes()),tests=tests(),zlib9_size_bytes=len(zlib.compress(data,9)),scope='Every observed physical attempt, in original order. Exact scalar values and nullable/missing semantics retained; no inferred acceptance, exit, native count or cache-to-execution conversion. Full source-row digest/pointer refers to original raw physical metadata via the bound projection. Verbose event counters, model/epoch/input/source bindings and virtual non-attempt owner remain in the exact local projection/result. No source file changed.',verification='All5891 selected rows and every output field roundtrip exactly; no outcome filtering.',new_models_or_scores=0)
 dest=p.parent/'COMPACT_CSV_EXPORT_RECEIPT.json'
 with dest.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps(binding(dest,dest.read_bytes())))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--result',required=True);a=p.parse_args();run(a.result)
