"""Plot reviewed full-bank attribution aggregates; README_S6C_PLOT_ATTRIBUTION_V1.md."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent / "reports/S6C/20260910T123540Z"
POPULATION = "ALL_COMPLETE_NONEMPTY"
VIEWS = (
    ("first_display", "cp_first_display_label_final_words", "First-display label"),
    ("latest", "cp_latest_revised", "Latest label"),
)

def require(condition, message):
    if not condition:
        raise ValueError(message)

def binding(path, raw=None):
    path = Path(path).resolve()
    raw = path.read_bytes() if raw is None else raw
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def read_exact(declared, limit=4 * 1024 * 1024):
    path = Path(declared["path"]).resolve()
    raw = path.read_bytes()
    require(len(raw) <= limit, "Compact source size limit")
    actual = binding(path, raw)
    require(actual == declared, "Changed exact source: " + str(path))
    return raw, actual

def integer(value):
    require(isinstance(value, str) and value.isdigit(), "Exact unsigned integer CSV field")
    return int(value)

def read_table(authority, declared):
    matches = [b for b in authority["tables"] if Path(b["path"]).name == "PROFILE_RESULTS.csv"]
    require(len(matches) == 1 and matches[0] == declared, "Unique authority-bound profile table")
    raw, actual = read_exact(declared)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    require(len(reader.fieldnames) == len(set(reader.fieldnames)), "Unique CSV headers")
    rows = list(reader)
    keys = [(x["profile_id"], x["stream"], x["population"]) for x in rows]
    require(len(keys) == len(set(keys)), "Unique profile/tap/population rows")
    return rows, raw, actual

def write_json(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")
    return binding(path)

def write_csv(path, rows):
    require(bool(rows), "Nonempty CSV export")
    with path.open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return binding(path)

def extract(spec):
    require(spec["schema"] == "s6c.attribution_figure_spec.v1", "Figure spec schema")
    require(spec["status"] == "WORKING_EXPLORATORY_FIXED_ORDER", "Working status required")
    require(spec["population"] == POPULATION, "Exact complete population")
    require(spec["scenes"] == 203 and spec["reference_words"] == 6016, "Fixed figure cohort")
    order = spec["candidate_order"]
    require(len(order) > 0 and len(order) == len(set(order)), "Unique declared order")
    require(spec["taps"] == ["O0", "O1"], "Both taps separately")
    selected, source_bindings, source_rows = {}, [], []
    for source in spec["sources"]:
        raw, rb = read_exact(source["receipt"])
        receipt = json.loads(raw)
        require(receipt["status"] == "COMPLETE_REQUESTED_INDEX", "Completed source only")
        n = source["expected_scored_cells"]
        require((receipt["requested"], receipt["scored"], receipt["unscored"]) == (n, n, 0),
                "Exact complete source grid")
        rows, raw_table, tb = read_table(receipt, source["table"])
        require(len(rows) == source["expected_aggregate_rows"], "Exact table row count")
        source_bindings.extend([rb, tb])
        pids = source["candidate_ids"]
        require(len(pids) == len(set(pids)) and set(pids) <= set(order), "Source candidate selection")
        for pid in pids:
            for tap in spec["taps"]:
                key = (pid, tap)
                require(key not in selected, "Candidate route declared twice")
                matched = [x for x in rows if (x["profile_id"], x["stream"], x["population"]) ==
                           (pid, tap, POPULATION)]
                require(len(matched) == 1, "Unique selected aggregate")
                row = matched[0]
                require(integer(row["scenes"]) == 203 and integer(row["word_reference_words"]) == 6016,
                        "Same stated scene and word denominators")
                evidence = dict(profile_id=pid, stream=tap, population=POPULATION,
                                source_receipt_path=rb["path"], source_receipt_sha256=rb["sha256"],
                                source_table_path=tb["path"], source_table_sha256=tb["sha256"])
                # Retain exact original CSV strings, including original reported rates.
                for field in ("scenes", "word_reference_words"):
                    evidence[field] = row[field]
                values = {}
                for view, prefix, label in VIEWS:
                    for suffix in ("errors", "reference_words", "scored_scenes", "rate"):
                        evidence[prefix + "_" + suffix] = row[prefix + "_" + suffix]
                    errors = integer(row[prefix + "_errors"])
                    words = integer(row[prefix + "_reference_words"])
                    require(words == 6016 and integer(row[prefix + "_scored_scenes"]) == 203,
                            "Metric-valid complete cohort")
                    reported = float(row[prefix + "_rate"])
                    require(math.isfinite(reported) and math.isclose(reported, errors / words,
                            rel_tol=1e-12, abs_tol=1e-12), "Reported rate agrees with existing counts")
                    values[view] = dict(errors=errors, reference_words=words, percent=100 * errors / words,
                                        original_rate_string=row[prefix + "_rate"])
                selected[key] = dict(profile_id=pid, stream=tap, scenes=203, reference_words=6016,
                                     first_display=values["first_display"], latest=values["latest"],
                                     latest_minus_first_errors=values["latest"]["errors"] - values["first_display"]["errors"],
                                     source_table=tb, source_receipt=rb)
                source_rows.append(evidence)
    require(set(selected) == {(p, t) for p in order for t in spec["taps"]}, "Exact requested plot grid")
    # Prior reviews are authority references, not rerun numerical tests.
    reviews = []
    for declared in spec["prior_review_authorities"]:
        raw, b = read_exact(declared)
        json.loads(raw)
        reviews.append(b)
    data = [selected[p, t] for t in spec["taps"] for p in order]
    return data, source_rows, source_bindings, reviews

def plot(out, data, order):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "svg.fonttype": "none", "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12.8, max(7.5, 4 + .7 * len(order))), sharex=True)
    colors = {"first_display": "#BA5B28", "latest": "#176987"}
    all_rates = [r[v]["percent"] for r in data for v, _, _ in VIEWS]
    low, high = 5 * math.floor((min(all_rates) - 1) / 5), 5 * math.ceil((max(all_rates) + 1) / 5)
    for ax, tap in zip(axes, ("O0", "O1")):
        for i, pid in enumerate(order):
            row = next(r for r in data if (r["profile_id"], r["stream"]) == (pid, tap))
            a, b = row["first_display"], row["latest"]
            ax.plot([a["percent"], b["percent"]], [i, i], color="#AEBBC4", lw=2.5, zorder=1)
            for view, value, marker, offset in (("first_display", a, "o", 13), ("latest", b, "D", -19)):
                ax.scatter([value["percent"]], [i], color=colors[view], marker=marker, s=59,
                           edgecolor="white", linewidth=.8, zorder=3)
                ax.annotate(f'{value["errors"]:,}', (value["percent"], i), xytext=(0, offset),
                            textcoords="offset points", ha="center", va="center",
                            color=colors[view], fontsize=10.5, fontweight="bold")
        ax.set_yticks(range(len(order)), order)
        ax.set_ylim(len(order) - .43, -.58)
        ax.set_xlim(low, high)
        ax.set_xticks(range(int(low), int(high) + 1, 5))
        ax.grid(axis="x", color="#DDE3E7", lw=.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0, pad=10)
        ax.set_title(tap + " · fixed output", fontsize=14, loc="left", pad=18, fontweight="bold")
        ax.set_xlabel("cp error rate (%) · lower is better", labelpad=13)
        ax.spines["left"].set_visible(False)
    axes[0].set_ylabel("Registered configuration · fixed order", labelpad=17)
    fig.suptitle("First-display and latest attribution errors", fontsize=20,
                 x=.08, y=.965, ha="left", fontweight="bold")
    fig.text(.08, .904, "Each pipeline is scored with its own final ASR words under two speaker-label views.",
             fontsize=11.2, color="#40525E")
    handles = [Line2D([0], [0], marker="o" if key == "first_display" else "D", ls="",
               color=colors[key], markersize=7, label=label) for key, _, label in VIEWS]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.074, .861), ncol=2,
               frameon=False, handletextpad=.5, columnspacing=2)
    fig.subplots_adjust(left=.11, right=.965, top=.755, bottom=.28, wspace=.30)
    fig.text(.08, .165, "Each point: 203 complete nonempty scenes / 6,016 reference words. Labels are exact cp error counts.",
             fontsize=10.1)
    fig.text(.08, .118, "First-display uses the first shown label with final words; it is not partial-transcript WER or wall-clock latency.",
             fontsize=9.7, color="#40525E")
    fig.text(.08, .074, "Shared scenes and O0/O1 views are dependent. B36 is a cross-generation full-pipeline comparator.",
             fontsize=9.7, color="#40525E")
    fig.text(.08, .036, "WORKING exploratory comparison · no isolated-algorithm or final-selection claim",
             fontsize=9.2, color="#657580")
    for ext in ("png", "svg"):
        fig.savefig(out / ("attribution_tradeoffs." + ext), dpi=180, facecolor="white")
    plt.close(fig)
    return matplotlib.__version__

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--spec-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    require(out.parent == REPORT / "figures" and not out.exists(), "Fresh direct figure namespace")
    raw = args.spec.resolve().read_bytes()
    sb = binding(args.spec, raw)
    require(sb["sha256"] == args.spec_sha256, "Exact explicitly admitted plot specification")
    spec = json.loads(raw)
    data, source_rows, sources, reviews = extract(spec)
    # Admission and exact-table conversion complete before output creation.
    out.mkdir()
    csv_binding = write_csv(out / "SOURCE_ROWS.csv", source_rows)
    db = write_json(out / "PLOT_DATA.json",
                    dict(schema="s6c.attribution_plot_data.v1", status="WORKING",
                         spec=sb, fixed_order=spec["candidate_order"], taps=spec["taps"], rows=data,
                         source_row_csv=csv_binding, scope=spec["scope"]))
    version = plot(out, data, spec["candidate_order"])
    caption = (
        "Working exploratory comparison in the fixed declared order " + ", ".join(spec["candidate_order"]) + ". "
        "Each O0/O1 point uses the already scored ALL_COMPLETE_NONEMPTY population: 203 scenes and "
        "6,016 reference words. The full experiment retained all 240 scenes; 26 incomplete-reference "
        "and 11 strict-empty controls have separate metrics and are outside this plotted cp population. "
        "First-display-label cp applies the first displayed speaker label to that pipeline's final ASR "
        "words. Latest cp uses its final revised labels. These are concatenated minimum-permutation "
        "attribution error measures, not partial-transcript WER, literal known-person identification "
        "accuracy or measured wall-clock display latency. Exact error counts are annotated; percentages "
        "are errors divided by 6,016, without rescoring or resampling. Gray segments link the two views "
        "within each condition, not uncertainty intervals. Shared scenes and O0/O1 observations are "
        "dependent. B36 is the original S6B full-pipeline comparator across generations and does not "
        "isolate an association algorithm intervention. The plot omits other necessary short-turn, "
        "return, abstention, naming and cost criteria; it is neither final selection nor a dominance claim. "
        "Earlier numerical reviews remain the underlying authority. Later completed configurations "
        "require a new explicit specification and fresh figure namespace; V1 is never overwritten."
    )
    with (out / "CAPTION.md").open("x", encoding="utf-8") as f:
        f.write(caption + "\n")
    outputs = [csv_binding, db] + [binding(out / name) for name in
              ("attribution_tradeoffs.png", "attribution_tradeoffs.svg", "CAPTION.md")]
    result = dict(status="WORKING_FIGURE_COMPLETE_PENDING_VISUAL_REVIEW",
                  utc=datetime.now(timezone.utc).isoformat(), spec=sb, sources=sources,
                  prior_review_authorities=reviews, source=binding(__file__),
                  readme=binding(HERE / "README_S6C_PLOT_ATTRIBUTION_V1.md"),
                  outputs=outputs, plotted_routes=len(data), plotted_points=2 * len(data),
                  population=POPULATION, scenes_per_point=203, reference_words_per_point=6016,
                  source_conversion_only=True, matplotlib_version=version,
                  new_scoring=False, numeric_review_reruns=0, new_native_or_model_calls=0)
    print(json.dumps(write_json(out / "FIGURE_RECEIPT.json", result)))

if __name__ == "__main__":
    main()
