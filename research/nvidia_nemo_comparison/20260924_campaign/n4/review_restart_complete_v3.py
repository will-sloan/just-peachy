"""Guarded restart transport plus existing observations; README_RESTART_FAMILY_V3.md."""
from pathlib import Path
from review_restart_complete import join_reviews, CELL_STATUS
from review_restart_transport_v3 import review_cell as review_transport
from review_restart_observations import review_observations

def review_cell(folder, *, checkpoint=None, **expected):
    if checkpoint: checkpoint()
    transport = review_transport(folder, checkpoint=checkpoint, **expected)
    if checkpoint: checkpoint()
    observations = review_observations(Path(folder)/'application', payload=expected['payload'],
        application_owner=transport['application'], checkpoint=checkpoint)
    joins = join_reviews(folder, expected['payload'], transport, observations)
    if checkpoint: checkpoint()
    return dict(status=CELL_STATUS, cell_id=expected['payload']['cell_id'], collected=transport['collected'],
        transport=transport, observations=observations, joins=joins, viewport_rows_reviewed=True, resource_samples_reviewed=True,
        complete_selected_population_reviewed=False, native_caption_payloads_joined=False, actual_restart_qualified=False,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False, integrated_N4_cells=0, N4_accepted=False)
