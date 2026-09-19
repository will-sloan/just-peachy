"""S6C model-free S6B foundation audit. See README_S6C_FOUNDATION_AUDIT.md."""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import runpy
import shutil
import sys
import time

import numpy as np

SIM = Path(__file__).resolve().parents[1]
S6B = SIM / "reports/S6B/20260909T230840Z"
S6C = SIM / "reports/S6C/20260910T123540Z"
PACK = SIM.parent / "Just_Peachy_S6C_Integrated_Enrollment_Pack/Just_Peachy_S6C_Integrated_Enrollment_Pack"
APP = SIM / "staging/s6b/20260909T230840Z/epoch2/app"
TRACKER_SHA = "d5feddc193a84afd613b5fad2f1ed037609631cca543d3db160990c5775dbd1a"
INDEX_SHA = "2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e"
DEFAULT_PROFILES = ("B09", "B10", "B16", "B17", "B24", "B25")


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encode(value))


def binding(path, expected=None):
    p = Path(path)
    raw = p.read_bytes()
    result = dict(path=str(p.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if expected:
        if result["sha256"] != expected["sha256"] or ("bytes" in expected and len(raw) != expected["bytes"]):
            raise ValueError("Changed bound input: " + str(path))
    return raw, result


def read(path, expected=None):
    raw, identity = binding(path, expected)
    return json.loads(raw), identity


def csv_write(path, rows):
    import csv
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def import_api():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(APP))
    from edge_speech_pipeline.research_tracking_v2 import S6BTracker, S6BTrackingConfig, _union
    from edge_speech_pipeline.research_profiles import JsonSpatialProvider
    return S6BTracker, S6BTrackingConfig, JsonSpatialProvider, _union


def frozen_sources():
    index, index_binding = read(S6B / "LOCAL_ARTIFACT_INDEX.json", {"sha256": INDEX_SHA})
    by_path = {str(Path(e["path"]).resolve()).casefold(): e for e in index["artifacts"]}
    paths = [APP / "edge_speech_pipeline" / name for name in
             ("research_tracking_v2.py", "research_profiles.py", "research_scheduler.py", "config.py", "contracts.py", "__init__.py")]
    result = []
    for path in paths:
        expected = by_path[str(path.resolve()).casefold()]
        _, receipt = binding(path, expected)
        result.append(receipt)
    if result[0]["sha256"] != TRACKER_SHA:
        raise ValueError("Unexpected historical tracker")
    return index, index_binding, result


def controls(output):
    """Execute the actual supplied script in a new isolated directory, unchanged."""
    folder = output / "provided_controls"
    destination = folder / "code/edge_speech_pipeline/research_tracking_v2.py"
    destination.parent.mkdir(parents=True)
    supplied = PACK / "diagnostics/check_voice_gate_interaction.py"
    original = APP / "edge_speech_pipeline/research_tracking_v2.py"
    _, tracker_identity = binding(original, {"sha256": TRACKER_SHA})
    _, supplied_identity = binding(supplied)
    _, packaged_identity = binding(PACK / "diagnostics/code/edge_speech_pipeline/research_tracking_v2.py", tracker_identity)
    shutil.copyfile(original, destination)
    script_copy = folder / supplied.name
    shutil.copyfile(supplied, script_copy)
    with redirect_stdout(io.StringIO()):
        runpy.run_path(str(script_copy), run_name="__main__")
    actual, actual_identity = read(folder / "VOICE_GATE_CONTROL_RECEIPT.json")
    expected, expected_identity = read(PACK / "diagnostics/VOICE_GATE_CONTROL_RECEIPT.json")
    if actual["cases"] != expected["cases"] or actual["source_sha256"] != TRACKER_SHA:
        raise ValueError("Six original numerical controls changed")
    Tracker, Config, _, _ = import_api()

    def unit(axis):
        v = np.zeros(192, np.float32)
        v[axis] = 1
        return v

    retirement = Tracker(Config(mode="voice", max_tracks=1))
    first = retirement.update(unit(0), 0, .5, .5)
    retirement.tracks[0].retired = True  # Explicit model-free intervention, never an actual bank operation.
    before = dict(stored=len(retirement.tracks), active=len(retirement._active()),
                  lifetime_ids=retirement.next_track - 1, retired=sum(t.retired for t in retirement.tracks))
    second = retirement.update(unit(1), .5, 1, 1)
    rejection = [e for e in second["lineage"] if e["event"] == "track_capacity_rejection"]
    if not (first["tracker_id"] == 1 and before == dict(stored=1, active=0, lifetime_ids=1, retired=1)
            and second["tracker_id"] is None and len(rejection) == 1 and retirement.next_track == 2):
        raise ValueError("Retired stored-record capacity control changed")
    tree = ast.parse(original.read_text(encoding="utf-8-sig"))
    writes = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Attribute) and n.attr == "retired" and isinstance(n.ctx, ast.Store)]
    named_setattr = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == "setattr"
                    and len(n.args) > 1 and isinstance(n.args[1], ast.Constant) and n.args[1].value == "retired"]
    if writes or named_setattr:
        raise ValueError("Unexpected automatic retirement writer; update the source finding")
    result = dict(status="PASS", mode="MODEL_FREE_DIAGNOSTIC", supplied_script=supplied_identity,
                  original_tracker=tracker_identity, packaged_tracker=packaged_identity,
                  original_expected_receipt=expected_identity, reproduced_receipt=actual_identity,
                  exact_provided_cases=6, exact_case_equality=True,
                  retirement_control=dict(intervention="Explicitly set the sole existing record retired=True.",
                     before_second_update=before, second_tracker_id=second["tracker_id"],
                     capacity_rejections=len(rejection), lifetime_next_id_after=retirement.next_track,
                     empirical_bank_operation=False),
                  static_retirement_writes=writes, static_named_setattr_retirement_calls=named_setattr,
                  finding="No automatic retirement or list-compaction operation exists in this frozen module. Dormancy changes a flag/gate but does not remove stored records.",
                  model_calls=0, hardware_calls=0, old_files_modified=False)
    write(output / "SOURCE_CONTROL_RESULTS.json", result)
    return result


