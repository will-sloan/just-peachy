"""Independent refresh delta review; README_TEST_S6C_INVENTORY_REFRESH_DESIGN_V1.md."""
import argparse, ast, hashlib, importlib, json, os, tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
PIN="bc66af0ae233935c5b33c0c5487883d5d0e4c80769d383018bbe0e3d90e66618"
def bind(p):
 raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
assert bind(HERE/"s6c_inventory_refresh_v1.py")["sha256"]==PIN
M=importlib.import_module("s6c_inventory_refresh_v1")
def function(module,name):
 return deepcopy(next(n for n in ast.parse(Path(module.__file__).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name==name))
def run(output):
 names=[];captured=[]
 fix=ast.fix_missing_locations
 def capture(node):
  captured.append(deepcopy(node));return fix(node)
 d=M.Discovery([],guard=lambda:None)
 originals=(M.B.collect,M.B.collect_auxiliary,M.B.validate_native,M.B.process_state,M.V4.paced_adapter,M.V5.additive,M.V6.additive)
 with patch.object(M.ast,"fix_missing_locations",capture):
  collector=M.legacy_context(d,[])
 assert len(captured)==7
 contexts=[(M.B,"collect_auxiliary",None),(M.V3,"auxiliary_adapter",None),(M.V4,"paced_adapter",None),(M.V4,"paced_adapter",M.V5.SENTINEL_REPLACEMENTS),(M.V5,"additive",None),(M.V6,"additive",None),(M.B,"collect",None)]
 class Reverse(ast.NodeTransformer):
  def visit_Call(self,n):
   n=self.generic_visit(n)
   if isinstance(n.func,ast.Name) and n.func.id=="_discovery_paths":
    assert len(n.args)==1 and not n.keywords;return n.args[0]
   if isinstance(n.func,ast.Name) and n.func.id=="_discovery_walk":
    n.func=ast.Attribute(value=ast.Name(id="os",ctx=ast.Load()),attr="walk",ctx=ast.Load())
   return n
 class Literals(ast.NodeTransformer):
  def __init__(self,mapping):self.mapping=mapping
  def visit_Constant(self,n):
   if isinstance(n.value,str) and n.value in self.mapping:n.value=self.mapping[n.value]
   return n
 for i,((module,name,literals),changed) in enumerate(zip(contexts,captured)):
  expected=function(module,name)
  if literals:expected=Literals(literals).visit(expected)
  actual=Reverse().visit(changed.body[0])
  assert ast.dump(actual,include_attributes=False)==ast.dump(expected,include_attributes=False),(i,name)
  names.append("exact_reversed_AST_"+str(i)+"_"+name)
 assert originals==(M.B.collect,M.B.collect_auxiliary,M.B.validate_native,M.B.process_state,M.V4.paced_adapter,M.V5.additive,M.V6.additive)
 names.append("seven_original_function_bindings_unchanged")
 assert collector.__globals__ is not M.B.__dict__
 assert collector.__globals__["normalize_native"].__code__ is M.B.normalize_native.__code__
 names.append("native_normalizer_code_retained_private")
 with tempfile.TemporaryDirectory(prefix="s6c_refresh_independent_") as td:
  root=Path(td)
  for rel in ("regular/nested","unknown_fast_v2/nested","own_fast_v2/nested"):
   p=root/rel;p.mkdir(parents=True);(p/"small.json").write_text("{}")
  plain=[(str(p),list(dirs),list(files)) for p,dirs,files in os.walk(root)]
  observed=[(str(p),list(dirs),list(files)) for p,dirs,files in M.Discovery([],guard=lambda:None).walk(root)]
  assert plain==observed;names.append("empty_exclusions_exact_walk")
  owned=root/"own_fast_v2";disc=M.Discovery([dict(path=str(owned))],guard=lambda:None)
  result=list(disc.walk(root))
  assert {str(p) for p,_,_ in result}=={p for p,_,_ in plain if Path(p)!=owned and owned not in Path(p).parents}
  names.append("only_owned_paths_removed")
  assert list(disc.paths([root/"unknown_fast_v2/MANIFEST.json"]))==[root/"unknown_fast_v2/MANIFEST.json"]
  names.append("unlisted_fast_manifest_remains_visible")
 sources=M.sources()
 for mod in (M.B,M.V3,M.V4,M.V5,M.V6):
  assert bind(Path(mod.__file__))["sha256"]==M.LEGACY_PINS[Path(mod.__file__).name]
 names.append("all_legacy_exact_pins_and_import_paths")
 output=Path(output);assert not output.exists();output.mkdir(parents=True)
 receipt=dict(schema="s6c.inventory_refresh_independent_review.v1",status="PASS_SOURCE_AND_TINY_FIXTURES_ONLY",
  checks=len(names),names=names,inherited_checks=46,inherited_receipt=bind(M.REPORT/"independent_review/inventory_refresh_design_v1/inherited_checks/SOURCE_CHECKS.json"),
  sources=sources+[bind(HERE/"test_s6c_inventory_refresh_design_v1.py"),bind(HERE/"README_TEST_S6C_INVENTORY_REFRESH_DESIGN_V1.md"),bind(Path(M.B.__file__))],
  findings=[],scope=[
   "Seven complete function ASTs match after reversing only each explicit discovery wrapper and retaining the pre-existing sentinel literal map.",
   "No mutation of original module bindings; original receipt normalization and finite-owner behavior remain in private contexts.",
   "Only exact V7-admitted owned roots can be excluded. Historical global payload_root remains visible; unlisted fast-looking and offline trees are not suffix-filtered.",
   "Late pool closure/result/index references are coverage checks against fresh physical enumeration, not new attempts. Missing references remain outer flags.",
   "Fresh legacy and V7 append receipts must be interpreted with the outer refresh receipt; no final census or scientific acceptance is certified here."],
  actual_inventory_runs=0,actual_authorizations_created=0,models=0,actual_output_tree_reads=0)
 out=output/"REVIEW_RECEIPT.json";out.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8");print(json.dumps(bind(out),indent=2))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",required=True);run(p.parse_args().output)

