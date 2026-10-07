"""Record existing spatial/IMU observations on the source clock. See README.md."""
import threading

from runtime_support import SegmentedText, encoded
from runtime_ui_channel import SpatialViews


class ArchivedSpatialViews(SpatialViews):
    """No extra sensor queries, inference, synchronous disk I/O or session buffer."""
    def __init__(self, primary, device, motion, directory, budget, fail):
        super().__init__(primary, device)
        self.motion_worker = motion
        self.origin = None
        self.last_pose = float('-inf')
        self.last_frame = None
        self.last_callback = None
        self.last_sample = 0
        self.archive_lock = threading.RLock()
        self.archive_error = None
        self.closed = False
        (directory/'spatial').mkdir()
        (directory/'motion').mkdir()
        self.beams = SegmentedText(directory/'spatial'/'beam_angles.jsonl',
            maximum_bytes=budget.maximum, budget=budget, fail=fail)
        self.poses = SegmentedText(directory/'motion'/'orientation.jsonl',
            maximum_bytes=budget.maximum, budget=budget, fail=fail)
        self.fail_archive = fail
        # Observe the retained update AFTER its original math. This consumes no
        # additional I2C samples and does not wait for the speech/model thread.
        # Queue failures stop the speech session, not the sensor's recovery loop.
        with motion.lock:
            self.original_update = motion.motion.update
            def observed_update(*args, **kwargs):
                result = self.original_update(*args, **kwargs)
                try:
                    self._capture_history()
                except Exception as exc:
                    self._fault(exc)
                return result
            self.observed_update = observed_update
            motion.motion.update = observed_update
            self._capture_history()

    def _fault(self, error):
        if self.archive_error is None:
            self.archive_error = error
            self.fail_archive(error)

    def bind_origin(self, origin):
        super().bind_origin(origin)
        with self.archive_lock:
            self.origin = float(origin)
            self._emit(self.poses, 'source_origin', {}, None, None)

    def receive(self, command, values, started, completed):
        super().receive(command, values, started, completed)
        with self.archive_lock:
            self._emit(self.beams, 'xvf_observation', dict(command=command, values=list(values),
                control_started_monotonic_sec=started, control_completed_monotonic_sec=completed,
                measurement_clock_scope='control read; DSP acoustic measurement time unavailable'), None, None)

    def _emit(self, sink, kind, row, callback, sample):
        if self.closed:
            raise RuntimeError('Spatial archive has closed')
        sink.write(encoded(dict(schema='just-peachy.source-aligned-spatial.v1',
            kind=kind, source_epoch_monotonic_sec=self.origin,
            audio_callback_monotonic_sec=callback, model_sample_end=sample,
            model_sample_rate=16000, alignment=('exact_audio_callback' if kind == 'audio_clock_anchor'
                else 'observation_monotonic_clock; join_recorded_audio_clock_anchors'),
            **row)).decode()+'\n')

    def _capture_history(self):
        # Caller holds the existing sensor lock; no separate polling owner.
        with self.archive_lock:
            if self.closed:
                return
            history = self.motion_worker.motion.history
            if (history and self.last_pose != float('-inf') and history[0]['at'] > self.last_pose + .1
                    and history[0]['frame_generation'] == self.last_frame):
                error = RuntimeError('Motion history advanced beyond the last archived pose; preserve gap and Stop')
                self._fault(error)
                raise error
            for source in history:
                if source['at'] <= self.last_pose:
                    continue
                row = dict(source)
                if self.last_frame is not None and row['frame_generation'] != self.last_frame:
                    self._emit(self.poses, 'reference_changed', dict(previous_frame=self.last_frame,
                        frame_generation=row['frame_generation'], at=row['at']), None, None)
                self.last_frame = row['frame_generation']
                self.last_pose = row['at']
                row['source_offset_sec'] = None if self.origin is None else row['at']-self.origin
                row['absolute_heading_available'] = False
                row['absolute_translation_available'] = False
                self._emit(self.poses, 'bmi270_pose', row, None, None)

    def advance_audio(self, block):
        super().advance_audio(block)
        callback = block.callback_perf_counter_ns/1e9
        sample = int(block.model_start_sample)+len(block.audio)
        self.last_callback, self.last_sample = callback, sample
        if self.archive_error is not None:
            raise self.archive_error
        # Retain exact audio anchors for later joins. Sensor rows are recorded
        # immediately even while inference delays this consumer.
        with self.motion_worker.lock:
            self._capture_history()
        with self.archive_lock:
            self._emit(self.poses, 'audio_clock_anchor', dict(model_start_sample=int(block.model_start_sample)), callback, sample)

    def close_archive(self):
        if self.closed:
            return
        errors = []
        with self.motion_worker.lock:
            try:
                self._capture_history()
            except Exception as exc:
                errors.append(repr(exc))
            if self.motion_worker.motion.update is not self.observed_update:
                errors.append('Owned sensor observation hook changed')
            else:
                self.motion_worker.motion.update = self.original_update
            with self.archive_lock:
                self._emit(self.poses, 'audio_end_bound', {}, self.last_callback, self.last_sample)
                self.closed = True
        for writer in (self.beams, self.poses):
            try:
                writer.close()
            except BaseException as exc:
                errors.append(repr(exc))
        if errors:
            raise RuntimeError('; '.join(errors))
