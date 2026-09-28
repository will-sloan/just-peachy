"""Actual empty-store UI and transfer protocol. README_EMPTY_STORE_V1.md."""
import json
from pathlib import Path
import zipfile
from common import bind,freeze


def exercise(controller,ui,a,output,idle,require,check_error):
    from app.mode_policy import MODE_METADATA,SELECTED_MODES,SEAT_MODES,SPATIAL_PARENTS
    from app.backends import backend_status
    controls=[];selected=controller.backend_id
    require(controller.store.list()==[],'Isolated store must be empty')
    def choose(mode):
        if MODE_METADATA[mode]['advanced']:ui.show_advanced()
        else:ui.show_modes()
        require('mode_'+mode in ui.actions,'Mode hidden from actual UI: '+mode)
        ui.actions['mode_'+mode].invoke();idle()
    def displayed(widget):
        values=[]
        try:values.append(str(widget.cget('text')))
        except Exception:pass
        for child in widget.winfo_children():values.extend(displayed(child))
        return values
    # All modes remain visible. Draft-only choices must not change the active mode.
    for mode in MODE_METADATA:
        if mode in ('caption_only','anonymous_conversation'):continue
        previous=controller.mode;choose(mode)
        if mode in SEAT_MODES:
            require(ui.page=='seats' and not ui._seat_draft,'Seat editor populated or absent')
            ui.actions['seat_cancel'].invoke();idle()
            require(controller.mode==previous,'Seat cancel changed active mode')
            outcome='EMPTY_SEAT_DRAFT_CANCELLED'
        elif mode in SELECTED_MODES:
            require(ui.page=='roster' and not ui._roster_draft,'Roster unexpectedly populated')
            require(str(ui.actions['roster_apply'].cget('state'))=='disabled','Empty matching roster can apply')
            ui.actions['roster_cancel'].invoke();idle()
            require(controller.mode==previous,'Roster cancel changed active mode')
            outcome='EMPTY_ROSTER_DISABLED_CANCELLED'
        else:
            require(controller.mode==mode and controller.error is None,'Mode selection failed')
            outcome='SELECTED_IDLE'
        status=backend_status(selected,mode,'O0',recorded_spatial=False)
        if mode in SPATIAL_PARENTS:
            ui.show_modes();text='\n'.join(displayed(ui.root))
            require(not status['available'] and status['reason'] in text,'Spatial unavailability hidden')
        controls.append(dict(mode=mode,outcome=outcome,available_without_spatial=status['available'],
                             unavailable_reason=None if status['available'] else status['reason']))
    # Empty selected gallery must also fail at the controller boundary.
    choose('enrolled_names');previous=controller.mode
    controller.switch(mode='selected_focus',selected_ids=[]);idle()
    check_error('empty_matching_roster',selected)
    require(controller.mode==previous and controller.selected_ids==[],'Invalid roster changed state')
    choose('enrolled_names')
    # Empty archives contain no identities or vectors. No enrollment is called.
    export=output/'empty-people.zip'
    controller.export_people(export,consent=False);idle();check_error('export_without_consent',selected)
    require(not export.exists(),'Export ignored consent')
    ui._path_chosen('export',export);require('confirm' in ui.actions,'Export confirmation missing')
    ui.actions['cancel'].invoke();idle();require(not export.exists(),'Cancel exported data')
    ui._path_chosen('export',export);ui.actions['confirm'].invoke();idle()
    require(controller.error is None and export.exists(),'Confirmed empty export failed')
    with zipfile.ZipFile(export) as z:
        require(z.namelist()==['MANIFEST.json'],'Empty export included payload')
        manifest=json.loads(z.read('MANIFEST.json'))
        require(manifest['schema_version']==1 and manifest['files']=={},'Empty archive schema differs')
    controller.import_people(export,consent=False);idle();check_error('import_without_consent',selected)
    ui._path_chosen('import',export);ui.actions['cancel'].invoke();idle()
    require(controller.store.list()==[],'Cancelled import changed profiles')
    ui._path_chosen('import',export);ui.actions['confirm'].invoke();idle()
    require(controller.error is None and controller.store.list()==[],'Empty round trip failed')
    bad=output/'unsupported-schema.zip'
    with zipfile.ZipFile(bad,'x') as z:z.writestr('MANIFEST.json',json.dumps(dict(schema_version=99,files={})))
    ui._path_chosen('import',bad);ui.actions['confirm'].invoke();idle();check_error('invalid_archive',selected)
    require('Invalid archive manifest' in controller.error and controller.store.list()==[],'Bad archive altered store')
    require(controller.models.asr_loads==controller.models.speaker_loads==controller.models.streams==0,'Controls ran inference')
    choose('enrolled_names');ui.show_recipes();ui.actions['recipe_balanced'].invoke();idle()
    require(controller.error is None and controller.mode=='enrolled_names','All-enrolled setup failed')
    transfer=dict(export=bind(export),invalid_archive=bind(bad),profile_count=0,consent_cancel_and_confirm=True,
                  successful_model_allocations_before_inference=0)
    freeze(output/'TRANSFER.json',transfer)
    return dict(controls=controls,transfer=bind(output/'TRANSFER.json'))


def naming_proof(controller,engine,output,require):
    gallery=engine._research_gallery
    require(gallery is not None and gallery.ids==[],'Expected an explicit empty all-enrolled gallery')
    decisions=list(engine._n2_names.values())
    require(decisions and engine.n2_name_map.calls>0,'No actual naming decisions exercised')
    labels=[d.get('display_label') for d in decisions]
    require(set(labels)=={'Unknown'},'Empty named gallery did not retain constant Unknown')
    require(all(not d.get('known_name') and not d.get('known_profile_id') for d in decisions),'Invented personal identity')
    rows=controller.snapshot()['rows'];require(rows,'No captions')
    def identities(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key in ('known_name','known_profile_id') and value:yield value
                yield from identities(value)
        elif isinstance(obj,list):
            for value in obj:yield from identities(value)
    require(not list(identities(rows)),'Caption rows contain a personal identity')
    freeze(output/'NAMING.json',dict(gallery_receipt=gallery.receipt,decisions=decisions,rows=rows,
                                   naming_calls=engine.n2_name_map.calls,labels=labels))
    return bind(output/'NAMING.json')
