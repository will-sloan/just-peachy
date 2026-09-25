"""Join the source clock to V1's lifecycle checks. README_APPLICATION_CLOSURE_V2.md."""
from pathlib import Path
import application_closure as base


def capture_engine(engine, consumer, clock, job):
    result = base.capture_engine(engine, consumer, clock, job)
    controller = getattr(clock, 'controller', None)
    result['source_clock_owner_join'] = dict(
        same_engine=clock is not None and getattr(clock, 'engine', None) is engine,
        consumer_retained=controller is not None and (getattr(controller, 'consumer', None) is consumer
            or controller.closed and consumer is not None and not consumer.is_alive()))
    return result


def validate_clock_join(observed):
    require = base.require
    join = observed.get('source_clock_owner_join', {})
    require(join.get('same_engine') is True and join.get('consumer_retained') is True, 'source clock owner differs')
    clock = observed.get('controller_clock') or {}; started = clock.get('source_started') or {}
    payload = started.get('event_payload') or {}; job = observed['job']; session = Path(observed['session']).name
    require(clock.get('publication_session') == session and payload.get('session_id') == session, 'source clock session differs')
    require(isinstance(payload.get('path'), str) and Path(payload['path']).resolve() == Path(job['audio_path']).resolve(),
        'source clock file differs')
    require(payload.get('mode') == 'file' and payload.get('pacing') == 'absolute'
        and payload.get('start_sample') == 0 and payload.get('gain') == 1., 'source clock delivery route differs')
    origin = payload.get('source_epoch_monotonic_sec')
    require(type(origin) in (int,float) and origin > 0
        and origin == clock.get('source_epoch_monotonic_sec') == started.get('source_epoch_monotonic_sec'),
        'source origin differs or is missing')
    require(clock.get('errors') == 0 and clock.get('event_counts',{}).get('source_started') == 1,
        'source clock has errors or ambiguous starts')
    census = observed['publication_census']
    require(clock.get('event_count') == census['consumed']
        and clock.get('last_publication_sequence') == census['published']
        and clock.get('missing_publication_sequences') == census['coalesced_obsolete_ui_partials'],
        'source clock and final event census differ')


def validate_engine(observed):
    result = base.validate_engine(observed); validate_clock_join(observed)
    return dict(result, source_clock_identity_join_verified=True)


def capture_archive(controller, engine):
    return base.capture_archive(controller, engine)


def validate_complete(observed, archive):
    validate_clock_join(observed)
    result = base.validate_complete(observed, archive)
    return dict(result, source_clock_identity_join_verified=True)
