"""Aggregate generation stats + judge scores per model and per task."""
import json, os, re, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, HERE)
from tasks import TASKS

gen = json.load(open(os.path.join(HERE, "results", "gen.json"), encoding="utf-8"))
jud = json.load(open(os.path.join(HERE, "results", "judge.json"), encoding="utf-8"))

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
def format_violations(a):
    n = 0
    n += bool(re.search(r"(?m)^\s*#", a))                 # headings
    n += "**" in a or "__" in a                           # bold
    n += bool(re.search(r"(?m)^\s*([-*•]|\d+[.)])\s", a)) # lists
    n += bool(re.search(r"(?m)^\s*(---|___)\s*$", a))     # rules
    n += "|" in a                                         # tables / pipes
    n += bool(EMOJI.search(a))
    return n

models = sorted({v["model"] for v in gen.values()}, key=lambda m: m)
JUDGES = sorted({v["judge"] for v in jud.values()})
CRIT = ["analysedybde", "fagbegrep", "konkretisering", "rod_trad", "forstaelse", "tolkningsniva", "form_innhold", "selvstendighet", "sprak", "oppgavetilpasning"]

def g(model, task, judge):
    r = jud.get(f"{judge}|{model}|{task}")
    return r["scores"] if r and r.get("scores") else None

rows = []
for m in models:
    recs = [gen[f"{m}|{t}"] for t in TASKS if f"{m}|{t}" in gen and gen[f"{m}|{t}"].get("answer")]
    row = {"model": m, "n": len(recs)}
    row["words_ok"] = sum(TASKS[r["task"]]["words"][0] * 0.9 <= len(r["answer"].split()) <= TASKS[r["task"]]["words"][1] * 1.1 for r in recs)
    row["avg_words"] = round(st.mean(len(r["answer"].split()) for r in recs)) if recs else 0
    row["quotes"] = round(st.mean(r["answer"].count("«") for r in recs), 1) if recs else 0
    row["fmt_viol"] = sum(format_violations(r["answer"]) for r in recs)
    row["sec"] = round(st.mean(r["seconds"] for r in recs), 1) if recs else 0
    row["out_tok"] = round(st.mean(r["out_tokens"] for r in recs)) if recs else 0
    row["reason_tok"] = round(st.mean(r["reasoning_tokens"] for r in recs)) if recs else 0
    for j in JUDGES:
        vals = [g(m, t, j)["karakter"] for t in TASKS if g(m, t, j)]
        row[j] = round(st.mean(vals), 2) if vals else None
    sub = defaultdict(list)
    for j in JUDGES:
        for t in TASKS:
            s = g(m, t, j)
            if s:
                for c in CRIT:
                    if isinstance(s.get(c), (int, float)): sub[c].append(s[c])
    row["subs"] = {c: round(st.mean(v), 2) for c, v in sub.items() if v}
    vals = [row[j] for j in JUDGES if row[j] is not None]
    row["mean"] = round(st.mean(vals), 2) if vals else None
    rows.append(row)

rows.sort(key=lambda r: -(r["mean"] or 0))
print(f"{'model':14s} " + " ".join(f"{j:>12s}" for j in JUDGES) + "    mean | words(avg, in-range) quotes fmt  sec  outtok reasoning")
for r in rows:
    print(f"{r['model']:14s} " + " ".join(f"{(r[j] if r[j] is not None else float('nan')):12.2f}" for j in JUDGES)
          + f"  {(r['mean'] or 0):6.2f} | {r['avg_words']:5d} {r['words_ok']}/{r['n']}   {r['quotes']:6.1f} {r['fmt_viol']:3d} {r['sec']:5.1f} {r['out_tok']:6d} {r['reason_tok']:6d}")

print("\nPer-task mean grade (avg of both judges):")
print(f"{'model':14s} " + " ".join(f"{t:>9s}" for t in TASKS))
for r in rows:
    cells = []
    for t in TASKS:
        v = [g(r['model'], t, j)["karakter"] for j in JUDGES if g(r['model'], t, j)]
        cells.append(f"{st.mean(v):9.2f}" if v else f"{'-':>9s}")
    print(f"{r['model']:14s} " + " ".join(cells))

print("\nCriteria means (both judges, all tasks):")
print(f"{'model':14s} " + " ".join(f"{c[:8]:>8s}" for c in CRIT))
for r in rows:
    print(f"{r['model']:14s} " + " ".join(f"{r['subs'].get(c, float('nan')):8.2f}" for c in CRIT))

# judge agreement
pairs = [(g(m, t, JUDGES[0])["karakter"], g(m, t, JUDGES[1])["karakter"]) for m in models for t in TASKS if len(JUDGES) > 1 and g(m, t, JUDGES[0]) and g(m, t, JUDGES[1])]
if len(pairs) > 3:
    xs, ys = zip(*pairs)
    mx, my = st.mean(xs), st.mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    corr = cov / (sum((x - mx) ** 2 for x in xs) ** .5 * sum((y - my) ** 2 for y in ys) ** .5 or 1)
    print(f"\nJudge agreement: correlation {corr:.2f} over {len(pairs)} answers; mean grades {JUDGES[0]}={mx:.2f} {JUDGES[1]}={my:.2f}")
