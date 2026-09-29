"""Isolate two whole pinned native recipes; see README_NATIVE_PROFILES_V1.md."""
import argparse
import hashlib
import json
from pathlib import Path

PARENT_SHA='d067f94ab2f64d536334ca31ee87a8243efd35d17f3895f66b9621fd0e09d7bd'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    blob=args.parent.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=PARENT_SHA:raise RuntimeError('Adapter parent hash differs')
    text=blob.decode();anchor="    StreamingProfile('ultra_low_latency', 3, 1),"
    if text.count(anchor)!=1:raise RuntimeError('Profile patch context differs')
    addition="""
    # Whole recipes from pinned aosc_state.h; coarse frames are80ms.
    # Keep prior profiles immutable. These candidates need native qualification.
    StreamingProfile('native_v3_streaming', chunk_frames=13, right_context_frames=1,
                     left_context_frames=0, fifo_frames=80, spkcache_frames=264,
                     update_period_frames=40),
    StreamingProfile('native_v3_delayed', chunk_frames=264, right_context_frames=1,
                     left_context_frames=1, fifo_frames=0, spkcache_frames=264,
                     update_period_frames=188),"""
    patched=text.replace(anchor,anchor+addition)
    compile(patched,'nemotron_diarization.py','exec')
    args.output.mkdir(parents=True,exist_ok=False)
    target=args.output/'nemotron_diarization.py'
    target.write_text(patched,encoding='utf-8',newline='\n')
    receipt=dict(parent_path=str(args.parent),parent_sha256=PARENT_SHA,
                 output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                 status='SOURCE_PREPARED_NOT_EXECUTED',native_runtime_revision='97a15afa5caa9bce5baaa86c1184103877af4101',
                 only_change='Two explicitly named whole geometry profiles; native C ABI and old profiles unchanged',
                 real_world_validated=False,release_accepted=False)
    (args.output/'DERIVATIVE.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':main()
