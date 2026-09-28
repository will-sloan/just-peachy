"""Derive bounded early-Stop/full-restart harnesses; see README_EARLY_STOP.md."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prepi_20260928"
HASHES = {
    "e0_lifecycle_v1.py": "96a8ed353f283fd708faea4a1966de56d88154ab89f518b0f2dfdbe88b4ccb8d",
    "prepare_e0_lifecycle_v1.py": "7b70537a077c8ddf395c28cd5e35a7ab9b75a85c69f0e26b750d4094a8e22a90",
    "review_e0_lifecycle_v1.py": "1472d43b922859d642e4cd972aba99f45580d1d4a0ce0d783652480009b279ad",
}


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Parent transformation anchor differs: " + old[:100])
    return source.replace(old, new, 1)


def main():
    originals = {}
    for name, expected in HASHES.items():
        raw = (PARENT / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Frozen parent changed: " + name)
        originals[name] = raw.decode("utf-8").replace("\r\n", "\n")
    s = originals["e0_lifecycle_v1.py"]
    s = s.replace("PREPI_WINDOWS_E0_RUNTIME_V1", "EXTENDED_WINDOWS_EARLY_STOP_V1")
    s = replace_once(s, "HERE = CODE.parent", "HERE = CODE.parent\nsys.path.append(str(HERE/'prepi_20260928'))")
    anchor = "                controller.start_file(a['audio']['path']); pump(lambda:controller.commands.unfinished_tasks==0)"
    early = '''                # First epoch: explicit user-style Stop while the source is still arriving.
                controller.start_file(a['audio']['path']); pump(lambda:controller.commands.unfinished_tasks==0)
                early_engine=controller.engine; require(early_engine is not None,'Early epoch absent')
                with wave.open(a['audio']['path'],'rb') as wav: full_samples=wav.getnframes()
                require(full_samples>16*16000,'Early-Stop fixture must exceed 16 seconds')
                pump(lambda:early_engine._journal.committed_samples>=8*16000)
                before_stop=early_engine._journal.committed_samples
                require(before_stop<full_samples,'Source already ended before Stop')
                early_identifier=controller.conversation_id
                requested_at=time.monotonic(); controller.stop()
                pump(lambda:controller.commands.unfinished_tasks==0 and controller.state=='STOPPED')
                early=early_engine.telemetry(); early_samples=early_engine._journal.committed_samples
                early_asr=(early['n3_input_samples'] if a['backend_key']=='nemotron_600m' else round(early['asr_cursor_sec']*16000))
                require(0<early_samples<full_samples,'Early Stop did not truncate source delivery')
                require(early_asr==early_samples==early['identity_audio_samples'],'Early epoch failed to drain accepted samples')
                require(early['speaker_lag_sec']==0,'Early speaker lane did not drain')
                require(all(w.accepted==w.completed and not w.error for w in early_engine.text_writers),'Early writers did not drain')
                require(controller.engine is None and controller.consumer is None,'Early epoch ownership retained')
                require(not early.get('live_lanes_at_finalization') and not early.get('bundle_retained_due_live_lanes'),'Early native lane retained')
                cleanup=controller.metrics.get('last_worker_cleanup',{})
                require(cleanup.get('owned_threads_joined') is True,'Early worker cleanup unverified')
                require(len(shadow_observers)==1,'Early source observation absent')
                early_shadow=shadow_observers[0].report()
                with wave.open(a['audio']['path'],'rb') as wav:
                    early_pcm=hashlib.sha256(wav.readframes(early_samples)).hexdigest()
                require(early_shadow['samples']==early_samples and early_shadow['source_pcm_sha256']==early_pcm,'Early prefix differs')
                require(early_shadow['actually_skipped_samples']==0,'Early observer skipped audio')
                result['early_stop']=dict(requested_after_samples=before_stop,source_samples=early_samples,
                    asr_samples=early_asr,identity_samples=early['identity_audio_samples'],
                    full_file_samples=full_samples,speaker_lag_sec=early['speaker_lag_sec'],
                    stop_to_drained_sec=time.monotonic()-requested_at,workers_joined=True,
                    accepted_prefix_sha256=early_pcm,actually_skipped_samples=0,
                    completed_sessions=controller.metrics.get('completed_sessions',0),
                    telemetry=early,cleanup=cleanup)
                require(controller.session_store.folder(early_identifier).exists(),'Early session archive absent')
                freeze(output/'EARLY_SESSION.json',dict(identifier=early_identifier))
                prior_completed=controller.metrics.get('completed_sessions',0)
                # Second epoch: explicit start_file restarts at sample zero with cached models.
'''
    s = replace_once(s, anchor, early + anchor)
    s = replace_once(s, "controller.metrics.get('completed_sessions',0)>=1", "controller.metrics.get('completed_sessions',0)>=prior_completed+1")
    s = replace_once(s, "require(len(shadow_observers)==1,'Expected one instrumented saved-file source')\n                shadow=shadow_observers[0].report()",
                     "require(len(shadow_observers)==2,'Expected early and restarted file sources')\n                require(result['model_cache']['streams']==2,'Expected two streams with resident models')\n                shadow=shadow_observers[1].report()")
    s = replace_once(s, "                result['test_session_deleted']=True", """                result['test_session_deleted']=True
                earlier=load(output.parent/'infer/EARLY_SESSION.json')
                command('delete',identifier=earlier['identifier'],confirmed=True)
                require(not controller.session_store.folder(earlier['identifier']).exists(),'Early test session not deleted')
                result['early_test_session_deleted']=True""")
    s = s.replace("scope='E0 runtime without TitaNet fields;", "scope='Early Stop, accepted-prefix drain and full-file restart with resident E0/ASR models;")
    s = s.replace("See README_E0_RUN.md.", "See README_EARLY_STOP.md.")

    prep = originals["prepare_e0_lifecycle_v1.py"]
    prep = prep.replace("PREPI_WINDOWS_E0_RUNTIME_V1", "EXTENDED_WINDOWS_EARLY_STOP_V1")
    prep = replace_once(prep, "N5=HERE.parent", "N5=HERE.parent\nLEGACY=N5/'prepi_20260928'")
    prep = prep.replace("bind(HERE/f)", "bind(LEGACY/f)")
    prep = replace_once(prep, "    code += [ref_review,ref_result]", """    code += [bind(HERE/f) for f in ('early_stop_lifecycle_v1.py','prepare_early_stop_v1.py',
        'build_early_stop_v1.py','review_early_stop_v1.py','README_EARLY_STOP.md',
        'window_guard.py','WINDOW.json','GUARD_DERIVATION.json')]
    code += [ref_review,ref_result]""")
    prep = replace_once(prep, "str(HERE/'e0_lifecycle_v1.py')", "str(HERE/'early_stop_lifecycle_v1.py')")
    prep = prep.replace("See README_E0_RUN.md.", "See README_EARLY_STOP.md.")

    review = originals["review_e0_lifecycle_v1.py"]
    review = review.replace("PREPI_WINDOWS_E0_RUNTIME_V1", "EXTENDED_WINDOWS_EARLY_STOP_V1")
    anchor = "            t=result['telemetry']"
    checks = '''            e=result['early_stop']
            require(0<e['requested_after_samples']<=e['source_samples']<e['full_file_samples'],'Not an early Stop')
            require(e['source_samples']==e['asr_samples']==e['identity_samples'],'Early accepted-prefix drain differs')
            require(e['speaker_lag_sec']==0 and e['workers_joined'] and e['actually_skipped_samples']==0,'Early drain/ownership failure')
            require(e['cleanup']['owned_threads_joined'],'Early cleanup missing')
            import hashlib,wave
            with wave.open(a['audio']['path'],'rb') as wav:
                require(hashlib.sha256(wav.readframes(e['source_samples'])).hexdigest()==e['accepted_prefix_sha256'],'Early source prefix hash differs')
            require(result['model_cache']['streams']==2,'Not two resident-model streams')
'''
    review = replace_once(review, anchor, checks+anchor)
    review = replace_once(review, "summary=dict(shadow=shadow_summary,", "summary=dict(early_stop=e,shadow=shadow_summary,")
    review = replace_once(review, "else:require(result['test_session_deleted'],'Delete not verified')", "else:require(result['test_session_deleted'] and result.get('early_test_session_deleted'),'Both test session deletions unverified')")
    review = review.replace("PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY", "PASS_EARLY_STOP_AND_FULL_RESTART_WINDOWS_ONLY")
    review = review.replace("scope='Paired one-file 1x saved-source Windows shadow proposals with unchanged PCM, captions/timestamps and native activity; no audio skipping or inference saving'", "scope='One early stopped prefix drained then same full saved file restarted; exact full reference parity and resident model reuse; Windows only, no sustained performance qualification'")
    review = review.replace("See README_E0_RUN.md.", "See README_EARLY_STOP.md.")
    outputs = {"early_stop_lifecycle_v1.py": s, "prepare_early_stop_v1.py": prep, "review_early_stop_v1.py": review}
    for name, source in outputs.items():
        if (HERE/name).exists(): raise FileExistsError(name)
        compile(source, name, "exec")
    for name, source in outputs.items():
        with (HERE/name).open('x', encoding='utf-8', newline='\n') as f: f.write(source)
    receipt = dict(parent_hashes=HASHES, child_hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in outputs},
                   application_source_changed=False, models_started=False)
    with (HERE/'EARLY_STOP_DERIVATION.json').open('x',encoding='utf-8') as f: json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))


if __name__ == "__main__": main()
