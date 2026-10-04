"""No-Tk UI/channel contract checks; README_RUNTIME_UI.md."""
import math
import types
import unittest
from unittest import mock
from runtime_ui import device_tip,history_label,SpatialPanel
from runtime_ui_channel import SpatialViews,StreamDecoder,spatial_message,MAX_MESSAGE
from installed_source import _RemoteStatus


class RuntimeUiTests(unittest.TestCase):
    def test_device_display_does_not_reapply_motion_or_change_primary_associations(self):
        primary=mock.Mock();device=mock.Mock();device.motion=None
        primary.snapshot.return_value=dict(coordinate_frame='relative_anchor_front_assumed',
            arrows=[dict(angle_deg=120)],associations=[dict(label='Speaker 1',angle_deg=130)],
            motion=dict(valid=True,yaw_deg=30))
        device.snapshot.return_value=dict(coordinate_frame='device',arrows=[dict(angle_deg=90)],associations=[])
        view=SpatialViews(primary,device);live=types.SimpleNamespace()
        view.attach(live);view.bind_origin(4);live.spatial_observer('field',[1],5,6)
        block=object();view.advance_audio(block)
        view.observe_segmentation(dict(speech=True));view.observe_decision(dict(label='Speaker 1'))
        display=view.display_snapshot()
        self.assertEqual(display['arrows'][0]['angle_deg'],90)
        self.assertEqual(display['motion']['yaw_deg'],30)
        self.assertEqual(display['association_reference_frame'],'relative_anchor_front_assumed')
        self.assertEqual(view.snapshot()['arrows'][0]['angle_deg'],120)
        for provider in (primary,device):
            provider.receive.assert_called_once_with('field',[1],5,6)
            provider.advance_audio.assert_called_once_with(block)
            provider.bind_origin.assert_called_once_with(4)
        primary.observe_decision.assert_called_once()
        device.observe_decision.assert_not_called()
        device.motion=object()
        with self.assertRaises(ValueError):SpatialViews(primary,device)

    def test_retained_linear_array_coordinates_and_display_only_zero(self):
        for angle,expected in ((0,(10,0)),(90,(0,-10)),(180,(-10,0))):
            actual=device_tip(angle,0,0,10)
            for left,right in zip(actual,expected):self.assertAlmostEqual(left,right)
        with self.assertRaises(ValueError):device_tip(float('nan'),0,0,10)
        panel=SpatialPanel.__new__(SpatialPanel)
        panel.snapshot=dict(motion=dict(valid=True,yaw_deg=32));panel.zero=0
        panel.draw_debug=mock.Mock();panel.recenter()
        self.assertEqual(panel.zero,32)
        self.assertEqual(panel.snapshot['motion']['yaw_deg'],32)

    def test_fragmented_channel_keeps_latest_in_ram_and_diagnostics_exact(self):
        view=dict(state='RUNNING',coordinate_frame='device',motion=dict(valid=True,yaw_deg=2),
                  arrows=[dict(id='selected_auto',angle_deg=90,fresh=True)],associations=[])
        raw=spatial_message(view);self.assertLessEqual(len(raw),MAX_MESSAGE)
        received=[];diagnostic=[];decoder=StreamDecoder(received.append,diagnostic.append)
        wire=b'normal diagnostic\n'+raw+b'partial diagnostic'
        for start in range(0,len(wire),7):decoder.feed(wire[start:start+7])
        decoder.finish()
        self.assertEqual(len(received),1)
        self.assertEqual(received[0]['spatial']['arrows'][0]['angle_deg'],90)
        self.assertEqual(b''.join(diagnostic),b'normal diagnostic\npartial diagnostic')

    def test_remote_state_never_invents_running_and_history_keeps_unique_identity(self):
        source=types.SimpleNamespace(_status={})
        remote=_RemoteStatus(source)
        self.assertEqual(remote.beam_diagnostics.snapshot()['state'],'UNAVAILABLE')
        source._status['beam_diagnostics_state']='RUNNING'
        self.assertEqual(remote.beam_diagnostics.snapshot()['state'],'RUNNING')
        label=history_label(dict(created=0,session_id='abcdef012345',duration_seconds=1.5,spec=dict(title='Example')))
        self.assertIn('Example',label);self.assertIn('abcdef01',label);self.assertIn('1.5s',label)


if __name__=='__main__':unittest.main()
