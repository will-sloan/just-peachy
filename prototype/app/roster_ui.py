"""Touch roster transaction and lightweight score/parameter pages. See README_ROSTER.md."""
import time
from .mode_policy import MODE_METADATA,SELECTED_MODES,NAMED_MODES,PARAMETERS,SPATIAL_PARENTS


def score_text(snapshot):
    rows=snapshot.get('metrics',{}).get('recent_identity_decisions',[])
    heading=f"Current selection: {snapshot.get('recipe')} / {snapshot.get('tap')} · {snapshot.get('state')}\nRaw cosine is not a probability."
    if not rows:return heading+'\nNo voice decision yet; no invented score.'
    payload=rows[-1];decision=payload.get('decision',{});d=decision.get('identity') or {}
    config=payload.get('prototype_configuration') or {}
    observed=MODE_METADATA.get(config.get('mode'),{}).get('label','unavailable')
    age=time.perf_counter()-payload['publication_monotonic_sec'] if payload.get('publication_monotonic_sec') else None
    fmt=lambda x:'—' if x is None else f'{x:.3f}'
    lines=[heading,f"Decision mode: {observed}\nRecipe: {config.get('recipe','—')} / {config.get('tap','—')}",f"Last decision {d.get('assignment','pending').upper()} · age {fmt(age)}s",
        f"Threshold {fmt(d.get('score_threshold'))} · margin {fmt(d.get('next_candidate_margin'))} / {fmt(d.get('margin_threshold'))}"]
    for r in d.get('scores',[])[:3]:lines.append(f"{r['name'][:24]} · {r['profile_id'][:6]}  {r['cosine']:.3f}")
    lines.append(f"Window {fmt(d.get('evidence_duration_sec'))}s · clean {fmt(d.get('clean_duration_sec'))}s · {d.get('evidence_kind','—')}")
    lines.append(f"Unique {fmt(d.get('unique_clean_sec'))}/{fmt(d.get('minimum_unique_sec'))}s · disjoint {d.get('disjoint_count','—')}/{d.get('minimum_disjoint_count','—')}")
    lines.append(f"Fresh at decision {d.get('valid_fresh_voice')} · overlap {d.get('overlap')} · evidence age then {fmt(d.get('evidence_age_sec'))}s")
    availability=d.get('spatial_availability') or {};cue=d.get('spatial') or {}
    contribution=(cue.get('candidate_contributions') or {}).get(str(decision.get('tracker_id')),{}).get('cue_score')
    lines.append(f"Spatial term {fmt(contribution)} · cue age {fmt(availability.get('age_sec'))}s · reliability {fmt(availability.get('reliability'))}")
    lines.append(d.get('reason','Voice evidence pending'))
    seat=d.get('seat')
    if seat:
        lines.append(f"Seat basis: {seat.get('basis')} · anchor valid {seat.get('anchor_valid')} · {seat.get('strength')}")
        lines.append(f"Direction {fmt(seat.get('angle_deg'))}° · age {fmt(seat.get('cue_age_sec'))}s · ambiguous {seat.get('ambiguous')}")
        lines.append(f"Seat gate: {seat.get('reason')} · released priors: {len(seat.get('released',{}))}")
    if d.get('one_selected_person_assumption'):lines.append('One selected person: the label is a user assumption.')
    return '\n'.join(lines)


