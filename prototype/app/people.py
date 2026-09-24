"""Private UUID enrollment with bound preprocessing and safe local import/export."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import threading
import uuid
import zipfile
import numpy as np
from .paths import atomic_json, read_json, sha256
from edge_speech_pipeline.research_identity_v3 import ResearchGallery
from .adaptation_store import AdaptationStore,validate_bank
from .reference_adaptation import base_version,domain

PREPROCESSING = 'mono-float32-16k-redimnet2-native-l2-v1'


def vector_valid(vector):
    if vector.dtype != np.float32 or vector.shape != (192,) or not np.isfinite(vector).all():
        raise ValueError('Expected finite float32 192-dimensional voice vector')
    norm = float(np.linalg.norm(vector.astype(np.float64)))
    if not math.isfinite(norm) or norm <= 1e-8: raise ValueError('Zero or invalid voice vector')
    return (vector/norm).astype(np.float32)


def clean_name(name):
    name = str(name).strip()
    if not name or len(name) > 80 or any(ord(c)<32 for c in name):
        raise ValueError('Name must contain 1–80 printable characters')
    return name


class PersonalGallery(ResearchGallery):
    """Same real resolver interface; UUID keys support duplicate display names."""
    def __init__(self, rows, backend, route, *, preprocessing=PREPROCESSING):
        self.names = [r['name'] for r, v in rows]
        self.ids = [r['id'] for r, v in rows]
        self.matrix = np.stack([v for r,v in rows]).astype(np.float32) if rows else np.empty((0,192),np.float32)
        self.matrix.setflags(write=False)
        templates = [{'person_id':r['id'],'display_name':r['name'],
                      'metadata_sha256':hashlib.sha256(json.dumps(r,sort_keys=True,allow_nan=False).encode()).hexdigest(),
                      'centroid_sha256':hashlib.sha256(v.astype('<f4').tobytes()).hexdigest(),
                      'references':[deepcopy(ref) for ref in r['references'] if route_compatible(ref['route'],route)]} for r,v in rows]
        binding = {'backend_sha256':backend,'preprocessing':preprocessing,'route':route,'templates':templates}
        self.gallery_id = 'personal-'+hashlib.sha256(json.dumps(binding,sort_keys=True,allow_nan=False).encode()).hexdigest()
        self.receipt = {'gallery_id':self.gallery_id,'backend_sha256':backend,'loaded_count':len(rows),
                        'loader':'PROTO1 PersonalStore UUID loader','preprocessing':preprocessing,
                        'dimension':192,'dtype':'float32','route':deepcopy(route),'personal_ids':self.ids[:],
                        'templates':templates,'binding_scope':'actual metadata, compatible references, normalized centroids and query route'}
        self.query_count = 0
        self.alternate_matrix=None;self.alternate_enabled=False;self.last_alternate=None
        self.base_versions={r['id']:base_version(r) for r,v in rows}
        self.environment_bank=[deepcopy(c) for r,v in rows for c in r.get('environment_bank',[])]
        self.adaptation=None

    def score(self, vector):
        self.query_count += 1
        if self.alternate_enabled and self.alternate_matrix is not None:
            import time
            v=vector_valid(np.asarray(vector,np.float32))
            base=self.matrix@v;alternate=self.alternate_matrix@v
            self.last_alternate=dict(advisory_only=True,monotonic_sec=time.perf_counter(),
                kind='whole-context voice cosine; not matched-content or phonetic score',
                candidates=[dict(person_id=pid,name=name,base=float(b),alternate=float(a) if np.isfinite(a) else None)
                            for pid,name,b,a in zip(self.ids,self.names,base,alternate)])
        ordinary=super().score(vector)
        return self.adaptation.match(vector,ordinary) if self.adaptation is not None else ordinary


class PersonalStore(AdaptationStore):
    preprocessing = PREPROCESSING
    def __init__(self, root, backend):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.backend = self._sha(backend)
        self.epoch = 0
        self._lock = threading.RLock()
        self._list_cache = None

    def _invalidate(self):
        self.epoch += 1
        self._list_cache = None

    @staticmethod
    def _sha(value):
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Expected lowercase SHA256 identity')
        return value

    @staticmethod
    def _finite(value, name, lower=None, upper=None):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError(f'{name} must be a finite number')
        if lower is not None and value<lower or upper is not None and value>upper:
            raise ValueError(f'{name} is outside the supported range')
        return float(value)

    @classmethod
    def _route(cls, route):
        if not isinstance(route,dict) or route.get('tap') not in ('O0','O1') or route.get('sample_rate')!=16000 or route.get('preprocessing')!=cls.preprocessing or route.get('waveform_domain') not in ('xvf_ua','dry_test_fixture'):
            raise ValueError('Unsupported voice reference route/preprocessing')
        expected='O0_host_plus3dB_once' if route['tap']=='O0' else 'O1_unity'
        allowed={expected,'fixture_unity'} if route['waveform_domain']=='dry_test_fixture' else {expected}
        if route.get('gain_policy') not in allowed:
            raise ValueError('Voice reference tap/gain policy mismatch')
        if route.get('enhancement') is not None:
            from .enhancement import identity_binding
            if any(route.get(k)!=v for k,v in identity_binding('identity').items()):raise ValueError('Unknown enhanced reference domain/hash')
        elif route.get('enhancement_sha256') is not None:raise ValueError('Enhancement hash without domain')
        if route.get('beam_stream') is not None and (not isinstance(route['beam_stream'],str) or not 1<=len(route['beam_stream'])<=80):raise ValueError('Invalid beam stream')
        if route.get('enhancement_config') is not None and route['enhancement_config']!=domain({k:v for k,v in route.items() if k!='enhancement_config'})['enhancement_config']:raise ValueError('Unknown enhancement configuration')
        # Additional measured device/session fields are preserved in bindings;
        # they must be finite JSON, never executable objects or unbounded blobs.
        if len(json.dumps(route,allow_nan=False).encode('utf-8'))>32768:
            raise ValueError('Oversized route provenance')
        return deepcopy(route)

    @classmethod
    def _support(cls, intervals, usable_s, elapsed_s=None):
        usable=cls._finite(usable_s,'usable_s',.5,180.)
        if not isinstance(intervals,list) or not 1<=len(intervals)<=360:
            raise ValueError('Invalid unique speech interval inventory')
        previous=0.; total=0.
        for item in intervals:
            if not isinstance(item,(list,tuple)) or len(item)!=2:raise ValueError('Invalid speech interval')
            left=cls._finite(item[0],'interval start',0.,180.)
            right=cls._finite(item[1],'interval end',0.,180.)
            if not previous<=left<right:raise ValueError('Speech intervals overlap or are unordered')
            if elapsed_s is not None and right>elapsed_s+1e-6:raise ValueError('Speech interval exceeds recorded source')
            previous=right;total+=right-left
        if abs(total-usable)>1e-5:raise ValueError('Unique speech duration differs from admitted intervals')
        return usable

    @classmethod
    def _load_vector(cls,path):
        path=Path(path)
        if path.is_symlink() or not path.is_file() or not 128<=path.stat().st_size<=4096:
            raise ValueError('Invalid voice vector file or bounded file size')
        with path.open('rb') as f:
            version=np.lib.format.read_magic(f)
            if version==(1,0):shape,fortran,dtype=np.lib.format.read_array_header_1_0(f)
            elif version==(2,0):shape,fortran,dtype=np.lib.format.read_array_header_2_0(f)
            else:raise ValueError('Unsupported voice vector NPY version')
            if shape!=(192,) or dtype!=np.dtype(np.float32) or fortran:
                raise ValueError('Expected non-pickled C-order float32 192D voice vector')
        vector=np.load(path,allow_pickle=False)
        normalized=vector_valid(vector)
        if not np.allclose(vector,normalized,rtol=0,atol=1e-5):
            raise ValueError('Voice template must be a normalized finite vector')
        return normalized

    def _path(self, identifier):
        if not isinstance(identifier,str) or str(uuid.UUID(identifier)) != identifier: raise ValueError('Invalid person UUID')
        path=self.root/identifier
        if path.is_symlink() or path.resolve().parent!=self.root:raise ValueError('Person path escapes private store')
        return path

    def list(self, *, refresh=False):
        """Return detached validated metadata; GUI polling performs no vector I/O.

        The enclosing application exclusively owns this store via runtime.lock.
        CRUD invalidates the cache. Gallery admission and a new process perform
        full validation; external edits during ownership are unsupported.
        """
        with self._lock:
            if self._list_cache is not None and not refresh:
                return deepcopy(self._list_cache)
            result = []
            for p in sorted(self.root.glob('*/person.json')):
                if p.is_symlink() or p.stat().st_size>128*1024:raise ValueError('Invalid person metadata file')
                row = read_json(p)
                self._validate(row, p.parent)
                result.append(row)
            if len(result)>256:raise ValueError('Personal gallery exceeds 256 people')
            self._list_cache = deepcopy(result)
            return result

    def summaries(self,route=None):
        """Small detached rows for touch UI; no full provenance copy per refresh."""
        with self._lock:
            if self._list_cache is None:self.list()
            return [{'id':row['id'],'name':row['name'],'references':len(row['references']),
                     'environment_references':len(row.get('environment_bank',[])),
                     'enrichment_undo':any(t['status']=='active' for t in row.get('enrichment_history',[])),
                     **({'compatible_references':sum(route_compatible(ref['route'],route) for ref in row['references'])} if route else {})}
                    for row in self._list_cache]

    def _validate(self, row, folder):
        if not isinstance(row,dict) or row.get('schema_version') != 1 or row.get('backend_sha256') != self.backend or row.get('preprocessing') != self.preprocessing:
            raise ValueError('Incompatible personal profile; no automatic model conversion')
        if len(json.dumps(row,allow_nan=False).encode('utf-8'))>128*1024:raise ValueError('Person metadata exceeds bounded size')
        if self._path(row['id']) != folder.resolve(): raise ValueError('Person folder/UUID mismatch')
        if not isinstance(row.get('name'),str):raise ValueError('Display name must be text')
        clean_name(row['name'])
        references = row.get('references')
        if not isinstance(references,list) or not 1 <= len(references) <= 20:
            raise ValueError('Invalid reference inventory')
        seen_ids=set();seen_sources=set()
        for ref in references:
            identifier = str(uuid.UUID(ref['id']))
            if identifier!=ref['id'] or identifier in seen_ids or ref['vector'] != identifier+'.npy': raise ValueError('Invalid/duplicate vector path')
            seen_ids.add(identifier)
            path = folder/ref['vector']
            self._load_vector(path)
            if sha256(path) != self._sha(ref['sha256']): raise ValueError('Voice template checksum differs')
            self._route(ref['route'])
            source=self._sha(ref['source_sha256'])
            if source in seen_sources:raise ValueError('Duplicate source reference')
            seen_sources.add(source)
            if ref.get('unique_nonoverlapping') is not True:raise ValueError('Unique source support must be explicit')
            elapsed=self._finite(ref.get('elapsed_s',180.),'elapsed_s',.5,180.)
            usable=self._support(ref['source_spans'],ref['usable_s'],elapsed)
            self._enrollment_target(ref,usable)
            quality=ref['quality']
            self._finite(quality['clipping'],'clipping',0,.005)
            self._finite(quality['consistency'],'consistency',.3,1.000001)
            if not isinstance(quality['embedding_count'],int) or isinstance(quality['embedding_count'],bool) or not 1<=quality['embedding_count']<=360:
                raise ValueError('Invalid embedding count')
            if not isinstance(ref.get('source_kind'),str) or not 1<=len(ref['source_kind'])<=80:
                raise ValueError('Missing source kind')
        for ref in references:
            side=ref.get('script_evidence')
            if side:
                if side['file']!=ref['id']+'.script.json':raise ValueError('Invalid ScriptEvidence path')
                path=folder/side['file']
                if path.is_symlink() or path.stat().st_size>256*1024 or sha256(path)!=self._sha(side['sha256']):raise ValueError('ScriptEvidence integrity failure')
                from .script_evidence import validate
                validate(read_json(path),ref,self.backend)
        validate_bank(row)
        expected={'person.json'}|{ref['vector'] for ref in references}|{ref['script_evidence']['file'] for ref in references if ref.get('script_evidence')}
        if {p.name for p in folder.iterdir()}!=expected:raise ValueError('Unreferenced personal-store payload')
        return row

    def gallery(self, route, person_ids=None, *, alternate_advisory=False):
        with self._lock:
            route=self._route(route);entries=[];incompatible=[]
            rows=self.list(refresh=True)
            if person_ids is not None:
                selected=set(person_ids)
                if not selected:raise ValueError('Select at least one compatible person for identification')
                if selected-{r['id'] for r in rows}:raise ValueError('Selected person no longer exists')
                rows=[r for r in rows if r['id'] in selected]
            for row in rows:
                compatible = [ref for ref in row['references'] if route_compatible(ref['route'],route)]
                if not compatible:
                    incompatible.append(row['id']);continue
                vectors = [self._load_vector(self._path(row['id'])/r['vector']) for r in compatible]
                weighted = sum(v*ref['usable_s'] for v,ref in zip(vectors,compatible))
                entries.append((row,vector_valid(np.asarray(weighted,np.float32))))
            result=PersonalGallery(entries,self.backend,route,preprocessing=self.preprocessing)
            if alternate_advisory:
                alternates=[]
                for row,base in entries:
                    vectors=[]
                    for ref in row['references']:
                        if ref.get('script_evidence') and route_compatible(ref['route'],route):
                            document=read_json(self._path(row['id'])/ref['script_evidence']['file'])
                            if document.get('alternate_vector') is not None:vectors.append(document['alternate_vector'])
                    alternates.append(vector_valid(np.mean(np.array(vectors,np.float32),axis=0)) if vectors else np.full(192,np.nan,np.float32))
                result.alternate_matrix=np.array(alternates,np.float32).reshape(-1,192)
                result.alternate_enabled=True
            result.receipt.update(incompatible_person_ids=incompatible,store_epoch=self.epoch,
                roster_scope='selected' if person_ids is not None else 'all',selected_person_ids=list(person_ids) if person_ids is not None else None,
                template_availability='AVAILABLE' if entries else 'NO_COMPATIBLE_PERSONAL_TEMPLATES',
                incompatibility_reason='Tap/model-input gain or preprocessing differs' if incompatible else None)
            if incompatible and (not entries or person_ids is not None):
                raise ValueError('Personal profiles exist but none match this tap/gain/preprocessing. Switch to their enrollment tap or add a compatible reference.')
            return result

    @staticmethod
    def _enrollment_target(record,usable):
        mode=record.get('capture_mode','timed')
        target=record.get('target_sec')
        if mode=='paragraph' and target is None and usable>=.5:return
        if mode=='timed' and target in (15,30,60) and usable>=target:return
        raise ValueError('Enrollment has not reached its unique-speech target or supported paragraph input')

    def save(self, name, vector, quality, route, *, person_id=None):
        with self._lock:
            return self._save(name,vector,quality,route,person_id=person_id)

    def _save(self,name,vector,quality,route,*,person_id=None):
        if not isinstance(name,str):raise ValueError('Display name must be text')
        name=clean_name(name);route=self._route(route)
        vector=vector_valid(np.asarray(vector,np.float32))
        if quality.get('can_save') is not True or quality.get('gaps',0)!=0:raise ValueError('Enrollment quality gate not satisfied')
        elapsed=self._finite(quality.get('elapsed_s',180.),'elapsed_s',.5,180.)
        usable=self._support(quality['accepted_intervals'],quality['usable_s'],elapsed)
        self._sha(quality['source_sha256'])
        target_sec=quality.get('target_sec',15)
        self._enrollment_target(dict(quality,target_sec=target_sec),usable)
        self._finite(quality['clipping'],'clipping',0,.005)
        self._finite(quality['consistency'],'consistency',.3,1.000001)
        if not isinstance(quality['embedding_count'],int) or isinstance(quality['embedding_count'],bool) or not 1<=quality['embedding_count']<=360:raise ValueError('Invalid embedding count')
        source_kind=quality.get('source_kind','user_consented_live')
        if not isinstance(source_kind,str) or not 1<=len(source_kind)<=80:raise ValueError('Invalid source kind')
        provenance={k:deepcopy(quality[k]) for k in ('source_session_id','source_provenance','capture_metadata','capture_integrity','script_estimate') if k in quality}
        for utterance in provenance.get('script_estimate',{}).get('utterances',[]):utterance.pop('token_timing',None)
        if quality.get('capture_mode')=='paragraph' and 'offered_reference' in quality:
            from .enrollment_progress import reference_text
            offered=reference_text(quality['offered_reference']['offered_text'])
            if offered!=quality['offered_reference']:raise ValueError('Offered reference hash/role mismatch')
            provenance['offered_reference']=offered
        if len(json.dumps(provenance,allow_nan=False).encode('utf-8'))>32768:raise ValueError('Oversized source provenance')
        person_id=person_id or str(uuid.uuid4());folder=self._path(person_id)
        if folder.exists():self._validate(read_json(folder/'person.json'),folder)
        elif len(self.list())>=256:raise ValueError('Personal gallery exceeds 256 people')
        folder.mkdir(exist_ok=True)
        row = read_json(folder/'person.json') if (folder/'person.json').exists() else {
            'schema_version':1,'id':person_id,'name':name,'backend_sha256':self.backend,
            'preprocessing':self.preprocessing,'created_utc':datetime.now(timezone.utc).isoformat(),'references':[]}
        if len(row['references'])>=20: raise ValueError('Maximum 20 references per person')
        if any(r.get('source_sha256')==quality['source_sha256'] for r in row['references']):
            raise ValueError('This exact reference has already been enrolled')
        identifier = str(uuid.uuid4())
        target = folder/(identifier+'.npy')
        with target.open('xb') as f: np.save(f,vector,allow_pickle=False)
        ref = {'id':identifier,'vector':target.name,'sha256':sha256(target),'route':deepcopy(route),
            'usable_s':quality['usable_s'],'source_sha256':quality['source_sha256'],
            'source_kind':source_kind,
            'source_spans':quality['accepted_intervals'],'unique_nonoverlapping':True,
            'quality':{k:quality[k] for k in ('clipping','consistency','embedding_count')},
            'elapsed_s':elapsed,'target_sec':target_sec,
            'capture_mode':quality.get('capture_mode','timed'),
            'evidence_status':'limited_short_reference' if usable<15 else 'quality_checked_not_identity_proof',
            'source_provenance':provenance,
            'created_utc':datetime.now(timezone.utc).isoformat()}
        row['references'].append(ref)
        side_path=None
        try:
            if route.get('enhancement'):self._require_script_feature('enhanced-reference-v1')
            if quality.get('script_evidence'):
                from .script_evidence import validate
                evidence=deepcopy(quality['script_evidence'])
                evidence.update(reference_id=identifier,anchor_file_sha256=ref['sha256'])
                validate(evidence,ref,self.backend)
                self._require_script_feature()
                side_path=folder/(identifier+'.script.json');atomic_json(side_path,evidence)
                ref['script_evidence']=dict(file=side_path.name,sha256=sha256(side_path))
            if len(json.dumps(row,allow_nan=False).encode('utf-8'))>128*1024:raise ValueError('Person metadata exceeds bounded size')
            atomic_json(folder/'person.json',row)
        except Exception:
            if side_path is not None:side_path.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            if not (folder/'person.json').exists():folder.rmdir()
            raise
        self._invalidate()
        return row

    def _require_script_feature(self,feature='script-evidence-v1'):
        schema=self.root.parent/'DATA_SCHEMA.json'
        document=read_json(schema) if schema.exists() else dict(schema_version=1)
        if document.get('schema_version')!=1:raise ValueError('Unknown personal data schema')
        document['required_features']=sorted(set(document.get('required_features',[]))|{feature})
        atomic_json(schema,document)

    @staticmethod
    def _reference_files(row):
        return [ref['vector'] for ref in row['references']]+[ref['script_evidence']['file'] for ref in row['references'] if ref.get('script_evidence')]

    def rename(self, identifier, name):
        with self._lock:
            if not isinstance(name,str):raise ValueError('Display name must be text')
            p = self._path(identifier)/'person.json'
            row = self._validate(read_json(p),p.parent); row['name'] = clean_name(name)
            atomic_json(p,row); self._invalidate()

    def delete(self, identifier):
        with self._lock:
            folder = self._path(identifier)
            row = self._validate(read_json(folder/'person.json'),folder)
            # Exact files belonging to the validated UUID only; no recursive deletion.
            for name in self._reference_files(row):(folder/name).unlink()
            (folder/'person.json').unlink(); folder.rmdir(); self._invalidate()

    def export(self, path, consent=False):
        if consent is not True: raise ValueError('Explicit unencrypted voice profile export consent required')
        with self._lock:
            files = {}
            for row in self.list(refresh=True):
                folder = self._path(row['id'])
                for p in [folder/'person.json']+[folder/name for name in self._reference_files(row)]:
                    files[str(p.relative_to(self.root)).replace('\\','/')] = p.read_bytes()
        manifest = {'schema_version':1,'privacy':'UNENCRYPTED PERSONAL VOICE VECTORS',
                    'files':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()}}
        with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED) as z:
            for k,v in files.items(): z.writestr(k,v)
            z.writestr('MANIFEST.json',json.dumps(manifest))

    def import_archive(self, path, consent=False):
        if consent is not True: raise ValueError('Explicit personal voice import consent required')
        with self._lock:
            return self._import_archive(path)

    def _import_archive(self,path):
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist())>16*1024*1024 or len(z.infolist())>6000:
                raise ValueError('Oversized voice archive')
            if len(z.namelist())!=len({n.casefold() for n in z.namelist()}): raise ValueError('Duplicate archive entries')
            manifest = json.loads(z.read('MANIFEST.json'))
            if manifest.get('schema_version')!=1 or set(z.namelist())!=set(manifest['files'])|{'MANIFEST.json'}:
                raise ValueError('Invalid archive manifest')
            data = {}
            for name,digest in manifest['files'].items():
                parts = name.split('/')
                if len(parts)!=2 or str(uuid.UUID(parts[0]))!=parts[0] or (parts[1]!='person.json' and not parts[1].endswith(('.npy','.script.json'))):
                    raise ValueError('Unsafe profile archive path')
                if Path(parts[1]).name!=parts[1] or ':' in name or '\\' in name: raise ValueError('Unsafe profile filename')
                raw = z.read(name)
                if hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('Archive checksum failure')
                data[name]=raw
            # Fully validate in an isolated temporary directory before modifying people.
            import tempfile
            # Same-filesystem staging permits atomic UUID-directory publication.
            with tempfile.TemporaryDirectory(prefix='.peachy-import-',dir=self.root) as tmp:
                for name,raw in data.items():
                    p=Path(tmp)/name; p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
                staged=PersonalStore(Path(tmp),self.backend); rows=staged.list()
                expected={r['id']+'/person.json' for r in rows}|{r['id']+'/'+name for r in rows for name in self._reference_files(r)}
                if expected!=set(data): raise ValueError('Unreferenced archive payload')
                if any(self._path(r['id']).exists() for r in rows): raise ValueError('UUID already exists; import never overwrites people')
                if len(self.list())+len(rows)>256:raise ValueError('Import exceeds 256 personal profiles')
                published=[]
                try:
                    if any(ref.get('script_evidence') for row in rows for ref in row['references']):self._require_script_feature()
                    if any(ref['route'].get('enhancement') for row in rows for ref in row['references']):self._require_script_feature('enhanced-reference-v1')
                    if any(row.get('enrichment_history') for row in rows):
                        from .reference_adaptation import FEATURE
                        self._require_script_feature(FEATURE)
                    for row in rows:
                        destination=self._path(row['id']);os.replace(Path(tmp)/row['id'],destination);published.append(row)
                except Exception:
                    # Roll back only UUIDs created by this import; existing people are untouched.
                    for row in published:
                        destination=self._path(row['id'])
                        for name in self._reference_files(row):(destination/name).unlink()
                        (destination/'person.json').unlink();destination.rmdir()
                    raise
        self._invalidate()


def route_compatible(reference, query):
    return domain(reference)==domain(query)


def analyze_enrollment(samples, models, config, target_sec=30, *, gaps=0, source_kind='user_consented_live'):
    """Unique disjoint half-second evidence, estimated speech/overlap quality gate."""
    samples=np.asarray(samples,np.float32).reshape(-1)
    if not np.isfinite(samples).all(): raise ValueError('Nonfinite enrollment audio')
    if target_sec not in (15,30,60): raise ValueError('Enrollment target must be15,30or60 seconds')
    clipping=float(np.mean(np.abs(samples)>=.999)) if len(samples) else 0.
    accepted=[];vectors=[]
    # Each source sample can count at most once. Segment using fixed nonoverlapping10s blocks;
    # padding the last block supplies model context but contributes no usable duration.
    for offset in range(0,len(samples),160000):
        chunk=samples[offset:offset+160000]
        padded=np.pad(chunk,(0,160000-len(chunk)))
        seg=models.segment(padded,include_posteriors=True)
        speech=seg.get('speech_probability',seg['speech'])
        overlap=seg.get('overlap_probability',seg['overlap'])
        for left in range(0,len(chunk)-7999,8000):
            piece=chunk[left:left+8000]
            lo=int(left/160000*len(speech));hi=max(lo+1,int((left+8000)/160000*len(speech)))
            rms=float(np.sqrt(np.mean(piece.astype(np.float64)**2)))
            if rms<config.minimum_rms or np.mean(np.abs(piece)>=.999)>.005: continue
            if float(np.mean(speech[lo:hi]))<.6 or float(np.mean(overlap[lo:hi]))>.2: continue
            accepted.append([(offset+left)/16000,(offset+left+8000)/16000])
            vectors.append(models.embed(piece))
    usable=len(accepted)*.5
    centroid=None;consistency=0.
    if vectors:
        matrix=np.stack(vectors);centroid=vector_valid(np.mean(matrix,axis=0).astype(np.float32))
        consistency=float(np.quantile(matrix@centroid,.1))
    quality={'elapsed_s':len(samples)/16000,'usable_s':usable,'target_sec':target_sec,
        'clipping':clipping,'consistency':consistency,'embedding_count':len(vectors),
        'accepted_intervals':accepted,'gaps':gaps,'source_kind':source_kind,
        'source_sha256':hashlib.sha256(samples.astype('<f4').tobytes()).hexdigest(),
        'can_save':bool(usable>=target_sec and clipping<=.005 and consistency>=.3 and not gaps),
        'quality':'Estimated clean speech only; not proof of a single speaker or identity accuracy'}
    return quality,centroid
