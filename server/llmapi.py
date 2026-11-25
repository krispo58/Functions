import os
import re
from pathlib import Path
import api_key
from openai import OpenAI

# The answer-writer prompt lives in its own file so it is easy to edit.
LLM_PROMPT = (Path(__file__).parent / "rettslare_prompt.txt").read_text(encoding="utf-8")
JUDGE_PROMPT = (Path(__file__).parent / "judge_prompt_rettslare.txt").read_text(encoding="utf-8")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3.5-super-vl:free"
DEFAULT_OPENAI_MODEL = "gpt-6.2-sol"
LLM_TIMEOUT_SECONDS = 120  # per attempt; bounds how long one request can block the server
# OpenAI answers do many web searches before writing, so they need far longer.
OPENAI_TIMEOUT_SECONDS = 900
MAX_TOOL_CALLS = 60  # cap on web searches/page reads per OpenAI request


class LLM:
    """
    Chat wrapper with two providers:
      - OpenAI (default)
      - OpenRouter, through its OpenAI-compatible API (also the fallback)
    Keeps separate histories for the essay writer and the judge.
    """

    def __init__(self, openrouter_model: str = DEFAULT_OPENROUTER_MODEL,
                 openai_model: str = DEFAULT_OPENAI_MODEL):
        # Explicit timeouts: the SDK default is 10 minutes x 2 retries, and the
        # server handles one request at a time, so one stuck call would make the
        # whole server look dead.
        self.openrouter_client = OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY") or "missing",
            base_url=OPENROUTER_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=1,
        )
        # A missing OpenAI key must not stop the server from starting;
        # the call will just fail and fall back to OpenRouter.
        self.openai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY") or "missing",
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=0,  # a retried 15-minute request is not worth it; _run falls back instead
        )

        self.openrouter_model = openrouter_model
        self.openai_model = openai_model
        self.use_openai = True  # OpenAI is the default
        self.last_sources = []  # URLs consulted by the last OpenAI web search

        # Internal histories (OpenAI chat format)
        self.messages = []
        self.judge_messages = []
        self.reset_chat_history()
        self.reset_judge_history()

    @property
    def provider_name(self) -> str:
        return "OpenAI" if self.use_openai else "OpenRouter"

    def reset_chat_history(self):
        # Starts history with the system prompt
        self.messages = [{"role": "system", "content": LLM_PROMPT}]

    def reset_judge_history(self):
        # Starts judge history with the judge system prompt
        self.judge_messages = [{"role": "system", "content": JUDGE_PROMPT}]

    @staticmethod
    def _clean_answer(text: str) -> str:
        """
        The web search tool makes the model add inline citations such as
        ([lovdata.no](https://...?utm_source=openai)). The answer must be plain
        text, so remove them (the URLs are kept in last_sources instead).
        """
        text = re.sub(r"[ \t]*\(\[[^\]]*\]\([^)]*\)\)", "", text)  # ([name](url))
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)       # [text](url) -> text
        return text.strip()

    @staticmethod
    def _log_actions(response):
        """
        Log what the web search tool actually did: search (query), open_page
        (whole page opened) or find_in_page (only a search inside a page).
        """
        counts = {}
        lines = []
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", "") != "web_search_call":
                continue
            action = getattr(item, "action", None)
            kind = getattr(action, "type", "?")
            counts[kind] = counts.get(kind, 0) + 1
            detail = (getattr(action, "query", None) or getattr(action, "url", None) or "")
            pattern = getattr(action, "pattern", None)
            if pattern:
                detail = f"{detail}  [find: {pattern}]"
            lines.append(f"  {kind}: {detail}")
        if lines:
            print("Web search actions:", counts)
            print("\n".join(lines))

    @staticmethod
    def _extract_sources(response) -> list:
        """URLs the web search consulted or cited, de-duplicated."""
        urls = []

        def add(url):
            if url and url not in urls:
                urls.append(url)

        for item in getattr(response, "output", None) or []:
            kind = getattr(item, "type", "")
            if kind == "web_search_call":
                action = getattr(item, "action", None)
                for src in getattr(action, "sources", None) or []:
                    add(getattr(src, "url", None))
            elif kind == "message":
                for part in getattr(item, "content", None) or []:
                    for ann in getattr(part, "annotations", None) or []:
                        if getattr(ann, "type", "") == "url_citation":
                            add(getattr(ann, "url", None))
        return urls

    def _ask(self, history: list, content: str, use_openai: bool) -> str:
        """
        Send `content` with the given history to one provider. No sampling
        parameters (temperature, top_p) are sent: some models reject them.
        On success the exchange is added to `history`; on any failure the
        history is left untouched and the exception is re-raised.
        """
        history.append({"role": "user", "content": content})
        try:
            if use_openai:
                # Responses API with web search. Which sites may be used is set
                # in the system prompt, not by a domain filter.
                response = self.openai_client.responses.create(
                    model=self.openai_model,
                    input=history,
                    tools=[{"type": "web_search"}],
                    tool_choice="auto",
                    max_tool_calls=MAX_TOOL_CALLS,
                    include=["web_search_call.action.sources"],
                )
                answer = self._clean_answer(response.output_text)
                self.last_sources = self._extract_sources(response)
                self._log_actions(response)
                if self.last_sources:
                    print("Sources consulted:", *self.last_sources, sep="\n  ")
            else:
                response = self.openrouter_client.chat.completions.create(
                    model=self.openrouter_model, messages=history)
                answer = response.choices[0].message.content
                self.last_sources = []
            if not answer:
                raise ValueError("The model returned an empty response")
            history.append({"role": "assistant", "content": answer})
            return answer
        except Exception:
            history.pop()  # don't leave an unanswered user turn behind
            raise

    def _run(self, history: list, content: str) -> str:
        """Ask the selected provider; if OpenAI fails, fall back to OpenRouter."""
        prefix = ""
        if self.use_openai:
            try:
                return self._ask(history, content, use_openai=True)
            except Exception as e:
                print(f"OpenAI Error (Context issue or Rate Limit): {e}. Falling back to OpenRouter.")
                self.use_openai = False
                prefix = "OpenAI Error. Falling back to OpenRouter.\n\n"

        try:
            return prefix + self._ask(history, content, use_openai=False)
        except Exception as e:
            print(f"OpenRouter Error: {e}")
            return f"{prefix}OpenRouter Error: {e}"

    def toggle_llm(self) -> str:
        """Toggle between OpenRouter and OpenAI."""
        self.use_openai = not self.use_openai
        return f"Switched to {self.provider_name}"

    def prompt(self, content: str) -> str:
        print("Prompting... Current provider: ", self.provider_name)
        return self._run(self.messages, content)

    def judge(self, content: str) -> str:
        """Send content to judge using separate judge history."""
        print("Judging... Current provider: ", self.provider_name)
        return self._run(self.judge_messages, content)
