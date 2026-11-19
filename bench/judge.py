"""Blind numeric grading of every generated answer by two judge models. Resumable.

The judges get the project's own strict-examiner prompt (JUDGE_PROMPT) plus an instruction to
answer with JSON scores. They see the task and the answer only - never the model name.
"""
import json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
sys.path.insert(0, HERE)
import llmapi
from openai import OpenAI
from tasks import TASKS

JUDGES = ["gpt-5.5", "gpt-6.2-sol"]
GEN = os.path.join(HERE, "results", "gen.json")
OUT = os.path.join(HERE, "results", "judge.json")

ADDENDUM = """

TILLEGG FOR DENNE KJØRINGEN
Ikke skriv vurderingen som prosa. Svar KUN med gyldig JSON, uten kodeblokk og uten annen tekst, med nøyaktig disse feltene:
{"karakter": tall fra 1 til 6 med én desimal,
 "analysedybde": 1-6, "fagbegrep": 1-6, "konkretisering": 1-6, "rod_trad": 1-6, "forstaelse": 1-6,
 "tolkningsniva": 1-6, "form_innhold": 1-6, "selvstendighet": 1-6,
 "sprak": 1-6 (korrekt bokmål, flyt og variasjon),
 "oppgavetilpasning": 1-6 (svarer på oppgaven, passende lengde og form),
 "hovedsvakhet": "én setning"}
Vær like streng som en ekte sensor. Gi ikke 6 hvis du kan peke på en konkret svakhet."""

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=600, max_retries=1)
lock = threading.Lock()
gen = json.load(open(GEN, encoding="utf-8"))
results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else None


def run(job):
    judge, key = job
    jkey = f"{judge}|{key}"
    if jkey in results and results[jkey].get("scores"):
        return
    rec_g = gen[key]
    user = f"OPPGAVE (med eventuelt vedlegg):\n{TASKS[rec_g['task']]['prompt']}\n\nBESVARELSE:\n{rec_g['answer']}"
    scores, err = None, ""
    for attempt in range(2):
        try:
            r = client.chat.completions.create(
                model=judge,
                messages=[{"role": "system", "content": llmapi.JUDGE_PROMPT + ADDENDUM},
                          {"role": "user", "content": user}])
            scores = parse(r.choices[0].message.content or "")
            if scores:
                break
            err = "unparseable"
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:150]}"
    with lock:
        results[jkey] = {"judge": judge, "key": key, "scores": scores, "error": err}
        json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{jkey:42s} grade={scores.get('karakter') if scores else None} {err}", flush=True)


jobs = [(j, k) for k, v in gen.items() if v.get("answer") for j in JUDGES]
with ThreadPoolExecutor(6) as ex:
    list(ex.map(run, jobs))
print("done:", sum(1 for v in results.values() if v.get("scores")), "of", len(jobs))
