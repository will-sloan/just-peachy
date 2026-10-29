"""Contracts protecting data, queue ordering, model selection and resumption."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import shared
import campaign
import prepare
import decide
import score
import eta
import extension


@pytest.fixture(autouse=True)
def original_protocol_only(monkeypatch):
    """These existing contracts exercise the original, unamended protocol."""
    monkeypatch.setattr(extension,"plan",lambda:{})


def test_multi_view_weight_is_per_source_and_dataset():
    frame=pd.DataFrame([{"dataset_id":"ami","source_group_id":"a"}]*9+[{"dataset_id":"ami","source_group_id":"b"},{"dataset_id":"voices","source_group_id":"c"}])
    out=prepare.reweight(frame,{"ami":.6,"voices":.4})
    totals=out.groupby("dataset_id").sample_weight.sum()/len(out)
    assert totals.to_dict()==pytest.approx({"ami":.6,"voices":.4})
    assert out.groupby("source_group_id").sample_weight.sum()["a"]==pytest.approx(out.groupby("source_group_id").sample_weight.sum()["b"])


def test_initial_completion_requires_both_results_and_models(tmp_path,monkeypatch):
    monkeypatch.setattr(shared,"BASE",tmp_path)
    for filename in ("whistle.final.cact","whistle.best.cact"): (tmp_path/filename).write_bytes(b"model")
    (tmp_path/"status.json").write_text('{"phase":"trained"}')
    (tmp_path/"evaluation_summary.json").write_text('{"complete":true}')
    assert not shared.initial_complete()
    (tmp_path/"status.json").write_text('{"phase":"complete"}')
    assert shared.initial_complete()
    (tmp_path/"evaluation_summary.json").write_text('{"complete":false}')
    assert not shared.initial_complete()


def test_queue_covers_all_four_singles_without_unbounded_sweep():
    jobs=campaign.ablations()
    assert len(jobs)==5 and jobs[0]["name"]=="mix_reference"
    for ds in shared.DATASETS:
        assert next(j for j in jobs if j["name"]=="only_"+ds)["spec"]["datasets"]==[ds]
    assert len(jobs)+1+len(campaign.method_jobs({d:.25 for d in shared.DATASETS}))+1==shared.policy()["maximum_training_runs"]==8


def test_one_full_trial_shares_the_pilot_batch_budget():
    jobs=campaign.method_jobs({d:.25 for d in shared.DATASETS})
    assert {j["spec"]["max_batch_size"] for j in jobs}=={8}
    assert {j["spec"]["batch_audio_seconds"] for j in jobs}=={60}
    assert len(jobs)==1 and jobs[0]["spec"]["method"]=="full"
    assert jobs[0]["spec"]["learning_rate"]==1e-5
    for key in ("max_batch_size","batch_audio_seconds","batch_tokens"):
        assert jobs[0]["spec"][key]==campaign.ablations()[0]["spec"][key]


def fake_run(root,name,errors):
    folder=root/name; folder.mkdir()
    items=[]
    datasets={}
    for ds in shared.DATASETS:
        error=errors.get(ds,2)
        datasets[ds]={"wer":error/20}
        for cluster in range(8):
            for view in range(2):
                items.append({"item_id":f"{ds}-{cluster}-{view}","dataset":ds,"source_group_id":f"{ds}-{cluster}","cluster":f"{ds}-{cluster}","word_errors":error,"reference_words":20})
    pd.DataFrame(items).to_json(folder/"predictions.jsonl",orient="records",lines=True)
    data={"complete":True,"role":"development","selected":"best","models":{"best":{"predictions":"predictions.jsonl","macro_wer":sum(x["wer"] for x in datasets.values())/4,"datasets":datasets,"negative_probes":{"false_positive_rate":0.,"inserted_words":0}}}}
    (folder/"scores.json").write_text(json.dumps(data))


def test_promotion_requires_paired_gain_and_no_dataset_regression(tmp_path,monkeypatch):
    monkeypatch.setattr(decide,"run_dir",lambda name:tmp_path/name)
    fake_run(tmp_path,"ref",{d:4 for d in shared.DATASETS})
    fake_run(tmp_path,"good",{d:2 for d in shared.DATASETS})
    fake_run(tmp_path,"bad",{"common_voice":5,"ami":0,"chime6":0,"voices":0})
    assert decide.paired("ref","good")["promote"]
    assert not decide.paired("ref","bad")["promote"]


def test_final_test_scores_cannot_select_recipe(tmp_path,monkeypatch):
    monkeypatch.setattr(decide,"run_dir",lambda name:tmp_path/name)
    folder=tmp_path/"x"; folder.mkdir()
    (folder/"scores.json").write_text('{"complete":true,"role":"frozen_test"}')
    with pytest.raises(ValueError): decide.result("x")


def test_scoring_resumes_after_partial_last_write(tmp_path):
    path=tmp_path/"results.jsonl"
    path.write_bytes(b'{"a":1}\n{"a":')
    assert score.records(path)==[{"a":1}]
    assert path.read_bytes()==b'{"a":1}\n'
    path.write_bytes(b'{"a":2}')
    assert score.records(path)==[{"a":2}]
    assert path.read_bytes().endswith(b"\n")


def test_pause_of_either_supervisor_blocks_followups(tmp_path,monkeypatch):
    base=tmp_path/"base"; base.mkdir()
    home=tmp_path/"campaign"; home.mkdir()
    monkeypatch.setattr(shared,"BASE",base); monkeypatch.setattr(shared,"HOME",home)
    assert not shared.paused()
    (base/"control.json").write_text('{"paused":true}')
    assert shared.paused()
    (base/"control.json").write_text('{"paused":false}')
    (home/"control.json").write_text('{"paused":true}')
    assert shared.paused()


def test_explicit_second_audio_channel(tmp_path,monkeypatch):
    import soundfile as sf
    import audio
    path=tmp_path/"stereo.wav"
    samples=np.column_stack([np.zeros(1600,np.float32),np.ones(1600,np.float32)*.25])
    sf.write(path,samples,16000,subtype="FLOAT")
    monkeypatch.setattr(audio,"audio_path",lambda *args:path)
    row={"audio_root_id":"test","audio_relative_path":"stereo.wav","start_sec":0.,"end_sec":.1,"channel_index":1}
    assert np.allclose(audio.load_audio(row),.25)
    row["channel_index"]=2
    with pytest.raises(ValueError): audio.load_audio(row)


def test_quiet_view_weight_does_not_multiply_dataset_influence():
    frame=pd.DataFrame([{"dataset_id":"ami","source_group_id":"a","view_confidence":q} for q in (1.,.25)]+[{"dataset_id":"voices","source_group_id":"b","view_confidence":1.}])
    out=prepare.reweight(frame,{"ami":.6,"voices":.4})
    assert out.sample_weight.iloc[0]==pytest.approx(4*out.sample_weight.iloc[1])
    assert out.groupby("dataset_id").sample_weight.sum().div(len(out)).to_dict()==pytest.approx({"ami":.6,"voices":.4})


def test_level_audit_quarantines_near_silent_speech_but_preserves_blank_targets(tmp_path,monkeypatch):
    import soundfile as sf
    import quality
    monkeypatch.setattr(quality,"paused",lambda:False)
    path=tmp_path/"levels.wav"
    wave=np.column_stack([np.ones(16000)*1e-5,np.ones(16000)*.001,np.ones(16000)*.1]).astype(np.float32)
    sf.write(path,wave,16000,subtype="FLOAT")
    levels=quality.measure_file(path,np.array([[0,1,0],[0,1,1],[0,1,2]],float))
    assert levels[:,0]==pytest.approx([-100,-60,-20],abs=.01)
    excluded,weights=quality.classify(levels[:,0],levels[:,1],np.array([True,True,True]))
    assert excluded.tolist()==[True,False,False]
    assert weights.tolist()==[.25,.25,1.]
    assert not quality.classify(levels[:1,0],levels[:1,1],np.array([False]))[0][0]


def test_better_wer_cannot_promote_more_silence_insertions(tmp_path,monkeypatch):
    monkeypatch.setattr(decide,"run_dir",lambda name:tmp_path/name)
    fake_run(tmp_path,"ref",{d:4 for d in shared.DATASETS})
    fake_run(tmp_path,"candidate",{d:2 for d in shared.DATASETS})
    path=tmp_path/"candidate/scores.json"
    data=json.loads(path.read_text())
    data["models"]["best"]["negative_probes"]={"false_positive_rate":.05,"inserted_words":3}
    path.write_text(json.dumps(data))
    assert not decide.paired("ref","candidate")["promote"]


def test_quality_pipeline_caches_files_and_never_qualifies_silent_speech(tmp_path,monkeypatch):
    import soundfile as sf
    import quality
    monkeypatch.setattr(shared,"HOME",tmp_path)
    monkeypatch.setattr(quality,"HOME",tmp_path)
    monkeypatch.setattr(eta,"HOME",tmp_path)
    monkeypatch.setattr(quality,"paused",lambda:False)
    monkeypatch.setattr(quality,"freeze_policy",lambda:"test")
    monkeypatch.setattr(quality,"audio_path",lambda root,path:tmp_path/path)
    for split in ("train","dev"):
        wave=np.column_stack([np.zeros(16000),np.sin(np.arange(16000)*.1)*.1]).astype(np.float32)
        sf.write(tmp_path/(split+'.wav'),wave,16000,subtype="FLOAT")
        frame=pd.DataFrame([{"dataset_id":"ami","audio_root_id":"test","audio_relative_path":split+'.wav',"source_group_id":split,"source_registry_row_id":split+str(c),"start_sec":0.,"end_sec":1.,"duration_seconds":1.,"audio_capacity":5,"token_capacity":32,"channel_index":c,"text":"hello", "tokens":np.array([1,2]),"mic_kind":"array","cluster":split} for c in (0,1)])
        frame.to_parquet(tmp_path/(split+'.parquet'),index=False)
    (tmp_path/"pool.json").write_text(json.dumps({"sha256":{s:shared.sha256(tmp_path/(s+'.parquet')) for s in ('train','dev')}}))
    assert quality.audit_pool()
    report=json.loads((tmp_path/"audio_quality.json").read_text())
    assert report["rows"]=={"train":1,"dev":1}
    assert report["quarantined_views"]==2 and report["source_groups_lost"]==0
    assert pd.read_parquet(shared.qualified("train")).channel_index.tolist()==[1]
    monkeypatch.setattr(quality,"measure_file",lambda *args:pytest.fail("Completed audit must not decode again"))
    assert quality.audit_pool()


def test_stage_transitions_end_after_eight_runs(tmp_path,monkeypatch):
    monkeypatch.setattr(campaign,"HOME",tmp_path)
    monkeypatch.setattr(campaign,"run_dir",lambda name:tmp_path/name)
    def fake_result(name):
        return {"macro_wer":.2 if name=="mix_reference" else .1,"negative_probes":{"false_positive_rate":0.,"inserted_words":0}}
    monkeypatch.setattr(decide,"result",fake_result)
    monkeypatch.setattr(decide,"choose",lambda ref,candidates:{"selected":candidates[0] if candidates else ref})
    (tmp_path/"baseline").mkdir()
    (tmp_path/"baseline/scores.json").write_text('{"models":{"base_w4a8":{"macro_wer":0.3}}}')
    (tmp_path/"weight_once").mkdir()
    (tmp_path/"weight_once/config.json").write_text(json.dumps({"dataset_weights":{d:.25 for d in shared.DATASETS}}))
    state={"stage":"baseline","jobs":[]}
    for expected in ("ablations","weights","methods","production","complete"):
        campaign.advance(state)
        assert state["stage"]==expected
    assert len(state["jobs"])==8
    assert sum(j["spec"].get("production",False) for j in state["jobs"])==1


def test_campaign_eta_includes_future_work_and_suspends_dates_when_paused(tmp_path,monkeypatch):
    monkeypatch.setattr(eta,"HOME",tmp_path)
    base=tmp_path/"base";base.mkdir()
    monkeypatch.setattr(eta,"BASE",base)
    monkeypatch.setattr(eta,"run_dir",lambda name:tmp_path/"runs"/name)
    (base/"status.json").write_text('{"phase":"training","remaining_seconds":3600,"elapsed_seconds":3600}')
    output=eta.estimate(now=1000)
    assert output["remaining_to_production"]["low_seconds"]>3600
    assert output["remaining_to_production"]["high_seconds"]>output["remaining_to_production"]["low_seconds"]
    (tmp_path/"control.json").write_text('{"paused":true}')
    assert eta.estimate(now=1000)["projected_production_finish_utc"]=={"earliest":None,"latest":None}
    (tmp_path/"control.json").write_text('{"paused":false}')
    (base/"status.json").write_text('{"phase":"failed","remaining_seconds":3600}')
    assert eta.estimate(now=1000)["blocked"] is True
    assert eta.estimate(now=1000)["projected_production_finish_utc"]=={"earliest":None,"latest":None}


def test_complete_campaign_has_zero_eta(tmp_path,monkeypatch):
    monkeypatch.setattr(eta,"HOME",tmp_path)
    (tmp_path/"summary.json").write_text('{"complete":true}')
    output=eta.estimate(now=1000)
    assert output["remaining_to_campaign_complete"]=={"low_seconds":0.,"high_seconds":0.}
    assert output["estimated_overall_percent"]==100


def test_identical_model_reuses_decode_but_different_weights_do_not(tmp_path):
    from score import reuse_identical
    (tmp_path/'best.dev.jsonl').write_text('{"hypothesis":"hello"}\n')
    (tmp_path/'best.negative.jsonl').write_text('{"inserted_words":0}\n')
    summaries={'best':{'model_sha256':'same','predictions':'best.dev.jsonl','macro_wer':.1}}
    assert reuse_identical(tmp_path,'final',tmp_path/'final.cact','different',summaries) is None
    value=reuse_identical(tmp_path,'final',tmp_path/'final.cact','same',summaries)
    assert value['reused_identical_model_from']=='best'
    assert (tmp_path/'final.dev.jsonl').read_bytes()==(tmp_path/'best.dev.jsonl').read_bytes()
    assert (tmp_path/'final.negative.jsonl').read_bytes()==(tmp_path/'best.negative.jsonl').read_bytes()
