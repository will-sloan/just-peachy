"""Export actual default mode/recipe/tap configurations without models. See README_ROSTER.md."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.mode_policy import MODE_METADATA,PARAMETERS
from app.pipeline import RECIPES,effective_profile
from app.seats import DEFAULT_TOLERANCE,MAPPING


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/MODE_MATRIX.json');args=parser.parse_args()
    matrix=dict(schema='just-peachy.mode-matrix.v2',scope='Tasks 04–05 modes including assigned seats; default parameters, no personal IDs or inference',
        modes=deepcopy(MODE_METADATA),recipes=deepcopy(RECIPES),developer_parameter_bounds=deepcopy(PARAMETERS),
        seat_defaults=dict(tolerance_deg=DEFAULT_TOLERANCE,tolerance_range=[1,45],angle_range=[0,180],max_people=16,
            strength='soft',hybrid_strength_parents=dict(soft='C079',strong='C060'),direction_only_parent='C079',
            input_cue_max_age_sec=.25,observed_decision_cue_max_age_sec=.75,mapping=MAPPING,
            template_auto_anchor=False,motion_sensor=None,manual_seats_do_not_steer=True),
        notes=['Raw cosine is not probability. No simulation score gates experimental selection.',
            'Selected gallery is UUID-filtered before model lookup. Closed names can be user assumptions.',
            'Display highlight/hide does not change the matching gallery.',
            'Per-session effective overrides/roster/gallery binding are exported in prototype_mode_configuration and linked epoch metadata.'],
        profiles={},seat_strong_variants={},bindings={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for name in ('config/assets.json','config/s7_profiles.json','config/parent_C067.json','config/parent_C079.json',
                         'config/parent_C060.json','config/parent_B36.json','app/mode_policy.py','app/identity_policy.py','app/pipeline.py',
                         'app/controller.py','app/ui.py','app/people.py','app/roster_ui.py','app/seats.py','app/seat_identity.py',
                         'app/seat_controller.py','app/seat_ui.py','app/live_spatial.py','tools/export_mode_matrix.py') for p in [ROOT/name]})
    for recipe in RECIPES:
        for mode in recipe['compatible_modes']:
            for tap in recipe['taps']:
                matrix['profiles']['/'.join((mode,recipe['id'],tap))]=asdict(effective_profile(recipe['id'],mode,tap))
                if mode=='assigned_hybrid':
                    matrix['seat_strong_variants']['/'.join((mode,recipe['id'],tap,'strong'))]=asdict(effective_profile(recipe['id'],mode,tap,seat_strength='strong'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(matrix,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),modes=len(matrix['modes']),effective_profiles=len(matrix['profiles']),strong_seat_variants=len(matrix['seat_strong_variants']))))


if __name__=='__main__':main()
