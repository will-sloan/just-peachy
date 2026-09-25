"""V1 regression suite plus cross-session contamination tests. README_APPLICATION_CLOSURE_V2.md."""
from copy import deepcopy
from pathlib import Path
import test_application_closure as prior
from common import load
import application_closure_v2 as joined

CONTEXT = prior.CONTEXT
old_fixture = prior.observed_fixture


def observed_fixture():
    row = old_fixture(); census = row['publication_census']; origin = 100.
    payload = dict(path=row['job']['audio_path'],session_id=Path(row['session']).name,mode='file',pacing='absolute',
        start_sample=0,gain=1.,source_epoch_monotonic_sec=origin)
    row['controller_clock'].update(publication_session=payload['session_id'],source_epoch_monotonic_sec=origin,
        source_started=dict(event_payload=payload,source_epoch_monotonic_sec=origin),
        errors=0,event_counts=dict(source_started=1),event_count=census['consumed'],
        last_publication_sequence=census['published'],missing_publication_sequences=census['coalesced_obsolete_ui_partials'])
    row['source_clock_owner_join'] = dict(same_engine=True,consumer_retained=True)
    return row


# Reuse the exact prior tests against the joined implementation. Only test-module
# globals change; no application, frozen source or prior evidence is modified.
prior.observed_fixture = observed_fixture
prior.capture_engine = joined.capture_engine
prior.validate_engine = joined.validate_engine
prior.validate_complete = joined.validate_complete


class ClosureTests(prior.ClosureTests):
    def test_wrong_clock_engine_file_session_origin_and_census_rejected(self):
        mutations = [lambda r:r['source_clock_owner_join'].update(same_engine=False),
            lambda r:r['source_clock_owner_join'].update(consumer_retained=False),
            lambda r:r['controller_clock'].update(publication_session='foreign'),
            lambda r:r['controller_clock']['source_started']['event_payload'].update(session_id='foreign'),
            lambda r:r['controller_clock']['source_started']['event_payload'].update(path=str(CONTEXT['output']/'foreign.wav')),
            lambda r:r['controller_clock'].update(source_epoch_monotonic_sec=101.),
            lambda r:r['controller_clock'].update(event_count=0),
            lambda r:r['controller_clock'].update(missing_publication_sequences=0),
            lambda r:r['controller_clock'].update(errors=1)]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                row = observed_fixture(); mutate(row)
                with self.assertRaises(ValueError): joined.validate_engine(row)

    def test_join_keeps_closure_and_inference_claims_separate(self):
        row = observed_fixture(); before = deepcopy(row)
        result = joined.validate_complete(row,load(CONTEXT['cases'][0]['archive']['path']))
        self.assertTrue(result['source_clock_identity_join_verified'])
        self.assertFalse(result['model_accuracy_qualified']); self.assertFalse(result['controlled_resources_qualified'])
        self.assertFalse(result['source_to_widget_latency_qualified']); self.assertEqual(row,before)
