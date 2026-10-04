"""Host-only allocation/phase regressions; README_BACKUP_RECONCILER_V3.md."""
import json
from pathlib import Path
import tempfile
import unittest

import reconcile_production_backup_external_v3 as target


class ReconcilerTests(unittest.TestCase):
    def test_exact_large_file_empty_file_and_seeded_phase_count(self):
        rows = [dict(path=name, identity=dict(bytes=size)) for name, size in
                [('large', 64782446), ('empty', 0), ('one', 1048576), ('seeded', 10**9)]]
        plan = [dict(path=row['path'], seed='verified-local' if row['path']=='seeded' else None)
                for row in rows]
        result = target.transfer_plan(rows, plan)
        self.assertEqual(result['transfer_phases'], 62 + 1 + 1)
        self.assertEqual(result['missing_transfer_bytes'], 64782446 + 1048576)
        self.assertEqual(result['segment_bytes'], 1048576)
        changed = [dict(row) for row in plan]
        changed[0]['path'] = 'other'
        with self.assertRaisesRegex(ValueError, 'ordering'):
            target.transfer_plan(rows, changed)

    def test_one_total_preparation_budget_preserves_final_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'REGISTERED_OWNER.json').write_text('{"pid":1}')
            ledger = target.PreparationBudget(root)
            # A preparation phase may use room beyond the old 4 MiB partition,
            # while independently reserving the complete final manifests.
            for i in range(25):
                phase = root/('snapshot-%04d' % i); phase.mkdir()
                (phase/'STATUS.json').write_bytes(b'x' * 200000)
                ledger.charge_phase(phase)
            self.assertEqual(ledger.used, 5000000 + len('{"pid":1}'))
            ledger.used = target.PREPARATION_BYTES - ledger.held - 10
            with self.assertRaisesRegex(ValueError, '16 MiB'):
                ledger.write(root/'REFUSED.json', b'x'*11)
            self.assertFalse((root/'REFUSED.json').exists())
            ledger.held = 0
            ledger.write(root/'COMPLETE.json', b'{}')
            self.assertEqual((root/'COMPLETE.json').read_bytes(), b'{}')

    def test_snapshot_receipts_keep_independent_owner_and_finite_phase_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = target.PreparationBudget(root)
            phase = root/'snapshot-0001'; phase.mkdir()
            (phase/'NATIVE_OWNER.json').write_text(json.dumps(dict(pid=1, start_ticks=2, boot_id='fixture')))
            (phase/'STATUS.json').write_bytes(b'x' * target.PHASE_BYTES)
            with self.assertRaisesRegex(ValueError, 'Per-phase'):
                ledger.charge_phase(phase)
            self.assertEqual(ledger.used, 0)
            (phase/'STATUS.json').unlink()
            (phase/'nested').mkdir()
            with self.assertRaisesRegex(ValueError, 'membership'):
                ledger.charge_phase(phase)


if __name__ == '__main__': unittest.main()
