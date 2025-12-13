import os
from groq import Groq

class LLM:
    def __init__(self, model: str = "openai/gpt-oss-120b", temperature: float = 0.4, top_p: float = 0.9, reasoning_effort: str = "medium"):
        os.environ["GROQ_API_KEY"] = "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"  # Replace with your actual API key
        self.client = Groq(
            api_key=os.environ.get("GROQ_API_KEY"),  # This is the default and can be omitted
        )

        self.messages = []
        self.prompt("""
Du skal opptre som en erfaren norsklærer og ekstern sensor på VG3-nivå med mange års sensurerings­erfaring. Du kjenner læreplanen (LK20), vurderingskriteriene og hva som faktisk skiller karakter 6 fra 5 i norskfaget.

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

Målet er alltid:
En tekst som ville blitt vurdert til karakter 6 av en streng sensor i norsk VG3.

Vent på oppgavetekst eller instruks før du skriver.
""")

        self.temperature = temperature
        self.top_p = top_p
        self.reasoning_effort = reasoning_effort

    def _get_completion_response(self, completion):
        result = ""
        for chunk in completion:
            result += chunk.choices[0].delta.content or ""
        return result

    def prompt(self, content: str):
        self.messages.append({
            "role": "user",
            "content": content
        })

        completion = self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=self.messages,
            temperature=self.temperature,
            top_p=self.top_p,
            reasoning_effort=self.reasoning_effort,
            stream=True,
            stop=None
        )

        response = self._get_completion_response(completion)
        self.messages.append({
            "role": "assistant",
            "content": response
        })
        return response