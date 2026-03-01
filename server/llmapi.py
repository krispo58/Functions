import os
from groq import Groq
from google import genai
from google.genai import types

LLM_PROMPT = """Du skal opptre som en erfaren norsklærer og ekstern sensor på VG3-nivå med mange års sensurerings­erfaring. Du kjenner læreplanen (LK20), vurderingskriteriene og hva som faktisk skiller karakter 6 fra 5 i norskfaget.

Når du produserer tekst, skal du:

Skrive presist, analytisk og faglig sikkert uten unødvendig fyll.

Bruke korrekt og variert språk med naturlig flyt, men uten å virke kunstig eller overpolert.

Vise tydelig tekstforståelse, selvstendig tolkning og refleksjon.

Bruke relevante fagbegreper der det styrker analysen, men aldri som pynt.

Trekke selvstendige poenger og vise moden resonnering.

Tilpasse sjanger, formål og mottaker fullstendig til oppgaveteksten.

Skrive som en svært sterk elev, ikke som en lærebok eller akademisk artikkel.

Viktig:

Teksten skal fremstå 100 % menneskelig skrevet av en elev på høyt nivå.

Ingen metakommentarer, ingen forklaringer om hva du gjør, kun selve teksten.

Ingen klisjeer, ingen generiske formuleringer, ingen “typisk AI-struktur”.

Variér setningslengde og rytme naturlig.

Unngå oppramsing. Bruk sammenhengende resonnering.

Skriv med svo-struktur (subjekt-verb-objekt) og unngå passiv, og substantiviserte verb.

Målet er alltid:
En tekst som ville blitt vurdert til karakter 6 av en streng sensor i norsk VG3.
                    
Også viktig:
Du er KUN tillatt å bruke disse tegnsettingene: komma, punktum, bindestrek (ikke m-dash), apostrof, kolon, parantes

Du skal aldri svare meg direkte eller lage kommentarer til svaret ditt, bare følg instruksen din. Om instruksen er uklar, så gjør du ditt beste forsøk på å svare det som er ønsket
Vent på oppgavetekst eller instruks før du skriver.
"""

class LLM:
    def __init__(self, gemini_model: str = "gemini-3-flash-preview", fallback_model: str = "openai/gpt-oss-120b", temperature: float = 0.4, top_p: float = 0.9):
        self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        self.gemini_model = gemini_model
        self.fallback_model = fallback_model
        self.use_fallback = False 

        self.temperature = temperature
        self.top_p = top_p
        
        # Internal history (Master list in Groq/OpenAI format)
        self.messages = []
        self.reset_chat_history()

    def reset_chat_history(self):
        # Starts history with the system prompt
        self.messages = [{"role": "system", "content": LLM_PROMPT}]

    def _get_gemini_history(self):
        """Converts master history to Gemini's expected format and role names."""
        gemini_history = []
        for msg in self.messages:
            # Gemini system instructions are handled in config, not history
            if msg["role"] == "system":
                continue
            
            # Map 'assistant' role to 'model'
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_history.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        return gemini_history

    def _prompt_gemini(self, content: str):
        # 1. Update master history with the new user message
        self.messages.append({"role": "user", "content": content})
        
        try:
            # 2. Get history formatted for Gemini (excluding current message)
            history = self._get_gemini_history()[:-1] 

            # 3. Call Gemini with full history and system instruction
            response = self.gemini_client.models.generate_content(
                model=self.gemini_model,
                contents=history + [{"role": "user", "parts": [{"text": content}]}],
                config=types.GenerateContentConfig(
                    system_instruction=LLM_PROMPT,
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
            )
            
            answer = response.text
            self.messages.append({"role": "assistant", "content": answer})
            return answer

        except Exception as e:
            print(f"Gemini Error (Context issue or Rate Limit): {e}. Falling back.")
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

    def prompt(self, content: str):
        if not self.use_fallback:
            return self._prompt_gemini(content)
        return self._prompt_groq(content)