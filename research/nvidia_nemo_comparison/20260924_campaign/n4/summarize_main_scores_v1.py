"""Publish aggregate-only accepted main scores; README_MAIN_SCORE_SUMMARY_V1.md."""
import argparse
from pathlib import Path

from common import bind, load, verify
from metric_process import pin


def percent(value):
    return 'unavailable' if value is None else f'{100*value:.2f}%'


def run(acceptance, output):
    pin();a=load(acceptance);verify(a['review']);review=load(a['review']['path']);verify(a['report'])
    if (a['status']!='ACCEPTED_REVIEWED_MAIN_MODELED_SCORING_ONLY'
            or review['status']!='PASS_REVIEWED_MODELED_SCORING_ONLY' or review['report']!=a['report']
            or review['reviewed']!=7680 or review['required']!=7680):raise ValueError('Reviewed main score authority required')
    report=load(a['report']['path'])
    if report['scope']!='main' or report['required_cells']!=7680 or len(report['cohorts'])!=32 or len(report['paired'])!=45:raise ValueError('Complete main report required')
    cohorts=sorted(report['cohorts'],key=lambda c:(c['composition'],c['tap']))
    seen={(c['composition'],c['tap']) for c in cohorts}
    if len(seen)!=32 or len({c['composition'] for c in cohorts})!=16:raise ValueError('Composition/tap census differs')
    lines=['# Main modeled scoring results','',
        'All 7,680 cases have completed scoring and independent input/report review. '
        'These are modeled application-method results, not N4 acceptance or a deployment recommendation. '
        '832 cases with incomplete ambient references retain target-only scope.','',
        'Primary WER sums edits and reference words on complete non-overlap references. '
        'cpWER and MIMO use their own supported-reference populations; their denominators are shown separately. '
        'MIMO excludes unsupported speaker counts. Estimated activity is not phonetic ground truth. '
        'First-visible naming, actual GUI latency, memory, CPU feasibility and CM5 performance remain unvalidated.','',
        '| Composition | Tap | Completed | Primary WER (edits/words) | cpWER (edits/words) | MIMO (edits/words) |',
        '|---|---|---:|---:|---:|---:|']
    for c in cohorts:
        n=c['counts'];m=n['word_metrics']
        if c['mode']!='open_with_names' or n['required_cells']!=240 or n['execution_statuses']!={'COMPLETE':240} or n['metric_statuses']!={'SCORED':240}:raise ValueError('Incomplete cohort')
        cells=[]
        for metric in ('primary_wer','cpwer','mimo'):
            x=m[metric];expected=x['errors']/x['words'] if x['words'] else None
            if expected!=x['rate']:raise ValueError('Aggregate rate differs from edit/word totals')
            cells.append(f"{percent(x['rate'])} ({x['errors']}/{x['words']})")
        lines.append(f"| {c['composition']} | {c['tap']} | 240/240 | "+' | '.join(cells)+' |')
    lines+=['','## Paired comparisons with A0/D0/E0','',
        'Both taps are paired by scene. Deltas are candidate minus baseline in percentage points; '
        'negative means fewer errors for that supported paired population. These are descriptive seen-bank '
        'comparisons. Confidence intervals remain unavailable where fewer than eight dependency clusters exist.','',
        '| Composition | Metric | Pairs | Baseline | Candidate | Delta (pp) | Interval |',
        '|---|---|---:|---:|---:|---:|---|']
    for p in sorted(report['paired'],key=lambda p:(p['composition'],p['metric'])):
        r=p['result']
        if r is None:continue
        delta=r['candidate_minus_baseline'];interval=r['interval95']
        lines.append(f"| {p['composition']} | {p['metric']} | {r['pairs']}/{p['required_pairs']} | "
            f"{percent(r['baseline']['rate'])} | {percent(r['candidate']['rate'])} | {100*delta:+.2f} | "
            +('unavailable' if interval is None else str(interval))+' |')
    lines+=['','No winner is promoted from this table. Complete the modes bank and functional/resource confirmation '
        'before selecting releases. Baseline retention and honest partial delivery remain required if the remaining '
        'campaign window cannot cover all confirmations.','',
        'Acceptance SHA-256: '+bind(acceptance)['sha256']+'.',
        'Private report SHA-256: '+a['report']['sha256']+'.',
        'Independent review SHA-256: '+a['review']['sha256']+'.',
        'See README_MAIN_SCORE_SUMMARY_V1.md for reproduction. Private per-scene evidence remains outside Git.','']
    if output.exists():raise ValueError('Preserve the previous summary; use a fresh destination')
    output.write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acceptance',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.acceptance,a.output)
