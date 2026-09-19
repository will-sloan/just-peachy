"""Exact flat CSV export; README_S6C_EXECUTION_COVERAGE_CSV_V1.md."""
import argparse,csv,hashlib,io,json
from pathlib import Path
def digest(raw):return hashlib.sha256(raw).hexdigest()
def bound(p,raw):return dict(path=str(p.resolve()),bytes=len(raw),sha256=digest(raw))
def run(result,sha):
 p=Path(result).resolve();raw=p.read_bytes();assert digest(raw)==sha
 d=json.loads(raw);assert d["status"]=="COMPLETE_PHYSICAL_METADATA_PROJECTION_WITH_FLAGS"
 b=d["outputs"]["csv_matrix"];q=Path(b["path"]);buf=q.read_bytes();assert bound(q,buf)==b
 matrix=json.loads(buf);values=matrix["values"];assert len(values)==5892 and len(values[0])==len(set(values[0])) and all(len(x)==len(values[0]) for x in values)
 def cell(x):
  if x is None:return ""
  if isinstance(x,bool):return "true" if x else "false"
  return str(x)
 expected=[[cell(x) for x in row] for row in values];text=io.StringIO(newline="");w=csv.writer(text,lineterminator="\n");w.writerows(expected);csvraw=text.getvalue().encode("utf-8")
 assert list(csv.reader(io.StringIO(csvraw.decode())))==expected
 out=p.parent/"EXECUTION_COVERAGE.csv"
 with out.open("xb") as f:f.write(csvraw)
 rb=bound(out,csvraw);receipt=dict(status="COMPLETE_ALL_OBSERVED_EXECUTION_CSV_EXPORT",rows=5891,columns=len(values[0]),original_projection=bound(p,raw),matrix=b,output=rb,source=bound(Path(__file__),Path(__file__).read_bytes()),readme=bound(Path(__file__).with_name("README_S6C_EXECUTION_COVERAGE_CSV_V1.md"),Path(__file__).with_name("README_S6C_EXECUTION_COVERAGE_CSV_V1.md").read_bytes()),verification="All header and5891 row fields roundtrip exactly; null scalar blanks disambiguated by missing field bitmap and typed JSON source.",csv_export_capability="Artifact Tool public workbook.export offers xlsx/render; exact workbook.toCSV help returned no entry. Bundled Python standard CSV used for this flat machine export.",new_scoring_or_models=0)
 rp=p.parent/"CSV_EXPORT_RECEIPT.json"
 with rp.open("x",encoding="utf-8") as f:json.dump(receipt,f,indent=2);f.write("\n")
 print(json.dumps(bound(rp,rp.read_bytes())))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--result",nargs=2,required=True);a=p.parse_args();run(*a.result)

