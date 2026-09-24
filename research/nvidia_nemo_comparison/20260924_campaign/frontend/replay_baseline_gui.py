"""Audit saved baseline final snapshots through the frozen shared Tk frontend.

Only private-desktop rendering, no inference or audio. See README.md.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest


MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.frontend.replay_baseline_gui'
SCOPE = 'FINAL_SNAPSHOT render through frozen common UI after inference; not live/source-paced GUI latency or physical scanout'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def atomic(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def verified_inputs(source, index_path, allow_partial):
    source, index_path = Path(source).resolve(strict=True), Path(index_path).resolve(strict=True)
    admission = load(index_path.parent/'ADMISSION.json')
    index = load(index_path)
    if index['contract_sha256'] != admission['contract_sha256']:
        raise ValueError('Result index/admission contract mismatch')
    if not allow_partial and (index['status'] != 'COMPLETE' or len(index['completed']) != index['total'] or index['failed']):
        raise ValueError('Final replay requires a complete result index; use --allow-partial only for explicit smoke evidence')
    source_bindings = admission['contract']['source_bindings']
    for relative, expected in source_bindings.items():
        file = (source/relative).resolve(strict=True)
        if not file.is_relative_to(source) or digest(file) != expected:
            raise ValueError('Frozen source binding changed: '+relative)
    jobs = []
    for identifier, result_path in sorted(index['completed'].items()):
        if not identifier or any(not (c.isalnum() or c in '_-') for c in identifier):
            raise ValueError('Unsafe result identifier')
        result_path = Path(result_path).resolve(strict=True)
        checkpoint = load(result_path.parent.parent/'CHECKPOINT.json')
        if Path(checkpoint['result']['path']).resolve() != result_path or digest(result_path) != checkpoint['result']['sha256']:
            raise ValueError('Checkpoint result binding mismatch: '+identifier)
        result = load(result_path)
        if result['status'] != 'COMPLETE' or result['job_id'] != identifier:
            raise ValueError('Incomplete or mismatched result: '+identifier)
        snapshot_path = result_path.parent/'FINAL_SNAPSHOT.json'
        bound = next((entry for entry in result['evidence'] if Path(entry['path']).resolve() == snapshot_path),None)
        if not bound or digest(snapshot_path) != bound['sha256']:
            raise ValueError('Final snapshot hash mismatch: '+identifier)
        jobs.append(dict(job_id=identifier,snapshot=str(snapshot_path),snapshot_sha256=bound['sha256'],
                         result=str(result_path),result_sha256=digest(result_path)))
    return index, admission, jobs


class SnapshotController:
    """Detached final snapshots only. No start/capture/model methods exist."""
    def __init__(self, snapshot):
        self.data = deepcopy(snapshot)
        self.data['status'] = 'SAVED FINAL SNAPSHOT · GUI replay only'
        self.receipts = []
    def snapshot(self): return deepcopy(self.data)
    def record_presentation(self, receipt): self.receipts.append(deepcopy(receipt))
    def close(self): self.data['state'] = 'CLOSED'


class SavedSnapshotReplayTests(unittest.TestCase):
    def test_saved_final_snapshots(self):
        if not os.environ.get('N1_REPLAY_SOURCE'):
            self.skipTest('Use this script CLI with explicit frozen source and result index')
        from prototype.tests.run_private_desktop import desktop_name, setup_api
        import ctypes
        user32 = setup_api()
        desktop = desktop_name(user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId()))
        self.assertTrue(desktop.startswith('codex-n1-'), 'Refuse GUI replay on input desktop')
        source = Path(os.environ['N1_REPLAY_SOURCE']).resolve(strict=True)
        index_path = Path(os.environ['N1_REPLAY_INDEX']).resolve(strict=True)
        output = Path(os.environ['N1_REPLAY_OUTPUT']).resolve()
        allow_partial = os.environ.get('N1_REPLAY_ALLOW_PARTIAL') == '1'
        index, admission, jobs = verified_inputs(source,index_path,allow_partial)
        sys.path[:0] = [str(source),str(source/'vendor')]
        # The application module must come from the pinned release, independently
        # of the test launcher/helper package in the development worktree.
        from app.ui import PrototypeUI, prepare_dpi_awareness
        import app.ui as frozen_ui
        self.assertEqual(Path(frozen_ui.__file__).resolve(),source/'app'/'ui.py')
        import tkinter as tk
        spec = importlib.util.spec_from_file_location('_n1_capture_helper',source/'tests'/'test_n1_capture.py')
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        prepare_dpi_awareness()
        report = dict(schema='n1-frozen-final-snapshot-gui-replay.v1',scope=SCOPE,
            source=str(source),source_binding_count=len(admission['contract']['source_bindings']),
            contract_sha256=admission['contract_sha256'],index_path=str(index_path),index_sha256=digest(index_path),
            total_expected=index['total'],completed_input_count=len(jobs),allow_partial=allow_partial,
            capture_helper_sha256=digest(source/'tests'/'test_n1_capture.py'),
            private_desktop=desktop,started_utc=datetime.now(timezone.utc).isoformat(),cells=[],status='RUNNING')
        screenshots = {round(i*(len(jobs)-1)/min(5,len(jobs)-1)) for i in range(min(6,len(jobs)))} if len(jobs)>1 else {0}
        for position, job in enumerate(jobs):
            root = ui = None
            cell = dict(job,scope=SCOPE,status='FAILED')
            cell_root = output/'cells'/job['job_id']; cell_root.mkdir(parents=True,exist_ok=True)
            try:
                snapshot = load(job['snapshot'])
                # All modes retain full rows; baseline anonymous mode is unfiltered.
                self.assertFalse(snapshot.get('strict'), 'Unexpected filtered comparative snapshot')
                controller = SnapshotController(snapshot)
                root = tk.Tk(); ui = PrototypeUI(root,controller,allow_auto_start=False)
                root.update()
                # Allow the existing 1.2s pending-name bound plus one 80ms poll
                # to settle using real elapsed time; this is replay display time.
                end = time.monotonic()+1.3
                while time.monotonic()<end:
                    root.update(); time.sleep(.01)
                ui.poll(); root.update()
                self.assertEqual((root.winfo_width(),root.winfo_height()),(480,800))
                self.assertEqual(ui.active_region.winfo_height(),184)
                self.assertGreater(ui.caption_text.winfo_height(),0)
                self.assertEqual(ui.snapshot.get('backend_id'),snapshot.get('backend_id'))
                row_ids = [str(row['id']) for row in snapshot['rows']]
                self.assertEqual(ui._render_order,row_ids)
                spans = []
                for row in snapshot['rows']:
                    rid = str(row['id']); spans.extend(row.get('span_ids') or [rid])
                    expected = ui._display_row(row)[1]
                    start,stop = ui._marks[rid]
                    self.assertIn(expected,ui.caption_text.get(start,stop),'Display text dropped from history storage: '+rid)
                    if rid in ui._active_pane.marks:
                        a,b = ui._active_pane.marks[rid]
                        self.assertIn(expected,ui.active_text.get(a,b),'Display text dropped from active pane: '+rid)
                observed = {span for receipt in controller.receipts for span in receipt['span_ids']}
                self.assertTrue(set(spans).issubset(observed),'Missing GUI receipt for a stable span')
                with (cell_root/'PRESENTATION_RECEIPTS.jsonl').open('w',encoding='utf-8') as stream:
                    for receipt in controller.receipts:
                        stream.write(json.dumps(receipt,ensure_ascii=False,allow_nan=False)+'\n')
                image = helper.render_client(root,cell_root/'FINAL_SNAPSHOT_RENDER.png') if position in screenshots else None
                cell.update(status='COMPLETE',row_count=len(row_ids),stable_span_count=len(set(spans)),
                    gui_receipt_count=len(controller.receipts),logical_client=[480,800],active_height_px=184,
                    minimum_display_settle_seconds=1.3,
                    all_row_display_text_retained=True,all_span_receipts_present=True,
                    screenshot=image,ui_applied_first_labels_scope='Initial application of saved final state, not original online first labels',
                    receipts_sha256=digest(cell_root/'PRESENTATION_RECEIPTS.jsonl'))
            except BaseException as exc:
                cell['error']=type(exc).__name__+': '+str(exc)
            finally:
                if ui is not None:
                    ui.close(); ui.poll()
                elif root is not None:
                    root.destroy()
            atomic(cell_root/'GUI_RENDER_CHECK.json',cell)
            report['cells'].append(cell)
            atomic(output/'GUI_REPLAY_REPORT.json',report)
        # Re-read all hashes after rendering, so a concurrent source edit cannot
        # yield a false frozen-front-end receipt.
        verified_inputs(source,index_path,allow_partial)
        failed = [cell['job_id'] for cell in report['cells'] if cell['status']!='COMPLETE']
        report.update(status='FAILED' if failed else 'PARTIAL' if len(jobs)!=index['total'] else 'COMPLETE',
            failed=failed,rendered=len(report['cells']),finished_utc=datetime.now(timezone.utc).isoformat())
        atomic(output/'GUI_REPLAY_REPORT.json',report)
        self.assertFalse(failed,'Final snapshot GUI failures: '+', '.join(failed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,help='Frozen release prototype directory')
    parser.add_argument('--index',required=True,help='Baseline RESULT_INDEX.json beside ADMISSION.json')
    parser.add_argument('--output',required=True,help='Fresh private evidence directory outside source and Git')
    parser.add_argument('--allow-partial',action='store_true',help='Explicit smoke-only render; report remains PARTIAL')
    parser.add_argument('--timeout-seconds',type=float,default=600)
    args = parser.parse_args()
    source,index,output = Path(args.source).resolve(strict=True),Path(args.index).resolve(strict=True),Path(args.output).resolve()
    if output.is_relative_to(source) or output.exists():
        raise ValueError('Output must be fresh and outside frozen source')
    verified_inputs(source,index,args.allow_partial)
    worktree = Path(__file__).resolve().parents[4]
    environment = dict(os.environ,N1_REPLAY_SOURCE=str(source),N1_REPLAY_INDEX=str(index),
        N1_REPLAY_OUTPUT=str(output),N1_REPLAY_ALLOW_PARTIAL='1' if args.allow_partial else '0')
    command = [sys.executable,'-m','prototype.tests.run_private_desktop','--receipt-dir',str(output),
        '--timeout-seconds',str(args.timeout_seconds),MODULE]
    return subprocess.run(command,cwd=worktree,env=environment,check=False).returncode


if __name__=='__main__': raise SystemExit(main())
