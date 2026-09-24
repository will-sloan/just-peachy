"""Bounded capture/telemetry qualification; see README_CM5_CHECKS.md."""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--config', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--seconds', type=float, default=10)
parser.add_argument('--imu-config', type=Path)
args = parser.parse_args()
if not 1 <= args.seconds <= 90: parser.error('Use a bounded 1..90 second check')
sys.path.insert(0, str(args.source))
from app.live_audio import LiveConfig, XVFLiveSource, summarize_live_integrity

config = LiveConfig(**json.loads(args.config.read_text()))
source = XVFLiveSource(config)
source.spatial_fast = True
count = 0; energy = 0.; peak = 0.; error = None; beams = {}
motion = None; motion_rows = []; motion_next = 0.
try:
    if args.imu_config:
        from app.imu import BMI270Worker
        motion = BMI270Worker(json.loads(args.imu_config.read_text())).start()
    source.start(consent=True)  # User explicitly preapproved these device checks.
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        block = source.read()
        if block is None: continue
        count += len(block.audio)
        energy += float(np.sum(block.audio.astype(np.float64)**2))
        peak = max(peak, float(np.max(np.abs(block.audio))))
        if motion is not None and time.monotonic() >= motion_next:
            motion_rows.append(motion.snapshot()); motion_next=time.monotonic()+1.
    beams = source.beam_diagnostics.snapshot()
except Exception as exc:
    error = f'{type(exc).__name__}: {exc}'
finally:
    try: source.stop()
    except Exception as exc: error = (error or '') + f'; Stop: {exc}'
    if motion is not None: motion.close()
result = dict(error=error, model_samples=count, rms=(energy/count)**.5 if count else 0,
              peak=peak, beams=beams, integrity=summarize_live_integrity(source),
              audio_saved=False, speech_quality_or_identity_validated=False)
result['motion'] = motion_rows
result['motion_ok'] = (None if motion is None else bool(motion_rows
    and motion_rows[-1]['valid'] and not any(row.get('error') for row in motion_rows)))
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('error','model_samples','rms','peak','motion_ok')}))
raise SystemExit(0 if not error and result['integrity']['ok'] and count and result['motion_ok'] is not False else 1)
