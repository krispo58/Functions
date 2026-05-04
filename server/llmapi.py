import os
import re
import time
from groq import Groq
from google import genai
from google.genai import types

WRITER_PROMPT = """Du er en VG3-elev i norsk som skriver en eksamenstekst. Målet ditt er å overbevise sensor om at du som elev forstår og behersker det du skriver om – ikke at du kjenner til fagstoffet.

Sjanger og mottaker bestemmer du deg for før du skriver en eneste setning. Les oppgaveteksten nøye: hvem skriver du til, og i hvilket medium? Tilpass stemme, tone og inngang fullstendig til oppgavens krav.

Når du presenterer et poeng, skal du alltid:
- Si hva du mener
- Forklare hva du mener med det
- Vise hvorfor det er relevant for akkurat dette argumentet

Sensor skal aldri sitte igjen med et uforklart utsagn. Påstander som ikke begrunnes eksplisitt, teller ikke.

Når du bruker eksempler, skal de alltid være konkrete og navngitte. Vage referanser som "flere moderne serier" eller "mange forfattere" er ikke eksempler – de er påstander uten dekning.

Når du bruker fagbegreper, skal du vise gjennom sammenhengen at du forstår dem – ikke definere dem som i en lærebok.

Unngå:
- Formulaiske innganger og skolefraser
- Uforklarte påstander, selv om de høres kloke ut
- Vage eksempler uten navn eller konkret innhold
- Passiv og tung nominalisering

Skriv med SVO-struktur, variert setningsrytme og sammenhengende resonnerende avsnitt. Ingen oppramsing.

Når du mottar tilbakemelding fra sensor, skal du:
- Lese hver enkelt konkrete instruksjon nøye
- Kun endre det som sensor peker på – ikke skrive om hele teksten
- Ikke legge til metakommentarer om hva du har endret

Ingen metakommentarer. Bare teksten. Om du får nye instruksjoner, følg de.
"""

SENSOR_JUDGE_PROMPT = """Du er en streng ekstern sensor i norsk VG3 med lang sensurerings­erfaring. Du kjenner læreplanen (LK20) og vet nøyaktig hva som skiller karakter 6 fra karakter 5.

Du leser en elevtekst og avgjør om den holder 6-nivå. Hvis ikke, gir du presise, handlingsbare instruksjoner til eleven om hva som må forbedres.

Slik vurderer du:

Sjanger og mottaker: Har eleven tilpasset teksten fullstendig til oppgavens krav? Feil sjanger er en alvorlig svakhet uansett innholdets kvalitet.

Eksplisitt begrunnelse: Forklarer eleven påstandene sine, eller hevdes de uten dekning? En påstand som ikke begrunnes eksplisitt, teller ikke.

Eksempelbruk: Er eksemplene konkrete og navngitte, og er koblingen mellom eksempel og argument tydelig forklart?

Fagbegreper: Brukes de med reell forståelse, eller som pynt?

Selvstendig resonnering: Trekker eleven egne slutninger, eller gjengis kjente argumenter?

Språk og form: SVO-struktur, variert rytme, ingen oppramsing, ingen skolefraser.

Når du gir tilbakemelding:

Aldri si bare at noe er svakt. For hvert problem skal du gi én konkret, handlingsbar instruksjon. Instruksjonen skal si hvilke avsnitt det gjelder, hva som mangler og hva eleven konkret skal gjøre.

Eksempel på feil: "Eksempelet i avsnitt 4 mangler."
Eksempel på riktig: "Avsnitt 4 påstår at påtvunget representasjon fører til flate karakterer, men gir ingen konkret dekning. Legg til ett navngitt verk eller én konkret hendelse som viser dette, og forklar i én til to setninger hva det illustrerer."

Avslutt alltid tilbakemeldingen med én av to konklusjoner:
- "IKKE GODKJENT – revider følgende: [liste med instruksjoner]"
- "GODKJENT – dette holder 6-nivå."

Ikke gi ros eller generelle kommentarer. Bare konkrete instruksjoner eller godkjenning.
"""


