"""Explicit immutable amendment: three longer pilots and at most one extra fit.

See README.md for scope, inputs, outputs, commands and recovery. Never infer
new trials from test results or mutate an already prepared run configuration.
"""
from __future__ import annotations
from shared import HOME, LAB, SOURCE, DATASETS, read_json, atomic_json, sha256, run_dir, policy

PILOTS = ("ext_mix_reference", "ext_without_voices", "ext_without_chime6")
FIRST = "production_all_audio"
REFIT = "production_selected_omission"


def plan():
    path = SOURCE / "extension_plan.json"
    snapshot = read_json(HOME / "extension_snapshot.json")
    if not path.exists():
        if snapshot:
            raise ValueError("Frozen campaign amendment is missing")
        return {}
    value = read_json(path)
    if (value.get("version") != 1 or value.get("pilot_names") != list(PILOTS)
            or value.get("pilot_steps") != 30000 or value.get("pilot_max_active_seconds") != 7200
            or value.get("pilot_max_epochs") != 3 or value.get("maximum_training_runs") != 12
            or value.get("maximum_additional_training_runs") != 4
            or value.get("maximum_extra_production_fits") != 1
            or value.get("minimum_promotion_steps") != 20000
            or value.get("minimum_views_per_retained_dataset") != 500):
        raise ValueError("Unsupported campaign amendment budget")
    if snapshot and snapshot != {"plan": value, "sha256": sha256(path)}:
        raise ValueError("Campaign amendment changed after freezing")
    return value


def freeze():
    value = plan()
    if not value:
        return None
    if sha256(SOURCE / "plan.json") != value["base_policy_sha256"]:
        raise ValueError("Amendment does not match the original frozen policy")
    if sha256(run_dir(FIRST) / "config.json") != value["first_production_config_sha256"]:
        raise ValueError("Existing production configuration changed")
    if read_json(run_dir(FIRST) / "checkpoint.json").get("identity") != value["first_production_identity"]:
        raise ValueError("Existing production checkpoint identity changed")
    if sha256(HOME / "audio_quality.json") != value["audio_quality_summary_sha256"]:
        raise ValueError("Amendment requires the original completed quality audit")
    digest = sha256(SOURCE / "extension_plan.json")
    target = HOME / "extension_snapshot.json"
    if not target.exists():
        atomic_json(target, {"plan": value, "sha256": digest})
    return digest


def pilot_jobs(value=None):
    value = plan() if value is None else value
    if not value:
        return []
    weights = read_json(run_dir(FIRST) / "config.json")["dataset_weights"]
    jobs = []
    for name, omitted in zip(PILOTS, (None, "voices", "chime6")):
        datasets = [d for d in DATASETS if d != omitted]
        total = sum(weights[d] for d in datasets)
        jobs.append({"name": name, "spec": {
            "extension_id": value["id"], "method": "lora", "datasets": datasets,
            "dataset_weights": {d: weights[d] / total for d in datasets},
            "max_batch_size": 8, "batch_audio_seconds": 60, "batch_tokens": 1024,
            "seed": policy()["seed"]}})
    return jobs


def config_limits(name, spec):
    """Only the declared immutable new jobs can receive the larger budget."""
    value = plan()
    if not value or spec.get("extension_id") != value["id"]:
        raise ValueError("Unknown campaign amendment")
    if name in PILOTS:
        expected = next(j["spec"] for j in pilot_jobs(value) if j["name"] == name)
        if spec != expected:
            raise ValueError("Amended pilot recipe differs from the declared comparison")
    elif name == REFIT:
        decision = read_json(HOME / "extension_production_decision.json")
        if not decision.get("rerun_required") or spec != decision.get("recipe"):
            raise ValueError("Extra production fit lacks a qualifying saved decision")
    else:
        raise ValueError("Unplanned amended run")
    return {"extension_policy_sha256": freeze(),
            "max_steps": None if spec.get("production") else value["pilot_steps"],
            "max_active_seconds": None if spec.get("production") else value["pilot_max_active_seconds"],
            "epochs": 3}


def eligible_jobs(state):
    stage = state["stage"]
    if stage == "extension_pilots":
        return [j for j in state["jobs"] if j["name"] in PILOTS]
    if stage == "extension_production":
        return [j for j in state["jobs"] if j["name"] == REFIT]
    if stage == "final_comparison":
        return [j for j in state["jobs"] if j["spec"].get("production")]
    return state["jobs"]


def exported(name):
    return bool(read_json(run_dir(name) / "model_manifest.json").get("completed_training"))


