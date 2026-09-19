"""Focused independent diagnostic closure probes; see README_S6D_BEAM_DIAGNOSTIC_INDEPENDENT_V1.md."""
import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert out.drive.casefold() == 'g:' and 'review_fixtures' in out.parts and not out.exists()
    out.mkdir(parents=True)
    sys.path.insert(0, str(args.source_root))
    native = load(args.source_root / 's6d_beam_native_run_diagnostic_v2.py', 's6d_beam_native_run_diagnostic_v2')
    queue = load(args.source_root / 's6d_beam_queue_prepare_diagnostic_v2.py', 'independent_diagnostic_queue')
    assert native.bind(native.__file__)['sha256'] == '5b391754acb6b02623100a6dcdf574e67c489e5e3a207100c009e4c4875b3d50'
    assert native.bind(queue.__file__)['sha256'] == '40199ae62e0c27ec7b5226e41a1b84117c6740c1bae64fe3bc462a50b0d88ec4'
    parent = Path('C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S6D/20260913T195357Z/application/beam_execution_predecl_v3/helpers/s6d_beam_execution_checks_v1.py')
    tree = ast.parse(parent.read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'Checks')
    constructor = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'good')
    ns = {'deepcopy': deepcopy}
    exec(compile(ast.Module(body=[constructor], type_ignores=[]), str(parent), 'exec'), ns)
    raw = bytes(range(128)) * 250
    original = out / 'synthetic_source.fixture'
    original.write_bytes(raw)
    audio = native.bind(original)
    rows = []
    serial = 0

    def case():
        nonlocal serial
        serial += 1
        session = out / f'session{serial:02d}'
        session.mkdir()
        for name in ('audio_spool.pcm16', 'identity_audio_spool.pcm16'):
            (session / name).write_bytes(raw)
        values = list(ns['good'](None))
        job = values[1]
        name = 'focus0_asr_raw'
        proof = dict(audio=audio, frames=16000, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), gain=1.0)
        job.update(mode='stream_diagnostic', asr_raw_stream=name, stream_proofs={name: proof},
                   audio=audio, audio_pcm_sha256=proof['sha256'], expected_identity_frames=16000)
        values[0]['session_dir'] = str(session)
        values[4] = {name: native.bind(session / 'audio_spool.pcm16')}
        pair = native.diagnostic_pair_proof(job, session)
        admitted = {'streams': [dict(name=name, audio=audio)]}
        assert native.validate_multistream(*values, pair) == []
        assert native.validate_diagnostic_source(job, admitted) == proof
        return values, pair, admitted

    def rejects(callback):
        try:
            callback()
        except (ValueError, KeyError, TypeError):
            return
        raise AssertionError('Expected explicit rejection')

    def probe(name, callback):
        try:
            callback()
            rows.append(dict(name=name, status='PASS'))
        except BaseException:
            rows.append(dict(name=name, status='FAIL', traceback=traceback.format_exc()))

    def joint_source_relabel():
        values, pair, admitted = case()
        job = values[1]
        other = out / 'same_bytes_other_source.fixture'
        other.write_bytes(raw)
        job['audio'] = native.bind(other)
        job['stream_proofs'][job['asr_raw_stream']]['audio'] = job['audio']
        rejects(lambda: native.validate_diagnostic_source(job, admitted))

    probe('joint_job_and_proof_relabel_cannot_replace_actual_admitted_source', joint_source_relabel)

    def duplicate_and_nonnumeric():
        values, pair, admitted = case()
        admitted['streams'].append(deepcopy(admitted['streams'][0]))
        rejects(lambda: native.validate_diagnostic_source(values[1], admitted))
        admitted['streams'].pop()
        for field in ('expected_frames', 'expected_identity_frames'):
            job = deepcopy(values[1])
            job[field] = True
            rejects(lambda: native.validate_diagnostic_source(job, admitted))

    probe('duplicate_admitted_stream_and_boolean_frames_reject', duplicate_and_nonnumeric)

    def alias_spools():
        values, pair, admitted = case()
        pair['identity'] = deepcopy(pair['asr'])
        errors = native.validate_multistream(*values, pair)
        assert 'Foreign diagnostic identity journal path' in errors, errors

    probe('identity_cannot_alias_ASR_spool_even_with_equal_full_bytes', alias_spools)

    def still_open():
        values, pair, admitted = case()
        values[2]['event_and_transcript_handles_closed'] = False
        assert 'Finalizer not closed' in native.validate_multistream(*values, pair)

    probe('paired_full_spools_cannot_bypass_open_finalizer_handles', still_open)

    def reject_non_diagnostic():
        for index, mode in enumerate(('calibration_collection', 'beam_selected')):
            path = out / f'held_wrong_mode{index}.json'
            manifest = dict(schema='s6d-beam-execution.v1', stage='calibration_collection',
                            runner_helper=native.bind(native.__file__), jobs=[dict(job_id='synthetic', mode=mode)])
            native.save(path, manifest)
            binding = native.bind(path)
            # Both calls must reject before dependency imports, process inspection or any output creation.
            rejects(lambda: native.run(path, binding['sha256'], 'synthetic'))
            target = out / f'forbidden_queue{index}'
            rejects(lambda: queue.prepare(path, binding['sha256'], target))
            assert not target.exists()

    probe('C_and_core_modes_reject_before_process_or_queue_paths', reject_non_diagnostic)
    receipt = dict(status='PASS' if all(x['status'] == 'PASS' for x in rows) else 'FAIL', tests=rows,
                   passed=sum(x['status'] == 'PASS' for x in rows), total=len(rows),
                   sources=[native.bind(native.__file__), native.bind(queue.__file__), native.bind(__file__), native.bind(parent)],
                   models=0, hardware=0, UI=0, process_queries=0, queues_or_approvals_created=0,
                   production_audio_read=0, original_three_beam_tests_rerun=False)
    native.save(out / 'RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
