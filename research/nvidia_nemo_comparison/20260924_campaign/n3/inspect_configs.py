"""Read model configuration metadata without loading neural weights."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import yaml


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    results=[]
    for path in sorted(args.model_directory.glob('*.nemo')):
        found=False
        with tarfile.open(path,mode='r|*') as archive:
            for member in archive:
                if Path(member.name).name=='model_config.yaml':
                    if member.size>4*2**20:raise ValueError('Unexpectedly large config')
                    payload=archive.extractfile(member).read();config=yaml.safe_load(payload)
                    results.append(dict(model=path.name,config_sha256=hashlib.sha256(payload).hexdigest(),
                        target=config.get('target'),top_level_ctc_keys=[k for k in config if 'ctc' in k.lower()],
                        encoder_type=config.get('encoder',{}).get('_target_'),
                        decoder_type=config.get('decoder',{}).get('_target_')))
                    found=True;break
        if not found:raise ValueError('Missing model configuration: '+path.name)
    if len(results)!=3:raise ValueError('Expected three pinned N3 checkpoints')
    report=dict(schema='just-peachy.n3.model-head-inspection.v1',status='METADATA_INSPECTED_NO_NEURAL_INFERENCE',models=results,
        forced_alignment_status='DEFERRED_NO_CTC_HEAD_VERIFIED_IN_AVAILABLE_N3_CHECKPOINTS',
        limits='Configuration inspection, not a runtime head test. No new aligner model is fetched for this optional ablation. Existing disjoint E metadata remains intact.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
