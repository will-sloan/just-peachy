"""Small operator catalogue over immutable internal profiles. See README_OPERATOR_PROFILES.md."""
from __future__ import annotations

from dataclasses import dataclass
import json

from profiles import RuntimeSelection, get_profile


DEFAULT_RECIPE = 'balanced'
ATTRIBUTION_PRESETS = ('Standard', 'Sparse clean turns', 'Late labels', 'Sparse + late')
_GEOMETRIES = {
    'current_delayed': (264, 1, 1, 0, 264, 188, 'v3-offline', -1),
    'chunk52_threads2': (52, 1, 0, 80, 264, 40, 'v3-streaming', -1),
    'candidate_3_compact': (37, 1, 0, 40, 128, 40, 'v3-streaming', -1),
}


@dataclass(frozen=True)
class OperatorProfile:
    id: str
    label: str
    diarizer: str
    embedding: str
    nemotron_profile: str | None = None

    def selection(self, source='live', *, embedding_schedule='continuous',
                  speaker_attribution='retained', embedding_refresh_seconds=2.0,
                  revision_window_seconds=30):
        """Source/scheduling are independent; no second diarizer or fallback."""
        profile = _profile(self.nemotron_profile) if self.diarizer == 'nemotron' else None
        experimental = bool(profile and (profile.experimental or
            embedding_schedule != 'continuous' or speaker_attribution != 'retained'))
        selection = RuntimeSelection(diarizer=self.diarizer, embedding=self.embedding,
            input_source=source, nemotron_profile=self.nemotron_profile,
            allow_experimental=experimental, embedding_schedule=embedding_schedule,
            speaker_attribution=speaker_attribution,
            embedding_refresh_seconds=embedding_refresh_seconds,
            revision_window_seconds=revision_window_seconds)
        selection.validate()
        return selection

    def descriptor(self):
        profile = _profile(self.nemotron_profile) if self.diarizer == 'nemotron' else None
        return dict(id=self.id, label=self.label, diarizer=self.diarizer,
            embedding=self.embedding, nemotron_profile=self.nemotron_profile,
            default_recipe=DEFAULT_RECIPE, sources=['live', 'saved'],
            experimental=bool(profile and profile.experimental),
            status=('Experimental · whole-application real-time unqualified'
                    if profile and profile.experimental else
                    'Reference · larger speaker-output delay' if profile else 'Reference baseline'),
            profile=profile.descriptor() if profile else None,
            selection=self.selection().validate(), native_qualification_claimed=False)


_OPERATOR = (
    OperatorProfile('pyannote_redimnet', 'Pyannote + ReDimNet', 'pyannote', 'redimnet'),
    OperatorProfile('pyannote_titanet', 'Pyannote + TitaNet', 'pyannote', 'titanet'),
    OperatorProfile('delayed_redimnet', 'Nemotron Delayed + ReDimNet', 'nemotron', 'redimnet', 'current_delayed'),
    OperatorProfile('delayed_titanet', 'Nemotron Delayed + TitaNet', 'nemotron', 'titanet', 'current_delayed'),
    OperatorProfile('chunk52_2t_redimnet', 'Nemotron Chunk52 2T + ReDimNet', 'nemotron', 'redimnet', 'chunk52_threads2'),
    OperatorProfile('chunk52_2t_titanet', 'Nemotron Chunk52 2T + TitaNet', 'nemotron', 'titanet', 'chunk52_threads2'),
)
_COMPACT = (
    OperatorProfile('compact3_redimnet', 'Nemotron Compact 3s + ReDimNet', 'nemotron', 'redimnet', 'candidate_3_compact'),
    OperatorProfile('compact3_titanet', 'Nemotron Compact 3s + TitaNet', 'nemotron', 'titanet', 'candidate_3_compact'),
)


def _profile(identifier):
    profile = get_profile(identifier)
    geometry = profile.geometry
    actual = tuple(getattr(geometry, key) for key in ('chunk_frames', 'right_context_frames',
        'left_context_frames', 'fifo_frames', 'spkcache_frames', 'update_period_frames', 'preset', 'gpu'))
    if actual != _GEOMETRIES[identifier]:
        raise ValueError('Retained operator geometry changed: ' + identifier)
    if identifier == 'chunk52_threads2':
        descriptor = profile.descriptor()
        if (descriptor.get('required_native_variant') != 'chunk52-native-threads2' or
                descriptor.get('configured_native_graph_threads') != 2):
            raise ValueError('Chunk52 requires the separately pinned two-thread native variant')
    return profile


def catalog():
    """Six intended operator rows; this does not grant native admission."""
    from application_contract import default
    if any(default(embedding)['recipe'] != DEFAULT_RECIPE for embedding in ('redimnet', 'titanet')):
        raise ValueError('Retained default recipe changed; review operator catalogue')
    return [row.descriptor() for row in _OPERATOR]


