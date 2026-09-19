"""Tiny no-hardware recovery checks; README_S6D_CLOSED_TELEMETRY_RESTORE_V1.md."""
from __future__ import annotations
import argparse
import base64
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import traceback
from unittest.mock import patch


def load(path):
    spec=importlib.util.spec_from_file_location('recovery_under_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper',type=Path,default=Path(__file__).with_name('s6d_closed_telemetry_restore_v1.py'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--actual-native-files-read-only',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if out.drive.casefold()!='g:' or 'review_fixtures' not in out.parts:raise ValueError('Fresh G review_fixtures output required')
    out.mkdir(parents=True,exist_ok=False);m=load(args.helper);results=[]
    def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,allow_nan=False)+'\n',encoding='utf-8');return m.bind(p)
    def fail(call):
        try:call()
        except (ValueError,RuntimeError,KeyError,TypeError):return
        raise AssertionError('Expected fail-closed rejection')
    def check(name,call):
        try:call();results.append(dict(name=name,status='PASS'))
        except BaseException:results.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def lines(p,rows):p.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    def telemetry(label,change=None):
        d=out/label;d.mkdir();samples=[];received=[];transactions=[]
        for i,(name,width) in enumerate(zip(m.FIELDS,m.COUNTS)):
            row=dict(sequence=i,phase='measurement',command=name,values=[0]*width,response_end_monotonic_ns=100+i)
            samples.append(row);received.append(dict(deepcopy(row),parse_ok=True,receipt_sequence=i,host_response_end_monotonic_ns=100+i,host_line_arrival_monotonic_ns=200+i))
            transactions.append('\t'.join(map(str,[i,0,'measurement',i,0,50+i,100+i,0,0,base64.b64encode(bytes(1+4*width)).decode()])))
        native=dict(status='PASS',error=None,cleanup_return=0,pending_reads_at_exit=[False]*14,no_firmware_or_parameter_writes=True,per_field={n:dict(count=1) for n in m.FIELDS},completed_cycles=1,transactions=14,retry_responses=0)
        inspection=dict(process_bits=32,inspection_only_no_device_initialization=True)
        state=dict(native=native,inspection=inspection,samples=samples,received=received,stdout=deepcopy(samples)+[native],transactions=transactions,stderr=b'')
        if change:change(state)
        write(d/'result.json',state['native']);write(d/'inspection.json',state['inspection']);lines(d/'samples.jsonl',state['samples']);lines(d/'stdout.bin',state['stdout']);lines(d/'received.jsonl',state['received']);(d/'stderr.bin').write_bytes(state['stderr'])
        (d/'transactions.tsv').write_text('sequence\tcycle\tphase\tfield_index\tattempt\trequest_start_monotonic_ns\tresponse_end_monotonic_ns\ttransport_return\tdevice_status\traw_response_base64\n'+'\n'.join(state['transactions'])+'\n',encoding='utf-8')
        return {k:m.bind(d/n) for k,n in dict(native_result='result.json',native_inspection='inspection.json',native_samples='samples.jsonl',native_transactions='transactions.tsv',stdout='stdout.bin',received='received.jsonl',stderr='stderr.bin').items()}
    good=telemetry('native_good');closure=m.native_closure(good,14)
    check('native_complete_population',lambda:assert_equal(closure['measurement_rows'],14))
    for name,mutation in [
        ('pending_boolean_zero',lambda s:s['native']['pending_reads_at_exit'].__setitem__(0,0)),
        ('missing_received_row',lambda s:s['received'].pop()),
        ('changed_received_payload',lambda s:s['received'][0]['values'].__setitem__(0,9)),
        ('nonempty_stderr',lambda s:s.update(stderr=b'error')),
        ('missing_stdout_terminal',lambda s:s['stdout'].pop()),
        ('bad_native_transaction_count',lambda s:s['native'].update(transactions=15)),
        ('changed_sample_sequence',lambda s:s['samples'][0].update(sequence=7)),
        ('impossible_received_clock',lambda s:s['received'][0].update(host_line_arrival_monotonic_ns=1)),
    ]:
        refs=telemetry(name,mutation);check(name,lambda refs=refs:fail(lambda:m.native_closure(refs,14)))
    partial=telemetry('partial_line');p=Path(partial['received']['path']);p.write_bytes(p.read_bytes().rstrip(b'\n'));partial['received']=m.bind(p)
    check('partial_final_json_line',lambda:fail(lambda:m.native_closure(partial,14)))
    current=dict(pid=100,creation_time=10.0);known=[dict(role='capture_owner',pid=200,creation_time=20.0),dict(role='supervisor',pid=300,creation_time=30.0)]
    def scan(extra=()):return dict(complete=True,errors=[],observed_unix=1000.0,rows=[dict(current,name='python.exe',cmdline=['python','s6d_closed_telemetry_restore_v1.py']),*extra])
    check('only_exact_current_process_excluded',lambda:m.scan_decision(scan(),known,current))
    check('same_original_owner_blocks',lambda:fail(lambda:m.scan_decision(scan([dict(known[0],name='unrelated.exe',cmdline=[])]),known,current)))
    check('reused_unrelated_original_pid_allowed',lambda:m.scan_decision(scan([dict(pid=200,creation_time=90,name='unrelated.exe',cmdline=['unrelated'])]),known,current))
    check('new_unknown_telemetry_process_blocks',lambda:fail(lambda:m.scan_decision(scan([dict(pid=400,creation_time=90,name='powershell.exe',cmdline=['Run-S6D-Telemetry.ps1'])]),known,current)))
    check('opaque_critical_process_blocks',lambda:fail(lambda:m.scan_decision(scan([dict(pid=400,creation_time=90,name='python.exe',cmdline=None)]),known,current)))
    check('partial_process_census_blocks',lambda:fail(lambda:m.scan_decision(dict(scan(),complete=False),known,current)))
    check('nonfinite_original_creation_blocks',lambda:fail(lambda:m.scan_decision(scan(),[dict(pid=200,creation_time=float('nan'))],current)))
    check('boolean_current_pid_blocks',lambda:fail(lambda:m.scan_decision(scan(),known,dict(pid=True,creation_time=10))))
    initial=dict(identity=dict(VERSION=[3,2,1],AEC_MIC_ARRAY_TYPE=[1],USB_BIT_DEPTH=[16,16],I2S_INPUT_PACKED=[0]),usb_bits=[16,16],settings=dict(PP_AGCGAIN=[1.2],PP_AGCONOFF=[1],STATIC=[7]),observe_only=dict(ANCILLARY=[3]))
    originals=out/'originals';originals.mkdir()
    owner=write(originals/'owner.json',dict(pid=200));restoration=write(originals/'restoration.json',dict(status='FAIL',audio_handles_closed=True,hardware_lease_released=True,telemetry_process_closed=False));initial_ref=write(originals/'initial.json',initial)
    ledger=write(originals/'ledger.json',dict(batches={'bank_v2_P_MAIN6_B1':dict(owner=owner,restoration=restoration)},passes=[]))
    bridge=write(originals/'bridge.json',dict(pid=200,creation_time=20.0));launch=write(originals/'launch.json',dict(pid=300,creation_time=30.0))
    original=dict(owner=owner,restoration=restoration,initial_state=initial_ref,ledger=ledger,bridge_failure=bridge,supervisor_launch=launch)
    def context(label):
        output=out/label
        review=dict(status='PROPOSED_SOURCE_REVIEW_ONLY',allow_fresh_exposed_restore=False,fixture_only=True,owner_thread_id=m.ROOT_THREAD,run_id='20260913T195357Z',original_batch='bank_v2_P_MAIN6_B1',recovery_kind=m.KIND,original_bindings=original,source_bindings=[m.bind(p) for p in m.required_sources()],telemetry_bindings=good,expected_measurement_rows=14,recovery_output_root=str(output))
        ref=write(out/(label+'_PROPOSED_INPUT.json'),review)
        return dict(review=review,review_ref=ref,original=original,values=dict(initial_state=initial),known=known,native_proof=closure,output=output)
    class Fake:
        fixture=True
        def __init__(self,mode=None):self.identity=current;self.mode=mode;self.events=[];self.scans=0;self.owned=False
        def census(self):
            self.events.append('scan');self.scans+=1
            if self.mode=='late_process' and self.scans==3:return scan([dict(pid=400,creation_time=90,name='python.exe',cmdline=['s6d_telemetry.py'])])
            return scan()
        def ports_idle(self):
            self.events.append('ports')
            if self.mode=='port_busy':raise ValueError('Fixture port busy')
            return True
        def acquire(self):
            self.events.append('lock')
            if self.mode=='lock_busy':raise ValueError('Fixture lock busy')
            self.owned=True
        def release(self):
            self.events.append('release')
            if self.mode=='release_failed':raise ValueError('Fixture unlock failure')
            self.owned=False;return True
        def initialize_control(self,p):
            assert self.owned and self.scans==2;self.events.append('initialize')
        def identify(self):
            self.events.append('getter')
            if self.mode=='getter_failed':raise ValueError('Fixture getter failed')
            return deepcopy(initial['identity'])
        def restore(self,expected):
            assert self.owned and self.scans==3 and expected==initial;self.events.append('restore')
            if self.mode=='setter_failed':raise ValueError('Fixture setter failed')
            after=dict(identity=deepcopy(initial['identity']),settings=deepcopy(initial['settings']),observe_only=deepcopy(initial['observe_only']))
            if self.mode=='policy_failed':after['settings']['STATIC']=[8]
            return dict(reset={'fixture':True},reapply=dict(observed=deepcopy(initial['settings']),exact_match=True),readback=after)
    valid=context('valid_orchestration');fake=Fake();receipt_ref=m.recover_prevalidated(valid,fake);receipt=m.read(receipt_ref['path'])
    check('owned_getter_restore_release_order',lambda:assert_equal(fake.events,['scan','ports','lock','scan','ports','initialize','getter','scan','ports','restore','scan','ports','release']))
    check('fixture_cannot_authorize_production',lambda:fail(lambda:m.verify_recovery_record(receipt,owner_binding=owner,restoration_binding=restoration,initial_binding=initial_ref)))
    for mode in ('late_process','port_busy','lock_busy','release_failed','getter_failed','setter_failed','policy_failed'):
        def run_failure(mode=mode):
            c=context(mode);service=Fake(mode);fail(lambda:m.recover_prevalidated(c,service));assert not (c['output']/'RECOVERY.json').exists()
            result=m.read(c['output']/'RESULT.json');assert result['status']=='FAILED_UNRESOLVED' and service.events[-1]=='release'
            if mode in ('port_busy','lock_busy'):assert 'initialize' not in service.events
            if mode in ('late_process','getter_failed'):assert 'restore' not in service.events
            if mode=='release_failed':assert result['hardware_lock_released'] is False
        check(mode+'_never_recovery_pass',run_failure)
    # In-memory file-reader substitution tests the production verifier's joins without
    # writing a fake root acceptance or a nonfixture recovery to disk.
    def verifier_probe(change=None):
        rec=deepcopy(receipt);rec['fixture_only']=False
        measurement=m.read(rec['recovery_measurement']['path']);measurement['fixture_only']=False
        authority=deepcopy(valid['review']);authority.update(status=m.REVIEW_STATUS,allow_fresh_exposed_restore=True)
        if change:change(rec,measurement,authority)
        actual_verify=m.verify
        def reader(ref):
            if ref==receipt['recovery_measurement']:return deepcopy(measurement)
            if ref==receipt['source_review']:return deepcopy(authority)
            return actual_verify(ref)
        with patch.object(m,'verify',reader):return m.verify_recovery_record(rec,owner_binding=owner,restoration_binding=restoration,initial_binding=initial_ref)
    check('production_file_only_join_in_memory',lambda:verifier_probe())
    check('changed_fresh_reapply_rejected',lambda:fail(lambda:verifier_probe(lambda r,z,a:r['reapply'].update(exact_match=False))))
    check('fabricated_historical_receipt_rejected',lambda:fail(lambda:verifier_probe(lambda r,z,a:r.update(historical_python_terminal_receipt_present=True))))
    check('missing_locked_final_scan_rejected',lambda:fail(lambda:verifier_probe(lambda r,z,a:z['process_scans'].pop())))
    check('unaccepted_root_status_rejected',lambda:fail(lambda:verifier_probe(lambda r,z,a:a.update(status='UNRELATED_PASS'))))
    check('original_inputs_unchanged',lambda:all(m.bind(b['path'])==b or fail(lambda:None) for b in original.values()))
    if args.actual_native_files_read_only:
        d=Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_01_17/P_MAIN6/P_MAIN6_S45_01_17/telemetry')
        actual={k:m.bind(d/n) for k,n in dict(native_result='native/result.json',native_inspection='native/command_map_inspection.json',native_samples='native/samples.jsonl',native_transactions='native/transactions.tsv',stdout='stdout.bin',received='received_telemetry.jsonl',stderr='stderr.bin').items()}
        def actual_check():
            value=m.native_closure(actual,2381);write(out/'ACTUAL_NATIVE_FILE_ONLY_PROOF.json',value)
        check('actual_native_2381_file_only_population',actual_check)
    result=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',fixture_only=True,source=m.bind(args.helper),fixture=m.bind(__file__),tests=results,passed=sum(r['status']=='PASS' for r in results),total=len(results),actual_process_scans=0,actual_hardware_commands=0,actual_models=0,scope='Synthetic services and file-only validation. In-memory root status substitution never written as acceptance; no WindowsServices constructed.')
    write(out/'RECEIPT.json',result);print(json.dumps(result,indent=2));return 0 if result['status']=='PASS' else 1


def assert_equal(a,b):
    assert a==b,(a,b)


if __name__=='__main__':raise SystemExit(main())
