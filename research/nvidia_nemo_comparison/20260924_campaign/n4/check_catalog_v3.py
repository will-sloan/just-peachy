"""Real Controller selection with model loading forbidden; see README_COMPOSITIONS.md."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from common import load, bind, freeze


def drain(controller):
    end = time.monotonic()+30
    while controller.commands.unfinished_tasks:
        if time.monotonic() > end:
            raise TimeoutError('Controller command did not drain')
        time.sleep(.01)
    if controller.error:
        raise RuntimeError(controller.error)


def main(args):
    import psutil
    process=psutil.Process();process.cpu_affinity([4]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if args.output.exists():
        raise ValueError('Fresh isolated test data directory required')
    args.output.mkdir(parents=True)
    sys.path[:0] = [str(args.source),str(args.source/'vendor')]
    from app.controller import Controller
    from app.backends import backend_catalog, backend_status
    from app.pipeline import ResidentModels
    from app.n2_models import N2ResidentModels
    from app.n3_models import N3ResidentModels
    # An unexpected acquisition is a test failure, never a competing model run.
    def forbidden(*args, **kwargs):
        raise AssertionError('Model acquisition is forbidden in catalog-only checks')
    for cls in (ResidentModels,N2ResidentModels,N3ResidentModels):
        cls.acquire = forbidden
        cls.enrollment_models = forbidden
    rows = [r for r in backend_catalog() if r['implemented']]
    if len(rows) != 16:
        raise ValueError('Expected 16 wired compositions')
    from compose_release_v3 import inventory
    if len(inventory(dict(backends=rows))) != 16:
        raise ValueError('Missing intended factorial combinations')
    results=[]
    for backend in rows:
        data=args.output/backend['key']
        data.mkdir()
        shutil.copyfile(args.n2_runtime,data/'n2_runtime.json')
        shutil.copyfile(args.n3_runtime,data/'n3_runtime.json')
        controller=Controller(data,args.models,saved_audio_only=True)
        try:
            controller.select_backend(backend['id']);drain(controller)
            if controller.backend_id != backend['id'] or controller.engine is not None:
                raise AssertionError('Unexpected backend selection or started engine')
            models=controller.models
            if any(getattr(models,k,0) for k in ('asr_loads','speaker_loads','streams')):
                raise AssertionError('Selection loaded a model')
            composition=backend['composition']
            if controller._n3_components != composition.get('n3') or controller._n2_components != composition.get('n2'):
                raise AssertionError('Controller components differ from manifest')
            modes=backend_status(backend['id'])['compatible_modes']
            unavailable=[m for m in modes if not backend_status(backend['id'],m)['available']]
            results.append(dict(key=backend['key'],manifest_id=backend['id'],
                selected=True,model_loads=0,modes=len(modes),unavailable_without_spatial_fixture=unavailable))
        finally:
            controller.close();drain(controller);controller.worker.join(10)
            if controller.worker.is_alive() or not controller.closed:
                raise RuntimeError('Controller failed to release owned command thread')
    result=dict(status='PASS_MODEL_FREE_WIRING_ONLY',cases=results,models_loaded=0,
        inference_cells=0,hardware_calls=0,source_catalog=bind(args.source/'config/backends.json'),
        inputs=[bind(args.n2_runtime),bind(args.n3_runtime)],test_code=bind(__file__))
    freeze(args.output/'RESULT.json',result)
    print(json.dumps(dict(status=result['status'],cases=len(results),models_loaded=0),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','n2-runtime','n3-runtime','models','output'):
        p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
