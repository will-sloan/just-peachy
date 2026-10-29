"""CPU-only amendment contracts; all writes use pytest temporary directories."""
import copy
import json
import pytest
import shared
import extension
import campaign
import decide
import eta


@pytest.fixture
def amended(tmp_path, monkeypatch):
    base_policy = shared.policy()
    declared = shared.read_json(shared.SOURCE / "extension_plan.json")
    home, source, base = (tmp_path / n for n in ("home", "source", "base"))
    for p in (home, source, base): p.mkdir()
    for module in (shared, extension, campaign, eta):
        monkeypatch.setattr(module, "HOME", home)
        if hasattr(module, "BASE"): monkeypatch.setattr(module, "BASE", base)
        if hasattr(module, "SOURCE"): monkeypatch.setattr(module, "SOURCE", source)
    shared.atomic_json(source / "plan.json", base_policy)
    folder = shared.run_dir(extension.FIRST); folder.mkdir(parents=True)
    config = {"method":"lora", "dataset_weights":dict(zip(shared.DATASETS,(.4,.3,.2,.1))),
              "max_batch_size":16,"batch_audio_seconds":120,"batch_tokens":2048}
    shared.atomic_json(folder / "config.json", config)
    shared.atomic_json(folder / "checkpoint.json", {"identity":"original-identity"})
    shared.atomic_json(home / "audio_quality.json", {"complete":True})
    declared.update(base_policy_sha256=shared.sha256(source / "plan.json"),
        first_production_identity="original-identity",
        first_production_config_sha256=shared.sha256(folder / "config.json"),
        audio_quality_summary_sha256=shared.sha256(home / "audio_quality.json"))
    shared.atomic_json(source / "extension_plan.json", declared)
    return home, source, base


def production_state():
    jobs=campaign.ablations()+[{"name":"weight_once","spec":{}},*campaign.method_jobs({d:.25 for d in shared.DATASETS}),
                             {"name":extension.FIRST,"spec":{"production":True}}]
    return {"stage":"production","jobs":jobs}


def complete_pilots(state, steps=30000):
    for job in extension.eligible_jobs(state):
        folder=shared.run_dir(job["name"]); folder.mkdir(parents=True)
        shared.atomic_json(folder/"scores.json",{"complete":True,"role":"development"})
        shared.atomic_json(folder/"model_manifest.json",{"completed_training":{
            "step":steps,"active_seconds":7000,"dataset_records":{d:4000 for d in job["spec"]["datasets"]}}})


def begin(state):
    shared.atomic_json(shared.run_dir(extension.FIRST)/"model_manifest.json",{"completed_training":{"step":517569}})
    campaign.advance(state)


def test_amendment_cannot_mutate_original_or_expand_after_freeze(amended):
    home,source,_=amended
    original=shared.run_dir(extension.FIRST)/"config.json"
    before=original.read_bytes()
    extension.freeze()
    assert original.read_bytes()==before
    p=shared.read_json(source/"extension_plan.json");p["rationale"]+=" edited"
    shared.atomic_json(source/"extension_plan.json",p)
    with pytest.raises(ValueError,match="changed after freezing"): extension.freeze()


def test_frozen_amendment_missing_is_not_silent_opt_out(amended):
    _,source,_=amended
    extension.freeze()
    (source/"extension_plan.json").unlink()
    with pytest.raises(ValueError,match="missing"): extension.plan()


def test_larger_limits_apply_only_to_three_declared_immutable_pilots(amended):
    jobs=extension.pilot_jobs()
    assert len(jobs)==3
    for job in jobs:
        limits=extension.config_limits(job["name"],job["spec"])
        assert limits["max_steps"]==30000 and limits["max_active_seconds"]==7200
        assert sum(job["spec"]["dataset_weights"].values())==pytest.approx(1.)
    bad=copy.deepcopy(jobs[0]);bad["spec"]["learning_rate"]=1.
    with pytest.raises(ValueError,match="differs"): extension.config_limits(bad["name"],bad["spec"])
    with pytest.raises(ValueError,match="Unplanned"): extension.config_limits("another_trial",jobs[0]["spec"])
    assert "voices" not in jobs[1]["spec"]["datasets"]
    assert "chime6" not in jobs[2]["spec"]["datasets"]


