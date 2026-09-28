"""Derive private-desktop empty-store checks; see README_EMPTY_STORE_V1.md."""
from pathlib import Path
import ast,hashlib,json
HERE=Path(__file__).resolve().parent

def main():
    names=['controls_child_v3.py','controls_harness_v3.py','prepare_controls_v3.py','review_controls_v3.py']
    rename={n:n.replace('controls','empty_store').replace('_v3','_v1') for n in names}
    targets=[HERE/n for n in rename.values()]+[HERE/'EMPTY_STORE_DERIVATION_V1.json']
    if any(p.exists() for p in targets):raise FileExistsError('Fresh generated paths required')
    receipt=dict(schema='extended-empty-store-derivation-v1',parents={},outputs={})
    for name,target in rename.items():
        raw=(HERE/name).read_bytes();text=raw.decode('utf-8')
        receipt['parents'][name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        for old,new in rename.items():text=text.replace(old,new).replace(old[:-3]+' import',new[:-3]+' import')
        text=text.replace('README_CONTROLS_V3.md','README_EMPTY_STORE_V1.md').replace('EXTENDED_WINDOWS_CONTROLS_V3','EXTENDED_WINDOWS_EMPTY_STORE_V1')
        if name=='controls_child_v3.py':
            start=text.index("            runtime=data/'n2_runtime.json'")
            end=text.index("            controller.session_action('new'",start)
            text=text[:start]+'''            select(a['backend_key'])
            require(controller.error is None and controller.backend_id==selected,'Backend selection failed')
            from empty_store_protocol_v1 import exercise,naming_proof
            result.update(exercise(controller,ui,a,output,idle,require,check_error))
'''+text[end:]
            marker="            select('baseline');require("
            text=text.replace(marker,"            result['naming_proof']=naming_proof(controller,engine,output,require)\n"+marker)
        elif name=='controls_harness_v3.py':
            text=text.replace('Actual Windows controls, isolated invalid runtime and missing D1 startup, recovery prefix and explicit baseline rollback.',
                              'Actual Windows empty roster and profile-transfer controls, empty all-enrolled inference prefix and baseline rollback.')
        elif name=='prepare_controls_v3.py':
            marker="    code=list({b['path']:b for b in code}.values())"
            text=text.replace(marker,"    code += [bind(HERE/f) for f in ('build_empty_store_v1.py','empty_store_protocol_v1.py','EMPTY_STORE_DERIVATION_V1.json','README_EMPTY_STORE_V1.md')]\n"+marker)
        else:
            start=text.index("    require([x['case'] for x in c['cases']]")
            end=text.index("    s=c['recovery'];",start)
            text=text[:start]+'''    require([x['case'] for x in c['cases']]==['empty_matching_roster','export_without_consent','import_without_consent','invalid_archive'],'Missing boundary cases')
    for x in c['cases']:
        require(x['state']=='ERROR' and x['error'][:120] in x['rendered_error'] and x['backend_id']==c['backend_id'],'Hidden failure or fallback')
        require(x['models']==dict(asr_loads=0,speaker_loads=0,streams=0),'Boundary check ran inference')
    expected={'enrolled_names':'SELECTED_IDLE','open_with_names':'SELECTED_IDLE',
              'spatial_assisted':'SELECTED_IDLE','strongly_spatial_assisted':'SELECTED_IDLE',
              'selected_focus':'EMPTY_ROSTER_DISABLED_CANCELLED','selected_closed':'EMPTY_ROSTER_DISABLED_CANCELLED',
              'spatial_selected':'EMPTY_ROSTER_DISABLED_CANCELLED','strongly_spatial_selected':'EMPTY_ROSTER_DISABLED_CANCELLED',
              'assigned_direction':'EMPTY_SEAT_DRAFT_CANCELLED','assigned_hybrid':'EMPTY_SEAT_DRAFT_CANCELLED'}
    require({x['mode']:x['outcome'] for x in c['controls']}==expected,'Mode coverage differs')
    for x in c['controls']:
        if x['mode'].startswith(('spatial','strongly_spatial','assigned')):
            require(not x['available_without_spatial'] and x['unavailable_reason'],'Missing spatial reason')
    verify(c['transfer']);transfer=load(c['transfer']['path'])
    verify(transfer['export']);verify(transfer['invalid_archive'])
    import zipfile,json
    with zipfile.ZipFile(transfer['export']['path']) as z:
        require(z.namelist()==['MANIFEST.json'] and json.loads(z.read('MANIFEST.json'))['files']=={},'Empty transfer included profiles')
    require(transfer['profile_count']==transfer['successful_model_allocations_before_inference']==0 and transfer['consent_cancel_and_confirm'],'Transfer scope differs')
    verify(c['naming_proof']);naming=load(c['naming_proof']['path'])
    require(naming['gallery_receipt']['loaded_count']==0 and naming['naming_calls']>0 and naming['rows'],'Empty gallery not exercised')
    require(set(naming['labels'])=={'Unknown'} and naming['decisions'],'Unexpected labels')
    require(all(not d.get('known_name') and not d.get('known_profile_id') for d in naming['decisions']),'Invented identity')
'''+text[end:]
            text=text.replace('PASS_WINDOWS_CONTROLS_STARTUP_RECOVERY_ONLY','PASS_WINDOWS_EMPTY_STORE_AND_UNKNOWN_ONLY')
            text=text.replace("controls=c['controls'],cases=c['cases']","controls=c['controls'],cases=c['cases'],transfer=c['transfer'],naming_proof=c['naming_proof']")
        ast.parse(text);path=HERE/target
        with path.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
        raw=path.read_bytes();receipt['outputs'][target]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    with targets[-1].open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2)
    print(dict(status='PREPARED_NOT_EXECUTED',outputs=list(receipt['outputs'])))

if __name__=='__main__':main()
