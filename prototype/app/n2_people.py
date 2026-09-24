"""Real TitaNet personal store with existing UUID/CRUD flow. See README_N2.md."""
from copy import deepcopy
from .people import PersonalStore
from .n2_identity import binding


def titanet_store(data_root,namespace):
    # A distinct concrete class preserves classmethod route validation without
    # mutating the baseline class or sharing its folder/voice vectors.
    preprocessing='titanet:'+binding(namespace)
    class TitanetStore(PersonalStore):
        def gallery(self,route,person_ids=None,*,alternate_advisory=False):
            result=super().gallery(route,person_ids,alternate_advisory=alternate_advisory)
            result.namespace=deepcopy(namespace)
            result.calibration={'status':'UNCALIBRATED_PERSONAL_DOMAIN'}
            result.receipt.update(namespace=deepcopy(namespace),calibration=deepcopy(result.calibration))
            return result
    TitanetStore.preprocessing=preprocessing
    return TitanetStore(data_root/'embedding_spaces'/binding(namespace)/'people',namespace['model_sha256'])
