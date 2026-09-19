"""Full-source native confirmation protocol; README_S6D_NATIVE_CONFIRMATION_PROTOCOL_V2.md."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import threading
import time
import psutil
sys.dont_write_bytecode = True
RUNNER_SHA='fdffb4cae7c111302b90d4128d8b44049354cd225f241868f6d83a5a2fab15b4'
EVIDENCE_SHA='bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2'
RUNNER_PATH=Path(r'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6D\20260913T195357Z\runner\source_epoch_census_v4\s6d_runner_v1.py')


def import_exact(path,sha,name):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Pinned module source differs')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


COMMON=import_exact(RUNNER_PATH,RUNNER_SHA,'s6d_confirmation_runner_common_v4')
binding,finite_number,identity_matches,load,save,utc=(getattr(COMMON,n) for n in ('binding','finite_number','identity_matches','load','save','utc'))


def verify(value):
    if binding(value['path'],value['sha256'])!=value:raise ValueError('Exact source bytes/path differ')
    return value


def predeclared_source(job):
    frames,pcm=job.get('expected_frames'),job.get('audio_pcm_sha256')
    if type(frames) is not int or frames<=0 or type(job.get('expected_identity_frames')) is not int or job['expected_identity_frames']!=frames:
        raise ValueError('Both complete source frame counts must be predeclared')
    if not isinstance(pcm,str) or len(pcm)!=64 or any(c not in '0123456789abcdef' for c in pcm):
        raise ValueError('Full source PCM SHA256 must be predeclared')


def admit_affinity(process,manifest):
    cpus=manifest['limits'].get('cpu_affinity');allowed=process.cpu_affinity()
    if not isinstance(cpus,list) or cpus!=[12,13,14,15] or any(type(x) is not int or x not in allowed for x in cpus):
        raise ValueError('Exact root-admitted CPU affinity12,13,14,15 required')
    process.cpu_affinity(cpus)
    if sorted(process.cpu_affinity())!=cpus:raise ValueError('Actual CPU affinity readback differs')
    return cpus


def publish_exclusive(path,value,checkpoint):
    """Fully written fresh artifact, then owner/STOP check immediately before commit."""
    path=Path(path);temporary=path.with_name('.'+path.name+'.pending')
    save(temporary,value,exclusive=True)
    for attempt in range(7):
        checkpoint()
        if path.exists():raise FileExistsError(str(path))
        try:os.rename(temporary,path);return
        except PermissionError:
            if attempt==6:raise
            time.sleep(.025*2**attempt)


def tk_evidence(result,job,evidence):
    if not job.get('views'):return None
    target=Path(job['output']).resolve();owned=result.get('owned_resource_closure')
    if not owned or Path(owned['path']).resolve()!=target/'OWNED_RESOURCE_CLOSURE.json':raise ValueError('Owned Tk closure binding required')
    verify(owned);closure=load(owned['path'])
    if (closure.get('resources_closed') is not True or closure.get('cleanup_errors')!=[] or closure.get('setup_or_loop_error') is not None
            or any(closure.get(k) is not True for k in ('root_destroyed','consumer_closed','gallery_spy_restored','render_files_closed'))
            or any(closure.get(k) is not False for k in ('startup_thread_alive','observer_thread_alive'))):
        raise ValueError('Owned Tk resources did not close successfully')
    views=result.get('views') or [];expected=[v['name'] for v in job['views']]
    if len(set(expected))!=len(expected) or [v.get('name') for v in views]!=expected or result.get('gui_tested') is not True:
        raise ValueError('Exact actual Tk view inventory required')
    digest=hashlib.sha256();events={};count=0;origin=None;previous=None;display_triggers=set()
    producing={'s6d_text_ready','transcript_partial','transcript_final','transcript_label_revision','s6d_punctuation_revision'}
    for event in evidence.stream(target/'consumer_events.jsonl'):
        row=dict(event);row.pop('actual_consumed_monotonic_sec',None);count+=1
        digest.update(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n')
        payload=row['payload'];seq=payload['publication_sequence']
        if type(seq) is not int or seq in events:raise ValueError('Nonunique native causal publication')
        events[seq]=(count,payload['pilot_publication_monotonic_sec'],row['event_type'],payload.get('utterance_id'))
        if row['event_type']=='s6d_display':
            if (previous is None or events[previous][2] not in producing or not payload.get('utterance_id')
                    or events[previous][3]!=payload['utterance_id'] or previous in display_triggers):
                raise ValueError('Native display lacks its locked adjacent producing event')
            display_triggers.add(previous)
        previous=seq
        if row['event_type']=='source_started':origin=payload['pilot_publication_monotonic_sec']
    if count<=0 or result.get('source_event_count')!=count or result.get('source_event_order_sha256')!=digest.hexdigest():
        raise ValueError('Native causal event journal binding differs')
    if type(result.get('native_T0_semantic_comparisons')) is not int or result['native_T0_semantic_comparisons']!=len(display_triggers):
        raise ValueError('Native T0 comparison count differs from actual displays')
    artifacts=[]
    for view in views:
        q=view.get('queue') or {};forwarded=view.get('forwarded')
        if (view.get('input_count')!=count or view.get('input_order_sha256')!=digest.hexdigest() or view.get('consumer_closed') is not True
                or q.get('depth')!=0 or type(forwarded) is not int or forwarded<0
                or any(type(q.get(k)) is not int or q[k]<0 for k in ('consumed','coalesced_obsolete_ui_partials'))
                or q['consumed']+q['coalesced_obsolete_ui_partials']!=forwarded
                or 'accepted' in q and q['accepted']!=forwarded):
            raise ValueError('Tk view causal order/count/drain differs')
        render=target/'views'/view['name']/'s6d_gui_render.jsonl'
        # A fully consumed no-text result remains an acoustic failure for scoring,
        # not invented render activity. If a journal exists, every receipt is bound.
        if not render.exists():
            if result.get('native_T0_semantic_comparisons',0)>0:raise ValueError('Actual display output lacks per-view render journal')
            continue
        rb=binding(render);rendered=set()
        for row in evidence.stream(render):
            if row.get('view_id')!=view['name'] or not isinstance(row.get('widget_text'),str) or hashlib.sha256(row['widget_text'].encode()).hexdigest()!=row.get('widget_text_sha256'):
                raise ValueError('Actual widget text/hash/view receipt differs')
            if 'utterance_id' in row:
                payload=row.get('display_payload') or {};seq=row.get('source_native_publication_sequence')
                if seq not in display_triggers or seq in rendered:raise ValueError('Render lacks unique actual native display trigger')
                ordinal,pub,kind,uid=events[seq];rendered.add(seq)
                if (row.get('session_id')!=Path(result['session_dir']).name or row.get('source_started_monotonic_sec')!=origin
                        or row['utterance_id']!=uid or payload.get('utterance_id')!=uid
                        or row.get('causal_view_input_count')!=ordinal or row.get('source_native_publication_monotonic_sec')!=pub
                        or any(payload.get(k)!=row.get(k) for k in ('session_id','source_native_publication_sequence','source_native_publication_monotonic_sec','causal_view_input_count'))):
                    raise ValueError('Render trigger/source clock differs')
                times=[pub,row.get('event_publication_monotonic_sec'),row.get('widget_update_started_monotonic_sec'),row.get('widget_update_finished_monotonic_sec'),row.get('actual_callback_monotonic_sec')]
                if not all(finite_number(t) for t in times) or times!=sorted(times):raise ValueError('Impossible actual widget event clock')
        if rendered!=display_triggers:raise ValueError('Truncated or missing per-view display receipts')
        verify(rb);artifacts.append(rb)
    return dict(owned_resource_closure=owned,render_journals=artifacts,views=len(views),source_event_count=count,
                source_event_order_sha256=digest.hexdigest(),physical_scanout_tested=False)


class NativeStopRequested(RuntimeError):
    pass


def semantic_result(result, job, manifest_bound, helper_bound, identity):
    checks = {
        "status_complete": result.get("status") == "COMPLETE",
        "failure_absent": result.get("failure") is None,
        "native_tested": result.get("native_tested") is True,
        "observer_closed": result.get("resource_observer_closed") is True,
        "observer_errors_empty": result.get("observer_errors") == [],
        "native_completion_errors_empty": result.get("completion_errors") == [],
        "event_consumer_drained": result.get("event_consumer_drained") is True,
        "same_process": result.get("pid") == identity["pid"] and abs(result.get("process_create_time", 0) - identity["creation_time"]) < .001,
        "exact_native_job": result.get("job") == job,
        "exact_manifest": result.get("manifest") == manifest_bound,
        "exact_helper": result.get("helper") == helper_bound,
        "engine_completed": result.get("telemetry", {}).get("state") == "COMPLETED",
    }
    queues = result.get("telemetry", {}).get("s6d")
    if job.get("settings") is not None:
        checks["s6d_queue_state_present"] = isinstance(queues, dict)
    if isinstance(queues, dict):
        consumer = queues.get("event_consumer")
        checks["consumer_queue_empty"] = isinstance(consumer, dict) and consumer.get("depth") == 0
        for lane in ("journal", "punctuation", "policy"):
            worker = queues.get(lane)
            if worker is not None:
                checks[lane + "_fully_drained"] = (
                    worker.get("depth") == 0 and worker.get("accepted") == worker.get("completed")
                    and worker.get("error") is None and worker.get("closed") is True and worker.get("thread_alive") is False)
    if not all(checks.values()):
        raise ValueError("native semantic completion rejected: " + ", ".join(k for k, v in checks.items() if not v))
    return checks


class ProtocolBridge:
    def __init__(self, identity, heartbeat_path, stop_path, native_job, heartbeat_interval=5):
        self.identity, self.heartbeat_path, self.stop_path = identity, Path(heartbeat_path), Path(stop_path)
        self.native_job = native_job
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.closed = threading.Event()
        self.progress_count = 0
        self.checkpoint_count = 0
        self.latest = {"stage": "WRAPPER_ADMISSION", "done_source_sec": 0., "source_admitted_sec": 0., "completed_work_items": 0}
        self.failure = None
        self.completed = False
        self.observer_errors = []
        self.heartbeat_interval = heartbeat_interval
        self.thread = threading.Thread(target=self.observe, name="s6d-native-protocol", daemon=True)

    def update(self, stage, done=0., admitted=0., completed=0):
        with self.lock:
            previous = self.latest
            actual_advance = (stage != previous["stage"] or done > previous["done_source_sec"]
                or admitted > previous["source_admitted_sec"] or completed > previous["completed_work_items"])
            if actual_advance:
                self.progress_count += 1
            self.latest = {"stage": stage, "done_source_sec": max(done, previous["done_source_sec"]),
                "source_admitted_sec": max(admitted, previous["source_admitted_sec"]),
                "completed_work_items": max(completed, previous["completed_work_items"])}

    def heartbeat(self):
        with self.lock:
            value = {**self.identity, "utc": utc(), "status": "FAILED" if self.failure else ("COMPLETE" if self.completed else "RUNNING"),
                "progress_count": self.progress_count, "checkpoint_count": self.checkpoint_count,
                "native_job_id": self.native_job["job_id"], "native_output": self.native_job["output"],
                "total_source_sec": self.native_job["audio_duration_sec"], "progress": dict(self.latest),
                "stop_requested": self.stop.is_set(), "error": self.failure, "queue_age_s": None}
        save(self.heartbeat_path, value)

    def observe(self):
        last_write = 0
        try:
            while not self.closed.is_set():
                self.check_stop()
                if time.monotonic() - last_write >= self.heartbeat_interval:
                    self.heartbeat()
                    last_write = time.monotonic()
                self.closed.wait(.1)
        except BaseException as exc:
            self.observer_errors.append(repr(exc))
            self.stop.set()

    def check_stop(self):
        if self.stop_path.exists():
            request=load(self.stop_path,retries=3,delay=.02)
            if not isinstance(request,dict):raise ValueError('STOP must be a complete object')
            if (identity_matches(request,self.identity) and request.get('pid')==self.identity['pid']
                    and finite_number(request.get('creation_time')) and abs(request['creation_time']-self.identity['creation_time'])<.001):
                self.stop.set()
        return self.stop.is_set()

    def guard(self):
        if self.check_stop() or self.observer_errors:raise NativeStopRequested('Same-owner STOP or protocol observer failure prevents completion')

    def checkpoint(self, engine, telemetry, job, output):
        if job != self.native_job or Path(output).resolve() != Path(self.native_job["output"]).resolve():
            self.stop.set()
            raise RuntimeError("native checkpoint job/output mismatch")
        with self.lock:
            self.checkpoint_count += 1
        queues = telemetry.get("s6d") or {}
        completed = sum(worker.get("completed", 0) for key, worker in queues.items()
            if key in ("journal", "punctuation", "policy") and isinstance(worker, dict))
        consumer = queues.get("event_consumer")
        if isinstance(consumer, dict):
            completed += consumer.get("consumed", 0)
        done, admitted = telemetry.get("asr_cursor_sec", 0.), telemetry.get("source_duration_sec", 0.)
        if not all(finite_number(x) for x in (done, admitted, completed)):
            engine.stop()
            raise RuntimeError("nonfinite native progress")
        self.update(str(telemetry.get("state", engine.state)), done, admitted, completed)
        if self.check_stop() or self.observer_errors:
            engine.stop()
            raise NativeStopRequested("explicit same-run STOP_REQUEST; native engine.stop invoked")

    def close(self):
        self.closed.set()
        if self.thread.ident is not None:self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError("native protocol observer failed to close")


def execute(helper_path, helper_sha256, manifest_path, manifest_sha256, native_job_id, heartbeat_interval=5):
    helper_bound, manifest_bound = binding(helper_path, helper_sha256), binding(manifest_path, manifest_sha256)
    manifest = load(manifest_path)
    wrapper_bound=binding(__file__)
    if manifest.get('protocol_wrapper')!=wrapper_bound:raise ValueError('Manifest must bind the exact confirmation wrapper')
    if manifest.get("schema") != "s6d-native-pilot.v1" or manifest['helper']!=helper_bound:
        raise ValueError("native manifest/helper contract mismatch")
    jobs = [job for job in manifest["jobs"] if job["job_id"] == native_job_id]
    if len(jobs) != 1:
        raise ValueError("native job ID is absent or ambiguous")
    job = jobs[0]
    predeclared_source(job)
    protocol=manifest['protocol_sources']
    if protocol['runner']!=binding(RUNNER_PATH,RUNNER_SHA) or protocol['evidence']['sha256']!=EVIDENCE_SHA:
        raise ValueError('Accepted runner/evidence protocol graph required')
    verify(protocol['evidence'])
    if manifest.get('evidence_helper')!=protocol['evidence']:raise ValueError('Native and protocol evidence helper bindings differ')
    evidence=import_exact(protocol['evidence']['path'],EVIDENCE_SHA,'s6d_confirmation_full_source_evidence')
    if evidence.frame(job['audio_duration_sec'])!=job['expected_frames']:raise ValueError('Declared source duration differs')
    sources=manifest['execution_files']+manifest.get('support_files',[])+list(protocol.values())
    for source in sources:verify(source)
    process=psutil.Process()
    affinity=admit_affinity(process,manifest)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    identity = {"run_id": os.environ["S6D_RUN_ID"], "job_id": os.environ["S6D_JOB_ID"],
        "child_run_id": os.environ["S6D_CHILD_RUN_ID"], "pid": os.getpid(), "creation_time": psutil.Process().create_time()}
    heartbeat_path, completion_path, stop_path = (Path(os.environ[k]) for k in (
        "S6D_HEARTBEAT_PATH", "S6D_COMPLETION_PATH", "S6D_STOP_REQUEST_PATH"))
    if heartbeat_path.exists() or completion_path.exists() or Path(job["output"]).exists():
        raise ValueError("native wrapper requires fresh protocol and native output paths")
    bridge = ProtocolBridge(identity, heartbeat_path, stop_path, job, heartbeat_interval)
    failure, checks, result_bound, audit_bound, gui_proof = None, None, None, None, None
    try:
        bridge.thread.start();bridge.guard()
        proof=evidence.pcm_proof(job['audio']['path'],job['audio'])
        if proof['frames']!=job['expected_frames'] or proof['sha256']!=job['audio_pcm_sha256']:
            raise ValueError('Actual source differs from predeclared complete PCM')
        bridge.update('FULL_SOURCE_INPUT_VERIFIED');bridge.guard()
        # The frozen native model constructors validate all8 declared model hashes.
        # Do not duplicate multi-GiB asset hashing in this bridge or supervisor health loop.
        if bridge.check_stop():
            raise NativeStopRequested("STOP requested before native initialization")
        module_name = "s6d_native_pilot_frozen_helper"
        specification = importlib.util.spec_from_file_location(module_name, helper_bound["path"])
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        specification.loader.exec_module(module)
        if "checkpoint" not in inspect.signature(module.run_one).parameters:
            raise ValueError("frozen native helper lacks the reviewed checkpoint STOP hook")
        bridge.update("NATIVE_RUN_ONE_ENTERED")
        module.run_one(Path(manifest_bound["path"]), native_job_id, checkpoint=bridge.checkpoint)
        bridge.guard()
        result_path = Path(job["output"]) / "RESULT.json"
        result_bound = binding(result_path)
        native_result=load(result_path)
        checks = semantic_result(native_result, job, manifest_bound, helper_bound, identity)
        if bridge.checkpoint_count == 0:
            raise ValueError("native helper did not invoke reviewed checkpoint hook")
        bridge.update('VERIFYING_FULL_SOURCE_COMPLETION')
        audit=evidence.audit(manifest_bound['path'],manifest_bound['sha256'],native_job_id)
        audit_bound=binding(Path(job['output'])/'FULL_SOURCE_AUDIT.json') if (Path(job['output'])/'FULL_SOURCE_AUDIT.json').exists() else None
        if audit_bound is not None:raise ValueError('Fresh full-source audit path required')
        publish_exclusive(Path(job['output'])/'FULL_SOURCE_AUDIT.json',audit,bridge.guard)
        audit_bound=binding(Path(job['output'])/'FULL_SOURCE_AUDIT.json')
        if (audit['status']!='PASS_OFFLINE_EVIDENCE' or audit['errors']!=[] or audit['expected_frames_predeclared'] is not True
                or audit['result']!=result_bound or audit['source']!=protocol['evidence']
                or audit['journals']['source']['frames']!=job['expected_frames'] or audit['journals']['source']['sha256']!=job['audio_pcm_sha256']):
            raise ValueError('Full source/journal/dispatch completion evidence rejected')
        gui_proof=tk_evidence(native_result,job,evidence)
        bridge.update("SEMANTIC_COMPLETION_VALIDATED");bridge.guard()
    except BaseException as exc:
        failure = type(exc).__name__ + ": " + str(exc)
        bridge.failure = failure
    finally:
        try:
            bridge.close()
        except BaseException as exc:
            failure = failure or repr(exc)
            bridge.failure = failure
        try:bridge.guard();bridge.heartbeat()
        except BaseException as exc:failure=failure or repr(exc);bridge.failure=failure
    def final_guard():
        bridge.guard()
        if bridge.thread.is_alive():raise ValueError('Protocol observer still alive')
        if sorted(process.cpu_affinity())!=affinity:raise ValueError('Native affinity changed')
        verify(helper_bound);verify(manifest_bound);verify(wrapper_bound)
        for source in sources:verify(source)
        if result_bound:verify(result_bound)
        if audit_bound:verify(audit_bound)
        if gui_proof:
            for source in [gui_proof['owned_resource_closure']]+gui_proof['render_journals']:verify(source)
        bridge.guard()
    if failure is None:
        try:final_guard()
        except BaseException as exc:failure=repr(exc)
    result = {**identity, "native_job_id": native_job_id, "created_utc": utc(),
        "status": "COMPLETE" if failure is None else "FAILED", "failure": failure,
        "manifest": manifest_bound, "helper": helper_bound, "wrapper": wrapper_bound,
        "native_result": result_bound, "declared_model_assets": manifest["assets"],
        "model_asset_hash_validation": "Frozen native models.py constructors before execution; wrapper/supervisor do not repeat large-asset hashing",
        "semantic_checks": checks, "protocol_observer_closed": not bridge.thread.is_alive(),
        "protocol_observer_errors": bridge.observer_errors, "checkpoint_count": bridge.checkpoint_count,
        "progress_count": bridge.progress_count, "native_run_one_same_process": True,
        "subprocess_spawned_by_wrapper": False, "stop_requested": bridge.stop.is_set(),
        'protocol_sources':protocol,'full_source_evidence_validated':failure is None,'completion_audit':audit_bound,
        'affinity_verified':affinity,'tk_view_evidence_validated':gui_proof is not None and failure is None,
        'tk_view_evidence':gui_proof,'actual_gui_job':bool(job.get('views'))}
    if failure is None:
        try:publish_exclusive(completion_path,result,final_guard)
        except BaseException as exc:
            failure=repr(exc);result.update(status='FAILED',failure=failure,full_source_evidence_validated=False,tk_view_evidence_validated=False,stop_requested=bridge.stop.is_set())
    if failure is not None:
        save(completion_path.with_name("WRAPPER_FAILURE.json"), result, exclusive=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--helper-sha256", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--native-job-id", required=True)
    args = parser.parse_args()
    result = execute(args.helper, args.helper_sha256, args.manifest, args.manifest_sha256, args.native_job_id)
    print(json.dumps({"status": result["status"], "failure": result["failure"], "native_job_id": args.native_job_id}), flush=True)
    raise SystemExit(0 if result["status"] == "COMPLETE" else 2)
