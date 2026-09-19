"""Independent scorer V3 admission review. README_S6C_SCORER_V3_REVIEW.md."""
import argparse
import ast
from pathlib import Path
from copy import deepcopy
import s6c_analysis_v3 as core
import s6c_name_analysis_v3 as naming
import s6c_scoring_extensions as extension


def run(output):
    checks=[]
    def yes(name,value):
        if not value:raise AssertionError(name)
        checks.append(name)
    authority=core.bind(core.REPORT/'independent_review/SCORER_V3_ADMISSION_CHECKS_V1.json',
        'dbd76232cc34f662df5b73ecb8d094847914aecaa6dc9e4e92bc04e500506cd9')
    original=core.verified(authority)
    for b in original['sources']:core.bind(b['path'],b['sha256'])
    yes('six_reviewed_source_document_bindings_match',len(original['sources'])==6)
    def function_asts(path):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(path).read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef)}
    for old,new,names in [('s6c_analysis_v2.py','s6c_analysis_v3.py',original['core_unchanged_function_AST']),
        ('s6c_name_analysis.py','s6c_name_analysis_v3.py',original['name_unchanged_function_AST'])]:
        left=function_asts(core.SIM/'scripts'/old);right=function_asts(core.SIM/'scripts'/new)
        for name in names:yes('exact_metric_or_support_AST_'+new+':'+name,left[name]==right[name])
    registry_specs=[(b['path'],b['sha256']) for b in original['registry_bindings'][3:]]
    rows,bindings=extension.registry(registry_specs,234)
    base_rows,base_bindings=extension.registry([],184)
    yes('all_184_original_definitions_exact',rows[:184]==base_rows)
    yes('234_unique_registered_labels',len(rows)==234 and len({r['candidate_id'] for r in rows})==234)
    yes('exact_declared_registry_bindings',bindings==original['registry_bindings'])
    mb=core.bind(core.REPORT/'enrollment/SCORER_GALLERY_MAP.json');base_map=core.verified(mb)
    bank=core.verified(core.bind(core.BANK,core.BANK_SHA));cases={s['case_id'] for s in bank['scenes']}
    specs=[(r['scorer_map']['path'],r['scorer_map']['sha256'],r['completion']['path'],r['completion']['sha256']) for r in original['gallery_extensions']]
    merged,maps=extension.gallery_map(mb,base_map,specs,cases)
    yes('2169_original_gallery_rows_exact',len(base_map['rows'])==2169 and merged['rows'][:2169]==base_map['rows'])
    yes('2175_unique_gallery_assignment_keys',len(merged['rows'])==2175 and len({extension.map_key(r) for r in merged['rows']})==2175)
    yes('exact_gallery_extension_binding_chain',maps==original['gallery_extensions'])
    # Additional exact-authority failures supplement, rather than replace, the
    # published pure candidate/map fixtures. No input file is changed.
    for name,spec in [('changed explicit registry SHA',[(registry_specs[0][0],'0'*64)]),('duplicate registry extension',registry_specs+registry_specs[:1])]:
        try:extension.registry(spec,234)
        except (ValueError,RuntimeError):checks.append('rejected_'+name)
        else:raise AssertionError(name)
    try:extension.registry(registry_specs,233)
    except ValueError:checks.append('rejected_wrong_explicit_final_count')
    else:raise AssertionError('wrong final count accepted')
    core_checks=core.fixtures();name_checks=naming.fixtures()
    yes('core_pure_fixtures_PASS',core_checks['status']=='PASS')
    yes('name_pure_fixtures_PASS',name_checks['status']=='PASS')
    result=dict(status='PASS',schema='s6c_scorer_v3_independent_review.v1',
        sources=original['sources'],admission_authority=authority,
        reviewer_source=core.bind(__file__),reviewer_readme=core.bind(Path(__file__).with_name('README_S6C_SCORER_V3_REVIEW.md')),
        independent_checks=checks,independent_check_count=len(checks),core_fixture_count=len(core_checks['checks']),
        name_fixture_count=len(name_checks['checks']),registry_labels=len(rows),gallery_assignments=len(merged['rows']),
        registry_bindings=bindings,gallery_extensions=maps,
        metric_claim='Core/name metric and support function ASTs unchanged from previously reviewed versions. Explicit source admission and output identity changed; no metric/route substitution.',
        scope='Read-only current source and admitted tiny profile/map chains, actual registry/map assembly, pure fixtures. No prediction scored, model loaded, native job launched or frozen source edited.',
        limits=['Registered labels include historical controls/aliases; 234 is not a neural recipe or algorithm count.',
            'Extension admission hashes input bindings at invocation and does not lock external writers.',
            'Native classification/enrollment quality remains measured separately; map validity does not establish recognition accuracy.',
            'Core exact interrupted per-output resume is supported; completed aggregate namespaces are rejected. Naming requires a fresh directory.'])
    if Path(output).exists():raise ValueError('Preserve existing review receipt; use a new filename')
    core.save(output,result);return core.bind(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    print(core.json.dumps(run(p.parse_args().output),indent=2))
