"""Finalize private runtime gallery metadata without changing any vector; see README.md."""
import argparse
from copy import deepcopy
from pathlib import Path

from prepare import HERE, bind, fingerprint, frozen_save, load


def publish(component):
    component=Path(component)
    receipt=load(HERE / f"{component.name}_COMPONENT_RECEIPT.json")
    if bind(component / "RESULT.json")["sha256"] != receipt["private_result"]["sha256"]:
        raise ValueError("Component result hash mismatch")
    result=load(component / "RESULT.json")
    if result["status"] != "COMPLETE":
        raise ValueError("Cannot publish incomplete component")
    target=component / "runtime_galleries"
    rows=[]
    for row in result["galleries"]:
        source=Path(row["gallery"]["path"])
        if bind(source)["sha256"] != row["gallery"]["sha256"]:
            raise ValueError("Unverified source gallery")
        gallery=load(source)
        old_namespace=deepcopy(gallery["namespace"])
        if component.name == "E0":
            if gallery["namespace"]["preprocessing"] != "original_redimnet2_b2_fp32_graph_waveform_mono16k_gain1":
                raise ValueError("Unexpected E0 preparation namespace")
            gallery["namespace"]["preprocessing"]="mono-float32-16k-redimnet2-native-l2-v1"
        gallery["research_only"]=True
        gallery["publication_provenance"]={"source_gallery":row["gallery"],"component_result":bind(component / "RESULT.json"),
                                           "source_namespace":old_namespace,
                                           "metadata_alias_only":component.name == "E0",
                                           "alias_basis":"Same original ReDimNet graph, same mono16k float32 unity-gain waveform, same L2 output; canonical baseline namespace label only" if component.name == "E0" else "Exact loaded TitaNet namespace",
                                           "vectors_changed":False}
        gate=gallery["calibration"]
        gate["namespace"]=deepcopy(gallery["namespace"])
        gate["namespace_sha256"]=fingerprint(gallery["namespace"])
        gate["source_evaluator_profiles_sha256"]=gate.pop("gallery_profiles_sha256")
        gate["gallery_profiles_sha256"]=fingerprint(gallery["profiles"])
        gate.pop("gate_sha256",None)
        gate["gate_sha256"]=fingerprint(gate)
        frozen_save(target / source.name,gallery)
        rows.append({**row,"source_gallery":row["gallery"],"gallery":bind(target / source.name)})
    allowed={"gallery_id","roster_id","mode","domain","position","stream","tier_seconds","matched_duration_diagnostic",
             "intended_size","available_size","unavailable_count","gallery"}
    index={"schema":"n2-runtime-safe-gallery-index-v1","namespace":gallery["namespace"],"encoder":component.name,
           "publication":"actual extraction; runtime metadata canonicalized, no vector or source change",
           "conditions":[{k:v for k,v in r.items() if k in allowed} for r in rows]}
    frozen_save(component / "RUNTIME_GALLERY_INDEX_SAFE.json",index)
    return bind(component / "RUNTIME_GALLERY_INDEX_SAFE.json")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component",required=True)
    args=parser.parse_args()
    print(publish(args.component))
