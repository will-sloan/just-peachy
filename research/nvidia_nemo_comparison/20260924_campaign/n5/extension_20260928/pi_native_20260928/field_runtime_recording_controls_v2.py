"""Optional processed recording; README_RUNTIME_RECORDING_CONTROLS_V2.md."""
import ast
import base64
import hashlib
import json

INPUT_SHA = '7b6bf198c6d131e6e034f35f4cf07e1212d3b0c30e55046d9e20e592f6620e09'


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Exact recording boundary changed: '+old[:100])
    return source.replace(old, new)


def request(audio, consent):
    if type(audio) is not bool or type(consent) is not bool or audio != consent:
        raise ValueError('Select audio Off, or Processed with explicit storage consent')
    return audio


TRANSFER_HELPERS = r'''

def recording_source(source):
    def change(old,new):
        nonlocal source
        if source.count(old)!=1:raise ValueError('Exact optional archive boundary changed: '+old[:80])
        source=source.replace(old,new)
    change("expected={'conversation.json'}|{f'epochs/{e}/{f}' for e in epochs for f in EPOCH_FILES}",
        "audio=m['audio_requested']\n    members=EPOCH_FILES if audio else EPOCH_FILES-{'model_input.f32le','model_input.wav'}\n    expected={'conversation.json'}|{f'epochs/{e}/{f}' for e in epochs for f in members}")
    change("sample_rate=16000,channels=1,audio_enabled=True,\n                master='model_input.f32le',listening_copy='model_input.wav'",
        "sample_rate=16000,channels=1,audio_enabled=audio,\n                master='model_input.f32le' if audio else None,listening_copy='model_input.wav' if audio else None")
    start=source.index("        master=p/'model_input.f32le';n=master.stat().st_size//4")
    end=source.index('        # Consume the full bounded compact stream',start)
    block=source[start:end]
    source=source[:start]+"        if audio:\n"+''.join('    '+line+'\n' for line in block.splitlines())+"""        else:
            n=em.get('source_samples')
            if type(n) is not int or not 0<n<=2080000:raise ValueError('Bounded text-only source sample clock')
            if em.get('recorded_samples')!=0 or type(em.get('recorded_samples')) is not int or em.get('audio_bytes')!=0 or type(em.get('audio_bytes')) is not int or em.get('audio_sha256') is not None:
                raise ValueError('Audio-off archive contains inconsistent recording facts')
        if em.get('audio_enabled') is not audio:raise ValueError('Exact boolean audio selection')
"""+source[end:]
    change("len(infos)!=8","len(infos) not in (6,8)")
    return source


def recording_metadata(original):
    # Derive the actual installed schema function; keep every other validator.
    import inspect,textwrap
    source=textwrap.dedent(inspect.getsource(original))
    old="if type(m.get('audio_requested')) is not bool or not m['audio_requested']:raise ValueError('audio_requested must be true for this full-audio format')"
    new="if type(m.get('audio_requested')) is not bool or type(m.get('consent')) is not dict or m['consent'].get('audio_storage') is not m['audio_requested']:raise ValueError('Exact recording selection and matching consent required')"
    if source.count(old)!=1:raise ValueError('Installed conversation schema changed')
    namespace=dict(original.__globals__)
    exec(compile(source.replace(old,new),'<installed-optional-conversation-schema>','exec'),namespace)
    return namespace['conversation_metadata']
'''


