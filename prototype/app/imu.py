"""Bounded BMI270 sensing and 3D relative attitude; see README_IMU.md."""
from collections import deque
from copy import deepcopy
import ctypes
import math
from pathlib import Path
import threading
import time

from .live_audio import DeviceLease
from .motion import MotionEvent
from .inertial_geometry import (MountGeometry, add, conjugate, cross, dot,
    horizontal_candidates, integrate, norm, rotate, scale, specific_force_at_array, unit)


def mounted_array_motion(worker, source_kind):
    """A loose sensor is diagnostic only. Bad configured sensors still fail closed."""
    if source_kind != 'live' or worker is None: return None
    motion = getattr(worker, 'motion', None)
    return worker if motion is None or motion.fixed_mount else None


class RelativeMotion:
    """Fresh boot reference, full body rotation, gravity feedback; no position integration.

    Tilt is observable from gravity, heading is relative and can drift. Fresh
    samples and a validated mount are not a claim of absolute heading accuracy.
    Normal tilt/turns keep the reference. Missing rotation requires a NEW frame,
    established automatically at rest, never silently reusing old locations.
    """
    def __init__(self, *, fixed_mount=False, compensate=False, mount=None):
        self.fixed_mount, self.compensate = fixed_mount, compensate
        self.mount = MountGeometry(mount)
        self.calibration = deque(maxlen=100)
        self.history = deque(maxlen=256)
        self.unsafe_generation = 0; self.frame_generation = 0; self.recovery_reason = None
        self.reset()

    def invalidate(self, reason):
        if self.bias is not None: self.unsafe_generation += 1
        self.valid = False; self.reason = reason; self.recovery_reason = reason
        self.bias = None; self.calibration.clear(); self.still_since = None
        self.state = 'RECOVERING'

    def reset(self):
        self.calibration.clear(); self.history.clear(); self.bias = None; self.up = None
        self.last = None; self.yaw = 0.; self.moving_seconds = 0.; self.rotation_total = 0.
        self.anchor = 0.; self.valid = False; self.q = (1., 0., 0., 0.)
        self.x_ref = None; self.y_ref = None; self.previous_omega = None
        self.alpha = (0., 0., 0.); self.still_since = None; self.dynamic_until = -math.inf
        self.dynamic = False; self.center_acc = None; self.drift_allowance = 2.
        self.state = 'INITIALIZING'; self.reason = 'Automatic startup reference: waiting for 2 seconds at rest'

    def _initialize(self, stamp, acc, gyro):
        if abs(norm(acc)-1.) > .08 or norm(gyro) > 3.:
            self.calibration.clear(); return
        self.calibration.append((stamp, tuple(acc), tuple(gyro)))
        if len(self.calibration) < 50 or stamp-self.calibration[0][0] < 1.9: return
        n = len(self.calibration)
        mean_acc = tuple(sum(r[1][i] for r in self.calibration)/n for i in range(3))
        if max(norm(add(r[1], scale(mean_acc, -1))) for r in self.calibration) > .035:
            self.calibration.clear(); return
        up = unit(mean_acc)
        projected = add(self.mount.array_axis, scale(up, -dot(self.mount.array_axis, up)))
        if self.mount.verified and norm(projected) < .25:
            self.reason = 'Array baseline is nearly vertical; waiting for a horizontal reference'
            return
        # Unverified geometry still permits raw sensor diagnostics, never a corrected cue.
        if norm(projected) < .25:
            arbitrary = min(((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)), key=lambda v: abs(dot(v,up)))
            projected = add(arbitrary, scale(up, -dot(arbitrary,up)))
        self.bias = tuple(sum(r[2][i] for r in self.calibration)/n for i in range(3))
        self.up = up; self.x_ref = unit(projected); self.y_ref = cross(up, self.x_ref)
        self.q = (1.,0.,0.,0.); self.yaw = 0.; self.anchor = stamp
        self.moving_seconds = 0.; self.rotation_total = 0.; self.drift_allowance = 2.
        self.previous_omega = None; self.alpha = (0.,0.,0.); self.dynamic = False
        self.dynamic_until = -math.inf; self.still_since = stamp
        self.frame_generation += 1; self.history.clear(); self.calibration.clear()

    def _advance(self, stamp, dt, acc, gyro):
        rate = add(gyro, scale(self.bias, -1.))
        omega = scale(rate, math.pi/180.)
        if self.previous_omega is not None:
            derivative = scale(add(omega, scale(self.previous_omega, -1.)), 1/dt)
            gain = dt/(.1+dt)  # Bounded derivative noise for lever-arm diagnostics.
            self.alpha = add(scale(self.alpha, 1-gain), scale(derivative, gain))
        self.previous_omega = omega
        self.center_acc = (specific_force_at_array(acc, omega, self.alpha, self.mount.offset)
                           if self.mount.verified and self.mount.offset_verified else acc)
        self.q = integrate(self.q, omega, dt)
        predicted_up = rotate(conjugate(self.q), self.up)
        residual = norm(add(self.center_acc, scale(predicted_up, -1.)))
        disturbed = abs(norm(self.center_acc)-1.) > .08 or residual > .12
        if disturbed:
            self.dynamic_until = stamp+.35
        dynamic = stamp < self.dynamic_until
        if dynamic and not self.dynamic: self.unsafe_generation += 1
        self.dynamic = dynamic
        # Accelerometer correction only during quiet, gravity-consistent periods.
        # It cannot correct yaw: the innovation is perpendicular to gravity.
        if not dynamic:
            error = cross(unit(self.center_acc), predicted_up)
            self.q = integrate(self.q, scale(error, .6), dt)
        rotating = norm(rate) > .5
        self.state = 'MOVING' if rotating or dynamic else 'STATIONARY'
        self.rotation_total += norm(rate)*dt
        if rotating: self.moving_seconds += dt
        # Very slow stationary bias adaptation reduces temperature drift without
        # resetting the frame. Slow constant yaw remains fundamentally ambiguous.
        if not dynamic and norm(rate) < .25 and residual < .035:
            if self.still_since is None: self.still_since = stamp
            if stamp-self.still_since >= 2.:
                gain = 1.-math.exp(-dt/60.)
                self.bias = add(scale(self.bias, 1-gain), scale(gyro, gain))
        else: self.still_since = None
        if rotating and not self.compensate:
            self.invalidate('Rotation assistance is off; acquiring a new stationary reference')

    def update(self, stamp, acc, gyro):
        values = (*acc, *gyro, stamp)
        if len(acc) != 3 or len(gyro) != 3 or not all(math.isfinite(v) for v in values):
            raise ValueError('Invalid inertial sample')
        if self.last is not None and stamp <= self.last: raise ValueError('Out-of-order inertial sample')
        dt = stamp-self.last if self.last is not None else 0.
        self.last = stamp
        clipped = max(abs(v) for v in gyro) >= 490. or max(abs(v) for v in acc) >= 3.9
        if dt > .15 or clipped:
            self.invalidate('Unmeasured rotation after sensor gap/range limit; acquiring a new reference')
        acc, gyro = self.mount.map(acc), self.mount.map(gyro)
        if self.bias is None:
            if not clipped: self._initialize(stamp, acc, gyro)
        elif dt > 0:
            self._advance(stamp, dt, acc, gyro)
        axis_xy = None
        if self.bias is not None:
            axis = rotate(self.q, self.mount.array_axis)
            axis_xy = (dot(axis, self.x_ref), dot(axis, self.y_ref))
            if math.hypot(*axis_xy) >= .25:
                heading = math.degrees(math.atan2(axis_xy[1], axis_xy[0]))
                self.yaw += (heading-self.yaw+180.) % 360.-180.
            self.drift_allowance = 2.+.002*(stamp-self.anchor)+.002*self.rotation_total
            self.valid = (self.fixed_mount and (self.mount.verified or not self.compensate)
                          and not self.dynamic and math.hypot(*axis_xy) >= .25)
            if not self.fixed_mount: self.reason = 'Fixed mounting has not been confirmed'
            elif self.compensate and not self.mount.verified: self.reason = 'Mount axis alignment pending; corrected direction unavailable'
            elif self.dynamic: self.reason = 'Acceleration detected; heading retained, old locations invalidated'
            elif math.hypot(*axis_xy) < .25: self.reason = 'Array nearly vertical; horizontal bearing unobservable'
            else:
                if self.state in ('INITIALIZING', 'RECOVERING'): self.state = 'STATIONARY'
                self.reason = 'Relative horizontal reference; drift and front/back ambiguity remain'
        row = dict(at=stamp, yaw_deg=self.yaw, valid=self.valid,
                   state=self.state, reason=self.reason, drift_allowance_deg=self.drift_allowance,
                   axis_xy=axis_xy, quaternion_body_to_reference=self.q,
                   frame_generation=self.frame_generation, unsafe_generation=self.unsafe_generation,
                   array_specific_force_g=self.center_acc)
        self.history.append(row)
        return row

    def transform(self, angle, at):
        row = next((r for r in reversed(self.history) if r['at'] <= at), None)
        if (not row or at-row['at'] > .15 or not row['valid'] or not self.valid
                or row['frame_generation'] != self.frame_generation
                or row['unsafe_generation'] != self.unsafe_generation):
            return None, 0.
        if angle is None: return None, 0.
        if not self.compensate: return angle, 1.
        # Both horizontal intersections of the native linear-array cone must be
        # tested. The retained tracker uses only the initial 0..180 half-plane.
        candidates = []
        for world in horizontal_candidates(angle, row['axis_xy']):
            if 5. <= world <= 175. and not any(abs(world-x) < 1e-6 for x in candidates):
                candidates.append(world)
        if len(candidates) != 1: return None, 0.
        return candidates[0], math.exp(-row['drift_allowance_deg']/10.)


