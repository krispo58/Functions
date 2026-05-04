import os
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

Kun disse tegnsettingene: komma, punktum, bindestrek, apostrof, kolon, parantes.

Når du mottar tilbakemelding fra sensor, skal du:
- Lese hver enkelt konkrete instruksjon nøye
- Kun endre det som sensor peker på – ikke skrive om hele teksten
- Ikke legge til metakommentarer om hva du har endret

Ingen metakommentarer. Bare teksten.
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
    def __init__(self, gemini_model: str = "gemini-3.1-pro-preview", gemini_fallback_model: str = "gemini-3-flash-preview", fallback_model: str = "openai/gpt-oss-120b", temperature: float = 0.4, top_p: float = 0.9):
        self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        self.gemini_model = gemini_model
        self.gemini_fallback_model = gemini_fallback_model
        self.current_gemini_model = gemini_model
        self.fallback_model = fallback_model
        self.use_fallback = False 

        self.temperature = temperature
        self.top_p = top_p
        
        # Internal history (Master list in Groq/OpenAI format)
        self.messages = []
        self.reset_chat_history()

    def reset_chat_history(self):
        # Starts history with the system prompt
        self.messages = [{"role": "system", "content": WRITER_PROMPT}]

    def _get_gemini_history(self):
        """Converts master history to Gemini's expected format using SDK types."""
        gemini_history = []
        
        for msg in self.messages:
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

    def _prompt_gemini(self, content: str):
        # 1. Update master history with the new user message
        self.messages.append({"role": "user", "content": content})
        
        try:
            # 2. Get history formatted for Gemini (excluding current message)
            history = self._get_gemini_history()[:-1] 

            new_message = types.Content(
            role="user",
            parts=[types.Part(text=content)]
)

            # 3. Call Gemini with full history and system instruction
            response = self.gemini_client.models.generate_content(
                model=self.current_gemini_model,
                contents=history + [new_message],
                config=types.GenerateContentConfig(
                    system_instruction=WRITER_PROMPT,
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
            )
            
            answer = response.text
            self.messages.append({"role": "assistant", "content": answer})
            return answer

        except Exception as e:
            error_str = str(e).lower()
            
            # Check if this is a rate limit error and we're still on the primary gemini model
            if "rate" in error_str and "limit" in error_str and self.current_gemini_model == self.gemini_model:
                print(f"Gemini Rate Limit on {self.current_gemini_model}: {e}. Switching to {self.gemini_fallback_model}.")
                # Remove the failed message and retry with fallback gemini model
                self.messages.pop()
                self.current_gemini_model = self.gemini_fallback_model
                return self._prompt_gemini(content)
            
            # For any other error, or if we're already on the fallback gemini model, fall back to groq
            print(f"Gemini Error: {e}. Falling back to Groq.")
            self.use_fallback = True
            # Remove the message from history and retry with Groq
            self.messages.pop() 
            return self._prompt_groq(content)

    def _prompt_groq(self, content: str):
        self.messages.append({"role": "user", "content": content})

        completion = self.groq_client.chat.completions.create(
            model=self.fallback_model,
            messages=self.messages,
            temperature=self.temperature,
            top_p=self.top_p,
            stream=False # Simplified for history management
        )

        answer = completion.choices[0].message.content
        self.messages.append({"role": "assistant", "content": answer})
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

        response = self.gemini_client.models.generate_content(
            model=self.current_gemini_model,
            contents=gemini_messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=self.temperature,
                top_p=self.top_p,
            )
        )

        return response.text or ""

    def _complete_groq_once(self, messages: list, system_instruction: str) -> str:
        completion = self.groq_client.chat.completions.create(
            model=self.fallback_model,
            messages=[{"role": "system", "content": system_instruction}] + messages,
            temperature=self.temperature,
            top_p=self.top_p,
            stream=False
        )

        return completion.choices[0].message.content or ""

    def _complete_once(self, messages: list, system_instruction: str) -> str:
        if self.use_fallback:
            return self._complete_groq_once(messages, system_instruction)

        try:
            return self._complete_gemini_once(messages, system_instruction)
        except Exception as e:
            error_str = str(e).lower()

            if "rate" in error_str and "limit" in error_str and self.current_gemini_model == self.gemini_model:
                print(f"Gemini Rate Limit on {self.current_gemini_model}: {e}. Switching to {self.gemini_fallback_model}.")
                self.current_gemini_model = self.gemini_fallback_model
                return self._complete_gemini_once(messages, system_instruction)

            print(f"Gemini Error: {e}. Falling back to Groq.")
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

    def agent_prompt(self, content: str, max_rounds: int = 6) -> str:
        if self._is_context_only_prompt(content):
            answer = "Ferdig lest."
            self.messages.extend([
                {"role": "user", "content": content},
                {"role": "assistant", "content": answer}
            ])
            return answer

        previous_context = self._context_messages()
        writer_messages = previous_context + [{"role": "user", "content": content}]
        answer = self._complete_once(writer_messages, WRITER_PROMPT)

        for _ in range(max_rounds):
            judge_messages = [{
                "role": "user",
                "content": (
                    "RELEVANT TIDLIGERE KONTEKST:\n"
                    f"{self._format_context(previous_context)}\n\n"
                    "OPPGAVE:\n"
                    f"{content}\n\n"
                    "TEKST SOM SKAL VURDERES:\n"
                    f"{answer}"
                )
            }]
            verdict = self._complete_once(judge_messages, SENSOR_JUDGE_PROMPT)

            if self._judge_approved(verdict):
                self.messages.extend([
                    {"role": "user", "content": content},
                    {"role": "assistant", "content": answer}
                ])
                return answer

            writer_messages.extend([
                {"role": "assistant", "content": answer},
                {
                    "role": "user",
                    "content": (
                        "Sensor godkjente ikke teksten som 6-nivå. "
                        "Revider teksten ved å følge hver konkrete instruksjon fra sensor. "
                        "Returner bare den ferdige reviderte teksten, uten metakommentarer.\n\n"
                        f"Sensors vurdering:\n{verdict}"
                    )
                }
            ])
            answer = self._complete_once(writer_messages, WRITER_PROMPT)

        self.messages.extend([
            {"role": "user", "content": content},
            {"role": "assistant", "content": answer}
        ])
        return answer

    def fallback(self):
        self.use_fallback = not self.use_fallback
        # Reset to primary gemini model when switching back
        if not self.use_fallback:
            self.current_gemini_model = self.gemini_model
        return True

    def prompt(self, content: str):
        if not self.use_fallback:
            return self._prompt_gemini(content)
        return self._prompt_groq(content)
