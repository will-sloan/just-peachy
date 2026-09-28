"""Create reviewable restart harnesses from the frozen lifecycle; README_RESTART.md."""
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent


def build():
    original=(HERE/'lifecycle_v1.py').read_bytes()
    if hashlib.sha256(original).hexdigest()!='80cf103837c2958af5078f306837a95367d4d370631078daf4b1f39a1356f85c':
        raise ValueError('Qualified lifecycle source differs')
    s=original.decode('utf-8').replace('\r\n','\n')
    start=s.index("            if phase=='infer':\n                controller.switch")
    end=s.index("            else:\n                prior=load(output.parent/'infer/SAVED.json')",start)
    body=s[start+len("            if phase=='infer':\n"):end]
    body=body.replace("                controller.start_file(a['audio']['path']);", "                prior_completed=controller.metrics.get('completed_sessions',0)\n                controller.start_file(a['audio']['path']);")
    body=body.replace("controller.metrics.get('completed_sessions',0)>=1", "controller.metrics.get('completed_sessions',0)>=prior_completed+1")
    body=body.replace("freeze(output/'SAVED.json',", "freeze(output/f'SAVED_{cycle}.json',")
    body+='''                restart_rows.append(dict(cycle=cycle,source_samples=result['source_samples'],
                    asr_samples=result['asr_samples'],identity_samples=result['identity_samples'],
                    activity_fingerprint=result['activity_fingerprint'],
                    stored_fingerprint=fingerprint([{k:r.get(k) for k in ('text','display_text','source_start_sec','source_end_sec')} for r in stored])))
                if cycle==0:
                    controller.stop();pump(lambda:controller.commands.unfinished_tasks==0)
                    require(controller.engine is None and controller.consumer is None,'Stop retained first epoch')
'''
    block="            if phase=='infer':\n                restart_rows=[]\n                for cycle in range(2):\n"+''.join('    '+line if line.strip() else line for line in body.splitlines(True))
    block+='''                for key in ('source_samples','asr_samples','identity_samples','activity_fingerprint','stored_fingerprint'):
                    require(restart_rows[0][key]==restart_rows[1][key],'Restart parity differs: '+key)
                result['restart_cycles']=restart_rows
                result['restart_parity_passed']=True
                freeze(output/'SAVED.json',load(output/'SAVED_1.json'))
'''
    s=s[:start]+block+s[end:]
    s=s.replace("    t=result['telemetry']", "    require(result.get('restart_parity_passed') is True and len(result.get('restart_cycles',[]))==2,'Restart evidence missing')\n    require(result['model_cache']['streams']==2,'Resident models not reused for two streams')\n    t=result['telemetry']")
    s=s.replace("                result['test_session_deleted']=True", """                result['test_session_deleted']=True
                earlier=load(output.parent/'infer/SAVED_0.json')
                require(fingerprint(controller.session_store.rows(earlier['identifier']))==earlier['rows_fingerprint'],'First saved session changed')
                command('delete',identifier=earlier['identifier'],confirmed=True)
                require(not controller.session_store.folder(earlier['identifier']).exists(),'First session not deleted')
                result['earlier_session_deleted']=True""")
    s=s.replace('PREPI_WINDOWS_LIFECYCLE_V1','PREPI_WINDOWS_RESTART_V1')
    s=s.replace("scope='One saved source, '","scope='Two EOF/Stop/Start cycles of the same saved source with cached models, '")
    s=s.replace('See prepi_20260928/README.md.','See README_RESTART.md.')
    target=HERE/'restart_lifecycle_v1.py'
    compile(s,str(target),'exec')
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
    prep=(HERE/'prepare_lifecycle_v1.py').read_text(encoding='utf-8')
    prep=prep.replace('PREPI_WINDOWS_LIFECYCLE_V1','PREPI_WINDOWS_RESTART_V1')
    prep=prep.replace("'lifecycle_v1.py'","'restart_lifecycle_v1.py'").replace("'prepare_lifecycle_v1.py'","'prepare_restart_v1.py'")
    prep=prep.replace("'test_window_guard.py','README.md'", "'test_window_guard.py','README_RESTART.md','build_restart_harness_v1.py','README.md'")
    prep=prep.replace('See README.md.', 'See README_RESTART.md.')
    target=HERE/'prepare_restart_v1.py'
    compile(prep,str(target),'exec')
    with target.open('x',encoding='utf-8',newline='\n') as f:f.write(prep)
    print('Prepared fresh restart harness and admission tool; no application started.')


if __name__=='__main__':build()
