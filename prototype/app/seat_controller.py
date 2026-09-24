"""Controller-owned seat transactions and unanchored templates. See README_SEATS.md."""
from copy import deepcopy
from .paths import atomic_json, read_json
from .mode_policy import SEAT_MODES
from .seats import SeatSession, validate_layout
from .motion import MotionSafety


class SeatWorkflow:
    def _seats_initialize(self):
        self.seats=SeatSession(); self.seat_template={}; self.seat_template_error=None
        self.motion_safety=MotionSafety()
        path=self.data_root/'seat_template.json'
        if path.exists():
            try:
                saved=read_json(path)
                rows=validate_layout(saved['rows'])
                if saved.get('strength','soft') not in ('soft','strong'):raise ValueError('Invalid saved seat strength')
                self.seat_template=dict(rows=rows,strength=saved.get('strength','soft'),valid=False)
            except (KeyError,ValueError,TypeError) as exc:self.seat_template_error=str(exc)

    def seats_apply(self,rows,mode,strength='soft',acknowledged=False):
        self._enqueue('seats_apply',deepcopy(rows),mode,strength,acknowledged)

    def _do_seats_apply(self,rows,mode,strength,acknowledged):
        self._ensure_no_enrollment()
        if mode not in SEAT_MODES:raise ValueError('Choose one of the two assigned-seat modes')
        if mode=='assigned_direction' and strength!='soft':raise ValueError('Soft/strong prior applies to hybrid; use the fixed direction-only setting')
        rows=validate_layout(rows,{p['id'] for p in self.store.list()})
        if not rows:raise ValueError('Assign a person before applying a seating mode')
        if type(acknowledged) is not bool:raise ValueError('Ambiguity acknowledgement must be explicit')
        proposal=SeatSession(rows,strength=strength,acknowledged=acknowledged)
        ids=[r['person_id'] for r in rows]
        if mode=='assigned_hybrid':self.store.gallery(self.route(),ids)
        old=self.seats; self.seats=proposal
        if getattr(self,'imu',None) is not None:self.imu.reset()
        try:
            self._do_switch(mode,'balanced' if self.recipe in ('fast','classic') else self.recipe,self.tap,ids,False)
        except BaseException:
            self.seats=old
            raise
        self._record_seat_state('apply_at_current_location')
        self.status='Seat layout anchored here for this session. '+('Direction names are seating assumptions.' if mode=='assigned_direction' else 'Voice + seat prior; Unknown retained.')

    def seats_save_template(self,rows,strength='soft'):
        self._enqueue('seats_save_template',deepcopy(rows),strength)

    def _do_seats_save_template(self,rows,strength):
        rows=validate_layout(rows,{p['id'] for p in self.store.list()})
        if strength not in ('soft','strong'):raise ValueError('Invalid seat strength')
        self.seat_template=dict(rows=rows,strength=strength,valid=False)
        atomic_json(self.data_root/'seat_template.json',dict(schema='just-peachy.seat-template.v1',**self.seat_template,
                    scope='Reusable draft only; never a valid physical anchor'))
        self.status='Reusable draft saved. Apply is still required at each physical location.'

    def _invalidate_seats(self,reason):
        if getattr(self,'reference_bank',None) and reason!='user_stopped_session; re-anchor before next Start':self.reference_bank.freeze('seat_or_motion_change: '+reason)
        if getattr(self,'seats',None) is None:return
        self.seats.motion.moved(reason)
        spatial=getattr(self.engine,'live_spatial',None)
        if spatial is not None and hasattr(spatial,'invalidate_positions'):spatial.invalidate_positions()
        self._record_seat_state(reason)

    def motion_event(self,event):
        """Optional mapped sensor/mock event; no hardware is opened by this API."""
        self._enqueue('motion_event',event)

    def _do_motion_event(self,event):
        decision=self.motion_safety.accept(event)
        if decision['accepted']:
            self.metrics['motion']=self.motion_safety.snapshot()
        if decision['invalidate']:
            self._invalidate_seats(decision['reason'])
            self.status=('Movement cleared old locations. Apply assigned seats again; voice profiles retained.'
                         if self.mode in SEAT_MODES else
                         'Movement cleared old locations; fresh voice and direction evidence will rebuild them.')

    def _record_seat_state(self,reason):
        detail=dict(action=reason,**self.seats.snapshot())
        self.metrics['last_seat_change']=detail
        archive=getattr(self,'archive',None)
        if archive is not None:
            from edge_speech_pipeline.contracts import PipelineEvent
            archive.event(PipelineEvent('prototype_seat_configuration',archive.source_samples/16000,detail))

    def seating_snapshot(self):
        seats=getattr(self,'seats',None)
        return dict(**(seats.snapshot() if seats is not None else {}),
                    motion=self.motion_safety.snapshot() if hasattr(self,'motion_safety') else dict(state='HARDWARE_PENDING',enabled=False),
                    template=deepcopy(getattr(self,'seat_template',{})),template_error=getattr(self,'seat_template_error',None))
