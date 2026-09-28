"""Generate a fresh paired shadow application harness. See README_SHADOW_RUN.md."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Expected one source anchor: ' + old[:70])
    return source.replace(old, new, 1)


def main():
    raw = (HERE / 'lifecycle_v1.py').read_bytes()
    if hashlib.sha256(raw).hexdigest() != '80cf103837c2958af5078f306837a95367d4d370631078daf4b1f39a1356f85c':
        raise ValueError('Qualified lifecycle harness changed')
    source = raw.decode('utf-8').replace('\r\n', '\n')
    source = source.replace('PREPI_WINDOWS_LIFECYCLE_V1', 'PREPI_WINDOWS_SHADOW_V1')
    source = replace_once(source, 'import traceback', 'import traceback\nimport hashlib')
    source = replace_once(source, "    return a\n", """    verify(a['shadow_reference_review']);verify(a['shadow_reference_result'])
    reviewed=load(a['shadow_reference_review']['path'])
    require(reviewed['status']=='PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY' and reviewed['backend_key']==a['backend_key'],'Ungated reference not reviewed')
    require(reviewed['phases'][0]['result']==a['shadow_reference_result'],'Reference phase binding differs')
    return a
""")
    source = replace_once(source, '            import app.controller\n', '''            import app.controller
            import app.pipeline
            from shadow_gate_v1 import install
            shadow_observers=install(app.pipeline) if phase=='infer' else []
''')
    source = replace_once(source, "                result['paired_parity_passed']=a['arm']=='candidate'", """                result['paired_parity_passed']=a['arm']=='candidate'
                require(len(shadow_observers)==1,'Expected one instrumented saved-file source')
                shadow=shadow_observers[0].report()
                with wave.open(a['audio']['path'],'rb') as wav:
                    pcm_hash=hashlib.sha256(wav.readframes(wav.getnframes())).hexdigest()
                require(shadow['samples']==result['expected_samples'] and shadow['source_pcm_sha256']==pcm_hash,'Observed PCM changed or incomplete')
                require(shadow['actually_skipped_samples']==0,'Shadow removed input')
                reference=load(a['shadow_reference_result']['path'])
                for key in ('expected_samples','source_samples','asr_samples','identity_samples',
                            'activity_frame_count','activity_fingerprint','caption_fingerprint','stored_caption_fingerprint'):
                    require(result[key]==reference[key],'Shadow changed matched output: '+key)
                freeze(output/'SHADOW.json',shadow)
                result['shadow']=bind(output/'SHADOW.json')
                result['shadow_parity_passed']=True
""")
    source = source.replace("scope='One saved source, '", "scope='Paired shadow diagnostics with every source sample retained; one saved source, '")
    source = source.replace('See prepi_20260928/README.md.', 'See README_SHADOW_RUN.md.')
    prepare = (HERE / 'prepare_lifecycle_v1.py').read_text(encoding='utf-8')
    prepare = prepare.replace('lifecycle_v1.py', 'shadow_lifecycle_v1.py')
    prepare = prepare.replace('PREPI_WINDOWS_LIFECYCLE_V1', 'PREPI_WINDOWS_SHADOW_V1')
    prepare = replace_once(prepare, '    cap=128*1024**2', """    ref_name='a0-d1-e0-v2' if backend=='nemotron_hybrid' else 'a2-d1-e0-v1'
    ref_review=bind(base/(ref_name+'-REVIEW.json'));ref=load(ref_review['path'])
    if ref['status']!='PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY' or ref['backend_key']!=backend:
        raise ValueError('Matching ungated lifecycle review missing')
    ref_result=ref['phases'][0]['result'];verify(ref_result)
    a.update(shadow_reference_review=ref_review,shadow_reference_result=ref_result)
    cap=128*1024**2""")
    prepare = replace_once(prepare, "    code=list({b['path']:b for b in code}.values())", """    code += [bind(HERE/f) for f in ('shadow_gate_v1.py','test_shadow_gate_v1.py',
        'build_shadow_harness_v1.py','README_SHADOW.md','README_SHADOW_RUN.md')]
    code += [ref_review,ref_result]
    code=list({b['path']:b for b in code}.values())""")
    prepare = prepare.replace('See README.md.', 'See README_SHADOW_RUN.md.')
    for name, text in [('shadow_lifecycle_v1.py', source), ('prepare_shadow_lifecycle_v1.py', prepare)]:
        compile(text, name, 'exec')
        with (HERE / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    print('Prepared shadow harness; no model or application was started.')


if __name__ == '__main__':
    import psutil
    psutil.Process().cpu_affinity([14])
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    main()