def instrumented_tracker(Tracker):
    class Inspector(Tracker):
        """Read-only preselection observer; calls the original selector once."""
        def _select(self, vector, voice, scores, angle, quality, start, end, now, events):
            tracks = self._active()
            eligible = [t.identifier for t in tracks if voice[t.identifier] >= self._threshold(t)]
            contributions = {t.identifier: scores[t.identifier] - voice[t.identifier] for t in tracks}
            ranked = sorted(eligible, key=lambda k: (-voice[k], k))
            if not ranked:
                voice_action = (None, True)
            elif len(ranked) > 1 and voice[ranked[0]] - voice[ranked[1]] < self.config.ambiguity_margin:
                voice_action = (None, False)
            else:
                voice_action = (ranked[0], False)
            actual = super()._select(vector, voice, scores, angle, quality, start, end, now, events)
            borderline = [t.identifier for t in tracks if self._threshold(t) - .05 <= voice[t.identifier] < self._threshold(t)
                          and voice[t.identifier] >= self.config.conflict_cosine_floor and contributions[t.identifier] > 1e-12]
            arithmetic_cross = [k for k in borderline if scores[k] >= self._threshold(next(t for t in tracks if t.identifier == k))]
            only = eligible[0] if len(eligible) == 1 else None
            only_track = next((t for t in tracks if t.identifier == only), None)
            conflict = (only_track is not None and angle is not None and quality > 0 and only_track.location is not None
                        and abs(angle - only_track.location) > self.config.direction_change_deg)
            self.audit = dict(
                selection_reached=1, active_candidates=len(tracks), voice_eligible_candidates=len(eligible),
                no_voice_eligible=int(not eligible), no_voice_eligible_with_existing=int(not eligible and bool(tracks)),
                one_voice_eligible=int(len(eligible) == 1), multiple_voice_eligible=int(len(eligible) >= 2),
                qualified_cue=int(angle is not None and quality > 0),
                nonzero_spatial_contribution=int(any(abs(v) > 1e-12 for v in contributions.values())),
                no_eligible_borderline_positive_cue=int(not eligible and bool(borderline)),
                no_eligible_combined_crosses_numerical_voice_gate=int(not eligible and bool(arithmetic_cross)),
                one_eligible_negative_cue_retained=int(only is not None and contributions[only] < -1e-12 and actual[0] == only),
                one_eligible_combined_below_numerical_voice_gate_retained=int(
                    only is not None and actual[0] == only and scores[only] < self._threshold(only_track)),
                one_eligible_direction_conflict_retained=int(conflict and actual[0] == only),
                multiple_eligible_with_nonzero_cue=int(len(eligible) >= 2 and any(abs(contributions[k]) > 1e-12 for k in eligible)),
                local_voice_only_action_changed=int(tuple(actual[:2]) != voice_action),
                dormant_candidates=sum(t.dormant for t in tracks),
                dormant_gate_exclusions=sum(t.dormant and self.config.cosine_threshold <= voice[t.identifier] < self._threshold(t) for t in tracks),
                severe_voice_conflict_candidates=sum(voice[t.identifier] < self.config.conflict_cosine_floor for t in tracks),
                severe_voice_nonzero_spatial_candidates=sum(
                    voice[t.identifier] < self.config.conflict_cosine_floor and abs(contributions[t.identifier]) > 1e-12 for t in tracks))
            self.candidate_excerpt = [
                dict(track_id=t.identifier, voice=voice[t.identifier], voice_gate=self._threshold(t),
                     spatial_contribution=contributions[t.identifier], combined_score=scores[t.identifier],
                     eligible=t.identifier in eligible, stored_angle=t.location, dormant=t.dormant)
                for t in tracks]
            return actual
    return Inspector


