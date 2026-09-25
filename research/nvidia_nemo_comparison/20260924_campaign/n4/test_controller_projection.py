"""Actual Controller display-consumer checks. README_CONTROLLER_PROJECTION.md."""
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from common import load,verify
from controller_projection import project_mode_result,forbid_inference,validate_display_history,ObservedDrainQueue


def read_replay(binding):
    verify(binding['compressed'])
    with gzip.open(binding['compressed']['path'],'rb') as stream:raw=stream.read(32*1024**2+1)
    if len(raw)!=binding['expanded_bytes'] or hashlib.sha256(raw).hexdigest()!=binding['expanded_sha256']:
        raise ValueError('Mode replay expanded hash/size mismatch')
    return json.loads(raw)


class TestControllerProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local=Path(os.environ.get('JP_N4_LOCAL',r'G:\Just_Peachy_N1\20260924_campaign\local\n4'))
        cls.receipt=load(cls.local/'component-modes-probe-v1/RESULT.json')
        verify(cls.receipt['source_receipt']);source=Path(load(cls.receipt['source_receipt']['path'])['prototype'])
        sys.path[:0]=[str(source),str(source/'vendor')]
        cls.catalog=load(cls.local/'catalog-check-v3/RESULT.json')
        cls.runtimes={Path(b['path']).name:b for b in cls.catalog['inputs']}

    def parent(self,backend='baseline',mode='selected_closed'):
        entry=next(r for r in self.receipt['checks'] if r['backend']==backend and r['mode']==mode)
        for b in entry['inputs']:verify(b)
        tap=load(entry['inputs'][0]['path'])['job']['tap']
        return read_replay(entry['output']),tap

    def project(self,replay,tap):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        with forbid_inference():
            return project_mode_result(replay,tap=tap,preparation=self.receipt['gallery_preparation'],
                n2_runtime=self.runtimes['n2_runtime.json'],n3_runtime=self.runtimes['n3_runtime.json'],
                data_root=Path(tmp.name)/'controller')

    def test_baseline_closed_actual_consumer_and_projection_keep_assumptions(self):
        replay,tap=self.parent();result=self.project(replay,tap)
        self.assertEqual(result['display_inputs'],len(replay['display_events']))
        self.assertEqual(len(result['history']),result['display_inputs'])
        self.assertTrue(any(r['identity_assignment']=='closed_assumed' and r['label'].endswith(' · assumed') for r in result['final_rows']))
        self.assertTrue(result['controller_closed']);self.assertFalse(result['consumer_thread_alive'])
        self.assertFalse(any(result['model_loads'].values()));self.assertEqual(result['integrated_N4_cells'],0)

    def test_n2_d1_closed_native_assumptions_are_not_recognition(self):
        replay,tap=self.parent('nemotron_hybrid');result=self.project(replay,tap)
        assumed=[r for h in result['history'] for r in h['rows'] if r['closed_display_assignment']]
        self.assertTrue(assumed)
        self.assertTrue(all(r['profile_id'] is None and r['display_profile_id'] is not None for r in assumed))
        self.assertTrue(all(r['label'].endswith(' · assumed') for r in assumed))
        self.assertFalse(result['upstream_publication_parity'])

    def test_enrolled_unknown_and_numbered_modes_follow_actual_projection(self):
        # Same frozen source/model with different downstream mode; no Q truth.
        for mode in ('enrolled_names','open_with_names','selected_focus'):
            replay,tap=self.parent('compact_eou',mode);result=self.project(replay,tap)
            rows=[r for h in result['history'] for r in h['rows']]
            self.assertTrue(rows);self.assertTrue(all(r['profile_id'] is None for r in rows))
            if mode=='enrolled_names':self.assertTrue(all(r['label']=='Unknown' for r in rows))
            else:
                # Source snapshot() uses anonymous fallback for selected_focus too.
                # Preserve this product behavior even though metadata says one Unknown.
                self.assertTrue(any(str(r['label']).startswith('Speaker') for r in rows))

    def test_raw_and_formatted_tokens_survive_actual_controller(self):
        replay,tap=self.parent('n4_a2_d1_e1','enrolled_names');result=self.project(replay,tap)
        latest={r['published_row']['caption_key']:r['published_row']['text'] for r in replay['display_events']}
        actual={}
        for r in result['final_rows']:actual.setdefault(r['caption_key'],[]).append(r['raw_asr_text'])
        self.assertEqual({k:''.join(v) for k,v in actual.items()},latest)
        self.assertTrue(all(r['visible'] for r in result['final_rows']))

    def test_display_clock_foreign_session_and_word_loss_fail_before_controller(self):
        original,_=self.parent()
        for mutate in (lambda r:r['display_events'][-1].update(modeled_at_sec=-1),
                       lambda r:r['display_events'][-1]['published_row'].update(session_id='other'),
                       lambda r:r['display_events'][0]['published_row'].update(text='lost')):
            r=deepcopy(original);mutate(r)
            with self.assertRaises(ValueError):validate_display_history(r)

    def test_changed_catalog_mode_contract_is_rejected(self):
        replay,tap=self.parent();replay['contract']['uses_n2']=True
        with self.assertRaisesRegex(ValueError,'catalog/mode'):self.project(replay,tap)

    def test_queue_observer_runs_after_delivery_and_exactly_once(self):
        seen=[];q=ObservedDrainQueue(lambda value,index:seen.append((value,index)),maximum=2)
        q.put_nowait('one');q.put_nowait('two')
        self.assertEqual(q.get(block=False),'one');self.assertEqual(seen,[])
        self.assertEqual(q.get(block=False),'two');self.assertEqual(seen,[('one',0)])
        import queue
        with self.assertRaises(queue.Empty):q.get(block=False)
        with self.assertRaises(queue.Empty):q.get(block=False)
        self.assertEqual(seen,[('one',0),('two',1)]);self.assertEqual(q.observed,2)

    def test_cleanup_releases_actual_controller_thread_and_owner(self):
        names={'proto-controller','proto-caption-consumer','n4-sealed-display-input'}
        before={t.ident for t in threading.enumerate() if t.name in names}
        replay,tap=self.parent('titanet','anonymous_conversation');result=self.project(replay,tap)
        self.assertEqual(before,{t.ident for t in threading.enumerate() if t.name in names})
        self.assertTrue(all(r['status']=='DISABLED_SAVED_AUDIO_ONLY' for r in result['output_defaults']))


if __name__=='__main__':unittest.main()
