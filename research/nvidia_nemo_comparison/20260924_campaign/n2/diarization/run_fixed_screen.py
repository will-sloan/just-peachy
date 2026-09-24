"""Checkpointed Nemotron streaming screen; CPU default. See README.md before dispatch."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
import wave

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'
HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local/n2')
PROFILE_NAMES = ('low_latency', 'very_low_latency', 'ultra_low_latency')


def utc():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bind(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def verify(item):
    if Path(item['path']).stat().st_size != item['bytes'] or sha(item['path']) != item['sha256']:
        raise ValueError('Evidence binding mismatch: '+item['path'])


def classify(exc):
    if isinstance(exc, MemoryError) or 'bad_alloc' in str(exc):
        return 'RUNTIME_MEMORY_CAPACITY'
    if isinstance(exc, TimeoutError):
        return 'RUNTIME_TIMEOUT'
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return 'ADMISSION_OR_INTEGRITY_FAILURE'
    if isinstance(exc, OSError):
        return 'RUNTIME_IO_OR_CAPACITY'
    return 'RUNTIME_IMPLEMENTATION_FAILURE'


class WriterLock:
    """An OS-owned advisory lock, plus separately readable PID/creation-time metadata."""
    def __init__(self, output):
        import psutil
        self.output = output
        self.stream = (output/'WRITER.lock').open('a+b')
        self.stream.seek(0, 2)
        if self.stream.tell() == 0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('A live coordinator owns this output; no second writer was started')
        self.owner_path = output/'RUNNER_OWNER.json'
        try:
            if self.owner_path.exists():
                prior = load(self.owner_path).get('worker')
                if prior:
                    try:
                        old = psutil.Process(prior['pid'])
                        if abs(old.create_time()-prior['create_time']) < .01 and old.is_running():
                            raise RuntimeError('Previous owned worker is still live; wait for it or let its coordinator stop it')
                    except psutil.NoSuchProcess:
                        pass
            self.owner = {'token': uuid.uuid4().hex, 'pid': os.getpid(),
                          'create_time': psutil.Process().create_time(), 'started_utc': utc(), 'worker': None}
            self.update(None)
        except BaseException:
            self.close()
            raise

    def update(self, worker):
        self.owner['worker'] = worker
        atomic(self.owner_path, self.owner)

    def close(self):
        if self.stream.closed:
            return
        self.stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream, fcntl.LOCK_UN)
        self.stream.close()


class Worker:
    """One resident profile, one input in flight, bounded output and owned-process stop."""
    def __init__(self, admission, profile, output, lock, load_timeout):
        import psutil
        self.directory = output/'workers'/(profile+'_'+uuid.uuid4().hex[:12])
        self.directory.mkdir(parents=True)
        self.messages = queue.Queue(maxsize=16)
        self.stderr_first, self.stderr_tail = bytearray(), bytearray()
        self.stderr_bytes = 0
        self.stderr_hash = hashlib.sha256()
        self.lock = lock
        contract = load(admission)['contract']
        self.proc = subprocess.Popen([sys.executable, contract['frozen_runner']['path'], '--worker', str(admission), profile],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(output),
            creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == 'nt' else 0)
        try:
            self.identity = {'pid': self.proc.pid, 'create_time': psutil.Process(self.proc.pid).create_time(),
                             'profile': profile, 'log_directory': str(self.directory)}
            self.lock.update(self.identity)
            self.stdout_thread = threading.Thread(target=self._stdout, daemon=True)
            self.stderr_thread = threading.Thread(target=self._stderr, daemon=True)
            self.stdout_thread.start()
            self.stderr_thread.start()
        except BaseException:
            # Ownership metadata/thread setup can itself fail after Popen.
            # Stop only this just-created process before propagating the error.
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr):
                stream.close()
            raise
        self.closed = False
        try:
            ready = self.receive(load_timeout)
            if ready.get('status') != 'READY':
                raise RuntimeError('Resident model initialization failed: '+str(ready))
            self.ready = ready
            atomic(self.directory/'READY.json', ready)
        except BaseException:
            self.stop()
            raise

    def _stdout(self):
        try:
            for line in self.proc.stdout:
                if len(line) > 65536:
                    raise RuntimeError('Worker protocol line exceeded 64 KiB')
                self.messages.put(json.loads(line), timeout=2)
        except BaseException as exc:
            try:
                self.messages.put({'status': 'PROTOCOL_ERROR', 'error': str(exc)[:8192]}, timeout=2)
            except queue.Full:
                pass

    def _stderr(self):
        # Drain all native output so a full pipe cannot deadlock inference. Keep
        # only bounded prefix/tail, and hash/count the entire observed stream.
        prefix_path = self.directory/'stderr-prefix.log'
        with prefix_path.open('wb') as prefix:
            for chunk in iter(lambda: self.proc.stderr.read(4096), b''):
                self.stderr_hash.update(chunk)
                self.stderr_bytes += len(chunk)
                keep = max(0, 131072-len(self.stderr_first))
                self.stderr_first.extend(chunk[:keep])
                if keep:
                    prefix.write(chunk[:keep])
                    prefix.flush()
                self.stderr_tail.extend(chunk)
                if len(self.stderr_tail) > 131072:
                    del self.stderr_tail[:-131072]

    def send(self, value):
        self.proc.stdin.write((json.dumps(value)+'\n').encode())
        self.proc.stdin.flush()

    def receive(self, timeout, progress_callback=None):
        end = time.monotonic()+timeout
        while True:
            try:
                return self.messages.get(timeout=min(1, max(.01, end-time.monotonic())))
            except queue.Empty:
                if progress_callback:
                    progress_callback()
                if self.proc.poll() is not None:
                    raise RuntimeError(f'Owned native worker exited with code {self.proc.returncode}')
                if time.monotonic() >= end:
                    raise TimeoutError(f'Owned native worker exceeded {timeout} seconds')

    def stop(self):
        if self.closed:
            return
        self.closed = True
        forced = False
        if self.proc.poll() is None:
            try:
                self.send({'action': 'stop'})
                self.proc.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                forced = True
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
        self.stdout_thread.join(timeout=3)
        self.stderr_thread.join(timeout=3)
        self.proc.stdin.close()
        self.proc.stdout.close()
        self.proc.stderr.close()
        log = self.directory/'stderr-bounded.log'
        if self.stderr_bytes <= len(self.stderr_first):
            log.write_bytes(self.stderr_first)
        else:
            log.write_bytes(self.stderr_first+b'\n[bounded log: middle omitted]\n'+self.stderr_tail)
        atomic(self.directory/'WORKER_RECEIPT.json', {
            **self.identity, 'returncode': self.proc.returncode, 'forced_owned_termination': forced,
            'stderr_total_bytes': self.stderr_bytes, 'stderr_full_stream_sha256': self.stderr_hash.hexdigest(),
            'bounded_log': bind(log), 'finished_utc': utc()})
        self.lock.update(None)


def worker_main(admission_path, profile_name):
    """Protocol worker; launched only by the coordinator, never by a human CLI."""
    import psutil
    import numpy as np
    import soundfile as sf
    process = psutil.Process()
    if os.name == 'nt':
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    else:
        process.nice(10)
    admission = load(admission_path)
    contract = admission['contract']
    for item in [contract['frozen_runner'], contract['frozen_adapter'], contract['model'], *contract['native_runtime_files']]:
        verify(item)
    if contract['cpu_affinity'] is not None:
        process.cpu_affinity([contract['cpu_affinity']])
    sys.path.insert(0, str(Path(contract['frozen_adapter']['path']).parent.parent))
    from edge_speech_pipeline.nemotron_diarization import NemotronDiarizer
    model = None
    try:
        load_start = time.perf_counter()
        model = NemotronDiarizer(contract['model']['path'], contract['library']['path'], profile=profile_name,
                                 expected_library_sha256=contract['library']['sha256'], gpu=contract['gpu_device'])
        print(json.dumps({'status': 'READY', 'pid': os.getpid(), 'profile': profile_name,
                          'model_load_sec': time.perf_counter()-load_start, 'manifest': model.manifest(),
                          'rss_bytes': process.memory_info().rss, 'priority': process.nice(),
                          'cpu_affinity': process.cpu_affinity()}), flush=True)
        for line in sys.stdin:
            request = json.loads(line)
            if request['action'] == 'stop':
                break
            job, attempt = request['job'], Path(request['attempt'])
            started, cpu_start = time.perf_counter(), time.process_time()
            result = {'status': 'FAILED', 'failure_class': None, 'job_id': job['job_id'], 'profile': profile_name,
                      'cache_key': request['cache_key'], 'started_utc': utc(), 'worker_pid': os.getpid(),
                      'quality_status': 'NOT_SCORED', 'bad_score': None, 'input': job,
                      'runtime_manifest': model.manifest(), 'model_load_amortized': True,
                      'numerical_threads': 1, 'input_queue_limit': 1, 'queued_audio_blocks': 0,
                      'gpu':contract['gpu'],'gpu_device':contract['gpu_device'],
                      'gpu_work_measurement':'requires separately bound coordinator device samples' if contract['gpu'] else 'NOT_APPLICABLE',
                      'delivery': 'accelerated_causal_100ms_file_blocks', 'physical_latency': 'NOT_MEASURED'}
            resources, probabilities = [], []
            received = 0
            last_resource = -5.0
            try:
                if job != contract['jobs_by_id'][job['job_id']]:
                    raise ValueError('Worker request differs from admitted audio-only job')
                if sha(job['audio_path']) != job['audio_sha256']:
                    raise ValueError('Audio changed after admission')
                for item in [contract['frozen_adapter'], *contract['native_runtime_files']]:
                    verify(item)
                audio, rate = sf.read(job['audio_path'], dtype='float32')
                if audio.ndim != 1 or rate != 16000 or len(audio) != job['frames']:
                    raise ValueError('Audio waveform geometry changed')
                model.reset(session_id=profile_name+':'+job['job_id'])
                with (attempt/'AVAILABILITY.jsonl').open('x', encoding='utf-8', newline='\n') as events:
                    def record(update):
                        nonlocal last_resource
                        elapsed = time.perf_counter()-started
                        if update.probabilities.size:
                            probabilities.append(update.probabilities)
                        events.write(json.dumps({'frame_start': update.frame_start, 'frame_end': update.frame_end,
                            'audio_received_sec': update.audio_received_sec,
                            'received_at_elapsed_sec': update.received_at_monotonic-started,
                            'available_at_elapsed_sec': update.available_at_monotonic-started,
                            'compute_sec': update.compute_sec, 'is_final': update.is_final})+'\n')
                        events.flush()
                        if elapsed-last_resource >= 5 or update.is_final:
                            sample = {'elapsed_sec': elapsed, 'rss_bytes': process.memory_info().rss,
                                      'process_cpu_sec': time.process_time()-cpu_start,
                                      'audio_received_samples': received, 'native_frames': update.frame_end}
                            resources.append(sample)
                            atomic(attempt/'HEARTBEAT.json', {'utc': utc(), **sample})
                            last_resource = elapsed
                    for offset in range(0, len(audio), 1600):
                        block = audio[offset:offset+1600]
                        received += len(block)
                        record(model.push(block))
                    record(model.finish())
                values = np.concatenate(probabilities) if probabilities else np.empty((0,8),np.float32)
                expected_frames = len(audio)//160+1 if len(audio) else 0
                if values.shape != (expected_frames,8) or not np.isfinite(values).all():
                    raise RuntimeError('Native final shape/finiteness contract failed')
                output = attempt/'probabilities.npz'
                np.savez_compressed(output, probabilities=values,
                                    seconds_per_frame=np.array(model.seconds_per_frame), audio_samples=np.array(len(audio)))
                result.update(status='COMPLETE', shape=list(values.shape), all_audio_samples_delivered=received==len(audio),
                              native_clock_end_sec=len(values)*model.seconds_per_frame,
                              audio_end_sec=len(audio)/16000,
                              endpoint_support_overhang_sec=len(values)*model.seconds_per_frame-len(audio)/16000,
                              probability_file=bind(output), reset_policy='independent_scene_only_no_slot_recycling')
            except BaseException as exc:
                result.update(failure_class=classify(exc), error=f'{type(exc).__name__}: {exc}'[:8192],
                              traceback=traceback.format_exc()[-16384:])
            result.update(finished_utc=utc(), wall_sec=time.perf_counter()-started,
                          process_cpu_sec=time.process_time()-cpu_start,
                          sampled_peak_rss_bytes=max((x['rss_bytes'] for x in resources), default=process.memory_info().rss),
                          worker_lifetime_peak_wset_bytes=getattr(process.memory_info(), 'peak_wset', None),
                          delivered_audio_samples=received,
                          resource_scope=('CUDA native process with CPU1 support; CPU/RSS only; device measurement separate' if contract['gpu']
                                          else 'one CPU native process; not idle-machine or CM5 total-system qualification'))
            atomic(attempt/'RESOURCE_SAMPLES.json', resources)
            result['evidence'] = [bind(p) for p in sorted(attempt.iterdir()) if p.is_file() and p.name!='RESULT.json']
            atomic(attempt/'RESULT.json', result)
            print(json.dumps({'status': result['status'], 'job_id': job['job_id'], 'result': bind(attempt/'RESULT.json'),
                              'failure_class': result['failure_class']}), flush=True)
    except BaseException as exc:
        print(json.dumps({'status': 'WORKER_FAILED', 'error': f'{type(exc).__name__}: {exc}'[:8192],
                          'failure_class': classify(exc)}), flush=True)
    finally:
        if model is not None:
            model.close()


def prepare(args, output):
    import psutil
    campaign, worktree = HERE.parents[1], HERE.parents[4]
    sys.path.insert(0, str(worktree/'prototype/vendor'))
    from edge_speech_pipeline.nemotron_diarization import PROFILES
    build = load(args.build_receipt)
    if build['threads'] != 1 or build['status'] != 'ACTUALLY_BUILT':
        raise ValueError('A verified CPU-one-thread build is required')
    if args.gpu >= 0 and not build['gpu']:
        raise ValueError('Explicit GPU execution requires a verified CUDA build receipt')
    library = bind(build['library_path'])
    if library['sha256'] != build['library_sha256']:
        raise ValueError('Native C ABI DLL hash mismatch')
    for item in build['runtime_files']:
        verify(item)
    model_record = next(x for x in load(campaign/'assets/model_manifest.json')['models'] if x['id']=='D1')['download']
    model = bind(model_record['path'])
    if model['sha256'] != model_record['sha256']:
        raise ValueError('Official Q8 hash mismatch')
    manifest = load(args.manifest)
    jobs = manifest['jobs']
    if len(jobs) != 96 or len({x['job_id'] for x in jobs}) != 96:
        raise ValueError('This runner requires the fixed 96-cell paired audio-only screen')
    allowed = {'job_id','audio_path','audio_sha256','frames','sample_rate_hz','gain','reset_between_scenes','tap'}
    for job in jobs:
        if set(job)!=allowed or job['gain']!=1 or not job['reset_between_scenes'] or job['sample_rate_hz']!=16000:
            raise ValueError('Audio-only firewall, gain or state contract failed')
        if not re.fullmatch(r'[A-Za-z0-9_]+', job['job_id']) or job['tap'] not in ('O0','O1'):
            raise ValueError('Unsafe job identity or unknown tap')
        if sha(job['audio_path']) != job['audio_sha256']:
            raise ValueError('Input audio hash mismatch')
        with wave.open(job['audio_path'],'rb') as wav:
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())!=(1,2,16000,job['frames']):
                raise ValueError('Input audio header mismatch')
    if Counter(j['tap'] for j in jobs) != {'O0':48,'O1':48}:
        raise ValueError('Both complete tap sets are required')
    pairs = {}
    for job in jobs:
        pair = job['job_id'].rsplit('_',1)[0]
        pairs.setdefault(pair, {})[job['tap']] = job
    if len(pairs)!=48 or any(set(pair)!= {'O0','O1'} or pair['O0']['frames']!=pair['O1']['frames'] for pair in pairs.values()):
        raise ValueError('Pair identities/durations are inconsistent')
    if args.cpu is not None and args.cpu not in psutil.Process().cpu_affinity():
        raise ValueError('Requested CPU is outside the current allowed affinity')
    adapter = worktree/'prototype/vendor/edge_speech_pipeline/nemotron_diarization.py'
    frozen_root = output/'source'
    frozen_adapter = frozen_root/'edge_speech_pipeline/nemotron_diarization.py'
    frozen_runner = frozen_root/'run_fixed_screen.py'
    for original, frozen in ((Path(__file__), frozen_runner),(adapter,frozen_adapter)):
        frozen.parent.mkdir(parents=True,exist_ok=True)
        if frozen.exists():
            if sha(original)!=sha(frozen):
                raise ValueError('Source changed; use a new output directory')
        else:
            shutil.copyfile(original,frozen)
    (frozen_adapter.parent/'__init__.py').touch(exist_ok=True)
    shutil.copyfile(HERE/'README.md', frozen_root/'README.md')
    contract = {'schema':'n2-native-fixed-screen-v1','model':model,'library':library,
        'native_runtime_files':build['runtime_files'],'native_build_receipt':bind(args.build_receipt),
        'frozen_runner':bind(frozen_runner),'frozen_adapter':bind(frozen_adapter),
        'manifest':bind(args.manifest),'screen_sha256':manifest['screen_sha256'],
        'jobs_by_id':{x['job_id']:x for x in jobs},
        'profiles':{name:asdict(PROFILES[name]) for name in args.profiles},
        'python':sys.version,'python_executable':bind(sys.executable),
        'packages':{name:importlib.metadata.version(name) for name in ('numpy','soundfile','psutil')},
        'preprocessing':'exact mono16k PCM16 waveform; runtime gain1; no normalization or enhancement',
        'history':'new stream for each independent scene; resident weights; no turn resets or slot recycling',
        'scoring_version':'native-probability-and-availability-v1-no-gold-scoring',
        'delivery':'accelerated causal fixed100ms blocks; final remainder then explicit finish',
        'cpu_threads':1,'cpu_affinity':args.cpu,'gpu':args.gpu>=0,'gpu_device':args.gpu,
        'native_device':{'kind':args.device,'gpu_index':args.gpu},'worker_inflight_limit':1,
        'cell_timeout_sec':args.timeout_sec,'model_load_timeout_sec':args.load_timeout_sec,'reserve_gib':args.reserve_gib}
    contract_hash = stable_hash(contract)
    path = output/'ADMISSION.json'
    if path.exists():
        if load(path)['contract_sha256'] != contract_hash:
            raise ValueError('Resume contract changed; use a new output directory')
    else:
        atomic(path,{'contract_sha256':contract_hash,'contract':contract,'created_utc':utc()})
    return path,contract,contract_hash,jobs


def main(args):
    import psutil
    output = args.output.resolve()
    if not output.is_relative_to(LOCAL.resolve()):
        raise ValueError('Private evidence must remain under the campaign local/n2 directory')
    output.mkdir(parents=True,exist_ok=True)
    process = psutil.Process()
    if os.name == 'nt':
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    lock = WriterLock(output)
    worker = None
    completed, failures = {}, {}
    started = time.monotonic()
    active = None
    try:
        admission,contract,contract_hash,jobs = prepare(args,output)
        cells = []
        for profile in args.profiles:
            for job in jobs:
                cell_id = profile+'/'+job['job_id']
                cache_key = stable_hash({'contract':contract_hash,'profile':profile,'job':job})
                checkpoint = output/'cells'/profile/job['job_id']/'CHECKPOINT.json'
                if checkpoint.exists():
                    prior = load(checkpoint)
                    if prior['cache_key'] != cache_key:
                        raise ValueError('Cell cache key mismatch')
                    verify(prior['result'])
                    result = load(prior['result']['path'])
                    for evidence in result.get('evidence',[]):
                        verify(evidence)
                    if prior['status']=='COMPLETE':
                        completed[cell_id] = prior['result']
                        continue
                    if not args.retry_failed:
                        failures[cell_id] = prior['result']
                        continue
                cells.append((profile,job,cache_key,checkpoint,cell_id))
        total = len(args.profiles)*len(jobs)
        planned = len(cells)
        if args.limit:
            cells = cells[:args.limit]
        last_report = -10.0
        def report(status,force=False,error=None):
            nonlocal last_report
            if not force and time.monotonic()-last_report < 5:
                return
            last_report = time.monotonic()
            atomic(output/'PROGRESS.json',{'schema':'n2-native-screen-progress-v1','utc':utc(),'pid':os.getpid(),
                'status':status,'contract_sha256':contract_hash,'completed':len(completed),'failed':len(failures),
                'total':total,'pending_not_dispatched':total-len(completed)-len(failures)-(1 if active else 0),
                'active':active,'elapsed_sec':time.monotonic()-started,'error':error,
                'numerical_workers':1 if worker else 0,'gpu':contract['gpu'],'gpu_device':contract['gpu_device'],'quality_status':'NOT_SCORED'})
            atomic(output/'RESULT_INDEX.json',{'contract_sha256':contract_hash,'completed':completed,'failed':failures})
        report('PREPARED',True)
        if args.prepare_only:
            print(json.dumps({'status':'PREPARED_NO_INFERENCE','total':total,'pending':planned,'output':str(output)}))
            return 0
        for profile,job,cache_key,checkpoint,cell_id in cells:
            if shutil.disk_usage(output).free < args.reserve_gib*1024**3:
                raise OSError('Free disk reserve reached; stopped before allocating another cell')
            if worker is None or worker.identity['profile'] != profile:
                if worker:
                    worker.stop()
                worker = None
                report('LOADING_PROFILE',True)
                worker = Worker(admission,profile,output,lock,args.load_timeout_sec)
            attempt = checkpoint.parent/('attempt_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8])
            attempt.mkdir(parents=True)
            active = {'cell_id':cell_id,'attempt':str(attempt),'worker_pid':worker.proc.pid,'started_utc':utc(),
                      'timeout_sec':args.timeout_sec,'queue_depth':0}
            atomic(attempt/'ATTEMPT.json',{'cache_key':cache_key,**active})
            report('RUNNING',True)
            try:
                worker.send({'action':'run','job':job,'cache_key':cache_key,'attempt':str(attempt)})
                reply = worker.receive(args.timeout_sec,lambda: report('RUNNING'))
                if reply.get('job_id')!=job['job_id'] or reply.get('status') not in ('COMPLETE','FAILED'):
                    raise RuntimeError('Unexpected resident-worker protocol result: '+str(reply))
                result_binding = reply['result']
                verify(result_binding)
                result = load(result_binding['path'])
                if result['cache_key']!=cache_key:
                    raise ValueError('Worker result cache key mismatch')
            except BaseException as exc:
                worker.stop()
                worker_log = bind(worker.directory/'WORKER_RECEIPT.json')
                worker = None
                result = {'status':'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'FAILED',
                          'failure_class':'INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else classify(exc),
                          'quality_status':'NOT_SCORED','bad_score':None,'job_id':job['job_id'],'profile':profile,
                          'cache_key':cache_key,'error':f'{type(exc).__name__}: {exc}'[:8192],
                          'finished_utc':utc(),'owned_worker_log':worker_log,
                          'evidence':[bind(p) for p in sorted(attempt.iterdir()) if p.is_file() and p.name!='COORDINATOR_RESULT.json']}
                # A worker may finish just as the parent's timeout expires.
                # Preserve its result verbatim and keep the coordinator verdict separate.
                atomic(attempt/'COORDINATOR_RESULT.json',result)
                result_binding = bind(attempt/'COORDINATOR_RESULT.json')
                if isinstance(exc,KeyboardInterrupt):
                    atomic(checkpoint,{'cache_key':cache_key,'status':result['status'],'result':result_binding})
                    failures[cell_id]=result_binding
                    active=None
                    report('INTERRUPTED',True)
                    raise
            atomic(checkpoint,{'cache_key':cache_key,'status':result['status'],'result':result_binding})
            if result['status']=='COMPLETE':
                completed[cell_id]=result_binding
                failures.pop(cell_id,None)
            else:
                failures[cell_id]=result_binding
                if worker:
                    worker.stop()
                    worker=None
            active=None
            report('RUNNING',True)
            print(json.dumps({'cell_id':cell_id,'status':result['status'],'completed':len(completed),'failed':len(failures)}),flush=True)
        final_status = 'COMPLETE' if len(completed)==total else ('COMPLETE_WITH_RUNTIME_FAILURES' if len(completed)+len(failures)==total else 'PARTIAL')
        if worker:
            worker.stop()
            worker=None
        report(final_status,True)
        return 2 if failures else 0
    except BaseException as exc:
        atomic(output/('COORDINATOR_ERROR_'+uuid.uuid4().hex[:12]+'.json'),
               {'utc':utc(),'error':f'{type(exc).__name__}: {exc}'[:8192],'failure_class':classify(exc),
                'traceback':traceback.format_exc()[-16384:],'active':active})
        if 'report' in locals() and not isinstance(exc,KeyboardInterrupt):
            report('COORDINATOR_FAILED',True,error=str(exc)[:8192])
        raise
    finally:
        if worker:
            worker.stop()
        lock.close()


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        worker_main(sys.argv[2],sys.argv[3])
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--output',type=Path,required=True)
        parser.add_argument('--manifest',type=Path,default=LOCAL.parent/'data/BASELINE_SCREEN_AUDIO_ONLY.json')
        parser.add_argument('--build-receipt',type=Path,default=HERE/'NATIVE_BUILD_RECEIPT.json')
        parser.add_argument('--profiles',nargs='+',choices=PROFILE_NAMES,default=list(PROFILE_NAMES))
        parser.add_argument('--prepare-only',action='store_true')
        parser.add_argument('--limit',type=int,default=0,help='Limit pending cells; never truncate audio')
        parser.add_argument('--retry-failed',action='store_true')
        parser.add_argument('--timeout-sec',type=float,default=1800)
        parser.add_argument('--load-timeout-sec',type=float,default=120)
        parser.add_argument('--reserve-gib',type=float,default=75)
        parser.add_argument('--cpu',type=int)
        parser.add_argument('--device',choices=('cpu','cuda'),default='cpu')
        parser.add_argument('--gpu-index',type=int,default=0,help='Explicit CUDA device index; ignored for CPU')
        parsed = parser.parse_args()
        parsed.gpu = parsed.gpu_index if parsed.device=='cuda' else -1
        if parsed.limit<0 or parsed.timeout_sec<=0 or parsed.load_timeout_sec<=0 or parsed.reserve_gib<75 or parsed.gpu_index < 0 or len(set(parsed.profiles))!=len(parsed.profiles):
            parser.error('Invalid limits, duplicate profiles, or disk reserve below75 GiB')
        raise SystemExit(main(parsed))
