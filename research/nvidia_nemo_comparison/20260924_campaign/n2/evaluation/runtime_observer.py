"""Online gallery-policy observers on actual runtime windows, never Q truth. See README.md."""
from __future__ import annotations

from collections import Counter, OrderedDict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import queue
import threading
import time


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _payload_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _save(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n",encoding="utf-8")


class RuntimeGalleryObserver:
    """One bounded writer evaluates gallery policies as observed events arrive.

    No audio/model inference, transcript truth, source identity, seat or actor
    metadata is read. Names are compared against permitted E profiles only.
    Model/ASR event delivery never waits for gallery scoring; overflow fails
    explicitly. This is an online shadow-policy study, not an independent GUI
    run or a zero-overhead resource benchmark.
    """

    def __init__(self,embedding,gallery_index_path,output_dir,session_id):
        from app.n2_identity import N2Gallery,N2NameMap
        from edge_speech_pipeline.research_s6d import S6DSettings
        from edge_speech_pipeline.research_s7_presentation import S7PresentationState
        if embedding not in {"E0","E1"} or not session_id:
            raise ValueError("Explicit embedding and session required")
        index=json.loads(Path(gallery_index_path).read_text(encoding="utf-8"))
        if index.get("schema") != "n2-runtime-safe-gallery-index-v1" or index["encoder"] != embedding:
            raise ValueError("Observer requires sanitized runtime-only gallery index for this encoder")
        self.embedding,self.session_id=embedding,session_id
        self.out=Path(output_dir);self.out.mkdir(parents=True,exist_ok=True)
        self.namespace=index["namespace"]
        self.conditions=[]
        settings=S6DSettings()
        options={"session_id":session_id,"ownership_mode":"timestamped_spans_v3","mode":"M2"}
        self.baseline=S7PresentationState(settings,dict(options,mode="M1"))
        shared_reject_view=None
        self.ignored_no_gallery=[]
        for entry in index["conditions"]:
            if entry["tier_seconds"] != 15 or entry["matched_duration_diagnostic"]:
                continue
            if entry["mode"] == "none":
                self.ignored_no_gallery.append(entry["gallery_id"])
                continue
            path=Path(entry["gallery"]["path"])
            if _hash(path) != entry["gallery"]["sha256"]:
                raise ValueError("Gallery index hash mismatch")
            document=json.loads(path.read_text(encoding="utf-8"))
            if not document.get("research_only"):
                raise ValueError("Research observer requires isolated research gallery")
            gate=document["calibration"]
            if gate["gallery_profiles_sha256"] != _payload_hash(document["profiles"]):
                raise ValueError("Gate/profile population hash mismatch")
            if gate["gate_sha256"] != _payload_hash({k:v for k,v in gate.items() if k!="gate_sha256"}):
                raise ValueError("Gate integrity mismatch")
            gallery=N2Gallery(document,self.namespace)
            # All uncalibrated open policies produce the same Unknown fields
            # in M2. Share that presentation state, not score/name-map state.
            shared=entry["mode"]!="closed" and gate.get("status")!="CALIBRATED"
            if shared and shared_reject_view is None:
                shared_reject_view={"presentation":S7PresentationState(settings,options),"first_visible":{},"first_final":{}}
            view=shared_reject_view if shared else {"presentation":S7PresentationState(settings,options),"first_visible":{},"first_final":{}}
            self.conditions.append({"entry":entry,"gallery":gallery,"names":N2NameMap(gallery,closed=entry["mode"]=="closed"),
                                    "track_names":{},"counts":Counter(),**view})
        self.queue=queue.Queue(maxsize=8192)
        self.lock=threading.Lock();self.serial=0;self.closed=False;self.error=None
        self.pending=OrderedDict();self.pending_decisions=OrderedDict();self.seen_decisions=set()
        self.event_counts=Counter();self.match_counts=Counter();self.max_depth=0;self.max_age=0.;self.work_seconds=0.
        self.handles={name:(self.out / (name+".jsonl")).open("x",encoding="utf-8") for name in ["n2_gallery_decisions","n2_actual_embedding_windows","n2_caption_events","n2_activity_frames"]}
        _save(self.out / "OBSERVER_ADMISSION.json",{"schema":"n2-online-gallery-observer-v1","encoder":embedding,
              "session_id":session_id,"namespace":self.namespace,"gallery_index_path":str(gallery_index_path),
              "gallery_index_sha256":_hash(gallery_index_path),"observer_sha256":_hash(__file__),
              "conditions":[c["entry"] for c in self.conditions],"no_gallery_scope":"engine actual rows; baseline observer clone used only for invariance",
              "query_truth_loaded":False,"model_calls":0,"queue_capacity":8192,"timing":"observed callback admission and worker clocks; source intervals inherited; not GUI timing"})
        self.worker=threading.Thread(target=self._run,name="n2-gallery-observer",daemon=True)
        self.worker.start()

    def event(self,event_type,source_sec,payload):
        if event_type not in {"research_embedding","speaker_decision","s6d_text_ready","transcript_partial","transcript_final","transcript_label_revision","s6d_punctuation_revision","n2_diarization_frames"}:
            return
        with self.lock:
            if self.closed or self.error:
                raise RuntimeError("N2 observer closed or failed: "+str(self.error))
            self.serial+=1
            row=(self.serial,time.perf_counter(),event_type,float(source_sec),deepcopy(payload))
            try:self.queue.put_nowait(row)
            except queue.Full as exc:raise RuntimeError("N2 observer bounded queue exhausted; no silent drops") from exc
            self.max_depth=max(self.max_depth,self.queue.qsize())

    def _write(self,name,row):
        self.handles[name].write(json.dumps(row,separators=(",",":"),allow_nan=False)+"\n")

    def _run(self):
        while True:
            item=self.queue.get()
            try:
                if item is None:return
                start=time.perf_counter();self.max_age=max(self.max_age,start-item[1])
                if self.error is None:
                    self._process(*item)
                    self.work_seconds+=time.perf_counter()-start
            except BaseException as exc:
                self.error=type(exc).__name__+": "+str(exc)
            finally:self.queue.task_done()

    @staticmethod
    def _evidence_id(payload):
        return payload.get("evidence_event_id") or payload.get("input_event_id") or payload.get("evidence_id") or payload.get("event_id")

    def _process(self,serial,admitted,kind,source_sec,payload):
        self.event_counts[kind]+=1
        if kind=="n2_diarization_frames":
            self._write("n2_activity_frames",{"observer_sequence":serial,"observer_admitted_monotonic":admitted,"payload":payload})
            return
        if kind=="research_embedding":
            identifier=payload.get("evidence_event_id",payload.get("event_id"))
            if not identifier or identifier in self.pending or identifier in self.seen_decisions or len(self.pending)>=4096:
                raise ValueError("Missing/repeated/bounded embedding event identity")
            vector=payload.get("normalized_embedding",payload.get("vector"))
            if vector is None:raise ValueError("Actual embedding event lacks vector")
            event=dict(payload,vector=vector,event_id=identifier)
            event.setdefault("speech",True);event.setdefault("overlap",False)
            event.setdefault("clean_intervals",[[event["source_start_sec"],event["source_end_sec"]]])
            self.pending[identifier]=(event,serial,admitted)
            self._write("n2_actual_embedding_windows",dict(event,observer_sequence=serial,observer_admitted_monotonic=admitted,encoder=self.embedding))
            if identifier in self.pending_decisions:
                self._match(identifier,*self.pending_decisions.pop(identifier))
            return
        if kind=="speaker_decision":
            identifier=self._evidence_id(payload)
            if not identifier or identifier in self.seen_decisions:
                self.match_counts["unmatched_or_duplicate_decision"]+=1;return
            if identifier in self.pending:self._match(identifier,payload,serial,admitted)
            elif len(self.pending_decisions)<4096:self.pending_decisions[identifier]=(payload,serial,admitted)
            else:raise ValueError("Unmatched decision capacity exhausted")
            return
        payload.setdefault("session_id",self.session_id)
        identities={}
        track=payload.get("replacement_tracker_id",payload.get("tracker_id"))
        for condition in self.conditions:
            known=condition["track_names"].get(track)
            identities[condition["entry"]["gallery_id"]]={
                "latest_label":known["display_label"] if known else "Unknown",
                "latest_known_profile_id":known.get("known_profile_id") if known else None,
                "latest_known_name":known.get("known_name") if known else None,
                "latest_naming_state":known.get("naming_state","unknown") if known else "unknown"}
        self._write("n2_caption_events",{"observer_sequence":serial,"observer_admitted_monotonic":admitted,
                    "event_type":kind,"source_sec":source_sec,"payload":payload,"identity_snapshots":identities})

    def _replay_captions(self):
        """Replay after model lanes drain, using identities captured online.

        Source/publication order is causal. Shadow display timing is modelled,
        not actual GUI timing. Never use the final name map to relabel history.
        """
        for line in (self.out/"n2_caption_events.jsonl").read_text(encoding="utf-8").splitlines():
            record=json.loads(line);payload=record["payload"];kind=record["event_type"]
            stamp=payload.get("publication_monotonic_sec",record["observer_admitted_monotonic"])
            self.baseline.consume(kind,payload,now=stamp)
            processed=set()
            for condition in self.conditions:
                view=condition["presentation"]
                if id(view) in processed:continue
                processed.add(id(view))
                clone=deepcopy(payload)
                if kind in {"transcript_partial","transcript_final","transcript_label_revision"}:
                    clone.update(record["identity_snapshots"][condition["entry"]["gallery_id"]])
                shown=view.consume(kind,clone,now=stamp)
                if shown is not None:
                    key=shown["utterance_id"]
                    if shown.get("visible",True):condition["first_visible"].setdefault(key,deepcopy(shown))
                    if shown.get("final"):condition["first_final"].setdefault(key,deepcopy(shown))

    def _match(self,identifier,payload,serial,admitted):
        event,embedding_serial,embedding_admitted=self.pending.pop(identifier)
        self.seen_decisions.add(identifier)
        decision=deepcopy(payload.get("decision",payload))
        for key in ("tracker_id","track_id","anonymous_label","cluster_id","state","committed"):
            if key in payload:decision[key]=payload[key]
        track=decision.get("tracker_id",decision.get("track_id"))
        if track is None:
            self.match_counts["actual_decision_without_track"]+=1
        self.match_counts["matched_actual_embedding_decisions"]+=1
        for condition in self.conditions:
            result=condition["names"].resolve(decision,event)
            if track is not None:condition["track_names"][track]=result
            condition["counts"][result["naming_state"]]+=1
            self._write("n2_gallery_decisions",{"gallery_id":condition["entry"]["gallery_id"],"mode":condition["entry"]["mode"],
                        "event_id":identifier,"observer_sequence":serial,"embedding_observer_sequence":embedding_serial,
                        "observer_admitted_monotonic":admitted,"embedding_admitted_monotonic":embedding_admitted,
                        "observer_decision_finished_monotonic":time.perf_counter(),"source_start_sec":event["source_start_sec"],
                        "source_end_sec":event["source_end_sec"],"clean_intervals":event["clean_intervals"],
                        "evidence_kind":event.get("evidence_kind"),"speech":event["speech"],"overlap":event["overlap"],
                        "actual_tracker_id":track,"decision":result,"window_selection":"actual_runtime_no_Q_truth",
                        "scope":"online_shadow_gallery_policy_no_additional_model_call"})

    def finish(self,final_rows):
        with self.lock:
            if self.closed:raise RuntimeError("Observer already finished")
            self.closed=True
        self.queue.put(None);self.worker.join(120)
        if self.worker.is_alive():raise RuntimeError("Observer failed to drain within120 seconds")
        for handle in self.handles.values():handle.flush();handle.close()
        if self.error:raise RuntimeError("N2 observer failed: "+self.error)
        replay_start=time.perf_counter();self._replay_captions();replay_seconds=time.perf_counter()-replay_start
        base_rows=self.baseline.snapshot_rows()
        def canonical(rows,formatted=False):
            groups={}
            for row in rows:groups.setdefault(row["utterance_id"],[]).append(row)
            result={}
            for key,parts in groups.items():
                if all("raw_asr_text" in p for p in parts):
                    parts.sort(key=lambda p:p.get("token_range",[0])[0])
                    result[key]="".join((p.get("final_punctuated_display_text") or p.get("provisional_display_text") or p["raw_asr_text"]) if formatted else p["raw_asr_text"] for p in parts)
                elif len(parts)==1:
                    result[key]=parts[0].get("display_text",parts[0].get("text","")) if formatted else parts[0].get("text","")
                else:raise ValueError("Unqualified duplicated final caption rows")
            return result
        raw=lambda rows:canonical(rows,False)
        formatted=lambda rows:canonical(rows,True)
        _save(self.out / "ACTUAL_FINAL_ROWS.json",final_rows)
        _save(self.out / "OBSERVER_BASE_ROWS.json",base_rows)
        conditions=[]
        for condition in self.conditions:
            rows=condition["presentation"].snapshot_rows()
            path=self.out / (condition["entry"]["gallery_id"]+"_ROWS.json")
            _save(path,rows)
            stages_path=self.out / (condition["entry"]["gallery_id"]+"_STAGES.json")
            _save(stages_path,{"first_visible":list(condition["first_visible"].values()),
                               "first_final":list(condition["first_final"].values()),"latest":rows,
                               "scope":"causal replay of original publications and online name snapshots; modelled shadow display timing, not actual GUI; initial hypotheses may differ from final words"})
            conditions.append({"gallery_id":condition["entry"]["gallery_id"],"mode":condition["entry"]["mode"],
                               "rows_path":str(path),"rows_sha256":_hash(path),"rows":len(rows),
                               "stages_path":str(stages_path),"stages_sha256":_hash(stages_path),
                               "raw_words_equal_observer_base":raw(rows)==raw(base_rows),
                               "formatted_words_equal_observer_base":formatted(rows)==formatted(base_rows),
                               "naming_states":dict(condition["counts"]),"name_map":condition["names"].snapshot(),
                               "presentation_rejections":dict(condition["presentation"].rejected)})
        report={"schema":"n2-online-gallery-observer-result-v1","status":"ACTUALLY_RUN_ONLINE_SHADOW_POLICIES",
                "session_id":self.session_id,"encoder":self.embedding,"conditions":conditions,
                "actual_rows_equal_observer_base_raw":raw(final_rows)==raw(base_rows),
                "actual_rows_equal_observer_base_formatted":formatted(final_rows)==formatted(base_rows),
                "event_counts":dict(self.event_counts),"embedding_matches":dict(self.match_counts),
                "embeddings_without_actual_decision":len(self.pending),"decisions_without_actual_embedding":len(self.pending_decisions),
                "queue_peak":self.max_depth,"queue_max_observed_age_seconds":self.max_age,"observer_compute_seconds":self.work_seconds,
                "deferred_caption_replay_seconds":replay_seconds,
                "independent_resource_trial":False,"GUI_each_condition":"NOT_TESTED_SHADOW_PRESENTATION_ONLY", "query_truth_loaded":False,
                "first_visible_first_final_latest":"causal replay snapshots from publications and names captured online; modelled shadow display clocks, actual primary Controller rows separately retained",
                "actual_query_windows_path":str(self.out / "n2_actual_embedding_windows.jsonl"),
                "gallery_decisions_path":str(self.out / "n2_gallery_decisions.jsonl")}
        _save(self.out / "OBSERVER_RESULT.json",report)
        return report
