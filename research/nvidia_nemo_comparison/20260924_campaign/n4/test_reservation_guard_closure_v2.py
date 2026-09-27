"""Completed-handle and exact-exit boundaries; README_RESERVATION_GUARD_V2.md."""
from types import SimpleNamespace
import unittest
from probe_reservation_guard_v2 import close_waited_handle, wait_exact_exit


class Closure(unittest.TestCase):
    def test_only_completed_owned_handle_is_closed(self):
        handle=SimpleNamespace(closed=False)
        handle.Close=lambda:setattr(handle,'closed',True)
        child=SimpleNamespace(_handle=handle,poll=lambda:0)
        close_waited_handle(child);self.assertTrue(handle.closed)
        handle.closed=False;child.poll=lambda:None
        with self.assertRaisesRegex(ValueError,'running helper'):close_waited_handle(child)
        self.assertFalse(handle.closed)
    def test_retained_identity_gets_bounded_exit_observation(self):
        states=iter([object(),object(),None]);clock=[0.0];sleeps=[]
        def pause(delta):clock[0]+=delta;sleeps.append(delta)
        self.assertTrue(wait_exact_exit(dict(pid=1,create_time=1),lookup=lambda _:next(states),
            now=lambda:clock[0],pause=pause,seconds=1))
        self.assertEqual(sleeps,[.02,.02])
    def test_uncertain_identity_and_timeout_are_not_success(self):
        def denied(_):raise PermissionError('unverified')
        with self.assertRaises(PermissionError):wait_exact_exit({},lookup=denied)
        clock=[0.0]
        def pause(delta):clock[0]+=delta
        with self.assertRaisesRegex(ValueError,'identity remained'):
            wait_exact_exit({},lookup=lambda _:object(),now=lambda:clock[0],pause=pause,seconds=.05)
        self.assertLessEqual(clock[0],.05)
    def test_already_exited_exact_identity_needs_no_delay(self):
        def never(_):self.fail('unnecessary delay')
        self.assertTrue(wait_exact_exit({},lookup=lambda _:None,pause=never))


if __name__=='__main__':unittest.main()
