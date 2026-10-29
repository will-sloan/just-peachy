"""Append completed Whistle evidence and interpretations to one local Word report.

No training imports, GPU work, dataset scans, or changes to campaign decisions.
See README.md for installation, commands, inputs, outputs and recovery.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid
from zoneinfo import ZoneInfo

SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[3]
FILENAME = "Whistle_Fine_Tuning_Findings.docx"
DATASETS = ("common_voice", "ami", "chime6", "voices")
LABELS = {"common_voice": "Common Voice age filtered", "ami": "AMI", "chime6": "CHiME 6", "voices": "VOiCES"}
MAX_JSON_BYTES = 2_000_000


def read_json(path, default=None):
    if not path.exists():
        return {} if default is None else default
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f"Refusing large reporting input: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def now_text():
    try:
        return datetime.now(ZoneInfo("America/Toronto")).strftime("%d %B %Y at %H:%M %Z")
    except Exception:
        return datetime.now(timezone.utc).strftime("%d %B %Y at %H:%M UTC")


def collect(repo, output):
    """Read an allowlist of small summaries, never predictions or manifests."""
    initial = repo / "training/whistle_age_robust_v1"
    followup = repo / "training/whistle_followups_v1"
    lab = repo / "Software Validation from Datasets/Training Tool/whistle_lab"
    events = []

    def event(kind, title, data, paths, key=""):
        sources = []
        for path in paths:
            sources.append({"path": path.relative_to(repo).as_posix(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        payload = {"kind": kind, "title": title, "data": data, "sources": sources, "key": key}
        payload["id"] = "wh_" + digest(payload)[:32]
        events.append(payload)

    config_path, plan_path = lab / "config.json", lab / "followup/plan.json"
    if config_path.exists() and plan_path.exists():
        event("protocol", "Campaign design and automatic decisions",
              {"config": read_json(config_path), "plan": read_json(plan_path)}, [config_path, plan_path])
    amendment_path = followup / "extension_snapshot.json"
    amendment = read_json(amendment_path)
    if amendment:
        p = amendment["plan"]
        event("note", "Authorized longer comparisons and conditional production refit", {
            "paragraphs": [
                "On 24 October 2026 the user authorized a finite extension. The existing production fit continues unchanged and is preserved. The combined ceiling is 12 training runs, including the original seven pilots, current production, three longer pilots and at most one additional production fit.",
                p["rationale"],
                "The added pilots are a fresh mixed reference, without VOiCES, and without CHiME-6. Each stops at 30,000 updates, two active hours or three passes, whichever comes first. Six active GPU hours is the maximum added pilot budget; compilation, export and scoring are extra. Added results are not yet available when this amendment is recorded.",
                "All three use qualified training only and the same four-dataset development panel. Original relative weights are renormalized over retained datasets. Promotion requires the original recognition, uncertainty, dataset, quiet and noise guards plus at least 20,000 updates and 500 visited views per retained dataset in both runs. Exposure floors do not prove representativeness; insufficient evidence retains the existing recipe.",
                p["production_policy"], p["comparison_limits"],
                "The dashboard separates measured current-fit time from the amended campaign. Its upper scenario includes a conditional extra three-pass fit; the lower retains the first fit. Neither a report delay nor an LLM response blocks the supervisor."
            ]}, [amendment_path], p["id"])
    model_path = initial / "model_manifest.json"
    if model_path.exists():
        model = read_json(model_path)
        if model.get("completed_training"):
            event("training", "Initial training completion and model provenance", model, [model_path])
    for path, kind, title in (
        (initial / "evaluation_summary.json", "matched", "Initial matched recognition comparison"),
        (followup / "audio_quality.json", "quality", "Expanded microphone audit"),
        (followup / "baseline/scores.json", "scores", "Expanded development baseline"),
    ):
        data = read_json(path)
        if data.get("complete") is True:
            event(kind, title, data, [path], "baseline" if kind == "scores" else "")
    queue = read_json(followup / "queue.json")
    for job in queue.get("jobs", []):
        name = job["name"]
        if not re.fullmatch(r"[a-z0-9_]+", name):
            raise ValueError("Unsafe run name in reporting input")
        folder = followup / "runs" / name
        if job.get("unavailable"):
            event("unavailable", "Full tuning availability", {"run": name, "reason": job["unavailable"]}, [], name)
            continue
        path = folder / ("test_scores.json" if job["spec"].get("production") else "scores.json")
        data = read_json(path)
        if data.get("complete") is True:
            paths = [path]
            manifest = folder / "model_manifest.json"
            if manifest.exists():
                data = dict(data, model_manifest=read_json(manifest))
                paths.append(manifest)
            event("scores", "Results for " + name.replace("_", " "), data, paths, name)
    for name, kind, title in (
        ("dataset_contributions.json", "contributions", "What the individual dataset pilots show"),
        ("weight_decision.json", "decision", "Dataset weighting decision"),
        ("method_decision.json", "decision", "LoRA and full tuning decision"),
        ("production_decision.json", "production", "Selected production recipe"),
        ("extension_decision.json", "decision", "Longer omission comparison decision"),
        ("extension_production_decision.json", "extension_production", "Retain or refit the production model"),
        ("matched_comparison.json", "matched", "Final matched recognition comparison"),
        ("summary.json", "final", "Campaign completion"),
    ):
        path = followup / name
        data = read_json(path)
        if data and (kind not in ("matched", "final") or data.get("complete") is True):
            event(kind, title, data, [path], name)
    notes = read_json(output / "analyst_notes.json", {"entries": []})
    for note in notes.get("entries", []):
        if not note.get("id") or not note.get("title") or not note.get("paragraphs"):
            raise ValueError("Analyst notes require id, title and paragraphs")
        event("note", note["title"], note, [], note["id"])
    return events


def percent(value):
    return "Pending" if value is None else f"{100 * value:.1f}%"


def paragraph(doc, text, style=None):
    return doc.add_paragraph(str(text), style)


def table(doc, headers, rows, widths=None):
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor
    tab = doc.add_table(rows=1, cols=len(headers))
    tab.alignment = WD_TABLE_ALIGNMENT.CENTER
    tab.autofit = False
    widths = widths or [6.8 / len(headers)] * len(headers)
    for col, width in zip(tab.columns, widths):
        col.width = Inches(width)
    for i, header in enumerate(headers):
        tab.rows[0].cells[i].text = str(header)
    repeat = OxmlElement("w:tblHeader")
    tab.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        for cell, value in zip(tab.add_row().cells, row):
            cell.text = str(value)
    for r, row in enumerate(tab.rows):
        no_split = OxmlElement("w:cantSplit")
        row._tr.get_or_add_trPr().append(no_split)
        for c, cell in enumerate(row.cells):
            cell.width = Inches(widths[c])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            props = cell._tc.get_or_add_tcPr()
            shading = OxmlElement("w:shd")
            shading.set(qn("w:fill"), "233F56" if r == 0 else ("F1F5F8" if r % 2 else "FFFFFF"))
            props.append(shading)
            margins = OxmlElement("w:tcMar")
            for edge in ("top", "left", "bottom", "right"):
                value = OxmlElement("w:" + edge)
                value.set(qn("w:w"), "95")
                value.set(qn("w:type"), "dxa")
                margins.append(value)
            props.append(margins)
            borders = OxmlElement("w:tcBorders")
            for edge in ("top", "left", "bottom", "right"):
                border = OxmlElement("w:" + edge)
                for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
                    border.set(qn("w:" + key), value)
                borders.append(border)
            props.append(borders)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.05
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c == 0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.size = Pt(10)
                    run.font.bold = r == 0
                    run.font.color.rgb = RGBColor.from_string("FFFFFF" if r == 0 else "000000")
    paragraph(doc, "").paragraph_format.space_after = Pt(0)


def new_document():
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(.7)
    section.left_margin = section.right_margin = Inches(.85)
    for name in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Caption"):
        style = doc.styles[name]
        style.font.name = "Calibri"
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.underline = False
    doc.styles["Normal"].font.size = Pt(11)
    doc.styles["Normal"].paragraph_format.space_after = Pt(7)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.1
    doc.styles["Title"].font.size = Pt(25)
    doc.styles["Heading 1"].font.size = Pt(17)
    doc.styles["Heading 2"].font.size = Pt(12)
    doc.core_properties.title = "Whistle Fine Tuning Findings and Analysis"
    doc.core_properties.author = "Just Peachy"
    paragraph(doc, "Whistle Fine Tuning Findings and Analysis", "Title")
    paragraph(doc, "Local RTX 3080 campaign", "Subtitle")
    paragraph(doc, "This report records the evidence, interpretation and decisions for adapting Whistle to older voices, meetings and difficult microphone conditions. Completed findings are appended as the campaign progresses. The campaign uses a fixed experiment budget and selects the production recipe from development results.")
    paragraph(doc, "Word error rate is the number of substituted, deleted and inserted words divided by the reference word count. Lower is better. A change in percentage points is different from a relative percentage reduction. Scores from different panels are reported separately.")
    p = section.footer.paragraphs[0]
    p.alignment = 2
    p.add_run("Whistle findings  |  ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    p._p.append(field)
    return doc


def event_heading(doc, event, new_page=True):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    if new_page:
        doc.add_page_break()
    title = re.sub(r"[^A-Za-z0-9 ]", " ", event["title"])
    p = doc.add_heading(" ".join(title.split()), level=1)
    existing_ids = [int(x.get(qn("w:id"), "0")) for x in doc.element.iter(qn("w:bookmarkStart"))]
    bookmark_id = str(max(existing_ids, default=0) + 1)
    start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), event["id"])
    end.set(qn("w:id"), bookmark_id)
    p._p.append(start)
    p._p.append(end)
    paragraph(doc, "Recorded " + now_text(), "Caption")


def render_event(doc, event):
    data, kind = event["data"], event["kind"]
    event_heading(doc, event, new_page=kind != "protocol")
    if kind == "protocol":
        config, plan = data["config"], data["plan"]
        paragraph(doc, "The initial run uses LoRA attention adapters with rank 16 and alpha 32, a learning rate of 0.0001, bf16 activations and three complete passes. Checkpoints preserve the optimizer and training position for exact resumption. Lower validation loss helps choose a checkpoint; recognition scores are needed to establish whether transcription improves.")
        table(doc, ["Dataset", "Initial loss weight"], [(LABELS[d], percent(config["dataset_weights"][d])) for d in DATASETS], [4.6, 2.2])
        paragraph(doc, "Weights are explicit loss allocations, not simply dataset sizes. Each source utterance shares its allocation across its microphone views. A quiet view receives 0.25 relative confidence compared with clearer views of the same utterance; if every surviving view has equal confidence, normalization cancels that factor. Every retained view is still visited in each full pass.")
        paragraph(doc, "The follow-up sequence contains a mixed LoRA reference, four individual-dataset LoRA pilots, at most one weighting proposal, one full-tuning pilot and one final three-pass fit. Pilots stop at the first of 10,000 steps, three passes or one active hour. Compilation, export and scoring are additional time. The final fit can use all qualified training and development audio after recipe selection; frozen tests remain reserved.")
        paragraph(doc, "Promotion requires at least 2% relative improvement in macro WER, a paired cluster-bootstrap 95% interval below zero, no dataset regression above two percentage points, and no increase in silence or noise probe false positives or inserted words. Quiet-speech WER may not worsen by more than three points when both results contain at least 100 reference words. Full-tuning memory failure retains the declared LoRA fallback.")
        paragraph(doc, "The supervisor applies these rules and advances without waiting for a report or a message. Short pilots screen options; they do not prove a dataset's causal contribution or globally optimal weighting. Pauses, persistent failures, low disk space and invalid evidence remain legitimate stopping conditions.")
    elif kind == "training":
        trained = data["completed_training"]
        paragraph(doc, f"Initial training completed {trained['epoch']} passes and {trained['step']:,} optimizer steps. It processed {trained['processed_records']:,} record visits in {trained['active_seconds']/3600:.2f} active hours. The corrected pool contains 842,439 rows; repeated microphone views and repeated passes are not unique speech.")
        table(doc, ["Export", "Size in MiB", "SHA256 prefix"], [(n, f"{m['bytes']/1024**2:.2f}", m['sha256'][:16]) for n, m in data["models"].items()], [3.3, 1.3, 2.2])
        paragraph(doc, "The best and final checkpoints are evaluated separately. The label best refers to validation loss; it does not guarantee the lowest recognition error. Initial diagnostic checkpoints archived before the audio audit are outside this run identity.")
        paragraph(doc, "Recorded provenance: " + data.get("license", "See source manifest") + ". CHiME 6 licensing was explicitly resolved by the user on 23 October 2026. Common Voice was also approved by the user for this project. Source attribution and license records remain with the assets.")
        paragraph(doc, "Base revision: " + data["base_revision"])
        paragraph(doc, "Run identity: " + data["run_identity"])
        paragraph(doc, "The compact exported file is not a measurement of device RAM consumption. Raspberry Pi memory, streaming latency and product microphone performance remain unverified. Whistle speech features have not been established as a replacement for speaker embeddings or the Nemotron diarization pipeline.")
    elif kind == "matched":
        metrics = data["metrics"]
        order=("whistle_base", "whistle_tuned_best", "whistle_tuned_final", "whistle_production_final", "whistle_production_all_audio", "whistle_production_selected_omission", "sherpa_gigaspeech_cached")
        models = [n for n in order if any(m["model"] == n for m in metrics)]
        if data.get("productions") and "whistle_tuned_best" in models:
            models.remove("whistle_tuned_best")  # Already reported in the initial matched table.
        labels = {"whistle_base":"Base", "whistle_tuned_best":"Initial best", "whistle_tuned_final":"Initial final", "whistle_production_final":"Production", "whistle_production_all_audio":"First fit", "whistle_production_selected_omission":"Refit", "sherpa_gigaspeech_cached":"Giga cached"}
        by_key = {(m["cohort"], m["model"]): m for m in metrics}
        cohorts = sorted({m["cohort"] for m in metrics})
        paragraph(doc, "This matched panel contains eight cohorts with 64 clips each. Historical GigaSpeech predictions are rescored with the same English text normalizer. These are recorded, segmented clips; they do not establish live product streaming performance. The original VOiCES split was not fully speaker disjoint; the expanded campaign reserves the overlapping speakers.")
        widths = [2.05] + [4.75 / len(models)] * len(models)
        table(doc, ["Cohort"] + [labels[m] for m in models], [[c.replace(":", " ")] + [percent(by_key.get((c,m), {}).get("wer")) for m in models] for c in cohorts], widths)
        target = "whistle_"+data["selected_production_run"] if data.get("selected_production_run") else ("whistle_production_final" if "whistle_production_final" in models else "whistle_tuned_final")
        if data.get("selected_production_run"):
            paragraph(doc,"The selected production identity is " + data["selected_production_run"] + ". Both production fits are retained in this table when present; the development decision was fixed before these test results. Initial best remains in the earlier initial matched table and source metrics.")
        improved, regressed = [], []
        for c in cohorts:
            a, b = by_key.get((c, "whistle_base")), by_key.get((c, target))
            if a and b:
                delta = 100 * (b["wer"] - a["wer"])
                if abs(delta) >= .05:
                    (improved if delta < 0 else regressed).append(f"{c.replace(':',' ')} ({abs(delta):.1f} percentage points)")
        paragraph(doc, "Compared with the base, " + labels.get(target, target).lower() + " has lower WER on " + (", ".join(improved) or "none of the measured cohorts") + ".")
        if regressed:
            paragraph(doc, "Higher WER remains on " + ", ".join(regressed) + ". The gains therefore do not establish a universal improvement. No confidence interval is provided for this initial matched table.")
        paragraph(doc, "These frozen-panel results are reported for reference and final assessment. They do not change the predeclared development selection policy or start additional training trials. CPU timings on this WSL host cannot be treated as Raspberry Pi timings or compared directly with historical GigaSpeech latency.")
    elif kind == "quality":
        paragraph(doc, f"The completed audit retains {data['rows']['train']:,} training views and {data['rows']['dev']:,} development views. It quarantines {data['quarantined_views']:,} views, including {data['opening_beep_views']:,} views whose speech annotations overlap CHiME session seconds zero to one. These are microphone views, not independent utterances.")
        table(doc, ["Dataset", "Views inspected", "Quarantined", "Quiet retained"], [(LABELS.get(d,d), f"{x['measured_views']:,}", f"{x['quarantined']:,}", f"{x['quiet_retained']:,}") for d,x in data["datasets"].items()], [2.6,1.4,1.4,1.4])
        paragraph(doc, "AMI uses locally available Array1 channels 01 to 08 and the transcript speaker's own headset. CHiME uses the corresponding speaker's two worn-microphone channels and synchronized local array channels. VOiCES includes eligible clean sources and the existing close and far re-recordings. Common Voice keeps its original age-filtered single-microphone selection and was not included in this multi-microphone level audit.")
        paragraph(doc, f"Speech-labelled views below both minus 65 dBFS RMS and minus 50 dBFS peak are excluded. Other quiet views are retained with reduced relative confidence. No automatic gain, denoising, blanket one-second trimming or invented blank transcripts are applied. {data['source_groups_lost']:,} source groups lose all usable views; other quarantined groups retain usable alternatives.")
        paragraph(doc, "This addresses near-silence and relative microphone levels. Energy cannot prove intelligibility or estimate signal-to-noise ratio: loud background noise may still conceal the labelled speaker. Quiet-view recognition and synthetic silence/noise probes remain separate evaluation safeguards.")
    elif kind == "scores":
        models = data["models"]
        paragraph(doc, "Evaluation role: " + data["role"].replace("_", " ") + ". Macro WER averages the dataset scores equally after accounting for repeated views of each source. This panel must not be numerically pooled with the eight-cohort matched panel.")
        table(doc, ["Model", "Macro WER", "Quiet WER", "Noise false positives", "Inserted words"], [(n.replace("_"," "), percent(x.get("macro_wer")), percent(x.get("quiet_audio",{}).get("wer")), percent(x.get("negative_probes",{}).get("false_positive_rate")), x.get("negative_probes",{}).get("inserted_words","Pending")) for n,x in models.items()], [2.1,1.1,1.1,1.4,1.1])
        names = list(models)
        table(doc, ["Dataset"]+[n.replace("_"," ") for n in names], [[LABELS[d]]+[percent(models[n].get("datasets",{}).get(d,{}).get("wer")) for n in names] for d in DATASETS], [2.5]+[4.3/len(names)]*len(names))
        selected = data["selected"]
        paragraph(doc, f"The lowest macro WER within this scoring result is {selected.replace('_',' ')} at {percent(models[selected]['macro_wer'])}. Checkpoint selection within a run is separate from the guarded weighting and method promotion decisions.")
        if "base_w4a8" in models and "initial_final" in models:
            a,b=models["base_w4a8"],models["initial_final"]
            paragraph(doc, f"On this expanded development panel, initial final reduces macro WER from {percent(a['macro_wer'])} to {percent(b['macro_wer'])}, a {(a['macro_wer']-b['macro_wer'])*100:.1f} percentage point change and {(1-b['macro_wer']/a['macro_wer'])*100:.1f}% relative reduction. This is descriptive development evidence; these recordings have already supported model development and the result is not an untouched generalization test.")
            paragraph(doc, "The development reference uses W4A8 quantization to make the deployment comparison more consistent. The original matched panel also contains the public mixed-bit base, so the two base scores answer different comparisons.")
        quiet = models[selected].get("quiet_audio",{})
        probes = models[selected].get("negative_probes",{})
        paragraph(doc, f"Quiet scoring covers {quiet.get('clips',0):,} views and {quiet.get('reference_words',0):,.0f} reference words. The {probes.get('clips',0)} fixed silence and Gaussian-noise probes cannot guarantee zero hallucinations in real rooms. Zero inserted words here means no false words on this small probe set only.")
        manifest=data.get("model_manifest",{})
        if manifest.get("completed_training"):
            trained=manifest["completed_training"]
            paragraph(doc, f"Training exposure recorded for this run: {trained.get('step','unknown')} steps and {trained.get('active_seconds',0)/3600:.2f} active hours. Different individual datasets can reach the epoch limit at different exposure levels.")
    elif kind == "contributions":
        effects=data["single_dataset_macro_wer_gain_over_base"]
        table(doc,["Individual dataset", "Macro WER gain over base in points"],[(LABELS.get(d,d),f"{v*100:+.2f}") for d,v in effects.items()],[3.8,3.0])
        paragraph(doc, "A positive value means the short standalone adaptation lowered macro WER relative to the base. It does not measure the dataset's marginal benefit inside a mixture. The supervisor proposes only one 1.5-times relative-weight adjustment, for the best standalone effect, and skips it if no effect is positive.")
        paragraph(doc, data["caution"])
    elif kind == "decision":
        paragraph(doc, "Selected recipe: " + data["selected"].replace("_"," ") + ". Comparison reference: " + data["reference"].replace("_"," ") + ".")
        comparisons=data.get("comparisons",[])
        if not comparisons:
            paragraph(doc, "No eligible alternative was available for this decision. The reference is retained under the fixed campaign policy.")
        for item in comparisons:
            lo,hi=item["paired_cluster_95pct_interval"]
            paragraph(doc, f"{item['candidate'].replace('_',' ')}: macro WER change {item['macro_wer_delta']*100:+.2f} points; relative gain {item['relative_gain']*100:.2f}%; paired cluster interval [{lo*100:+.2f}, {hi*100:+.2f}] points. Promotion {'passed' if item['promote'] else 'did not pass'}.")
            table(doc,["Dataset", "WER change in points"],[(LABELS.get(d,d),f"{v*100:+.2f}") for d,v in item["dataset_deltas"].items()],[4.5,2.3])
            paragraph(doc, f"Silence and noise guard: {'passed' if item['silence_noise_guard_passed'] else 'failed'}. Quiet-audio guard: {'passed or not applicable' if item['quiet_audio_guard_passed'] else 'failed'}. A negative WER change favors the candidate. The confidence interval accounts for grouped recordings but does not correct for the entire model search.")
            failures=[]
            if item['relative_gain'] < .02: failures.append('relative improvement below 2%')
            if hi >= 0: failures.append('the paired interval does not exclude no improvement')
            if max(item['dataset_deltas'].values()) > .02: failures.append('a dataset regresses by more than two points')
            if not item['silence_noise_guard_passed']: failures.append('silence or noise false output increases')
            if not item['quiet_audio_guard_passed']: failures.append('quiet recognition exceeds the regression allowance')
            if failures: paragraph(doc, 'Reasons the alternative is not promoted: ' + '; '.join(failures) + '.')
        paragraph(doc, "The next stage follows this saved decision automatically. The report does not override the decision or authorize further trials.")
        if data.get("exposure"):
            table(doc,["Run","Updates","Active hours","Exposure eligible"],[(n.replace("ext_",""),str(x["step"]),f"{x['active_seconds']/3600:.2f}","Yes" if x["eligible"] else "No") for n,x in data["exposure"].items()],[2.8,1.1,1.2,1.7])
            paragraph(doc,"Insufficient exposure is inconclusive and does not create another trial. These are fixed-budget comparisons, not a proof of an optimal mixture. The production fit's development scores and all frozen-test scores are excluded from selection.")
    elif kind == "extension_production":
        paragraph(doc,"Selected production run: " + data["selected_production_run"] + ". " + data["reason"] + ".")
        if data["rerun_required"]:
            recipe=data["recipe"]
            paragraph(doc,"One fresh-base three-pass fit uses all qualified training and development views from the retained datasets. The first production model remains saved. No further trials or production fits follow the frozen comparison.")
            table(doc,["Dataset","Selected weight"],[(LABELS.get(d,d),percent(w)) for d,w in recipe["dataset_weights"].items()],[4.6,2.2])
        else:
            paragraph(doc,"The existing production fit is retained. Repeating the same full fit would add compute without a supported recipe change, so the optional fit is skipped. Frozen scoring follows automatically.")
        paragraph(doc,"This is a development-based decision. Frozen tests report generalization and cannot trigger another search. There is still no independent final age test or actual product microphone validation.")
    elif kind == "production":
        recipe=data["recipe"]
        paragraph(doc, "The production fit uses " + data["selected_method_run"].replace("_"," ") + " with method " + recipe.get("method","lora") + ". It starts from the pretrained base and runs three passes over the qualified training plus development pool. Frozen tests remain reserved.")
        table(doc,["Setting","Selected value"],[(k,str(recipe[k])) for k in ("learning_rate","max_batch_size","batch_audio_seconds","batch_tokens","seed") if k in recipe],[3.8,3.0])
        if recipe.get("dataset_weights"):
            table(doc,["Dataset","Weight"],[(LABELS.get(d,d),percent(w)) for d,w in recipe["dataset_weights"].items()],[4.6,2.2])
        paragraph(doc, "This is the best eligible recipe among the bounded tested choices, not a claim of globally optimal weighting. The final test is run once after export. Using development audio in this fit leaves no independent final age-filtered test; new product recordings are still needed.")
    elif kind == "unavailable":
        paragraph(doc, data["reason"])
        paragraph(doc, "The campaign keeps the declared LoRA fallback and does not start a new memory or hyperparameter search.")
    elif kind == "final":
        paragraph(doc, "The bounded campaign has completed. The selected recipe, cohort recognition results and silence/noise findings are recorded above. The final candidate remains subject to actual product microphone and device validation.")
        paragraph(doc, "Final model directory: " + data.get("final_models","See source summary"))
        paragraph(doc, "No independent final age test or real product microphone validation is available. A training result does not establish diarization replacement, Raspberry Pi RAM use, or live streaming latency.")
    elif kind == "note":
        for text in data["paragraphs"]:
            paragraph(doc,text)
        for source in data.get("evidence",[]):
            paragraph(doc, "Evidence: " + source, "Caption")
    for source in event["sources"]:
        paragraph(doc, "Source: " + source["path"], "Caption")
        paragraph(doc, "SHA256 " + source["sha256"], "Caption")


def update(repo=REPO, output=None):
    from docx import Document
    from docx.oxml.ns import qn
    output = output or repo / "training/whistle_followups_v1/reporting"
    output.mkdir(parents=True,exist_ok=True)
    target = output/FILENAME
    doc = Document(target) if target.exists() else new_document()
    present={x.get(qn("w:name")) for x in doc.element.iter(qn("w:bookmarkStart"))}
    events=collect(repo,output)
    additions=[event for event in events if event["id"] not in present]
    state_path=output/"report_status.json"
    state=read_json(state_path)
    state.pop("error",None)
    if not additions:
        state.update(checked_at=time.time(), pending=False, status="unchanged")
        atomic_json(state_path,state)
        return {"status":"unchanged","added_events":0,"path":str(target)}
    for event in additions:
        render_event(doc,event)
        atomic_json(output/"evidence"/(event["id"]+".json"),event)
    temporary=output/("report_"+uuid.uuid4().hex+".docx")
    doc.save(temporary)
    # Reopen before publication so invalid OOXML never replaces the last good file.
    Document(temporary)
    try:
        os.replace(temporary,target)
    except PermissionError:
        pending=output/"Whistle_Fine_Tuning_Findings.pending.docx"
        os.replace(temporary,pending)
        state.update(status="waiting_for_document_unlock",pending=True,pending_path=str(pending),checked_at=time.time())
        atomic_json(state_path,state)
        return state
    state.update(status="updated",pending=False,updated_at=time.time(),checked_at=time.time(),
                 path=str(target),document_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                 added_events=len(additions),total_events=len(present)+len(additions),
                 visual_review="pending",campaign_complete=read_json(repo/"training/whistle_followups_v1/summary.json").get("complete",False))
    atomic_json(state_path,state)
    return state


@contextmanager
def exclusive(output):
    output.mkdir(parents=True,exist_ok=True)
    with (output/"report.lock").open("a+b") as handle:
        if os.name=="nt":
            import msvcrt
            handle.seek(0)
            if not handle.read(1): handle.write(b"0"); handle.flush()
            handle.seek(0)
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:
                yield False
                return
            try: yield True
            finally:
                handle.seek(0); msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            try: fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try: yield True
            finally: fcntl.flock(handle,fcntl.LOCK_UN)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",type=Path,default=REPO)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    output=args.output or args.repo/"training/whistle_followups_v1/reporting"
    with exclusive(output) as acquired:
        if not acquired:
            print('{"status":"already_running"}')
            return
        try:
            print(json.dumps(update(args.repo,output)))
        except Exception as error:
            state=read_json(output/"report_status.json")
            state.update(status="error",error=str(error),checked_at=time.time())
            atomic_json(output/"report_status.json",state)
            raise


if __name__=="__main__": main()
