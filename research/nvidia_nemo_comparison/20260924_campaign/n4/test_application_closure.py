"""Closure rejection fixtures and saved terminal receipts. README_APPLICATION_CLOSURE.md."""
from copy import deepcopy
from pathlib import Path
import unittest

from application_closure import capture_engine, validate_engine, validate_complete, persisted, validate_persisted
from common import bind, freeze, load, verify

CONTEXT = {}


def observed_fixture():
    """Synthetic in-memory owner facts joined to unchanged historical receipts.

    This fixture never claims that a new application/source/model was run.
    """
    case = CONTEXT['cases'][0]; job = case['audio']; count = job['frames']
    terminal = persisted(case['session'], count); consumer = load(terminal['consumer']['path']); q = consumer['queues']
    thread = dict(present=True, started=True, alive=False, name='fixture', ident=1, native_id=1)
    journal = dict(present=True, actual_MemoryJournal=True, sample_rate=16000, committed_samples=count,
        finished=True, fatal_error=None, overrun_reads=0, capacity=16000*120)
    workers = {k:deepcopy(q[k]) for k in ('journal','punctuation','policy')}
    workers['trace'] = dict(closed=True, thread_alive=False, error=None, depth=0, accepted=2, completed=2, overflow=0)
    return dict(schema='n4-application-engine-closure-v1', job=deepcopy(job), engine_class='N3IdentityEngine',
        session=case['session'], state='COMPLETED', finalization_error=None, enhancement_route='bypass',
        enhancement_router_present=False, source=dict(present=True, actual_FileSource=True, path=job['audio_path'],
            start_sample=0, sent=count, thread=deepcopy(thread), journal=deepcopy(journal)),
        journals={k:deepcopy(journal) for k in ('_input_journal','_journal','_identity_journal')},
        bypass_journals_are_source_journal=True,
        threads={**{k:deepcopy(thread) for k in ('source','consumer','finalization','journal','punctuation','policy','trace')},
            'lane_0':dict(thread,name='edge-asr'), 'lane_1':dict(thread,name='edge-speaker')},
        workers=workers, text_writers=[dict(workers['trace'],sink_closed=True) for _ in range(3)],
        asr_cursor_sec=count/16000, n3_input_samples=count,
        controller_clock=dict(source_event_clock_available=True),
        publication_census=dict(status='PASS_ACTUAL_EVENT_INBOX_CENSUS',
            **{k:terminal['result'][k] for k in ('published','consumed','coalesced_obsolete_ui_partials')}),
        publication_census_error=None, persisted=terminal, persisted_error=None)


