"""Generate one answer per (model, task) with the server's exact call shape. Resumable."""
import json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
sys.path.insert(0, HERE)
import llmapi  # LLM_PROMPT (also imports api_key, which sets env vars; never printed)
from openai import OpenAI
from tasks import TASKS

MODELS = ["gpt-4.1", "gpt-5.2", "gpt-5.4", "gpt-5.4-mini", "gpt-5.5", "o3",
          "gpt-5.6-sol", "gpt-6-sol", "gpt-6.2-sol", "gpt-6.2-astra"]
OUT = os.path.join(HERE, "results", "gen.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=600, max_retries=1)
lock = threading.Lock()
results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}


def run(job):
    model, task = job
    key = f"{model}|{task}"
    if key in results and results[key].get("answer"):
        return
    t = time.time()
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": llmapi.LLM_PROMPT},
                      {"role": "user", "content": TASKS[task]["prompt"]}])  # no sampling params, like the server
        u = r.usage
        rec = {"model": model, "task": task, "answer": r.choices[0].message.content or "",
               "seconds": round(time.time() - t, 1), "out_tokens": u.completion_tokens,
               "reasoning_tokens": getattr(getattr(u, "completion_tokens_details", None), "reasoning_tokens", 0) or 0,
               "in_tokens": u.prompt_tokens}
    except Exception as e:
        rec = {"model": model, "task": task, "answer": "", "error": f"{type(e).__name__}: {str(e)[:200]}",
               "seconds": round(time.time() - t, 1)}
    with lock:
        results[key] = rec
        json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{key:28s} {rec['seconds']:6.1f}s  words={len(rec['answer'].split()):4d}  {rec.get('error','')}", flush=True)


jobs = [(m, t) for t in TASKS for m in MODELS]
with ThreadPoolExecutor(6) as ex:
    list(ex.map(run, jobs))
print("done:", sum(1 for v in results.values() if v.get("answer")), "of", len(jobs))
