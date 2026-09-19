def completion_errors(engine, telemetry):
    """Fail closed on worker/consumer/finalizer leaks, including apparently COMPLETED state."""
    errors = []
    if engine.state != 'COMPLETED':
        errors.append('native session did not complete')
    if not engine.events.empty():
        errors.append('event consumer not drained')
    if engine._finalization_thread is None or engine._finalization_thread.is_alive():
        errors.append('finalization thread not joined')
    for worker in getattr(engine, '_threads', ()):
        if worker.is_alive():
            errors.append('live engine worker: ' + worker.name)
    if telemetry.get('live_lanes_at_finalization') or telemetry.get('bundle_retained_due_live_lanes'):
        errors.append('lane or bundle lease retained')
    for name, row in (telemetry.get('s6d') or {}).items():
        if name == 'event_consumer':
            if row is None or row.get('depth') != 0:
                errors.append('S6D event consumer depth not zero')
        elif name in {'journal', 'punctuation', 'policy'} and row is not None:
            if row.get('error') or row.get('depth') != 0 or row.get('thread_alive') is not False or (row.get('closed') is not True) or (row.get('accepted') != row.get('completed')):
                errors.append('S6D worker not successfully drained: ' + name)
    return errors
