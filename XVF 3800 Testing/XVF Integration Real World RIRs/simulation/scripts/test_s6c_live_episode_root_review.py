"""Independent episode oracle; README_TEST_S6C_LIVE_EPISODE_ROOT_REVIEW.md."""
from __future__ import annotations
import argparse, hashlib, itertools, json
from pathlib import Path
import s6c_live_name_episodes as subject


def binding(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def oracle(timeline, support, truth):
    """Enumerate integer samples, independent of interval-intersection/union code."""
    result = []
    length = timeline[-1]['end'] if timeline else 0
    tokens = []
    for sample in range(length):
        if not any(a <= sample < b for a, b in support):
            tokens.append(None)
            continue
        state = next(r for r in timeline if r['start'] <= sample < r['end'])
        kind = ('unknown_name' if state['status'] == 'UNKNOWN_NAME' else
                'correct_name' if state['status'] == 'ASSIGNED_NAME' and state['identity'] == truth else
                'wrong_known_name')
        tokens.append((kind, state['identity'], state['status']))
    i = 0
    while i < length:
        token = tokens[i]
        j = i + 1
        while j < length and tokens[j] == token:
            j += 1
        if token is not None and token[0] != 'unknown_name':
            nxt = tokens[j] if j < length else None
            ending = ('SUPPORT_BOUNDARY_CENSORED' if nxt is None else
                      'CORRECT_NAME_OBSERVED' if nxt[0] == 'correct_name' else
                      'UNKNOWN_OR_EXPIRED_ABSTENTION' if nxt[0] == 'unknown_name' else
                      'OTHER_WRONG_IDENTITY')
            result.append(dict(start_sample=i, end_sample=j, status=token[0],
                               assigned_identity=token[1], assignment_status=token[2],
                               duration_samples=j-i, end_status=ending))
        i = j
    return result


def review(expected_sha):
    source = binding(subject.__file__)
    if source['sha256'] != expected_sha:
        raise ValueError('Held source changed; require the new explicit reviewed SHA')
    own = subject.fixtures()
    assert own['status'] == 'PASS'
    states = [('UNKNOWN_NAME', None, False), ('ASSIGNED_NAME', 'A', False),
              ('ASSIGNED_NAME', 'A', True), ('ASSIGNED_NAME', 'B', True),
              ('UNDECLARED_ASSIGNED_NAME', None, False)]
    supports = [[], [[0, 7]], [[1, 6]], [[0, 2], [3, 5], [6, 7]], [[0, 1], [2, 7]]]
    boundaries = [0, 1, 3, 6, 7]
    comparisons = 0
    for values in itertools.product(states, repeat=4):
        line = [dict(start=boundaries[i], end=boundaries[i+1], status=s,
                     identity=p, confirmed=c) for i, (s, p, c) in enumerate(values)]
        for support in supports:
            for truth in ('A', 'B'):
                expected = oracle(line, support, truth)
                actual = subject.episodes(line, support, truth)
                assert len(actual) == len(expected)
                for got, want in zip(actual, expected):
                    assert {k: got[k] for k in want} == want
                    assert got['duration_sec'] == want['duration_samples'] / 16000
                comparisons += 1
    bad_supports = [[[3, 5], [0, 2]], [[0, 4], [3, 6]], [[-1, 1]],
                    [[0, 8]], [[False, 2]], [[0, 1.5]]]
    line = [dict(start=0, end=7, status='ASSIGNED_NAME', identity='A', confirmed=True)]
    for support in bad_supports:
        try:
            subject.episodes(line, support, 'A')
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError('Invalid support admitted: '+repr(support))
    assert subject.episodes(line, None, 'A') is None
    assert subject.episodes(line, [], 'A') == []
    assert source == binding(subject.__file__)
    return dict(status='PASS', scope='Independent integer-sample episode oracle and held pure fixtures; no empirical scoring, prediction replay, native logs or model calls.',
                exhaustive_cases=comparisons, invalid_support_cases=len(bad_supports),
                held_fixtures=own, codes=[source,
                    binding(Path(subject.__file__).with_name('README_S6C_LIVE_NAME_EPISODES.md')),
                    binding(subject.names.__file__), binding(subject.core.__file__),
                    binding(__file__), binding(Path(__file__).with_name('README_TEST_S6C_LIVE_EPISODE_ROOT_REVIEW.md'))],
                limitations=['The oracle tests integer support intervals and the inherited metadata-identity vocabulary.',
                             'Undeclared foreign names cannot be distinguished after the unchanged V3 mapping; they remain explicitly undeclared.',
                             'Actual episode counts require the separately admitted completed-receipt supplement.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--held-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = review(args.held_sha)
    if args.output.exists():
        raise ValueError('Preserve prior review; choose a fresh output')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(status=result['status'], exhaustive_cases=result['exhaustive_cases'],
                         held_fixture_count=result['held_fixtures']['count'], receipt=binding(args.output))))
