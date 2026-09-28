"""Read-only caption lineage for a closed targeted retry. See README_PANEL_CAPTION_V1.md."""
import argparse
import json
from pathlib import Path

from panel_retry_v3 import BASE, HERE, check_bindings, require, run_path
from common import bind, freeze, load, verify
from metric_process import exact_process, pin
from review_native_captions import review as review_captions


def main(name):
    pin()
    run = run_path(name)
    output = BASE / (name + '-CAPTION_REVIEW_V1.json')
    require(not output.exists(), 'Fresh review output required')
    prior_binding = bind(BASE / (name + '-REVIEW.json'))
    prior = load(prior_binding['path'])
    require(prior['status'] == 'PASS_TARGETED_APPLICATION_STRUCTURE_ONLY', 'Structure not reviewed')
    verify(prior['result'])
    verify(prior['admission'])
    admission = check_bindings(load(prior['admission']['path']))
    require(all(exact_process(owner) is None for owner in prior['closed_exact_owners']), 'Run owner alive')
    envelope = prior['native_journal']
    session = Path(envelope['journal'][0]['path']).parent
    require(session.is_relative_to(run / 'infer/cell/data/sessions'), 'Foreign session')
    code = [bind(HERE / name) for name in ('review_panel_caption_v1.py', 'README_PANEL_CAPTION_V1.md')]
    result = dict(status='FAILED_PRESERVED', structural_review=prior_binding, code=code,
                  N4_accepted=False, N5_complete=False, CM5_tested=False, integrated_N4_cells=0)
    try:
        caption = review_captions(session, job=admission['job'], expected_envelope=envelope)
        require(caption['raw_revision_caption_coverage_complete'] is True, 'Unrepresented raw revision')
        require(not caption['partial_only_utterance_ids'], 'Unfinalized utterance remains')
        result.update(status='PASS_TARGETED_RAW_CAPTION_LINEAGE_ONLY', caption=caption,
                      scope='Complete recorded raw-ASR/caption partition lineage only. Speaker accuracy, '
                            'actual widget interpretation, source-to-widget latency and panel acceptance remain open.')
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    verify(prior_binding)
    for binding in admission['bindings'] + code:
        verify(binding)
    require(len(json.dumps(result).encode('utf-8')) < 1024**2, 'Review exceeds 1 MiB bound')
    freeze(output, result)
    print(dict(status=result['status'], error=result.get('error'), output=str(output)))
    return int(result['status'] == 'FAILED_PRESERVED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    raise SystemExit(main(parser.parse_args().name))
