"""Bounded real-model plumbing smoke; the synthetic cue is not measurement evidence."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import soundfile as sf
from .config import PipelineConfig
from .runtime import PipelineEngine
from .research_profiles import ResearchProfile, JsonSpatialProvider


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--pcm16",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--seconds",type=float,default=12.037)
    args=parser.parse_args()
    if not 1<=args.seconds<=30: raise ValueError("smoke length must be1..30seconds")
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=False)
    samples=np.fromfile(args.pcm16,dtype="<i2",count=round(args.seconds*16000)).astype(np.float32)/32768
    wav=out/"engineering_input.wav"
    sf.write(wav,samples,16000,subtype="FLOAT")
    cue=out/"synthetic_constant_cue.jsonl"
    cue.write_text("\n".join(json.dumps({"angle_deg":90.,"energy":1.,"reliability":1.,"available_at_sec":i*.05,"source_end_sec":i*.05,"sequence":i}) for i in range(round(args.seconds/.05)+1))+"\n",encoding="utf-8")
    profile=ResearchProfile.from_dict({"profile_id":"ENGINEERING_SMOKE_NOT_SCORED","input":{"already_gained":True},"asr":{"journal_read_ms":50,"endpoint_rule1_silence_sec":1.6,"endpoint_rule2_silence_sec":.8},"segmentation":{"hop_sec":.5,"post_policy":"posterior_hysteresis"},"embedding":{"window_sec":1.,"hop_sec":.5},"tracker":{"mode":"reliability_adaptive"},"xvf":{"mode":"soft_energy_advisory"}})
    base=PipelineConfig(session_root=out/"sessions",profile_root=out/"empty_gallery")
    engine=PipelineEngine(base,research_profile=profile,spatial_provider=JsonSpatialProvider(cue))
    started=time.perf_counter()
    engine.start_file(wav,realtime=False,accelerated_factor=0)
    engine.wait_for_completion(timeout=60)
    elapsed=time.perf_counter()-started
    summary=json.loads((engine.session_dir/"session_summary.json").read_text())
    events=[json.loads(line) for line in (engine.session_dir/"events.jsonl").read_text().splitlines()]
    counts=Counter(row["event_type"] for row in events)
    assert summary["state"]=="COMPLETED"
    assert summary["telemetry"]["audio_frames_dropped"]==0
    assert counts["research_embedding"]>0 and counts["research_segmentation"]>0
    assert counts["research_asr_drain"]==1 and counts["research_asr_tail_dispatch"]==1
    assert counts["research_effective_config"]==1
    for row in events:
        if row["event_type"]=="research_embedding":
            v=row["payload"]
            assert v["source_end_sec"]-v["source_start_sec"]==1.0
            assert v["modeled_available_at_sec"]>=v["source_end_sec"]+v["compute_ms"]/1000.
    result={"status":"PASS","created_utc":datetime.now(timezone.utc).isoformat(),"scope":"engineering plumbing only; first source samples, synthetic constant cue, no accuracy evidence","input_pcm16":str(args.pcm16.resolve()),"source_file_sha256":hashlib.sha256(args.pcm16.read_bytes()).hexdigest(),"actual_samples":len(samples),"elapsed_sec":elapsed,"session_dir":str(engine.session_dir),"event_counts":dict(counts),"profile":profile.to_dict(),"effective_config":summary["research"],"telemetry":summary["telemetry"]}
    (out/"SMOKE_RECEIPT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","events":dict(counts),"elapsed_sec":elapsed,"output":str(out/"SMOKE_RECEIPT.json")}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

