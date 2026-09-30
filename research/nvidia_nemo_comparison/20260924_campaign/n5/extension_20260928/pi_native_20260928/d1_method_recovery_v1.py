"""Recover only pre-owner validation errors; README_D1_METHOD_RECOVERY_V1.md."""
from copy import deepcopy
import d1_method_application_v1 as application
from d1_application_saved_v4 import adapter_request


def controller_class(Base, root, spec, writer, closer, failure, catalog):
    Parent = application.controller_class(Base, root, spec, writer, closer, failure, catalog)

    class RecoverableMethods(Parent):
        def __init__(self, *args, **kwargs):
            self._d1_validation_error = None
            super().__init__(*args, **kwargs)

        def _d1_unowned(self):
            return (not self.closed and not self.d1_owned and not self.d1_used
                and self.d1_thread is None and self.engine is None and self.consumer is None
                and self.source_kind is None and self.enrollment['state'] == 'IDLE'
                and not self.session_store.active)

        def _d1_recovery_matches(self):
            return (self._d1_validation_error is not None and self._d1_unowned()
                and self.state == 'ERROR' and self.status == self._d1_validation_error[0]
                and self.d1_error == self._d1_validation_error[1]
                and self.d1_phase == 'METHOD_ERROR')

        def _d1_latch_validation(self, exc):
            self.d1_error = 'Method contract rejected: ' + str(exc)
            self.d1_phase = 'METHOD_ERROR'
            # The installed command loop assigns the exact first string after re-raise.
            self._d1_validation_error = ('ValueError: ' + str(exc), self.d1_error)

        def _do_d1_select(self, mode):
            with self.d1_lock:
                recovering = self._d1_recovery_matches()
                if not self._d1_unowned():
                    raise RuntimeError('Selection cannot release an existing operation; close it first.')
                if not recovering and (self.state != 'IDLE' or self.d1_error is not None):
                    raise RuntimeError('Selection cannot clear another failure: ' + self.status)
                # Only this pre-owner validation can create a recoverable error token.
                try:
                    catalog.request(mode)
                except ValueError as exc:
                    self._d1_latch_validation(exc)
                    raise
                super()._do_d1_select(mode)
                self._d1_validation_error = None
                self.state = 'IDLE'
                self.error = None
                self.status = ('Saved diarizer ready. Microphone is off.' if self.d1_phase == 'READY'
                    else 'Selected mode is outside this saved admission. Start is unavailable.')

        def _do_d1_start(self):
            with self.d1_lock:
                if not self._d1_unowned() or self.state != 'IDLE' or self.d1_error is not None:
                    raise RuntimeError('Saved Start requires an idle, explicitly selected application.')
                try:
                    selected = deepcopy(self.d1_selected)
                    adapter_request(selected)
                    catalog.validate(selected['selection']['id'], self.d1_method_profile)
                except ValueError as exc:
                    self._d1_latch_validation(exc)
                    raise
                # Writer/constructor/ownership failures from the parent do NOT gain a token.
                return super()._do_d1_start()

        def _do_d1_stop(self):
            with self.d1_lock:
                pending = self._d1_recovery_matches()
            result = super()._do_d1_stop()
            with self.d1_lock:
                if pending and self._d1_recovery_matches():
                    self.error = self._d1_validation_error[0]
            return result

        def d1_snapshot(self):
            with self.d1_lock:
                value = super().d1_snapshot()
                value['start_available'] = (value['start_available'] and self.state == 'IDLE'
                    and self.error is None and self._d1_validation_error is None)
                value['application_state'] = self.state
                value['application_status'] = self.status
                value['application_error'] = self.error
                value['validation_recovery_available'] = self._d1_recovery_matches()
                return value
    return RecoverableMethods


ui_class = application.ui_class
