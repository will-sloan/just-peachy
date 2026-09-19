"""Only diagnostic dual-spool evidence fixtures; see README_S6D_BEAM_DIAGNOSTIC_V2.md."""
import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts and not out.exists();out.mkdir(parents=True)
    sys.path.insert(0,str(a.source_root));N=module(a.source_root/'s6d_beam_native_run_diagnostic_v2.py','s6d_beam_native_run_diagnostic_v2');Q=module(a.source_root/'s6d_beam_queue_prepare_diagnostic_v2.py','diagnostic_queue_test')
    R=Path('C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S6D/20260913T195357Z')
    parent=R/'application/beam_execution_predecl_v3/helpers/s6d_beam_native_run_v1.py';old=module(parent,'old_beam_frozen');assert N.bind(parent)['sha256']=='6f7162900dbf19ff1876c5bbb09720a16081d1a330319ac8cc6e1f6ef61dfbb4'
    # Reuse only the existing pure good() dictionary constructor; no original test suite.
    checks=parent.with_name('s6d_beam_execution_checks_v1.py');tree=ast.parse(checks.read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Checks');good=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='good');ns={'deepcopy':deepcopy};exec(compile(ast.Module(body=[good],type_ignores=[]),str(checks),'exec'),ns)
    raw=bytes(range(128))*250;source=out/'declared_source.fixture';source.write_bytes(raw);audio=N.bind(source);pcmsha=hashlib.sha256(raw).hexdigest();rows=[];counter=0
    def case():
        nonlocal counter
        counter+=1;session=out/f'session{counter:02d}';session.mkdir();(session/'audio_spool.pcm16').write_bytes(raw);(session/'identity_audio_spool.pcm16').write_bytes(raw)
        args=list(ns['good'](None));job=args[1];proof=dict(audio=audio,frames=16000,bytes=32000,sha256=pcmsha,gain=1.0)
        job.update(mode='stream_diagnostic',asr_raw_stream='focus0_asr_raw',stream_proofs={'focus0_asr_raw':proof},expected_identity_frames=16000,audio=audio,audio_pcm_sha256=pcmsha)
        args[0]['session_dir']=str(session);args[4]={'focus0_asr_raw':N.bind(session/'audio_spool.pcm16')};pair=N.diagnostic_pair_proof(job,session)
        return args,pair,session
    def check(name,fn):
        try:fn();rows.append(dict(name=name,status='PASS'))
        except BaseException:rows.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(fn):
        try:fn()
        except (ValueError,KeyError,TypeError,FileNotFoundError):return
        raise AssertionError('Expected rejection')
    def equal(a,b):assert a==b,(a,b)
    def old_gap():
        args,pair,session=case();(session/'identity_audio_spool.pcm16').unlink()
        equal(old.validate_multistream(*args),[]);assert N.validate_multistream(*args)
        N.save(out/'OLD_ADVERSE_OBSERVATION.json',dict(old_accepts_with_identity_spool_absent=True,new_missing_pair_rejected=True,source=N.bind(parent),no_native_job=True))
    check('old_frozen_diagnostic_accepts_unverified_absent_identity_spool',old_gap)
    def positive():
        args,pair,session=case();equal(N.validate_multistream(*args,pair),[])
        equal(N.validate_diagnostic_source(args[1],{'streams':[dict(name=args[1]['asr_raw_stream'],audio=audio)]}),args[1]['stream_proofs'][args[1]['asr_raw_stream']])
    check('both_actual_fixture_spool_hashes_full_source_positive',positive)
    def file_damage(kind):
        args,pair,session=case();path=session/'identity_audio_spool.pcm16'
        if kind=='missing':path.unlink();reject(lambda:N.diagnostic_pair_proof(args[1],session));return
        path.write_bytes(raw[:-2] if kind=='truncated' else bytes([255])+raw[1:]);pair=N.diagnostic_pair_proof(args[1],session);assert N.validate_multistream(*args,pair)
    for name in ['missing','truncated','changed_same_length']:check(name+'_identity_spool_rejected',lambda name=name:file_damage(name))
    def foreign():
        args,pair,session=case();other=out/'foreign_identity.pcm16';other.write_bytes(raw);pair['identity']=N.bind(other);assert N.validate_multistream(*args,pair)
    check('foreign_session_same_bytes_identity_rejected',foreign)
    def pair_change(field,value):
        args,pair,session=case();pair[field]=value;assert N.validate_multistream(*args,pair)
    check('foreign_stream_label_rejected',lambda:pair_change('stream_name','focus1_asr_raw'))
    check('foreign_source_binding_rejected',lambda:pair_change('source_audio',dict(audio,sha256='f'*64)))
    check('changed_source_pcm_declaration_rejected',lambda:pair_change('source_pcm_sha256','f'*64))
    def source_change(field,value):
        args,pair,session=case();args[1][field]=value;reject(lambda:N.validate_diagnostic_source(args[1],{'streams':[dict(name=args[1]['asr_raw_stream'],audio=audio)]}))
    check('actual_start_file_foreign_audio_rejected_pre_model',lambda:source_change('audio',dict(audio,path=str(out/'other.fixture'))))
    check('expected_identity_prefix_rejected_pre_model',lambda:source_change('expected_identity_frames',15999))
    def completion_change(kind):
        args,pair,session=case()
        if kind=='dispatch':args[5]['frames']=15999
        elif kind=='drain':args[3]['full_event_consumer_drained']=False
        else:args[2]['identity_samples']=15999
        assert N.validate_multistream(*args,pair)
    for name in ['dispatch','drain','finalizer']:check('dual_spools_do_not_bypass_'+name,lambda name=name:completion_change(name))
    def queue_gate():
        args,pair,session=case();fields=Q.diagnostic_expected_fields(args[1]);equal(fields['diagnostic_pair.identity.sha256'],pcmsha);equal(fields['diagnostic_pair.identity.bytes'],32000);equal(fields['diagnostic_pair.asr.sha256'],pcmsha);equal(fields['diagnostic_pair.source_audio.path'],audio['path'])
    check('literal_queue_requires_both_spools_and_source',queue_gate)
    def preserved():
        equal(N.PINS,old.PINS)
        def node(path,name):return ast.dump(next(x for x in ast.parse(path.read_text()).body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name==name),include_attributes=False)
        for name in ['journal_representation','validate_original_identity','CalibrationProbe']:equal(node(parent,name),node(a.source_root/'s6d_beam_native_run_diagnostic_v2.py',name))
        oldrun=next(x for x in ast.parse(parent.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='run');newrun=next(x for x in ast.parse((a.source_root/'s6d_beam_native_run_diagnostic_v2.py').read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='run')
        for typename in ['Instrumented']:
            equal([ast.dump(x,include_attributes=False) for x in ast.walk(oldrun) if isinstance(x,ast.ClassDef) and x.name==typename],[ast.dump(x,include_attributes=False) for x in ast.walk(newrun) if isinstance(x,ast.ClassDef) and x.name==typename])
        for fun in ['execute_cell','start_file']:
            equal([ast.dump(x,include_attributes=False) for x in ast.walk(oldrun) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr==fun],[ast.dump(x,include_attributes=False) for x in ast.walk(newrun) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr==fun])
    check('scientific_engine_native_loop_and_old_C_core_pins_unchanged',preserved)
    result=dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',fixture_only=True,tests=rows,passed=sum(x['status']=='PASS' for x in rows),total=len(rows),sources=[N.bind(a.source_root/n) for n in ['s6d_beam_native_run_diagnostic_v2.py','s6d_beam_queue_prepare_diagnostic_v2.py','s6d_beam_diagnostic_checks_v2.py','README_S6D_BEAM_DIAGNOSTIC_V2.md']],parent=N.bind(parent),actual_models=0,actual_audio_sessions=0,actual_process_queries=0,hardware=0,queue_or_approval_created=False,scope='Only tiny deterministic PCM byte fixtures and extracted existing pure completion constructor. No production waveform, native inference or original three-beam suite rerun.')
    N.save(out/'RECEIPT.json',result);print(json.dumps(result,indent=2));return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
