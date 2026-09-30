"""Bind implemented methods to an installed saved app; README_D1_MODE_ENTRY_V1.md."""
from copy import deepcopy
from pathlib import Path
import d1_saved_mode_entry_v1 as saved
import d1_method_controls_v1 as methods

class BoundStartWriter:
    """Attach the exact accepted profile at the real pre-owner START_REQUEST write."""
    def __init__(self, writer, catalog):
        self.writer=writer;self.catalog=catalog;self.controller=None
    def __getattr__(self, name):return getattr(self.writer, name)
    def json(self, name, value):
        if name == 'START_REQUEST.json':
            c=self.controller
            if c is None:raise ValueError('Unbound method controller')
            with c.d1_lock:
                selected=deepcopy(c.d1_selected)
                if methods.canonical(value['selected']) != methods.canonical(selected['selection']):
                    raise ValueError('Start writer selection mismatch')
                profile=self.catalog.validate(selected['selection']['id'],c.d1_method_profile)
                if value['capture'] is not False or value['scope']!='saved-input-only':
                    raise ValueError('Method admission is saved-only')
                value=deepcopy(value);value['implemented_methods']=profile
                value['method_binding_boundary']='before_source_model_thread_ownership'
        return self.writer.json(name,value)

def controller_class(Base,root,spec,writer,closer,failure,catalog,*,endpoint):
    proxy=BoundStartWriter(writer,catalog)
    Saved=saved.controller_class(Base,root,spec,proxy,closer,failure,endpoint=endpoint)
    Checked=methods.controller_class(Saved,catalog)
    class MethodApplication(Checked):
        def __init__(self,*args,**kwargs):
            if proxy.controller is not None:raise RuntimeError('One controller per admitted factory')
            super().__init__(*args,**kwargs);proxy.controller=self
        def _do_d1_select(self,mode):
            with self.d1_lock:
                super()._do_d1_select(mode)
                self.d1_error=None
        def _do_d1_start(self):
            with self.d1_lock:
                try:return super()._do_d1_start()
                except ValueError as exc:
                    self.d1_error='Method contract rejected: '+str(exc)
                    self.d1_phase='METHOD_ERROR'
                    raise
    return MethodApplication

def ui_class(Base):
    return methods.ui_class(saved.ui_class(Base))
