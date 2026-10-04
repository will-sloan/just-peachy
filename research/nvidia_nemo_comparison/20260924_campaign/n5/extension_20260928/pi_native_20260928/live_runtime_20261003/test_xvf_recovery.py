"""No-device conditional recovery checks. README_XVF_RECOVERY.md."""
import json
from pathlib import Path
import unittest
from launch_xvf_recovery_action import qualifying_fault,recovery_sequence,SEQUENCE_SOURCE,DRIVER


class RecoveryTests(unittest.TestCase):
    def test_actual_failed_source_gate(self):
        path=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/raw-qualification-06-monitor-01/closed-output/qualification/recordings/sessions/513e4b704aa94d12b9bdd5486cde935c/work/source/SOURCE_CLOSE.json')
        value=json.loads(path.read_bytes());self.assertTrue(qualifying_fault(value))
        for key,item in (('sent_samples',1),('stream_closed',False),('lease_released',False)):
            self.assertFalse(qualifying_fault(dict(value,**{key:item})))
        compile(SEQUENCE_SOURCE+'\n'+DRIVER,'<native-recovery-driver>','exec')

    def run_sequence(self,aec=255,maintenance=0,timeout=False,changed=False):
        calls=[];saved={};sleeps=[]
        def command(name,args=()):
            calls.append((name,args))
            code=aec if name=='AEC_MIC_ARRAY_TYPE' and len(calls)==3 else maintenance if name=='TEST_CORE_BURN' else 0
            stdout='VERSION 3 2 2' if changed and name=='VERSION' and len(calls)>4 else 'VERSION 3 2 1' if name=='VERSION' else 'BLD_MSG intdev-lr48-lin-i2c' if name=='BLD_MSG' else 'AEC_MIC_ARRAY_TYPE 1'
            return dict(exit_code=code,timeout=timeout and name=='TEST_CORE_BURN',stdout=stdout,
                        stderr='Resource could not respond' if code==255 else '')
        try:
            result=recovery_sequence(command,lambda name,value:saved.update({name:value}),sleeps.append,'a'*64)
        except Exception as exc:result=exc
        return calls,saved,sleeps,result

    def test_readable_control_never_sends(self):
        calls,saved,sleeps,result=self.run_sequence(aec=0)
        self.assertEqual(len(calls),3);self.assertEqual(saved,{})
        self.assertEqual(result['maintenance_sends'],0)

    def test_single_send_and_fresh_post_readbacks(self):
        calls,saved,sleeps,result=self.run_sequence()
        self.assertEqual(len(calls),7);self.assertEqual(calls.count(('TEST_CORE_BURN',('0',))),1)
        self.assertEqual(sleeps,[2]);self.assertEqual(saved['RESTART_INTENT.json']['maximum_sends'],1)
        self.assertEqual(result['before'],result['after']);self.assertTrue(result['post_aec_readable'])
        self.assertFalse(result['audio_qualified'])

    def test_uncertain_or_failed_send_never_retries(self):
        for args in (dict(maintenance=1),dict(timeout=True)):
            calls,saved,sleeps,result=self.run_sequence(**args)
            self.assertIsInstance(result,RuntimeError);self.assertEqual(len(calls),4)
            self.assertEqual(calls.count(('TEST_CORE_BURN',('0',))),1);self.assertEqual(sleeps,[])
            self.assertIn('RESTART_INTENT.json',saved)

    def test_unqualified_current_error_or_changed_firmware_refused(self):
        calls,saved,sleeps,result=self.run_sequence(aec=1)
        self.assertIsInstance(result,ValueError);self.assertEqual(len(calls),3);self.assertEqual(saved,{})
        calls,saved,sleeps,result=self.run_sequence(changed=True)
        self.assertIsInstance(result,ValueError);self.assertEqual(len(calls),6)
        self.assertEqual(calls.count(('TEST_CORE_BURN',('0',))),1)


if __name__=='__main__':unittest.main()
