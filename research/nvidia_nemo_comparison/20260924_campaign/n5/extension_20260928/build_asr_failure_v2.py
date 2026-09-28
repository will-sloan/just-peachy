"""Use the actual in-memory journal's persisted counters. README_ASR_FAILURE_V2.md."""
from pathlib import Path
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent


def main():
    names=['asr_failure_child_v1.py','asr_failure_harness_v1.py','prepare_asr_failure_v1.py','review_asr_failure_v1.py']
    targets=[HERE/n.replace('_v1.py','_v2.py') for n in names]+[HERE/'ASR_FAILURE_DERIVATION_V2.json']
    if any(p.exists() for p in targets):raise FileExistsError('Fresh output required')
    receipt=dict(schema='extended-asr-failure-derivation-v2',parents={},outputs={})
    for name,target in zip(names,targets):
        p=HERE/name;raw=p.read_bytes();text=raw.decode('utf-8')
        receipt['parents'][name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        for old in names:
            new=old.replace('_v1.py','_v2.py')
            text=text.replace(old,new).replace(old[:-3]+' import',new[:-3]+' import')
        text=text.replace('README_ASR_FAILURE_V1.md','README_ASR_FAILURE_V2.md').replace('EXTENDED_WINDOWS_ASR_FAILURE_V1','EXTENDED_WINDOWS_ASR_FAILURE_V2')
        if name=='asr_failure_child_v1.py':
            marker="                controller.start_file(a['audio']['path']);idle();pump(lambda:controller.state=='ERROR')"
            assert text.count(marker)==1
            text=text.replace(marker,"                before=set((data/'sessions').glob('*/session_finalization_v3.json'))\n"+marker)
            start=text.index("                journals=[bind(p)")
            end=text.index("                freeze(output/(case+'-CLOSURE.json'),proof)",start)
            text=text[:start]+'''                after=set((data/'sessions').glob('*/session_finalization_v3.json'))
                require(len(after-before)==1,'Expected exactly one new failed epoch')
                final_path=(after-before).pop();final=load(final_path)
                summary_path=final_path.parent/'session_summary.json';summary=load(summary_path)
                require(final['state']=='FAILED' and final['source_samples']==final['identity_samples']==0,
                    'Startup failure accepted source or identity samples')
                require(not final['live_lanes_at_finalization'] and final['event_and_transcript_handles_closed']
                    and final['finalization_error'] is None,'Failed epoch did not finalize')
                t=summary['telemetry']
                require(t['source_duration_sec']==t['asr_cursor_sec']==t['speaker_cursor_sec']==0,
                    'Startup failure advanced an inference cursor')
                proof=dict(case=case,config=bind(config),observation=bind(output/(case+'.json')),
                    cleanup=cleanup,native_asr_absent=True,finalization=bind(final_path),summary=bind(summary_path))
'''+text[end:]
        if name=='review_asr_failure_v1.py':
            start=text.index("        require(proof['journals']")
            end=text.index("        proofs.append(bind(proof_path))",start)
            text=text[:start]+'''        verify(proof['finalization']);verify(proof['summary'])
        final=load(proof['finalization']['path']);summary=load(proof['summary']['path'])
        require(final['state']=='FAILED' and final['source_samples']==final['identity_samples']==0,
                'Failure accepted samples')
        require(not final['live_lanes_at_finalization'] and final['event_and_transcript_handles_closed']
                and final['finalization_error'] is None,'Finalization incomplete')
        t=summary['telemetry']
        require(t['source_duration_sec']==t['asr_cursor_sec']==t['speaker_cursor_sec']==0,'Failure advanced cursors')
'''+text[end:]
        if name=='prepare_asr_failure_v1.py':
            marker="    code=list({b['path']:b for b in code}.values())"
            text=text.replace(marker,"    code += [bind(HERE/f) for f in ('build_asr_failure_v2.py','ASR_FAILURE_DERIVATION_V2.json','README_ASR_FAILURE_V2.md')]\n"+marker)
        ast.parse(text)
        with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
        data=target.read_bytes();receipt['outputs'][target.name]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    with targets[-1].open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print(dict(status='PREPARED_NOT_EXECUTED',outputs=list(receipt['outputs'])))


if __name__=='__main__':main()
