import numpy as np

from app.onnx_pipeline.matching import choose_speaker, cosine_similarity


def test_cosine_similarity_identity():
    x = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert abs(cosine_similarity(x, x) - 1.0) < 1e-6


def test_choose_speaker_accepts_clear_best():
    gallery = {
        "Alice": [np.array([1.0, 0.0], dtype=np.float32)],
        "Bob": [np.array([0.0, 1.0], dtype=np.float32)],
    }
    query = np.array([0.9, 0.1], dtype=np.float32)
    match = choose_speaker(query, gallery, accept_threshold=0.5, margin_threshold=0.1)
    assert match.accepted is True
    assert match.label == "Alice"


def test_choose_speaker_rejects_below_threshold():
    gallery = {"Alice": [np.array([1.0, 0.0], dtype=np.float32)]}
    query = np.array([0.0, 1.0], dtype=np.float32)
    match = choose_speaker(query, gallery, accept_threshold=0.95, margin_threshold=0.1)
    assert match.accepted is False
    assert match.reason == "below_accept_threshold"
