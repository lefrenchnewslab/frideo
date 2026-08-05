#!/usr/bin/env python3
"""Score the 100-item second-rater study. Run: python3 score_second_rater.py

Reads the returned sheet (second_rater_sheet_BLIND.csv) against the withheld
key (second_rater_KEY.csv) and reports agreement with the author gold and with
the D7 rule, broken out by stratum and term side.
"""
import csv
from collections import Counter
from pathlib import Path
csv.field_size_limit(10**7)
H=Path(__file__).resolve().parent

def kappa(p):
    n=len(p)
    if not n: return float("nan"),float("nan"),0
    c=sorted({x for q in p for x in q}); po=sum(1 for a,b in p if a==b)/n
    ca,cb=Counter(a for a,b in p),Counter(b for a,b in p)
    pe=sum((ca[x]/n)*(cb[x]/n) for x in c)
    return ((po-pe)/(1-pe) if pe<1 else float("nan")),po,n

sheet={r["item_id"]:r for r in csv.DictReader(open(H/"second_rater_sheet_BLIND.csv",encoding="utf-8"))}
key={r["item_id"]:r for r in csv.DictReader(open(H/"second_rater_KEY.csv",encoding="utf-8"))}
rows=[]
skip=0
for i,s in sheet.items():
    l=(s["your_label_PLAIN_or_QUALIFIED"] or "").strip().upper()
    if l not in ("PLAIN","QUALIFIED"): skip+=1; continue
    k=key[i]; rows.append((l,k["author_gold"],k["d7_label"],k["stratum"],k["side"]))
print(f"\nscored {len(rows)}/{len(sheet)}" + (f"  ({skip} blank/UNCERTAIN, excluded)" if skip else ""))
def blk(name,sub):
    if not sub: return
    a,pa,n=kappa([(r[0],r[1]) for r in sub]); b,pb,_=kappa([(r[0],r[2]) for r in sub])
    print(f"  {name:26s} n={n:3d}   vs author gold: k={a:.3f} ({pa:.1%})   vs D7: k={b:.3f} ({pb:.1%})")
print("\n--- inter-annotator agreement ---")
blk("ALL",rows)
blk("boundary (adjudicated)",[r for r in rows if r[3] in ("boundary","contested")])
blk("  of which CONTESTED",[r for r in rows if r[3]=="contested"])
blk("control (D7=LLM agreed)",[r for r in rows if r[3]=="control"])
blk("left terms",[r for r in rows if r[4]=="left"])
blk("right terms",[r for r in rows if r[4]=="right"])
ct=[r for r in rows if r[3]=="contested"]
if ct:
    sg=sum(1 for r in ct if r[0]==r[1]); sd=sum(1 for r in ct if r[0]==r[2])
    print(f"\n--- tie-break on the {len(ct)} contested rows (your gold != D7) ---")
    print(f"  rater sided with YOU: {sg}/{len(ct)}   with D7: {sd}/{len(ct)}")
nb=sum(1 for r in rows if r[3] in ("boundary","contested"))
print(f"\nNB: report boundary and control separately — the sample over-weights boundary")
print(f"    ({nb}/{len(rows)}) relative to the gold (118/430), so ALL is not representative.\n")
