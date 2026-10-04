"""Closed saved primary prerequisite review. See README_PRIMARY_PREREQUISITE.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os
import json
import uuid
from pathlib import Path

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OWNER = PRIVATE/('presets-preparation-primary-prerequisite-'+uuid.uuid4().hex)
OWNER.mkdir()
with (OWNER/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(), create_time=psutil.Process().create_time(), affinity=[14]), stream)
    stream.flush(); os.fsync(stream.fileno())

# Existing bounded reader imports only after this process has a registered owner.
import argparse
import hashlib
import importlib.util
import sys

READER_SHA = '5a104a19aeda0ef221cacda4f34732d62c49016ba41e82c9dc6e094a8f28248f'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--monitor', required=True, type=Path)
    parser.add_argument('--expected-payload', required=True, type=Path)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    source = Path(__file__).with_name('review_research_comparison.py')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == READER_SHA
    spec = importlib.util.spec_from_file_location('pinned_primary_closed_reader', source)
    reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
    expected = reader.read_json(args.expected_payload, 16384)
    selection = expected['selection']
    reader.require(selection == dict(diarizer='pyannote', embedding='titanet', input_source='saved',
        nemotron_profile=None, allow_experimental=True, provisional_correction=False,
        refinement_profile='current_delayed', revision_window_seconds=60, refinement_period_seconds=5,
        embedding_schedule='continuous', embedding_refresh_seconds=2.0,
        speaker_attribution='retained', optional_d1_refiner=False), 'Exact window60 primary prerequisite required')
    reader.require(expected['policy'] == dict(maximum_session_seconds=45, developer_soak=False,
        max_drain_seconds=60, max_backlog_seconds=30, model_load_seconds=120, cleanup_seconds=60),
        'Exact finite source/load/drain/backlog/cleanup policy required')
    # Pyannote primary has no native D1 probability stream. Keep all existing
    # closed-mirror/source/worker/host/SQLite/ASR/provenance checks unchanged.
    reader.native_probability_summary = lambda directory: dict(available=False,
        scope='Pyannote primary; no D1 frame equivalence claim')
    result = reader.summarize(args.monitor)
    reader.require(result['selection'] == selection and result['policy'] == expected['policy'] and
        result['manifest_sha256'] == expected['package_manifest_sha256'] and
        result['executed_package'] == expected['package'], 'Actual execution differs from exact intended prerequisite')
    reader.require(result['source']['processed_float32_sha256'] ==
        'fa876f01084bcaab1eb6a1b0f31edc1c115b8f2e9ab0f98601c9a57c8c0e9039', 'Matched float source changed')
    reader.require(result['costs'].get('asr_accept', {}).get('samples') == 715127 and
        result['native_events']['event_counts'].get('research_embedding', 0) > 0 and
        result['costs'].get('model_setup', {}).get('calls', 0) > 0,
        'Actual source/embedding/model function receipts required')
    report = dict(schema='just-peachy.optional-primary-prerequisite-review.v1', reviewed=True,
        functional_pass=True, complete_primary_eof=True, all_owners_closed=True,
        full_mirror_verified=True, source_samples=715127, production_eligible=False,
        primary_selection=selection, source=dict(kind='saved', path=expected['input'],
            sha256=expected['input_sha256'], samples=715127), actual=result,
        reader_sha256=READER_SHA, reviewer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        expected_payload_sha256=reader.checksum(args.expected_payload, 16384),
        native_executed_by_reviewer=False,
        limits=['Function/closure evidence only; no speaker accuracy, correction or sustained real-time claim.',
                'Original GUI/raw source evidence requires its separate explicit reviewed composition provenance.'])
    raw = reader.encoded(report)
    reader.require(len(raw) <= 128*1024, 'Bounded prerequisite report exceeded')
    path = OWNER/'PRIMARY_REVIEW.json'
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(dict(output=str(path), sha256=hashlib.sha256(raw).hexdigest(),
        functional_pass=True, source_samples=715127, embedding_events=result['native_events']['event_counts']['research_embedding'])))


if __name__ == '__main__':
    main()
