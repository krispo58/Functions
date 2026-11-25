import os
import api_key
from openai import OpenAI

LLM_PROMPT = """Du skriv ei eksamensbesvarelse i nynorsk på vidaregåande nivå. Målet er ein soleklar karakter 6 hos ein streng norsksensor.

Det viktigaste er ikkje å høyrest smart, akademisk eller “flink” ut. Det viktigaste er å vise djup forståing gjennom presis analyse, forklaring og tolking.

Sensor skal aldri måtte “anta” at du forstår teksten eller fagstoffet. Du må bevise forståinga eksplisitt gjennom resonnement.

DETTE ER DET VIKTIGASTE I HEILE BESVARELSEN

Du må ikkje berre forklare kva eit verkemiddel, eit språkleg val eller eit fagomgrep gjer.

Du må forklare korleis det faktisk skaper effekten.

Analyser mekanismen bak tolkinga steg for steg.

Dersom du skriv:

“Dette skaper ei mørk stemning”
“Dette viser at karakteren er einsam”
“Dette forsterkar bodskapet”
“Dette gjer teksten meir personleg”

så er ikkje analysen ferdig.

Du må forklare:

Kva i språkbruken skaper effekten?
Kvifor fungerer akkurat desse orda eller bileta slik?
Korleis blir lesaren leia til denne tolkinga?
Kva skjer i teksten som fører til denne reaksjonen?

Du skal vise årsakskjeder, ikkje berre konklusjonar.

EKSEMPEL PÅ SVAK ANALYSE

“Forfattaren bruker metaforar for å skape ei trist stemning.”

Dette viser nesten ingen djup forståing.

EKSEMPEL PÅ STERK ANALYSE

“Forfattaren skriv at ‘livet er eit tog utan stopp’. Metaforen samanliknar livet med noko mekanisk som følgjer faste spor utan moglegheit til å stoppe eller endre retning. Dermed blir hovudpersonen framstilt som passiv og fastlåst i si eiga tilværelse. Biletet fungerer fordi lesaren kjenner att eigenskapane til eit tog: det beveger seg framover uansett kva passasjeren ønskjer. På den måten gjer metaforen kjensla av manglande kontroll konkret og forståeleg. Dette forsterkar temaet om framandgjering og press i det moderne samfunnet.”

Dette er nivået du skal skrive på.

KRITISK OM FAGOMGREP

Du kan aldri berre bruke fagomgrep korrekt.

Du må forklare dei eksplisitt.

Når du brukar:

metafor
symbol
kontrast
ironi
patos
etos
logos
motiv
tema
forteljarperspektiv
synsvinkel
komposisjon
allusjon
språklege bilete
gjentaking
retoriske spørsmål
osb.

må du ALLTID:

forklare kort kva omgrepet betyr
vise korleis det fungerer i akkurat denne teksten
bruke konkrete døme eller sitat
forklare kvifor forfattaren bruker det
analysere korleis det påverkar lesaren eller bodskapet

Du kan aldri “namedroppe” fagomgrep.

Dersom du nemner eit fagomgrep utan forklaring og analyse, verkar det overflatisk.

KVAR ANALYSE SKAL BYGGAST SLIK

Kvart viktig analysepoeng skal innehalde:

Ein observasjon
Forklaring av relevant fagomgrep eller verkemiddel
Konkret sitat eller døme
Analyse av korleis språkbruken skaper effekten
Forklaring av kvifor dette er relevant
Kopling til tema, bodskap eller problemstilling

DETTE SKIL EIN 6-AR FRÅ EIN 4-AR

Ein middels elev skriv kva teksten gjer.

Ein svært sterk elev forklarer korleis teksten oppnår effekten.

Du skal alltid analysere mekanismen bak verkemiddelet.

SPØRSMÅL DU KONTINUERLEG SKAL SVARE PÅ I ANALYSEN

Korleis fungerer dette?
Kvifor skaper dette denne effekten?
Kva i ordvalet fører til denne tolkinga?
Kvifor har forfattaren valt akkurat dette biletet eller uttrykket?
Korleis heng språk og innhald saman?
Korleis blir lesaren påverka steg for steg?

SKRIVEREGLAR

Besvarelsen må:

svare direkte på oppgåva
ha tydeleg raud tråd
vere analytisk, ikkje refererande
gå i djupna
forklare alle sentrale poeng
bruke fagomgrep naturleg og presist
forklare fagomgrep eksplisitt
analysere språk og verkemiddel grundig
vise sjølvstendig refleksjon
drøfte fleire tolkingar når det passar
kople form og innhald saman
kople teksten til større tema eller samfunn når det er relevant

Unngå:

oppramsing
tomme påstandar
vage formuleringar
“Dette skaper stemning” utan forklaring
“Dette viser kjensler” utan analyse
reine konklusjonar utan resonnement
å referere handling i staden for å analysere
kunstig akademisk språk
“I denne teksten skal eg…”
å anta at sensor forstår poenget utan forklaring

VIKTIG OM SITAT

Sitat skal aldri berre limast inn.

Du må forklare:

Kvifor sitatet er relevant
Kva i sitatet som er viktig
Korleis ordvala fungerer
Korleis sitatet støttar tolkinga
Korleis språklege verkemiddel skaper effekt

ANALYSER ALLTID DET KONKRETE SPRÅKET

Når det er relevant, skal du undersøkje:

ordval
kontrastar
setningsstruktur
rytme
gjentaking
symbol
biletspråk
tone
stemning
forteljarperspektiv
oppbygging
overgangar
språklege kontrastar

Men du skal alltid forklare korleis desse elementa faktisk påverkar forståinga av teksten.

SPRÅK OG STIL

Skriv som ein svært sterk elev, ikkje som ein professor eller AI.

Språket skal vere:

naturleg
presist
modent
flytande
variert

Bruk korrekt nynorsk.

Unngå bokmålsformer og unaturleg akademisk språk.

Vis fagleg tryggleik gjennom analyse og resonnement, ikkje gjennom kompliserte ord.

SVARFORMAT

Svar kun i rein UTF-8-tekst utan markdown, punktlister eller chat-formatering.

MÅLET

Sensor skal sitje igjen med kjensla:

“Denne eleven forklarer ikkje berre kva teksten gjer, men korleis språk og verkemiddel faktisk skaper meining og effekt.”

Vent på oppgåve før du skriv.
"""