def transition_after_export(state):
    name = FIRST if state["stage"] == "production" else REFIT
    return state["stage"] in ("production", "extension_production") and bool(plan()) and exported(name)


def start(state):
    digest = freeze()
    if any(j["name"] in PILOTS for j in state["jobs"]):
        raise ValueError("Amended pilots already queued; refusing duplicate jobs")
    state.update(stage="extension_pilots", extension_policy_sha256=digest)
    state["jobs"].extend(pilot_jobs())


def choose_recipe(state):
    from decide import choose
    value = plan()
    exposures = {}
    for job in eligible_jobs(state):
        folder = run_dir(job["name"])
        scores = read_json(folder / "scores.json")
        meta = read_json(folder / "model_manifest.json").get("completed_training", {})
        datasets = job["spec"]["datasets"]
        exposures[job["name"]] = {
            "step": meta.get("step", 0), "active_seconds": meta.get("active_seconds", 0),
            "dataset_records": meta.get("dataset_records", {}),
            "audio_hours_processed": meta.get("processed_audio_seconds", 0) / 3600,
            "eligible": bool(scores.get("complete") and scores.get("role") == "development"
                and meta.get("step", 0) >= value["minimum_promotion_steps"]
                and all(meta.get("dataset_records", {}).get(d, 0) >= value["minimum_views_per_retained_dataset"] for d in datasets))}
    candidates = [n for n in PILOTS[1:] if exposures[n]["eligible"]] if exposures[PILOTS[0]]["eligible"] else []
    decision = choose(PILOTS[0], candidates)
    decision.update(exposure=exposures, extension_policy_sha256=freeze(),
        selection_panel="qualified development only; no production or frozen-test score used",
        inconclusive_runs=[n for n, data in exposures.items() if not data["eligible"]],
        next_stage="one additional three-pass production fit" if decision["selected"] != PILOTS[0] else "retain existing production; frozen comparison")
    atomic_json(HOME / "extension_decision.json", decision)
    rerun = decision["selected"] != PILOTS[0]
    recipe = None
    if rerun:
        chosen = next(j for j in state["jobs"] if j["name"] == decision["selected"])
        recipe = dict(chosen["spec"], production=True)
        # Preserve the validated final-fit batch policy; weights are refitted from the base.
        original = read_json(run_dir(FIRST) / "config.json")
        recipe.update({k: original[k] for k in ("max_batch_size", "batch_audio_seconds", "batch_tokens")})
    selected = REFIT if rerun else FIRST
    atomic_json(HOME / "extension_production_decision.json", {
        "rerun_required": rerun, "selected_production_run": selected,
        "selected_method_run": decision["selected"], "recipe": recipe,
        "decision_sha256": sha256(HOME / "extension_decision.json"),
        "development_folded_into_training": True, "frozen_test_used_for_selection": False,
        "reason": "Omission passed development promotion and exposure guards" if rerun else "No eligible omission passed all guards; preserve the existing production fit"})
    state.update(stage="extension_production" if rerun else "final_comparison", selected_production_run=selected)
    if rerun:
        if any(j["name"] == REFIT for j in state["jobs"]):
            raise ValueError("Additional production fit already exists")
        state["jobs"].append({"name": REFIT, "spec": recipe})


def finish_comparison(state, base_comparison):
    """Aggregate completed small summaries without using them to choose a recipe."""
    metrics = list(base_comparison["metrics"])
    productions = {}
    panel = None
    for job in eligible_jobs(state):
        name = job["name"]
        result = read_json(run_dir(name) / "test_scores.json")
        if not result.get("complete") or result.get("role") != "frozen_test":
            raise ValueError("Production comparison incomplete")
        if panel is not None and result["panel_sha256"] != panel:
            raise ValueError("Production comparison panels differ")
        panel = result["panel_sha256"]
        final = result["models"]["final"]
        productions[name] = {"model_sha256": final["model_sha256"], "noise_probes": final["negative_probes"],
                             "models": str(run_dir(name)), "selected": name == state["selected_production_run"]}
        metrics.extend(dict(row, model="whistle_" + name) for row in final["matched_cohort_metrics"])
    result = {"complete": True, "panel_sha256": panel, "metrics": metrics, "productions": productions,
              "selected_production_run": state["selected_production_run"],
              "selection_basis": "predeclared development comparison; frozen results did not select the recipe",
              "timing_comparison": "Historical GigaSpeech timing is not directly comparable to this WSL host",
              "real_product_validation_available": False, "independent_age_test_available": False}
    atomic_json(HOME / "matched_comparison.json", result)
    return result
