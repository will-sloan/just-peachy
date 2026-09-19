"""Independent actual working-export review; README_S6C_SCORE_EXPORT_REVIEW_V1.md."""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,io,json,math
HERE=Path(__file__).resolve().parent;REPORT=HERE.parent/'reports/S6C/20260910T123540Z';ROOT=REPORT/'compact_score_tables'
PINS={'working_v1/COLLECTION_MANIFEST.json':'d7ed70fc0ffbaea9d4caefef598930e5aa997ecf1bc90206a1d4ebb1941ab136','APPROVED_WORKING_SPEC_V1.json':'71621e77af64a1ee46acae2c118f5d64d289cb288041d3501e590abaf2bcc151','WORKING_V1_COMPRESSION_MEASUREMENT.json':'7b9a2d713d5a65298db7bfafb94fe7e45c2fe47fb31520ecfda0599e3192270a','catalog_draft_v2/RECOMMENDED_INPUT_CATALOG_DRAFT_V2.json':'2418ac08db1dfca1aa4393f3c8b75824136970b98e4dd2b39adcbf276946d814','catalog_draft_v2/LOCAL_TABLE_INDEX.json':'fcfa3270789817c8e247ad792428b8630740dab894a71506a815986b50728977','catalog_draft_v2/HEADER_PREVIEWS.json':'1d1fdac5928c6640a24746b5e112a0b582f5d673236d9229ac5f5d6deff0b886'}
FIELDS=['recipe_costs','strata','normalized_final_text']
EXTRAS=['__collection_'+x for x in ['source_id','scope_kind','scope_label','authority_sha256','table_sha256','source_row_1based','row_key_sha256']]
csv.field_size_limit(32*2**20)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def binding(p,raw=None):
 p=Path(p);raw=p.read_bytes() if raw is None else raw;return dict(path=str(p.resolve()),bytes=len(raw),sha256=digest(raw))
