"""Display-only enrollment progress and unbiased ASR reference estimates.

No text enters speaker inference or its quality gate. See README_ENROLLMENT.md.
"""
import hashlib
import re
from difflib import SequenceMatcher


def reference_text(text):
    if not isinstance(text, str) or len(text) > 4096 or '\x00' in text:
        raise ValueError('Recording guide must be text of at most 4096 characters')
    return {'offered_text': text, 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'role': 'offered_reference_only_not_verified_transcript'}


def agreement(offered, heard):
    words = lambda s: re.findall(r"[^\W_]+(?:['’][^\W_]+)*", s.casefold())
    ref, query = words(offered), words(heard)
    blocks = SequenceMatcher(None, ref, query, autojunk=False).get_matching_blocks()
    matches = sum(b.size for b in blocks)
    return {'estimated_coverage': matches / len(ref) if ref else None,
            'estimated_agreement': 2 * matches / (len(ref) + len(query)) if ref or query else None,
            'reference_words': len(ref), 'recognized_words': len(query), 'matched_words': matches,
            'method': 'casefolded ordered word matches; estimate, not verified reading',
            'affects_voice_quality': False}


class ReadProgress:
    """One stream of the existing recognizer, owned only by the quality worker."""
    def __init__(self, stream, offered, *, token_timing=False):
        self.stream = stream
        self.token_timing = token_timing
        self.reference = reference_text(offered)
        self.rows = []
        self.samples = 0
        self.start = 0
        self.partial = ''
        self.finished = False

    def _timing(self):
        if not self.token_timing:return None
        try:
            result=self.stream.recognizer.get_result_all(self.stream.stream)
            tokens=list(result.tokens);times=list(result.timestamps)
            if len(tokens)!=len(times) or len(tokens)>2048:return None
            return dict(tokens=tokens,timestamps_sec=times,segment_start_sec=float(result.start_time),
                        method='Sherpa 1.13.4 transducer token emissions; not acoustic boundaries',confidence=None)
        except (AttributeError,TypeError,ValueError):return None

    def _final(self, text, timing=None):
        if text.strip():
            self.rows.append({'utterance_id': f'enrollment-{len(self.rows)}',
                              'start_sample': self.start, 'end_sample': self.samples,
                              'raw_asr_text': text[:8192],
                              'timing_kind': 'decoder endpoint source bounds, not word alignment'})
            if self.token_timing:self.rows[-1]['token_timing']=timing
        self.start = self.samples
        self.partial = ''

    def accept(self, samples):
        if self.finished:
            raise ValueError('Enrollment ASR already finished')
        for left in range(0, len(samples), 1600):
            piece = samples[left:left + 1600]
            self.samples += len(piece)
            self.partial, endpoint = self.stream.accept(piece)
            if endpoint:
                timing=self._timing()
                self._final(self.stream.reset_endpoint(),timing)

    def finish(self):
        if not self.finished:
            text=self.stream.finish()
            self._final(text,self._timing())
            self.finished = True
        return self.snapshot()

    def snapshot(self):
        heard = ' '.join([r['raw_asr_text'] for r in self.rows] + [self.partial])
        return {**agreement(self.reference['offered_text'], heard),
                'state': 'final_estimate' if self.finished else 'provisional_estimate',
                'analyzed_audio_s': self.samples / 16000,
                'partial_raw_asr_text': self.partial[:8192],
                'utterances': [dict(r) for r in self.rows]}


class VerifiedAnimation:
    """Interpolate toward measured support; never extrapolate during backlog."""
    def __init__(self):
        self.value = 0.
        self.last = None

    def update(self, verified, now):
        dt = 0 if self.last is None else max(0., now - self.last)
        self.last = now
        self.value = min(verified, self.value + max(.5, (verified - self.value) * 5) * dt)
        return self.value
