"""
Distancing-aware lexical scorer (D7).

Reference implementation of the symmetric plain/qualified scoring rule. For each
ideologically loaded term occurrence, the sentence is checked for an explicit
distancing signal; an article counts as a left- or right-signal only when plain
uses outnumber qualified uses for that side. The outlet score is

    D7_raw = (n_right_signal - n_left_signal) / (n_right_signal + n_left_signal)

over articles clearing a ten-signal-article floor.

Distancing signals, all sentence-local and explicit:

  1. the term falls inside a guillemet span
  2. the term falls inside ASCII or curly quotes
  3. the term sits under an unclosed guillemet opened earlier in the sentence
  4. the term follows a colon-plus-quote attribution
  5. a distancing prefix appears in the sentence
  6. side-specific critique vocabulary appears in the sentence

Reported speech alone is not a distancing signal. Term lists, distancing
prefixes and critique vocabulary are defined in `d7_terms.py`.

Input is a JSONL file with one article per line, carrying at least
`outlet_json_name`, `headline` and `article_body_clean`. The article corpus is
third-party copyrighted and is not distributed with this package; the scored
outputs it produced are shipped under `results/` instead.

Usage:
  python3 d7_score.py --input corpus.jsonl --endorsed
  python3 d7_score.py --input a.jsonl --input b.jsonl --endorsed   # + pooled mean

Output columns match the shipped `results/d5_score_*.csv` files. The `d5_`
prefix and the `d5_raw` column are retained from an earlier family numbering;
they denote D7 throughout.
"""

import argparse
import csv
import json
import math
import re
import time
from collections import defaultdict
from pathlib import Path

from d7_terms import (
    COMPILED,
    _DIST_PREFIX_RE,
    _DIST_CRITIQUE_RE,
    _DIST_LEFT_CRITIQUE_RE,
)

MIN_SIGNAL_ARTICLES = 10

_COLON_QUOTE_RE = re.compile(r'(?::\s*["“‘«])')
_QUOTE_OPEN = re.compile(r'["“‘]')
_QUOTE_CLOSE = re.compile(r'["”’]')
_HEADER_LEAD_RE = re.compile(r'\b(débat|sujet|titre|thème|rubrique)\s*$', re.I)


# ── Distancing checks ─────────────────────────────────────────────────────────

def _has_colon_quote_attribution(text: str, term: str) -> bool:
    """True when the term follows a colon-plus-quote within 100 characters.

    A section header such as "débat :" is not an attribution and is excluded.
    """
    m = _COLON_QUOTE_RE.search(text)
    if not m:
        return False
    if term.lower().strip() not in text[m.end():m.end() + 100].lower():
        return False
    return not _HEADER_LEAD_RE.search(text[max(0, m.start() - 30):m.start()].strip())


def _term_in_guillemets(text: str, start: int, end: int) -> bool:
    """True when the span [start, end) lies inside a guillemet pair."""
    before, after = text[:start], text[end:]
    lo = before.rfind('«')
    if lo < 0 or after.find('»') < 0:
        return False
    between = text[lo:start]
    if between.count('»') > between.count('«'):
        return before[:lo].rfind('«') >= 0
    return True


def _term_in_quotes(text: str, start: int, end: int) -> bool:
    """True when the span [start, end) is tightly wrapped in ASCII or curly quotes."""
    for m in _QUOTE_OPEN.finditer(text[:start]):
        if start - m.start() <= 1:
            cm = _QUOTE_CLOSE.search(text[end:])
            if cm is not None and cm.start() <= 1:
                return True
    return False


def _has_unclosed_guillemet(text: str, start: int) -> bool:
    """True when a guillemet opens within 150 characters before the term and never closes.

    Catches quotations that run across sentence boundaries.
    """
    lo = text.rfind('«', 0, start)
    if lo < 0 or start - lo > 150:
        return False
    return text[lo:start].find('»') < 0


def _get_sentence(text: str, match_start: int, match_end: int) -> str:
    """Return the sentence containing a match, extended through a closing guillemet.

    Sentence splitting on punctuation alone can cut inside a quotation; when the
    match sits under a guillemet that closes later, the span is extended to it.
    """
    before, after = text[:match_start], text[match_end:]
    sb = max(before.rfind('. '), before.rfind('? '),
             before.rfind('! '), before.rfind('\n'))
    ends = [after.find(x) + match_end for x in ('. ', '? ', '! ', '\n') if after.find(x) >= 0]
    se = min(ends) if ends else len(text)

    sent_start = sb + 2 if sb >= 0 else 0
    lo = text[sent_start:match_start].rfind('«')
    if lo >= 0:
        abs_lo = sent_start + lo
        fi = text[abs_lo + 1:abs_lo + 501].find('»')
        if fi >= 0 and abs_lo + 1 + fi > se:
            se = abs_lo + 1 + fi

    return text[sent_start:se + 2].strip()


