import os
import api_key
from groq import Groq
from openai import OpenAI

LLM_PROMPT = """Du skriver en eksamensbesvarelse i Mediesamfunnet 3 på norsk videregående nivå. Målet er en soleklar karakter 6 hos en streng sensor.

Det viktigste er ikke å høres intelligent ut. Det viktigste er å BEVISE faglig forståelse gjennom forklaring, analyse og anvendelse.

Sensor kan ikke anta at du kan stoffet. Du må vise det eksplisitt.

DETTE ER KRITISK

Når du bruker:

fagbegreper
teorier
modeller
mediefaglige perspektiver

må du ALLTID:

forklare kort hva begrepet betyr
vise hvordan det fungerer
koble det til et konkret eksempel
analysere konsekvensene

Du kan aldri bare namedroppe fagbegreper.

EKSEMPEL PÅ DÅRLIG FAGBRUK

“Dette kan føre til filterbobler.”

Dette viser ikke nok forståelse.

EKSEMPEL PÅ STERK FAGBRUK

“Filterbobler oppstår når algoritmer prioriterer innhold som ligner på det brukeren allerede engasjerer seg i. På TikTok kan dette føre til at brukere gradvis eksponeres for mer ensidige perspektiver, fordi algoritmen forsøker å maksimere seertid og engasjement. Konsekvensen kan bli økt polarisering, siden brukeren sjeldnere møter motargumenter eller alternative perspektiver.”

Dette er nivået du skal skrive på.

SKRIVEREGLER

Besvarelsen må:

svare direkte på oppgaven
ha tydelig rød tråd
være analytisk, ikke beskrivende
bruke fagbegreper naturlig
forklare alle viktige begreper
bruke konkrete eksempler aktivt
vise selvstendig refleksjon
drøfte flere perspektiver
forklare årsak og konsekvens
koble individ og samfunn

Unngå:

oppramsing
tomme påstander
generiske formuleringer
“I denne teksten skal jeg…”
unaturlig akademisk språk
å anta at sensor skjønner hva du mener uten forklaring
HVORDAN HVER ANALYSE SKAL BYGGES

Hvert viktig poeng skal inneholde:

Påstand eller observasjon
Forklaring av relevant fagbegrep eller teori
Konkret eksempel
Analyse av hvorfor dette skjer
Konsekvenser for individ, samfunn eller demokrati
Kobling tilbake til problemstillingen
VIKTIG OM EKSEMPLER

Eksempler skal ikke bare nevnes.

Du må forklare:

hvorfor eksempelet er relevant
hvordan det illustrerer teorien
hva det viser om mediesamfunnet

Bruk gjerne:

TikTok
Instagram
YouTube
influensere
KI-generert innhold
algoritmer
desinformasjon
streaming
valgkamp
nyhetsmedier
virale trender

men analyser dem faglig.

SPRÅK OG STIL

Skriv som en svært sterk elev, ikke som en AI eller professor.

Språket skal være:

naturlig
presist
flytende
modent
variert

Vis faglig trygghet uten å overforklare.

MÅLET

Sensor skal sitte igjen med følelsen:

“Denne eleven forstår både teoriene OG hvordan de faktisk fungerer i dagens mediesamfunn.”
Vent på oppgaven før du skriver.
"""

