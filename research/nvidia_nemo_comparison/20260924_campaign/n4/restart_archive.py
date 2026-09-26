"""Archive drain while Controller stays open; README_RESTART_APPLICATION.md.

Explicit derivative of N3 archive ownership checks; no old receipt is relabeled
as a successful whole-Controller shutdown. All archive drain checks are retained.
"""
import importlib
from pathlib import Path
from common import load, verify
from application_closure import ARCHIVE_MODULE, require
from restart_session_closure import validate_engine


ARCHIVE_EPOCH_FIELDS=('epoch_id','state','closed','source_samples','recorded_samples',
    'audio_enabled','audio_recording','archive_error','loss','queue_items','queue_bytes',
    'accepted_items','completed_items','pipeline_terminal_state')


def capture_archive(controller, engine):
    value=importlib.import_module(ARCHIVE_MODULE).archive_integrity_receipt(controller,engine)
    value['schema']='n4-released-session-archive-v1'
    value['session_released']=(controller.engine is None and controller.consumer is None
        and controller.commands.unfinished_tasks == 0 and controller.source_kind is None
        and controller.state == 'STOPPED' and controller.error is None)
    return value


def validate_archive_integrity(receipt,expected_samples):
    """Fail on a silent archive warning, dropped metadata or incomplete teardown."""
    def require(ok,reason):
        if not ok:raise ValueError('Archive integrity failed: '+reason)
    require(receipt.get('schema')=='n4-released-session-archive-v1','missing receipt')
    require(receipt.get('controller_closed') is False and receipt.get('controller_worker_alive') is True,'Controller must remain available')
    require(receipt.get('session_released') is True,'Controller session owners are not released')
    require(receipt.get('worker_alive') is False and receipt.get('active_archive_owners')==0,'archive owner still active')
    sessions=receipt.get('sessions',{});owner=receipt.get('owner');last=sessions.get('last_archive')
    require(sessions.get('archive') is None,'sessions archive still active')
    require(isinstance(owner,dict) and isinstance(last,dict),'missing owner/last_archive')
    require(last==receipt.get('metrics_last_archive'),'last_archive differs from Controller metrics')
    require(owner==last,'joined archive differs from last_archive')
    for name,row in (('owner',owner),('last_archive',last),('persisted',receipt.get('persisted',{}))):
        require(row.get('archive_error') is None and row.get('loss') is None,name+' archive_error/loss')
        require(row.get('closed') is True and row.get('audio_recording') is False,name+' not closed')
        require(row.get('queue_items')==0 and row.get('queue_bytes')==0,name+' queue not drained')
        require(type(row.get('source_samples')) is int and row['source_samples']==expected_samples,name+' source samples differ')
        require(row.get('audio_enabled') in (True,False),name+' missing audio policy')
        require(row.get('recorded_samples')==(expected_samples if row['audio_enabled'] else 0),name+' recorded samples differ')
    require(owner.get('worker_alive') is False,'archive thread still alive')
    accepted=receipt.get('accepted_items');completed=receipt.get('completed_items')
    require(type(accepted) is int and accepted>0 and type(completed) is int and accepted==completed,'accepted/completed items differ or absent')
    persisted=receipt['persisted']
    require(persisted.get('state')=='CLOSED' and persisted.get('pipeline_terminal_state')=='COMPLETED','persisted archive not successfully closed')
    require(persisted.get('accepted_items')==accepted and persisted.get('completed_items')==completed,'persisted counters differ')
    require(persisted.get('epoch_id')==owner.get('epoch_id'),'epoch identity differs')
    current=[row for row in sessions.get('library',[]) if row.get('id')==sessions.get('current_id')]
    require(len(current)==1 and not current[0].get('issues'),'current session reports archive issues or is missing')
    require(isinstance(receipt.get('epoch'),dict),'missing persisted epoch binding')
    verify(receipt['epoch'])
    document=load(receipt['epoch']['path'])
    require({name:document.get(name) for name in ARCHIVE_EPOCH_FIELDS}==persisted,'persisted evidence differs')


def validate_complete(observed, archive):
    engine=validate_engine(observed)
    validate_archive_integrity(archive,observed['delivered_frames'])
    require(archive['persisted']['audio_enabled'] is False and archive['persisted']['recorded_samples'] == 0,
            'Restart check cannot make a new audio archive')
    epoch=load(archive['epoch']['path'])
    require(Path(epoch['native_session_path']).resolve() == Path(observed['session']).resolve(),
            'Archive belongs to a different engine session')
    return dict(status='PASS_RELEASED_SESSION_ENGINE_AND_OPEN_CONTROLLER_ARCHIVE',engine=engine,
        archive_epoch=archive['epoch'],controller_still_open=True,same_controller_restart_qualified=False,
        source_to_widget_latency_qualified=False,model_accuracy_qualified=False,
        controlled_resources_qualified=False,integrated_N4_cells=0)