def hidden_compact_candidates():
    """Separate review candidates, never concatenated into the normal chooser."""
    return [dict(row.descriptor(), operator_visible=False,
                 promotion_requires='Current-release native Live application smoke with complete source/model/closure evidence')
            for row in _COMPACT]


def selection_for(identifier, source='live', **options):
    for row in _OPERATOR:
        if row.id == identifier:
            return row.selection(source, **options)
    raise ValueError('Unknown or hidden operator backend; implicit fallback is forbidden')


def attribution_options(preset, diarizer):
    """One compact Advanced preset; existing scheduler/attribution fields only."""
    if preset not in ATTRIBUTION_PRESETS or diarizer not in ('pyannote', 'nemotron'):
        raise ValueError('Known attribution preset and diarizer required')
    if diarizer != 'nemotron' and preset != 'Standard':
        raise ValueError('Sparse/late attribution needs a named Nemotron backend')
    return dict(embedding_schedule='sparse_clean_turn' if preset in ('Sparse clean turns', 'Sparse + late') else 'continuous',
                speaker_attribution='single_d1_late_labels' if preset in ('Late labels', 'Sparse + late') else 'retained')


def _approved(selection, kind, document):
    """Retain the production allowlist; qualification stays in the session gate."""
    if kind == 'production':
        from release_authorization import selection_key
        if selection_key(selection) not in document['allowed_selections']:
            raise PermissionError('This backend/source is not in this release admission')


def choose(root, manager, config, *, fullscreen_after_map):
    """Portrait chooser only; returns selection while capture remains idle."""
    import tkinter as tk
    from tkinter import ttk
    from release_authorization import authorization
    rows = catalog()
    kind, document = authorization(manager.binding)
    colors = config['themes']['Dark']
    root.title('Just Peachy · choose backend')
    root.geometry('480x800+0+0')
    root.configure(bg=colors['background'])
    fullscreen_after_map(root)
    tk.Label(root, text='Just Peachy', font=('DejaVu Sans', 24, 'bold'),
             fg=colors['text'], bg=colors['background']).pack(pady=(14, 4))
    tk.Label(root, text='Choose a backend', font=('DejaVu Sans', 15),
             fg=colors['text'], bg=colors['background']).pack(pady=4)
    frame = tk.Frame(root, bg=colors['background'])
    frame.pack(fill='both', expand=True, padx=14, pady=6)
    selected_id = tk.StringVar(value=rows[0]['id'])
    source = tk.StringVar(value='live')
    detail = tk.StringVar()
    error = tk.StringVar()
    advanced = tk.BooleanVar(value=False)
    attribution = tk.StringVar(value='Standard')
    selected = [None]

    def update_details(*unused):
        error.set('')
        row = next(row for row in rows if row['id'] == selected_id.get())
        enabled = row['diarizer'] == 'nemotron'
        attribution_control.configure(state='readonly' if enabled else 'disabled')
        advanced_toggle.configure(state='normal' if enabled else 'disabled',
            text='Advanced attribution '+('▾' if advanced.get() else '▸') if enabled else 'Advanced attribution · Nemotron only')
        if not enabled:
            if attribution.get() != 'Standard':
                attribution.set('Standard')
            advanced.set(False)
            advanced_body.pack_forget()
        detail.set(row['status'] if advanced.get() else row['status'] +
                   '\nDefault recipe: Balanced · '+('Live microphone' if source.get() == 'live' else 'Saved WAV'))

    def toggle_advanced():
        advanced.set(not advanced.get())
        if advanced.get():
            advanced_body.pack(fill='x', padx=14, pady=2, before=detail_label)
        else:
            advanced_body.pack_forget()
        update_details()

    for row in rows:
        tk.Radiobutton(frame, text=row['label'], value=row['id'], variable=selected_id,
            font=('DejaVu Sans', 13), anchor='w', justify='left', wraplength=395,
            indicatoron=False, padx=9, pady=12, bg=colors['surface'],
            fg=colors['text'], selectcolor=colors['selected'],
            activebackground=colors['selected'], activeforeground=colors['text'],
            command=update_details).pack(fill='x', pady=3)
    source_frame = tk.Frame(root, bg=colors['background'])
    source_frame.pack(fill='x', padx=14, pady=5)
    for value, label in (('live', 'Live microphone'), ('saved', 'Saved WAV')):
        tk.Radiobutton(source_frame, text=label, value=value, variable=source,
            font=('DejaVu Sans', 13), indicatoron=False, padx=8, pady=10,
            bg=colors['surface'], fg=colors['text'], selectcolor=colors['selected'],
            activebackground=colors['selected'], activeforeground=colors['text'],
            command=update_details).pack(side='left', fill='x', expand=True, padx=2)
    advanced_toggle = tk.Button(root, text='Advanced attribution ▸', command=toggle_advanced,
        font=('DejaVu Sans', 11), bg=colors['surface'], fg=colors['text'])
    advanced_toggle.pack(fill='x', padx=14, pady=2)
    advanced_body = tk.Frame(root, bg=colors['background'])
    attribution_control = ttk.Combobox(advanced_body, textvariable=attribution,
        values=ATTRIBUTION_PRESETS, state='readonly', font=('DejaVu Sans', 11))
    attribution_control.pack(fill='x')
    detail_label = tk.Label(root, textvariable=detail, wraplength=440, justify='left',
             font=('DejaVu Sans', 10), fg=colors['muted'],
             bg=colors['background'])
    detail_label.pack(fill='x', padx=14, pady=4)
    tk.Label(root, textvariable=error, wraplength=440, justify='left',
             fg=colors['text'], bg=colors['background']).pack(fill='x', padx=14)

    def accept():
        try:
            row = next(row for row in rows if row['id'] == selected_id.get())
            options = attribution_options(attribution.get(), row['diarizer'])
            selection = selection_for(row['id'], source.get(), **options)
            _approved(selection, kind, document)
        except (ValueError, PermissionError) as exc:
            error.set(str(exc))
            return
        selected[0] = selection
        root.quit()

    tk.Button(root, text='Open Application', command=accept, height=2,
              font=('DejaVu Sans', 16), bg=colors['accent'],
              fg=colors['accent_text']).pack(fill='x', padx=14, pady=7)
    tk.Button(root, text='Exit to desktop', command=root.quit, height=2,
              font=('DejaVu Sans', 13)).pack(fill='x', padx=14, pady=(0, 10))
    root.protocol('WM_DELETE_WINDOW', root.quit)
    attribution.trace_add('write', update_details)
    update_details()
    root.mainloop()
    return selected[0]


