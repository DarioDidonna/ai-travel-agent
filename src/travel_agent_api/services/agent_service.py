from datetime import date

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

from travel_agent_api.llm import get_chat_model
from travel_agent_api.tools.chain_historical_expert import chain_historical_expert
from travel_agent_api.tools.chain_travel_plan import chain_travel_plan

# Tools
from travel_agent_api.tools.flights_finder import flights_finder
from travel_agent_api.tools.hotels_finder import hotels_finder

# Limiti di consumo per ogni richiesta (OWASP LLM10). Un viaggio completo usa di solito
# 3-4 chiamate al modello e 3-4 ai tool; senza limiti LangGraph consentirebbe ~10.000 passi
MAX_MODEL_CALLS = 8
MAX_TOOL_CALLS = 8
RECURSION_LIMIT = 40

# Capita (es. dopo ricerche bloccate dai limiti) che il modello chiuda senza testo
EMPTY_REPLY_MESSAGE = (
    "Non sono riuscito a formulare una risposta completa. Prova a riformulare la domanda "
    "o a dividerla in richieste più semplici (per esempio una settimana alla volta)."
)

FLIGHTS_OUTPUT = """
format: markdown

## Miglior Opzione

### Andata:
- Compagnia aerea: Ryanair
- Data di partenza: 2024-12-13
- Ora di partenza: 10:00
- Durata del volo: 1h 30m

### Ritorno:
- Compagnia aerea: Ryanair
- Data di ritorno: 2024-12-19
- Ora di ritorno: 14:30
- Durata del volo: 1h 30m

Inserisci il link di Google per la prenotazione se possibile.

#### Altre opzioni disponibili:
- Compagnia aerea: Ryanair
- Data di partenza: 2024-12-13
- Ora di partenza: 10:00
- Durata del volo: 1h 30m

- Compagnia aerea: Ryanair
- Data di ritorno: 2024-12-19
- Ora di ritorno: 14:30
- Durata del volo: 1h 30m
...
"""

HOTELS_OUTPUT = """
format: markdown

#### Hotel 1
Inserisci la foto dell'hotel se disponibile.

*Descrizione:* Camere e suite eleganti, a volte con vista sulla città, in hotel esclusivo con piscina panoramica e spa.
*Prezzo per notte:* €296 (prima delle tasse e spese: €260)
*Prezzo totale:* €2,660 (prima delle tasse e spese: €2,336)
*Check-in:* 15:00, Check-out: 12:00
*Valutazione complessiva:* 4.5 su 5
*Servizi Inclusi:* Spa, Piscina, Parcheggio gratuito

#### Hotel 2
Inserisci la foto dell'hotel se disponibile.

*Descrizione:* Hotel in stile Liberty con alloggi arredati in maniera artistica, ristorante elegante, bar e spa.
*Prezzo per notte:* €380 (prima delle tasse e spese: €333)
*Prezzo totale:* €3,418 (prima delle tasse e spese: €3,000)
*Check-in:* 15:00, Check-out: 12:00
*Valutazione complessiva:* 4.5 su 5
*Servizi Inclusi:* Spa, Piscina, Parcheggio gratuito
"""

TRAVEL_PLAN_OUTPUT = """
format: markdown

### Itinerario:

### Giorno 1 - 2024-12-13:
*Mattina:* Descrizione dell'attività da svolgere la mattina
*Pomeriggio:* Descrizione dell'attività da svolgere il pomeriggio
*Sera:* Descrizione dell'attività da svolgere la sera

### Giorno 2 - 2024-12-14:
*Mattina:* Descrizione dell'attività da svolgere la mattina
*Pomeriggio:* Descrizione dell'attività da svolgere il pomeriggio
*Sera:* Descrizione dell'attività da svolgere la sera
...
"""


class Agent:
    def __init__(self):
        self.today = date.today()
        self.model = get_chat_model()
        self.tools = [
            chain_historical_expert,
            flights_finder,
            hotels_finder,
            chain_travel_plan,
        ]
        self.agent_executor = create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=self._system_prompt(),
            middleware=[
                # Oltre il limite il modello si ferma con un errore: la richiesta è troppo complessa
                ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="error"),
                # Oltre il limite i tool vengono bloccati e il modello risponde con i dati che ha
                ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="continue"),
            ],
        )

    def _system_prompt(self) -> str:
        return f"""
        Sei un travel planner. Il tuo compito è organizzare il viaggio per l'utente.
        Aggiungi delle emojis per rendere il tuo output più interessante.
        Rispondi sempre in italiano e traduci in italiano anche le etichette che
        provengono dai dati dei tool (es. "Carbon emission estimate" -> "Emissioni di CO₂ stimate").
        La data di oggi è {self.today.isoformat()}

        Regole per le ricerche:
        - Se l'utente non indica date precise (es. "a febbraio", "in primavera"), chiedigliele
          prima di cercare. Se preferisci procedere, scegli tu le date e scrivi chiaramente
          all'inizio della risposta quali hai usato e che può chiederne altre.
        - Se l'utente chiede voli diretti usa nonstop_only; se chiede i più economici usa
          cheapest_first, sia per i voli sia per gli hotel.
        - Il prezzo massimo degli hotel si applica per notte: se l'utente dà un budget totale,
          dividilo per il numero di notti, usa max_price_per_night e spiega il calcolo.
        - Non è possibile filtrare il numero di camere: cerca con il numero di persone e
          avvisa l'utente che dovrà verificare la disponibilità delle camere al momento della prenotazione.
        - Fai al massimo 4 ricerche di voli o hotel per risposta. Se l'utente vuole confrontare
          molte date (es. "ogni giorno del mese"), scegline al massimo 3 rappresentative e
          spiega che può chiederne altre.
        - Per gli hotel con bambini serve l'età di ogni bambino: se non la conosci, chiedila.
        - Se una ricerca non trova risultati con i filtri richiesti (es. nessun volo diretto),
          dillo chiaramente e proponi l'alternativa più vicina.

        Usa le seguenti istruzioni per creare un output:

        Esempio Output Voli:
        {FLIGHTS_OUTPUT}

        Esempio Output Hotel:
        {HOTELS_OUTPUT}

        Esempio Output Viaggio:
        {TRAVEL_PLAN_OUTPUT}
        """

    def run(self, messages: list) -> str:
        """Esegue l'agente sulla conversazione e restituisce il testo della risposta finale."""
        # Il prompt di sistema è già nell'agente: lo stato contiene solo la conversazione
        response = self.agent_executor.invoke({"messages": messages}, config={"recursion_limit": RECURSION_LIMIT})
        # .text funziona anche quando Gemini 3 restituisce il contenuto come lista di blocchi
        reply = str(response["messages"][-1].text).strip()
        return reply or EMPTY_REPLY_MESSAGE
