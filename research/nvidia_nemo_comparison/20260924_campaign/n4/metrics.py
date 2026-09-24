"""Pinned established scorers, evaluator-only. See README_METRICS.md."""
from collections import defaultdict
from importlib.metadata import version
import math
import string
import unicodedata

PINNED = {'meeteval':'0.4.3', 'pyannote.metrics':'4.1'}
SCORING_VERSION = 'n4-established-v1'


def require_versions():
    actual = {name:version(name) for name in PINNED}
    if actual != PINNED:
        raise ValueError('Metric versions differ from reviewed contract: '+str(actual))
    return actual


def canonical(text):
    return ' '.join(unicodedata.normalize('NFKC', text).lower().translate(
        str.maketrans('', '', string.punctuation)).split())


def counts(value):
    return dict(errors=int(value.errors), words=int(value.length),
        substitutions=int(value.substitutions), deletions=int(value.deletions),
        insertions=int(value.insertions), rate=float(value.errors/value.length) if value.length else None)


def lexical(reference, hypothesis):
    require_versions()
    from meeteval.wer.wer.siso import siso_word_error_rate
    return counts(siso_word_error_rate(reference, hypothesis))


def speaker_words(reference_turns, hypothesis_segments, *, normalize=True):
    require_versions()
    from meeteval.wer.wer.cp import cp_word_error_rate
    from meeteval.wer.wer.mimo import mimo_word_error_rate
    convert = canonical if normalize else lambda text:' '.join(text.split())
    reference, hypothesis = defaultdict(list), defaultdict(list)
    for t in reference_turns:
        reference[str(t['identity'])].append(convert(t['transcript']))
    for row in hypothesis_segments:
        # Unknown remains a real hypothesis stream; never map using known truth.
        hypothesis[str(row['track'])].append(convert(row['text']))
    r = {k:' '.join(v) for k,v in reference.items()}
    h = {k:' '.join(v) for k,v in hypothesis.items()}
    cp = counts(cp_word_error_rate(r, h, reference_sort=False, hypothesis_sort=False))
    if max(len(r), len(h)) > 10:
        mimo = dict(status='UNAVAILABLE_ESTABLISHED_IMPLEMENTATION_SPEAKER_LIMIT', value=None)
    elif not r or not h:
        # The exact no-stream edit counts equal cpWER. Do not feed an empty list
        # to the upstream MIMO implementation (requires at least one stream).
        mimo = dict(status='EXACT_EMPTY_STREAM_COUNTS', value=dict(cp))
    else:
        mimo = dict(status='SCORED', value=counts(mimo_word_error_rate(dict(reference), h,
            reference_sort=False, hypothesis_sort=False)))
    return dict(cpwer=cp, mimo=mimo)


def activity(reference, hypothesis, duration, *, complete_reference, collar=.25):
    require_versions()
    if not complete_reference:
        return dict(status='UNAVAILABLE_INCOMPLETE_REFERENCE', DER=None, JER=None)
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(collar) or collar < 0:
        raise ValueError('Invalid evaluation timebase')
    from pyannote.core import Annotation, Segment, Timeline
    from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate
    def annotation(rows):
        result = Annotation()
        for i, row in enumerate(rows):
            a,b = row['start'],row['end']
            if not all(math.isfinite(t) for t in (a,b)) or not 0 <= a < b <= duration:
                raise ValueError('Out-of-file segment; no timestamp clamping')
            result[Segment(a,b), str(i)] = str(row['label'])
        # Coalesce adjacent/overlapping intervals per speaker before collaring.
        return result.support()
    r,h = annotation(reference),annotation(hypothesis)
    uem = Timeline([Segment(0,duration)])
    der_metric = DiarizationErrorRate(collar=collar, skip_overlap=False)
    jer_metric = JaccardErrorRate(collar=collar, skip_overlap=False)
    der = {k:float(v) for k,v in der_metric.compute_components(r,h,uem=uem).items()}
    jer = {k:float(v) for k,v in jer_metric.compute_components(r,h,uem=uem).items()}
    return dict(status='APPROXIMATE_ACTIVITY_ONLY' if reference else 'EMPTY_REFERENCE_FALSE_ALARMS',
        DER=float(der_metric.compute_metric(der)) if der['total'] else None,
        JER=float(jer_metric.compute_metric(jer)) if jer['speaker count'] else None,
        DER_components=der, JER_components=jer, collar_parameter_seconds=collar,
        collar_halfwidth_seconds=collar/2,
        overlap='include', mapping='per-scene Hungarian', uem_seconds=[0,duration],
        timing='existing mapped estimated activity, not phonetic gold')


