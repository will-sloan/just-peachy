"""Bounded actual native caption/archive and text-only tests. See README_TEXT_ASSISTANCE.md."""
import argparse
from importlib.metadata import version
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
import psutil
import sherpa_onnx
from app.controller import Controller
from app.paths import default_models_root
from app.sessions import records
from app.text_assistance import TextAssistance,BIAS_UNAVAILABLE


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wav',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();proc=psutil.Process();cpu=proc.cpu_times();c=None
    result={'status':'RUNNING','scope':'One actual native saved-audio caption session; separate synthetic text edge cases. No mic, playback or acoustic-bias A/B.'}
    try:
        c=Controller(args.output_dir/'data',default_models_root())
        c.text_assistance_action('switch',enabled=True,automatic=True);c.commands.join();assert not c.error,c.error
        c.text_assistance_action('add',preferred='Captain Cook',alias='captain cook',context='empiricist',kind='name',approved_auto=True,approved=True)
        c.commands.join();assert not c.error,c.error
        c.start_file(args.wav);c.commands.join();assert not c.error,c.error
        # Functional completion wait inside ordinary Python, no model polling.
        deadline=time.monotonic()+60
        while c.state in ('RUNNING','STARTING','STOPPING') and time.monotonic()<deadline:time.sleep(.1)
        if c.error or c.state!='STOPPED':raise RuntimeError(c.error or 'Native session did not close')
        c._stop_session()
        identifier=c.conversation_id;store=c.session_store;rows=store.rows(identifier);assert rows
        epoch=store.metadata(identifier)['epochs'][0];folder=store.epoch(identifier,epoch)
        raw=[x for x in records(folder/'events.jsonl') if x['kind']=='s6d_display']
        bykey={x['payload']['caption_key']:x['payload'] for x in raw}
        assert all(r['text']==bykey[r['caption_key']]['text'] for r in rows)
        assisted=[r for r in rows if r.get('text_assistance') and r['text_assistance'].get('enabled')]
        assert assisted,'Real native finals did not exercise assistance'
        assert all(r['text_assistance']['source']['caption_key']==r['caption_key'] for r in assisted)
        native_ms=[r['text_assistance']['compute_ms'] for r in assisted]
        native_examples=[{'raw':r['text'],'final':r.get('archived_final_formatted_text'),
                          'optional_corrected':r['text_assistance']['corrected_text'],'suggestions':r['text_assistance']['suggestions']} for r in assisted]
        (args.output_dir/'PRIVATE_NATIVE_EXAMPLES.json').write_text(json.dumps(native_examples,indent=2),encoding='utf-8')
        assert all(r['text_assistance']['corrected_text'] is None for r in assisted),'Unnecessary native lexical correction'
        original_journal=sha(folder/'events.jsonl');first=rows[0]
        store.annotate(identifier,'',row_id=first['caption_key'],correction='Explicit fixture manual edit.')
        edit=store.metadata(identifier)['corrections'][-1];store.undo_correction(identifier,edit['id'])
        assert sha(folder/'events.jsonl')==original_journal and store.rows(identifier)==rows
        c._do_session_action('open',{'identifier':identifier});assert any(r['raw_asr_text'] for r in c.snapshot()['rows'])
        c.text_assistance_action('switch',enabled=False);c.commands.join()
        assert not any(r['show_corrected_text'] for r in c.snapshot()['rows'])
        result['native']={'caption_count':len(rows),'assisted_finals':len(assisted),'raw_journal_preserved':True,
            'applied_text_edits':sum(len(r['text_assistance']['applied']) for r in assisted),
            'max_assistance_ms':max(native_ms),'mean_assistance_ms':sum(native_ms)/len(native_ms),
            'manual_undo_original_sha256':original_journal,'model_loads':{'asr':c.models.asr_loads,'speaker':c.models.speaker_loads},
            'asr_decoding_method':c.config.asr_decoding_method,'source_sha256':sha(args.wav)}
        assert c.config.asr_decoding_method=='greedy_search'
        result['assets']={a.component_id:{'expected':a.sha256,'actual':sha(a.path)} for a in c.config.assets}
        assert all(x['expected']==x['actual'] for x in result['assets'].values())
        # Original examples exercise safety; they are text fixtures, not ASR gains.
        assistant=TextAssistance(args.output_dir/'text_fixture.json');people=[{'id':'amir','name':'Amir'}]
        assistant.change('switch',{'enabled':True,'automatic':True},people)
        assistant.change('add',dict(preferred='Amir',alias='Emir',context='Peachy',kind='name',person_id='amir',approved=True,approved_auto=True),people)
        cases=[('generic_typo','The camptions are visible.',people,None),
               ('authorized_context','Emir joined Peachy.',people,'Amir joined Peachy.'),
               ('no_context','The emir spoke.',people,None),('substring','Peachy emirates.',people,None),
               ('real_other_emir','Emir joined Peachy.',people+[{'id':'other','name':'Emir'}],None),
               ('negation','Emir did not join Peachy.',people,None),('number','Emir brought 2 tablets to Peachy.',people,None),
               ('pronoun','He called Emir at Peachy.',people,None),('safety','Emir needs insulin at Peachy.',people,None)]
        examples=[]
        for label,text,roster,expected in cases:
            r=assistant.analyze(text,roster);assert r['corrected_text']==expected,label
            examples.append({'case':label,'before':text,'corrected':r['corrected_text'],'suggestions':r['suggestions'],'compute_ms':r['compute_ms']})
        result['text_fixture_examples']=examples
        result['bias']={'available':False,'reason':BIAS_UNAVAILABLE,'native_ab':'NOT_RUN; unsupported qualified ASR tokenizer binding',
                        'sherpa_version':version('sherpa-onnx'),'api_signature':str(inspect.signature(sherpa_onnx.OnlineRecognizer.from_transducer)),
                        'installed_api_sha256':sha(Path(inspect.getsourcefile(sherpa_onnx.OnlineRecognizer))),
                        'matching_asr_bpe_assets':[a.component_id for a in c.config.assets if 'bpe' in a.component_id and 'punctuation' not in a.component_id]}
        result['code_sha256']={str(p.relative_to(ROOT)):sha(p) for d in ('app','vendor','config') for p in (ROOT/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
        result['status']='PASS'
    except Exception:
        import traceback
        result['status']='FAIL';result['error']=traceback.format_exc()
    finally:
        if c:
            c.close();c.commands.join();c.worker.join(10);result['closed']=c.closed
        result['elapsed_sec']=time.perf_counter()-started;endcpu=proc.cpu_times()
        result['cpu_sec']=endcpu.user+endcpu.system-cpu.user-cpu.system
        memory=proc.memory_info();result['peak_rss_mib']=getattr(memory,'peak_wset',memory.rss)/2**20
        (args.output_dir/'NATIVE_TEXT_CHECK.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('status','native','elapsed_sec','cpu_sec','peak_rss_mib','closed','error')}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
