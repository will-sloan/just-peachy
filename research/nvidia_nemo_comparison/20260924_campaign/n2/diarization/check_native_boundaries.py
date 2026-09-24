"""Actual native exact-sample scheduling, overlap contract and teardown checks."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import time
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]/'prototype/vendor'))
import numpy as np
import psutil
import soundfile as sf
from edge_speech_pipeline.nemotron_diarization import NemotronDiarizer, DiarizationUpdate, PROFILES

def main():
    if os.name == 'nt':
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    campaign = HERE.parents[1]
    build = json.loads((HERE/'NATIVE_BUILD_RECEIPT.json').read_text())
    model_path = next(x for x in json.loads((campaign/'assets/model_manifest.json').read_text())['models'] if x['id']=='D1')['download']['path']
    audio_manifest = json.loads(Path('G:/Just_Peachy_N1/20260924_campaign/local/data/BASELINE_SCREEN_AUDIO_ONLY.json').read_text())
    job = audio_manifest['jobs'][0]
    with Path(job['audio_path']).open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest() == job['audio_sha256']
    audio, sr = sf.read(job['audio_path'], dtype='float32')
    assert sr == 16000
    checks = {}
    for profile in PROFILES.values():
        with NemotronDiarizer(model_path, build['library_path'], profile=profile.name,
                             expected_library_sha256=build['library_sha256'], session_id='boundary') as model:
            required = (8*(profile.chunk_frames+profile.right_context_frames)-1)*160+256
            before = model.push(audio[:required-1])
            old_tracks = model.track_ids
            start = time.perf_counter()
            at = model.push(audio[required-1:required])
            assert len(before.probabilities) == 0
            assert at.frame_start == 0 and at.frame_end == profile.chunk_frames*8
            assert at.available_at_monotonic >= at.received_at_monotonic >= start
            assert at.audio_received_sec == required/16000
            for bad in (np.array([np.nan], np.float32), np.zeros((4,2),np.float32)):
                try:
                    model.push(bad)
                except ValueError:
                    pass
                else:
                    raise AssertionError('bad input accepted')
            model.finish()
            model.reset(session_id='independent')
            assert not set(old_tracks).intersection(model.track_ids)
            assert len(model.finish().probabilities)==0
            checks[profile.name] = {'pass': True, 'first_emission_required_samples': required,
                                    'first_emission_input_sec': required/16000,
                                    'first_emission_frames': at.frame_end,
                                    'actual_compute_sec': at.compute_sec}
        try:
            model.push(np.zeros(1,np.float32))
        except RuntimeError:
            pass
        else:
            raise AssertionError('closed model accepted input')
    probabilities = np.zeros((4,8),np.float32)
    probabilities[:3,0] = .9
    probabilities[1:,1] = .8
    update = DiarizationUpdate('test',10,probabilities,.01,.14,1,2,1,False,tuple(f's:{i}' for i in range(8)))
    spans = update.activity_spans()
    assert len(spans)==2 and all(s['contains_overlap'] for s in spans)
    assert spans[0]['start_sec']==.10 and spans[1]['start_sec']==.11
    assert update.capacity_status == 'EIGHT_SLOTS_OVERFLOW_UNDETECTABLE'
    result = {'status':'ACTUALLY_RUN_PASS','profiles':checks,'overlap_contract':'PASS',
              'bad_input_closed_teardown_reset':'PASS','audio_sha256':job['audio_sha256'],
              'threshold_fixture_is_neural_inference':False}
    (HERE/'NATIVE_BOUNDARY_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':
    main()
