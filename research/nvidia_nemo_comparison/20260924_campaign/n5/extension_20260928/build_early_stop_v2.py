"""Make explicit New-transcript restart test; see README_EARLY_STOP_V2.md."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def replace_once(text, old, new):
    if text.count(old) != 1: raise ValueError("Unexpected parent anchor: " + old[:80])
    return text.replace(old, new, 1)


def main():
    parent = json.loads((HERE/'EARLY_STOP_DERIVATION.json').read_text())
    source = {}
    for name, expected in parent['child_hashes'].items():
        raw=(HERE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected: raise ValueError("Parent changed: "+name)
        source[name]=raw.decode('utf-8')
    s=source['early_stop_lifecycle_v1.py']
    s=replace_once(s,"                freeze(output/'EARLY_SESSION.json',dict(identifier=early_identifier))", """                early_rows_hash=fingerprint(controller.session_store.rows(early_identifier))
                freeze(output/'EARLY_SESSION.json',dict(identifier=early_identifier,rows_fingerprint=early_rows_hash))
                command('new',audio=False,consent=False)
                require(controller.conversation_id!=early_identifier,'New transcript did not change conversation')
                require(not controller.snapshot()['rows'],'New transcript retained old visible rows')
                require(fingerprint(controller.session_store.rows(early_identifier))==early_rows_hash,'New transcript changed earlier draft')
                result['early_stop']['explicit_new_transcript']=True
                result['early_stop']['earlier_draft_preserved']=True""")
    s=replace_once(s,"                command('delete',identifier=earlier['identifier'],confirmed=True)", """                require(fingerprint(controller.session_store.rows(earlier['identifier']))==earlier['rows_fingerprint'],'Earlier draft changed across restart')
                command('delete',identifier=earlier['identifier'],confirmed=True)""")
    prep=source['prepare_early_stop_v1.py']
    prep=replace_once(prep,"    code += [ref_review,ref_result]", """    code += [bind(HERE/f) for f in ('build_early_stop_v2.py','EARLY_STOP_V2_DERIVATION.json',
        'README_EARLY_STOP_V2.md','early_stop_lifecycle_v1.py','prepare_early_stop_v1.py',
        'review_early_stop_v1.py','EARLY_STOP_DERIVATION.json')]
    code += [ref_review,ref_result]""")
    # Rename generated-v2 execution and primary code bindings, retaining explicit
    # v1 ancestry as extra bindings after the replacement.
    for old,new in [('early_stop_lifecycle_v1.py','early_stop_lifecycle_v2.py'),
                    ('prepare_early_stop_v1.py','prepare_early_stop_v2.py'),
                    ('review_early_stop_v1.py','review_early_stop_v2.py')]:
        prep=prep.replace(old,new)
    review=source['review_early_stop_v1.py']
    review=replace_once(review,"            e=result['early_stop']", """            e=result['early_stop']
            require(e.get('explicit_new_transcript') and e.get('earlier_draft_preserved'),'New-transcript boundary absent')""")
    outputs={'early_stop_lifecycle_v2.py':s,'prepare_early_stop_v2.py':prep,'review_early_stop_v2.py':review}
    for name,text in list(outputs.items()):
        text=text.replace('EXTENDED_WINDOWS_EARLY_STOP_V1','EXTENDED_WINDOWS_STOP_NEW_RESTART_V2')
        text=text.replace('PASS_EARLY_STOP_AND_FULL_RESTART_WINDOWS_ONLY','PASS_STOP_NEW_TRANSCRIPT_FULL_RESTART_WINDOWS_ONLY')
        text=text.replace('README_EARLY_STOP.md','README_EARLY_STOP_V2.md')
        outputs[name]=text
        if (HERE/name).exists(): raise FileExistsError(name)
        compile(text,name,'exec')
    for name,text in outputs.items():
        with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    receipt=dict(parent_hashes=parent['child_hashes'],child_hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in outputs},
        application_changed=False,reason='V1 omitted New transcript and correctly appended both epochs to one unpinned draft; V2 explicitly tests a separate conversation, retains earlier draft and unchanged full-output parity.')
    with (HERE/'EARLY_STOP_V2_DERIVATION.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))


if __name__=='__main__': main()