def canonical(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode()
def structure(x):
 if x is None:return 'null'
 if isinstance(x,bool):return 'boolean'
 if isinstance(x,int):return 'integer'
 if isinstance(x,float):return 'number'
 if isinstance(x,str):return 'string'
 if isinstance(x,list):
  types={canonical(structure(y)).decode():structure(y) for y in x};return {'array_items':[types[k] for k in sorted(types)]}
 return {'object_properties':{k:structure(v) for k,v in sorted(x.items())}}
def run(output):
 require=Check();sources=[];docs={}
 for rel,sha in PINS.items():
  p=ROOT/rel;raw=p.read_bytes();require(digest(raw)==sha,'Pinned source '+rel);sources.append(binding(p,raw));docs[rel]=json.loads(raw)
 m=docs['working_v1/COLLECTION_MANIFEST.json'];approved=docs['APPROVED_WORKING_SPEC_V1.json'];draft=docs['catalog_draft_v2/RECOMMENDED_INPUT_CATALOG_DRAFT_V2.json'];measure=docs['WORKING_V1_COMPRESSION_MEASUREMENT.json'];local=docs['catalog_draft_v2/LOCAL_TABLE_INDEX.json'];headers=docs['catalog_draft_v2/HEADER_PREVIEWS.json']
 require(m['status']=='COMPLETE_EXPLICIT_TABLE_EXPORT' and m['table_count']==207 and m['model_calls']==m['scoring_calls']==0,'Scoped completed export')
 require(approved['status']=='APPROVED_EXPLICIT_EXPORT_SCOPE' and approved['whole_study_complete'] is False and approved['inputs']==draft['inputs'],'Exact approved38-authority207-table draft scope')
 require(m['spec']==binding(ROOT/'APPROVED_WORKING_SPEC_V1.json'),'Exact approved source binding')
 expected={(x['source_id'],t['binding_pointer']):(x,t) for x in approved['inputs'] for t in x['tables']};require(len(expected)==207 and len(approved['inputs'])==38,'Unique scopes')
 declared={(x['source_id'],x['binding_pointer']):x for x in local['tables'] if x['selected']};header_lookup={x['source_table']['path']:x['columns'] for x in headers['headers']}
 observed={(x['source_id'],x['binding_pointer']):x for x in m['tables']};require(observed.keys()==expected.keys() and len(observed)==len(m['tables']),'All selected tables exactly once')
 payload={};ledgers={};record_by_path={};rowcounts={};target_records=[]
 for key,rec in observed.items():
  item,table=expected[key];require(rec['table']==table and rec['authority']==item['authority'] and rec['authority_schema']==item['expected_authority']['schema'] and rec['authority_status']==item['expected_authority']['status'],'Exact authority/table '+str(key))
  require(rec['scope_kind']==item['scope_kind'] and rec['scope_label']==item['scope_label'],'Distinct scope '+str(key));require(rec['source_table']==declared[key]['table_binding'],'Original table binding '+str(key))
  require(rec['source_header']==header_lookup[rec['source_table']['path']],'Original source header '+str(key))
  require(Path(rec['output']['path'])==ROOT/'working_v1'/item['source_id']/(table['name']+'.csv'),'Independent output namespace')
  record_by_path[rec['output']['path']]=rec;payload[rec['output']['path']]=rec['output']
  if table['mode']=='copy_intact':require((rec['output']['bytes'],rec['output']['sha256'])==(rec['source_table']['bytes'],rec['source_table']['sha256']),'Intact source bytes '+str(key));require(rec['transformation']=='BYTE_EXACT_COPY_NO_AGGREGATION','Intact operation')
  else:
   omitted=table['omit_fields'];require(omitted==[x for x in FIELDS if x in rec['source_header']],'Only declared3 omission fields')
   require(rec['retained_columns']==rec['source_columns']-len(omitted) and rec['source_columns']==len(rec['source_header']) and rec['provenance_columns']==EXTRAS,'Exact column counts')
   require(rec['rows']==rec['authority_declared_counts']['scored']==rec['authority_declared_counts']['requested'] and rec['omission_records']==rec['rows']*len(omitted),'All source outputs/omission cells declared')
   payload[rec['omitted_schemas']['path']]=rec['omitted_schemas'];ledgers[rec['omissions']['path']]=rec['omissions'];target_records.append(rec)
 payload[str(ROOT/'working_v1/COLLECTION_MANIFEST.json')]=binding(ROOT/'working_v1/COLLECTION_MANIFEST.json')
 measurement={x['path']:x for x in measure['files']};require(len(measurement)==len(measure['files'])==239 and set(measurement)==set(payload),'Exact239 measured buffers')
 require(len(ledgers)==31 and len(payload)+len(ledgers)==270,'All270 files declared,31 local ledgers separate')
 require(sum(x['bytes'] for x in payload.values())==measure['original_bytes']==176747852,'Measured byte sum');require(sum(x['raw_deflate_bytes'] for x in measurement.values())==measure['raw_deflate_bytes']==10148144,'Declared raw-deflate arithmetic')
 require(sum(x['bytes'] for x in payload.values())+sum(x['bytes'] for x in ledgers.values())==279633654,'Whole export declared byte sum')
 samples={};empty_cells=Counter();actual_rows=0;compact_rows=0
 for path,b in sorted(payload.items()):
  measured=measurement[path];require({k:measured[k] for k in ['path','bytes','sha256']}==b,'Measured original binding '+path)
  raw=Path(path).read_bytes();require(binding(path,raw)==b,'Actual measured output buffer '+path)
  if Path(path).suffix!='.csv':continue
  rec=record_by_path[path];table=rec['table'];reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True);count=0;seen=set();first=[]
  wanted=[x for x in rec['source_header'] if x not in table['omit_fields']]+(EXTRAS if table['mode']=='compact_rows' else [])
  require(reader.fieldnames==wanted,'Actual output header '+path)
  for row in reader:
   count+=1;require(None not in row and all(v is not None for v in row.values()),'Actual CSV shape '+path)
   if len(first)<3:first.append(row)
   if table['mode']=='compact_rows':
    compact_rows+=1;k={x:row[x] for x in table['row_key']};encoded=canonical(k);require(encoded not in seen and all(k.values()),'Compact exact nonempty unique row key');seen.add(encoded)
    values=[rec['source_id'],rec['scope_kind'],rec['scope_label'],rec['authority']['sha256'],rec['source_table']['sha256'],str(count),digest(encoded)];require([row[x] for x in EXTRAS]==values,'Every row exact provenance')
    empty_cells[rec['source_id']]+=sum(row[x]=='' for x in wanted if x not in EXTRAS)
  require(count==rec['rows'],'Actual output row count '+path);actual_rows+=count;rowcounts[rec['source_id']+'/'+table['name']]=count;samples[path]=first
 # Stat only for local ledgers; their full hashes were not independently repeated.
 for path,b in ledgers.items():require(Path(path).stat().st_size==b['bytes'],'Local ledger declared size')
 sample_ids=['full_n01_anonymous_core_v3','S6B_full_analysis_v1','split_cross_panel_core_v3']
 sample_proofs=[]
 for source_id in sample_ids:
  rec=next(x for x in target_records if x['source_id']==source_id);p=Path(rec['source_table']['path']);before=p.stat()
  with p.open(encoding='utf-8-sig',newline='') as f:
   reader=csv.DictReader(f,strict=True);source_header=reader.fieldnames;source_rows=[next(reader) for _ in range(3)]
  after=p.stat();require((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns) and before.st_size==rec['source_table']['bytes'],'Stable bounded original sample read');require(source_header==rec['source_header'],'Source sample header')
  exported=samples[rec['output']['path']]
  for i,(original,row) in enumerate(zip(source_rows,exported),1):
   retained={k:v for k,v in row.items() if k not in EXTRAS};require(retained=={k:v for k,v in original.items() if k not in rec['table']['omit_fields']},'Exact original retained cell text '+source_id+' '+str(i))
  with Path(rec['omissions']['path']).open(encoding='utf-8') as f:details=[json.loads(next(f)) for _ in range(3*len(rec['table']['omit_fields']))]
  schemas=json.loads(Path(rec['omitted_schemas']['path']).read_bytes())
  for d in details:
   i=d['source_row_1based'];original=source_rows[i-1];text=original[d['field']];encoded=text.encode();key={k:original[k] for k in rec['table']['row_key']};parsed=json.loads(text) if d['field'] in ('recipe_costs','strata') and text!='' else text
   require(d['cell_utf8_bytes']==len(encoded) and d['cell_sha256']==digest(encoded) and d['row_key']==key and d['row_key_sha256']==digest(canonical(key)),'Actual omitted cell byte lineage')
   require(schemas[d['schema_sha256']]==structure(parsed),'Actual omitted schema')
  sample_proofs.append(dict(source_table=rec['source_table'],output=rec['output'],logical_source_rows=[1,2,3],retained_columns=rec['retained_columns'],source_sample_sha256=digest(canonical(source_rows)),exact_retained_cells=True,omission_records_checked=len(details),scope='Only first3 original source CSV records read; full original source-body hash was not repeated. Export output body was independently hashed in full.'))
 for source_id in ['smoke_names_v1','full_n01_naming_names_v3']:
  rec=next(x for x in m['tables'] if x['source_id']==source_id and x['table']['name']=='TURNS');require(rec['output']['sha256']==rec['source_table']['sha256'],'Whole intact naming source equality')
  sample_proofs.append(dict(source_table=rec['source_table'],output=rec['output'],actual_rows=rec['rows'],first_rows_sha256=digest(canonical(samples[rec['output']['path']])),scope='Entire actual exported naming table hash equals source authority hash, byte exact. No original name-table reread needed.'))
 output.parent.mkdir(parents=True,exist_ok=True)
 result=dict(status='PASS_ACTUAL_WORKING_EXPORT_RECONCILIATION',checks=require.count,sources=sources,export_authorities=38,selected_tables=207,actual_measured_buffers_hashed=239,actual_output_bytes_hashed=176747852,declared_all_files=270,declared_all_bytes=279633654,local_omission_jsonl_count=31,local_omission_jsonl_full_hashes_repeated=False,actual_csv_rows=actual_rows,compact_scene_rows=compact_rows,output_row_counts=rowcounts,targeted_actual_source_checks=sample_proofs,compact_empty_cells_retained_by_source=dict(empty_cells),compression=dict(measured_raw_deflate_bytes=10148144,arithmetic_verified=True,recompressed=False,actual_zip_created=False,scope='Existing measured sizes sum correctly for independently hash-verified CSV/JSON buffers. Excludes ZIP headers,31 local JSONL ledgers,future outputs,final documents/figures.'),helper=binding(Path(__file__)),readme=binding(HERE/'README_S6C_SCORE_EXPORT_REVIEW_V1.md'),limitations=['All actual selected output CSV/JSON buffers hashed and parsed; only9 original core source rows and their27 omitted-cell records compared directly.','Original source CSV hashes were not all re-read; exact authoritative source bindings, byte-identical copied output hashes and root completed export are retained.','Local31 omission JSONL bodies are not final payload and were not rehashed in full; declared sizes and targeted records verified.','No score formulas, predictions, native logs, PCM, models or full duplicate export.','Working scope only; later full component/cross/paced/long authorities remain excluded until separately approved. No final handoff or scientific completion claim.'],whole_study_complete=False)
 with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(binding(output)))
class Check:
 def __init__(self):self.count=0
 def __call__(self,ok,message):
  self.count+=1
  if not ok:raise ValueError(message)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
