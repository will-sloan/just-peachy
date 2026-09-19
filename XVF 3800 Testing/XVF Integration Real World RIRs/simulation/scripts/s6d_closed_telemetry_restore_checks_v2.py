"""Targeted OS-listener recovery checks; README_S6D_CLOSED_TELEMETRY_RESTORE_V2.md."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import traceback


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--actual-read-only',action='store_true');p.add_argument('--helper',type=Path,default=Path(__file__).with_name('s6d_closed_telemetry_restore_v2.py'));a=p.parse_args()
    if a.output.drive.upper()!='G:' or a.output.exists():raise ValueError('Fresh G output required')
    a.output.mkdir(parents=True);spec=importlib.util.spec_from_file_location('tcp_recovery_test',a.helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    results=[]
    def check(name,call):
        try:call();results.append(dict(name=name,status='PASS'))
        except BaseException:results.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(call):
        try:call()
        except (ValueError,RuntimeError):return
        raise AssertionError('Expected fail-closed rejection')
    def row(address='127.0.0.1',port=8765,status='LISTEN',family=2):return dict(family=family,socket_type=1,status=status,local_address=[address,port],remote_address=[],pid=None)
    def census(rows=(),errors=()):return dict(schema='s6d-tcp-listener-census.v1',api="psutil.net_connections(kind='tcp')",complete=not errors,errors=list(errors),rows=list(rows),observed_unix=1000,observed_utc='SYNTHETIC')
    check('complete_empty_OS_table_is_idle',lambda:m.tcp_listener_decision(census()))
    for name,value in [('ipv4_loopback',row()),('ipv4_other_loopback',row('127.2.3.4')),('ipv4_wildcard',row('0.0.0.0')),('ipv6_loopback',row('::1',8766,family=23)),('ipv6_wildcard',row('::',8767,family=23)),('mapped_loopback',row('::ffff:127.0.0.1',family=23))]:
        check(name+'_listener_blocks',lambda value=value:reject(lambda:m.tcp_listener_decision(census([value]))))
    check('established_target_port_is_not_listener',lambda:m.tcp_listener_decision(census([row(status='ESTABLISHED')])))
    check('unrelated_port_listener_is_distinguished',lambda:m.tcp_listener_decision(census([row(port=9999)])))
    check('enumeration_error_blocks',lambda:reject(lambda:m.tcp_listener_decision(census(errors=['Access denied']))))
    check('unknown_listener_address_blocks',lambda:reject(lambda:m.tcp_listener_decision(census([row('unreadable')]))))
    check('unknown_TCP_state_blocks',lambda:reject(lambda:m.tcp_listener_decision(census([row(status='UNKNOWN')]))))
    check('boolean_port_blocks',lambda:reject(lambda:m.tcp_listener_decision(census([row(port=True)]))))
    def failing_provider():
        def failed(**kwargs):raise PermissionError('SYNTHETIC OS enumeration failure')
        value=m.tcp_census(SimpleNamespace(net_connections=failed));assert value['complete'] is False and value['errors'];reject(lambda:m.tcp_listener_decision(value))
    check('actual_collector_converts_error_to_incomplete',failing_provider)
    identity=dict(pid=100,creation_time=10.)
    initial=dict(identity=dict(VERSION=[3,2,1],AEC_MIC_ARRAY_TYPE=[1],USB_BIT_DEPTH=[16,16],I2S_INPUT_PACKED=[0]),usb_bits=[16,16],settings=dict(PP_AGCONOFF=[1],PP_AGCGAIN=[1.2]),observe_only=dict(X=[3]))
    def context(name):
        d=a.output/name;d.mkdir();ledger=d/'ledger.json';m.save(ledger,dict(fixture_only=True,batches={},passes=[]));review=d/'proposal.json'
        r=dict(status='PROPOSED_SOURCE_REVIEW_ONLY',fixture_only=True,source_bindings=[m.bind(a.helper)],telemetry_bindings={});m.save(review,r)
        return dict(review=r,review_ref=m.bind(review),original={k:m.bind(ledger) for k in ('ledger','owner','restoration','initial_state')},values=dict(initial_state=initial),known=[],native_proof=dict(fixture_only=True),output=d/'run')
    class Fake:
        fixture=True
        def __init__(self,blocked_stage=0):self.identity=identity;self.stage=0;self.blocked_stage=blocked_stage;self.events=[]
        def census(self):
            self.stage+=1;self.events.append('process_scan');return dict(complete=True,errors=[],observed_unix=1000.,rows=[dict(identity,name='python.exe',cmdline=['SYNTHETIC'])])
        def ports_idle(self):self.events.append('TCP_census');return census([row()] if self.stage==self.blocked_stage else [])
        def acquire(self):self.events.append('lock')
        def release(self):self.events.append('release');return True
        def initialize_control(self,p):self.events.append('initialize')
        def identify(self):self.events.append('getter');return deepcopy(initial['identity'])
        def restore(self,old):
            self.events.append('restore');return dict(reset=dict(fixture_only=True),reapply=dict(exact_match=True,observed=deepcopy(initial['settings'])),readback={k:deepcopy(initial[k]) for k in ('identity','settings','observe_only')})
    for stage in (1,2,3):
        def blocked(stage=stage):
            c=context('blocked_'+str(stage));f=Fake(stage);reject(lambda:m.recover_prevalidated(c,f));assert not (c['output']/'RECOVERY.json').exists()
            names={1:'before_lock',2:'locked_before_getter',3:'locked_before_setter'}
            saved=m.read(c['output']/(names[stage]+'_TCP_LISTENERS.json'));assert saved['rows']==[row()]
            if stage==1:assert 'lock' not in f.events
            if stage<=2:assert 'getter' not in f.events
            assert 'restore' not in f.events and f.events[-1]=='release'
        check('listener_stage_'+str(stage)+'_saved_and_blocks_actions',blocked)
    def positive():
        c=context('positive');f=Fake();rec=m.read(m.recover_prevalidated(c,f)['path']);result=m.verify(rec['recovery_measurement']);assert rec['fixture_only'] is True
        assert len(result['process_scans'])==4
        for item in result['process_scans']:assert m.tcp_listener_decision(m.verify(item['tcp_listeners']))==item['tcp_listener_decision']
        assert f.events[-1]=='release' and f.events.count('restore')==1
    check('all_four_saved_idle_proofs_and_owned_release',positive)
    actual={}
    if a.actual_read_only:
        def live_tcp():
            import psutil
            value=m.tcp_census(psutil);m.save(a.output/'ACTUAL_READ_ONLY_TCP_CENSUS.json',value);decision=m.tcp_listener_decision(value);m.save(a.output/'ACTUAL_READ_ONLY_TCP_DECISION.json',decision);actual['tcp']=decision
        check('actual_read_only_OS_TCP_listener_census',live_tcp)
        def old_native():
            d=Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_01_17/P_MAIN6/P_MAIN6_S45_01_17/telemetry')
            names=dict(native_result='native/result.json',native_inspection='native/command_map_inspection.json',native_samples='native/samples.jsonl',native_transactions='native/transactions.tsv',stdout='stdout.bin',received='received_telemetry.jsonl',stderr='stderr.bin')
            proof=m.native_closure({k:m.bind(d/n) for k,n in names.items()},2381);m.save(a.output/'ACTUAL_NATIVE_FILE_ONLY_PROOF.json',proof);actual['native_measurement_rows']=proof['measurement_rows']
        check('existing_actual_native2381_proof_unchanged',old_native)
    receipt=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',source=m.bind(a.helper),fixture=m.bind(__file__),tests=results,passed=sum(r['status']=='PASS' for r in results),total=len(results),actual_read_only=actual,actual_process_censuses=0,actual_locks=0,actual_device_commands=0,models=0,actual_recovery=False,scope='Synthetic TCP/ownership fixtures; optional explicitly authorized OS TCP census and original native files read-only. No connect probe or timeout-to-idle inference.')
    m.save(a.output/'RECEIPT.json',receipt);print(json.dumps(dict(status=receipt['status'],passed=receipt['passed'],total=receipt['total'],receipt=m.bind(a.output/'RECEIPT.json'))));return 0 if receipt['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
