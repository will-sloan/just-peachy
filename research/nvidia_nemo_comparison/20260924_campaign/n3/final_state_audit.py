"""Observe final state even when rendered text needs no rewrite; README_GUI_RECOVERY.md."""
import time


def observe_final_rows(ui, rows, audit):
    for row in rows:
        if not row.get('final') or ui.snapshot.get('strict') and not row.get('selected'):
            continue
        rid=str(row['id']);spans=[str(s) for s in row.get('span_ids') or [rid]]
        if any(s not in audit.spans or not audit.spans[s]['first_applied'] for s in spans):
            raise ValueError('A final observation cannot invent a missing first display')
        if all(audit.spans[s]['first_final'] is not None for s in spans):continue
        shown=ui._row_cache[rid]
        actual=ui.caption_text.get(*ui._marks[rid])
        expected=ui._display_row(row)
        if shown[1]!=expected[1] or shown[1] not in actual:
            raise ValueError('Final state does not match actual Tk caption text')
        receipt=dict(row_id=rid,span_ids=spans,label=shown[0] or expected[0],
            applied_monotonic_sec=time.perf_counter(),pane='history' if rid in ui._history_order else 'active')
        audit.observe(receipt,row,kind='verified_Tk_final_state_after_render')
