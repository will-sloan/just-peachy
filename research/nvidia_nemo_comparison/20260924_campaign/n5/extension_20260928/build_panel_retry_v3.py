"""Rebind collector output/import paths without altering acceptance checks. README_PANEL_RETRY_V3.md."""
from pathlib import Path
import ast
import importlib.util
import sys
HERE=Path(__file__).resolve().parent
N4=HERE.parent.parent/'n4'
sys.path[:0]=[str(N4),str(HERE.parents[4])]
from common import bind,freeze
from metric_process import pin
from paced_child_admission import assert_plain_path


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Derivative anchor mismatch')
    return text.replace(old,new,1)


def main():
    pin();base=HERE.parent.parents[4]/'local/n5/research-extension-20260928'
    paths=[HERE/n for n in ('panel_retry_v3.py','panel_cell_v1.py','panel_delivery_v1.py')]
    if any(p.exists() for p in paths):raise FileExistsError('Fresh harness files required')
    module='research.nvidia_nemo_comparison.20260924_campaign.n3.gui_a1'
    spec=importlib.util.find_spec(module)
    if spec is None or Path(spec.origin).resolve()!=HERE.parent.parent/'n3/gui_a1.py':raise ValueError('Archive module unresolved')
    assert_plain_path(base,base.parent)
    try:assert_plain_path(base.parent/'outside-extension',base)
    except ValueError:pass
    else:raise AssertionError('Escaped root accepted')
    old=HERE/'panel_retry_v2.py';runner=old.read_text(encoding='utf-8')
    runner=once(runner,'sys.path[:0] = [str(N4), str(N5)]','sys.path[:0] = [str(N4), str(N5), str(N5.parents[3])]')
    runner=once(runner,'from paced_application_cell_v2 import ApplicationCell','from panel_cell_v1 import ApplicationCell')
    runner=once(runner,'from application_delivery import review_files','from panel_delivery_v1 import review_files')
    runner=once(runner,"code = [bind(p) for p in sorted(N4.glob('*.py'))]","code = [bind(p) for p in sorted(N4.glob('*.py'))]\n    code += [bind(p) for p in sorted((N5.parent/'n3').glob('*.py'))]")
    runner=once(runner,"'panel_retry_v1.py','panel_retry_v2.py',","'panel_retry_v3.py','panel_cell_v1.py','panel_delivery_v1.py','build_panel_retry_v3.py','README_PANEL_RETRY_V3.md','panel_retry_v1.py','panel_retry_v2.py',")
    runner=once(runner,'README_PANEL_RETRY_V2.md.','README_PANEL_RETRY_V3.md.')
    cell=(N4/'paced_application_cell_v2.py').read_text(encoding='utf-8')
    cell=once(cell,'from application_delivery import SourceLaunchCapture, POLICY, review_files','from panel_delivery_v1 import SourceLaunchCapture, POLICY, review_files')
    cell=once(cell,'README_APPLICATION_DELIVERY.md.','README_PANEL_RETRY_V3.md.')
    delivery=(N4/'application_delivery.py').read_text(encoding='utf-8')
    delivery=once(delivery,"Path('G:/Just_Peachy_N1/20260924_campaign/local/n4')","Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928')")
    delivery=once(delivery,'README_APPLICATION_DELIVERY.md.','README_PANEL_RETRY_V3.md.')
    for p,text in zip(paths,[runner,cell,delivery]):
        ast.parse(text);p.write_text(text,encoding='utf-8',newline='\n')
    freeze(base/'HARNESS_PATHS_V3.json',dict(status='PASS_IMPORT_AND_PATH_BINDING_CHECKS',
        parents=[bind(p) for p in (old,N4/'paced_application_cell_v2.py',N4/'application_delivery.py')],
        children=[bind(p) for p in paths],archive_module=bind(spec.origin),outside_path_rejected=True,
        code=[bind(Path(__file__)),bind(HERE/'README_PANEL_RETRY_V3.md')],application_source_changed=False,inference_run=False))
    print(dict(status='PASS_IMPORT_AND_PATH_BINDING_CHECKS',files=len(paths)))


if __name__=='__main__':main()