def _occurrence_distanced(sentence: str, term: str, group: str) -> bool:
    """True when this occurrence carries an explicit distancing signal.

    Every occurrence of the term in the sentence is checked, not only the first.
    """
    if len(sentence) < 10:
        return True
    for m in re.finditer(re.escape(term), sentence, re.IGNORECASE):
        s, e = m.start(), m.end()
        if (_term_in_guillemets(sentence, s, e)
                or _term_in_quotes(sentence, s, e)
                or _has_unclosed_guillemet(sentence, s)
                or _has_colon_quote_attribution(sentence, m.group())):
            return True
    if _DIST_PREFIX_RE.search(sentence):
        return True
    critique_re = _DIST_CRITIQUE_RE if group == "right" else _DIST_LEFT_CRITIQUE_RE
    return bool(critique_re.search(sentence))


# ── Article scoring ───────────────────────────────────────────────────────────

def _score_group_endorsed(text: str, group: str) -> int:
    """Return 1 when plain uses outnumber qualified uses for this side."""
    plain = qualified = 0
    for pattern in COMPILED[group]:
        for m in pattern.finditer(text):
            sentence = _get_sentence(text, m.start(), m.end())
            if _occurrence_distanced(sentence, m.group(), group):
                qualified += 1
            else:
                plain += 1
    return 1 if plain > qualified else 0


def score_text_endorsed(text: str) -> dict:
    """Symmetric plain/qualified scoring for one article.

    Returns {"left": 0/1, "right": 0/1}: a side fires only when its plain uses
    outnumber its qualified uses.
    """
    if not text:
        return {"left": 0, "right": 0}
    return {"left": _score_group_endorsed(text, "left"),
            "right": _score_group_endorsed(text, "right")}


def score_text(text: str) -> dict:
    """Bag-of-words baseline: a side fires on any term match, distancing ignored."""
    if not text:
        return {"left": 0, "right": 0}
    return {group: 1 if any(p.search(text) for p in patterns) else 0
            for group, patterns in COMPILED.items()}


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_records(records: list, endorsed: bool = False) -> dict:
    """Aggregate scored articles into per-outlet statistics.

    Outlets below MIN_SIGNAL_ARTICLES signal articles receive a null score.
    """
    stats_by_outlet = defaultdict(
        lambda: {"n_articles": 0, "n_left": 0, "n_right": 0, "n_both": 0})

    for rec in records:
        text = (rec.get("headline") or "") + " " + (rec.get("article_body_clean") or "")
        if len(text.strip()) < 20:
            continue
        flags = score_text_endorsed(text) if endorsed else score_text(text)

        stats = stats_by_outlet[rec["outlet_json_name"]]
        stats["n_articles"] += 1
        stats["n_left"] += flags["left"]
        stats["n_right"] += flags["right"]
        if flags["left"] and flags["right"]:
            stats["n_both"] += 1

    for stats in stats_by_outlet.values():
        total = stats["n_left"] + stats["n_right"]
        stats["d5_raw"] = ((stats["n_right"] - stats["n_left"]) / total
                           if total >= MIN_SIGNAL_ARTICLES else None)
        n = stats["n_articles"]
        stats["left_pct"] = round(100 * stats["n_left"] / n, 1) if n else 0
        stats["right_pct"] = round(100 * stats["n_right"] / n, 1) if n else 0

    return dict(stats_by_outlet)


# ── Reporting ─────────────────────────────────────────────────────────────────

def load_reference_scores() -> dict:
    """Load full-model scores for an optional rank correlation, if present."""
    path = Path(__file__).resolve().parent.parent / "results" / "scores_v2.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {r["outlet"]: float(r["final_score_z"]) for r in rows if r.get("final_score_z")}


def spearman_rho(x: list, y: list) -> float:
    def rank(values):
        ordered = sorted(enumerate(values), key=lambda t: t[1])
        ranks = [0] * len(values)
        for position, (index, _) in enumerate(ordered, 1):
            ranks[index] = position
        return ranks

    n = len(x)
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((r - mx) ** 2 for r in rx))
    dy = math.sqrt(sum((r - my) ** 2 for r in ry))
    return num / (dx * dy) if dx and dy else float("nan")


