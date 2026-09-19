"""Revise only current context in an immutable, still-unapproved 68-credit proposal."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
SOURCE=R/'application/native68_root_receipt_preparation_v1/ROOT_RETENTION_AND_68_CREDITS_PROPOSAL.json'
SOURCE_SHA='1c42767f6c400c127f2db25ccee9e810bd8cb238d5f90335b1cccd052edeca62'

def binding(path,data=None):
    p=Path(path).resolve();data=p.read_bytes() if data is None else data
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def main(path):
    out=Path(path).resolve()
    if out.exists():raise ValueError('Fresh proposal required')
    raw=SOURCE.read_bytes();origin=binding(SOURCE,raw)
    if origin['sha256']!=SOURCE_SHA:raise ValueError('Immutable original proposal differs')
    old=json.loads(raw);new=dict(old)
    if old['status']!='PROPOSED_ROOT_RECEIPT_NOT_APPROVED' or old['accepted_credits']!=0 or old['root_acceptance'] is not None or any(c['decision_effective'] for c in old['credits']):
        raise ValueError('Only an unapproved proposal can receive this context update')
    new['current_context']=dict(source='Root message; no live status query by this helper',updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        C12='FAILED',C12_running=False,C12_successful_jobs=0,C12_planned_jobs=12,C12_historical_reported_pid=634952,
        C12_failure='First source_started omitted pipeline_sample_rate; unchanged bb1b full-source validator rejected.',
        C12_repair='Application preparing additive producer fix and model-free review; old source and actual failed output preserved.',
        scorer_closed_before_C12_launch_sec=25.6,scorer_running=False,physical_recovery_remains_separate=True,
        derived_from=origin,context_revision_source=binding(__file__),context_revision_readme=binding(Path(__file__).with_name('README_S6D_NATIVE68_CONTEXT_REVISION_V2.md')),
        authority='Context update only; no retention/cache/queue approval, no credit effect or new scientific claim.')
    if {k:v for k,v in new.items() if k!='current_context'}!={k:v for k,v in old.items() if k!='current_context'}:
        raise ValueError('Non-context field changed')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(new,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps(dict(proposal=binding(out),only_changed_top_level_field='current_context',accepted_credits=0,root_approval_created=False)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);a=parser.parse_args();main(a.output)
