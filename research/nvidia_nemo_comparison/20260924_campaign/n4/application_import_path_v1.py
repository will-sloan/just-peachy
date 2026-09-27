"""Read-only isolated import regression; README_APPLICATION_IMPORT_PATH_V1.md."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys


def binding(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def check(input_path, output, expect_missing):
    value = json.loads(Path(input_path).read_text(encoding='utf-8-sig'))
    output = Path(output).resolve()
    if output.exists() or output.parent != Path(input_path).resolve().parent:
        raise ValueError('Fresh sibling import result required')
    # Match the V5 child branch, without constructing a Controller, GUI or model.
    source = Path(value['prototype']).resolve(strict=True)
    sys.path[:0] = [str(source), str(source/'vendor'), str(source.parent)]
    for item in value['bound_modules']:
        if binding(item['path']) != item: raise ValueError('Bound import input changed')
    import application_closure
    name = application_closure.ARCHIVE_MODULE
    if name != 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui_a1':
        raise ValueError('Archive import target changed')
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if not expect_missing or exc.name != 'research.nvidia_nemo_comparison.20260924_campaign.n3':
            raise
        result = dict(status='EXPECTED_UNSET_PATH_FAILURE_REPRODUCED', missing_module=exc.name,
                      archive_receipts_checked=0)
    else:
        if expect_missing: raise ValueError('Negative import unexpectedly resolved')
        observed = binding(module.__file__)
        if observed != value['archive_module']: raise ValueError('Import resolved a different module')
        if binding(module.IO_HELPER) != value['io_helper']: raise ValueError('Different archive IO helper')
        for case in value['archive_cases']:
            if binding(case['archive']['path']) != case['archive']: raise ValueError('Archive changed')
            receipt = json.loads(Path(case['archive']['path']).read_text(encoding='utf-8-sig'))
            module.validate_archive_integrity(receipt, case['frames'])
        if len(value['archive_cases']) != 9: raise ValueError('Historical archive denominator differs')
        result = dict(status='PASS_EXPLICIT_WORKTREE_PATH_AND_SAVED_ARCHIVE_VALIDATION',
                      archive_module=observed, io_helper=binding(module.IO_HELPER), archive_receipts_checked=9)
    forbidden = [n for n in ('tkinter', 'torch', 'onnxruntime', 'sounddevice', 'app.controller') if n in sys.modules]
    if forbidden: raise ValueError('Import-only regression loaded an application or model runtime')
    result.update(input=binding(input_path), pythonpath=os.environ.get('PYTHONPATH'),
                  interpreter=str(Path(sys.executable).resolve()), cwd=str(Path.cwd()),
                  application_started=False, audio_loaded=False, models_loaded=False, N4_accepted=False)
    with output.open('x', encoding='utf-8') as stream: json.dump(result, stream, indent=2, allow_nan=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--expect-missing', action='store_true')
    args = p.parse_args(); check(args.input, args.output, args.expect_missing)
