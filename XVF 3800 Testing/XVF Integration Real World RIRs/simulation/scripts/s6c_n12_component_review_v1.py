"""Bounded N12 adapter of the held independent table review; see README_S6C_N12_COMPONENT_REVIEW_V1.md."""
from pathlib import Path
import argparse,hashlib,json
ORIGINAL_SHA='8998e144925df82119f893bfa269f540701141c768c782ddb17701e97924caec'
CHANGES=[['N08/N10', 'N12', 1], ['N08_N10', 'N12', 3], ['n08_n10', 'n12', 4], ['C072', 'C067', 3], ['C074', 'C076', 3], ['bd19ed5f87b07b82b5c7fb9f095437603b20261f1d8944bb9767e8b7d99fbdae', 'd980fa246ab444810219961188c0c95ecf71c696d6d7103cf2ac87938b6691db', 1], ['9db7ca29da8604778cf97ed42b3bfeb396cf40c7b1d44755a41a11685cfb6cd2', '8b3ce24dbda109761bf36bee867e404083b88b3a104786c5b2632ef8d3459563', 1], ['a3d0baab3c7e8e54435a5b99ee228ef22af2c4b362fcd63a4d296aa11ea75902', '154ae3133be46727ad9a7adeca46a366776140c781b309651aa363f4879ad9fe', 1], ["('COMPLETE_REQUESTED_INDEX',960,960,0),'complete960'", "('COMPLETE_REQUESTED_INDEX',480,480,0),'complete480'", 1], ['(18,252,2880)', '(11,154,2880)', 1], ["'comparison scope18'", "'comparison scope11'", 1], ['for doc in (parent,core)', 'for doc in (parent,alternative,core)', 2], ['tables={}\n', "alternative=a.obj(summary['source_receipts']['C067']);a.check(summary['source_receipts']['C067']['sha256']=='10d38193dfa630bc06dd15d582f1d9086493ce104cc5b45535be01844e238517' and alternative['status']=='COMPLETE_REQUESTED_INDEX' and alternative['unscored']==0,'complete exact N03 alternative')\n tables={}\n", 1], ['len(pairs)==252', 'len(pairs)==154', 1], ["})==18,'18 contrasts/252 metric rows'", "})==11,'11 contrasts/154 metric rows'", 1], ["for pid in ('C067','C076'):", "for pid in ('C076',):", 1], ["len(unc['comparisons'])==18,'18 uncertainty groups'", "len(unc['comparisons'])==11,'11 uncertainty groups'", 1], ['uncertainty_observed_points_checked=18', 'uncertainty_observed_points_checked=11', 1], ['sources=list(a.sources.values()),population_denominators', 'sources=list(a.sources.values()),adapter_origin=ADAPTER_ORIGIN,population_denominators', 1]]

CHANGES += [('largest_observed_harm','largest_signed_difference',1),('largest_observed_benefit','smallest_signed_difference',1)]

def load():
    old=Path(__file__).with_name('s6c_n08_n10_component_review_v1.py')
    raw=old.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_SHA:raise ValueError('Held independent review source changed')
    text=raw.decode('utf-8')
    for before,after,count in CHANGES:
        if text.count(before)!=count:raise ValueError('Exact prospective review adaptation differs')
        text=text.replace(before,after)
    origin=dict(path=str(old.resolve()),bytes=len(raw),sha256=ORIGINAL_SHA,adaptations=[dict(before=x,after=y,exact_occurrences=n) for x,y,n in CHANGES],scope='Same independent integer/support/short/cost/extreme arithmetic; fixed N12 scope and extra original C067 authority only.')
    namespace={'__file__':str(Path(__file__).resolve()),'__name__':'s6c_n12_independent_adapted','ADAPTER_ORIGIN':origin}
    exec(compile(text,str(old)+'::n12_exact_adapter','exec'),namespace)
    return namespace

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    load()['run'](a.output)
