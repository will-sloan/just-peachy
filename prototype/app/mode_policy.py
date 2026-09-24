"""Product roster/Unknown semantics and bounded existing parameters. See README_ROSTER.md."""
import math

SEAT_MODES={'assigned_direction','assigned_hybrid'}
SPATIAL_PARENTS={'spatial_assisted':'C079','strongly_spatial_assisted':'C060',
                 'spatial_selected':'C079','strongly_spatial_selected':'C060',
                 'assigned_direction':'C079','assigned_hybrid':'C079'}
SELECTED_MODES={'selected_focus','selected_closed','spatial_selected','strongly_spatial_selected','assigned_hybrid'}
NUMBERED_MODES={'anonymous_conversation','open_with_names'}
NAMED_MODES={'enrolled_names','open_with_names',*SELECTED_MODES,*SPATIAL_PARENTS}


def definition(title,full,roster,unknown,description,*,advanced=False,parent='C065/C067 + C088',symbol='◇'):
    return dict(label=title,full_name=full,roster=roster,unknown_policy=unknown,description=description,
        advanced=advanced,parent=parent,symbol=symbol,status='simulation-supported' if symbol=='✓' else 'experimental',
        visibility='All captions; optional highlighting/hiding is a separate display feature',
        failure_conditions=(['Device/ASR failure is explicit; no identity inference'] if unknown=='neutral' else
            ['No valid voice evidence keeps captions pending/unavailable; overlap is not word alignment']+
            (['Missing/incompatible selected UUID references block identification'] if roster=='selected' else
             ['No enrollments means Unknown; an entirely tap-incompatible store blocks named startup'] if roster=='all' else [])))


MODE_METADATA={
 'caption_only':definition('Just Transcription','Just Transcription','none','neutral',
     'All words; no speaker inference or personal lookup.',parent='S7 C065/M0',symbol='✓'),
 'enrolled_names':definition('All enrolled · one Unknown','ID from ALL Enrolled names - Constant Unknown','all','constant',
     'Compare all tap-compatible enrolled people. Inadequate or conflicting voice evidence stays Unknown.'),
 'selected_focus':definition('Selected names · one Unknown','ID from SELECTED names - Constant Unknown','selected','constant',
     'Only selected compatible UUIDs enter matching. Outsiders can remain Unknown. All captions stay visible.'),
 'selected_closed':definition('Selected · closed group','ID from SELECTED names - Closed group (Always assign)','selected','closed',
     'Always displays a selected name. Valid voice picks its cosine winner; missing evidence uses an assumed same-utterance/recent name or the first roster entry. Assumed labels never train identity. Outsiders/overlap can be misnamed.'),
 'spatial_assisted':definition('Spatial · all enrolled','Spatial-assisted - ALL Enrolled names - Constant Unknown','all','constant',
     'C079 directions/position memory support voice association; C088 names still require voice. Missing cues fall back to voice.',parent='C079 + C065/C067 + C088'),
 'strongly_spatial_assisted':definition('Strong spatial · all enrolled','Strongly Spatial-assisted - ALL Enrolled names - Constant Unknown','all','constant',
     'Retained C060 stronger spatial weight; voice conflicts, freshness, relocation and decay remain active. Experimental.',parent='C060 + C065/C067 + C088'),
 'spatial_selected':definition('Spatial · selected names','Spatial-assisted - SELECTED names - Constant Unknown','selected','constant',
     'Same C079 method with only selected compatible references; all captions retained.',parent='C079 + C065/C067 + C088'),
 'strongly_spatial_selected':definition('Strong spatial · selected','Strongly Spatial-assisted - SELECTED names - Constant Unknown','selected','constant',
     'Same C060 stronger method with only selected compatible references; all captions retained.',parent='C060 + C065/C067 + C088'),
 'assigned_direction':definition('Seats · direction only','Assigned seats - Direction only (closed seating)','assigned seats','seat assumption',
     'Fresh speech-gated direction selects a unique assigned region. Closed-table/no-movement assumption, not verified voice identity. Missing/stale/ambiguous directions remain unavailable.',parent='C079 speech/causal direction gates + manual seating assumption'),
 'assigned_hybrid':definition('Seats · voice + direction','Assigned seats - Voice + direction + Unknown','selected','constant',
     'Assigned UUID voice gallery plus C079 soft / C060 strong seat prior. Unknown remains; voice disagreement releases spatial trust. Missing seats/directions are explicitly reported.',parent='C088 naming + retained C079/C060 joint score'),
 'anonymous_conversation':definition('Numbered Unknowns','Numbered Unknowns','none','numbered',
     'Advanced comparison: anonymous voice continuity only, no personal gallery. Tracks can split or merge.',advanced=True,parent='S7 C065/M1',symbol='✓'),
 'open_with_names':definition('All enrolled · numbered Unknowns','ID from ALL Enrolled names - Numbered Unknowns','all','numbered',
     'Advanced comparison: cautious names plus numbered anonymous continuity.',advanced=True),
}
MODE_METADATA['selected_closed']['failure_conditions']=[
    'Missing/incompatible selected UUID references block identification',
    'Every new caption gets a selected display name; missing voice is explicitly assumed, not verified',
    'Without any usable same-utterance/recent voice match, the first selected-gallery entry is an arbitrary marked fallback',
    'Overlap and outsiders can be misnamed; no word-level identity or enrollment evidence is implied']
for key in SEAT_MODES:
    MODE_METADATA[key]['failure_conditions'] = ['Manual Apply anchors this session only; saved template is not a valid physical anchor',
        'Linear 0–180 degrees cannot distinguish front/back; overlapping seat regions remain ambiguous',
        'Missing/stale direction, model speech/overlap rejection or multiple active bearings never force a seat name',
        'Music can fool speech detectors; no verified live seat-recognition accuracy',
        'Hybrid may explicitly use strong voice after spatial trust is released; direction-only cannot use a voice fallback']
MODES=tuple(MODE_METADATA)
PARAMETERS={
 'score_threshold':dict(section='identity',minimum=.35,maximum=.75,step=.02,label='Open-set cosine threshold'),
 'margin_threshold':dict(section='identity',minimum=0.,maximum=.15,step=.01,label='Next-candidate margin'),
 'joint_spatial_weight':dict(section='tracker',minimum=0.,maximum=1.2,step=.1,label='Spatial association weight'),
}


def validate_overrides(values):
    if not isinstance(values,dict) or set(values)-PARAMETERS.keys():raise ValueError('Unsupported developer parameter')
    for key,value in values.items():
        p=PARAMETERS[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not p['minimum']<=value<=p['maximum']:
            raise ValueError(f"{key} must be within [{p['minimum']}, {p['maximum']}]")
    return dict(values)


def apply_overrides(profile,mode,values):
    for key,value in validate_overrides(values or {}).items():
        if PARAMETERS[key]['section']=='identity' and (mode not in NAMED_MODES or mode=='assigned_direction'):continue
        if key=='joint_spatial_weight' and (mode not in SPATIAL_PARENTS or mode=='assigned_direction'):continue
        profile[PARAMETERS[key]['section']][key]=float(value)
    return profile
