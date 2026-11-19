"""Smoke test: which candidate models work with the server's exact call shape."""
import os, sys, time, json
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import api_key  # noqa: F401  (sets env vars; values are never printed)
from openai import OpenAI

CANDIDATES = ["gpt-4.1", "gpt-5.2", "gpt-5.4", "gpt-5.4-mini", "gpt-5.5", "o3",
              "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
              "gpt-6-luna", "gpt-6-sol", "gpt-6-astra", "gpt-6.1-terra", "gpt-6.1-sol",
              "gpt-6.2-astra", "gpt-6.2-sol"]

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=120, max_retries=0)


def probe(model):
    t = time.time()
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Du svarer kort på bokmål."},
                      {"role": "user", "content": "Svar kun med ordet: ok"}])
        u = r.usage
        rt = getattr(getattr(u, "completion_tokens_details", None), "reasoning_tokens", None)
        return model, True, f"{time.time()-t:.1f}s answer={r.choices[0].message.content!r} out={u.completion_tokens} reasoning={rt}"
    except Exception as e:
        return model, False, f"{time.time()-t:.1f}s {type(e).__name__}: {str(e)[:150]}"


with ThreadPoolExecutor(8) as ex:
    results = list(ex.map(probe, CANDIDATES))
for model, ok, msg in results:
    print(("OK   " if ok else "FAIL ") + f"{model:15s} {msg}")
