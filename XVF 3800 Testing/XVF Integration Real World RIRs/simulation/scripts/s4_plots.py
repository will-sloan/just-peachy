"""Three compact S4 evidence figures; run after physical capture and analysis. README_S4_RESULTS.md."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from s4_common import BANK, REPORT, bind, check_storage, now, read, save
from s4_summary import CASE_IDS, OUTPUTS, write_csv
from s4_capture_selection import accepted_cases, case_folder

COLORS = {'O0': '#2463A6', 'O1': '#D36A21', 'O0_adapter': '#218C79'}
CALIBRATION = ('calibration_base', 'calibration_limiter', 'calibration_agc')


def dbfs(peak):
    return 20 * math.log10(peak) if peak is not None and peak > 0 else None


def number(value):
    return float(value) if value not in (None, '') else None


def save_figure(fig, path):
    fig.savefig(path, dpi=150, facecolor='white', metadata={'Software': 'Just-Peachy S4 local Matplotlib'})


def headroom_figure(plt, directory, policy, partial):
    rows = []
    selected = accepted_cases(partial=partial)
    for batch in (*CALIBRATION, 'final'):
        cases = ('S4_01', 'S4_02', 'S4_03') if batch != 'final' else CASE_IDS
        for cid in cases:
            folder = selected[cid]['folder'] if batch == 'final' and cid in selected else REPORT / 'hardware' / batch / cid
            path = folder / 'audio_metrics.json'
            if not path.exists(): continue
            metrics = read(path)
            for stream, item in metrics['streams'].items():
                rows.append({'batch': batch, 'physical_capture_batch': metrics['batch'], 'case_id': cid, 'stream': stream, 'samples': item['sample_count'],
                             'rail_samples': item['rail_samples'],
                             'rail_samples_per_million': item['rail_samples'] * 1e6 / item['sample_count'],
                             'raw_peak_fs': item['peak_fs'], 'raw_peak_dbfs': dbfs(item['peak_fs']),
                             'fixed_host_gain': policy['fixed_host_gain'][stream],
                             'projected_peak_after_fixed_gain_fs': item['peak_fs'] * policy['fixed_host_gain'][stream],
                             'raw_support_rms_dbfs': item.get('support_rms_dbfs')})
    index = {(r['batch'], r['case_id'], r['stream']): r for r in rows}
    fig, axes = plt.subplots(3, 1, figsize=(13.2, 10.5), gridspec_kw={'height_ratios': [1, 1.25, 1.1]})
    totals = []
    for batch in CALIBRATION:
        values = [index.get((batch, cid, 'O1')) for cid in ('S4_01', 'S4_02', 'S4_03')]
        totals.append({'rails': sum(r['rail_samples'] for r in values if r), 'samples': sum(r['samples'] for r in values if r), 'count': sum(r is not None for r in values)})
    bars = axes[0].bar(range(3), [r['rails'] if r['count'] else float('nan') for r in totals], width=.55,
                       color=['#9DABC2', '#D3A37E', COLORS['O1']])
    for bar, row in zip(bars, totals):
        if row['count']:
            axes[0].annotate(f"{row['rails']} / {row['samples']:,} samples\n({row['count']} matched captures)",
                             (bar.get_x()+bar.get_width()/2, bar.get_height()), xytext=(0, 4), textcoords='offset points', ha='center', fontsize=9)
    axes[0].set_ylim(0, max(1, max(r['rails'] for r in totals)) * 1.35)
    axes[0].set_xticks(range(3), ['Inherited recipe', 'Lower limiter power', 'Limiter + AGC headroom'])
    axes[0].set_ylabel('O1 rail samples')
    axes[0].set_title('Matched calibration 01/02/03: nominal, −6 dB and +6 dB inputs; remaining rails stay visible', loc='left')
    for stream in OUTPUTS:
        x, y = [], []
        for i, cid in enumerate(CASE_IDS, 1):
            r = index.get(('final', cid, stream))
            if r and r['raw_peak_dbfs'] is not None: x.append(i); y.append(r['raw_peak_dbfs'])
        axes[1].plot(x, y, 'o-', color=COLORS[stream], lw=.8, ms=4, label=stream + ' raw')
    adapted = [(i, index.get(('final', cid, 'O0'))) for i, cid in enumerate(CASE_IDS, 1)]
    adapted = [(i, dbfs(r['projected_peak_after_fixed_gain_fs'])) for i, r in adapted if r and r['projected_peak_after_fixed_gain_fs'] > 0]
    axes[1].plot([x for x, _ in adapted], [y for _, y in adapted], '^--', color=COLORS['O0_adapter'], lw=.8, ms=4,
                 label=f"O0 with fixed {20*math.log10(policy['fixed_host_gain']['O0']):g} dB host gain")
    axes[1].axhline(0, color='#962626', lw=.8, ls=':')
    axes[1].set_ylim(top=3)
    axes[1].set_ylabel('Sample peak (dBFS)')
    axes[1].set_title('All final scenes: numerical peak headroom; zero-valued signals have no logarithmic peak', loc='left')
    axes[1].legend(ncol=3, frameon=False, fontsize=9)
    railrows = [index.get(('final', cid, 'O1')) for cid in CASE_IDS]
    bars = axes[2].bar(range(1, 25), [r['rail_samples_per_million'] if r else float('nan') for r in railrows], color=COLORS['O1'], width=.7)
    for bar, row in zip(bars, railrows):
        if row and row['rail_samples']:
            axes[2].annotate(str(row['rail_samples']), (bar.get_x()+bar.get_width()/2, bar.get_height()), xytext=(0, 3), textcoords='offset points', ha='center', fontsize=8)
    axes[2].set_title('Final O1 saturation: raw rail counts above nonzero bars', loc='left')
    axes[2].set_ylabel('Rail samples / million')
    axes[2].set_xlabel('Canonical scene ID (S4_)')
    for ax in axes[1:]: ax.set_xticks(range(1, 25), [f'{i:02}' for i in range(1, 25)]); ax.set_xlim(.3, 24.7)
    for ax in axes: ax.grid(axis='y', alpha=.2); ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle(('PARTIAL — ' if partial else '') + 'S4 output headroom', x=.07, ha='left', fontsize=16, fontweight='bold')
    fig.text(.07, .015, 'Calibration uses the same 01/02/03 inputs across recipes. Accepted final captures use the frozen recipe. A lower rail count is not an ASR/diarization winner.', fontsize=9)
    fig.tight_layout(rect=(.025, .035, .995, .95))
    png = directory / 'figure_01_headroom.png'; data = directory / 'figure_01_headroom.csv'
    save_figure(fig, png); plt.close(fig); write_csv(data, rows)
    return png, data


def text_figure(plt, directory, summary, partial):
    with (REPORT / 'per_case_metrics.csv').open(encoding='utf-8-sig', newline='') as handle:
        cases = list(csv.DictReader(handle))
    fields = ('case_id', 'stream', 'text_status', 'wer', 'cer', 'word_substitutions', 'word_deletions', 'word_insertions',
              'reference_words', 'hypothesis_words', 'empty_reference_insertions', 'empty_reference_words_per_minute', 'scheduled_duration_s')
    rows = [{k: row.get(k) for k in fields} for row in cases]
    index = {(r['case_id'], r['stream']): r for r in rows}
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.4), gridspec_kw={'width_ratios': [3.3, 1.2]})
    for cid in CASE_IDS:
        a, b = (index.get((cid, stream), {}) for stream in OUTPUTS)
        if a.get('text_status') == b.get('text_status') == 'SCORED':
            x = int(cid[-2:]); axes[0].plot([x-.09, x+.09], [100*number(a['wer']), 100*number(b['wer'])], color='#A8A8A8', lw=1)
    for stream, offset in [('O0', -.09), ('O1', .09)]:
        selected = [r for r in rows if r['stream'] == stream and r['text_status'] == 'SCORED']
        axes[0].scatter([int(r['case_id'][-2:])+offset for r in selected], [100*number(r['wer']) for r in selected], color=COLORS[stream], s=30, label=stream, zorder=3)
    limited = sorted({int(r['case_id'][-2:]) for r in rows if r['text_status'] == 'LIMITED'})
    for x in limited: axes[0].axvspan(x-.34, x+.34, color='#D3D3D3', alpha=.5)
    axes[0].set_xticks(range(1, 25), [f'{i:02}' for i in range(1, 25)], fontsize=8)
    axes[0].set_xlim(.4, 24.6); axes[0].set_ylim(bottom=0)
    axes[0].set_xlabel('Canonical scene ID (S4_); shaded scenes have LIMITED overlap scoring')
    axes[0].set_ylabel('WER (%)'); axes[0].legend(ncol=2, frameon=False)
    notes = []
    for stream in OUTPUTS:
        pool = summary['paired_weighted_text'][stream]; counts = pool['word_counts']
        value = f"{100*pool['pooled_wer']:.1f}%" if pool['pooled_wer'] is not None else 'unavailable'
        notes.append(f"{stream}: {value} ({counts['errors']}/{counts['reference_words']} words)")
    axes[0].set_title('Paired nonoverlap transcripts\nPooled matched WER — ' + '  |  '.join(notes), loc='left', fontsize=10)
    empty_ids = sorted({r['case_id'] for r in rows if r['text_status'] == 'EMPTY_REFERENCE'})
    for i, stream in enumerate(OUTPUTS):
        values = [index.get((cid, stream), {}) for cid in empty_ids]
        bars = axes[1].bar([j + (i-.5)*.3 for j in range(len(empty_ids))],
                           [number(r.get('empty_reference_words_per_minute')) or 0 for r in values], width=.27, color=COLORS[stream], label=stream)
        for bar, row in zip(bars, values):
            count = row.get('empty_reference_insertions')
            if count not in ('', None): axes[1].annotate(count, (bar.get_x()+bar.get_width()/2, bar.get_height()), xytext=(0,3), textcoords='offset points', ha='center', fontsize=9)
    axes[1].set_xticks(range(len(empty_ids)), [cid[-2:] + ('\nsilence' if cid == 'S4_22' else '\npoint noise') for cid in empty_ids])
    axes[1].set_ylabel('Inserted words / minute'); axes[1].set_ylim(bottom=0)
    axes[1].set_title('Empty references\nRaw insertion counts above bars', loc='left', fontsize=10)
    for ax in axes: ax.grid(axis='y', alpha=.2); ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle(('PARTIAL — ' if partial else '') + 'S4 paired text baseline', x=.06, ha='left', fontsize=16, fontweight='bold')
    fig.text(.06, .035, 'Pooled scores sum errors and reference words; no averaging per-scene WER. Empty references have undefined WER. Dependent development cases; no output winner or population CI.', fontsize=8.5)
    fig.tight_layout(rect=(.01, .08, 1, .92))
    png = directory / 'figure_02_text.png'; data = directory / 'figure_02_text.csv'
    save_figure(fig, png); plt.close(fig); write_csv(data, rows)
    return png, data


def directions_figure(plt, directory, partial):
    # The scorer supplies the causal reader and already-corrected activity ranges.
    # No samples are convolved and no offset is fitted to expected directions here.
    from s4_spatial_analysis import ReceiptTimeline
    import numpy as np
    rows = []; origins = {}
    fig, axes = plt.subplots(3, 1, figsize=(13.2, 8.6), sharex=True, sharey=True)
    observed = []
    for ax, batch in zip(axes, ('final', 'repeat1', 'repeat2')):
        folder = case_folder('S4_01', partial=partial) if batch == 'final' else REPORT / 'hardware' / batch / 'S4_01'
        paths = [folder / 'spatial_metrics.json', folder / 'capture_metadata.json', folder / 'telemetry/received_telemetry.jsonl']
        if not all(p.exists() for p in paths):
            ax.text(.5, .5, batch + ': evidence unavailable', transform=ax.transAxes, ha='center', va='center')
            ax.set_ylabel('Native degrees'); continue
        spatial, metadata = read(paths[0]), read(paths[1])
        callbacks = metadata['callback_times']
        origin = callbacks[0].get('host_copy_complete_monotonic_ns', callbacks[0]['host_callback_monotonic_ns'])
        end = callbacks[-1].get('host_copy_complete_monotonic_ns', callbacks[-1]['host_callback_monotonic_ns']) + round(callbacks[-1]['frames'] / 48000 * 1e9)
        origins[batch] = origin
        with paths[2].open(encoding='utf-8-sig') as handle:
            timeline = ReceiptTimeline([json.loads(line) for line in handle if line.strip()])
        for stream, color, label in [('selected_processed', '#2463A6', 'Selected processed'), ('raw_auto', '#D36A21', 'Raw auto, energy gated')]:
            intervals = timeline.intervals(stream, origin, end)
            x = [(a-origin)/1e9 for a, _, _ in intervals]
            y = [state['angle_deg'] if state['available'] else np.nan for _, _, state in intervals]
            if intervals:
                x.append((end-origin)/1e9); y.append(y[-1])
            ax.step(x, y, where='post', lw=1.15, color=color, label=label)
            for a, b, state in intervals:
                rows.append({'record_type': 'causal_observation_interval', 'batch': batch, 'stream': stream,
                             'start_s': (a-origin)/1e9, 'stop_s': (b-origin)/1e9,
                             'native_deg': state['angle_deg'] if state['available'] else None,
                             'available': state['available'], 'source_label': None,
                             'manual_interval_lo_deg': None, 'manual_interval_hi_deg': None})
        for label, turn in spatial.get('turns', {}).items():
            if 'source_angle_label' not in turn: continue
            reference = turn['source_angle_label']; low, high = reference['expected_native_interval_deg']
            ranges = turn['host_activity_ranges_ns']
            for a, b in ranges:
                x0, x1 = (a-origin)/1e9, (b-origin)/1e9
                ax.fill_between([x0, x1], [low, low], [high, high], color='#555555', alpha=.20, lw=0)
                rows.append({'record_type': 'manual_source_interval', 'batch': batch, 'stream': 'scoring_reference_only',
                             'start_s': x0, 'stop_s': x1, 'native_deg': reference['expected_native_nominal_deg'],
                             'available': None, 'source_label': label, 'manual_interval_lo_deg': low, 'manual_interval_hi_deg': high})
            if ranges:
                center = ((ranges[0][0]+ranges[-1][1])/2-origin)/1e9
                ax.text(center, min(174, high+6), label, ha='center', fontsize=9, color='#444444')
        ax.set_title('S4_01 — ' + ('final capture' if batch == 'final' else batch.replace('repeat', 'repeat ')), loc='left', fontsize=11)
        ax.set_ylabel('Native degrees')
        for y in (60, 120): ax.axhline(y, color='#999999', ls=':', lw=.7)
        ax.set_yticks([0, 60, 90, 120, 180]); ax.set_ylim(-4, 186)
        ax.grid(axis='x', alpha=.2); ax.spines[['top', 'right']].set_visible(False)
        observed.extend(bind(path) for path in paths)
    axes[-1].set_xlabel('Seconds since the first capture callback became available on the host')
    handles, labels = axes[0].get_legend_handles_labels()
    if handles: fig.legend(handles, labels, loc='upper right', bbox_to_anchor=(.985, .935), ncol=2, frameon=False, fontsize=9)
    fig.suptitle(('PARTIAL — ' if partial else '') + 'Nominal A→B→A: causal direction availability across repetitions', x=.07, ha='left', fontsize=15, fontweight='bold')
    fig.text(.07, .022, 'Gray bands: complete nominally folded manual ±5° source intervals on estimated activity support. Gaps: cue unavailable. No future interpolation or fitted angle shift. DSP time remains unknown.', fontsize=8.5)
    fig.tight_layout(rect=(.02, .055, 1, .95))
    png = directory / 'figure_03_directions.png'; data = directory / 'figure_03_directions.csv'
    save_figure(fig, png); plt.close(fig)
    write_csv(data, rows, ['record_type', 'batch', 'stream', 'start_s', 'stop_s', 'native_deg', 'available', 'source_label', 'manual_interval_lo_deg', 'manual_interval_hi_deg'])
    return png, data, {'capture_callback_origins_monotonic_ns': origins, 'input_bindings': observed}


def run(partial=False):
    summary = read(REPORT / 'summary_metrics.json')
    if not partial and summary['status'] != 'COMPLETE_EVIDENCE_COUNTS':
        raise RuntimeError('Full plots require complete aggregation; --partial must explicitly label partial evidence')
    check_storage()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 11,
                         'axes.labelsize': 10, 'savefig.bbox': None, 'figure.dpi': 120})
    directory = REPORT / 'plots'; directory.mkdir(exist_ok=True)
    headroom = headroom_figure(plt, directory, summary['output_level_policy'], partial)
    text = text_figure(plt, directory, summary, partial)
    directions = directions_figure(plt, directory, partial)
    products = [*headroom, *text, *directions[:2]]
    manifest = {'created_utc': now(), 'status': 'PARTIAL' if partial else 'GENERATED_FROM_COMPLETE_EVIDENCE',
                'figure_count': 3, 'figures_and_small_csvs': [bind(path) for path in products],
                'source_summary': bind(REPORT / 'summary_metrics.json'), 'source_case_csv': bind(REPORT / 'per_case_metrics.csv'),
                'directions': directions[2], 'code': bind(Path(__file__)),
                'claims_excluded': ['S5 output winner', 'S6 cue benefit', 'full DER', 'source-independent population confidence', 'calibrated angular accuracy or device latency']}
    save(directory / 'FIGURE_INDEX.json', manifest)
    check_storage()
    print(json.dumps({'status': manifest['status'], 'figure_count': 3, 'directory': str(directory), 'bytes': sum(p.stat().st_size for p in products)}, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args(); run(args.partial)
