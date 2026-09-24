"""Source-only synthetic EVENT rows; no synthesized/acoustic data or truth input.

These intentionally fictional speaker IDs exercise display behavior only.
See README_N1_FRONTEND.md for schema, commands and limitations.
"""
from copy import deepcopy


def row(identifier, speaker, text, start, end, *, caption='turn', final=False, token_range=None):
    words = text.split()
    return dict(id=identifier, caption_key=caption, label=speaker, profile_id='fixture-'+speaker,
        track_id=speaker, raw_asr_text=text, provisional_display_text=text, final=final,
        source_start_sec=start, source_end_sec=end, timing_kind='synthetic_event_window',
        span_ids=[identifier+'-word-'+str(i) for i in range(len(words))],
        speaker_revision=1, first_shown_label='Unknown', committed_label=speaker,
        ownership_state='supported_history', token_range=token_range or [0, len(words)],
        selected=speaker == 'Alex', speaker_history=[{'label':speaker,'revision':1}])


def scenarios():
    aba = [row('aba-a1', 'Alex', 'I will start this conversation.', 0, 1, token_range=[0,5]),
           row('aba-b', 'Blair', 'One short interruption.', 1, 1.3, token_range=[5,8]),
           row('aba-a2', 'Alex', 'I will finish my sentence.', 1.3, 3, token_range=[8,13])]
    simultaneous = [row('sim-a', 'Alex', 'The first ongoing message.', 4, 6, caption='sim-a'),
                    row('sim-b', 'Blair', 'The second ongoing message.', 4.5, 6.5, caption='sim-b')]
    correction = deepcopy(aba)
    correction[1].update(label='Casey', profile_id='fixture-Casey', track_id='Casey',
        speaker_revision=2, committed_label='Casey',
        speaker_history=[{'label':'Blair','revision':1},{'label':'Casey','revision':2}])
    history = [row('history-'+str(i), 'Alex' if i%2 else 'Blair',
                   'Completed transcript turn '+str(i)+'.', i*2, i*2+1, caption='history-'+str(i), final=True)
               for i in range(50)]
    large = row('large', 'Alex', ' '.join('word'+str(i) for i in range(420)), 100, 140, caption='large')
    return {
        'aba_and_short_interruption': [aba[:1], aba[:2], aba],
        'simultaneous_updates': [simultaneous[:1], simultaneous,
            [simultaneous[0],dict(simultaneous[1],raw_asr_text='A revised simultaneous message.',provisional_display_text='A revised simultaneous message.')]],
        'late_correction': [aba, correction],
        'scrolling': [history, history+[row('current','Alex','Current words.',101,102,caption='current')]],
        'large_paragraph': [history+[large], history+[dict(large,raw_asr_text=large['raw_asr_text']+' New suffix.',provisional_display_text=large['raw_asr_text']+' New suffix.')]],
    }
