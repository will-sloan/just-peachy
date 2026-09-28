"""Validate selected catalog semantics before relocating a fixed gallery. README_PANEL_RETRY_V2.md."""
from copy import deepcopy


def rebind_gallery(gallery, old_catalog, new_catalog, new_binding, backend, contract):
    from mode_galleries import backend_contract
    if {k:v for k,v in old_catalog.items() if k!='backends'} != {k:v for k,v in new_catalog.items() if k!='backends'}:
        raise ValueError('Catalog schema/metadata changed')
    old = {r['key']:r for r in old_catalog['backends']}
    new = {r['key']:r for r in new_catalog['backends']}
    if len(old)!=len(old_catalog['backends']) or len(new)!=len(new_catalog['backends']):
        raise ValueError('Duplicate backend key')
    if backend not in ('nemotron_hybrid','nemotron_600m') or old.get(backend)!=new.get(backend) or backend not in old:
        raise ValueError('Selected complete backend row changed')
    if backend_contract(new_catalog,backend,'open_with_names') != contract or contract['encoder']!='E0':
        raise ValueError('Selected routing/gallery contract changed')
    result=deepcopy(gallery);result['catalog']=deepcopy(new_binding)
    proof=dict(selected_row_identical=True,selected_contract_identical=True,
        changed_unselected_keys=sorted(k for k in set(old)|set(new) if old.get(k)!=new.get(k)),
        gallery_only_changed_field='catalog',original_catalog=gallery['catalog'],new_catalog=new_binding)
    return result,proof
