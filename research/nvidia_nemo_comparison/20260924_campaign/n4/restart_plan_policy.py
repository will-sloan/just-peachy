"""Fixed saved-file restart controls; see README_RESTART_PLAN.md."""
from common import audio_only

CHUNK = 320
JOBS = ('N2_S45_03_03_O0', 'N2_S45_03_03_O1')
POLICY = dict(schema='n4-selected-restart-policy-v1', jobs=list(JOBS),
    pairs_per_candidate=2, sessions_per_pair=2, minimum_source_seconds=2,
    maximum_source_seconds=120, maximum_pair_seconds=900,
    stop_rule='floor(full_frames / 2 / 320) * 320; observe actual delivered prefix',
    first_session='public mid-file stop followed by full delivered-prefix drain',
    second_session='same unchanged full file from zero through EOF and release',
    same_controller_ui_worker_models=True, fresh_application_per_pair=True,
    prior_caption_history='retained; partition observations by native session',
    timing_correction=False, no_source_schedule_change=True)


def stop_after_samples(job):
    """No references or content inspection; threshold is not delivered length."""
    audio_only(job)
    if job['job_id'] not in JOBS or not job['job_id'].endswith('_'+job['tap']):
        raise ValueError('Use the predeclared S45_03_03 saved O0/O1 anchor')
    if not 2*16000 <= job['frames'] <= 120*16000:
        raise ValueError('Restart source duration outside the bounded policy')
    threshold = (job['frames']//(2*CHUNK))*CHUNK
    if not CHUNK <= threshold <= job['frames']-2*CHUNK:
        raise ValueError('Stop must leave a positive prefix and pre-EOF margin')
    return threshold
