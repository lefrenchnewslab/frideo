#!/usr/bin/env python3
"""
Score the D7 gold standard.

Run from this directory once adjudication_sheet_BLIND.csv is filled:
    python3 score_gold.py

Reports kappa(D7, gold) and kappa(LLM, gold) BOTH over the full set and over
the human-adjudicated rows only. The second number is the honest one: on
auto-gold rows the gold IS D7's own output, so agreement there is definitional.
"""
import csv, sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10 ** 7)
HERE = Path(__file__).resolve().parent


def kappa(pairs):
    n = len(pairs)
    if not n:
        return float("nan"), float("nan"), 0
    cats = sorted({x for p in pairs for x in p})
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, b in pairs), Counter(b for a, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    return ((po - pe) / (1 - pe) if pe < 1 else float("nan")), po, n


def rows(name):
    p = HERE / name
    if not p.exists():
        sys.exit(f"missing {name}")
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


sheet = {r["item_id"]: r for r in rows("adjudication_sheet_BLIND.csv")}
key = {r["item_id"]: r for r in rows("adjudication_KEY.csv")}
reuse = rows("reusable_prior_adjudications.csv")
auto = rows("autogold_no_action.csv")

gold = []      # (d7, llm, gold_label, source)

# De-duplicate the auto rows. `autogold_no_action.csv` carries 313 rows but only
# 312 distinct item_ids: IT27f3d084aa appears twice, because the sample holds one
# `justice sociale` occurrence (article 2411849, records 4059/4056) twice with
# identical sentence, term and labels. Without this the script would report 431
# rows against the released file's 430.
# (kappa is unchanged to 3 d.p. either way, but the counts must not disagree.)
_seen_auto = set()
for r in auto:                                    # gold by construction
    if r["item_id"] in _seen_auto:
        continue
    _seen_auto.add(r["item_id"])
    gold.append((r["agreed_label"], r["agreed_label"], r["agreed_label"], "auto"))

# Round-2 re-adjudications supersede the carried-over labels where present.
r2 = {}
p2, k2 = HERE / "adjudication_sheet_ROUND2_BLIND.csv", HERE / "adjudication_KEY_ROUND2.csv"
if p2.exists() and k2.exists():
    for s in rows("adjudication_sheet_ROUND2_BLIND.csv"):
        lbl = (s["your_label_PLAIN_or_QUALIFIED"] or "").strip().upper()
        if lbl in ("PLAIN", "QUALIFIED"):
            r2[s["item_id"]] = lbl

for r in reuse:
    if r["item_id"] in r2:                        # refreshed under the current rule
        gold.append((r["new_d7"], r["llm_label"], r2[r["item_id"]], "human_new"))
    else:                                         # carried over unchanged
        gold.append((r["new_d7"], r["llm_label"], r["prior_gold_label"], "human_prior"))

missing = 0
for i, s in sheet.items():
    lbl = (s["your_label_PLAIN_or_QUALIFIED"] or "").strip().upper()
    if lbl not in ("PLAIN", "QUALIFIED"):
        missing += 1
        continue
    k = key[i]
    gold.append((k["new_d7"], k["llm_label"], lbl, "human_new"))

print(f"\nComposed gold: {len(gold)} rows"
      f"   (auto {sum(1 for g in gold if g[3]=='auto')},"
      f" prior {sum(1 for g in gold if g[3]=='human_prior')},"
      f" new {sum(1 for g in gold if g[3]=='human_new')})")
if missing:
    print(f"  {missing} sheet rows still blank or UNCERTAIN — excluded")

# Guard: the set composed here must match the released gold row for row.
_canonical = HERE / ".." / ".." / "results" / "exp_a" / "exp_a_gold_430.csv"
if _canonical.exists():
    with open(_canonical, newline="", encoding="utf-8") as f:
        _n = sum(1 for _ in csv.DictReader(f))
    if _n != len(gold):
        sys.exit(f"FATAL: {len(gold)} rows composed here vs {_n} in "
                 f"exp_a_gold_430.csv — the sources and the released gold disagree.")
    print(f"  agrees with exp_a_gold_430.csv ({_n} rows)")

human = [g for g in gold if g[3] != "auto"]

print("\n--- full set (inflated: auto rows are D7's own output) ---")
for nm, idx in (("D7  vs gold", 0), ("LLM vs gold", 1)):
    k, po, n = kappa([(g[idx], g[2]) for g in gold])
    print(f"  {nm}: kappa={k:.3f}  agreement={po:.1%}  n={n}")

print("\n--- human-adjudicated rows only (the honest number) ---")
for nm, idx in (("D7  vs gold", 0), ("LLM vs gold", 1)):
    k, po, n = kappa([(g[idx], g[2]) for g in human])
    print(f"  {nm}: kappa={k:.3f}  agreement={po:.1%}  n={n}")

print()
