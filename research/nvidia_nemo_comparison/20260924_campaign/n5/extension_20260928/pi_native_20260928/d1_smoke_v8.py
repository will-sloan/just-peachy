"""Bounded native saved-audio D1 smoke; not an integrated mode. See README_V8.md."""
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


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(__file__).resolve().parent
    if sorted(os.sched_getaffinity(0)) != [2, 3] or os.getuid() == 0:
        raise RuntimeError('Expected ordinary user, CPUs 2/3')
    if not Path('/proc/device-tree/model').read_text().startswith('Raspberry Pi Compute Module 5'):
        raise RuntimeError('Wrong target')
    admission = json.loads((root/'ADMISSION_V8.json').read_text())
    if datetime.now(timezone.utc) >= datetime.fromisoformat(admission['expires_utc']):
        raise RuntimeError('Expired admission')
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot_id != admission['boot_id'] or admission['cpus'] != [2, 3] or admission['address_space_max_bytes'] != 768*1024**2:
        raise RuntimeError('Target identity or resource admission differs')
    if admission['inputs_sha256'] != digest(root/'INPUTS_V8.json'):
        raise RuntimeError('Admission input binding differs')
    cgroup = next(line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    limits = Path('/sys/fs/cgroup')/cgroup.lstrip('/')
    # Kernel lacks MEMCG. A hard per-process virtual address-space bound is enforced instead.
    resource.setrlimit(resource.RLIMIT_AS, (768*1024**2, 768*1024**2))
    if resource.getrlimit(resource.RLIMIT_AS) != (768*1024**2, 768*1024**2):
        raise RuntimeError('Hard address-space bound absent')
    quota, period = (limits/'cpu.max').read_text().split()
    if quota == 'max' or int(quota)/int(period) > 2:
        raise RuntimeError('Required cgroup CPU bound absent')
    available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    if available < 850*1024**2:
        raise RuntimeError('Need 850 MiB available for isolated component smoke')
    result_path = root/'RESULT_V8.json'
    if result_path.exists() or (root/'OWNER_V8.json').exists():
        raise FileExistsError('Fresh run required')
    for row in json.loads((root/'INPUTS_V8.json').read_text())['files']:
        if digest(root/row['name']) != row['sha256']:
            raise RuntimeError('Changed staged input')
    result = dict(status='FAILED_PRESERVED', started_utc=datetime.now(timezone.utc).isoformat(),
                  pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
                  boot_id=boot_id, admission_sha256=digest(root/'ADMISSION_V8.json'),
                  native_CM5=True, address_space_limit_bytes=resource.getrlimit(resource.RLIMIT_AS)[1], memory_controller_available=False, swap_prohibited=False, integrated_mode_qualified=False, real_world_audio=False,
                  benchmark_uncontended=False, cases=[], scope='First 12 seconds of saved synthetic-source hardware capture; native component smoke only')
    with (root/'OWNER_V8.json').open('x') as stream:
        json.dump({k:result[k] for k in ('pid','start_ticks','boot_id','admission_sha256')}, stream)
    try:
        import numpy as np
        import soundfile as sf
        from nemotron_diarization import NemotronDiarizer
        audio, sr = sf.read(root/'source.wav', dtype='float32', frames=192000)
        if sr != 16000 or audio.ndim != 1 or len(audio) != 192000:
            raise RuntimeError('Unexpected audio shape')
        library = root/'nemo-arm64/lib/libnemo_speech_asr_c.so.1'
        began = time.perf_counter()
        with NemotronDiarizer(root/'D1.gguf', library, profile='low_latency',
                             expected_library_sha256='9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f', gpu=-1) as model:
            result['load_wall_seconds'] = time.perf_counter()-began
            outputs = []
            for case in ('saved_prefix', 'resident_repeat'):
                model.reset(session_id=case)
                begun = time.perf_counter(); cpu = time.process_time(); values = []; cursor = 0
                for offset in range(0, len(audio), 1600):
                    update = model.push(audio[offset:offset+1600])
                    if update.frame_start != cursor:
                        raise RuntimeError('Discontinuous output')
                    cursor = update.frame_end
                    values.append(update.probabilities)
                final = model.finish()
                if final.frame_start != cursor:
                    raise RuntimeError('Discontinuous final output')
                values.append(final.probabilities)
                probabilities = np.concatenate(values)
                elapsed = time.perf_counter()-begun
                if probabilities.shape != (len(audio)//160+1, 8) or not np.isfinite(probabilities).all():
                    raise RuntimeError('Invalid complete probability output: '+str(probabilities.shape))
                if np.min(probabilities) < 0 or np.max(probabilities) > 1:
                    raise RuntimeError('Probabilities outside range')
                outputs.append(probabilities)
                np.save(root/(case+'_v8.npy'), probabilities, allow_pickle=False)
                result['cases'].append(dict(case=case, frames=len(probabilities), audio_seconds=12, endpoint_support_overhang_seconds=len(probabilities)*model.seconds_per_frame-12,
                    elapsed_seconds=elapsed, call_sequence_rtf=elapsed/12,
                    cpu_seconds=time.process_time()-cpu,
                    temperature_millic=int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())))
                print(json.dumps(result['cases'][-1]), flush=True)
            result['repeat_max_abs_probability_error'] = float(np.max(np.abs(outputs[0]-outputs[1])))
            if result['repeat_max_abs_probability_error'] > 1e-5:
                raise RuntimeError('Resident repeat parity failed')
            if model.finish().probabilities.size:
                raise RuntimeError('Repeated finish emitted new frames')
            try:
                model.push(np.zeros(1, np.float32))
            except RuntimeError:
                result['post_finish_push_rejected'] = True
            else:
                raise RuntimeError('Post-finish push accepted')
            model.reset(session_id='empty')
            if model.push(np.empty(0, np.float32)).probabilities.size or model.finish().probabilities.size:
                raise RuntimeError('Empty stream emitted frames')
        result['model_closed'] = True
        reference = np.load(root/'reference_generic.npy', allow_pickle=False)
        if reference.shape != outputs[0].shape:
            raise RuntimeError('Generic reference shape differs')
        delta = np.abs(outputs[0]-reference)
        result['generic_reference_max_abs_probability_error'] = float(np.max(delta))
        result['generic_reference_mean_abs_probability_error'] = float(np.mean(delta))
        result['generic_reference_tolerance'] = 1e-5
        if np.max(delta) > 1e-5:
            raise RuntimeError('A76 versus generic numerical parity exceeds declared tolerance')
        result['status'] = 'NATIVE_D1_COMPONENT_SMOKE_COLLECTED_REQUIRES_REVIEW'
    except Exception as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    result['peak_process_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    result['ended_utc'] = datetime.now(timezone.utc).isoformat()
    with result_path.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(dict(status=result['status'], error=result.get('error'))), flush=True)
    return int(result['status'] == 'FAILED_PRESERVED')


if __name__ == '__main__':
    raise SystemExit(main())
