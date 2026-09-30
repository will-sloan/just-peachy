"""Settle two previously premature Wayland screenshots; README_FIELD_VISIBLE_V4.md."""
import hashlib,json,shutil,subprocess,sys,time
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def run(root,a):
    installed=Path(a['installed_release']);data=root/'data';data.mkdir()
    for source,target in [('N2_RUNTIME_BACKUP.json','n2_runtime.json'),('LIVE_CONFIG_BACKUP.json','live_config.json')]:shutil.copyfile(root/source,data/target)
    launch=dict(release_manifest_sha256=sha(installed/'RELEASE_MANIFEST.json'),autonomous_quiet_authorized=True,expires_unix=time.time()+90,data_root=str(data.resolve()))
    (root/'GUI_LAUNCH.json').write_text(json.dumps(launch,indent=2))
    sys.path[:0]=[str(installed),str(installed/'vendor'),str(installed/'native')]
    from native import field_entry_v2 as entry
    from app import ui as module
    original=module.PrototypeUI;holder={};observations=[];errors=[]
    class ScheduledUI(original):
        def __init__(self,*values,**options):
            super().__init__(*values,**options);holder['ui']=self
            self.root.after(600,advance)
    def u():return holder['ui']
    def snap(name):
        ui=u();ui.controller.commands.join();ui.snapshot=ui.controller.snapshot()
        assert ui.controller.engine is None and ui.controller.models.asr_loads==ui.controller.models.speaker_loads==0
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        assert ui.root.winfo_geometry()=='480x800+0+0' and ui.root.winfo_viewable()
        if name.startswith('consent'):
            assert ui.page=='consent' and ui.actions['confirm'].winfo_ismapped() and ui.actions['cancel'].winfo_ismapped()
            assert ui.actions['confirm'].cget('text')=='I consent · Start listening' and ui.actions['cancel'].cget('text')=='Cancel'
        else:
            assert ui.page=='recipes' and str(ui.actions['recipe_balanced'].cget('state'))=='normal'
        path=root/(name+'.png');subprocess.run(['grim',str(path)],check=True,timeout=10)
        observations.append(dict(name=name,sha256=sha(path),bytes=path.stat().st_size,geometry=ui.root.winfo_geometry(),mapped=True,page=ui.page))
    steps=[lambda:u().actions['start_stop'].invoke(),lambda:snap('consent_settled_a'),lambda:snap('consent_settled_b'),
           lambda:u().actions['cancel'].invoke(),lambda:u().show_recipes(),lambda:snap('recipes_settled_a'),lambda:snap('recipes_settled_b')]
    def advance():
        try:
            if not steps:u().close();return
            steps.pop(0)();u().root.after(500,advance)
        except Exception as e:
            import traceback
            (root/'CALLBACK_FAILURE.txt').write_text(traceback.format_exc());errors.append(str(e));u().close()
    module.PrototypeUI=ScheduledUI;before=sys.argv[:]
    try:
        sys.argv=[str(installed/'main.py'),'gui','--data-root',str(data),'--launch-admission',str(root/'GUI_LAUNCH.json')]
        code=entry.main()
    finally:module.PrototypeUI=original;sys.argv=before
    assert code==0 and not errors and not steps and u().controller.closed and not u().controller.worker.is_alive()
    assert {p.relative_to(installed).as_posix():sha(p) for p in installed.rglob('*') if p.is_file()}==a['installed_files']
    return dict(status='INSTALLED_SETTLED_CONSENT_RECIPE_RENDER_ONLY',observations=observations,
                stable_pairs=[observations[0]['sha256']==observations[1]['sha256'],observations[2]['sha256']==observations[3]['sha256']],
                model_loads=0,capture=False,physical_touch=False,controller_closed=True,installed_unchanged=True)
