"""Continuity input, inference firewall and population tests; model-free."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
import wave

from common import bind, fingerprint, freeze
import continuity_application_plan as subject
from test_paced_panel_plan import selection
import test_paced_panel_plan_v3 as fixture

CONTEXT={}
OUTPUT=None


def panel(candidates=None):
    jobs,short,anchors,catalog,reviews,context,*_=fixture.fixture_context()
    selected=candidates or [subject.original.BASELINE,'A3_D1_E1']
    return subject.panels.build_plan(selection(selected,reviews),reviews,jobs,short,anchors,catalog,context)


def plan(candidates=None):
    return subject.build_plan({'development_fixture':'panel'},panel(candidates),
        CONTEXT['sequence_binding'],CONTEXT['job'])


class ContinuityPlanTests(unittest.TestCase):
    def test_one_full_file_per_selected_candidate(self):
        value=plan();self.assertEqual(value['required'],2)
        self.assertEqual(len(value['rows']),2);self.assertEqual(value['seconds_per_candidate'],1206.7768125)
        self.assertTrue(value['continuity']['initial_reset_only']);self.assertFalse(value['continuity']['reset_at_internal_joins'])
        self.assertFalse(value['stop_restart_included']);self.assertEqual(value['integrated_N4_cells'],0)
        self.assertFalse(value['N4_accepted']);self.assertFalse(value['source_execution_authorized'])

    def test_child_payload_is_exact_existing_allowlist(self):
        value=plan();payload=subject.execution_payload(value,0)
        expected=subject.panels.execution_payload(panel(),0)
        self.assertEqual(set(payload),set(expected));self.assertEqual(len(payload['job']),8)
        for field in set(payload)-{'job','cell_id'}:self.assertEqual(payload[field],expected[field])
        self.assertEqual(payload['job'],CONTEXT['job'])
        for field in ('sequence','continuity','joins','scene_cast','evaluator_truth','selection','reviews','panel','context'):
            self.assertNotIn(field,payload)
        payload['job']['frames']=1;self.assertNotEqual(value['rows'][0]['job']['frames'],1)

    def test_short_plan_is_not_relabelled_into_continuity(self):
        with self.assertRaises(ValueError):subject.execution_payload(panel(),0)
        value=plan()
        with self.assertRaises(ValueError):subject.panels.execution_payload(value,0)
        bad=panel();bad['schema']='n4-paced-panel-plan-v2'
        with self.assertRaises(ValueError):subject.build_plan({},bad,{},CONTEXT['job'])

    def test_short_or_o1_or_reference_bearing_audio_rejected(self):
        for field,value in (('frames',16000),('frames',1301*16000),('tap','O1'),('scene_cast',['actor']),('gain',2.),('reset_between_scenes',False)):
            job=deepcopy(CONTEXT['job']);job[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):subject.build_plan({},panel(),{},job)

    def test_candidate_population_and_contract_fail_closed(self):
        for mutation in ('missing','unselected','candidate','route','inconsistent'):
            p=panel()
            if mutation=='missing':p['rows'].pop()
            if mutation=='candidate':p['candidates'].reverse()
            if mutation=='unselected':p['rows'][0]['composition']='A2_D1_E0'
            if mutation=='route':p['rows'][0]['contract']['variant']='A3'
            if mutation=='inconsistent':p['rows'][0]['contract']['backend_key']='foreign'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):subject.build_plan({},p,{},CONTEXT['job'])

    def test_changes_to_bound_context_input_or_reset_scope_rejected(self):
        for mutation in ('panel','sequence','job','context','policy','kind','repeat','index'):
            p=plan();index=0
            if mutation in ('panel','sequence'):p[mutation]={'different':True}
            if mutation=='job':p['rows'][0]['job']['frames']+=1
            if mutation=='context':p['context']['source_receipt']={'different':True}
            if mutation=='policy':p['continuity']['reset_at_internal_joins']=True
            if mutation=='kind':p['rows'][0]['kind']='timing_repeat'
            if mutation=='repeat':p['rows'][0]['repeat']=1
            if mutation=='index':index=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):subject.execution_payload(p,index)

    def test_all_six_candidates_and_maximum_do_not_drop_baseline(self):
        chosen=[subject.original.BASELINE]+sorted(subject.original.COMPOSITIONS-{subject.original.BASELINE})[:5]
        p=plan(chosen);self.assertEqual(p['required'],6);self.assertEqual(p['candidates'],chosen)
        self.assertEqual(len({r['cache_key'] for r in p['rows']}),6)
        self.assertEqual(sum(subject.execution_payload(p,i)['job']['frames'] for i in range(6)),6*CONTEXT['job']['frames'])
        with self.assertRaises(ValueError):plan(chosen+['A3_D1_E1'])

    def test_production_reconstruction_refuses_partial_review(self):
        # A forged success header cannot substitute for a stopped, qualified
        # source panel preparer and its complete rebuilt score-review chain.
        target=OUTPUT/'partial';target.mkdir()
        freeze(target/'PLAN.json',panel());freeze(target/'ADMISSION.json',dict(owner={'pid':1,'create_time':0},code=[]))
        freeze(target/'RESULT.json',dict(status='PARTIAL',admission=bind(target/'ADMISSION.json')))
        with self.assertRaises(ValueError):subject.reconstruct(target/'PLAN.json')

    def test_prepared_input_proof_reconstructs_exact_full_sequence(self):
        job=subject.validate_input_proof(*deepcopy(CONTEXT['proof']))
        self.assertEqual(job,CONTEXT['job'])

    def test_reference_truth_or_internal_reset_changes_rejected(self):
        for mutation in ('truth','join','offset','identity','frame','code','owner'):
            proof=deepcopy(CONTEXT['proof']);public,q,a,result,sequence,audio,truth,copy,*_=proof
            if mutation=='truth':truth['cells'][0]['scene_cast']=['foreign']
            if mutation=='join':sequence['reset_at_joins']=True
            if mutation=='offset':copy['segments'][2]['index']=1
            if mutation=='identity':audio['jobs'][0]['audio_sha256']='0'*64
            if mutation=='frame':audio['jobs'][0]['frames']-=1
            if mutation=='code':a['code']=[]
            if mutation=='owner':public['exited_preparation_owner']['create_time']+=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):subject.validate_input_proof(*proof)

    def test_preparation_never_confers_execution_acceptance(self):
        for record in (0,3):
            for field in ('actual_application_spawned','actual_source_execution','actual_continuity_test','N4_accepted','integrated_N4_cells'):
                proof=deepcopy(CONTEXT['proof']);proof[record][field]=True if field!='integrated_N4_cells' else 1
                with self.subTest(record=record,field=field),self.assertRaises(ValueError):subject.validate_input_proof(*proof)

    def pcm_fixture(self, name):
        root=OUTPUT/name;root.mkdir();streams=[b'\x01\x00'*64001,b'\xff\x7f'*101]
        def wav(path,data):
            with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(data)
            return bind(path)
        sources=[wav(root/('source'+str(i)+'.wav'),raw) for i,raw in enumerate(streams)]
        output=wav(root/'all.wav',b''.join(streams))
        sequence=dict(frames=sum(len(s)//2 for s in streams),segments=[{},{}])
        copied=dict(output=output,pcm_sha256=hashlib.sha256(b''.join(streams)).hexdigest(),segments=[
            dict(original_waveform=b,frames=len(raw)//2,pcm_sha256=hashlib.sha256(raw).hexdigest()) for b,raw in zip(sources,streams)])
        return sequence,copied

    def test_read_only_pcm_comparison_crosses_chunk_and_segment_boundaries(self):
        sequence,copy=self.pcm_fixture('pcm-valid');before=deepcopy(copy);calls=[]
        subject.verify_pcm(sequence,copy,lambda:calls.append(True))
        self.assertEqual(copy,before);self.assertEqual(len(calls),2)

    def test_changed_pcm_and_copy_digest_cannot_pass(self):
        sequence,copy=self.pcm_fixture('pcm-changed');copy['segments'][1]['pcm_sha256']='0'*64
        with self.assertRaises(ValueError):subject.verify_pcm(sequence,copy)
        sequence,copy=self.pcm_fixture('pcm-bytes');path=Path(copy['output']['path'])
        raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw);copy['output']=bind(path)
        with self.assertRaises(ValueError):subject.verify_pcm(sequence,copy)

    def test_changed_header_and_extra_tail_cannot_pass(self):
        sequence,copy=self.pcm_fixture('pcm-header');sequence['frames']-=1
        with self.assertRaises(ValueError):subject.verify_pcm(sequence,copy)
        sequence,copy=self.pcm_fixture('pcm-tail');copy['segments'][-1]['frames']-=1
        with self.assertRaises(ValueError):subject.verify_pcm(sequence,copy)