def traces(output, profiles, limit_cases=None):
    index, idx_binding, source_bindings = frozen_sources()
    admitted = {str(Path(x["path"]).resolve()).casefold(): x for x in index["artifacts"]}
    pred_path = S6B / "FULL_PREDICTION_INDEX.json"
    native_path = S6B / "epoch2/FULL_ALL_NEURAL_INDEX.json"
    predictions, pred_binding = read(pred_path, admitted[str(pred_path.resolve()).casefold()])
    native, native_binding = read(native_path, admitted[str(native_path.resolve()).casefold()])
    if predictions["status"] != "COMPLETE" or native["status"] != "COMPLETE":
        raise ValueError("Required completed S6B indexes")
    case_ids = sorted(predictions["case_ids"])[:limit_cases]
    targets = sorted((x for x in predictions["rows"] if x["profile_id"] in profiles and x["case_id"] in case_ids),
                     key=lambda x: (x["case_id"], x["stream"], x["recipe_id"], x["profile_id"]))
    if len(targets) != len(profiles) * len(case_ids) * 2:
        raise ValueError("Selected prediction matrix is incomplete")
    keyed_native = {(x["recipe_id"], x["case_id"], x["stream"]): x for x in native["rows"]}
    Tracker, Config, Provider, union = import_api()
    Inspector = instrumented_tracker(Tracker)
    rows, source_rows, examples, paired = [], [], [], []
    totals = defaultdict(Counter)
    cache_key, vectors, native_receipt, vector_binding = None, None, None, None
    provider_cache = {}
    pair_cache = {}
    started = last = time.perf_counter()
    full_decisions = exact_decisions = 0
    for position, item in enumerate(targets, 1):
        prediction, prediction_binding = read(item["result"]["path"], item["result"])
        key = (item["recipe_id"], item["case_id"], item["stream"])
        if key != cache_key:
            source_native = keyed_native[key]
            native_receipt, nb = read(source_native["receipt"]["path"], source_native["receipt"])
            vector_raw, vector_binding = binding(native_receipt["vectors"]["path"], native_receipt["vectors"])
            with np.load(io.BytesIO(vector_raw), allow_pickle=False) as archive:
                vectors = archive["vectors"].copy()
            cache_key = key
            source_rows.append(dict(kind="native_vector_source", recipe_id=key[0], case_id=key[1], stream=key[2],
                                    native_receipt=nb, vectors=vector_binding, evidence_bound_transitively=native_receipt["evidence"]))
        if prediction["identity"]["source"]["evidence"] != native_receipt["evidence"]:
            raise ValueError("Prediction refers to another neural evidence identity")
        if prediction["identity"]["source"]["recipe_job_key"] != native_receipt["job_key"]:
            raise ValueError("Prediction/native job identity mismatch")
        features, expected = prediction["features"], prediction["decisions"]
        if len(features) != len(vectors) or len(features) != len(expected):
            raise ValueError("Feature/vector/decision count mismatch")
        source_rows.append(dict(kind="prediction", profile_id=item["profile_id"], case_id=item["case_id"],
                                stream=item["stream"], binding=prediction_binding))
        config = Config(**prediction["identity"]["profile"]["tracker"])
        if config.mode not in ("voice", "adaptive", "dual_memory"):
            raise ValueError("This bounded incidence observer supports its registered six modes/profiles only")
        tracker = Inspector(config)
        provider = None
        if config.cues_enabled:
            cue = prediction["identity"]["cue_input"]
            if item["case_id"] not in provider_cache:
                _, cb = binding(cue["path"], cue)
                provider_cache[item["case_id"]] = Provider(Path(cue["path"]))
                source_rows.append(dict(kind="delivered_cues", case_id=item["case_id"], binding=cb))
            provider = provider_cache[item["case_id"]]
        count = Counter(cells=1, decisions=len(expected))
        maxima = Counter()
        rejected_spans = []
        local_details = []
        for i, (feature, old) in enumerate(zip(features, expected)):
            tracker.audit = {}
            tracker.candidate_excerpt = []
            start, end, now = (feature[k] for k in ("source_start_sec", "source_end_sec", "available_at_sec"))
            obs = provider.evidence(start, now) if provider else None
            current = tracker.update(vectors[i].tolist(), start, end, now, spatial=obs,
                                     speech=feature.get("speech", True), overlap=feature.get("overlap", False))
            full_decisions += 1
            if current != old:
                write(output / ("PARITY_FAILURE_%s_%s_%s.json" % (item["profile_id"], item["case_id"], item["stream"])),
                      dict(decision_index=i, expected=old, actual=current, prediction=prediction_binding))
                raise ValueError("Exact historical decision parity failed")
            exact_decisions += 1
            count.update(tracker.audit)
            count["stored_cue_observation_present"] += int(obs is not None)
            count["raw_words_untouched"] += 0  # Tracker-only audit never decodes/reformats words.
            for e in current["lineage"]:
                count["event_" + e["event"]] += 1
                if e["event"] == "track_capacity_rejection":
                    rejected_spans.append([start, end])
            for label, value in dict(stored_records=len(tracker.tracks), active_records=len(tracker._active()),
                  retired_records=sum(t.retired for t in tracker.tracks), dormant_records=sum(t.dormant for t in tracker.tracks),
                  committed_records=sum(t.committed for t in tracker.tracks),
                  provisional_records=sum(not t.committed for t in tracker.tracks),
                  lifetime_ids=tracker.next_track-1,
                  prototype_slots=sum(len(t.prototypes) for t in tracker.tracks),
                  prototype_numpy_payload_bytes=sum(p.nbytes for t in tracker.tracks for p in t.prototypes),
                  retained_revision_nodes=len(tracker.nodes)).items():
                maxima["max_" + label] = max(maxima["max_" + label], value)
            highlights = [k for k in (
                "no_eligible_borderline_positive_cue", "no_eligible_combined_crosses_numerical_voice_gate",
                "one_eligible_combined_below_numerical_voice_gate_retained", "one_eligible_direction_conflict_retained",
                "local_voice_only_action_changed", "dormant_gate_exclusions") if tracker.audit.get(k)]
            if highlights and sum(x["profile_id"] == item["profile_id"] for x in examples) < 12:
                examples.append(dict(profile_id=item["profile_id"], case_id=item["case_id"], stream=item["stream"],
                  decision_index=i, decision_id=current["decision_id"], source_start_sec=start, source_end_sec=end,
                  available_at_sec=now, actual_tracker_id=current["tracker_id"], actual_state=current["state"],
                  reason=current["reason"], findings=highlights, candidate_scores=tracker.candidate_excerpt,
                  cue=current.get("cue"), source=prediction_binding,
                  correctness="Not assessed; these are observed engineering decision opportunities, not counted speaker errors."))
            local_details.append(dict(span=[start, end], id=current["tracker_id"], state=current["state"],
                                      reason=current["reason"], cue=current.get("cue"),
                                      lineage=current["lineage"], prototype=current["prototype_version"]))
        if tracker.snapshot() != prediction["snapshot"]["tracker"]:
            raise ValueError("Final tracker snapshot parity failed")
        count["capacity_rejected_span_sum_sec"] = sum(b-a for a,b in rejected_spans)
        count["capacity_rejected_span_union_sec"] = sum(b-a for a,b in union(rejected_spans))
        row = dict(profile_id=item["profile_id"], case_id=item["case_id"], stream=item["stream"], recipe_id=item["recipe_id"],
                   duration_sec=prediction["duration_sec"], max_tracks=config.max_tracks, **dict(count), **dict(maxima),
                   exact_decision_parity=True, final_snapshot_parity=True)
        rows.append(row)
        totals[(item["profile_id"], item["stream"])].update(count)
        token = (item["case_id"], item["stream"])
        pair_cache.setdefault(token, {})[item["profile_id"]] = dict(details=local_details,
            final_words=[x["text"] for x in prediction["final_transcripts_first"]],
            latest_labels=[x["speaker"] for x in prediction["final_transcripts_latest"]])
        if len(pair_cache[token]) == len(profiles):
            for left, right in (("B09","B10"),("B16","B17"),("B24","B25")):
                if left not in profiles or right not in profiles:
                    continue
                a, b = pair_cache[token][left], pair_cache[token][right]
                amap = {tuple(x["span"]): x for x in a["details"]}
                bmap = {tuple(x["span"]): x for x in b["details"]}
                common = sorted(set(amap) & set(bmap))
                paired.append(dict(case_id=token[0], stream=token[1], left=left, right=right,
                  left_decisions=len(amap), right_decisions=len(bmap), exact_common_spans=len(common),
                  left_only_spans=len(set(amap)-set(bmap)), right_only_spans=len(set(bmap)-set(amap)),
                  common_id_or_state_changes=sum(any(amap[k][s] != bmap[k][s] for s in ("id","state")) for k in common),
                  common_reason_changes=sum(amap[k]["reason"] != bmap[k]["reason"] for k in common),
                  common_lineage_changes=sum(amap[k]["lineage"] != bmap[k]["lineage"] for k in common),
                  common_prototype_version_changes=sum(amap[k]["prototype"] != bmap[k]["prototype"] for k in common),
                  raw_final_words_equal=a["final_words"] == b["final_words"], latest_label_sequence_equal=a["latest_labels"] == b["latest_labels"],
                  scope="B24/B25 is a cue/cadence bundle with different observed opportunities" if left=="B24" else
                        "Matched neural input and support; parent/cue profile comparison. Internal actions can differ without cpWER changes."))
            del pair_cache[token]
        now = time.perf_counter()
        if now-last >= 20 or position == len(targets):
            print(json.dumps(dict(phase="MODEL_FREE_SOURCE_TRACE_AUDIT",completed_cells=position,requested_cells=len(targets),
                                  exact_decisions=exact_decisions,elapsed_sec=now-started)),flush=True)
            last = now
    aggregates = []
    for (profile_id,stream), total in sorted(totals.items()):
        own = [x for x in rows if x["profile_id"]==profile_id and x["stream"]==stream]
        aggregate = dict(profile_id=profile_id, stream=stream, **dict(total))
        keys = set(k for row in own for k in row if k.startswith("max_"))
        aggregate.update({k:max(x.get(k,0) for x in own) for k in keys})
        for label in ("event_track_capacity_rejection","no_eligible_borderline_positive_cue",
                      "no_eligible_combined_crosses_numerical_voice_gate",
                      "one_eligible_combined_below_numerical_voice_gate_retained",
                      "one_eligible_direction_conflict_retained","local_voice_only_action_changed","dormant_gate_exclusions"):
            aggregate[label+"_cells"] = sum(x.get(label,0)>0 for x in own)
        aggregates.append(aggregate)
    csv_write(output/"PER_CELL_DECISION_OPPORTUNITIES.csv",rows)
    csv_write(output/"PROFILE_TAP_PREVALENCE.csv",aggregates)
    csv_write(output/"MATCHED_PARENT_TRACE_COMPARISON.csv",paired)
    write(output/"REPRESENTATIVE_DECISION_EXCERPTS.json",dict(scope="Outcome-selected illustrative opportunity examples; not correctness labels.",examples=examples))
    write(output/"SOURCE_TRACE_BINDINGS.json",dict(index=idx_binding,predictions=pred_binding,native_index=native_binding,
                                                  frozen_sources=source_bindings,inputs=source_rows))
    result=dict(status="COMPLETE" if len(case_ids)==240 else "COMPLETE_BOUNDED_SUBSET",
        execution_type="VERIFIED_NATIVE_CACHE plus MODEL_FREE_DIAGNOSTIC original-selector replay",
        profiles=list(profiles),case_count=len(case_ids),tap_count=2,completed_cells=len(rows),
        decision_count=full_decisions,exact_decision_matches=exact_decisions,
        final_snapshot_matches=len(rows),source_index=idx_binding,
        native_model_calls=0,hardware_calls=0,old_inputs_or_H2_modified=False,
        elapsed_sec=time.perf_counter()-started,
        denominator_notes=[
            "Observation/candidate counts are repeated correlated opportunities, not independent conversations or empirical errors.",
            "Candidate count sums count track-by-observation comparisons. *_cells counts scene/tap cells with any occurrence.",
            "Combined-score numerical crossing is descriptive only: the uncalibrated combined score has no declared cosine decision threshold.",
            "Local cue effect compares voice-only ranking at the SAME current state; it is not an end-to-end cue-off counterfactual.",
            "Capacity blocked span sums double-count overlap; separate per-cell unions count unique source-time coverage.",
            "Only B09/B10/B16/B17/B24/B25 selected traces are audited. No unselected-family prevalence is implied.",
            "Retired versus stored capacity is tested by an explicit state intervention; original bank retirement remains absent.",
            "Prototype NumPy bytes exclude Python object overhead, retained vectors outside prototypes and all neural model/runtime memory.",
            "No ASR, transcript-attribution or scoring rerun occurs; exact original tracker decisions/snapshots are the invariant."],
        per_profile_tap=aggregates)
    write(output/"TRACE_AUDIT_RECEIPT.json",result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=S6C/"foundation/audit_v1")
    p.add_argument("--mode",choices=("controls","traces","all"),default="all")
    p.add_argument("--profiles",nargs="+",default=list(DEFAULT_PROFILES),choices=DEFAULT_PROFILES)
    p.add_argument("--limit-cases",type=int)
    args=p.parse_args()
    if args.limit_cases is not None and not 1<=args.limit_cases<=240:
        p.error("--limit-cases must be 1..240")
    if len(set(args.profiles))!=len(args.profiles):p.error("Duplicate profile")
    output=args.output.resolve()
    if not output.is_relative_to(S6C.resolve()):p.error("Output must remain within this new S6C report")
    output.mkdir(parents=True,exist_ok=False)
    try:
        index,ib,sources=frozen_sources()
        result=dict(status="PASS",mode=args.mode,source_index=ib,original_sources=sources,
                    code=binding(__file__)[1],readme=binding(Path(__file__).with_name("README_S6C_FOUNDATION_AUDIT.md"))[1])
        if args.mode in ("controls","all"):result["controls"]=controls(output)
        if args.mode in ("traces","all"):
            r=traces(output,args.profiles,args.limit_cases)
            result["trace_receipt"]=binding(output/"TRACE_AUDIT_RECEIPT.json")[1]
            result["coverage"]=dict(status=r["status"],cells=r["completed_cells"],decisions=r["decision_count"])
        write(output/"FOUNDATION_AUDIT_RECEIPT.json",result)
        print(json.dumps(dict(status="PASS",output=str(output),coverage=result.get("coverage")),indent=2))
    except Exception as exc:
        write(output/"FAILURE.json",dict(status="FAILED",error=repr(exc),native_model_calls=0,hardware_calls=0))
        raise


if __name__=="__main__":
    main()
