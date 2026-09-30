"""Selected installed Stop derivative; README_FIELD_SOURCE_RECEIPTS_V1.md."""
from field_source_receipt_routes_v1 import ReceiptFailure

def source_class(base):
    class BudgetedSource(base.XVFLiveSource):
        def __init__(self, config, receipt_routes, **kwargs):
            self.receipt_routes=receipt_routes
            super().__init__(config, **kwargs)
        def start(self, *args, **kwargs):
            raise base.LiveAudioError('CAPTURE_UNAVAILABLE_IN_RECEIPT_QUALIFICATION')
        def _stop_owned(self):
            if self._receipt is not None:
                return self._receipt
            self._stopped = True
            self._route_ready = False
            errors = []
            if self.beam_diagnostics is not None:
                if not self.beam_diagnostics.stop(timeout=self.config.control_timeout_seconds + 1):
                    raise base.LiveAudioError("Beam diagnostic worker still owns device control; retry Stop")
            # UA control servicing needs the audio clock. No samples are admitted
            # during restoration; close the input stream immediately afterwards.
            restored = self.route.restore() if self.route is not None else {}
            if self.stream is not None:
                try:
                    self.stream.stop()
                except Exception as exc:
                    errors.append("stream_stop: " + str(exc))
                try:
                    self.stream.close()
                except Exception as exc:
                    errors.append("stream_close: " + str(exc))
                # A driver can reject both stop and close. Do not let another
                # process take the lease while this input stream is still active.
                # Keep the incomplete stop retryable instead of caching success.
                try:
                    still_active = bool(self.stream.active)
                except Exception:
                    still_active = not bool(getattr(self.stream, "closed", False))
                if still_active:
                    self._fault = self._fault or "STREAM_REMAINS_ACTIVE_AFTER_CLOSE"
                    raise base.LiveAudioError("Input stream remains active after close; hardware lease retained for cleanup retry: " + "; ".join(errors))
            if self.lease is not None:
                self.lease.close()
            after = base.endpoint_snapshot()
            self._done.set()
            self._receipt = {"status": self.status(), "route_restoration": restored, "errors": errors,
                             "metadata": self.metadata, "defaults_after_stop": after,
                             "default_output_comparison": base.compare_defaults(self.metadata.get("defaults_before", {}), after),
                             "commands": self.control.receipts if self.control else []}
            try:
                self.receipt_routes.source('ROUTE_STOP.json', self._receipt)
            except ReceiptFailure as exc:
                # Physical Stop/route/lease completion happened above.
                self._receipt['errors'].append('SOURCE_RECEIPT_NOT_PUBLISHED')
                self._receipt['receipt_failure'] = exc.receipt
            self.status_callback("source_stopped", self._receipt)
            return self._receipt
    return BudgetedSource
