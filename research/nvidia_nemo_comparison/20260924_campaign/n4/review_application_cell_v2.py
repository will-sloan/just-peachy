"""Join stopped V2 native/transport/GUI evidence. README_APPLICATION_CELL_REVIEW_V2.md."""
from pathlib import Path

from common import fingerprint, verify
from review_application_transport_v2 import record, review_cell as review_transport
from review_application_observations import review_observations
from review_scoring_bank import require


def join_reviews(folder, payload, transport, observations):
    """Join independently checked records; do not treat checks as acceptance."""
    folder = Path(folder).resolve(strict=True)
    require(transport['status'] == 'PASS_APPLICATION_TRANSPORT_AND_NATIVE_ENVELOPE_JOINS_ONLY'
        and observations['status'] == 'PASS_APPLICATION_OBSERVATION_JOINS_ONLY', 'Independent V2 checks required')
    require(transport['cell_id'] == payload['cell_id'], 'Transport cell differs')
    records = {}
    for binding in transport['evidence'] + observations['evidence']:
        require(binding['path'] not in records or records[binding['path']] == binding,
            'Shared cell evidence changed between independent reviews')
        records[binding['path']] = binding
    def checked(relative):
        binding, value = record(folder/relative, folder)
        require(records.get(binding['path']) == binding, 'Joined record was not checked by the independent readers')
        return binding, value
    result_binding, _ = checked('application/RESULT.json')
    require(result_binding == observations['cell_result'], 'Observed cell result differs')
    _, closure = checked('application/ENGINE_CLOSURE.json')
    _, clock = checked('application/SOURCE_CLOCK.json')
    _, envelope = checked('NATIVE_JOURNAL_ENVELOPE.json')
    native = transport['native_envelope_review']
    require(fingerprint(envelope['review']) == fingerprint(native), 'Native envelope review changed')
    terminal = {Path(b['path']).name: b for b in native['terminal']}
    require(len(terminal) == 2 and terminal == {
        'session_finalization_v3.json': closure['persisted']['finalization'],
        's6d_consumer_closure.json': closure['persisted']['consumer']}, 'Native/engine terminal receipts differ')
    require(closure['job'] == payload['job'] and clock['publication_session'] == Path(closure['session']).name,
        'Native source session/job differs')
    source = native['source_start']; event = clock['source_started']['event_payload']
    require(source['source_epoch_monotonic_sec'] == clock['source_epoch_monotonic_sec']
        == observations['phase_intervals']['source_origin_monotonic_sec'], 'Native/consumer/viewport origins differ')
    require(source['sequence'] == event['publication_sequence']
        and source['publication_monotonic_sec'] == event['publication_monotonic_sec']
        and event['publication_source_cursor_sec'] == 0, 'Native/consumer source-start publication differs')
    census = closure['publication_census']
    require(native['expected_events'] == native['retained_events'] == census['published']
        == clock['last_publication_sequence'] and clock['event_count'] == census['consumed']
        and clock['missing_publication_sequences'] == census['coalesced_obsolete_ui_partials'],
        'Native/consumer closure populations differ')
    require(native['completion_publication_monotonic_sec'] <= closure['observed_monotonic_sec'],
        'Engine closure capture predates native session completion')
    for binding in records.values(): verify(binding)
    return dict(native_terminal_and_source_start_joined=True, common_evidence_bindings=len(records),
        native_events=native['retained_events'], consumed_events=census['consumed'],
        coalesced_obsolete_ui_partials=census['coalesced_obsolete_ui_partials'],
        source_origin_monotonic_sec=source['source_epoch_monotonic_sec'],
        evidence=list(records.values()),
        clock_scope='Native publication, consumer and viewport perf_counter observations from the same cell; no cross-clock lifetime subtraction')


def review_cell(folder, *, checkpoint=None, **expected):
    """Caller must first reconstruct the qualified V2 production plan/population."""
    if checkpoint: checkpoint()
    transport = review_transport(folder, **expected)
    if checkpoint: checkpoint()
    observations = review_observations(Path(folder)/'application', payload=expected['payload'],
        application_owner=transport['application'], checkpoint=checkpoint)
    joins = join_reviews(folder, expected['payload'], transport, observations)
    if checkpoint: checkpoint()
    return dict(status='PASS_V2_APPLICATION_CELL_EVIDENCE_JOINS_ONLY', transport=transport,
        observations=observations, joins=joins, complete_panel_reviewed=False,
        native_payload_semantics_reviewed=False, caption_strings_independently_scored=False,
        names_independently_scored=False, accuracy_qualified=False, source_to_widget_latency_qualified=False,
        controlled_resources_qualified=False, physical_scanout_measured=False,
        actual_continuity_test=False, stop_restart_qualified=False, deployment_tier='UNKNOWN',
        integrated_N4_cells=0, N4_accepted=False)
