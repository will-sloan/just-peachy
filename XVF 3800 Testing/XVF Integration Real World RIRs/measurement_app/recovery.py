"""Idle-only USB24 recovery. Uses the same hardware lease as every capture."""
import re
import subprocess
import threading
from datetime import datetime, timezone
from .core import HOST, CREATE_NO_WINDOW, Control, write_json, freeze


def probe_usb_width():
    """Read-only probe; normal idle polling does not create capture folders."""
    p = subprocess.run([str(HOST), '-u', 'usb', 'USB_BIT_DEPTH'], cwd=HOST.parent,
                       capture_output=True, timeout=5, creationflags=CREATE_NO_WINDOW)
    out = p.stdout.decode('utf-8-sig', errors='replace')
    err = p.stderr.decode('utf-8-sig', errors='replace')
    if p.returncode or err.strip():
        raise RuntimeError((err or out).strip() or 'USB probe failed')
    matches = re.findall(r'^USB_BIT_DEPTH\s+(16|24)\s+(16|24)\s*$', out, re.M)
    if len(matches) != 1:
        raise RuntimeError('Invalid USB_BIT_DEPTH reply: ' + out[:300])
    return list(map(int, matches[0]))


class RecoveryMonitor:
    def __init__(self, runs, claim, release, publish, refresh_audio, *,
                 probe=probe_usb_width, control=Control, seal=freeze, interval=5):
        self.runs, self.claim, self.release = runs, claim, release
        self.publish, self.refresh_audio = publish, refresh_audio
        self.probe, self.control, self.seal = probe, control, seal
        self.interval = interval
        self.stop = threading.Event()
        self.thread = None
        self.ready = False
        self.generation = 0
        self.inventory = []
        self.failures = 0

    def emit(self, state, message, **extra):
        self.publish({'enabled': True, 'state': state, 'ready': self.ready,
                      'generation': self.generation, 'message': message,
                      'checked_utc': datetime.now(timezone.utc).isoformat(), **extra})

    def request_check(self):
        self.ready = False
        self.emit('checking', 'Checking the XVF connection before another take.')

    def recover(self):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        folder = self.runs / ('AUTO_USB24_' + stamp)
        folder.mkdir(parents=True)
        reboot_requested = False
        try:
            c = self.control(folder / 'commands')
            before = c.identify()  # Rejects a different firmware/array or injection mode.
            write_json(folder / 'before.json', before)
            if before['AUDIO_MGR_MIC_GAIN'] != [10] or before['AUDIO_MGR_SYS_DELAY'] != [-32]:
                raise RuntimeError('Campaign gain/delay mismatch; automatic USB repair will not change an intentional DSP configuration.')
            if self.stop.is_set():
                raise RuntimeError('Recorder shutdown interrupted USB recovery')
            if before['USB_BIT_DEPTH'] != [24, 24]:
                (folder / 'before_params.txt').write_text(c.query('--dump-params'), encoding='utf-8')
                self.emit('recovering', 'Restoring USB24. Waiting for the XVF to restart…')
                reboot_requested = True
                c.query('USB_BIT_DEPTH', 24, 24)
                if self.stop.wait(4):
                    raise RuntimeError('Recorder shutdown interrupted USB recovery')
                for name in ('AUDIO_MGR_MIC_GAIN', 'AUDIO_MGR_REF_GAIN', 'AUDIO_MGR_SYS_DELAY'):
                    c.set(name, before[name])
            after = c.identify()
            write_json(folder / 'after.json', after)
            if (after['USB_BIT_DEPTH'] != [24, 24] or after['AUDIO_MGR_MIC_GAIN'] != [10]
                    or after['AUDIO_MGR_SYS_DELAY'] != [-32]):
                raise RuntimeError('USB24 / campaign gain-delay verification failed')
            # Called only while holding the capture lease, with no live writers.
            inventory = self.refresh_audio()
            self.inventory = inventory
            write_json(folder / 'result.json', {'status': 'PASS', 'reboot_requested': reboot_requested,
                       'flash_written': False, 'other_runtime_settings_reset_to_defaults': reboot_requested,
                       'audio_inventory': inventory, 'automatic_capture_started': False})
            self.seal(folder)
            return after, str(folder)
        except Exception as error:
            if not (folder / 'SHA256SUMS.txt').exists():
                write_json(folder / 'recovery_error.json', {'error': str(error),
                           'reboot_requested': reboot_requested, 'automatic_capture_started': False})
                self.seal(folder)
            raise

    def tick(self):
        try:
            self.claim()
        except RuntimeError:
            return  # Active capture, retained writer lease, or another app owns it.
        try:
            if self.stop.is_set():
                return
            width = self.probe()
            if self.ready and width == [24, 24]:
                return
            self.ready = False
            self.emit('recovering', 'Checking the XVF and refreshing audio devices…')
            identity, evidence = self.recover()
            self.ready = True
            self.failures = 0
            self.generation += 1
            self.emit('ready', 'XVF ready: USB24 verified. Failed takes remain saved; press Play & record to retry.',
                      identity=identity, evidence_directory=evidence)
        except Exception as error:
            self.ready = False
            self.failures += 1
            self.emit('waiting', 'XVF unavailable or not ready. Reconnect its USB cable; automatic recovery will retry.',
                      error=str(error)[:1500])
        finally:
            self.release()

    def start(self):
        self.emit('checking', 'Automatic USB recovery: checking the XVF…')
        def run():
            while not self.stop.is_set():
                self.tick()
                self.stop.wait(min(30, self.interval * max(1, self.failures)))
        self.thread = threading.Thread(target=run, name='xvf-idle-recovery', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(15)
