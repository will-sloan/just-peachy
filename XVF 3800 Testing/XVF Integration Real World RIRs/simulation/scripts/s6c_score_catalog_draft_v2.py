"""Draft-only explicit compact score catalog; README_S6C_SCORE_CATALOG_DRAFT_V2.md."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,importlib,io,json,sys
HERE=Path(__file__).resolve().parent;SIM=HERE.parent;REPORT=SIM/'reports/S6C/20260910T123540Z'
CODE_SHA='2c9bd02ec318a34fc2f7a0d07004a5b099c2afd5f404a6a362e3302bca747406'
SPEC_SHA='769f201ae9d5f116028f0f94a50f35eca0e0324dd85e21dfdc9a97668a1eb244'
CORE_FILES={'SCENE_RESULTS.csv','PROFILE_RESULTS.csv','SHORT_REPLY_RESULTS.csv','PAIRED_COMPARISONS.csv','TRACK_LIFECYCLE_RESULTS.csv'}
NAME_FILES={'TURNS.csv','PEOPLE.csv','QUERIES.csv','RETAINED_ROWS.csv','NAME_REVISIONS.csv','EMPTY_CONTROL_RESULTS.csv','PROFILE_NAME_RESULTS.csv','COVERAGE.csv'}
NAME_DETAIL_MAX=8*2**20
HEADER_MAX=64*2**10

def require(ok,msg):
 if not ok:raise ValueError(msg)
def binding(path,raw=None):
 p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw;return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def save(path,value):
 raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
 with path.open('xb') as f:f.write(raw)
 return binding(path,raw)

def run(output):
 require(not output.exists(),'Fresh draft directory required');source=HERE/'s6c_score_tables.py';require(binding(source)['sha256']==CODE_SHA,'Held collector changed')
 mod=importlib.import_module('s6c_score_tables');require(Path(mod.__file__).resolve()==source,'Wrong collector import')
 sources=[];cache={};previews=[];index=[];inputs=[];core_count=0;name_count=0;excluded=[]
 def read(p,expected=None):
  p=Path(p).resolve();key=str(p)
  if key not in cache:
   raw=p.read_bytes();require(len(raw)<=128*2**20,'Bounded JSON authority');b=binding(p,raw);value=mod.parse_json(raw.decode('utf-8-sig'));cache[key]=(value,b);sources.append(b)
  value,b=cache[key]
  if expected:require(b==expected,'Exact authority bytes differ '+key)
  return value,b
 oldp=REPORT/'compact_score_tables/RECOMMENDED_INPUT_CATALOG_DRAFT_V1.json';old,oldb=read(oldp)
 spec,specb=read(REPORT/'candidate_support/SPEC_WORKING_V1.json');require(specb['sha256']==SPEC_SHA and len(spec['authorities'])==31,'Exact31 audited core authorities')
 review,reviewb=read(REPORT/'independent_review/SCORE_TABLES_COMPONENT_REVIEW_V1.json')
 for b in review['held_sources']:require(binding(b['path'])==b,'Previously reviewed collector/README bytes changed')
 sources+=review['held_sources']
 def preview(b):
  p=Path(b['path']);before=p.stat()
  require(before.st_size==b['bytes'],'CSV current size differs from authority '+str(p))
  with p.open('rb') as f:raw=f.readline(HEADER_MAX+1)
  require(len(raw)<=HEADER_MAX and (raw.endswith(b'\n') or len(raw)==b['bytes']),'Header exceeds bound')
  after=p.stat();require((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'CSV changed during header preview')
  text=raw.decode('utf-8-sig');header=next(csv.reader(io.StringIO(text,newline=''),strict=True),[])
  valid=bool(header) and len(header)==len(set(header)) and all(k and not k.startswith('__collection_') for k in header)
  entry=dict(source_table=b,header_utf8=text,header_bytes=len(raw),header_sha256=hashlib.sha256(raw).hexdigest(),columns=header,valid_nonempty_header=valid,observed_file_bytes=before.st_size,full_table_bytes_verified=False,scope='Bounded header only; declared whole CSV hash not renewed. Future export must verify exact whole source buffer.')
  previews.append(entry);return header,valid
 def scope(identifier,kind):
  if identifier.startswith('full_') or identifier=='all_n00_controls_core_v2' or identifier=='S6B_full_analysis_v1':return 'full240'
  if 'split' in identifier:return 'split'
  if identifier=='family_gate6_native_core_v3':return 'gate6'
  if identifier in ('S6B_challenge_analysis_v1','smoke_names_v1') or '_native_' in identifier:return 'native'
  return 'panel56'
 def admit(identifier,ab,wanted,kind,scope_label):
  value,b=read(ab['path'],ab);require(value['schema']==wanted['schema'] and value['status']==wanted['status'] and wanted['status'].startswith('COMPLETE'),'Completed schema differs')
  require(value['requested']==value['scored'],'Completed authority has unscored outputs')
  selected=[];original=value['tables'];require(isinstance(original,list),'Explicit original table list')
  for i,tb in enumerate(original):
   require(set(tb)=={'path','bytes','sha256'} and Path(tb['path']).suffix=='.csv','Exact original CSV table binding required')
   name=Path(tb['path']).name;desired=name in (CORE_FILES if kind=='core' else NAME_FILES)
   entry=dict(source_id=identifier,authority=b,authority_schema=value['schema'],authority_status=value['status'],binding_pointer='/tables/'+str(i),table_name=name,table_binding=tb,selected=False,omitted_table_reason=None)
   if not desired:entry['omitted_table_reason']='Not in requested compact core table set; exact local table retained with original authority. No outcome-based omission.'
   elif kind=='names' and name not in {'PROFILE_NAME_RESULTS.csv','EMPTY_CONTROL_RESULTS.csv'} and tb['bytes']>NAME_DETAIL_MAX:entry['omitted_table_reason']='Name detail table exceeds prospectively declared8MiB per-table draft bound; retain exact local table index. No row filtering.'
   else:
    header,valid=preview(tb)
    if not valid:entry['omitted_table_reason']='Original table has no supported nonempty CSV header; held collector requires a header even for intact copies. Preserve original binding for explicit local/raw-file companion admission; do not invent columns.'
    else:
     compact=kind=='core' and name=='SCENE_RESULTS.csv';keys=['profile_id','stream']+(['identity_tap'] if 'identity_tap' in header else [])+['case_id','population'] if compact else []
     omissions=[n for n in ['recipe_costs','strata','normalized_final_text'] if n in header] if compact else []
     require(set(keys)<=set(header),'Explicit compact key missing')
     selected.append(dict(name=Path(name).stem+('_COMPACT' if compact else ''),binding_pointer='/tables/'+str(i),mode='compact_rows' if compact else 'copy_intact',row_key=keys,omit_fields=omissions))
     entry.update(selected=True,mode=selected[-1]['mode'],omit_fields=omissions,source_columns=len(header),retained_source_columns=len(header)-len(omissions),row_key=keys)
   index.append(entry)
  require(selected,'No usable selected table')
  inputs.append(dict(source_id=identifier,scope_kind=scope(identifier,kind),scope_label=scope_label,authority=b,expected_authority=wanted,tables=selected))
 for item in spec['authorities']:
  identifier=item['source_id'];admit(identifier,item['authority'],dict(schema=item['expected_schema'],status=item['expected_status']),'core',item['scope_label']+'; core score authority kept separate, no pooling or physical-run inference.');core_count+=1
 observed=[]
 for d in sorted(REPORT.iterdir()):
  if not d.is_dir():continue
  p=d/'NAME_ANALYSIS_RECEIPT.json'
  if not p.is_file():continue
  value,b=read(p);observed.append(dict(authority=b,schema=value.get('schema'),status=value.get('status')))
  if value.get('status')!='COMPLETE_REQUESTED_NAME_INDEX':excluded.append(dict(authority=b,reason='Not completed at the metadata observation; not added'));continue
  require(value['schema'] in ('s6c_name_metrics.v1','s6c_name_metrics.v2','s6c_name_metrics.v3'),'Unsupported current name schema')
  label='S6C '+d.name+'; exact completed naming authority, original scene/turn/roster/known-unknown denominators retained; separate from core anonymous metrics and other authorities.'
  if d.name=='smoke_names_v1':label+=' Six-output smoke; scope_kind native is a coarse collector category, not12/56/240-case qualification or new native inference.'
  admit(d.name,b,dict(schema=value['schema'],status=value['status']),'names',label);name_count+=1
 for item in inputs:
  if item['source_id']=='S6B_challenge_analysis_v1':item['scope_label']+=' Original44-scene challenge; scope_kind native is only an available coarse catalog category, not56 cases, pacing or fresh inference.'
 catalog=dict(schema=mod.SCHEMA,status='DRAFT_PARTIAL_CATALOG',created_utc=datetime.now(timezone.utc).isoformat(),inputs=inputs,supersedes_draft=oldb,starting_core_spec=specb,collector=binding(source),collector_readme=binding(HERE/'README_S6C_SCORE_TABLES.md'),scope='Explicit31 completed core authorities plus every completed immediate-child name authority observed now; separate namespaces, no aliases, row filtering, scoring, pooling or execution claims.',pending='Do not export this draft. Root must approve a separately bound explicit export scope after review. Later full N03/new native score authorities are added only when COMPLETE receipts exist; no waiting or inferred future rows.',header_verification='Only bounded header buffers and declared file sizes observed; whole CSV hashes remain future exact-export admission.',omitted_tables='All original selected/local bindings and objective reasons are in LOCAL_TABLE_INDEX.json.')
 mod.validate_spec(catalog,export=False)
 try:mod.validate_spec(catalog,export=True)
 except ValueError:pass
 else:raise AssertionError('Draft would export')
 # Recheck exact small authority bytes before publication; header snapshots do not claim body verification.
 for value,b in cache.values():require(binding(b['path'])==b,'Authority changed during catalog preparation')
 output.mkdir(parents=True)
 cb=save(output/'RECOMMENDED_INPUT_CATALOG_DRAFT_V2.json',catalog)
 total=sum(x['table_binding']['bytes'] for x in index);selected=[x for x in index if x['selected']];intact=sum(x['table_binding']['bytes'] for x in selected if x['mode']=='copy_intact');compact=sum(x['table_binding']['bytes'] for x in selected if x['mode']=='compact_rows')
 ib=save(output/'LOCAL_TABLE_INDEX.json',dict(status='DRAFT_PARTIAL_LOCAL_TABLE_INDEX',tables=index,table_count=len(index),selected_tables=len(selected),all_declared_source_bytes=total,selected_declared_source_bytes=intact+compact,intact_selected_source_bytes=intact,compact_selected_source_bytes=compact,local_only_source_bytes=total-intact-compact,scope='All original table bindings, including omitted tables. Distinct authority references are retained even if underlying byte content is equal. No accuracy payload was read.'))
 hb=save(output/'HEADER_PREVIEWS.json',dict(status='BOUNDED_UNVERIFIED_WHOLE_TABLE_HEADER_PREVIEWS',headers=previews))
 nb=save(output/'NAME_AUTHORITY_DISCOVERY.json',dict(status='IMMEDIATE_DIRECTORY_METADATA_OBSERVATION',observed=observed,not_selected=excluded,no_recursive_discovery=True))
 receipt=dict(status='DRAFT_PARTIAL_CATALOG',core_authorities=core_count,name_authorities=name_count,authorities=len(inputs),selected_tables=len(selected),original_tables=len(index),selected_source_bytes=intact+compact,copy_intact_source_bytes=intact,compact_rows_source_bytes=compact,local_only_source_bytes=total-intact-compact,omitted_tables=[{k:x[k] for k in ['source_id','table_name','table_binding','omitted_table_reason']} for x in index if not x['selected']],outputs=[cb,ib,hb,nb],sources=sources,helper=binding(Path(__file__)),readme=binding(HERE/'README_S6C_SCORE_CATALOG_DRAFT_V2.md'),actual_exports=0,models=0,score_payloads=0,full_csv_table_reads=0,whole_study_complete=False,estimation='Selected source bytes are exact sums of authority-declared sizes checked against file size for header-previewed tables. They are neither compact output bytes nor a compressed ZIP estimate. Omission metadata/provenance adds bytes; compression/savings unknown until authorized export.',future_command='python -B s6c_score_tables.py export --spec APPROVED_SPEC_PATH --spec-sha256 EXTERNALLY_APPROVED_SHA256 --output FRESH_OUTPUT_DIRECTORY')
 print(json.dumps(save(output/'DRAFT_CATALOG_RECEIPT_V2.json',receipt)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