def derive(raw):
    sha = lambda b: hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:
        raise ValueError('Exact backed common capsule required')
    value=json.loads(raw)
    files={n:base64.b64decode(s,validate=True) for n,s in value['files'].items()}
    if [dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]!=value['manifest']['files']:
        raise ValueError('Complete original member hashes')
    old=dict(files)
    def change(name,fn):
        path='code/'+name;source=fn(files[path].decode())
        compile(source,path,'exec');files[path]=source.encode()

    def controller(s):
        s=once(s,"or value['audio'] is not True or value['consent'] is not True:",
            "or type(value['audio']) is not bool or type(value['consent']) is not bool or value['audio'] != value['consent']:")
        s=once(s,"raise ValueError('Explicit audio-storage consent is required')",
            "raise ValueError('Choose audio Off, or Processed with storage consent')")
        s=once(s,"if meta.get('audio_requested') is not True or meta.get('consent',{}).get('audio_storage') is not True:",
            "if type(meta.get('audio_requested')) is not bool or meta.get('consent',{}).get('audio_storage') is not meta['audio_requested']:")
        s=s.replace('Create the explicitly consented audio draft before Start','Choose recording Off or consented Processed before Start')
        return s
    change('field_operator_controller_v6.py',controller)

    def ui(s):
        s=once(s,"unavailable=('New transcript Â· text only','Rename','Add note',",
            "unavailable=('Rename','Add note',")
        s=once(s,"            blocked=any(str(text).startswith(x) for x in unavailable)",
            """            if kwargs.get('key')=='new_text':
                text='Audio recording off · keep transcript'
            elif kwargs.get('key')=='new_audio':
                text='Record processed audio…'
            blocked=any(str(text).startswith(x) for x in unavailable)""")
        s=once(s,"if values.get('audio') is not True or values.get('consent') is not True:",
            "if type(values.get('audio')) is not bool or type(values.get('consent')) is not bool or values['audio'] != values['consent']:")
        s=once(s,"raise ValueError('Create a consented audio draft.')",
            "raise ValueError('Choose audio Off or consented Processed.')")
        s=once(s,"            self.preview_label.configure(text=context['runtime_profile']['label'])",
            """            status=self._session_data()
            archive=status.get('archive') or status.get('last_archive') or {}
            samples=archive.get('source_samples',0)
            state='Processed audio' if archive.get('audio_enabled') else 'Audio off'
            timing=f"{samples/16000:.1f}s / 120s" if archive else 'Choose recording before Start'
            self.preview_label.configure(text=context['runtime_profile']['label']+'\\n'+state+' · '+timing)""")
        s=once(s,'        def close(self):',"""        def show_sessions(self):
            super().show_sessions()
            after=self.actions['new_audio'].master
            holder=self.button(after.master,'Raw MIC0–MIC3 + processed · unavailable',lambda:None)
            holder.button.configure(state='disabled')
            holder.pack(after=after,fill='x',padx=self.px(12),pady=self.px(3))
            self._paragraph_label(after.master,'Simultaneous physical raw microphone taps have not been qualified for this firmware. Processed audio is the exact mono16k model input; it is not raw microphone audio.',True)

        def close(self):""")
        s=s.replace('Only a complete audio archive is available.','Use full private export for the complete saved transcript and any selected audio.')
        s=s.replace('This local ZIP contains the complete recording and its labels. It stays unencrypted on this device.',
            'This local ZIP contains the complete saved transcript, events and any selected audio. It stays unencrypted on this device.')
        s=s.replace('Create an audio draft in History before Start.','Choose Audio off or Processed in History before Start.')
        s=s.replace('Create an audio draft, then press Start. Recording needs explicit consent.',
            'Choose Audio off to keep text/events only, or Processed to save exact model-input audio with consent. Then press Start.')
        return s
    change('field_operator_ui_v1.py',ui)

    def transfer(s):
        s=once(s,'    ast.parse(source)','    source=recording_source(source)\n    ast.parse(source)')
        s=once(s,'    module.member_cap=member_cap','    module.conversation_metadata=recording_metadata(module.conversation_metadata)\n    module.member_cap=member_cap')
        s=once(s,'if len(infos)!=8 or len({x.filename for x in infos})!=8:',
            'if len(files) not in (5,7) or len(infos)!=len(files)+1 or len({x.filename for x in infos})!=len(infos):')
        return s+TRANSFER_HELPERS
    change('field_transfer_v2.py',transfer)
    change('field_operator_history_v2.py',lambda s:once(s,'if len(rows)!=7 or sum(',
        'if len(rows) not in (5,7) or sum(').replace('Complete bounded seven-member archive required','Complete bounded audio-off or processed archive required'))
    change('field_operator_transfer_files_v1.py',lambda s:once(s,'if len(before)!=7:', 'if len(before) not in (5,7):'))
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule allocation')
    for n,b in code.items():
        if n.endswith('.py'):compile(b,n,'exec')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(packed)>1048576:raise ValueError('Original packed capsule cap')
    return packed,dict(status='PREPARED_OPTIONAL_RECORDING',bundle_sha256=sha(packed),
        changed={n:dict(before_sha256=sha(old[n]),sha256=sha(b),bytes=len(b)) for n,b in files.items() if b!=old[n]},
        recording_choices=['off','processed'],raw_microphones='NOT_QUALIFIED',
        audio_off_members=5,processed_members=7,original_allocations_unchanged=True,native_executed=False)
