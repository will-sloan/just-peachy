"""Alias the exact N1 eight-job regression manifest for N2; see README.md."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import wave

from prepare import HERE,bind,fingerprint,frozen_save,load,sha

LOCAL=Path("G:/Just_Peachy_N1/20260924_campaign/local")


def prepare(source,truth_path,out):
    source,truth_path,out=Path(source),Path(truth_path),Path(out)
    original=load(source);truth={c["job_id"]:c for c in load(truth_path)["cells"]}
    prepared=load(truth_path.with_name("MANIFEST_RECEIPT.json"))
    expected_truth=next(r for r in prepared["outputs"] if Path(r["path"]).name==truth_path.name)
    if sha(truth_path)!=expected_truth["sha256"]:raise ValueError("Frozen evaluator truth changed")
    if len(original["jobs"])!=8:raise ValueError("Original N1 regression must remain exactly eight jobs")
    allowed={"job_id","audio_path","audio_sha256","frames","sample_rate_hz","gain","reset_between_scenes","tap"}
    jobs=[];aliases={}
    for job in original["jobs"]:
        if set(job)!=allowed or not re.fullmatch(r"N1_REGRESSION_S45_\d{2}_\d{2}_O[01]",job["job_id"]):raise ValueError("Unexpected original regression job/schema")
        canonical="N2_"+job["job_id"].removeprefix("N1_REGRESSION_")
        if canonical not in truth or truth[canonical]["frames"]!=job["frames"] or truth[canonical]["tap"]!=job["tap"]:raise ValueError("Regression job lacks matching frozen truth")
        if job["gain"]!=1 or job["sample_rate_hz"]!=16000 or job["reset_between_scenes"] is not True:raise ValueError("Regression gain/rate/state changed")
        if sha(job["audio_path"])!=job["audio_sha256"]:raise ValueError("Accepted regression waveform hash changed")
        with wave.open(job["audio_path"],"rb") as audio:
            if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getnframes())!=(1,2,16000,job["frames"]):raise ValueError("Regression waveform header changed")
        jobs.append(dict(job,job_id=canonical));aliases[job["job_id"]]=canonical
    if len(aliases)!=8 or len({j["job_id"] for j in jobs})!=8 or Counter(j["tap"] for j in jobs)!={"O0":4,"O1":4}:raise ValueError("Duplicate or missing paired regression job")
    pairs={}
    for job in jobs:pairs.setdefault(job["job_id"].rsplit("_",1)[0],{})[job["tap"]]=job["frames"]
    if len(pairs)!=4 or any(set(p)!={"O0","O1"} or p["O0"]!=p["O1"] for p in pairs.values()):raise ValueError("Regression source pairs differ")
    result=dict(original,jobs=jobs);frozen_save(out,result)
    receipt={"schema":"n2-regression-manifest-alias-v1","status":"PREPARED_VERIFIED_NO_INFERENCE","jobs":8,"paired_scenes":4,
             "source_manifest":{"name":source.name,"sha256":sha(source),"bytes":source.stat().st_size},
             "output_manifest":{"name":out.name,"sha256":sha(out),"bytes":out.stat().st_size},
             "original_screen_sha256":original["screen_sha256"],"truth_sha256":sha(truth_path),"generator_sha256":sha(__file__),
             "scheduler_aliases":aliases,"alias_receipt_sha256":fingerprint(aliases),"only_changed_job_field":"job_id",
             "source_audio_files_changed":0,"waveform_hashes_and_headers_verified":8,"new_audio_or_scenes":0,"model_calls":0,"device_calls":0,
             "scope":"exact original four-scene eight-job regression; noise control remains in the fixed Screen48; no invented additional regression cells"}
    frozen_save(HERE/"REGRESSION_PREPARATION_RECEIPT_V1.json",receipt)
    return receipt


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",default=str(LOCAL/"data/REGRESSION_AUDIO_ONLY.json"))
    parser.add_argument("--truth",default=str(LOCAL/"n2/evaluation/EVALUATOR_TRUTH.json"))
    parser.add_argument("--out",default=str(LOCAL/"n2/evaluation/REGRESSION_AUDIO_ONLY.json"))
    args=parser.parse_args();r=prepare(args.source,args.truth,args.out)
    print({"status":r["status"],"jobs":r["jobs"],"output_sha256":r["output_manifest"]["sha256"]})