def check():
    """Focused selection/geometry invariants; no GUI or model construction."""
    rows = catalog()
    assert len(rows) == len({row['id'] for row in rows}) == 6
    expected = [('pyannote', 'redimnet', None), ('pyannote', 'titanet', None),
                ('nemotron', 'redimnet', 'current_delayed'), ('nemotron', 'titanet', 'current_delayed'),
                ('nemotron', 'redimnet', 'chunk52_threads2'), ('nemotron', 'titanet', 'chunk52_threads2')]
    for row, pins in zip(rows, expected):
        assert (row['diarizer'], row['embedding'], row['nemotron_profile']) == pins
        for source in ('live', 'saved'):
            chosen = selection_for(row['id'], source)
            assert chosen.input_source == source and not chosen.optional_d1_refiner
            assert not chosen.provisional_correction and chosen.embedding != 'anonymous'
            assert chosen.validate()['nemotron_profile'] == pins[2]
    for identifier in ('compact3_redimnet', 'streaming', 'anonymous'):
        try:
            selection_for(identifier)
        except ValueError:
            pass
        else:
            raise AssertionError('Hidden profile entered the normal catalogue')
    from profiles import catalog as internal_catalog
    assert {'streaming', 'official_ultra_low', 'candidate_3_compact'} <= {row['id'] for row in internal_catalog()}
    assert all(row['operator_visible'] is False for row in hidden_compact_candidates())
    chosen = selection_for('delayed_titanet', 'saved', embedding_schedule='sparse_clean_turn',
                           speaker_attribution='single_d1_late_labels')
    assert chosen.allow_experimental and not chosen.optional_d1_refiner
    for row in rows:
        presets = ATTRIBUTION_PRESETS if row['diarizer'] == 'nemotron' else ('Standard',)
        for preset in presets:
            chosen = selection_for(row['id'], **attribution_options(preset, row['diarizer']))
            assert not chosen.optional_d1_refiner and not chosen.provisional_correction
            assert (chosen.embedding_schedule == 'sparse_clean_turn') == ('Sparse' in preset)
            assert (chosen.speaker_attribution == 'single_d1_late_labels') == ('late' in preset.lower())
    try:
        attribution_options('Late labels', 'pyannote')
    except ValueError:
        pass
    else:
        raise AssertionError('Nemotron attribution accepted for Pyannote')
    return dict(status='PASS_OPERATOR_SELECTION_INVARIANTS', independent_selections=12,
                hidden_rejections=3, retained_internal_features=True, attribution_preset_selections=18,
                native_execution=False, gui_execution=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check() if args.check else dict(operator=catalog(),
                     hidden_compact=hidden_compact_candidates()), indent=2, allow_nan=False))
