"""Actual app-delivery adapter causality fixtures; README_S6A_CUES.md."""
import math
import unittest
from s6a_cue_delivery import sanitize


def row(command,t,values,sequence=1):
    return dict(command=command,values=values,parse_ok=True,
                logical_request_start_monotonic_ns=t-1000000,response_end_monotonic_ns=t-100000,
                host_line_arrival_monotonic_ns=t,receipt_sequence=sequence,sequence=sequence,
                invalid_reasons=[None]*len(values),reference_speaker='MUST_NOT_REACH_PREDICTOR')


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.metadata={'callback_times':[dict(first_native_frame=i*4800,frames=4800,
                                              host_copy_complete_monotonic_ns=1000000000+i*100000000,
                                              host_callback_monotonic_ns=1000000000+i*100000000) for i in range(10)]}
        self.capture={'framing':{'startup_frames_excluded':0}}

    def test_packet_after_callback_waits_for_next_available_samples(self):
        values,stats=sanitize(self.metadata,self.capture,[row('AUDIO_MGR_SELECTED_AZIMUTHS',1310000000,[1.,1.])])
        self.assertAlmostEqual(values[0]['available_at_sec'],.5)
        self.assertAlmostEqual(stats['host_to_callback_delay_max_sec'],.09)

    def test_future_energy_never_attached(self):
        raw=[row('AUDIO_MGR_SELECTED_AZIMUTHS',1310000000,[1.,1.]),
             row('AEC_SPENERGY_VALUES',1320000000,[10.,10.,10.,10.],2)]
        values,_=sanitize(self.metadata,self.capture,raw)
        self.assertIsNone(values[0]['energy'])

    def test_truth_fields_and_unknown_source_span_omitted(self):
        values,stats=sanitize(self.metadata,self.capture,[row('AUDIO_MGR_SELECTED_AZIMUTHS',1310000000,[1.,1.])])
        self.assertEqual(set(values[0]),{'angle_deg','available_at_sec','energy','reliability','valid','sequence'})
        self.assertFalse(stats['source_span_supplied'])

    def test_after_capture_is_explicitly_unmapped(self):
        values,stats=sanitize(self.metadata,self.capture,[row('AUDIO_MGR_SELECTED_AZIMUTHS',2310000000,[1.,1.])])
        self.assertEqual(values,[]);self.assertEqual(stats['outside_capture_rows'],1)

    def test_future_suffix_change_does_not_change_delivered_prefix(self):
        first=row('AUDIO_MGR_SELECTED_AZIMUTHS',1310000000,[.1,.1])
        a,_=sanitize(self.metadata,self.capture,[first,row('AUDIO_MGR_SELECTED_AZIMUTHS',1610000000,[1.,1.],2)])
        b,_=sanitize(self.metadata,self.capture,[first,row('AUDIO_MGR_SELECTED_AZIMUTHS',1610000000,[2.,2.],2)])
        self.assertEqual(a[0],b[0])


if __name__=='__main__':unittest.main()