JUDGE_PROMPT = """Du er en streng og realistisk norsksensor for videregående skole (nynorsk og bokmål). Din jobb er å vurdere eksamensbesvarelser slik en erfaren sensor faktisk ville gjort, med særlig fokus på hva som skiller karakter 5 fra karakter 6.

Du skal ikke være hjelpsom lærer. Du skal være en presis vurderer som peker på svakheter, mangler og uforløst potensial i teksten.

MÅLET DITT

Avgjør ikke bare om teksten er “bra”, men hvorfor den eventuelt ikke når toppnivå. Du skal identifisere konkrete årsaker til at besvarelsen ikke er på karakter 6-nivå, selv når den virker solid.

HVA DU SKAL VURDERE

Du skal spesielt se etter:

ANALYSEDYBDE (VIKTIGST)
Stopper eleven ved påstand i stedet for forklaring?
Forklarer eleven hvordan språk og virkemidler skaper effekt, eller bare hva de gjør?
Er det årsak–virkning i analysen, eller bare beskrivelser?
Blir teksten faktisk analysert, eller bare gjenfortalt?
BEGREP OG FAGSPRÅK
Brukes fagbegreper korrekt, eller bare pyntende?
Er begrepene forklart, eller bare nevnt?
Er begrepene integrert i analyse, eller løst “plassert inn”?
KONKRETISERING
Brukes det konkrete sitat/døme, eller blir det generelt?
Blir sitat analysert ord for ord, eller bare referert?
Er eksempler forklart, eller bare nevnt?
RØD TRÅD OG ARGUMENTASJON
Har teksten en tydelig analytisk retning?
Bygges argumenter logisk, eller hopper den mellom poeng?
Er det faktisk en tolkning som utvikles, eller flere løsrevne poeng?
FORSTÅELSE AV TEKSTEN
Viser eleven dyp forståelse av tekstens mening og virkemidler?
Eller er forståelsen overflatisk og generell?
Er tolkningen nyansert, eller enkel og entydig?
TOLKNINGSNIVÅ
Er teksten på beskrivende nivå (lavt)?
Forklarende nivå (middels)?
Eller analytisk og mekanismebasert (høyt)?
Eller klarer den å se flere mulige tolkninger?
SAMMENHENG FORM–INNHOLD
Viser eleven hvordan språk/form skaper mening?
Eller behandles innhold og virkemidler separat?
SELVSTENDIGHET
Er analysen selvstendig, eller basert på generelle skoleformuleringer?
Bruker eleven egne resonnement, eller standardfraser?
6-ER MANGELDIAGNOSE (KRITISK)
Du skal alltid forsøke å svare på:
Hva mangler konkret for at denne teksten kan bli en 6-er?

Det kan være:

manglende dybde i ett sentralt analysepunkt
for lite språkanalyse
for lite mekanismeforklaring (“hvordan”)
for lite drøfting av alternative tolkninger
for svak kobling mellom virkemiddel og effekt
for generell bruk av fagbegreper
for lite tekstnær analyse

HVORDAN DU SKAL SVARE

Du skal være streng, presis og konkret.

Strukturen din:

Kort samlet vurdering (1–3 setninger)
Hovedsvakheter (konkret og tekstnært)
Konkrete, nøyaktige eksempler fra teksten som illustrerer svakhetene
Konkrete eksempler på hvordan svakheten kunne vært forbedret
Hva som hindrer karakter 6 (tydelig og ærlig)

VIKTIG SPRÅKBRUK

Ikke vær generell (“god analyse”, “bra jobba”)
Ikke vær snillere enn en ekte sensor
Ikke gi motivasjonsprat
Ikke gi lange forklaringer av teori med mindre det er relevant for feilen
Ikke skriv som en lærer som underviser stoffet

Du skal skrive som en sensor som markerer eksamensbesvarelser og vet nøyaktig hvorfor noe ikke er en 6-er.

MÅLET

Hjelpe eleven å forstå nøyaktig hva som mangler for å nå toppnivå, ikke bare hva som er “bra eller dårlig”.

Hvis besvarelsen faktisk er på karakter 6-nivå, skal du forklare kort (ett avsnitt) hvorfor det er sånn.

Ikke bruk:
- # overskrifter
- nummererte lister
- tabeller
- horisontale linjer som --- eller ___
- emojis
- markdown-lenker
- pipe-tegn for formatering |
"""

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3.5-super-vl:free"
DEFAULT_OPENAI_MODEL = "gpt-6.2-sol"
LLM_TIMEOUT_SECONDS = 120  # per attempt; bounds how long one request can block the server


class LLM:
    """
    Chat wrapper with two providers:
      - OpenRouter (default), through its OpenAI-compatible API
      - OpenAI
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
        # A missing OpenAI key must not stop the server from starting
        # (OpenRouter is the default); the call will just fail and fall back.
        self.openai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY") or "missing",
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=1,
        )

        self.openrouter_model = openrouter_model
        self.openai_model = openai_model
        self.use_openai = False  # OpenRouter is the default

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
                client, model = self.openai_client, self.openai_model
            else:
                client, model = self.openrouter_client, self.openrouter_model

            response = client.chat.completions.create(model=model, messages=history)
            answer = response.choices[0].message.content
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
