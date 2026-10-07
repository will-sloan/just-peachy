"""Evidence-bound D1 method controls. See README_D1_METHOD_CONTROLS_V1.md."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import d1_modes_v1 as modes

CONTRACT_SHA256 = '1ae32a068914370a4c237a5a0545c9452fd56c95346b8a8f9b091b39bdf2d629'

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

class MethodCatalog:
    def __init__(self, contract_path, evidence_path):
        raw = Path(contract_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
            raise ValueError('Changed method contract')
        contract = json.loads(raw)
        raw = Path(evidence_path).read_bytes()
        if len(raw) > 256*1024 or hashlib.sha256(raw).hexdigest() != contract['evidence_sha256']:
            raise ValueError('Changed method evidence')
        evidence = json.loads(raw)
        if contract['catalog_sha256'] != modes.CATALOG_SHA256:
            raise ValueError('Changed native mode catalogue')
        self._profiles = {}
        for mode_id, binding in contract['modes'].items():
            mode = modes.select(mode_id)
            if binding['geometry'] != mode['geometry'] or binding['assets_sha256'] != hashlib.sha256(canonical(mode['assets']).encode()).hexdigest():
                raise ValueError('Changed mode assets/geometry')
            pair = evidence['pairs'][mode_id]
            a = pair['a76']['documents'];g = pair['generic']['documents']
            ar = a['REVIEW.json'];gr = g['REVIEW.json']
            for review in [ar, gr]:
                if review['status'] != 'PASS_NATIVE_RECIPE_FUNCTIONAL_RESOURCE_ONLY' or not all(review[k] for k in ['all_samples_and_frames_passed', 'model_closed', 'owner_closed']):
                    raise ValueError('Unqualified retained comparison')
            if ar['observed_c_abi_geometry'] != gr['observed_c_abi_geometry'] or ar['observed_c_abi_geometry'] != mode['geometry'] or ar['independent_generic_max_abs'] > 1e-5:
                raise ValueError('Comparison is not same-geometry conformant')
            if a['CONFIG.json']['reference_result_sha256'] != gr['result_sha256']:
                raise ValueError('Wrong comparator')
            ai = {x['name']:x for x in a['INPUTS.json']['files']}
            gi = {x['name']:x for x in g['INPUTS.json']['files']}
            for name in pair['matched_inputs']:
                if ai[name] != gi[name]:raise ValueError('Changed matched input')
            cpu = next(x for x in mode['assets'] if x['name'] == 'nemo-arm64/lib/libggml-cpu.so')
            if ai[cpu['name']]['sha256'] != cpu['sha256'] or cpu['sha256'] != contract['kernel_cpu_library_sha256']:
                raise ValueError('Selected CPU kernel differs from measured kernel')
            am = next(x for x in ar['metrics'] if x['case'] == 'saved_full')
            gm = next(x for x in gr['metrics'] if x['case'] == 'saved_full')
            if (am['samples'], am['frames']) != (715127, 4470) or (gm['samples'], gm['frames']) != (715127, 4470):
                raise ValueError('Unmatched work')
            if not all(math.isfinite(x['elapsed_seconds']) and x['elapsed_seconds'] > 0 for x in [am, gm]):
                raise ValueError('Invalid retained timing')
            app = evidence['applications'][mode_id]
            if app['receipt']['status'] != 'PASS_INSTALLED_D1_SAVED_SELECTION_START_STOP_ONLY':
                raise ValueError('Missing saved application evidence')
            main = next(x for x in mode['assets'] if x['name'] == 'nemo-arm64/lib/libnemo_speech_asr.so')
            self._profiles[mode_id] = dict(schema='d1-implemented-methods.v1', mode=mode_id,
                contract_sha256=CONTRACT_SHA256, catalog_sha256=modes.CATALOG_SHA256,
                assets_sha256=binding['assets_sha256'], geometry=deepcopy(mode['geometry']),
                fixed_native_profile=True, selectable_kernel_variants=False, kernel='lane-preserving Cortex-A76',
                cpu_library_sha256=cpu['sha256'], main_library_sha256=main['sha256'],
                resources=dict(executable_graph_lru=binding['compute_graph_lru'], metadata_arena_mib=binding['metadata_arena_mib'],
                    thread_stack_mib=1, native_threads=1, gpu=False, speaker_history_shortened=False,
                    effect='resource bounds; no separate measured speedup'),
                retained_kernel_comparison=dict(generic_run=pair['generic']['run'], a76_run=pair['a76']['run'],
                    generic_seconds=gm['elapsed_seconds'], a76_seconds=am['elapsed_seconds'],
                    less_wall_percent=100*(1-am['elapsed_seconds']/gm['elapsed_seconds']),
                    source_seconds=am['audio_seconds'], source_samples=am['samples'],
                    max_abs=ar['independent_generic_max_abs'], tolerance=1e-5,
                    selected_main_equals_comparison_main=main['sha256']==ai[main['name']]['sha256'],
                    original_rc5_concurrent=True, measured_application_speedup=False,
                    sustained_speedup=False, cross_geometry_speedup=False),
                saved_app_evidence=app['run'], live_start_available=False,
                all_audio_retained=True, unavailable=deepcopy(contract['unavailable']))

    def request(self, mode, method='qualified-native'):
        if type(mode) is not str or mode not in self._profiles or method != 'qualified-native':
            raise ValueError('Method unavailable for this mode')
        return deepcopy(self._profiles[mode])

    def validate(self, mode, request):
        if canonical(request) != canonical(self.request(mode)):
            raise ValueError('Changed method profile; select a fresh exact profile')
        return deepcopy(request)

def sections(profile):
    c = profile['retained_kernel_comparison'];r = profile['resources']
    lineage = 'Selected main matches this comparison.' if c['selected_main_equals_comparison_main'] else 'Current LRU1 main differs; this measures the earlier kernel pair only.'
    return dict(kernel=(f"{profile['mode']}: {profile['kernel']} (fixed profile).\n"
        f"Retained same-geometry {c['source_seconds']:.3f}s file: generic {c['generic_seconds']:.3f}s; A76 {c['a76_seconds']:.3f}s ({c['less_wall_percent']:.1f}% less work time).\n"
        f"Max difference {c['max_abs']:g}, gate 1e-5. Original app concurrent. {lineage}\n"
        'No application/sustained/cross-mode speedup or speaker-accuracy claim.'),
        resources=(f"Executable graph cache: {r['executable_graph_lru']} entries; speaker/FIFO history unchanged.\n"
        f"Metadata arena: {str(r['metadata_arena_mib'])+' MiB' if r['metadata_arena_mib'] is not None else 'not specified by this mode catalogue'}. "
        'Launch envelope: one native thread, 1 MiB stacks, GPU off.\nResource bounds are not separate measured speedups. Another run requires a fresh process and independent session.'),
        unavailable=('Unavailable: '+', '.join(profile['unavailable'])+'.\nAll audio is retained. ONNX waveform state parity is unresolved; applied skipping/pools lack required gates.\n'
        f"Prior saved application evidence: {profile['saved_app_evidence']}. Live Start remains unavailable."))

class MethodsPanel:
    def __init__(self, parent, profile):
        import tkinter as tk
        self.frame = tk.Frame(parent)
        self.text = tk.Label(self.frame, justify='left', wraplength=360)
        self.text.pack(fill='x')
        self.buttons = {};self.profile = deepcopy(profile);self.views = sections(self.profile)
        for key, label in [('kernel', 'Kernel measurements'), ('resources', 'Resource bounds'), ('unavailable', 'Unavailable methods')]:
            button = tk.Button(self.frame, text=label, command=lambda k=key:self.show(k))
            button.pack(fill='x');self.buttons[key] = button
        self.show('kernel')
    def show(self, key):
        self.text.configure(text=self.views[key]);self.section = key

def controller_class(BaseSaved, catalog):
    """Fresh adapter; valid Start delegates only after exact method binding."""
    class WithMethods(BaseSaved):
        def _do_d1_select(self, mode):
            profile = catalog.request(mode)
            with self.d1_lock:
                super()._do_d1_select(mode)
                self.d1_method_profile = profile
        def _do_d1_start(self):
            with self.d1_lock:
                selected = self.d1_selected
                if selected is None:raise ValueError('Select a diarizer mode first')
                mode = selected['selection']['id'];native = modes.select(mode)
                expected = dict(schema='d1-saved-mode-selection.v1', selection=dict(id=mode,
                    catalog_sha256=modes.CATALOG_SHA256, geometry=native['geometry'], retained_run=native['retained_run']),
                    requires_fresh_process=True, requires_independent_session=True, source_scope='saved-input-only', live_start_available=False)
                if canonical(selected) != canonical(expected):raise ValueError('Changed saved mode selection')
                catalog.validate(mode, getattr(self, 'd1_method_profile', None))
                return super()._do_d1_start()
        def d1_snapshot(self):
            with self.d1_lock:
                value = super().d1_snapshot()
                value['implemented_methods'] = deepcopy(getattr(self, 'd1_method_profile', None))
                return value
    return WithMethods

def ui_class(BaseSaved):
    class WithMethods(BaseSaved):
        def _page(self, title, *args, **kwargs):
            body = super()._page(title, *args, **kwargs)
            if title == 'Diarizer saved test':
                holder = self.button(body, 'Implementation and measurements', self.show_d1_methods, key='d1_methods')
                holder.pack(fill='x')
            return body
        def show_d1_methods(self):
            import tkinter as tk
            body = self._page('Diarizer methods')
            profile = self.controller.d1_snapshot()['implemented_methods']
            if profile is None:
                tk.Label(body, text='Choose a diarizer mode first.').pack()
            else:
                self.d1_method_panel = MethodsPanel(body, profile);self.d1_method_panel.frame.pack(fill='both')
            self.button(body, 'Back to saved controls', self.show_d1_saved).pack(fill='x')
            self._page_update = lambda:None
    return WithMethods
