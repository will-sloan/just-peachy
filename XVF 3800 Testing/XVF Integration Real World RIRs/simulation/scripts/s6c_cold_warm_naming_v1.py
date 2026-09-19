"""Summarize existing query tables only; README_S6C_COLD_WARM_NAMING_V1.md."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent / "reports/S6C/20260910T123540Z"
SCORER_SHA = "79c58dd9f67ebbaa9d1f5ca2b9ef53ec788b8762e348eda5d6add44d5dac3017"
AUTHORITIES = (
    ("full_n01_naming_names_v3", "7fd6fbecd0cfbdd77e64333e65bb9ea19d5a9e5780f2b763a0d7470307b58bce",
     ("C088", "C091", "C105", "C106", "C111", "C114")),
    ("full_n01_common_duration_names_v3", "1da2a2dd1c9f50a9aefb89a0e024de03975c629914ecb8aac673cf817366118b",
     ("C141", "C142", "C143", "C144", "C145", "C146")),
)
COLD = "COLD_NEW_OR_RETIRED_NAME_STATE"
WARM = "WARM_RETAINED_NAME_STATE"
OUTCOMES = ("correct_name", "wrong_known_name", "unknown_name", "UNIDENTIFIABLE_REFERENCE")
BASE = ("authority", "profile_id", "stream", "identity_tap")
REQUIRED_QUERY = (
    "profile_id", "stream", "identity_tap", "case_id", "gallery_condition", "enrollment_tier",
    "available_at_sec", "source_start_sec", "source_end_sec", "tracker_id",
    "cold_track_query", "cold_warm_status", "first_query_for_lifetime_tracker_id",
    "first_query_for_reference_person", "reference_status", "reference_identity",
    "assigned_name_status", "roster_status", "unique_clean_sec", "disjoint_count",
    "evidence_kind", "query_executed",
)

def require(ok, message):
    if not ok:
        raise ValueError(message)

def bind(path, raw=None):
    path = Path(path).resolve()
    raw = path.read_bytes() if raw is None else raw
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def exact(path, declared=None):
    path = Path(path).resolve()
    raw = path.read_bytes()
    require(len(raw) <= 32 * 1024 * 1024, "Bounded compact-table size")
    actual = bind(path, raw)
    if declared is not None:
        require(actual == declared, "Changed exact buffer: " + str(path))
    return raw, actual

def dump(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")
    return bind(path)

def table(receipt, name):
    found = [x for x in receipt["tables"] if Path(x["path"]).name == name]
    require(len(found) == 1, "One exact table: " + name)
    raw, b = exact(found[0]["path"], found[0])
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "Unique CSV header")
    return list(reader), list(reader.fieldnames), b

def boolean(value):
    require(value in ("True", "False", ""), "Boolean CSV retains empty as unavailable")
    return {"True": True, "False": False, "": None}[value]

def numeric(value, integer=False):
    if value == "":
        return None
    v = float(value)
    require(math.isfinite(v) and v >= 0, "Finite nonnegative numeric metadata")
    if integer:
        require(v.is_integer(), "Integer count metadata")
    return int(v) if integer else v

def validate(row):
    require(all(k in row for k in REQUIRED_QUERY), "Complete exported query schema")
    require(row["query_executed"] == "True", "Executed-query table only")
    require(row["tracker_id"].isdigit() and int(row["tracker_id"]) > 0, "Positive lifetime tracker ID")
    cold = boolean(row["cold_track_query"])
    first_track = boolean(row["first_query_for_lifetime_tracker_id"])
    first_person = boolean(row["first_query_for_reference_person"])
    status = row["cold_warm_status"]
    if status == COLD:
        require(cold is True, "Cold status/flag agree")
    elif status == WARM:
        require(cold is False and first_track is not True, "Warm status/flags agree")
    else:
        # Do not turn missing or unsupported history classification into warm.
        status = "UNAVAILABLE_MISSING_COLD_WARM_STATUS" if not status else status
        require(status.startswith("UNAVAILABLE"), "Unrecognized history status is retained only as unavailable")
    if first_track is True and row["cold_warm_status"] in (COLD, WARM):
        require(cold is True, "First lifetime track query is cold when classified")
    outcome = row["assigned_name_status"]
    require(outcome in OUTCOMES, "Known exported assignment partition")
    if row["reference_identity"]:
        require(row["reference_status"] == "ONE_REFERENCE_PERSON" and outcome != "UNIDENTIFIABLE_REFERENCE",
                "Identifiable reference and assignment agree")
        require(first_person is not None and bool(row["roster_status"]), "Identifiable reference has first-query/roster fields")
        if outcome == "correct_name":
            require(row["roster_status"] == "ENROLLED", "Correct known name requires an available enrolled identity")
    else:
        require(outcome == "UNIDENTIFIABLE_REFERENCE" and first_person is None and not row["roster_status"],
                "Unidentifiable query cannot receive correct/wrong/unknown reference outcome")
    times = [numeric(row[k]) for k in ("available_at_sec", "source_start_sec", "source_end_sec")]
    require(all(x is not None for x in times) and times[1] < times[2], "Actual exported query span/time")
    require(times[0] >= times[2], "Query evidence available after its support")
    clean = numeric(row["unique_clean_sec"])
    disjoint = numeric(row["disjoint_count"], integer=True)
    return dict(cold_warm=status, first_track=first_track, first_person=first_person,
                clean=clean, disjoint=disjoint, outcome=outcome, available=times[0])

def first_person_class(value):
    return ("FIRST_IDENTIFIABLE_PERSON_QUERY_IN_SCENE" if value is True else
            "SUBSEQUENT_IDENTIFIABLE_PERSON_QUERY_IN_SCENE" if value is False else
            "UNAVAILABLE_UNIDENTIFIABLE_REFERENCE")

class Counts:
    def __init__(self):
        self.outcomes = Counter()
        self.histories = Counter()
        self.references = Counter()
        self.evidence = Counter()
        self.first_tracks = Counter()
        self.first_people = Counter()
        self.clean = []
        self.disjoint = []
        self.cells = set()
        self.people_in_scenes = set()
        self.row_hash = hashlib.sha256()

    def add(self, row, parsed, cell, ordinal):
        self.outcomes[parsed["outcome"]] += 1
        self.histories[parsed["cold_warm"]] += 1
        self.references[row["reference_status"]] += 1
        self.evidence[row["evidence_kind"]] += 1
        self.first_tracks[str(parsed["first_track"])] += 1
        self.first_people[str(parsed["first_person"])] += 1
        self.clean.append(parsed["clean"])
        self.disjoint.append(parsed["disjoint"])
        self.cells.add(cell)
        if row["reference_identity"]:
            self.people_in_scenes.add((cell, row["reference_identity"]))
        self.row_hash.update((json.dumps([ordinal, row], sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")) + "\n").encode("utf-8"))

    def export(self):
        n = sum(self.outcomes.values())
        identified = n - self.outcomes["UNIDENTIFIABLE_REFERENCE"]
        result = dict(query_rows=n, identifiable_reference_queries=identified,
                      unidentifiable_reference_queries=self.outcomes["UNIDENTIFIABLE_REFERENCE"],
                      correct_name_queries=self.outcomes["correct_name"],
                      wrong_known_name_queries=self.outcomes["wrong_known_name"],
                      unknown_name_queries=self.outcomes["unknown_name"],
                      contributing_case_routes=len(self.cells),
                      identifiable_person_scene_units=len(self.people_in_scenes),
                      first_lifetime_track_queries=self.first_tracks["True"],
                      subsequent_lifetime_track_queries=self.first_tracks["False"],
                      unavailable_lifetime_track_first_flag=self.first_tracks["None"],
                      first_reference_person_queries=self.first_people["True"],
                      subsequent_reference_person_queries=self.first_people["False"],
                      unavailable_reference_person_first_flag=self.first_people["None"],
                      cold_warm_counts=dict(sorted(self.histories.items())),
                      reference_status_counts=dict(sorted(self.references.items())),
                      evidence_kind_counts=dict(sorted(self.evidence.items())),
                      ordered_contributing_rows_sha256=self.row_hash.hexdigest())
        require(sum(result[k] for k in ("correct_name_queries", "wrong_known_name_queries", "unknown_name_queries")) == identified,
                "Correct/wrong/unknown identifiable partition")
        require(identified + result["unidentifiable_reference_queries"] == n, "All query rows retained")
        for outcome in ("correct_name", "wrong_known_name", "unknown_name"):
            result[outcome + "_percent_of_identifiable_queries"] = (
                100 * self.outcomes[outcome] / identified if identified else None)
        for label, values in (("unique_clean_sec", self.clean), ("disjoint_count", self.disjoint)):
            present = [x for x in values if x is not None]
            result[label + "_observed_queries"] = len(present)
            result[label + "_unavailable_queries"] = len(values) - len(present)
            for stat, value in (("min", min(present) if present else None),
                                ("median", statistics.median(present) if present else None),
                                ("max", max(present) if present else None)):
                result[label + "_" + stat] = value
        return result

def csv_out(path, rows):
    require(bool(rows), "Nonempty reporting CSV")
    with path.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list))
                             else v for k, v in row.items()})
    return bind(path)

def summarize(label, queries, coverage):
    covered = {}
    for row in coverage:
        key = (row["profile_id"], row["stream"], row["identity_tap"], row["case_id"])
        require(row["status"] == "SCORED" and key not in covered, "Unique scored case coverage")
        covered[key] = Counts()
    cold_groups, first_groups, reference_groups, profile_groups = (
        defaultdict(Counts) for _ in range(4))
    for cell in covered:
        profile_groups[(label, cell[0], cell[1], cell[2])]
    statuses = Counter()
    seen_tracks, seen_people, last_time = defaultdict(set), defaultdict(set), {}
    for ordinal, row in enumerate(queries, 1):
        cell = (row["profile_id"], row["stream"], row["identity_tap"], row["case_id"])
        require(cell in covered, "Every query belongs to declared coverage")
        p = validate(row)
        require(p["available"] >= last_time.get(cell, 0), "Per-cell exported query order")
        last_time[cell] = p["available"]
        # Check exported first flags using queries only; do not reconstruct skipped decisions/retirement.
        if p["first_track"] is not None:
            require(p["first_track"] == (row["tracker_id"] not in seen_tracks[cell]), "Exported first lifetime query flag")
        if row["reference_identity"]:
            require(p["first_person"] == (row["reference_identity"] not in seen_people[cell]),
                    "Exported first identifiable person query flag")
            seen_people[cell].add(row["reference_identity"])
        seen_tracks[cell].add(row["tracker_id"])
        base = (label, cell[0], cell[1], cell[2])
        roster = row["roster_status"] or "UNAVAILABLE_REFERENCE_ROSTER"
        for target in (
            covered[cell], cold_groups[base + (roster, p["cold_warm"])],
            first_groups[base + (roster, first_person_class(p["first_person"]))],
            reference_groups[base + (roster, row["reference_status"], p["cold_warm"])],
            profile_groups[base],
        ):
            target.add(row, p, cell, ordinal)
        statuses[base + (row["gallery_condition"], row["enrollment_tier"], row["roster_status"],
                        row["cold_warm_status"], row["cold_track_query"], row["reference_status"],
                        row["assigned_name_status"], row["evidence_kind"],
                        row["first_query_for_lifetime_tracker_id"], row["first_query_for_reference_person"])] += 1
    case_rows = [dict(authority=label, profile_id=k[0], stream=k[1], identity_tap=k[2], case_id=k[3],
                      query_coverage="NO_EXECUTED_QUERY" if not v.outcomes else "EXPORTED_EXECUTED_QUERIES",
                      **v.export()) for k, v in sorted(covered.items())]
    def grouped(mapping, extras):
        return [dict(zip(BASE + extras, key), **value.export()) for key, value in sorted(mapping.items())]
    outputs = dict(
        CASE_QUERY_COUNTS=case_rows,
        COLD_WARM_QUERY_SUMMARY=grouped(cold_groups, ("roster_status", "cold_warm_status")),
        FIRST_REFERENCE_PERSON_QUERY_SUMMARY=grouped(first_groups, ("roster_status", "person_query_status")),
        REFERENCE_STATUS_QUERY_SUMMARY=grouped(reference_groups, ("roster_status", "reference_status", "cold_warm_status")),
        PROFILE_QUERY_COUNTS=grouped(profile_groups, ()),
        ALL_EXPORTED_STATUS_COUNTS=[
            dict(zip(BASE + ("gallery_condition", "enrollment_tier", "roster_status_raw", "cold_warm_status_raw",
                            "cold_track_query_raw", "reference_status", "assigned_name_status", "evidence_kind_raw",
                            "first_lifetime_track_flag_raw", "first_reference_person_flag_raw"), key), query_rows=n)
            for key, n in sorted(statuses.items())],
    )
    for name, rows in outputs.items():
        require(sum(r["query_rows"] for r in rows) == len(queries), "All-row closure for " + name)
    return outputs

def fixture_row(**updates):
    row = dict(zip(REQUIRED_QUERY, ("C1", "O0", "O0", "case1", "A", "15", "2", "0", "1",
               "1", "True", COLD, "True", "True", "ONE_REFERENCE_PERSON", "person",
               "unknown_name", "ENROLLED", "0", "1", "mature", "True")))
    row.update(updates)
    return row

def fixtures():
    checks = []
    row = fixture_row(cold_warm_status="", cold_track_query="")
    require(validate(row)["cold_warm"] == "UNAVAILABLE_MISSING_COLD_WARM_STATUS", "Missing history unavailable")
    checks.append("missing history is not warm")
    row = fixture_row(cold_warm_status="UNAVAILABLE_TRUNCATED_RETIREMENT_HISTORY", cold_track_query="",
                      first_query_for_lifetime_tracker_id="False")
    require(validate(row)["cold_warm"].startswith("UNAVAILABLE"), "Truncated retained")
    checks.append("truncated history retained")
    for mutation in (dict(cold_warm_status=WARM), dict(reference_identity="", first_query_for_reference_person=""),
                     dict(unique_clean_sec="nan"), dict(query_executed="False")):
        try:
            validate(fixture_row(**mutation))
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid metadata accepted")
    checks.append("contradictory status, unidentified outcome, nonfinite support and nonquery rejected")
    coverage = [dict(profile_id="C1", stream="O0", identity_tap="O0", case_id=c, status="SCORED") for c in ("case1", "case2")]
    rows = [fixture_row(), fixture_row(tracker_id="2", available_at_sec="3",
                                      first_query_for_reference_person="False", assigned_name_status="correct_name"),
            fixture_row(tracker_id="2", available_at_sec="4", cold_track_query="False", cold_warm_status=WARM,
                        first_query_for_lifetime_tracker_id="False", first_query_for_reference_person="False",
                        assigned_name_status="wrong_known_name", unique_clean_sec="")]
    a = summarize("A", rows, coverage)
    require(a["CASE_QUERY_COUNTS"][1]["query_rows"] == 0, "Zero-query case retained")
    checks.append("all covered zero-query cases retained")
    require(sum(x["query_rows"] for x in a["FIRST_REFERENCE_PERSON_QUERY_SUMMARY"] if x["person_query_status"].startswith("FIRST_")) == 1,
            "New track not new person")
    checks.append("new lifetime track does not become first person query")
    require(sum(x["query_rows"] for x in a["COLD_WARM_QUERY_SUMMARY"] if x["cold_warm_status"] == COLD) == 2,
            "Cold queries retained")
    checks.append("overlapping repeated query opportunities counted rather than unioned")
    require(a["PROFILE_QUERY_COUNTS"][0]["unique_clean_sec_min"] == 0 and
            a["PROFILE_QUERY_COUNTS"][0]["unique_clean_sec_unavailable_queries"] == 1, "Missing separate from zero")
    checks.append("zero clean support differs from unavailable metadata")
    unident = fixture_row(reference_identity="", reference_status="INCOMPLETE_REFERENCE",
                         first_query_for_reference_person="", roster_status="", assigned_name_status="UNIDENTIFIABLE_REFERENCE")
    b = summarize("B", [unident], coverage)
    require(b["PROFILE_QUERY_COUNTS"][0]["correct_name_percent_of_identifiable_queries"] is None, "No fake denominator")
    checks.append("unidentifiable queries retained outside correct-wrong-unknown denominator")
    require(b["PROFILE_QUERY_COUNTS"][0]["authority"] != a["PROFILE_QUERY_COUNTS"][0]["authority"], "Separate authority")
    checks.append("authorities remain separate")
    return dict(status="PASS", checks=checks)

def run(subdir):
    out = (REPORT / subdir).resolve()
    require(out.parent == REPORT and not out.exists(), "Fresh direct report namespace")
    all_outputs = defaultdict(list)
    sources, source_scopes = [], []
    for label, sha, profiles in AUTHORITIES:
        raw, rb = exact(REPORT / label / "NAME_ANALYSIS_RECEIPT.json")
        require(rb["sha256"] == sha, "Explicit original authority")
        receipt = json.loads(raw)
        require((receipt["status"], receipt["requested"], receipt["scored"], receipt["failed_or_missing"]) ==
                ("COMPLETE_REQUESTED_NAME_INDEX", 2880, 2880, 0), "Exact full complete naming authority")
        code = [b for b in receipt["codes"] if Path(b["path"]).name == "s6c_name_analysis_v3.py"]
        require(len(code) == 1 and code[0]["sha256"] == SCORER_SHA, "Original query semantics authority")
        queries, headers, qb = table(receipt, "QUERIES.csv")
        coverage, _, cb = table(receipt, "COVERAGE.csv")
        require(set(REQUIRED_QUERY) <= set(headers), "Required exported query fields")
        expected = {(p, t, t, f"S45_{family:02d}_{case:02d}") for p in profiles for t in ("O0", "O1")
                    for family in range(1, 13) for case in range(1, 21)}
        require({(x["profile_id"], x["stream"], x["identity_tap"], x["case_id"]) for x in coverage} == expected and
                len(coverage) == 2880, "All 240 cases and both routes for all six declared profiles")
        result = summarize(label, queries, coverage)
        for name, rows in result.items():
            all_outputs[name].extend(rows)
        sources.extend((rb, qb, cb))
        source_scopes.append(dict(authority=label, receipt=rb, queries=qb, coverage=cb,
            original_query_rows=len(queries), coverage_rows=len(coverage),
            profiles=list(profiles), original_query_headers=headers, source_prediction_index_declared_unopened=receipt["index"],
            execution_scope="CACHED_POLICY_QUERY_OBSERVATIONS_OVER_ACTUAL_NATIVE_EVIDENCE",
            runtime_query_scope="Not actual accelerated native-gallery integration or source-paced wall queries",
            history_scope="Honor exported cold/warm/unavailable flags; raw retirement histories not reopened or reconstructed"))
    out.mkdir()
    artifacts = [csv_out(out / (name + ".csv"), rows) for name, rows in all_outputs.items()]
    result = dict(status="COMPLETE_BOUND_QUERY_TABLE_SUMMARY", schema="s6c.cold_warm_naming.v1",
                  utc=datetime.now(timezone.utc).isoformat(), sources=sources, authority_scopes=source_scopes,
                  original_query_rows=sum(x["original_query_rows"] for x in source_scopes), case_route_rows=5760,
                  all_case_rows_retained=True, all_query_rows_accounted=True, query_tables_unchanged=True,
                  per_authority_profile_summary=all_outputs["PROFILE_QUERY_COUNTS"],
                  artifacts=artifacts, helper=bind(__file__), readme=bind(HERE / "README_S6C_COLD_WARM_NAMING_V1.md"),
                  fixture_checks=fixtures(), models=0, new_scoring=False, native_logs_or_predictions_read=False,
                  limits=[
                    "Correct/wrong/unknown percentages use identifiable executed queries, with unidentifiable queries retained separately.",
                    "Query opportunities overlap in audio and may repeat the same state; they are not unique speech, elapsed time or independent trials.",
                    "First reference-person query is local to a fresh scene/profile/tap and requires identifiable query support; it is not first speech, first person lifetime or a cold-track definition.",
                    "ONE_REFERENCE_PERSON means one metadata identity intersects the queried support, not necessarily sole-active speech throughout the entire span.",
                    "No assigned-confirmation state is exported in QUERIES.csv; correct assigned names are not all confirmed or stable names.",
                    "Unique-clean and disjoint fields are per-query cumulative state observations; min/median/max only, never summed as fresh speech.",
                    "Both authorities are cached policy projections, distinct from actual native and paced query execution.",
                    "Blank/truncated history classifications remain unavailable; raw missing ledger information not exposed in the original table cannot be independently detected here.",
                    "Source-empty and other zero-query cases remain covered; zero executed queries is not zero error across all potential naming decisions.",
                    "All original query rows and statuses remain in their exact immutable source tables, bound here rather than duplicated as bulky exports.",
                  ])
    print(json.dumps(dump(out / "RESULT.json", result)))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--check-receipt", type=Path)
    parser.add_argument("--output-subdir")
    args = parser.parse_args()
    if args.test:
        result = dict(**fixtures(), helper=bind(__file__), readme=bind(HERE / "README_S6C_COLD_WARM_NAMING_V1.md"))
        if args.check_receipt:
            print(json.dumps(dump(args.check_receipt.resolve(), result)))
        else:
            print(json.dumps(result))
    else:
        require(args.output_subdir and not args.check_receipt, "Explicit fresh output-subdir required")
        run(args.output_subdir)

if __name__ == "__main__":
    main()