class RosterUI:
    def show_roster(self,target_mode=None):
        self._roster_target=target_mode
        people=self.snapshot.get('roster_compatibility',self.snapshot.get('people',[]))
        selected=self.snapshot.get('selected_ids' if target_mode else 'display_ids',[])
        self._roster_draft={p['id'] for p in people if p['id'] in selected and p.get('compatible_references',1)>0}
        self._draw_roster()

    def _draw_roster(self):
        self.page='roster';frame=self._page('Choose people',back=self.show_modes)
        target=self._roster_target
        self._paragraph_label(frame,MODE_METADATA[target]['full_name'] if target else 'Display roster · highlighting/filtering only')
        self._paragraph_label(frame,'Checkboxes are a draft. Cancel/Back leaves the active mode and gallery unchanged. '+
            ('Apply stops/drains capture and starts a fresh epoch with the chosen UUIDs.' if target else
             'Apply changes only display membership. Capture and the matching gallery keep running.'),True)
        if target=='selected_closed':self._paragraph_label(frame,'Every caption gets a selected name. Missing voice evidence uses a name marked assumed: same-utterance/recent voice, otherwise the first roster entry. This can misname overlap or outsiders. No assumed label updates enrollment.',True)
        people=self.snapshot.get('roster_compatibility',self.snapshot.get('people',[]))
        for p in people:
            pid=p['id'];compatible=p.get('compatible_references',1)>0
            text=('✓ ' if pid in self._roster_draft else '○ ')+p['name']+f" · {pid[:6]}"
            if not compatible:text+='\nNo compatible '+self.snapshot.get('tap','O0')+' reference'
            def toggle(identifier=pid):self._roster_draft.symmetric_difference_update({identifier});self._draw_roster()
            b=self.button(frame,text,toggle,accent=pid in self._roster_draft,height=65,key='roster_'+pid)
            b.pack(fill='x',padx=self.px(12),pady=self.px(3))
            if not compatible:b.button.configure(state='disabled')
        if not people:self._paragraph_label(frame,'No enrolled people. Add a person and a compatible reference first.')
        def apply():
            if target:ok=self._call('switch',selected_ids=sorted(self._roster_draft),strict=False,mode=target)
            else:ok=self._call('display_roster',sorted(self._roster_draft))
            if ok:self.home()
        button=self.button(frame,'Apply selected roster',apply,accent=True,key='roster_apply')
        button.pack(fill='x',padx=self.px(12),pady=self.px(6))
        if target and not self._roster_draft:button.button.configure(state='disabled')
        self.button(frame,'Cancel · keep current mode',self.show_modes,key='roster_cancel').pack(fill='x',padx=self.px(12),pady=self.px(3))

    def show_identity_scores(self):
        self.page='identity_scores';frame=self._page('Live identity scores',back=self.show_advanced)
        self._paragraph_label(frame,'Developer diagnostics · existing voice/spatial evidence. Scores do not prove identity. Missing values are unavailable, never fabricated.',True)
        label=self.label(frame,'',size='small_font_px');label.pack(fill='x',padx=self.px(12),pady=self.px(8))
        self.button(frame,'Sensitivity / spatial weight',self.show_identity_parameters).pack(fill='x',padx=self.px(12),pady=self.px(6))
        self.button(frame,'Return to captions',self.home).pack(fill='x',padx=self.px(12),pady=self.px(6))
        next_update=0.
        def update():
            nonlocal next_update
            if time.perf_counter()<next_update:return
            next_update=time.perf_counter()+1.;label.configure(text=score_text(self.snapshot))
        self._page_update=update;update()

    def show_identity_parameters(self):
        from .pipeline import effective_profile
        self.page='identity_parameters';frame=self._page('Developer parameters',back=self.show_identity_scores)
        if self.snapshot.get('backend',{}).get('composition',{}).get('n2'):
            self._paragraph_label(frame,'This backend uses a fixed naming policy. Verified names require C-only calibration bound to the exact voice model and preprocessing, query recording conditions, and enrolled roster.',True)
            self._paragraph_label(frame,'Without matching calibration, open groups stay Unknown. A closed group can show a selected name as an assumption when supported voice evidence is available; unresolved, missing or mixed evidence stays Unknown.',True)
            self._paragraph_label(frame,'Calibration gates cannot be changed from this page. Label stability (200ms) is a separate display rule.',True)
            self.button(frame,'Return to captions',self.home).pack(fill='x',padx=self.px(12),pady=self.px(6))
            return
        mode=self.snapshot.get('mode','caption_only');recipe=self.snapshot.get('recipe','fast');tap=self.snapshot.get('tap','O0')
        overrides=self.snapshot.get('identity_overrides',{})
        profile=effective_profile(recipe,mode,tap,overrides,self.snapshot.get('seating',{}).get('strength','soft'))
        self._paragraph_label(frame,'Bounded existing parameters, not a tuning study. Every change starts a safe epoch and is logged. Defaults remain unchanged until you act. Label stability (200ms) is a separate UI rule.',True)
        self._paragraph_label(frame,'Closed group still assigns valid speech below the threshold; the threshold changes accepted versus forced status.',True)
        for key,p in PARAMETERS.items():
            active=mode in (SPATIAL_PARENTS if p['section']=='tracker' else NAMED_MODES) and mode!='assigned_direction'
            current=getattr(getattr(profile,p['section']),key)
            self._paragraph_label(frame,f"{p['label']}: {current:.4f}"+('' if active else ' · inactive in this mode'))
            for sign,label in ((-1,'Decrease'),(1,'Increase')):
                value=max(p['minimum'],min(p['maximum'],current+sign*p['step']))
                def change(k=key,v=value):
                    if self._call('identity_parameters',{**overrides,k:v}):self.show_identity_scores()
                button=self.button(frame,label,change,height=48,key=f'parameter_{key}_{sign}')
                button.pack(fill='x',padx=self.px(12),pady=self.px(2))
                if not active:button.button.configure(state='disabled')
        self.button(frame,'Reset all to frozen recipe defaults',lambda:self._call('identity_parameters',None),key='reset_identity_parameters').pack(fill='x',padx=self.px(12),pady=self.px(6))