class BMI270Worker:
    def __init__(self, config, on_unsafe=None, *, clock=time.perf_counter):
        if config.get('address', 0x68) not in (0x68, 0x69): raise ValueError('BMI270 address must be 0x68/0x69')
        if config.get('bus', '/dev/i2c-1') != '/dev/i2c-1': raise ValueError('Only the verified CM5 I2C1 bus is configured')
        for key in ('fixed_mount', 'rotation_compensation'):
            if type(config.get(key, False)) is not bool: raise ValueError(key+' must be boolean')
        self.config = config; self.on_unsafe = on_unsafe; self.clock = clock
        self.motion = RelativeMotion(fixed_mount=config.get('fixed_mount', False),
                                     compensate=config.get('rotation_compensation', False), mount=config.get('mount'))
        self.lock = threading.RLock(); self.stop_event = threading.Event(); self.thread = None
        self.error = None; self.opened = False; self.samples = 0; self.cpu_seconds = 0.
        self.started = None; self.last_received = None; self.reconnects = 0
        self.last_error = None; self.last_acc = None; self.last_gyro = None

    def start(self):
        self.thread = threading.Thread(target=self._run, name='proto-bmi270', daemon=True)
        self.thread.start(); return self

    def _run(self):
        lib = None; lease = None; cpu_start = time.thread_time()
        self.started = self.clock(); generation = 0
        try:
            lease = DeviceLease(self.config['lease_path']).acquire()
            lib = ctypes.CDLL(str(Path(self.config['library']).resolve(strict=True)))
            lib.peachy_bmi_open.argtypes = [ctypes.c_char_p, ctypes.c_int]
            lib.peachy_bmi_open.restype = ctypes.c_int
            lib.peachy_bmi_read.argtypes = [ctypes.POINTER(ctypes.c_double)]
            lib.peachy_bmi_read.restype = ctypes.c_int
            lib.peachy_bmi_close.argtypes = []; lib.peachy_bmi_close.restype = None
            failures = 0
            while not self.stop_event.is_set():
                try:
                    result = lib.peachy_bmi_open(self.config.get('bus', '/dev/i2c-1').encode(), self.config.get('address', 0x68))
                    if result: raise RuntimeError(f'BMI270 initialization failed ({result})')
                    with self.lock:
                        self.opened = True; self.error = None; self.last_received = self.clock()
                    values = (ctypes.c_double*6)()
                    # Poll faster than the 50Hz ODR so I2C overhead does not
                    # systematically skip every few data-ready samples.
                    while not self.stop_event.wait(.01):
                        result = lib.peachy_bmi_read(values)
                        if result == 1:
                            if self.clock()-self.last_received > .3:
                                raise RuntimeError('BMI270 stopped delivering fresh samples')
                            continue
                        if result: raise RuntimeError(f'BMI270 read failed ({result})')
                        now = self.clock()
                        with self.lock:
                            self.last_acc, self.last_gyro = tuple(values[:3]), tuple(values[3:])
                            self.motion.update(now, self.last_acc, self.last_gyro)
                            self.last_received = now; self.samples += 1; failures = 0
                            self.cpu_seconds = time.thread_time()-cpu_start
                            unsafe = self.motion.unsafe_generation != generation
                            generation = self.motion.unsafe_generation
                        if unsafe: self._notify_unsafe()
                except Exception as exc:
                    with self.lock:
                        self.error = self.last_error = f'{type(exc).__name__}: {exc}'
                        self.opened = False; self.reconnects += 1
                        self.motion.invalidate('Sensor interrupted; automatic reconnect and new reference pending')
                        generation = self.motion.unsafe_generation
                    self._notify_unsafe()
                    lib.peachy_bmi_close()
                    failures += 1
                    if self.stop_event.wait(min(30., 2.**min(failures,5))): break
        except Exception as exc:
            with self.lock:
                self.error = f'{type(exc).__name__}: {exc}'
                self.motion.invalidate('Motion sensor unavailable; spatial trust suspended')
            self._notify_unsafe()
        finally:
            if lib is not None: lib.peachy_bmi_close()
            if lease is not None: lease.close()
            self.opened = False; self.cpu_seconds = time.thread_time()-cpu_start

    def _notify_unsafe(self):
        if self.motion.fixed_mount and self.on_unsafe and not self.stop_event.is_set():
            ns = time.monotonic_ns()
            try: self.on_unsafe(MotionEvent('moving', ns, ns, .4, translation_or_range_unknown=True))
            except Exception: pass  # Controller shutdown must not strand the hardware lease.

    def transform(self, angle, at):
        with self.lock:
            if self.error or not self.opened: return None, 0.
            return self.motion.transform(angle, at)

    def reset(self):
        with self.lock: self.motion.reset()

    def snapshot(self):
        with self.lock:
            row = deepcopy(self.motion.history[-1]) if self.motion.history else {}
            age = self.clock()-row['at'] if row else None
            return dict(enabled=True, hardware_opened=self.opened, model='BMI270', address=self.config.get('address',104),
                        state='RECONNECTING' if self.error else self.motion.state, error=self.error,
                        yaw_deg=self.motion.yaw, compensation=self.motion.compensate,
                        valid=self.motion.valid and self.opened and age is not None and 0 <= age <= .15,
                        age_sec=age, reason=self.motion.reason, samples=self.samples,
                        cpu_seconds=self.cpu_seconds, elapsed_sec=self.clock()-self.started if self.started else 0,
                        frame_generation=self.motion.frame_generation, unsafe_generation=self.motion.unsafe_generation,
                        last_reference_loss=self.motion.recovery_reason, reconnects=self.reconnects, last_error=self.last_error,
                        mount_axes_verified=self.motion.mount.verified, offset_verified=self.motion.mount.offset_verified,
                        fixed_mount=self.motion.fixed_mount,
                        quaternion_body_to_reference=self.motion.q, raw_acceleration_g=self.last_acc,
                        raw_angular_rate_dps=self.last_gyro, array_specific_force_g=self.motion.center_acc,
                        drift_allowance_deg=self.motion.drift_allowance, drift_allowance_is_accuracy_bound=False,
                        absolute_position_or_heading=False, raw_audio_inference=False)

    def close(self):
        self.stop_event.set()
        if self.thread: self.thread.join(2.)
        return self.thread is None or not self.thread.is_alive()
