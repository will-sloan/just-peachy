"""Review only the caption revision; see README_S6C_ENROLLMENT_FIGURE_V2_REVIEW.md."""
import ast,hashlib,json
from pathlib import Path
SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'

def main():
 checks=[];sources=[]
 def check(value,label):
  if not value:raise ValueError(label)
  checks.append(label)
 def read(path,binding=None):
  path=Path(path);raw=path.read_bytes();b=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if binding is not None:check(b==binding,'Exact source '+str(path))
  sources.append(b);return raw,b
 def doc(path,binding=None):
  raw,b=read(path,binding);return json.loads(raw),b
 v1,b1=doc(REPORT/'figures/enrollment_duration_v1/FIGURE_RECEIPT.json')
 v2,b2=doc(REPORT/'figures/enrollment_duration_v2/FIGURE_RECEIPT.json')
 prior,bp=doc(REPORT/'independent_review/ENROLLMENT_DURATION_FIGURE_REVIEW_V1.json')
 visual,bv=doc(REPORT/'figures/enrollment_duration_v2/VISUAL_AND_CAPTION_REVIEW_V2.json')
 check(b1['sha256']=='79e13b463627d5ee6fdeb0069a404facd356c20ebad623fcac627cfe04f74b9e','Prior figure receipt')
 check(b2['sha256']=='0d77f91fb14b8cb82e23f52f05a40341ac5e764ae92e48b03215dfd3c29b7eb2','V2 figure receipt')
 check(bp['sha256']=='12267d840e761ede617c3416d81e06830cc7c3d24d16f2bb74e6db13ffab0b9b','Prior 738-check numeric review')
 check(bv['sha256']=='d7778c4d6eda778957d97632e5c6e5bdfa30cae625f1776a2c84db22d1571b98','Visual/caption review')
 check(v1['authority']==v2['authority'] and v1['table']==v2['table'],'Exact same scoring authority and table')
 for binding in (v2['authority'],v2['table'],v2['source'],v2['readme'],*v2['outputs']):read(binding['path'],binding)
 def output(figure,name):
  found=[b for b in figure['outputs'] if Path(b['path']).name==name]
  check(len(found)==1,'Unique output '+name);return found[0]
 old_data,_=doc(output(v1,'PLOT_DATA.json')['path'],output(v1,'PLOT_DATA.json'))
 new_data,_=doc(output(v2,'PLOT_DATA.json')['path'],output(v2,'PLOT_DATA.json'))
 check(json.dumps(old_data,sort_keys=True,separators=(',',':'))==json.dumps(new_data,sort_keys=True,separators=(',',':')),'Exact canonical JSON with list order and numeric representations retained')
 old_png,_=read(output(v1,'enrollment_duration.png')['path'],output(v1,'enrollment_duration.png'))
 new_png,_=read(output(v2,'enrollment_duration.png')['path'],output(v2,'enrollment_duration.png'))
 check(old_png==new_png,'PNG bytes unchanged')
 old_source,oldb=read(visual['prior_source']['path'],visual['prior_source'])
 new_source,_=read(v2['source']['path'],v2['source'])
 check((oldb['bytes'],oldb['sha256'])==(v1['source']['bytes'],v1['source']['sha256']),'Preserved V1 source resolves the original source binding')
 trees=[]
 for source in (old_source,new_source):
  tree=ast.parse(source);nodes=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='caption']
  check(len(nodes)==1 and isinstance(nodes[0].value,ast.Constant) and isinstance(nodes[0].value.value,str),'Exactly one caption literal')
  nodes[0].value.value='CAPTION_TEXT_ONLY';trees.append(ast.dump(tree,include_attributes=False))
 check(trees[0]==trees[1],'Every other source AST field unchanged')
 raw,_=read(output(v2,'CAPTION.md')['path'],output(v2,'CAPTION.md'));caption=raw.decode('utf-8')
 for text in ('Each frozen roster contains 14 people: 9 CMU ARCTIC and 5 HiFiTTS identities',
              'two disjoint rosters contain 28 people combined','Whole-clip material, native evidence-window counts and resulting templates change',
              'not a duration-only intervention','estimated usable-speech tiers','Missing name assignments remain in the denominator'):
  check(text in caption,'Corrected caption: '+text)
 for path in (Path(__file__),Path(__file__).with_name('README_S6C_ENROLLMENT_FIGURE_V2_REVIEW.md')):read(path)
 result=dict(status='PASS_NUMERIC_CONTINUITY_AND_CAPTION_CORRECTIONS',check_count=len(checks),checks=checks,sources=sources,
  prior_numeric_review=bp,current_figure=b2,scope='V1 exact738 numerical checks remain source-bound; V2 plot data are canonically identical and only caption source literal changed. No plotting/scoring/prediction/model calls or new visual claim.')
 target=REPORT/'independent_review/ENROLLMENT_DURATION_FIGURE_REVIEW_V2.json'
 with target.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
 raw=target.read_bytes();print(json.dumps(dict(path=str(target),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),checks=len(checks))))

if __name__=='__main__':main()
