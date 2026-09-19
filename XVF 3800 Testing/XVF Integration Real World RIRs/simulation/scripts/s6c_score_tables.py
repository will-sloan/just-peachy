"""Lossless scalar score-table export. See README_S6C_SCORE_TABLES.md."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tempfile

SCHEMA='s6c-score-table-collection-spec.v1'
ALLOWED_OMISSIONS={'recipe_costs','strata','normalized_final_text'}
SCOPES={'panel56','full240','gate6','split','native','finalist'}
PREFIX='__collection_'
MAX_SOURCE_BYTES=512*2**20


def digest(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def pairs_unique(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('Duplicate JSON object key: '+key)
        value[key]=item
    return value


def parse_json(raw):
    return json.loads(raw,object_pairs_hook=pairs_unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON number: '+x)))


def binding(path,raw):return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=digest(raw))


def read_buffer(expected,reader=None):
    if set(expected)!={'path','bytes','sha256'} or type(expected['bytes']) is not int or not 0<=expected['bytes']<=MAX_SOURCE_BYTES or not re.fullmatch('[a-f0-9]{64}',expected['sha256']):raise ValueError('Exact bounded path/bytes/SHA256 binding required')
    path=Path(expected['path'])
    if not path.is_absolute():raise ValueError('Absolute authority/source path required')
    raw=(reader or Path.read_bytes)(path)
    actual=binding(path,raw)
    if actual['bytes']!=expected['bytes'] or actual['sha256']!=expected['sha256']:raise ValueError('Source bytes differ: '+str(path))
    return raw,actual


def read_json(expected,reader=None):
    raw,b=read_buffer(expected,reader);return parse_json(raw.decode('utf-8-sig')),b


def pointer(value,path):
    if not isinstance(path,str) or not path.startswith('/'):raise ValueError('Explicit non-root JSON pointer required')
    for part in path[1:].split('/'):
        part=part.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            if not re.fullmatch('0|[1-9][0-9]*',part):raise ValueError('Exact list index required')
            value=value[int(part)]
        else:value=value[part]
    return value


def safe_name(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value):raise ValueError('Safe explicit namespace/table name required')
    return value


def validate_spec(spec,export=False):
    if spec.get('schema')!=SCHEMA or spec.get('status') not in ('DRAFT_PARTIAL_CATALOG','APPROVED_EXPLICIT_EXPORT_SCOPE'):raise ValueError('Explicit collection specification required')
    if export and spec['status']!='APPROVED_EXPLICIT_EXPORT_SCOPE':raise ValueError('Draft catalog cannot execute final export')
    if not isinstance(spec.get('inputs'),list) or not spec['inputs']:raise ValueError('Explicit nonempty input list required')
    ids=set();scoped_tables=set()
    for item in spec['inputs']:
        identifier=safe_name(item['source_id'])
        if identifier.lower() in ids:raise ValueError('Duplicate source namespace')
        ids.add(identifier.lower())
        if item['scope_kind'] not in SCOPES or not isinstance(item['scope_label'],str) or not item['scope_label'].strip():raise ValueError('Explicit source scope required')
        if not isinstance(item.get('tables'),list) or not item['tables']:raise ValueError('Explicit score-table pointer list required')
        names=set()
        for table in item['tables']:
            name=safe_name(table['name'])
            if name.lower() in names:raise ValueError('Duplicate table output name')
            names.add(name.lower())
            identity=(item['authority']['sha256'],item['scope_kind'],item['scope_label'],table['binding_pointer'])
            if identity in scoped_tables:raise ValueError('Same authority/scope/table supplied twice')
            scoped_tables.add(identity)
            if table['mode'] not in ('compact_rows','copy_intact'):raise ValueError('Explicit compact or intact mode required')
            keys=table.get('row_key',[]);omissions=table.get('omit_fields',[])
            if not isinstance(keys,list) or len(keys)!=len(set(keys)) or any(not isinstance(k,str) or not k for k in keys):raise ValueError('Distinct explicit row key required')
            if table['mode']=='compact_rows' and ('case_id' not in keys or not keys):raise ValueError('Scene exports require case_id in explicit row key')
            if not isinstance(omissions,list) or len(omissions)!=len(set(omissions)) or not set(omissions)<=ALLOWED_OMISSIONS:raise ValueError('Only the exact three declared fields may be omitted')
            if table['mode']=='copy_intact' and omissions:raise ValueError('Intact aggregate copies cannot omit fields')


def admit_authority(item):
    value,b=read_json(item['authority'])
    wanted=item['expected_authority']
    if set(wanted)!={'schema','status'} or value.get('schema')!=wanted['schema'] or value.get('status')!=wanted['status'] or not wanted['status'].startswith('COMPLETE'):raise ValueError('Exact completed score authority required')
    # No scene discovery, prediction traversal, model imports or implicit score
    # binding inference. The supplied pointer must name an actual CSV binding.
    selected=[]
    for table in item['tables']:
        target=pointer(value,table['binding_pointer'])
        if not isinstance(target,dict) or set(target)!={'path','bytes','sha256'} or Path(target['path']).suffix.lower()!='.csv':raise ValueError('Pointer must identify one exact authoritative score CSV binding')
        selected.append((table,target))
    return value,b,selected


def csv_rows(raw):
    reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
    try:header=next(reader)
    except StopIteration:raise ValueError('CSV header required')
    if not header or len(header)!=len(set(header)) or any(not key or key.startswith(PREFIX) for key in header):raise ValueError('Duplicate/empty/reserved CSV header')
    def rows():
        for number,values in enumerate(reader,1):
            if len(values)!=len(header):raise ValueError('Ragged CSV row '+str(number))
            yield number,dict(zip(header,values))
    return header,rows()


def scalar_text(value):
    if value is None:return ''
    if isinstance(value,str):return value
    if type(value) is bool:return 'true' if value else 'false'
    if type(value) is int:return str(value)
    if type(value) is float:
        if not math.isfinite(value):raise ValueError('Nonfinite numeric scalar')
        return json.dumps(value,allow_nan=False)
    # Retained nested objects use unambiguous JSON if supplied as typed values.
    # Existing CSV JSON cells are strings and are preserved character-for-character.
    if isinstance(value,(dict,list)):return canonical(value).decode('utf-8')
    raise ValueError('Unsupported table cell type')


def schema_of(value):
    if value is None:return 'null'
    if type(value) is bool:return 'boolean'
    if type(value) is int:return 'integer'
    if type(value) is float:return 'number'
    if isinstance(value,str):return 'string'
    if isinstance(value,list):
        unique={canonical(schema_of(x)).decode('utf-8'):schema_of(x) for x in value}
        return {'array_items':[unique[k] for k in sorted(unique)]}
    if isinstance(value,dict):return {'object_properties':{k:schema_of(v) for k,v in sorted(value.items())}}
    raise ValueError('Unsupported omitted cell type')


def omitted_cell(field,value):
    text=scalar_text(value);parsed=value;encoding='typed_value'
    if isinstance(value,str):
        encoding='original_csv_cell_utf8'
        if field in ('recipe_costs','strata') and value!='':parsed=parse_json(value)
    if field in ('recipe_costs','strata') and parsed not in ('',None) and not isinstance(parsed,(dict,list)):raise ValueError('Declared nested omission is not a nested value')
    count=len(parsed) if isinstance(parsed,(dict,list,str)) else 0 if parsed is None else 1
    return dict(field=field,encoding=encoding,cell_utf8_bytes=len(text.encode('utf-8')),cell_sha256=digest(text.encode('utf-8')),schema=schema_of(parsed),top_level_count=count,
        count_unit='object_properties' if isinstance(parsed,dict) else 'array_items' if isinstance(parsed,list) else 'characters' if isinstance(parsed,str) else 'scalar_values')


def write_compact(header,rows,table,provenance,target,omitted):
    omitted_fields=table.get('omit_fields',[]);keys=table['row_key']
    if not set(omitted_fields)<=ALLOWED_OMISSIONS:raise ValueError('Undeclared omission forbidden')
    if not set(omitted_fields)<=set(header) or not set(keys)<=set(header) or set(keys)&set(omitted_fields):raise ValueError('Declared row keys/omissions must exist and remain retained')
    fields=[k for k in header if k not in omitted_fields];extras=[PREFIX+k for k in ('source_id','scope_kind','scope_label','authority_sha256','table_sha256','source_row_1based','row_key_sha256')]
    writer=csv.DictWriter(target,fieldnames=fields+extras,lineterminator='\n');writer.writeheader();seen=set();count=0;omission_count=0
    omitted_schemas={}
    for number,row in rows:
        if set(row)!=set(header):raise ValueError('Source row/header schema differs')
        key={k:scalar_text(row[k]) for k in keys}
        if any(v=='' for v in key.values()):raise ValueError('Empty primary identity field')
        encoded=canonical(key);key_sha=digest(encoded)
        if encoded in seen:raise ValueError('Duplicate row key within one explicit authority/scope/table')
        seen.add(encoded)
        result={k:scalar_text(row[k]) for k in fields}
        result.update({PREFIX+k:v for k,v in provenance.items()});result[PREFIX+'source_row_1based']=number;result[PREFIX+'row_key_sha256']=key_sha
        writer.writerow(result);count+=1
        for field in omitted_fields:
            detail=omitted_cell(field,row[field]);sid=digest(canonical(detail.pop('schema')))
            omitted_schemas[sid]=schema_of(parse_json(row[field]) if field in ('recipe_costs','strata') and isinstance(row[field],str) and row[field]!='' else row[field])
            detail.update(schema_sha256=sid,source_row_1based=number,row_key_sha256=key_sha,row_key=key)
            omitted.write(json.dumps(detail,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n');omission_count+=1
    return dict(rows=count,source_columns=len(header),retained_columns=len(fields),provenance_columns=extras,omission_records=omission_count,omitted_schemas=omitted_schemas,
        null_semantics='Original CSV empty cells remain empty; CSV does not distinguish original null from empty string. No zero/false imputation, numeric reformatting, row filtering or cross-source pooling.')


def immutable(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw)
    return binding(path,raw)


def export(spec_binding,output):
    spec,sb=read_json(spec_binding);validate_spec(spec,export=True)
    if output.exists():raise ValueError('Fresh versioned output directory required')
    output.mkdir(parents=True);records=[]
    for item in spec['inputs']:
        authority,ab,tables=admit_authority(item)
        for table,target in tables:
            raw,tb=read_buffer(target);header,rows=csv_rows(raw);folder=output/item['source_id'];folder.mkdir(exist_ok=True)
            path=folder/(table['name']+'.csv')
            record=dict(source_id=item['source_id'],scope_kind=item['scope_kind'],scope_label=item['scope_label'],authority=ab,authority_schema=authority['schema'],authority_status=authority['status'],binding_pointer=table['binding_pointer'],source_table=tb,table=table,
                authority_declared_counts={k:v for k,v in authority.items() if k in ('requested','scored','unscored','failed_or_missing','requested_scene_count','panel')},source_header=header)
            if table['mode']=='copy_intact':
                # Parse only to verify CSV shape. The exported bytes are exactly
                # those certified above, preserving original aggregates/quoting.
                keys=table.get('row_key',[])
                if not set(keys)<=set(header):raise ValueError('Aggregate row key is absent from source header')
                seen=set();count=0
                for _,row in rows:
                    if keys:
                        key=canonical({k:row[k] for k in keys})
                        if key in seen:raise ValueError('Duplicate aggregate key within explicit authority/scope/table')
                        seen.add(key)
                    count+=1
                record.update(rows=count,output=immutable(path,raw),transformation='BYTE_EXACT_COPY_NO_AGGREGATION',duplicate_key_check='EXPLICIT_KEYS' if keys else 'NOT_REQUESTED_NO_KEY_INVENTED')
            else:
                provenance=dict(source_id=item['source_id'],scope_kind=item['scope_kind'],scope_label=item['scope_label'],authority_sha256=ab['sha256'],table_sha256=tb['sha256'])
                out=io.StringIO(newline='');omitted=io.StringIO();details=write_compact(header,rows,table,provenance,out,omitted)
                schemas=details.pop('omitted_schemas');record.update(details)
                record.update(output=immutable(path,out.getvalue().encode('utf-8')),omissions=immutable(folder/(table['name']+'_OMISSIONS.jsonl'),omitted.getvalue().encode('utf-8')),omitted_schemas=immutable(folder/(table['name']+'_OMITTED_SCHEMAS.json'),canonical(schemas)+b'\n'),transformation='EXACT_RETAINED_CELLS_DECLARED_OMISSIONS_ONLY')
            records.append(record)
    # Recheck small authorities/spec after processing; payload rows were parsed
    # from their exact verified buffers, never from a second unverified read.
    read_buffer(sb)
    for item in spec['inputs']:read_buffer(item['authority'])
    source=Path(__file__);readme=source.with_name('README_S6C_SCORE_TABLES.md')
    receipt=dict(schema='s6c-score-table-export.v1',status='COMPLETE_EXPLICIT_TABLE_EXPORT',created_utc=datetime.now(timezone.utc).isoformat(),spec=sb,
        sources=[binding(p,p.read_bytes()) for p in (source,readme)],tables=records,table_count=len(records),model_calls=0,scoring_calls=0,
        completeness='Only the explicitly supplied completed score authorities/tables were exported. Scope labels are caller declarations, not newly certified case grids; no full-study/finalist completeness or new score validation is implied.',
        interpretation='No implicit discovery, filtering, relabeling, aggregation, averaging, re-scoring, pooling or alias merging. Source namespaces and original per-row metrics/status/denominators remain distinct.')
    return immutable(output/'COLLECTION_MANIFEST.json',canonical(receipt)+b'\n')


def checks():
    count=0
    def rejected(call):
        try:call()
        except (ValueError,KeyError):return 1
        raise AssertionError('Invalid input accepted')
    for value in (True,False,None,0,1.25,'a,"b"\nnext',{'x':[True,None]}):
        encoded=scalar_text(value);s=io.StringIO(newline='');csv.writer(s).writerow([encoded]);assert next(csv.reader(io.StringIO(s.getvalue(),newline='')))[0]==encoded;count+=1
    assert scalar_text(None)=='' and scalar_text(False)=='false' and scalar_text('False')=='False';count+=1
    count+=rejected(lambda:parse_json('{"x":1,"x":2}'));count+=rejected(lambda:parse_json('{"x":NaN}'))
    count+=rejected(lambda:csv_rows(b'x,x\n1,2\n'))
    _,rs=csv_rows(b'x,y\n1\n');count+=rejected(lambda:list(rs))
    with tempfile.TemporaryDirectory(prefix='s6c_score_tables_') as temp:
        p=Path(temp)/'source.json';p.write_bytes(b'{"x":1}');expected=binding(p,p.read_bytes());value,b=read_json(expected);assert value=={'x':1} and b==expected;count+=1
        def swapped(path):path.write_bytes(b'{"x":9}');return b'{"x":1}'
        value,b=read_json(expected,swapped);assert value=={'x':1} and b['sha256']==expected['sha256'];count+=1
        count+=rejected(lambda:read_json(expected))
    row=dict(profile_id='alias_C071',case_id='case',metric=0,flag=False,missing=None,recipe_costs='{"x":[1,null]}',strata='{"corpus":["A"]}',normalized_final_text='a,"quoted"\nline',lineage_counts='{"track": 2}')
    table=dict(row_key=['profile_id','case_id'],omit_fields=['recipe_costs','strata','normalized_final_text'])
    provenance=dict(source_id='first',scope_kind='gate6',scope_label='independent native',authority_sha256='a'*64,table_sha256='b'*64)
    out=io.StringIO(newline='');om=io.StringIO();result=write_compact(list(row),[(1,row)],table,provenance,out,om)
    parsed=list(csv.DictReader(io.StringIO(out.getvalue(),newline='')))[0]
    assert parsed['lineage_counts']==row['lineage_counts'] and parsed['missing']=='' and parsed['flag']=='false' and parsed['metric']=='0';count+=1
    omissions=[parse_json(line) for line in om.getvalue().splitlines()]
    assert len(omissions)==3 and omissions[-1]['cell_sha256']==digest(row['normalized_final_text'].encode()) and omissions[0]['top_level_count']==1;count+=1
    count+=rejected(lambda:write_compact(list(row),[(1,row),(2,row)],table,provenance,io.StringIO(),io.StringIO()))
    count+=rejected(lambda:write_compact(list(row),[(1,row)],dict(table,omit_fields=['missing']),provenance,io.StringIO(),io.StringIO()))
    # Different schemas and repeated scientific keys belong to separate source
    # namespaces; neither candidate aliases nor wider tables are normalized away.
    for n,identifier in ((75,'one'),(77,'two')):
        expanded={**row,**{f'extra_{i}':i for i in range(n-len(row))}}
        s=io.StringIO(newline='');o=io.StringIO();info=write_compact(list(expanded),[(1,expanded)],table,{**provenance,'source_id':identifier},s,o)
        assert info['source_columns']==n and 'alias_C071' in s.getvalue() and identifier in s.getvalue();count+=1
    base=dict(schema=SCHEMA,status='DRAFT_PARTIAL_CATALOG',inputs=[dict(source_id='one',scope_kind='gate6',scope_label='native',authority={'sha256':'a'*64},tables=[dict(name='SCENE',binding_pointer='/tables/0',mode='compact_rows',row_key=['case_id'],omit_fields=['strata'])])])
    validate_spec(base);count+=1
    count+=rejected(lambda:validate_spec(base,export=True))
    bad=parse_json(canonical(base));bad['inputs'][0]['tables'][0]['omit_fields']=['lineage_counts'];count+=rejected(lambda:validate_spec(bad))
    bad=parse_json(canonical(base));bad['inputs'].append({**bad['inputs'][0],'source_id':'two'});count+=rejected(lambda:validate_spec(bad))
    bad['inputs'][1]['scope_label']='different experiment';validate_spec(bad);count+=1
    bad['inputs'][1]['source_id']='ONE';count+=rejected(lambda:validate_spec(bad))
    with tempfile.TemporaryDirectory(prefix='s6c_score_export_') as temp:
        root=Path(temp);src=root/'input.csv';src.write_bytes(b'case_id,profile_id,metric,strata,lineage_counts\r\ncase,C071,0,"{""x"":[1]}","{""a"": 2}"\r\n')
        tb=binding(src,src.read_bytes());authority=root/'receipt.json';authority.write_bytes(canonical(dict(schema='fixture-score.v1',status='COMPLETE_REQUESTED_INDEX',tables=[tb])))
        item=dict(source_id='gate',scope_kind='gate6',scope_label='fixture native only',authority=binding(authority,authority.read_bytes()),expected_authority=dict(schema='fixture-score.v1',status='COMPLETE_REQUESTED_INDEX'),tables=[dict(name='SCENE',binding_pointer='/tables/0',mode='compact_rows',row_key=['case_id','profile_id'],omit_fields=['strata']),dict(name='UNCHANGED',binding_pointer='/tables/0',mode='copy_intact',row_key=['case_id','profile_id'],omit_fields=[])])
        # The same source table cannot be admitted twice within one scope even
        # under two output aliases. Use a separately certified aggregate binding.
        agg=root/'aggregate.csv';agg.write_bytes(b'profile_id,numerator,denominator,rate\r\nC071,1,3,0.3333333333333333\r\n');ab=binding(agg,agg.read_bytes())
        authority.write_bytes(canonical(dict(schema='fixture-score.v1',status='COMPLETE_REQUESTED_INDEX',tables=[tb,ab])))
        item['authority']=binding(authority,authority.read_bytes());item['tables'][1].update(binding_pointer='/tables/1',row_key=['profile_id'])
        specification=dict(schema=SCHEMA,status='APPROVED_EXPLICIT_EXPORT_SCOPE',inputs=[item]);sp=root/'spec.json';sp.write_bytes(canonical(specification));sb=binding(sp,sp.read_bytes())
        result=export(sb,root/'out');manifest,_=read_json(result)
        assert (root/'out/gate/UNCHANGED.csv').read_bytes()==agg.read_bytes() and len(manifest['tables'])==2;count+=1
        compact=list(csv.DictReader(io.StringIO((root/'out/gate/SCENE.csv').read_text(),newline='')))[0]
        assert compact['metric']=='0' and compact['lineage_counts']=='{"a": 2}' and compact[PREFIX+'authority_sha256']==item['authority']['sha256'];count+=1
        count+=rejected(lambda:export(sb,root/'out'))
        altered=parse_json(authority.read_bytes());altered['status']='STARTED';authority.write_bytes(canonical(altered));item['authority']=binding(authority,authority.read_bytes());count+=rejected(lambda:admit_authority(item))
    return dict(status='PASS_MODEL_FREE',checks=count,models=0,scoring=0,actual_score_exports=0,scope='Small isolated serialization/provenance/identity fixtures only.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);parser.add_argument('action',choices=('checks','export'));parser.add_argument('--spec',type=Path);parser.add_argument('--spec-sha256');parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.action=='checks':result=checks()
    else:
        if args.spec is None or args.spec_sha256 is None or args.output is None:parser.error('export requires explicit --spec --spec-sha256 --output')
        raw=args.spec.read_bytes();b=binding(args.spec,raw)
        if b['sha256']!=args.spec_sha256:raise ValueError('Caller-pinned collection specification differs')
        result=export(b,args.output.resolve())
    print(json.dumps(result,indent=2))
