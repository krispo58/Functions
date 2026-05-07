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

class LLM:
    def __init__(self, openai_model: str = "gpt-4o-mini", groq_model: str = "mixtral-8x7b-32768", temperature: float = 0.4, top_p: float = 0.9):
        self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        self.openai_model = openai_model
        self.groq_model = groq_model
        self.use_openai = False  # Default to Groq
        self.openai_failed = False  # Track if OpenAI fails

        self.temperature = temperature
        self.top_p = top_p
        
        # Internal history (Master list in Groq/OpenAI format)
        self.messages = []
        self.reset_chat_history()

    def reset_chat_history(self):
        # Starts history with the system prompt
        self.messages = [{"role": "system", "content": LLM_PROMPT}]

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
                reasoning_effort="medium"
            )
            
            answer = response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": answer})
            self.openai_failed = False
            return answer

        except Exception as e:
            print(f"OpenAI Error: {e}. Falling back to Groq.")
            self.openai_failed = True
            # Remove the message from history and retry with Groq
            self.messages.pop() 
            return self._prompt_groq(content)

    def _prompt_groq(self, content: str):
        self.messages.append({"role": "user", "content": content})

        completion = self.groq_client.chat.completions.create(
            model=self.groq_model,
            messages=self.messages,
            temperature=self.temperature,
            top_p=self.top_p,
            stream=False # Simplified for history management
        )

        answer = completion.choices[0].message.content
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def prompt(self, content: str):
        if self.use_openai and not self.openai_failed:
            return self._prompt_openai(content)
        return self._prompt_groq(content)
    
    def switch_to_openai(self):
        """Switch to using OpenAI."""
        self.use_openai = True
        self.openai_failed = False
        return "Switched to OpenAI"
    
    def switch_to_groq(self):
        """Switch to using Groq."""
        self.use_openai = False
        self.openai_failed = False
        return "Switched to Groq"
    
    def get_provider(self) -> str:
        """Get the current provider being used."""
        if self.use_openai and not self.openai_failed:
            return "OpenAI"
        return "Groq"