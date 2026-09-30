"""New native method controls only; README_D1_METHOD_CONTROLS_V1.md."""
from copy import deepcopy
import json
from pathlib import Path
import threading

def run(root, admission):
    from field_sidecar_budget_v1 import GroupWriter
    from d1_method_controls_v1 import MethodCatalog, MethodsPanel, controller_class, ui_class, sections, canonical
    import d1_modes_v1 as modes
    root = Path(root);(root/'passage').mkdir();(root/'passage_closure').mkdir()
    writer = GroupWriter(root/'passage', admission['passage_limits'])
    closer = GroupWriter(root/'passage_closure', admission['passage_closure_limits'])
    catalog = MethodCatalog(root/'code/D1_METHOD_CONTRACT_V1.json', root/'code/METHOD_EVIDENCE_V1.json')
    cases = [];profiles = {};texts = {}
    def reject(name, action):
        try:action()
        except ValueError as e:cases.append(dict(case=name, rejected=True, error=str(e)))
        else:raise AssertionError('Expected rejection: '+name)
    for mode in ['delayed', 'streaming', 'chunk52']:
        profile = catalog.request(mode);profiles[mode] = deepcopy(profile)
        for method in ['asr-applied-skip', 'vad-applied-skip', 'parallel-diarizer-pool', 'onnx-full-waveform']:
            reject(mode+'-'+method, lambda m=mode,k=method:catalog.request(m,k))
    # Stand-in Base counts delegation only: no installed constructor/Start/model/source is run.
    class Base:
        def __init__(self):self.d1_lock=threading.RLock();self.d1_selected=None;self.calls=0
        def _do_d1_select(self, mode):
            m=modes.select(mode)
            self.d1_selected=dict(schema='d1-saved-mode-selection.v1',selection=dict(id=mode,catalog_sha256=modes.CATALOG_SHA256,geometry=m['geometry'],retained_run=m['retained_run']),requires_fresh_process=True,requires_independent_session=True,source_scope='saved-input-only',live_start_available=False)
        def _do_d1_start(self):self.calls+=1
        def d1_snapshot(self):return dict(selected=deepcopy(self.d1_selected))
    C=controller_class(Base,catalog);c=C()
    reject('no-selection-start',c._do_d1_start)
    c._do_d1_select('delayed');c._do_d1_start();assert c.calls==1
    cases.append(dict(case='exact-profile-delegation',counted_stub_calls=1))
    snapshot=c.d1_snapshot();snapshot['implemented_methods']['resources']['executable_graph_lru']=99
    assert c.d1_snapshot()['implemented_methods']['resources']['executable_graph_lru']==1
    cases.append(dict(case='detached-snapshot',unchanged=True))
    for name,mutate in [
        ('bool-thread',lambda v:v['resources'].__setitem__('native_threads',True)),
        ('lru-change',lambda v:v['resources'].__setitem__('executable_graph_lru',8)),
        ('asset-change',lambda v:v.__setitem__('main_library_sha256','0'*64)),
        ('extra-skip',lambda v:v.__setitem__('skip_enabled',True))]:
        c.d1_method_profile=catalog.request('delayed');mutate(c.d1_method_profile)
        reject(name,c._do_d1_start);assert c.calls==1
    c.d1_method_profile=catalog.request('delayed');c.d1_selected['selection']['geometry']['fifo_frames']=80
    reject('selected-geometry-change',c._do_d1_start);assert c.calls==1
    c._do_d1_select('delayed')
    import tkinter as tk
    root_tk=tk.Tk(screenName=':0');root_tk.withdraw();errors=[]
    root_tk.report_callback_exception=lambda k,v,t:errors.append(repr(v))
    panels=[];nav=None;destroyed=False
    try:
        for mode in ['delayed','streaming','chunk52']:
            panel=MethodsPanel(root_tk,catalog.request(mode));panel.frame.pack();panels.append(panel)
            texts[mode]={}
            for key in ['kernel','resources','unavailable']:
                panel.buttons[key].invoke();root_tk.update()
                assert not errors and root_tk.state()=='withdrawn' and not root_tk.winfo_ismapped()
                text=panel.text.cget('text');assert text==sections(profiles[mode])[key]
                texts[mode][key]=text;cases.append(dict(case=mode+'-'+key+'-button',actual_Tk=True))
            panel.frame.destroy()
        # Page/holder fixture exercises the actual NEW ui_class navigation and Back wiring.
        class ViewBase:
            def __init__(self):self.controller=c;self.actions={};self.body=None
            def _page(self,title,*a,**k):
                if self.body is not None:self.body.destroy()
                self.body=tk.Frame(root_tk);self.body.pack();return self.body
            def button(self,body,label,command,key=None):
                holder=tk.Frame(body);holder.button=tk.Button(holder,text=label,command=command);holder.button.pack()
                if key:self.actions[key]=holder.button
                return holder
            def show_d1_saved(self):self._page('Diarizer saved test')
        nav=ui_class(ViewBase)();nav.show_d1_saved();nav.actions['d1_methods'].invoke();root_tk.update()
        assert nav.d1_method_panel.profile==catalog.request('delayed') and not errors
        cases.append(dict(case='new-ui-adapter-navigation',actual_Tk=True,base_page_fixture=True))
    finally:
        root_tk.destroy();destroyed=True
    assert c.calls==1 and len(cases)==30
    writer.json('CASES.json',cases);writer.json('PROFILES.json',profiles);writer.json('TEXT.json',texts)
    closer.json('CONTROL_CLOSURE.json',dict(Tk_destroyed=destroyed,command_threads_created=0,model_workers_created=0,source_samples=0,fixture_start_delegations=c.calls))
    return dict(status='PASS_D1_METHOD_CONTRACT_AND_WITHDRAWN_CONTROLS_ONLY',cases=len(cases),expected_rejections=sum(x.get('rejected',False) for x in cases),actual_Tk_views=9,actual_new_navigation=True,
        installed_Base_fixture=True,production_start_executed=False,models=False,ASR=False,capture=False,source_samples=0,
        visible_rendering=False,physical_touch=False,new_benchmark=False,old_model_passages_rerun=False,all_audio_policy_retained=True)
