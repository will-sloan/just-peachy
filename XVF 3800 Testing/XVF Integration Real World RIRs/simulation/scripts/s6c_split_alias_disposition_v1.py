"""Prepare exact cross-tap subset and preserve same-tap aliases. README_S6C_SPLIT_ALIAS_DISPOSITION_V1.md."""
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
OLD=REPORT/'jobs/epoch2/split_v1.json'
OLD_SHA='7c92967b207af60b9550990d4b152c6450006aebe498dc087dcdcebef00363a3'
COVERAGE=REPORT/'route_coverage_v1/ROUTE_COVERAGE.json'
COVERAGE_SHA='fce1140dcea13587abf10b296205777fba33ff3882d607d3e190e586fba7efb9'
TARGET=REPORT/'jobs/epoch2/split_cross_only_v2.json'
DISPOSITION=REPORT/'design/SPLIT_ALIAS_DISPOSITION_V1.json'

def binding(path,raw):return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path):
    p=Path(path).resolve();before=p.stat();raw=p.read_bytes();after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(raw)!=after.st_size:raise ValueError('Metadata changed during admission')
    return json.loads(raw.decode('utf-8-sig')),binding(p,raw)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
    return binding(path,raw)
def key(job):return job['candidate_id'],job['case_id'],job['asr_tap'],job['identity_tap']
def normalize(identity):
    obj=copy.deepcopy(identity);del obj['profile']['profile_id'];return obj

