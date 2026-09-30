"""Bound TRACE adapter for accepted blocks; README_FIELD_TRANSPORT_OUTPUTS_V1.md."""
from dataclasses import fields
import hashlib
from field_transport_outputs_v1 import OutputFailure

def traced_accept(original,outputs,maximum_accepted_samples):
    def accept(self,block,ipc):
        original(self,block,ipc)
        item=dict(samples=len(block.audio),metadata={f.name:getattr(block,f.name) for f in fields(block) if f.name!='audio'},ipc=ipc,
                  audio_sha256=hashlib.sha256(block.audio.astype('<f4',copy=False).tobytes()).hexdigest())
        try:
            outputs.trace(item)
            if self.sent>maximum_accepted_samples:raise RuntimeError('Accepted sample ceiling; prefix retained, run failed')
        except Exception as exc:
            # The block is already journaled. Mark failure/Stop without throwing
            # it back into _run's unaccepted-block accounting a second time.
            self._error(exc)
    return accept
