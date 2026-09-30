"""Changed source Stop/write paths only; README_FIELD_SOURCE_RECEIPTS_V1.md."""
import hashlib,json,sys,threading
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from field_source_receipt_routes_v1 import ReceiptRoutes,ReceiptFailure,sha
from field_source_factory_overlay_v1 import route_classes,save
from field_live_stop_overlay_v1 import source_class
from live_source_bridge_budget_v1 import LiveSourceBridge
from isolated_source_transport_v3 import SourceFault

def run(root,a):
    descriptor=root/'FIELD_SOURCE_RECEIPT_DESCRIPTOR_V1.json';plan=root/'FIELD_WHOLE_RUN_ALLOCATION_V2.json'
    original=json.loads(descriptor.read_text());cases=[];fixtures=root/'fixtures';fixtures.mkdir()
    def record(name,**value):
        row=dict(case=name,**value);(root/(name+'-CASE.json')).write_text(json.dumps(row,indent=2,allow_nan=False),encoding='utf-8');cases.append(row)
    def changed(name,mutator):
        doc=deepcopy(original);mutator(doc);path=root/(name+'-descriptor.json');path.write_text(json.dumps(doc),encoding='utf-8');return path,sha(path)
    negatives=[('descriptor-map',lambda d:d['mapped_names'].pop()),('descriptor-plan',lambda d:d.update(plan_sha256='0'*64)),('descriptor-source',lambda d:d['files'].update({'field_live_stop_overlay_v1.py':'0'*64})),('descriptor-group',lambda d:d['groups']['source'].update(maximum_bytes=2*1024**2)),('descriptor-capture',lambda d:d.update(scope='capture'))]
    for name,fn in negatives:
        path,h=changed(name,fn);dest=fixtures/name
        try:ReceiptRoutes(dest,path,h,plan)
        except ValueError as exc:record(name,rejected=True,error=str(exc),unpublished=not dest.exists())
        else:raise AssertionError(name)
        assert not dest.exists()
    try:ReceiptRoutes(fixtures/'descriptor-hash',descriptor,'0'*64,plan)
    except ValueError as exc:record('descriptor-hash',rejected=True,error=str(exc),unpublished=not (fixtures/'descriptor-hash').exists())
    else:raise AssertionError('hash')
    installed=Path(a['base_release']);sys.path[:0]=[str(installed),str(installed/'vendor')]
    import app.live_audio as live
    assert Path(live.__file__).resolve()==installed/'app/live_audio.py'
    BudgetedSource=source_class(live)
    def exercise(name,max_files=16,write_limit=65536,tail=0,mismatch=False):
        path,h=changed(name,lambda d:d['groups']['source'].update(maximum_files=max_files,maximum_file_bytes=write_limit,maximum_write_bytes=write_limit))
        routes=ReceiptRoutes(fixtures/name,path,h,plan);calls=[];events=[]
        class Control:
            receipts=[]
            def snapshot(self):return dict(route='fixture',value=2 if mismatch and 'restore' in calls else 1)
        class Route:
            def __init__(self,c):self.control=c
            def restore(self):calls.append('restore');return dict(route='RESTORED')
        C,Q=route_classes(SimpleNamespace(HostControl=Control,LiveRoute=Route),routes)
        control=C();control.snapshot()
        class Stream:
            closed=False;active=True
            def stop(self):calls.append('stream.stop');self.active=False
            def close(self):calls.append('stream.close');self.closed=True
        class Lease:
            handle=True
            def close(self):calls.append('lease.close');self.handle=None
        obj=BudgetedSource.__new__(BudgetedSource)
        obj.receipt_routes=routes;obj._receipt=None;obj._cancel_requested=threading.Event();obj._stop_lock=threading.Lock();obj._done=threading.Event();obj.beam_diagnostics=None
        obj.config=SimpleNamespace(control_timeout_seconds=2,evidence_dir=str(routes.root/'source'))
        obj.route=Q(control);obj.stream=Stream();obj.lease=Lease();obj.control=control;obj.metadata={};obj._fault=None
        obj.status=lambda:dict(finished=True,pending_raw_blocks=tail,raw_frames=0,converted_samples=0)
        obj.status_callback=lambda kind,value:events.append(dict(kind=kind,errors=list(value['errors'])))
        previous=live.endpoint_snapshot
        def endpoints():calls.append('endpoint_snapshot');return {}
        live.endpoint_snapshot=endpoints
        bridge=LiveSourceBridge(obj,live.LiveGap,routes.root/'source',routes)
        try:
            try:bridge.close();code=None
            except SourceFault as exc:code=exc.code
            first=list(calls);cached=obj.stop();assert list(calls)==first and cached is obj._receipt
            try:obj.start(consent=True)
            except live.LiveAudioError as exc:assert str(exc)=='CAPTURE_UNAVAILABLE_IN_RECEIPT_QUALIFICATION'
            else:raise AssertionError('capture')
        finally:live.endpoint_snapshot=previous
        assert calls==['restore','stream.stop','stream.close','lease.close','endpoint_snapshot']
        assert bridge.closed and obj.stream.closed and obj.lease.handle is None and obj._done.is_set()
        closure=json.loads((routes.root/'closure_reserve/SOURCE_CLOSURE.json').read_text())
        assert closure['failure_code']==code and closure['logical_success']==(code is None)
        for row in routes.failures:
            assert row['raw_retained'] and row['receipt_retained']
            raw=(routes.root/'failure'/row['raw_path']).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
        record(name,rejected=code is not None,error=code,calls=calls,events=events,closure=closure,diagnostics=routes.failures,layout=routes.layout(),snapshot={n:w.snapshot() for n,w in routes.groups.items()},start_rejected=True,cached_stop_no_repeat=True)
        return code
    assert exercise('normal-stop') is None
    assert exercise('post-route-quota',max_files=1)=='LIVE_SOURCE_CLOSE_INCOMPLETE'
    assert exercise('route-stop-quota',write_limit=256)=='LIVE_SOURCE_CLOSE_INCOMPLETE'
    assert exercise('bridge-quota',max_files=3)=='SOURCE_RECEIPT_NOT_PUBLISHED'
    assert exercise('accepted-tail',tail=1)=='UNCONSUMED_ACCEPTED_RAW_TAIL'
    assert exercise('route-mismatch',mismatch=True)=='SOURCE_RESTORATION_FAILED'
    routes=ReceiptRoutes(fixtures/'factory-path',descriptor,sha(descriptor),plan)
    try:save(routes,routes.root/'BAD.json',{})
    except ValueError as exc:record('factory-path',rejected=True,error=str(exc),unpublished=not list((routes.root/'source').iterdir()))
    else:raise AssertionError('path')
    # First oversized publication rejects before a destination exists. Exact
    # oversized synthetic diagnostic is retained by the test, not by archive.
    rawvalue={'fixture':'x'*262144};(root/'OVERSIZED_SYNTHETIC_INPUT.json').write_text(json.dumps(rawvalue,separators=(',',':')),encoding='utf-8')
    try:save(routes,routes.root/'source/SOURCE_START_FAILURE.json',rawvalue)
    except ReceiptFailure as exc:
        assert not exc.receipt['raw_retained'] and not exc.receipt['receipt_retained']
        assert not (routes.root/'source/SOURCE_START_FAILURE.json').exists()
        routes.closure(dict(logical_success=False,receipt_failure=exc.receipt))
        record('oversized-diagnostic',rejected=True,error=str(exc),receipt=exc.receipt,unpublished=True)
    else:raise AssertionError('oversize')
    (root/'SOURCE_RECEIPT_CASES.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
    return dict(status='PASS_SOURCE_STOP_RECEIPT_ADAPTER_FIXTURES_ONLY',cases=len(cases),rejections=sum(c['rejected'] for c in cases),actual_installed_stop_derivative=True,fake_hardware=True,source_started=False,models=False,audio=False,capture=False,GUI=False,controller=False,whole_run_integrated=False,policy_changed=False)
