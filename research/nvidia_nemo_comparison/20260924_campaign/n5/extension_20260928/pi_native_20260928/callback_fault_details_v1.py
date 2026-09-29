"""Unintegrated fault-only callback diagnostics; README_CALLBACK_FAULT_V1.md."""
import time


def detailed_source_class(base):
    class DetailedSource(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._callback_fault_detail = None

        def _callback(self, indata, frames, time_info, status):
            try:
                return super()._callback(indata, frames, time_info, status)
            except self.sd.CallbackAbort:
                # Fault-only bounded scalar record: no file I/O, audio copies,
                # retry or change to the parent's abort decision. A failure in
                # diagnostic extraction must never replace the original abort.
                try:
                    self._callback_fault_detail = (
                        int(frames), time.perf_counter_ns(),
                        getattr(status, '_flags', None),
                        *(getattr(status, key, None) for key in (
                            'input_underflow', 'input_overflow', 'output_underflow',
                            'output_overflow', 'priming_output')),
                        float(time_info.inputBufferAdcTime),
                        float(getattr(time_info, 'currentTime', float('nan'))),
                    )
                except Exception:
                    self._callback_fault_detail = ('DIAGNOSTIC_EXTRACTION_FAILED',)
                raise

        def status(self):
            result = super().status()
            detail = self._callback_fault_detail
            if detail is None:
                result['callback_fault_detail'] = None
            elif len(detail) == 1:
                result['callback_fault_detail'] = {'status': detail[0]}
            else:
                keys = ('rejected_callback_frames', 'after_abort_perf_counter_ns',
                        'raw_status_bits', 'input_underflow', 'input_overflow',
                        'output_underflow', 'output_overflow', 'priming_output',
                        'input_buffer_adc_time_seconds', 'callback_current_time_seconds')
                result['callback_fault_detail'] = dict(zip(keys, detail))
                result['callback_fault_detail']['upstream_lost_frames'] = None
                result['callback_fault_detail']['loss_extent'] = 'UNKNOWN'
            return result

    return DetailedSource
