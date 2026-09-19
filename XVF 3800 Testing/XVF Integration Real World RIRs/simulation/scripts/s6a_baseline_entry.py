"""Run exact archived B0 code with original asset locations. README_S6A.md."""
from __future__ import annotations
import sys
from s6a_common import SNAPSHOT, REPORT, REPO, H2, bind, read

def main():
    for row in read(REPORT/'RUN_MANIFEST_INITIAL.json')['baseline_snapshot']:
        bind(row['snapshot'],row['sha256'])
    sys.path.insert(0,str(SNAPSHOT))
    import edge_speech_pipeline.config as config
    # Relocation affects only discovery paths, not any numerical/runtime setting.
    config.REPOSITORY_ROOT=REPO
    config.EVALUATION_ROOT=H2
    from edge_speech_pipeline.cli import main as baseline_main
    return baseline_main(sys.argv[1:])

if __name__=='__main__':raise SystemExit(main())
