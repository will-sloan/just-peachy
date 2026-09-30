"""Saved-input source only; no device imports. README_ISOLATED_SOURCE_V1.md."""
from array import array
import os
import time
import wave
from isolated_source_transport_v1 import SourceFault


class SavedSource:
    def __init__(self, config):
        self.cfg = config
        if config['case'] == 'startup_failure':
            raise SourceFault('FIXTURE_STARTUP_FAILURE')
        with wave.open(config['source_wav'], 'rb') as wav:
            assert wav.getframerate() == 16000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
            pcm = array('h', wav.readframes(wav.getnframes()))
        assert os.sys.byteorder == 'little'
        self.audio = array('f', (x/32768 for x in pcm)).tobytes()
        self.limit = min(config['limit_samples'], len(self.audio)//4)
        self.offset = self.blocks = 0
        self.origin = time.monotonic_ns()
        self.stopped = False

    @property
    def finished(self):
        return self.offset >= self.limit

    def read(self, timeout):
        if self.finished:
            return None
        if self.cfg.get('paced'):
            remaining = (self.origin + self.offset*62500-time.monotonic_ns())/1e9
            if remaining > 0:
                time.sleep(min(remaining, timeout))
                return None
        case = self.cfg['case']
        if self.blocks == 10 and case == 'source_fault':
            raise SourceFault('INPUT_STATUS_GAP', {'raw_status_bits': 2, 'rejected_callback_frames': 480,
                              'upstream_lost_frames': None, 'loss_extent': 'UNKNOWN',
                              'input_buffer_adc_time_seconds': 10.25, 'callback_current_time_seconds': 10.282})
        if self.blocks == 10 and case == 'child_abrupt':
            os._exit(7)
        count = min(self.cfg['block_samples'], self.limit-self.offset)
        begin = self.offset
        audio = self.audio[begin*4:(begin+count)*4]
        meta = dict(model_start_sample=begin, native_start_frame=begin*3, native_frames=count*3,
                    epoch=self.cfg['epoch'], fixture_clock_ns=self.origin+begin*62500,
                    source_read_monotonic_ns=time.monotonic_ns(), source_kind='SAVED_FIXTURE_NOT_CAPTURE')
        self.offset += count
        self.blocks += 1
        if self.blocks == 3 and case == 'discontinuity':
            begin += 1
        if self.blocks == 3 and case == 'malformed_bytes':
            audio += b'!'
        if self.blocks == 3 and case == 'metadata_quota':
            meta['oversize'] = 'x'*3000
        return begin, audio, meta

    def stop(self):
        self.stopped = True
        # Unread saved-file samples were never captured or accepted by this fixture.
        self.limit = self.offset

    def close(self):
        return dict(closed=True, capture=False, source_read_samples=self.offset,
                    pending_previously_captured_blocks=0, unread_saved_file_not_accepted=True)


def create(config):
    return SavedSource(config)