class ClosureTests(unittest.TestCase):
    def test_nine_historical_terminal_and_archive_receipts(self):
        import importlib
        helper = importlib.import_module('research.nvidia_nemo_comparison.20260924_campaign.n3.gui_a1')
        checks = []
        for case in CONTEXT['cases']:
            for binding in (case['finalization'],case['consumer'],case['archive']): verify(binding)
            terminal = persisted(case['session'], case['audio']['frames'])
            archive = load(case['archive']['path']); helper.validate_archive_integrity(archive, case['audio']['frames'])
            epoch = load(archive['epoch']['path'])
            self.assertEqual(Path(epoch['native_session_path']).resolve(), Path(case['session']).resolve())
            self.assertFalse(archive['persisted']['audio_enabled']); self.assertEqual(archive['persisted']['recorded_samples'],0)
            checks.append(dict(cell_id=case['cell_id'], terminal=terminal, archive=case['archive'],
                status='PASS_HISTORICAL_PERSISTED_SUBSET_ONLY', new_source_execution=False,
                current_source_worker_objects_observed=False, integrated_N4_cells=0))
        self.assertEqual(len(checks), 9); CONTEXT['historical_checks'] = checks

    def test_positive_join_is_only_a_synthetic_owner_fixture(self):
        observed = observed_fixture(); before = deepcopy(observed)
        result = validate_complete(observed, load(CONTEXT['cases'][0]['archive']['path']))
        self.assertEqual(result['status'],'PASS_SOURCE_WORKERS_CONSUMER_AND_ARCHIVE_CLOSURE')
        self.assertFalse(result['model_accuracy_qualified']); self.assertEqual(result['integrated_N4_cells'],0)
        self.assertEqual(observed, before)

    def test_source_and_journal_loss_is_not_success(self):
        mutations = [lambda r:r['source'].update(sent=r['source']['sent']-1),
            lambda r:r['source'].update(start_sample=1), lambda r:r['source'].update(actual_FileSource=False),
            lambda r:r.update(bypass_journals_are_source_journal=False),
            lambda r:r['journals']['_journal'].update(finished=False),
            lambda r:r['journals']['_identity_journal'].update(overrun_reads=1),
            lambda r:r['journals']['_input_journal'].update(fatal_error='fixture failure'),
            lambda r:r.update(n3_input_samples=1), lambda r:r.update(asr_cursor_sec=0.)]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                row = observed_fixture(); mutate(row)
                with self.assertRaises(ValueError): validate_engine(row)

    def test_late_trace_failure_live_owners_and_missing_census_rejected(self):
        mutations = [lambda r:r.update(state='FAILED',finalization_error='late trace failure'),
            lambda r:r['workers']['trace'].update(error='trace failed'),
            lambda r:r['threads']['source'].update(alive=True),
            lambda r:r['threads']['consumer'].update(started=False),
            lambda r:r['workers'].pop('policy'), lambda r:r['journals'].pop('_identity_journal'),
            lambda r:r['threads'].pop('lane_0'), lambda r:r['text_writers'].pop(),
            lambda r:r['text_writers'][0].update(sink_closed=False),
            lambda r:r['publication_census'].update(consumed=0), lambda r:r.update(persisted_error='receipt missing')]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                row = observed_fixture(); mutate(row)
                with self.assertRaises(ValueError): validate_engine(row)

    def test_persisted_early_or_incomplete_checkpoints_rejected(self):
        row = CONTEXT['cases'][0]; final = load(row['finalization']['path']); consumer = load(row['consumer']['path'])
        for key, value in [('state','RUNNING'),('source_samples',0),('identity_samples',0),
            ('live_lanes_at_finalization',['edge-asr']),('resident_bundle_lease_retained',True),
            ('event_and_transcript_handles_closed',False),('handle_close_results',{})]:
            changed = deepcopy(final); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_persisted(changed,consumer,row['audio']['frames'])
        changed = deepcopy(consumer); changed['queues']['event_consumer']['coalesced_obsolete_ui_partials'] += 1
        with self.assertRaises(ValueError): validate_persisted(final,changed,row['audio']['frames'])

    def test_actual_partial_startup_closes_workers_but_is_not_accepted(self):
        from app.controller import Controller
        from app.pipeline import PrototypeEngine, effective_profile
        from controller_projection import drain_commands
        root = CONTEXT['output']/'actual-partial-startup'; root.mkdir()
        c = Controller(root,root/'NO_MODEL_PAYLOAD',saved_audio_only=True); engine = None
        try:
            engine = PrototypeEngine(c.config,c.models,effective_profile('balanced','anonymous_conversation','O0'),None,'anonymous_conversation')
            c.engine = engine; c.source_kind='file'
            engine.begin()  # Real bounded writers/policy; deliberately no source or model launch.
        finally:
            c.close(); drain_commands(c); c.worker.join(10.)
        self.assertFalse(c.worker.is_alive()); self.assertTrue(c.closed)
        observed = capture_engine(engine,None,None,CONTEXT['cases'][0]['audio'])
        self.assertFalse(observed['source']['present']); self.assertEqual(observed['state'],'FAILED')
        self.assertTrue(all(not t['alive'] for t in observed['threads'].values() if t['present']))
        self.assertTrue(all(not w['thread_alive'] for w in observed['workers'].values() if w is not None))
        with self.assertRaises(ValueError): validate_engine(observed)
        self.assertFalse(any(getattr(c.models,k,0) for k in ('asr_loads','speaker_loads','streams')))
        freeze(root/'OBSERVED.json',dict(scope='Actual startup/cancellation without any source or models; expected rejection', observed=observed))
        CONTEXT['partial_startup'] = bind(root/'OBSERVED.json')

    def test_foreign_archive_epoch_is_rejected(self):
        archive = load(CONTEXT['cases'][0]['archive']['path']); original = load(archive['epoch']['path'])
        changed = deepcopy(original); changed['native_session_path'] = str(CONTEXT['output']/'foreign-session')
        path = CONTEXT['output']/'foreign-epoch-fixture.json'; freeze(path,changed)
        archive['epoch'] = bind(path)
        with self.assertRaisesRegex(ValueError,'different engine session'): validate_complete(observed_fixture(),archive)
