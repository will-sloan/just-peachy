"""Authorized minimal S4 development-probe reuse. README_S45_SOURCES.md."""
import copy, json, math
from s45_sources import SIM, OUT, MANIFEST, read, bind, save, utc, file_hash, text_group, normalize

def main():
    current=read(MANIFEST);old_bank=SIM/'scene_bank/s4_v2_20260909T002140Z'
    old=read(old_bank/'SOURCE_AND_SPLIT_MANIFEST.json');policy=read(old_bank/'SOURCE_LEVEL_POLICY.json')
    people={p['identity']:p for p in current['people']};sources=[]
    for person in old['people']:
        pid=person['identity']
        if person['split']!='development':continue
        have=sum(s['identity']==pid and s['usage']=='probe' for s in current['sources'])
        needed=max(0,3-have)
        candidates=sorted([s for s in old['sources'] if s['identity']==pid and s['split']=='development' and s['usage']=='probe'],key=lambda s:s['source_id'])
        assert len(candidates)>=needed
        for original in candidates[:needed]:
            source=copy.deepcopy(original);level=policy['source_scalars'][source['source_id']]
            for field in ['source_binding','decoded_16k_binding']:assert file_hash(source[field]['path'])==source[field]['sha256']
            source.update(historical_development_reuse=True,historical_source_id=source['source_id'],
                preparation_gain=level['scalar'],preparation_gain_db=level['gain_db'],postgain_peak_fs=level['source_peak_after'],
                transcript_normalized=normalize(source['transcript']),prompt_group=text_group(source['transcript']),
                parent_group=text_group(source['transcript']),parent_book=None,quality_partition='self_reported_60plus_real_recording',
                gender=people[pid]['gender'],accent=source['self_reported_accent'],age_band=source['self_reported_age_category'],L1=None,
                source_crop_native_samples=[0,source['native_decoded']['samples']],source_crop_seconds=[0,source['duration_sec']],
                timestamp_provenance='Whole unchanged S4 development probe; inherited estimated activity, no manual word timing',
                role_frozen_before_QC=True,quality_disposition='REVIEW',
                quality_review_flags=['Compatible historical development source reuse, not a new source observation'],
                rights={'license_id':'CC0','license_binding':old['license_binding'],'no_contributor_identification':True,
                    'attribution':'Mozilla Common Voice English '+source['release'],'historical_rights_note':source['rights'],
                    'future_training_automatic_clearance':False},
                S4_source_manifest_binding=bind(old_bank/'SOURCE_AND_SPLIT_MANIFEST.json'),
                S4_level_policy_binding=bind(old_bank/'SOURCE_LEVEL_POLICY.json'))
            assert source['split']=='development' and source['usage']=='probe' and source['source_gain_applied']==1
            assert math.isclose(source['quality']['peak']*source['preparation_gain'],source['postgain_peak_fs'],abs_tol=1e-14)
            sources.append(source)
    result={'schema':'jp_s45_legacy_development_sources_v1','created_utc':utc(),'status':'PASS',
        'scope':'Only explicitly authorized minimal compatible S4 development PROBE reuse to reach three distinct probes per preserved development contributor. No S4 enrollment or reserve source reused.',
        'selection_rule':'For each preserved S4 development contributor with fewer than3 new probes, take the needed original probes by source_id order, without viewing S4.5 task scores.',
        'new_manifest_binding':bind(MANIFEST),'S4_manifest_binding':bind(old_bank/'SOURCE_AND_SPLIT_MANIFEST.json'),
        'S4_level_policy_binding':bind(old_bank/'SOURCE_LEVEL_POLICY.json'),'sources':sources,'source_count':len(sources),
        'affected_identities':sorted({s['identity'] for s in sources}),'new_selection_unchanged':True,
        'source_and_gain_bytes_preserved':True,'no_reserve_or_enrollment_reassignment':True,'adapter_binding':bind(__file__)}
    path=OUT/'LEGACY_DEVELOPMENT_PROBES.json'
    if path.exists():
        previous=read(path)
        assert previous['sources']==result['sources'] and previous['new_manifest_binding']==result['new_manifest_binding']
    else:save(path,result)
    print(json.dumps({'status':'PASS','path':str(path),'source_count':len(sources),'affected_identities':result['affected_identities'],'binding':bind(path)},indent=2))

if __name__=='__main__':main()
