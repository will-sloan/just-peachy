"""Build a fresh journal-only derivative and run model-free writer checks."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, fingerprint, freeze, load, verify
from metric_process import identity, pin
from paced_child_admission import assert_plain_path
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_native_journal_retention as regression

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
MAX_SOURCE_BYTES=32*1024**2


def replace_once(text, old, new):
    require(text.count(old)==1,'Qualified source patch context differs')
    return text.replace(old,new,1)


def build(parent, derivative, checkpoint):
    verify(parent);receipt=load(parent['path']);root=Path(receipt['prototype'])
    require(not derivative.exists() and derivative.parent.resolve()==(LOCAL/'releases').resolve(),
            'Fresh direct-child campaign release required')
    require(len(receipt['files'])<=4096 and sum(b['bytes'] for b in receipt['files'].values())<=MAX_SOURCE_BYTES,
            'Parent source exceeds copy allowance')
    source_bindings=[]
    for rel,meta in receipt['files'].items():
        path=assert_plain_path(root/rel,root);b=dict(path=str(path),**meta);verify(b);source_bindings.append(b)
    auxiliary=[]
    for rel,meta in receipt.get('auxiliary_files',{}).items():
        path=assert_plain_path(root.parent/rel,root.parent);b=dict(path=str(path),**meta);verify(b);auxiliary.append((rel,b))
    require(sum(b['bytes'] for b in source_bindings)+sum(b['bytes'] for _,b in auxiliary)<MAX_SOURCE_BYTES,
            'Parent source and auxiliary copy exceeds allowance')
    destination=derivative/'prototype';destination.mkdir(parents=True)
    for index,(rel,meta) in enumerate(receipt['files'].items()):
        checkpoint()
        target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write((root/rel).read_bytes())
        require(bind(target)['sha256']==meta['sha256'],'Source copy changed')
    for rel,b in auxiliary:
        target=derivative/rel;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(Path(b['path']).read_bytes())
        require(bind(target)['sha256']==b['sha256'],'Auxiliary copy changed')
    path=destination/'app/buffers.py';text=path.read_bytes().decode('utf-8')
    text=replace_once(text,'def __init__(self, path, capacity=4096, delay_once=0):',
        'def __init__(self, path, capacity=4096, delay_once=0, sink_factory=None):')
    text=replace_once(text,'self.sink = RotatingText(path)','self.sink = (sink_factory or RotatingText)(path)')
    path.write_bytes(text.encode('utf-8'))
    path=destination/'app/pipeline.py';text=path.read_bytes().decode('utf-8');newline='\r\n' if '\r\n' in text else '\n'
    text=replace_once(text,'from .buffers import MemoryJournal, AsyncText',
        'from .buffers import MemoryJournal, AsyncText'+newline+'from .native_complete_text import CompleteText')
    text=replace_once(text,"writer=AsyncText(path,delay_once=self.writer_delay if Path(path).name=='events.jsonl' else 0)",
        "writer=AsyncText(path,delay_once=self.writer_delay if Path(path).name=='events.jsonl' else 0,"+
        "sink_factory=CompleteText if Path(path).name=='events.jsonl' else None)")
    path.write_bytes(text.encode('utf-8'))
    (destination/'app/native_complete_text.py').write_bytes((HERE/'native_complete_text.py').read_bytes())
    (destination/'README_N4_COMPLETE_JOURNAL.md').write_bytes((HERE/'README_NATIVE_JOURNAL_RETENTION.md').read_bytes())
    changed=[rel for rel,meta in receipt['files'].items() if bind(destination/rel)['sha256']!=meta['sha256']]
    require(set(changed)=={'app/buffers.py','app/pipeline.py'},'Unexpected derivative change')
    for rel,digest in receipt['common_ui_files'].items():
        require(bind(destination/rel)['sha256']==digest,'Common frontend changed')
    files={str(path.relative_to(destination)).replace('\\','/'):
        {k:v for k,v in bind(path).items() if k!='path'} for path in sorted(destination.rglob('*')) if path.is_file()}
    require(sum(b['bytes'] for b in files.values())<MAX_SOURCE_BYTES,'Derivative exceeds source allowance')
    for b in source_bindings+[b for _,b in auxiliary]:verify(b)
    freeze(derivative/'SOURCE_RECEIPT.json',dict(schema='n4-complete-journal-derivative-v1',
        status='IMPLEMENTED_NOT_APPLICATION_ADMITTED',prototype=str(destination.resolve()),parent=parent,
        changed_files=changed,added_files=['app/native_complete_text.py','README_N4_COMPLETE_JOURNAL.md'],
        files=files,files_sha256=fingerprint(files),auxiliary_files=receipt.get('auxiliary_files',{}),
        common_ui_source_sha256=receipt['common_ui_source_sha256'],common_ui_files=receipt['common_ui_files'],
        implemented_compositions=receipt['implemented_compositions'],active_component_source_modified=False,
        policy=dict(events='CompleteText',max_events_bytes=256*1024**2,max_record_bytes=1024**2,
                    queue_capacity=4096,overflow='explicit writer failure; preserve prefix',other_journals='unchanged rotating'),
        actual_N4_inference_cells=0,N4_accepted=False,
        remaining_gates=['Bind derivative to versioned application preparation/runner/planner/review contracts',
                         'Reconfirm common actual GUI/source/worker closure for each candidate',
                         'Complete native event, pane content, naming/timing and resource review']))
    return bind(derivative/'SOURCE_RECEIPT.json')


def run(output,derivative):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private helper output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        checkpoint=lambda:guard(output,LOCAL,started,720)
        checkpoint();inventory=shared_allowance(LOCAL);active=active_d1()
        q=load(HERE/'APPLICATION_TRANSPORT_REVIEW_CHECK_V1.json')
        names=('native_complete_text.py','test_native_journal_retention.py','probe_native_journal_retention.py',
               'README_NATIVE_JOURNAL_RETENTION.md','probe_application_transport_review.py')
        code=[bind(HERE/name) for name in names]+[bind(HERE/'APPLICATION_TRANSPORT_REVIEW_CHECK_V1.json'),*q['code']]
        code=list({b['path']:b for b in code}.values())
        for b in code:verify(b)
        parent=load(HERE/'APPLICATION_CLOSURE_CHECK_V2.json')['source_receipt'];verify(parent)
        require(parent==load(active['result']['admission']['path'])['component_contract']['source_receipt'],
                'Expected component source parent differs')
        (output/'source').mkdir(parents=True)
        for b in code[:4]:(output/'source'/Path(b['path']).name).write_bytes(Path(b['path']).read_bytes())
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=[bind(path) for path in sorted((output/'source').iterdir())],
            parent_source=parent,derivative=str(derivative),inventory=inventory,D1_snapshot=active,
            new_source_or_model_execution=False))
        try:
            source=build(parent,derivative,checkpoint);regression.SOURCE=Path(load(source['path'])['prototype'])
            regression.OUTPUT=output/'tests';regression.OUTPUT.mkdir();stream=io.StringIO()
            tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.NativeRetentionTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==8 and not tests.skipped,'Native retention checks failed')
            for b in code:verify(b)
            verify(source);receipt=load(source['path'])
            for rel,meta in receipt['files'].items():verify(dict(path=str(regression.SOURCE/rel),**meta))
            checkpoint();after=active_d1();after_inventory=shared_allowance(LOCAL)
            require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 ownership changed')
            freeze(output/'RESULT.json',dict(status='PASS_NATIVE_JOURNAL_RETENTION_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                source_receipt=source,inventory_after=after_inventory,D1_after=after,
                test_scope='Actual copied AsyncText and isolated actual factory method; synthetic strings only, no source/model/Tk',
                new_application_or_model_started=False,application_runner_rebound=False,
                actual_panel_reviewed=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: eight native retention checks; fresh derivative only; no application or inference',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_NATIVE_RETENTION_PROBE_PRESERVED',error_type=type(exc).__name__,
                admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--derivative',type=Path,required=True)
    args=parser.parse_args();run(args.output,args.derivative)