def test_existing_production_finishes_before_extra_pilots_and_tests_are_deferred(amended):
    state=production_state()
    assert not extension.transition_after_export(state)
    with pytest.raises(ValueError,match="finish"): campaign.advance(state)
    begin(state)
    assert state["stage"]=="extension_pilots" and len(state["jobs"])==11
    assert [j["name"] for j in extension.eligible_jobs(state)]==list(extension.PILOTS)
    assert not campaign.job_complete(state["jobs"][7])  # frozen test deliberately pending
    with pytest.raises(ValueError,match="duplicate"): extension.start(state)


@pytest.mark.parametrize("promote",[False,True])
def test_only_development_gain_can_queue_one_extra_fit(amended,monkeypatch,promote):
    state=production_state();begin(state);complete_pilots(state)
    calls=[]
    def choose(ref,candidates):
        calls.append((ref,candidates))
        return {"reference":ref,"selected":candidates[0] if promote else ref,"comparisons":[]}
    monkeypatch.setattr(decide,"choose",choose)
    campaign.advance(state)
    assert calls==[(extension.PILOTS[0],list(extension.PILOTS[1:]))]
    assert len(state["jobs"])==(12 if promote else 11)
    assert state["stage"]==("extension_production" if promote else "final_comparison")
    decision=shared.read_json(amended[0]/"extension_production_decision.json")
    assert decision["rerun_required"] is promote
    if promote:
        job=state["jobs"][-1]
        assert job["name"]==extension.REFIT and job["spec"]["production"]
        assert "voices" not in job["spec"]["datasets"]
        assert job["spec"]["max_batch_size"]==16
        assert extension.config_limits(job["name"],job["spec"])["max_steps"] is None


def test_inadequate_exposure_is_inconclusive_without_another_trial(amended,monkeypatch):
    state=production_state();begin(state);complete_pilots(state,steps=10000)
    monkeypatch.setattr(decide,"choose",lambda ref,candidates:{"reference":ref,"selected":ref,"comparisons":[],"candidates":candidates})
    campaign.advance(state)
    decision=shared.read_json(amended[0]/"extension_decision.json")
    assert decision["candidates"]==[] and len(decision["inconclusive_runs"])==3
    assert state["stage"]=="final_comparison" and len(state["jobs"])==11


def test_combined_frozen_results_preserve_both_production_identities(amended):
    state={"stage":"final_comparison","selected_production_run":extension.REFIT,"jobs":[
        {"name":n,"spec":{"production":True}} for n in (extension.FIRST,extension.REFIT)]}
    for n in (extension.FIRST,extension.REFIT):
        folder=shared.run_dir(n);folder.mkdir(exist_ok=True)
        shared.atomic_json(folder/"test_scores.json",{"complete":True,"role":"frozen_test","panel_sha256":"same-panel","models":{"final":{
            "model_sha256":n,"negative_probes":{},"matched_cohort_metrics":[{"model":"old-label","wer":.2,"cohort":"ami"}]}}})
    result=extension.finish_comparison(state,{"metrics":[{"model":"base","wer":.3}]})
    assert [x["model"] for x in result["metrics"]]==["base","whistle_"+extension.FIRST,"whistle_"+extension.REFIT]
    assert result["productions"][extension.REFIT]["selected"]


def test_first_export_does_not_clear_extension_eta(amended):
    home,_,base=amended
    shared.atomic_json(base/"status.json",{"phase":"complete"})
    shared.atomic_json(base/"evaluation_summary.json",{"complete":True})
    shared.atomic_json(home/"baseline/scores.json",{"complete":True})
    state=production_state();begin(state)
    shared.atomic_json(shared.run_dir(extension.FIRST)/"status.json",{"step":517569,"elapsed_seconds":100000,"remaining_seconds":0})
    result=eta.estimate(now=1000)
    assert result["first_production_model_ready"] and not result["production_model_ready"]
    assert result["remaining_to_production"]["low_seconds"]>0
    assert result["conditional_additional_fit_upper_seconds"]>100000
    assert result["maximum_training_runs"]==12
    shared.atomic_json(home/"control.json",{"paused":True})
    assert eta.estimate(now=1000)["projected_production_finish_utc"]=={"earliest":None,"latest":None}