def score_cell(truth, prediction):
    """Successful empty output misses words; failed execution has no fabricated WER."""
    if prediction['job_id'] != truth['job_id']:
        raise ValueError('Prediction/reference join differs')
    reference = ' '.join(t['transcript'] for t in truth['turns'])
    result = dict(job_id=truth['job_id'], reference_class=truth['reference_class'],
        execution_status=prediction['status'], reference_words=len(canonical(reference).split()),
        audio_seconds=truth['frames']/16000, primary_wer=None, raw_wer=None,
        cpwer=None, mimo=None, activity=None,
        tcpwer_status='UNAVAILABLE_NO_EXACT_REFERENCE_WORD_TIMES')
    if prediction['status'] != 'COMPLETE':
        result['scoring_status'] = 'NOT_SCORED_EXECUTION_'+prediction['status']
        return result
    if not all(k in prediction for k in ('raw_text','segments','activity')):
        raise ValueError('Complete prediction lacks required evidence fields')
    if canonical(' '.join(s['text'] for s in prediction['segments'])) != canonical(prediction['raw_text']):
        raise ValueError('Speaker segments omit, duplicate or reorder raw caption words')
    result['scoring_status'] = 'SCORED'
    kind = truth['reference_class']
    if kind == 'complete_nonoverlap':
        result['primary_wer'] = lexical(canonical(reference),canonical(prediction['raw_text']))
        result['raw_wer'] = lexical(reference,prediction['raw_text'])
    elif kind == 'empty_control':
        inserted = len(canonical(prediction['raw_text']).split())
        result.update(inserted_words=inserted, inserted_words_per_minute=inserted/(truth['frames']/16000/60))
    elif kind == 'incomplete_ambient_reference':
        result['target_only_diagnostic'] = lexical(canonical(reference),canonical(prediction['raw_text']))
        result['scoring_status'] = 'TARGET_ONLY_NOT_ALL_SPEAKER_ACCURACY'
    elif kind != 'complete_overlap':
        raise ValueError('Unknown reference class')
    if kind in ('complete_nonoverlap','complete_overlap'):
        result.update(speaker_words(truth['turns'], prediction['segments']))
    refs = [dict(start=a/16000, end=b/16000, label=t['identity'])
            for t in truth['turns'] for a,b in t['activity_ranges_samples_estimated']]
    result['activity'] = (activity(refs, prediction['activity'], truth['frames']/16000,
                                  complete_reference=truth['complete_reference'])
        if prediction['activity'] is not None else dict(status='UNAVAILABLE_FULL_TRACK_ACTIVITY_NOT_RECORDED',DER=None,JER=None))
    return result


def aggregate(rows):
    from collections import Counter
    scored = [r['primary_wer'] for r in rows if r['primary_wer'] is not None]
    errors, words = sum(r['errors'] for r in scored), sum(r['words'] for r in scored)
    excluded = [r for r in rows if r['execution_status'] != 'COMPLETE']
    return dict(required_cells=len(rows), execution_statuses=dict(Counter(r['execution_status'] for r in rows)),
        primary_nonoverlap_scored_cells=len(scored), primary_nonoverlap_errors=errors,
        primary_nonoverlap_words=words, primary_nonoverlap_WER=errors/words if words else None,
        unscored_execution_reference_words=sum(r['reference_words'] for r in excluded),
        unscored_execution_audio_seconds=sum(r['audio_seconds'] for r in excluded))
