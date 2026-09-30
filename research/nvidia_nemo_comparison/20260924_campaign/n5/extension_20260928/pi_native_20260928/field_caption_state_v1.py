"""Empty caption wording for the offline candidate. README_FIELD_POSTRUN_V1.md."""


def empty_caption(snapshot, rows):
    if snapshot.get('strict') and rows:
        return 'No selected speech. Use Show all.'
    state = str(snapshot.get('state', 'IDLE')).upper()
    if state == 'RUNNING':
        return 'Listening for speech…'
    if state == 'STARTING':
        return 'Starting microphone…'
    if state == 'STOPPING':
        return 'Finishing this recording…'
    if state in {'ERROR', 'BLOCKED'}:
        return 'Captions unavailable. See the status above.'
    if (snapshot.get('sessions') or {}).get('opened_id'):
        return 'No captions in this saved conversation.'
    if state in {'STOPPED', 'CLOSED'}:
        return 'Recording stopped. No captions were produced.'
    return 'Choose Start when you are ready.'
