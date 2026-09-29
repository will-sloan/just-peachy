"""Ordered state with explicit ORT compression; README_D1_STATE_NATIVE_V1.md."""
import numpy as np
from d1_numpy_state_v1 import State


class OrtState(State):
    def __init__(self, silence_embedding, graph, fifo_capacity=0, refresh=188):
        import onnxruntime as ort
        options=ort.SessionOptions()
        options.intra_op_num_threads=1;options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        options.add_session_config_entry('session.intra_op.allow_spinning','0')
        options.add_session_config_entry('session.inter_op.allow_spinning','0')
        self.compressor=ort.InferenceSession(str(graph),options,providers=['CPUExecutionProvider'])
        assert self.compressor.get_providers()==['CPUExecutionProvider']
        super().__init__(silence_embedding,fifo_capacity,refresh)

    def _compress(self, embeddings, probabilities):
        if self.compressor is None:raise RuntimeError('Compressor already released')
        cache,preds=self.compressor.run(None,dict(embeddings=embeddings[None],probabilities=probabilities[None],silence=self.silence[None]))
        if cache.shape!=(1,264,512) or preds.shape!=(1,264,8) or not np.isfinite(cache).all() or not np.isfinite(preds).all():
            raise RuntimeError('Invalid compressor output')
        return cache[0],preds[0]

    def close(self):
        self.closed=True
        self.compressor=None
