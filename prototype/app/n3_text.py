"""Optional portable finite ITN and explicit mappings with original-text trace."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

TOKEN=re.compile(r"\b[\w]+(?:['’][\w]+)*\b",re.UNICODE)
UNSUPPORTED_NUMBER_WORDS={'hundred','thousand','million','billion','trillion','point','half','quarter','third','fourth','fifth'}
UNSUPPORTED_UNITS={'dollar','dollars','euro','euros','pound','pounds','cent','cents'}


class TextLayers:
    def __init__(self,grammar_path=None,*,expected_sha256=None):
        self.grammar=None;self.grammar_sha256=None
        if grammar_path is not None:
            payload=Path(grammar_path).read_bytes()
            self.grammar_sha256=hashlib.sha256(payload).hexdigest()
            if expected_sha256 is None or self.grammar_sha256!=expected_sha256:
                raise ValueError('Explicit verified ITN artifact hash required')
            value=json.loads(payload)
            if value.get('schema')!='just-peachy.n3.itn-subset.v1' or value.get('status')!='COMPILED_EXHAUSTIVE_NUMERIC_PARITY_PASSED':
                raise ValueError('Unverified ITN subset')
            self.grammar=value

    def transform(self,text,*,enabled=False,approved_mappings=()):
        if not isinstance(text,str) or len(text)>100000:raise ValueError('Bounded text input required')
        edits=[];tokens=list(TOKEN.finditer(text));words=[m.group().casefold() for m in tokens]
        unavailable = enabled and self.grammar is None
        if enabled and not unavailable:
            numbers=self.grammar['numbers'];units=self.grammar['units']
            numeric_words={word for phrase in numbers for word in phrase.split()}
            at=0
            while at<len(tokens):
                if words[at] not in numeric_words:at+=1;continue
                end=at+1
                while end<len(tokens) and words[end] in numeric_words|UNSUPPORTED_NUMBER_WORDS|{'and'} and text[tokens[end-1].end():tokens[end].start()].isspace():end+=1
                phrase=' '.join(words[at:end])
                initialism=at>=2 and len(words[at-1])==len(words[at-2])==1
                unsupported_neighbor=(at>0 and words[at-1] in UNSUPPORTED_NUMBER_WORDS) or (end<len(words) and words[end] in UNSUPPORTED_UNITS)
                if phrase in numbers and not initialism and not unsupported_neighbor:
                    unit=words[end] if end<len(words) else None
                    has_unit=unit in units and text[tokens[end-1].end():tokens[end].start()].isspace()
                    if has_unit or int(numbers[phrase])>=self.grammar['standalone_minimum']:
                        last=end+1 if has_unit else end
                        replacement=numbers[phrase]+(' '+units[unit] if has_unit else '')
                        edits.append((tokens[at].start(),tokens[last-1].end(),replacement,'verified_nemo_finite_itn'))
                        end=last
                at=end
        # Mappings are explicit, contextual caller choices. No active-speaker
        # name, gallery, fuzzy replacement or sentence reconstruction is used.
        for mapping in approved_mappings:
            if mapping.get('approved') is not True:continue
            alias,preferred,context=(mapping.get(k,'') for k in ('alias','preferred','context'))
            if not all(isinstance(x,str) and 0<len(x)<=100 for x in (alias,preferred,context)):
                raise ValueError('Approved mappings need bounded alias, preferred form and independent context')
            if context.casefold() in alias.casefold() or alias.casefold() in context.casefold():
                raise ValueError('Mapping context must be independent of its alias')
            if not re.search(r'(?<!\w)'+re.escape(context)+r'(?!\w)',text,re.I):continue
            for match in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text,re.I):
                edits=[e for e in edits if e[1]<=match.start() or e[0]>=match.end()]
                edits.append((match.start(),match.end(),preferred,'explicit_contextual_mapping'))
        edits.sort()
        pieces=[];trace=[];cursor=0;output_cursor=0
        for start,end,replacement,rule in edits:
            if start<cursor:raise ValueError('Overlapping approved mappings')
            unchanged=text[cursor:start];pieces.append(unchanged);output_cursor+=len(unchanged)
            trace.append(dict(source_start=start,source_end=end,original=text[start:end],replacement=replacement,
                output_start=output_cursor,output_end=output_cursor+len(replacement),rule=rule,
                grammar_sha256=self.grammar_sha256 if rule=='verified_nemo_finite_itn' else None))
            pieces.append(replacement);output_cursor+=len(replacement);cursor=end
        pieces.append(text[cursor:])
        return dict(original=text,text=''.join(pieces),trace=trace,
            status='APPLIED' if trace else 'UNCHANGED',itn_status='UNAVAILABLE_ITN_ARTIFACT' if unavailable else ('ENABLED' if enabled else 'DISABLED'),manual_corrections=[])