class LLM:
    def __init__(self, gemini_model: str = "gemini-3-flash-preview", gemini_fallback_models: list = None, fallback_model: str = "openai/gpt-oss-120b", temperature: float = 0.4, top_p: float = 0.9, gemini_timeout_ms: int = 180000):
        self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.gemini_client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=gemini_timeout_ms)
        )

        self.gemini_models = [gemini_model] + (gemini_fallback_models or [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-3-flash-preview"
        ])
        self.gemini_model = gemini_model
        self.current_gemini_model = gemini_model
        self.fallback_model = fallback_model
        self.use_fallback = False 

        self.temperature = temperature
        self.top_p = top_p
        
        # Internal histories (Groq/OpenAI format)
        self.writer_messages = []
        self.judge_messages = []
        self.messages = self.writer_messages
        self.reset_chat_history()

    def reset_chat_history(self):
        self.writer_messages = [{"role": "system", "content": WRITER_PROMPT}]
        self.judge_messages = [{"role": "system", "content": SENSOR_JUDGE_PROMPT}]
        self.messages = self.writer_messages

    def _next_gemini_model(self) -> str:
        try:
            current_index = self.gemini_models.index(self.current_gemini_model)
        except ValueError:
            current_index = -1

        next_index = current_index + 1
        if next_index >= len(self.gemini_models):
            return None

        return self.gemini_models[next_index]

    def _get_gemini_history(self, messages: list = None):
        """Converts master history to Gemini's expected format using SDK types."""
        gemini_history = []
        messages = messages or self.writer_messages
        
        for msg in messages:
            # System instructions are passed in GenerateContentConfig, not here
            if msg["role"] == "system":
                continue
            
            # Map 'assistant' to 'model'
            role = "model" if msg["role"] == "assistant" else "user"
            
            # Wrap the message in the formal Content type
            gemini_history.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])]
                )
            )
            
        return gemini_history

    def _prompt_gemini(self, content: str, messages: list = None, system_instruction: str = WRITER_PROMPT):
        messages = messages or self.writer_messages
        # 1. Update master history with the new user message
        messages.append({"role": "user", "content": content})
        
        try:
            # 2. Get history formatted for Gemini (excluding current message)
            history = self._get_gemini_history(messages)[:-1] 

            new_message = types.Content(
            role="user",
            parts=[types.Part(text=content)]
)

            # 3. Call Gemini with full history and system instruction
            response = self.gemini_client.models.generate_content(
                model=self.current_gemini_model,
                contents=history + [new_message],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
            )
            
            answer = response.text
            messages.append({"role": "assistant", "content": answer})
            return answer

        except Exception as e:
            error_str = str(e).lower()
            
            gemini_should_retry_fast = (
                ("rate" in error_str and "limit" in error_str)
                or "deadline" in error_str
                or "504" in error_str
                or "timeout" in error_str
            )
            next_gemini_model = self._next_gemini_model()
            if gemini_should_retry_fast and next_gemini_model is not None:
                print(f"Gemini Error on {self.current_gemini_model}: {e}. Switching to {next_gemini_model}.", flush=True)
                # Remove the failed message and retry with fallback gemini model
                messages.pop()
                self.current_gemini_model = next_gemini_model
                return self._prompt_gemini(content, messages, system_instruction)
            
            # For any other error, or if we're already on the fallback gemini model, fall back to groq
            print(f"Gemini Error: {e}. Falling back to Groq.", flush=True)
            self.use_fallback = True
            # Remove the message from history and retry with Groq
            messages.pop() 
            return self._prompt_groq(content, messages, system_instruction)

    def _prompt_groq(self, content: str, messages: list = None, system_instruction: str = WRITER_PROMPT):
        messages = messages or self.writer_messages
        messages.append({"role": "user", "content": content})

        completion = self.groq_client.chat.completions.create(
            model=self.fallback_model,
            messages=[{"role": "system", "content": system_instruction}] + [msg for msg in messages if msg["role"] != "system"],
            temperature=self.temperature,
            top_p=self.top_p,
            stream=False # Simplified for history management
        )

        answer = completion.choices[0].message.content
        messages.append({"role": "assistant", "content": answer})
        return answer

    def _complete_gemini_once(self, messages: list, system_instruction: str) -> str:
        gemini_messages = []

        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_messages.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])]
                )
            )

        print(f"[LLM] Calling Gemini model {self.current_gemini_model}.", flush=True)
        response = self.gemini_client.models.generate_content(
            model=self.current_gemini_model,
            contents=gemini_messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=self.temperature,
                top_p=self.top_p,
            )
        )

        print(f"[LLM] Gemini model {self.current_gemini_model} returned.", flush=True)
        return response.text or ""

    def _groq_retry_delay(self, error: Exception) -> float:
        match = re.search(r"try again in ([0-9.]+)s", str(error), re.IGNORECASE)
        if match:
            return float(match.group(1)) + 0.5
        return 5.0

    def _complete_groq_once(self, messages: list, system_instruction: str, max_retries: int = 3) -> str:
        for attempt in range(1, max_retries + 2):
            try:
                print(f"[LLM] Calling Groq fallback model {self.fallback_model}. Attempt {attempt}.", flush=True)
                completion = self.groq_client.chat.completions.create(
                    model=self.fallback_model,
                    messages=[{"role": "system", "content": system_instruction}] + messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    stream=False
                )

                print(f"[LLM] Groq fallback model {self.fallback_model} returned.", flush=True)
                return completion.choices[0].message.content or ""
            except Exception as e:
                error_str = str(e).lower()
                if "rate_limit" not in error_str and "rate limit" not in error_str:
                    raise
                if attempt > max_retries:
                    raise

                delay = self._groq_retry_delay(e)
                print(f"[LLM] Groq rate limit hit. Waiting {delay:.2f}s before retry.", flush=True)
                time.sleep(delay)

        return ""

    def _complete_once(self, messages: list, system_instruction: str) -> str:
        if self.use_fallback:
            return self._complete_groq_once(messages, system_instruction)

        try:
            return self._complete_gemini_once(messages, system_instruction)
        except Exception as e:
            error_str = str(e).lower()

            gemini_should_retry_fast = (
                ("rate" in error_str and "limit" in error_str)
                or "deadline" in error_str
                or "504" in error_str
                or "timeout" in error_str
            )
            next_gemini_model = self._next_gemini_model()
            if gemini_should_retry_fast and next_gemini_model is not None:
                print(f"Gemini Error on {self.current_gemini_model}: {e}. Switching to {next_gemini_model}.", flush=True)
                self.current_gemini_model = next_gemini_model
                return self._complete_once(messages, system_instruction)

            print(f"Gemini Error: {e}. Falling back to Groq.", flush=True)
            self.use_fallback = True
            return self._complete_groq_once(messages, system_instruction)

    def _judge_approved(self, verdict: str) -> bool:
        verdict_upper = verdict.upper()
        return "GODKJENT" in verdict_upper and "IKKE GODKJENT" not in verdict_upper

    def _is_context_only_prompt(self, content: str) -> bool:
        content_lower = content.lower()
        read_markers = [
            "read this",
            "read these",
            "read the following",
            "les dette",
            "les denne",
            "les disse",
            "example text",
            "example texts",
            "eksempeltekst",
            "eksempeltekster",
            "vedlagt tekst",
            "vedlagte tekst"
        ]
        ack_markers = [
            "done reading",
            "ferdig lest",
            "ferdiglest",
            "bare svar",
            "svar bare",
            "svar kun",
            "kun svar",
            "just answer",
            "only answer",
            "ikke skriv",
            "don't write",
            "do not write"
        ]

        return any(marker in content_lower for marker in read_markers) and any(
            marker in content_lower for marker in ack_markers
        )

    def _context_messages(self) -> list:
        return [msg for msg in self.messages if msg["role"] != "system"]

    def _format_context(self, messages: list) -> str:
        if not messages:
            return "Ingen tidligere kontekst."

        lines = []
        for msg in messages:
            label = "Assistent" if msg["role"] == "assistant" else "Bruker"
            lines.append(f"{label}: {msg['content']}")
        return "\n\n".join(lines)

    def fallback(self):
        self.use_fallback = not self.use_fallback
        # Reset to primary gemini model when switching back
        if not self.use_fallback:
            self.current_gemini_model = self.gemini_models[0]
        return True

    def prompt(self, content: str):
        if not self.use_fallback:
            return self._prompt_gemini(content, self.writer_messages, WRITER_PROMPT)
        return self._prompt_groq(content, self.writer_messages, WRITER_PROMPT)

    def judge(self, content: str):
        if not self.use_fallback:
            return self._prompt_gemini(content, self.judge_messages, SENSOR_JUDGE_PROMPT)
        return self._prompt_groq(content, self.judge_messages, SENSOR_JUDGE_PROMPT)