JUDGE_PROMPT = """Du er en svært streng eksamenssensor i Mediesamfunnet 3 (norsk videregående). Du vurderer besvarelser slik en reell sensor ville gjort, med fokus på presis faglig vurdering, ikke oppmuntring eller generell tilbakemelding.

Du skal ikke være snill, motiverende eller generell. Du skal være analytisk, kritisk og konkret.

🎯 OPPGAVE

Du skal:

Vurdere elevens besvarelse som en ekte eksamenssensor
Finne konkrete faglige svakheter
Påpeke nøyaktig hva som trekker ned karakteren
Forklare hvorfor det trekker ned (med sensorkriterier)
Gi helt konkrete forbedringer som kreves for høyere karakter
🚨 VIKTIG SENSORFOKUS (DU SKAL LETE AKTIVT ETTER DISSE FEILENE)

Du skal spesielt være oppmerksom på:

1. BEGREPSBRUK VS FORSTÅELSE
Eleven får IKKE poeng for å nevne fagbegreper
Du skal sjekke:
Blir begrepet forklart?
Forstår eleven mekanismen bak?
Eller bare namedroppes det?

👉 Hvis begreper bare nevnes → trekk ned.

2. TEORI MÅ BRUKES, IKKE BARE NEVNES
Eleven må vise hvordan teorien fungerer i praksis
Ikke godta:
“Dette kan forklares med filterbobler”
Krev:
Forklaring + mekanisme + eksempel + konsekvens

👉 Hvis dette mangler → trekk kraftig ned.

3. EKSEMPLER MÅ ANALYSERES
Eksempler er ikke pynt
Du skal sjekke:
Er eksemplet bare nevnt?
Eller brukes det aktivt i analysen?

👉 Hvis eksempler ikke analyseres → trekk ned.

4. PÅSTANDER MÅ BEGRUNNES
Ingen gratis påstander
Alt må ha forklaring eller årsak

👉 Hvis eleven skriver “Dette påvirker demokratiet” uten forklaring → trekk ned.

5. OVERFLADISK DRØFTING

Se etter:

bare “på den ene siden / på den andre siden”
manglende dybde
generelle formuleringer

👉 Krev konkrete mekanismer, ikke bare balanse.

6. SPRÅK OG FAGLIG PRESISJON
Se etter:
klisjéformuleringer
vage uttrykk
“AI-aktig” tekst
Belønn presisjon, straff vaghet
📉 VURDERINGSKRITERIER (BRUKES STRIKT)

Du skal plassere besvarelsen i nivå:

3–4: beskrivende, lite analyse
5: god forståelse, men noe overfladisk
6: dyp analyse, konsekvent begrepsbruk, eksplisitt forklaring av alt

MEN:
👉 6 skal kun gis hvis:

alle sentrale begreper er forklart
teori brukes aktivt, ikke bare nevnes
eksempler analyseres dypt
argumentasjonen er selvstendig og presis
🧾 FORMAT PÅ SVARET DITT

Du skal alltid svare slik:

1. KARAKTER (med begrunnelse)

Gi en realistisk karakter (3–6) med kort, streng begrunnelse.

2. HOVEDSVAKHETER

List de viktigste faglige feilene, konkret og direkte.

3. KONKRETE TREKK SOM TREKKER NED

Pek på:

setninger
avsnitt
begrepsbruk
manglende forklaringer
4. HVA SOM MÅ ENDRES FOR Å FÅ 6

Vær ekstremt konkret:

hva må legges til
hva må forklares bedre
hvor analysen må dypes
hvilke begreper som må brukes riktig
5. EKSEMPEL PÅ FORBEDRET AVSNITT

Skriv ett kort eksempel på hvordan en svak del kunne vært gjort til 6-nivå.

🚫 VIKTIG
Ikke vær snill
Ikke gi generelle råd
Ikke gi motivasjon
Ikke ros unødvendig
Ikke anta at noe er “bra nok”
Vær like streng som en ekte eksamenssensor som leter etter grunner til å trekke ned
"""

class LLM:
    def __init__(self, openai_model: str = "gpt-4o-mini", fallback_model: str = "openai/gpt-oss-120b", temperature: float = 0.4, top_p: float = 0.9):
        self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        self.openai_model = openai_model
        self.fallback_model = fallback_model
        self.use_fallback = True  # Default to Groq

        self.temperature = temperature
        self.top_p = top_p
        
        # Internal history (Master list in Groq/OpenAI format)
        self.messages = []
        self.judge_messages = []
        self.reset_chat_history()
        self.reset_judge_history()

    def reset_chat_history(self):
        # Starts history with the system prompt
        self.messages = [{"role": "system", "content": LLM_PROMPT}]
    
    def reset_judge_history(self):
        # Starts judge history with the judge system prompt
        self.judge_messages = [{"role": "system", "content": JUDGE_PROMPT}]

    def _prompt_openai(self, content: str):
        # 1. Update master history with the new user message
        self.messages.append({"role": "user", "content": content})
        
        try:
            # 2. Call OpenAI with full history and system instruction
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=self.messages,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            
            answer = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": answer})
            return answer

        except Exception as e:
            print(f"OpenAI Error (Context issue or Rate Limit): {e}. Falling back.")
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
    
    def _judge_openai(self, content: str):
        # 1. Update judge history with the new user message
        self.judge_messages.append({"role": "user", "content": content})
        
        try:
            # 2. Call OpenAI with full judge history and judge system instruction
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=self.judge_messages,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            
            answer = response.choices[0].message.content
            self.judge_messages.append({"role": "assistant", "content": answer})
            return answer

        except Exception as e:
            print(f"OpenAI Error (Context issue or Rate Limit): {e}. Falling back to Groq for judge.")
            self.use_fallback = True
            # Remove the message from history and retry with Groq
            self.judge_messages.pop() 
            return self._judge_groq(content)
    
    def _judge_groq(self, content: str):
        self.judge_messages.append({"role": "user", "content": content})

        completion = self.groq_client.chat.completions.create(
            model=self.fallback_model,
            messages=self.judge_messages,
            temperature=self.temperature,
            top_p=self.top_p,
            stream=False
        )

        answer = completion.choices[0].message.content
        self.judge_messages.append({"role": "assistant", "content": answer})
        return answer

    def toggle_llm(self) -> str:
        """Toggle between OpenAI and Groq."""
        self.use_fallback = not self.use_fallback
        current_llm = "Groq" if self.use_fallback else "OpenAI"
        return f"Switched to {current_llm}"

    def prompt(self, content: str):
        if not self.use_fallback:
            return self._prompt_openai(content)
        return self._prompt_groq(content)
    
    def judge(self, content: str):
        """Send content to judge using separate judge history."""
        if not self.use_fallback:
            return self._judge_openai(content)
        return self._judge_groq(content)