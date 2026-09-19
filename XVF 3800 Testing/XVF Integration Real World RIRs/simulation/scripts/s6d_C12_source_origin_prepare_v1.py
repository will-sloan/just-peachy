"""Prepare the unapproved C12 source-origin correction; see README_S6D_C12_SOURCE_ORIGIN_V1.md."""
from __future__ import annotations
import argparse, ast, copy, difflib, hashlib, json, shutil
from pathlib import Path

SIM=next((p for p in Path(__file__).resolve().parents if p.name=='simulation'),Path(r'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'))
R=SIM/'reports/S6D/20260913T195357Z'
OLD_MANIFEST=R/'application/beam_C_collection_preparation_v2/MANIFEST.json'
OLD_MANIFEST_SHA='139dc8f8004e4a2fac41619fa67d964e48150e5798f03db41230adbff43cf8b1'

def bind(p):
    p=Path(p).resolve();d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def read(p):return json.loads(Path(p).read_bytes())
def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def functions(p):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(Path(p).read_bytes()).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}

def prepare(out):
    out=Path(out).resolve();assert out.is_relative_to(R/'application') and not out.exists()
    prior=bind(OLD_MANIFEST);assert prior['sha256']==OLD_MANIFEST_SHA;m=read(OLD_MANIFEST)
    assert m['job_count']==len(m['jobs'])==12 and all(j['mode']=='calibration_collection' and j['stage']=='C_collection' for j in m['jobs'])
    assert m['runner_helper']['sha256']=='6f7162900dbf19ff1876c5bbb09720a16081d1a330319ac8cc6e1f6ef61dfbb4'
    assert m['support']['evidence']['sha256']=='bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2'
    # Verify only bounded source metadata. Never open captured WAVs, PCM, model assets or results.
    for b in m['source_files']+[m['runner_helper']]+list(m['support'].values()):assert bind(b['path'])==b
    out.mkdir();source=out/'source';source.mkdir();helpers=out/'helpers';helpers.mkdir()
    source_rows=[];old_root=Path(m['source_root'])
    for b in m['source_files']:
        p=Path(b['path']);target=source/p.relative_to(old_root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        source_rows.append(dict(original=b,target=str(target)))
    beam=source/'edge_speech_pipeline/research_beams_s6d.py';old_beam=old_root/'edge_speech_pipeline/research_beams_s6d.py'
    text=beam.read_text(encoding='utf-8');old=text
    before='self.names=names;self.frames=sample_counts[0]'
    assert text.count(before)==1
    text=text.replace(before,before+';self.sample_rate=info.samplerate')
    before="'capture_admission':self.admission.binding,'expected_samples':self.expected_samples,"
    assert text.count(before)==1
    text=text.replace(before,before+"'pipeline_sample_rate':self.admission.sample_rate,")
    beam.write_text(text,encoding='utf-8',newline='\n')
    assert {k for k in functions(old_beam) if functions(old_beam)[k]!=functions(beam)[k]}=={'CaptureAdmission','CapturedSource'}
    helper=helpers/'s6d_beam_native_run_n6g.py';prior_helper=Path(m['runner_helper']['path']);old_helper=prior_helper.read_text(encoding='utf-8')
    new_helper=old_helper.replace('See README_S6D_BEAM_EXECUTION_V1.md.','See ../README_S6D_C12_SOURCE_ORIGIN_V1.md.')
    assert new_helper.count("'beam':'deaf0af827c77afe9cfa9781eb70299e6833e1705d899b2fc228ea6bea0ba720'")==1
    new_helper=new_helper.replace("'beam':'deaf0af827c77afe9cfa9781eb70299e6833e1705d899b2fc228ea6bea0ba720'","'beam':'"+bind(beam)['sha256']+"'")
    helper.write_text(new_helper,encoding='utf-8',newline='\n');assert functions(helper)==functions(prior_helper)
    for row in source_rows:row['copy']=bind(row.pop('target'))
    proposed=copy.deepcopy(m);proposed.update(status='PROPOSED_C12_RATE_FIELD_REPAIR_NOT_ADMITTED',source_root=str(source),source_files=[x['copy'] for x in source_rows],runner_helper=bind(helper),prior_manifest=prior,source_origin_repair=dict(field='pipeline_sample_rate',value_origin='Actual lossless common source header, all admitted streams strictly validated16000Hz before assignment',old_attempt_credit=0,old_events_unchanged=True),model_calls=0,hardware_calls=0)
    payload=Path(r'G:\Just_Peachy_S6D\20260913T195357Z\application\beam_C_collection_source_origin_v1')
    assert not payload.exists()
    for j,old_job in zip(proposed['jobs'],m['jobs']):
        j['output']=str(payload/j['job_id'])
        assert {k:v for k,v in j.items() if k!='output'}=={k:v for k,v in old_job.items() if k!='output'}
    manifest=out/'MANIFEST_PROPOSAL.json';save(manifest,proposed)
    diffs=[]
    for name,a,b in [('PRODUCER_DIFF.diff',old,text),('N6F_TO_N6G_DIFF.diff',old_helper,new_helper)]:
        p=out/name;p.write_text(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='preserved_parent',tofile='proposal')),encoding='utf-8');diffs.append(bind(p))
    readme=SIM/'scripts/README_S6D_C12_SOURCE_ORIGIN_V1.md';shutil.copyfile(readme,out/readme.name)
    plan=dict(status='PROPOSED_SOURCE_AND_MANIFEST_ONLY_NOT_ADMITTED',parent_manifest=prior,parent_runner=m['runner_helper'],manifest=bind(manifest),source_files=source_rows,runner=bind(helper),support_unchanged=m['support'],limits_unchanged=m['limits'],diffs=diffs,source=bind(__file__),readme=bind(out/readme.name),fresh_payload_root=str(payload),payload_created=False,jobs=12,source_changed_files=1,source_identical_files=47,wrapper_scientific_functions_ast_identical=True,bb1b_validator_unchanged=True,original_failed_attempt_accepted=False,queue_created=False,approval_created=False,models=0,device_calls=0,process_queries=0,prospective_literal_child_argv=[['C:\\Users\\amiri\\Documents\\GitHub\\just-peachy\\.edge-speech-env\\python.exe','-B',str(helper),'--manifest',str(manifest),'--manifest-sha256',bind(manifest)['sha256'],'--job-id',j['job_id']] for j in proposed['jobs']],remaining_gates=['Independent source/fixture review and root acceptance of new graph/N6g','Fresh root queue, protocol/output paths and approval; old C12 failure remains0accepted','Current original V4/40GiB census/floors/deadline/one-supervisor admission and actual process closure','Exact original inputs/assets/galleries verified only at approved native launch; no source/header/PCM reads in this proposal','Actual whole three-journal hashes, full-frame dispatch/drain and outer completion for every fresh run; no retrofit of old events'])
    save(out/'PROPOSAL.json',plan);return bind(out/'PROPOSAL.json')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.output)))