def main():
    if TARGET.exists() or DISPOSITION.exists():raise ValueError('Preserve prior subset/disposition; no overwrite')
    old,ob=read(OLD);coverage,cb=read(COVERAGE)
    if ob['sha256']!=OLD_SHA or cb['sha256']!=COVERAGE_SHA:raise ValueError('Reviewed exact old/coverage source changed')
    prior_dir=REPORT/'orchestration/split_scan_v1'
    prior,pb=read(prior_dir/'ADMISSION.json')
    if prior['jobs']!=ob or prior['status']!='PREPARED_FOR_REVIEW':raise ValueError('Original preparation identity differs')
    if sorted(p.name for p in prior_dir.iterdir())!=['ADMISSION.json']:raise ValueError('Original orchestration has execution state')
    if old['requested']!=224 or len(old['jobs'])!=224 or len({key(j) for j in old['jobs']})!=224:raise ValueError('Original split grid differs')
    if any(Path(j['folder']).exists() for j in old['jobs']):raise ValueError('A prior split native output directory exists; do not supersede execution')
    expected={(cid,case,a,i) for cid,a,i in (('C083','O0','O0'),('C084','O1','O1'),('C085','O0','O1'),('C086','O1','O0')) for case in old['case_ids']}
    if {key(j) for j in old['jobs']}!=expected or len(old['case_ids'])!=56:raise ValueError('Exact four-route56-case grid differs')
    parent,parent_binding=read(REPORT/'jobs/epoch2/recipes_v1.json')
    parents={(j['case_id'],j['asr_tap'],j['identity_tap']):j for j in parent['jobs'] if j['candidate_id']=='C065'}
    if len(parents)!=112 or parent['execution_manifest']!=old['execution_manifest']:raise ValueError('Exact C065 parent recipe grid differs')
    aliases=[];selected=[]
    for job in old['jobs']:
        if digest(job['identity'])!=job['job_key'] or job['profile']!=job['identity']['profile']:raise ValueError('Job identity malformed')
        if job['candidate_id'] in ('C085','C086'):
            selected.append(job);continue
        p=parents[job['case_id'],job['asr_tap'],job['identity_tap']]
        if normalize(job['identity'])!=normalize(p['identity']):raise ValueError('Actual same-tap native job differs beyond profile_id')
        for field in ('recipe_id','asr_audio','identity_audio','asr_pcm_sha256','identity_pcm_sha256','duration_sec','telemetry','gallery','realtime'):
            if job[field]!=p[field]:raise ValueError('Alias actual input/condition differs: '+field)
        receipt,rb=read(Path(p['folder'])/'run_receipt.json')
        if receipt['status']!='COMPLETE' or receipt['job_key']!=p['job_key'] or receipt['identity']!=p['identity']:raise ValueError('Exact alias parent actual completion missing')
        aliases.append(dict(alias_candidate_id=job['candidate_id'],case_id=job['case_id'],asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],
            omitted_alias_job_key=job['job_key'],omitted_alias_output_folder=job['folder'],parent_candidate_id='C065',parent_job_key=p['job_key'],
            parent_output_folder=p['folder'],parent_completion=rb,actual_input_conditions_equal_after_profile_id_removal=True))
    if len(selected)!=112 or len(aliases)!=112 or len({j['job_key'] for j in selected})!=112:raise ValueError('Subset count differs')
    # Require the reviewed profile/condition alias proof as well as actual
    # per-case native input/receipt identity parity above.
    reviewed={(a['alias']['candidate_id'],a['alias']['asr_tap'],a['alias']['identity_tap']) for a in coverage['same_tap_aliases'] if a['current_profiles_equal_epoch2_profiles'] and a['conditions_exact'] and len(a['parent_exact_panel_cases'])==56}
    if reviewed!={('C083','O0','O0'),('C084','O1','O1')}:raise ValueError('Reviewed alias profile proof incomplete')
    helper=binding(__file__,Path(__file__).read_bytes());readme_path=Path(__file__).with_name('README_S6C_SPLIT_ALIAS_DISPOSITION_V1.md');readme=binding(readme_path,readme_path.read_bytes())
    new=copy.deepcopy(old);new.update(jobs=selected,requested=112,candidate_ids=['C085','C086'],
        profile_routes=[r for r in old['profile_routes'] if r['candidate_id'] in ('C085','C086')],
        builder_source=helper,created_utc=datetime.now(timezone.utc).isoformat(),superseded_manifest=ob,alias_coverage=cb,
        selection='Exact original unexecuted cross-tap job objects only: C085 O0-ASR/O1-ID and C086 O1-ASR/O0-ID,56 whole panel cases each. Original v1 job keys/folders unchanged. Same-tap C083/C084 use explicit C065 alias disposition; no alias-ID native execution or score is invented.')
    if any(new['jobs'][n]!=j for n,j in enumerate([j for j in old['jobs'] if j['candidate_id'] in ('C085','C086')])):raise AssertionError('Selected jobs changed')
    nb=save(TARGET,new)
    if read(OLD)[1]!=ob or read(prior_dir/'ADMISSION.json')[1]!=pb:raise ValueError('Old preparation changed during publication')
    value=dict(schema='s6c_split_alias_disposition.v1',status='NOT_EXECUTED_ALIAS_DUPLICATION_SUPERSEDED',created_utc=datetime.now(timezone.utc).isoformat(),
        original_224_manifest=ob,original_coordinator_admission=pb,original_namespace_contents=['ADMISSION.json'],original_all_224_native_output_folders_absent=True,
        superseding_112_manifest=nb,reviewed_profile_alias_coverage=cb,parent_native_job_manifest=parent_binding,
        original_count=224,unchanged_selected_native_jobs=112,omitted_alias_jobs=112,aliases=aliases,helper=helper,readme=readme,
        models_started=0,original_files_preserved=True,
        scope='Prospective unexecuted native plan reduction. Completed C065 metadata receipts support exact source/profile/condition aliases on112 same-tap cells; retained C085/C086 jobs still require112 actual native sessions. No prediction/score payload, waveform, model or full journal was rehashed; frozen execution admission verifies all dependencies before launch.')
    result=save(DISPOSITION,value)
    print(json.dumps({'manifest':nb,'disposition':result,'native_jobs_prepared':112,'models_started':0},indent=2))

if __name__=='__main__':main()