def print_table(outlet_stats: dict, reference: dict):
    scored = [(name, s) for name, s in outlet_stats.items() if s["d5_raw"] is not None]
    if not scored:
        print("  No outlet cleared the signal-article floor.")
        return

    comparable = [(n, s) for n, s in scored if n in reference]
    if comparable:
        rho = spearman_rho([s["d5_raw"] for _, s in comparable],
                           [reference[n] for n, _ in comparable])
        print(f"\n  D7 vs full model: Spearman rho = {rho:.4f} (n={len(comparable)})")

    print(f"  {'-' * 62}")
    print(f"  {'Outlet':<22} {'D7 raw':>8} {'articles':>10}  {'L%':>5}  {'R%':>5}")
    print(f"  {'-' * 62}")
    for name, s in sorted(scored, key=lambda x: x[1]["d5_raw"]):
        print(f"  {name:<22} {s['d5_raw']:>+8.3f} {s['n_articles']:>10,}"
              f"  {s['left_pct']:>4.1f}%  {s['right_pct']:>4.1f}%")

    below = [n for n, s in outlet_stats.items() if s["d5_raw"] is None]
    if below:
        print(f"\n  Below the {MIN_SIGNAL_ARTICLES}-signal-article floor: {', '.join(sorted(below))}")


def save_csv(outlet_stats: dict, path: Path, period_label: str):
    if not outlet_stats:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["outlet_json_name", "period", "n_articles", "n_left_signal",
                  "n_right_signal", "n_both_signal", "left_pct", "right_pct", "d5_raw"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for name, s in sorted(outlet_stats.items()):
            writer.writerow({
                "outlet_json_name": name,
                "period": period_label,
                "n_articles": s["n_articles"],
                "n_left_signal": s["n_left"],
                "n_right_signal": s["n_right"],
                "n_both_signal": s["n_both"],
                "left_pct": s["left_pct"],
                "right_pct": s["right_pct"],
                "d5_raw": s["d5_raw"],
            })
    print(f"  Saved: {path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def pool(all_stats: dict) -> dict:
    """Pool per-input statistics, averaging the score across inputs that scored an outlet."""
    pooled = defaultdict(lambda: {"n_articles": 0, "n_left": 0, "n_right": 0, "n_both": 0})
    scores = defaultdict(list)
    for stats in all_stats.values():
        for name, s in stats.items():
            p = pooled[name]
            for key in ("n_articles", "n_left", "n_right", "n_both"):
                p[key] += s[key]
            if s["d5_raw"] is not None:
                scores[name].append(s["d5_raw"])

    for name, p in pooled.items():
        p["d5_raw"] = sum(scores[name]) / len(scores[name]) if scores[name] else None
        n = p["n_articles"]
        p["left_pct"] = round(100 * p["n_left"] / n, 1) if n else 0
        p["right_pct"] = round(100 * p["n_right"] / n, 1) if n else 0
    return dict(pooled)


def main():
    parser = argparse.ArgumentParser(
        description="Distancing-aware lexical scorer (D7).")
    parser.add_argument("--input", type=Path, action="append", required=True,
                        help="JSONL corpus file; repeat to score several and pool them")
    parser.add_argument("--endorsed", action="store_true",
                        help="apply the distancing check (omit for the bag-of-words baseline)")
    parser.add_argument("--outdir", type=Path, default=Path.cwd(),
                        help="directory for the per-input CSV files (default: cwd)")
    args = parser.parse_args()

    reference = load_reference_scores()
    suffix = "_endorsed" if args.endorsed else ""
    all_stats = {}

    for path in args.input:
        if not path.exists():
            print(f"ERROR: {path} not found.")
            continue
        label = path.stem
        print(f"\n[{label}]")
        print(f"  Loading {path.name} ...", end=" ", flush=True)
        t0 = time.time()
        records = load_jsonl(path)
        print(f"{len(records):,} records ({time.time() - t0:.1f}s)")

        print(f"  Scoring [{'plain/qualified' if args.endorsed else 'bag-of-words'}] ...",
              end=" ", flush=True)
        t0 = time.time()
        stats = aggregate_records(records, endorsed=args.endorsed)
        print(f"({time.time() - t0:.1f}s)")

        all_stats[label] = stats
        print_table(stats, reference)
        save_csv(stats, args.outdir / f"d5_score_{label}{suffix}.csv", label)

    if len(all_stats) > 1:
        print(f"\n{'=' * 62}\n  POOLED\n{'=' * 62}")
        pooled = pool(all_stats)
        print_table(pooled, reference)
        save_csv(pooled, args.outdir / f"d5_score_pooled{suffix}.csv", "pooled")


if __name__ == "__main__":
    main()
