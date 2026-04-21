"""Small WER implementation for utterance-level scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WerResult:
    """Word error counts and derived WER."""

    wer: float
    errors: int
    substitutions: int
    deletions: int
    insertions: int
    reference_words: int
    hypothesis_words: int


def compute_wer(reference: str, hypothesis: str) -> WerResult:
    """Compute word error rate and operation counts."""

    ref_words = reference.split()
    hyp_words = hypothesis.split()
    ref_len = len(ref_words)
    hyp_len = len(hyp_words)

    # Each cell stores (cost, substitutions, deletions, insertions).
    dp: list[list[tuple[int, int, int, int]]] = [
        [(0, 0, 0, 0) for _ in range(hyp_len + 1)] for _ in range(ref_len + 1)
    ]
    for i in range(1, ref_len + 1):
        prev = dp[i - 1][0]
        dp[i][0] = (prev[0] + 1, prev[1], prev[2] + 1, prev[3])
    for j in range(1, hyp_len + 1):
        prev = dp[0][j - 1]
        dp[0][j] = (prev[0] + 1, prev[1], prev[2], prev[3] + 1)

    for i in range(1, ref_len + 1):
        for j in range(1, hyp_len + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
                continue

            sub_prev = dp[i - 1][j - 1]
            deletion_prev = dp[i - 1][j]
            insertion_prev = dp[i][j - 1]
            candidates = [
                (sub_prev[0] + 1, sub_prev[1] + 1, sub_prev[2], sub_prev[3]),
                (
                    deletion_prev[0] + 1,
                    deletion_prev[1],
                    deletion_prev[2] + 1,
                    deletion_prev[3],
                ),
                (
                    insertion_prev[0] + 1,
                    insertion_prev[1],
                    insertion_prev[2],
                    insertion_prev[3] + 1,
                ),
            ]
            dp[i][j] = min(candidates, key=lambda item: (item[0], item[1], item[2], item[3]))

    errors, substitutions, deletions, insertions = dp[ref_len][hyp_len]
    if ref_len == 0:
        wer = 0.0 if errors == 0 else 1.0
    else:
        wer = errors / ref_len
    return WerResult(
        wer=wer,
        errors=errors,
        substitutions=substitutions,
        deletions=deletions,
        insertions=insertions,
        reference_words=ref_len,
        hypothesis_words=hyp_len,
    )

