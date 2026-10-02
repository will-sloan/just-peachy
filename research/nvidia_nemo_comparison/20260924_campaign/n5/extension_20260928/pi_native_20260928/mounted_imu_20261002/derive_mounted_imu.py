"""Prepare reviewed app derivatives without changing old releases; see README.md."""
import ast
import hashlib


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Source derivation boundary changed: ' + before[:80])
    return text.replace(before, after)


INVERSE = '''    def to_device(self, reference_angle, at):
        """Project a retained horizontal bearing onto the CURRENT microphone axis.

        Returns the native folded 0..180 display angle. This never selects a
        front/back side or estimates distance. A stale/untrusted pose hides the
        association; the independent raw beam arrows remain available.
        """
        if (type(reference_angle) not in (int, float) or not math.isfinite(reference_angle)
                or type(at) not in (int, float) or not math.isfinite(at)):
            return None
        row = next((r for r in reversed(self.history) if r['at'] <= at), None)
        if (not row or at-row['at'] > .15 or not row['valid'] or not self.valid
                or row['frame_generation'] != self.frame_generation
                or row['unsafe_generation'] != self.unsafe_generation):
            return None
        if not self.compensate:
            return reference_angle if 0 <= reference_angle <= 180 else None
        theta = math.radians(reference_angle)
        cosine = row['axis_xy'][0]*math.cos(theta)+row['axis_xy'][1]*math.sin(theta)
        return math.degrees(math.acos(max(-1., min(1., cosine))))


'''


def derive(imu_bytes, spatial_bytes):
    """All source is explicit input; outputs are compiled new bytes plus digests."""
    imu, spatial = imu_bytes.decode(), spatial_bytes.decode()
    imu = replace_once(imu, '\n\nclass BMI270Worker:', '\n\n' + INVERSE + 'class BMI270Worker:')
    imu = replace_once(imu, '    def reset(self):\n        with self.lock:',
        '    def to_device(self, reference_angle, at):\n'
        '        with self.lock:\n'
        '            if self.error or not self.opened: return None\n'
        '            return self.motion.to_device(reference_angle, at)\n\n'
        '    def reset(self):\n        with self.lock:')
    imu = replace_once(imu, 'quaternion_body_to_reference=self.motion.q, raw_acceleration_g=self.last_acc,',
        "quaternion_body_to_reference=self.motion.q, axis_xy=row.get('axis_xy'),\n"
        '                        raw_acceleration_g=self.last_acc,')
    spatial = replace_once(spatial,
        "active = raw.get('state') in ('RUNNING', 'WAITING') and (motion is None or motion['valid'])",
        "active = raw.get('state') in ('RUNNING', 'WAITING')\n"
        "        motion_ready = motion is None or motion.get('valid') is True")
    spatial = replace_once(spatial,
        "            if self.motion is not None:\n"
        "                angle, _ = self.motion.transform(angle, field['completed'])\n"
        "                if angle is None: continue\n", '')
    spatial = replace_once(spatial,
        "            if (not active or age < 0 or age > self.config.position_decay_sec",
        "            if (not active or not motion_ready or age < 0 or age > self.config.position_decay_sec")
    spatial = replace_once(spatial,
        "            fresh = speaking and age <= DISPLAY_LIMIT and row['track_id'] == latest_track",
        "            if self.motion is not None:\n"
        "                reference_angle = row['angle_deg']\n"
        "                device_angle = self.motion.to_device(reference_angle, now)\n"
        "                if device_angle is None: continue\n"
        "                row.update(angle_deg=device_angle, reference_angle_deg=reference_angle)\n"
        "            fresh = speaking and age <= DISPLAY_LIMIT and row['track_id'] == latest_track")
    spatial = replace_once(spatial,
        "message = ('Relative front-side frame · yaw %.1f°' % motion['yaw_deg']) if motion['valid'] else motion['reason']",
        "message = ('Device-relative beams · motion-corrected location logic · turn %.1f°' % motion['yaw_deg']) if motion['valid'] else motion['reason']")
    spatial = replace_once(spatial,
        "coordinate_frame='relative_anchor_front_assumed' if motion and motion['compensation'] else 'device',",
        "coordinate_frame='device',\n"
        "            association_reference_frame='relative_anchor_front_assumed' if motion and motion['compensation'] else 'device',")
    outputs = {'imu.py': imu.encode(), 'live_spatial.py': spatial.encode()}
    for name, data in outputs.items():
        compile(data, name, 'exec')
        ast.parse(data)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    return outputs, dict(inputs={'imu.py': sha(imu_bytes), 'live_spatial.py': sha(spatial_bytes)},
                         outputs={name: dict(bytes=len(raw), sha256=sha(raw)) for name, raw in outputs.items()},
                         native_executed=False)
