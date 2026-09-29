"""Native whole-recipe passage/resource check. See README_GEOMETRY_V2.md."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import resource
import time
from datetime import datetime, timezone

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['NEMO_SPEECH_MEMSTATS'] = '1'
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value, mode='x'):
    with path.open(mode, encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def main():
    root = Path(__file__).resolve().parent
    admission = json.loads((root/'ADMISSION.json').read_text())
    config = json.loads((root/'CONFIG.json').read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert os.getuid() != 0 and sorted(os.sched_getaffinity(0)) == [2, 3]
    assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
    assert boot == admission['boot_id']
    assert datetime.now(timezone.utc) < datetime.fromisoformat(admission['expires_utc'])
    assert admission['address_space_max_bytes'] == 768*1024**2
    assert sha(root/'INPUTS.json') == admission['inputs_sha256']
    assert not (root/'OWNER.json').exists() and not (root/'RESULT.json').exists()
    for row in json.loads((root/'INPUTS.json').read_text())['files']:
        assert sha(root/row['name']) == row['sha256'], row['name']
    available = next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    assert available >= 850*1024**2
    group = next(x.split(':', 2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    quota, period = (Path('/sys/fs/cgroup')/group.lstrip('/')/'cpu.max').read_text().split()
    assert quota != 'max' and int(quota)/int(period) <= 2
    resource.setrlimit(resource.RLIMIT_AS, (768*1024**2, 768*1024**2))
    result = dict(status='FAILED_PRESERVED', started_utc=datetime.now(timezone.utc).isoformat(),
                  pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
                  boot_id=boot, admission_sha256=sha(root/'ADMISSION.json'), config=config,
                  cases=[], native_CM5=True, integrated_mode_qualified=False, real_world_audio=False,
                  accuracy_scored=False, benchmark_uncontended=False, paced=False,
                  address_space_limit_bytes=resource.getrlimit(resource.RLIMIT_AS)[1])
    write(root/'OWNER.json', {k:result[k] for k in ('pid','start_ticks','boot_id','admission_sha256')})
    try:
        import numpy as np
        import soundfile as sf
        import nemotron_diarization as d

        class AuditedDiarizer(d.NemotronDiarizer):
            def _bind(self):
                super()._bind()
                native_create = self._api.nemo_speech_diar_create

                def create(pointer, output):
                    c = C.cast(pointer, C.POINTER(d._ModelConfig)).contents
                    fields = ('chunk_frames','right_context_frames','left_context_frames','fifo_frames','spkcache_frames','update_period_frames')
                    observed = {k:int(getattr(c, k)) for k in fields}
                    observed['preset'] = c.preset.decode()
                    observed['gpu'] = int(c.gpu)
                    assert observed == config['c_abi_geometry'], observed
                    result['observed_c_abi_geometry'] = observed
                    return native_create(pointer, output)
                self._api.nemo_speech_diar_create = create

        audio, sr = sf.read(root/'source.wav', dtype='float32')
        assert sr == 16000 and audio.ndim == 1 and len(audio) == 715127
        started = time.perf_counter()
        with AuditedDiarizer(root/'D1.gguf', root/'nemo-arm64/lib/libnemo_speech_asr_c.so.1',
                            profile=config['profile'], gpu=-1,
                            expected_library_sha256='9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f') as model:
            result['load_wall_seconds'] = time.perf_counter()-started
            result['manifest'] = model.manifest()
            arrays = []
            for case in ('saved_full', 'resident_repeat'):
                model.reset(session_id=case)
                begun = time.perf_counter(); cpu = time.process_time(); cursor = 0
                values = []; calls = []; samples = 0
                with (root/(case+'_calls.jsonl')).open('x', encoding='utf-8') as trace:
                    def accept(update, kind):
                        nonlocal cursor
                        assert update.frame_start == cursor and update.session_id == case
                        assert abs(update.audio_received_sec-samples/sr) < 1e-9
                        assert update.received_at_monotonic <= update.available_at_monotonic
                        assert update.frame_end*.01 <= samples/sr+.011
                        cursor = update.frame_end
                        values.append(update.probabilities)
                        row = dict(kind=kind, source_samples=samples, frame_start=update.frame_start,
                                   frame_end=cursor, compute_seconds=update.compute_sec,
                                   available_elapsed_seconds=update.available_at_monotonic-begun)
                        calls.append(row)
                        trace.write(json.dumps(row)+'\n'); trace.flush()
                    for offset in range(0, len(audio), 1600):
                        chunk = audio[offset:offset+1600]; samples += len(chunk)
                        accept(model.push(chunk), 'push')
                        if offset % 16000 == 0:
                            write(root/'HEARTBEAT.json', dict(pid=os.getpid(), boot_id=boot,
                                  start_ticks=result['start_ticks'], case=case, samples=samples,
                                  utc=datetime.now(timezone.utc).isoformat()), 'w')
                    accept(model.finish(), 'finish')
                array = np.concatenate(values)
                elapsed = time.perf_counter()-begun
                assert samples == len(audio) and array.shape == (4470, 8)
                assert np.isfinite(array).all() and np.min(array) >= 0 and np.max(array) <= 1
                np.save(root/(case+'.npy'), array, allow_pickle=False)
                arrays.append(array)
                emitting = [x for x in calls if x['frame_end'] > x['frame_start']]
                result['cases'].append(dict(case=case, samples=samples, frames=len(array),
                     audio_seconds=len(audio)/sr, elapsed_seconds=elapsed, call_sequence_rtf=elapsed/(len(audio)/sr),
                     cpu_seconds=time.process_time()-cpu, call_compute_seconds=sum(x['compute_seconds'] for x in calls),
                     emitting_calls=len(emitting), first_emission_source_seconds=emitting[0]['source_samples']/sr,
                     first_emission_elapsed_seconds=emitting[0]['available_elapsed_seconds'],
                     finish_compute_seconds=calls[-1]['compute_seconds'],
                     temperature_millic=int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())))
                write(root/(case+'_CASE.json'), result['cases'][-1])
                print(json.dumps(result['cases'][-1]), flush=True)
            result['repeat_max_abs_probability_error'] = float(np.max(np.abs(arrays[0]-arrays[1])))
            assert result['repeat_max_abs_probability_error'] <= 1e-5
            assert model.finish().probabilities.size == 0
            result['repeated_finish_empty'] = True
            try:
                model.push(np.zeros(1, np.float32))
            except RuntimeError:
                result['post_finish_push_rejected'] = True
            else:
                raise AssertionError('post-finish push accepted')
            model.reset(session_id='empty')
            assert model.push(np.empty(0, np.float32)).probabilities.size == 0
            assert model.finish().probabilities.size == 0
            result['reset_empty_passed'] = True
        result['model_closed'] = True
        if config['kernel'] == 'a76':
            reference = np.load(root/'same_geometry_generic.npy', allow_pickle=False)
            assert reference.shape == arrays[0].shape
            result['generic_reference_tolerance'] = 1e-5
            result['generic_reference_max_abs_probability_error'] = float(np.max(np.abs(reference-arrays[0])))
            assert result['generic_reference_max_abs_probability_error'] <= 1e-5
        result['status'] = 'NATIVE_GEOMETRY_COLLECTED_REQUIRES_REVIEW'
    except Exception as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    result['peak_process_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    result['ended_utc'] = datetime.now(timezone.utc).isoformat()
    write(root/'RESULT.json', result)
    print(json.dumps(dict(status=result['status'], error=result.get('error'))), flush=True)
    return int(result['status'] == 'FAILED_PRESERVED')


if __name__ == '__main__':
    raise SystemExit(main())
