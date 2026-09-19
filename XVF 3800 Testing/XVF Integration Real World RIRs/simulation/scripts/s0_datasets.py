"""Inventory existing parquet indexes, never render scenes or traverse audio corpora."""
import argparse, collections, csv, importlib.metadata, os, re, time
from s0_common import *

SPEAKERS={'AMI':'speaker_global_name','CHiME_6':'speaker_id_ref','CMU_Arctic':'speaker_id','HiFiTTS':'reader_id','LibriSpeech':'speaker_id','VOiCES':'speaker_id'}
CLEAN={'CMU_Arctic','HiFiTTS','LibriSpeech'}

def run(report):
    import pyarrow.parquet as pq
    report=Path(report);cache=HashCache();meta=H2.parent/'Normalized Metadata';raw=H2.parent/'Raw Datasets (Not formatted)'
    rows=[];details=[];licenses=[];start=time.monotonic()
    # Bounded metadata-document discovery: inspect raw roots and their first two directory levels only.
    for directory, dirs, files in os.walk(raw):
        depth=len(Path(directory).relative_to(raw).parts)
        if depth>=3:dirs[:]=[]
        for name in files:
            if re.match(r'(?i)^(license|licence|copying|copyright|readme|terms)',name):
                p=Path(directory)/name
                if p.stat().st_size<200000 and p.suffix.lower() not in ['.pdf','.docx']:
                    text=p.read_text(encoding='utf-8',errors='replace')
                    rights=[l.strip() for l in text.splitlines() if re.search('(?i)licen[cs]|copyright|permission|commercial|public.domain|redistribut',l)]
                    licenses.append({'binding':cache.bind(p),'rights_lines':rights[:30]})
    save(report/'dataset_rights_evidence.json',{'scope':'Local documents at raw-root depth <=3; evidence of statements, not legal clearance','files':licenses})
    with Progress(report,'dataset_indexes',6) as progress:
        for name,speaker in SPEAKERS.items():
            folder=meta/name;tables={}
            for p in folder.glob('*.parquet'):
                pf=pq.ParquetFile(p)
                tables[p.stem]={'rows':pf.metadata.num_rows,'columns':pf.schema.names,'binding':cache.bind(p)}
            rp=folder/'recordings.parquet';up=folder/'utterances.parquet';cols=tables['recordings']['columns']
            paths=[c for c in ['audio_path','source_audio_path','distant_audio_path'] if c in cols]
            selected=list(dict.fromkeys(paths+[c for c in [speaker,'recording_id','split','subset_group','audio_quality','stream_type'] if c in cols]))
            df=pq.read_table(rp,columns=selected).to_pandas()
            idframe=df if speaker in df.columns else pq.read_table(up,columns=[speaker]).to_pandas()
            idcounts=idframe[speaker].dropna().astype(str).value_counts()
            textcols=[c for c in ['text','text_original','text_norm','text_norm_eval'] if c in tables['utterances']['columns']]
            textcol=textcols[0] if textcols else None
            if textcol:
                ts=pq.read_table(up,columns=[textcol]).to_pandas()[textcol]
                transcript_count=int((ts.notna() & ts.fillna('').astype(str).str.strip().ne('')).sum())
            else:transcript_count=0
            sample=[]
            for col in paths:
                for v in df[col].dropna().drop_duplicates().head(5):
                    p=Path(v);sample.append({'field':col,'path':str(p),'exists':p.is_file()})
            clean=df
            if name=='LibriSpeech':clean=df[df['subset_group']=='clean']
            if name=='HiFiTTS':clean=df[df['audio_quality']=='clean']
            pairs=[];distinct_counts={}
            audio_col='source_audio_path' if name=='VOiCES' else 'audio_path'
            if speaker in clean.columns and audio_col in clean.columns:
                unique=clean[[speaker,audio_col]].dropna().drop_duplicates()
                distinct_counts={str(k):int(v) for k,v in unique.groupby(speaker)[audio_col].nunique().items()}
                if name in CLEAN:
                    for key,group in unique.groupby(speaker,sort=True):
                        if len(group)>=2 and len(pairs)<3:
                            examples=[cache.bind(Path(v)) for v in group[audio_col].head(2)]
                            pairs.append({'speaker_key':f'{name}:{key}','enrollment_candidate':examples[0],'probe_candidate':examples[1],
                                          'different_files':examples[0]['path']!=examples[1]['path'],'split_selected':False})
            counts={c:{str(k):int(v) for k,v in df[c].fillna('UNKNOWN').value_counts().items()} for c in ['split','subset_group','audio_quality','stream_type'] if c in df}
            detail={'dataset':name,'metadata_root':str(folder),'tables':tables,'readme_binding':cache.bind(folder/'README_normalized.md'),
                'indexed_recording_rows':len(df),'indexed_utterance_rows':tables['utterances']['rows'],
                'indexed_speaker_keys':len(idcounts),'speaker_id_column':speaker,'transcript_field':textcol,'nonempty_transcript_rows':transcript_count,
                'word_timing':'words.parquet present: word_start_sec / word_end_sec' if 'words' in tables else 'No word timing table; utterance start/end is not word timing',
                'group_counts':counts,'clean_candidate_index_rows':len(clean) if name in CLEAN else None,
                'unique_audio_paths_by_field':{c:int(df[c].nunique()) for c in paths},
                'sample_path_checks':sample,'sampled_paths_all_exist':all(x['exists'] for x in sample),
                'speakers_with_at_least_two_distinct_candidate_files':sum(n>=2 for n in distinct_counts.values()),
                'enrollment_probe_examples':pairs,'raw_audio_availability_scope':'Index counts; only listed sample paths checked, not a corpus-wide availability audit',
                'identity_cautions':'Namespaced IDs avoid string collisions; they do not prove distinct humans across datasets. Deduplicate source audio and chapters/readers before splitting.'}
            details.append(detail)
            rows.append({'dataset':name,'metadata_root':str(folder),'recordings_indexed':len(df),'utterances_indexed':tables['utterances']['rows'],
                'speaker_id_scheme':speaker,'speaker_keys_indexed':len(idcounts),'transcript_rows_nonempty':transcript_count,'word_timing':detail['word_timing'],
                'clean_candidate_rows':detail['clean_candidate_index_rows'],'speakers_with_two_distinct_candidate_files':detail['speakers_with_at_least_two_distinct_candidate_files'],
                'role':'Promising clean speech; choose clean subset and fixed disjoint utterances' if name in CLEAN else 'Already acoustic/multispeaker; not dry source by default' if name!='VOiCES' else 'Source branch candidate after deduplication; distant branch already reverberant',
                'rights_status':'Local statements only; see dataset_rights_evidence.json and report; future permitted use/redistribution unresolved',
                'sample_paths_exist':detail['sampled_paths_all_exist'],'availability_scope':'Index counts, not full audio validation'})
            progress.done+=1;progress.detail=name;cache.flush()
    save(report/'dataset_inventory_details.json',{'datasets':details,'python':str(BASE_PYTHON),'pyarrow_version':importlib.metadata.version('pyarrow'),
        'unindexed_raw_roots':[p.name for p in raw.iterdir() if p.is_dir() and p.name in ['Common Voice','MIT 271 RIRs']],
        'noise':'No separately qualified noise-only inventory established. Eligible campaign pre-excitation windows need S1 validation; excluded recordings are never noise sources. AMI/CHiME/VOiCES speech mixtures are not certified noise-only.',
        'elapsed_sec':time.monotonic()-start})
    with (report/'dataset_inventory.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    cache.flush();print(json.dumps(rows,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
