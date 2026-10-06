"""Bounded current build21 startup/source diagnostics; see README.md."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

DATA = Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PACKAGE = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-21')
PIN = '9abaaaffe35d328fd97f5fc47f1f5b938803705dffb728c5d804d225a646ba6e'


def inspect(payload, baseline):
    if payload != {'package_manifest_sha256': PIN}:
        raise ValueError('Exact build21 read-only diagnostic payload required')
    if hashlib.sha256((PACKAGE/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest() != PIN:
        raise ValueError('Current package manifest changed')
    rows = []
    consumed = 0
    returned = 0

    def retain(path, tail=6144):
        nonlocal consumed, returned
        if not path.exists():
            return None
        before = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_size > 4*1024**2:
            raise ValueError('Bounded regular diagnostic required: '+str(path))
        consumed += before.st_size
        if consumed > 32*1024**2 or len(rows) >= 64:
            raise ValueError('Finite diagnostic inventory exceeded')
        raw = path.read_bytes()
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError('Diagnostic changed during read')
        kept = raw[-tail:]
        returned += len(kept)
        if returned > 131072:
            raise ValueError('Private diagnostic response bound')
        row = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                   returned_tail_bytes=len(kept), truncated=len(raw)>len(kept),
                   text=kept.decode('utf-8', 'replace'))
        rows.append(row)
        return raw

    for name in ('PORTRAIT_SETTINGS.json', 'APPLICATION_redimnet.json', 'APPLICATION_titanet.json',
                 'CURRENT_LAUNCH.json'):
        retain(DATA/name, 4096)
    for group, limit in (('unit-owners', 4), ('launches', 3)):
        directory = DATA/group
        choices = []
        if directory.exists():
            for index, path in enumerate(directory.iterdir(), 1):
                if index > 4096:
                    raise ValueError('Bounded owner/launch directory count')
                if re.fullmatch('[0-9a-f]{32}', path.name) and path.is_dir() and not path.is_symlink():
                    choices.append(path)
        for path in sorted(choices, key=lambda p:p.stat().st_mtime_ns, reverse=True)[:limit]:
            if group == 'unit-owners':
                for name in ('UNIT_OWNERSHIP.json', 'SERVICE_EXIT.json', 'UNIT_CLOSURE.json', 'service.log'):
                    retain(path/name, 6144 if name.endswith('.log') else 4096)
            else:
                for name in ('REQUEST.json', 'CLOSED.json', 'START_FAILURE.json', 'WORKER.log', 'worker/EXIT.json'):
                    retain(path/name, 6144 if name.endswith('.log') else 4096)
                session_raw = retain(path/'worker/SESSION.json', 2048)
                if session_raw:
                    identifier = json.loads(session_raw)['session_id']
                    if re.fullmatch('[0-9a-f]{32}', identifier) is None:
                        raise ValueError('Exact session UUID required')
                    session = DATA/'recordings/sessions'/identifier
                    for name in ('metadata.json', 'work/source/SOURCE_CLOSE.json', 'work/RESULT.json'):
                        retain(session/name, 8192 if name.endswith('SOURCE_CLOSE.json') else 4096)
    return dict(status='CURRENT_BUILD21_DIAGNOSTICS_READ', boot_id=baseline['boot_id'],
                owner=baseline.get('owner'), native_payload_writes=False, models_started=False,
                capture_started=False, consumed_bytes=consumed, returned_bytes=returned, records=rows)


if 'PAYLOAD' in globals():
    RESULT = inspect(PAYLOAD, BASELINE)
