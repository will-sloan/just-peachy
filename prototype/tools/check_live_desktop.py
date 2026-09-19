"""Bounded, explicitly consented real XVF/native pipeline check. See README.md."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'vendor')]
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(name, '1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consent', action='store_true', help='Authorize the bounded microphone test')
    parser.add_argument('--seconds', type=int, default=20, choices=range(5, 121), metavar='5..120')
    parser.add_argument('--data-root', type=Path, required=True, help='Fresh private evidence directory outside the app')
    parser.add_argument('--config', type=Path, required=True, help='Existing external live_config.json')
    parser.add_argument('--recipe', choices=('fast', 'balanced', 'patient'), default='balanced')
    parser.add_argument('--mode', choices=('caption_only', 'anonymous_conversation'), default='anonymous_conversation')
    args = parser.parse_args()
    if not args.consent:
        parser.error('--consent is required before opening the microphone')
    data = args.data_root.resolve()
    if data == ROOT or ROOT in data.parents or data.exists():
        parser.error('Choose a fresh private data directory outside the application')
    from app.controller import Controller
    from app.paths import default_models_root, atomic_json
    data.mkdir(parents=True)
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    atomic_json(data/'live_config.json', config)
    controller = Controller(data, default_models_root())
    result = {'utc': datetime.now(timezone.utc).isoformat(), 'requested_seconds': args.seconds,
              'scope': 'Real microphone and native inference; no saved WAV, enrollment, or accuracy claim',
              'recipe': args.recipe, 'mode': args.mode}
    live = None
    try:
        controller.switch(recipe=args.recipe, mode=args.mode)
        controller.commands.join()
        if controller.error:
            raise RuntimeError(controller.error)
        controller.start_live(consent=True)
        controller.commands.join()
        if controller.error or controller.state != 'RUNNING':
            raise RuntimeError(controller.error or controller.state)
        source = controller.engine._source
        live = source.live
        deadline = time.monotonic() + args.seconds + 15
        while source.sent/16000 < args.seconds and time.monotonic() < deadline:
            if controller.state != 'RUNNING' or controller.engine.state == 'FAILED':
                raise RuntimeError(controller.error or source.error or 'Native engine failed')
            time.sleep(.1)
        result['delivered_seconds'] = source.sent/16000
        result['beam_diagnostics_before_stop'] = controller.snapshot()['beam_diagnostics']
        result['source_clock'] = getattr(source, 'clock_metadata', None)
        controller.stop(); controller.commands.join()
        result['source_error'] = source.error
        result['capture_integrity'] = source.integrity
        result['model_cache'] = controller.metrics.get('model_cache')
        result['native_state'] = controller.metrics.get('last_state')
        result['native_telemetry'] = controller.metrics.get('last_telemetry')
        result['error'] = controller.error
        result['status'] = ('PASS' if result['delivered_seconds'] >= args.seconds
            and not source.error and source.integrity and source.integrity['ok']
            and result['native_state'] == 'COMPLETED' and not controller.error else 'FAIL')
    except Exception as exc:
        result.update(status='FAIL', error=str(exc))
    finally:
        controller.close(); controller.commands.join(); controller.worker.join(15)
        result['closed'] = controller.closed
        result['microphone_finished'] = live.status()['finished'] if live else None
        if not controller.closed:
            result.update(status='FAIL', cleanup_error=controller.error)
        atomic_json(data/'LIVE_CHECK.json', result)
    print(json.dumps({key: result.get(key) for key in
        ('status', 'delivered_seconds', 'native_state', 'error', 'closed', 'microphone_finished')}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
