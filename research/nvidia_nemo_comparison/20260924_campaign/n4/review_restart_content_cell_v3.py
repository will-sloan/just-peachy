"""Join restart lifecycle, fixed roster and native captions. README_RESTART_FAMILY_V3.md."""
from pathlib import Path

from common import bind, fingerprint, load, verify
from metric_process import exact_process
from paced_child_admission import assert_plain_path
from paced_panel_plan_v3 import application_qualification
from review_application_content import fixed_roster
from review_application_transport import record
from review_restart_complete_v3 import review_cell as review_complete
from review_restart_native_content import review_widget
from review_scoring_bank import require

CELL_STATUS = 'PASS_RESTART_LIFECYCLE_ROSTER_AND_NATIVE_CONTENT_ONLY'


def review_cell(folder, *, checkpoint=None, **expected):
    """Internal API: selected plan/population must be independently admitted."""
    qb, qualification, context = application_qualification()
    payload = expected['payload']
    for key in ('source_receipt', 'catalog', 'gallery_preparation', 'runtimes'):
        require(payload[key] == context[key], 'Restart payload differs from qualified application context: '+key)
    base = review_complete(folder, checkpoint=checkpoint, **expected)
    require(base['native_caption_payloads_joined'] is False and base['actual_restart_qualified'] is False
            and base['N4_accepted'] is False, 'Unexpected complete-review scope')
    folder = Path(folder).resolve(strict=True); app = folder/'application'
    pair = base['transport']['pair_review']; checked = {}
    def keep(binding):
        require(binding['path'] not in checked or checked[binding['path']] == binding,
                'Evidence changed across restart content readers')
        checked[binding['path']] = binding
    for binding in base['joins']['evidence']: keep(binding)
    def read(path):
        if checkpoint: checkpoint()
        binding, value = record(path, app)
        require(checked.get(binding['path']) == binding, 'Content input was not checked by the complete reader')
        return value
    prepared = read(app/'PREPARED.json')
    require(len(pair['sessions']) == len(pair['native_reviews']) == 2
            and pair['full_job_sha256'] == fingerprint(payload['job']), 'Native pair or full planned source differs')
    sources = []
    for index, (session, envelope) in enumerate(zip(pair['sessions'], pair['native_reviews'])):
        path = assert_plain_path(session['native_session'], app/'data/sessions')
        require(path.parent == app/'data/sessions' and session['index'] == index
                and session['intent'] == ('mid_file_stop', 'completed_release')[index], 'Native pair order or path differs')
        sources.append(dict(session=path, delivered_frames=session['delivered_frames'],
                            intent=session['intent'], envelope=envelope))
    rosters = []; widgets = []
    source = load(payload['source_receipt']['path']); prototype = Path(source['prototype'])
    source_files = {str((prototype/name).resolve()):dict(path=str((prototype/name).resolve()), **value)
                    for name, value in source['files'].items()}
    for index, number in enumerate(('01', '02')):
        snapshot = read(app/'sessions'/number/'CONTROLLER_SNAPSHOT.json')
        people, roster = fixed_roster(payload, prepared, snapshot, checkpoint=checkpoint)
        require(not rosters or roster['people_sha256'] == rosters[0]['people_sha256'], 'Display roster changed across restart')
        viewport = base['observations']['viewport_reviews'][index]['reconstruction']
        summary = bind((app/'viewport' if index == 0 else app/'sessions'/number/'viewport')/'SUMMARY.json')
        require(checked.get(summary['path']) == summary and checked.get(viewport['evidence']['path']) == viewport['evidence'],
                'Viewport was not independently checked')
        widget = review_widget(sources, job=payload['job'], index=index, viewport_summary=summary,
            source_receipt=payload['source_receipt'], people=people, mode=payload['contract']['mode'], checkpoint=checkpoint)
        require(widget['viewport_review_sha256'] == fingerprint(viewport)
                and widget['people_sha256'] == roster['people_sha256']
                and widget['current_session'] == Path(sources[index]['session']).name,
                'Native content, viewport or roster join differs')
        require(len(widget['native_reviews']) == index+1 and all(
            n['full_job_sha256'] == fingerprint(payload['job']) and n['delivered_frames'] == sources[j]['delivered_frames']
            and n['intent'] == sources[j]['intent'] and n['session_id'] == Path(sources[j]['session']).name
            for j, n in enumerate(widget['native_reviews'])), 'Native content changed planned or delivered scope')
        for binding in widget['evidence']:
            require(checked.get(binding['path']) == binding or source_files.get(binding['path']) == binding,
                    'Native content used evidence outside the independently reviewed pair/source')
            keep(binding)
        for binding in roster['evidence']: keep(binding)
        rosters.append(roster); widgets.append(widget)
    for binding in [qb, qualification['application_context']]: keep(binding)
    for binding in checked.values(): verify(binding)
    require(exact_process(base['transport']['application']) is None
            and exact_process(base['transport']['coordinator']) is None, 'Restart owner became active during content review')
    if checkpoint: checkpoint()
    return dict(base, status=CELL_STATUS, joins=dict(base['joins'], evidence=list(checked.values()),
        native_caption_payloads_joined=True), rosters=rosters, widgets=widgets,
        application_qualification=qb, source_context=qualification['application_context'],
        fixed_display_roster_independently_joined=True, primary_caption_text_consistency_reviewed=True,
        source_delivery_independently_joined=True, application_owner_and_primary_settings_joined=True,
        native_caption_payloads_joined=True, exact_consumed_event_attribution=False,
        names_independently_scored=False, accuracy_qualified=False, physical_scanout_measured=False,
        deployment_tier='UNKNOWN')
