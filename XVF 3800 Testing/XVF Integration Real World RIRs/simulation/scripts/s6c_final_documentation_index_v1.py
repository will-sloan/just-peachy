"""Current code/README catalog; see README_S6C_FINAL_DOCUMENTATION_INDEX_V1.md."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,re
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
DOCS=REPORT/'documentation_coverage'
REQUIRED={'s6c_final_narratives_v1.py','s6c_review_paced_document_v1.py','s6c_final_resource_snapshot_v1.py','s6c_final_narrative_copy_v2.py','s6c_operating_invocations_v1.py'}

def require(ok,message):
    if not ok:raise ValueError(message)

class Reader:
    def __init__(self):self.raw={};self.bindings={}
    def read(self,p):
        p=Path(p).resolve()
        if p not in self.raw:
            require(p.stat().st_size<=8*1024**2,'Finite source/documentation only')
            raw=p.read_bytes();self.raw[p]=raw;self.bindings[p]=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        return self.raw[p],self.bindings[p]
    def doc(self,p):
        raw,b=self.read(p);return json.loads(raw),b

def code_files():
    return sorted(p for p in (SIM/'scripts').glob('*.py') if p.name.startswith(('s6c_','test_s6c_')))

def run(output):
    out=Path(output).resolve();require(out.parent==DOCS and not out.exists(),'Fresh documentation_coverage child')
    reader=Reader();prior,pb=reader.doc(DOCS/'working_v1/RECEIPT.json')
    raw,cb=reader.read(DOCS/'working_v1/CODE_README_COVERAGE.csv')
    old=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    oldmap={str(Path(x['source_path']).resolve()).lower():x for x in old}
    addenda=[]
    for p in sorted(DOCS.glob('*ADDENDUM*.json')):
        _,b=reader.doc(p);addenda.append(b)
    paths=code_files();require(REQUIRED<={p.name for p in paths},'Required latest root/operating wrappers')
    app_rows=[x for x in old if x['area']=='APP']
    require(len(app_rows)==10,'Original explicit ten APP targets')
    paths+=sorted(Path(x['source_path']) for x in app_rows)
    readmes={};text={}
    for p in sorted((SIM/'scripts').glob('README*.md')):
        raw,b=reader.read(p);readmes[p.name.lower()]=p;text[p]=raw.decode('utf-8-sig')
    for x in app_rows:
        p=Path(x['readme_path']);raw,b=reader.read(p);text[p]=raw.decode('utf-8-sig')
    rows=[];used={};gaps=[]
    for p in paths:
        raw,sb=reader.read(p);previous=oldmap.get(str(p.resolve()).lower());area='SIM_scripts' if p.parent==SIM/'scripts' else 'APP'
        exact=readmes.get(('README_'+p.stem+'.md').lower()) if area=='SIM_scripts' else None
        historical=Path(previous['readme_path']) if previous and Path(previous['readme_path']).is_file() else None
        mentions=sorted(q for q,t in text.items() if p.name.lower() in t.lower())
        chosen=exact or historical or (mentions[0] if mentions else None)
        basis='EXACT_CONVENTIONAL_README' if exact else 'PREVIOUS_EXPLICIT_MAPPING_CURRENT_BYTES' if historical else 'EXPLICIT_FILENAME_IN_README' if mentions else 'MISSING'
        if chosen:
            _,rb=reader.read(chosen);key=rb['path'];used[key]=rb
            body=text[chosen]
            shell=dict(powershell=bool(re.search('powershell',body,re.I)),anaconda_or_cmd=bool(re.search(r'anaconda|\bCMD\b|command prompt',body,re.I)))
            if not all(shell.values()):gaps.append(dict(source=sb,readme=rb,kind='MISSING_SHELL_LABEL',observed=shell))
        else:
            rb=None;shell=None;gaps.append(dict(source=sb,kind='NO_README_MAPPING'))
        rows.append(dict(area=area,source=sb,readme_path=None if rb is None else rb['path'],mapping_basis=basis,shell_labels=shell,
                         previous_census_source_sha256=None if previous is None else previous['source_sha256'],
                         current_source_matches_previous=None if previous is None else sb['sha256']==previous['source_sha256'],
                         previous_census_readme_sha256=None if previous is None else previous['readme_sha256']))
    # Current code is cataloged, not substituted for any frozen execution epoch.
    inv,ib=reader.doc(REPORT/'command_examples/four_operating_conditions_v2/VALIDATION_ROLLUP.json')
    require(ib['sha256']=='06d33321fb623d13214fa83d27503cfdf2b0f663ad4f4e4a8d7e4fa0a8309568','Exact completed invocation rollup')
    execution_links=[]
    for x in inv['conditions']:
        d,vb=reader.doc(x['validation']['path']);require(vb==x['validation'],'Exact original invocation validation')
        execution_links.append(dict(candidate_id=x['candidate_id'],validation=x['validation'],execution_epoch=d['admission']['epoch'],frozen_app_path=d['admission']['app'],
                                    frozen_python_file_count=x['frozen_python_files'],current_python_same=x['current_python_same'],current_python_different=x['current_python_different']))
    require(code_files()==[p for p in paths if p.parent==SIM/'scripts'],'Code filename set changed during catalog')
    for p,raw in reader.raw.items():require(p.read_bytes()==raw,'Source/documentation changed during catalog: '+str(p))
    out.mkdir()
    result=dict(schema='s6c-current-code-readme-index.v1',status='COMPLETE_CURRENT_DOCUMENTATION_INDEX' if not gaps else 'CURRENT_DOCUMENTATION_INDEX_WITH_GAPS',
                purpose='Local current code paths, exact byte hashes and maintained README mappings. Not execution provenance or final acceptance.',
                entries=rows,readmes=list(used.values()),counts=dict(sim_scripts=len(paths)-10,explicit_app_targets=10,total_code=len(rows),distinct_readmes=len(used),missing_or_shell_gaps=len(gaps)),
                prior_working_receipt=pb,prior_mapping_csv=cb,explicit_addenda=addenda,inherited_reproduction_findings=prior['findings'],
                frozen_execution_reference_examples=execution_links,operating_validation_rollup=ib,gaps=gaps,
                scope=['Immediate SIM/scripts s6c_*.py and test_s6c_*.py plus the ten previously explicit S6C APP targets; all retained draft/historical helper filenames remain listed.','Current source/README hashes do not inherit old source-review PASS or prove historical execution parity. Exact executed generations remain bound by their original epoch/native/coordinator receipts and the final census.','Prior working snapshots/addenda remain unchanged and locally available. Frozen APP examples refer to already completed metadata validation, not a new file/model run.','README mapping and shell labels are checked; this catalog does not execute commands or claim every occupied historical example can be rerun. Use fresh namespaces or print-only operating commands.','All code/README buffers and current script filename membership were checked again before publication. This is a point-in-time documentation snapshot; future files need an additive update.'],
                code_or_documented_commands_executed=False,new_models=0,whole_study_complete=False)
    p=out/'CODE_README_INDEX.json';raw=(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    with p.open('xb') as f:f.write(raw)
    b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    receipt=dict(status=result['status'],index=b,counts=result['counts'],source=reader.read(__file__)[1],readme=reader.read(Path(__file__).with_name('README_S6C_FINAL_DOCUMENTATION_INDEX_V1.md'))[1],gaps=gaps,whole_study_complete=False)
    q=out/'RECEIPT.json'
    with q.open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(receipt))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True);run(p.parse_args().output)
