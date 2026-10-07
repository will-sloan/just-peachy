"""Per-process combined writer attachment; README_FIELD_OPERATOR_PARENT_V1.md."""
from pathlib import Path
from field_live_files_v2 import TOKENS,PathBudgetError
from field_operator_transfer_files_v1 import make_class
from field_operator_paths_v1 import project
_ACTIVE=None

def attach(root,admission,outputs):
    global _ACTIVE
    root=Path(root).absolute();code=root/'code'
    transfer=admission.get('transfer')
    if type(transfer) is not dict or set(transfer)!={'import_token'}:
        raise ValueError('One exact admitted import allocation required')
    token=transfer['import_token']
    rows={Path(r['path']).name:r['bytes'] for r in admission['files'] if Path(r['path']).parent==code}
    contract=project(**TOKENS,code_files=rows,import_token=token)
    if _ACTIVE is None:
        _ACTIVE=make_class(token)(root,rows,lambda:outputs.request_stop(),
            hardware_lease=Path.home()/'JustPeachy/data/xvf-hardware.lock').install()
    else:
        if _ACTIVE.root!=root or len(_ACTIVE.callbacks)>=8 or _ACTIVE.import_token!=token:
            raise PathBudgetError('Operator attachment identity/cardinality')
        if _ACTIVE.contract!=contract:raise PathBudgetError('Operator physical projection changed')
        _ACTIVE.callbacks.append(lambda:outputs.request_stop())
    outputs.physical_files=_ACTIVE
    return outputs
