import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

TONE_INSTRUCTIONS = {
    "diretto": (
        "TONO — Diretto, sicuro, non chiede permesso. "
        "Va dritto al punto come chi sa già di essere interessante."
    ),
    "curioso": (
        "TONO — Curiosità genuina ma leggera, non invadente. "
        "Una domanda che dimostra che hai guardato davvero, non che hai 'studiato' il profilo."
    ),
    "giocoso": (
        "TONO — Ironico, un filo sfacciato, si prende gioco della situazione. "
        "Come una battuta tra amici intelligenti, non una barzelletta."
    ),
    "romantico": (
        "TONO — Caldo, lascia qualcosa in sospeso. "
        "Non dice tutto, crea una tensione leggera."
    ),
}

CHARACTER_INSTRUCTIONS = {
    "chuck_bass": "Sei Chuck Bass nella vita reale — non in una serie TV. Scrivi un primo messaggio Instagram a questa ragazza basandoti su ciò che hai visto nel profilo.",
    "damon_salvatore": "Sei Damon Salvatore nella vita reale — non in una serie TV. Scrivi un primo messaggio Instagram a questa ragazza basandoti su ciò che hai visto nel profilo.",
    "hitch": "Sei Hitch (il personaggio di Will Smith nel film) nella vita reale. Scrivi un primo messaggio Instagram a questa ragazza basandoti su ciò che hai visto nel profilo.",
    "harvey_specter": "Sei Harvey Specter nella vita reale — non in uno studio legale. Scrivi un primo messaggio Instagram a questa ragazza basandoti su ciò che hai visto nel profilo.",
    "michael_scott": "Sei un ragazzo con l'energia e la sincerità disarmante di Michael Scott, ma nella vita reale. Scrivi un primo messaggio Instagram a questa ragazza basandoti su ciò che hai visto nel profilo.",
}


def _extract_json(raw: str) -> str:
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            s = part.strip()
            if s.startswith("{"):
                return s
        candidate = parts[1].strip()
        return candidate[4:].strip() if candidate.startswith("json") else candidate
    return raw

PREMIUM_MODEL = "claude-opus-4-8"
FREE_MODEL = "claude-sonnet-4-6"


def analyze_profile(profile_data: dict, tone: str, character: str = "", user_info: str = "", is_premium: bool = False) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non configurata nelle impostazioni")
    model = PREMIUM_MODEL if is_premium else FREE_MODEL

    client = anthropic.Anthropic(api_key=api_key)
    tone_text = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["curioso"])
    character_text = CHARACTER_INSTRUCTIONS.get(character, "") if character else ""

    posts_text = "\n".join(
        f"• {p['caption']}"
        for p in profile_data.get("posts", [])[:9]
        if p.get("caption")
    ) or "(nessuna caption)"

    highlights_text = ""
    if profile_data.get("highlight_titles"):
        titles = ", ".join(f'"{t}"' for t in profile_data["highlight_titles"])
        highlights_text = f"Story highlights: {titles}\n"

    user_info_section = ""
    if user_info and user_info.strip():
        user_info_section = f"""
━━━ CHI SCRIVE (info su di te) ━━━
{user_info.strip()}
Usa queste info se aprono spunti naturali: una passione in comune, un contrasto interessante, un gancio personale.
Non citarle in modo forzato — solo se funzionano davvero.
"""

    opening = character_text if character_text else "Sei un ragazzo che deve scrivere il primo messaggio a una ragazza che non conosce. Sei brillante, mai banale e sicuro di te. Non scriverai mai un messaggio come tutti gli altri. Ti vuoi distinguere dalla massa e sorprendere."

    prompt = f"""{opening}

PROFILO:
Nome: {profile_data.get('full_name', '')} (@{profile_data['username']})
Bio: {profile_data.get('biography') or '(nessuna bio)'}
Follower: {profile_data.get('follower_count', 0):,} | Following: {profile_data.get('following_count', 0):,}
{highlights_text}
CAPTIONS ULTIMI POST:
{posts_text}
{user_info_section}
Guarda le immagini allegate con attenzione — dettagli, pattern, quello che si vede solo fermandosi davvero.

━━━ COME RAGIONARE ━━━

STEP 1 — BUTTA VIA L'OVVIO
Elenca mentalmente le 5 cose più ovvie su questo profilo.
Sono già state dette da chiunque le abbia scritto. Non usarle.

STEP 2 — TROVA IL DETTAGLIO CHE SORPRENDE
Guarda tutto: le foto, le captions, la bio, gli highlights. Non fermarti agli highlights — sono la prima cosa che vede chiunque.
Cerca qualcosa che richiede vera attenzione:
• Un pattern nelle foto che lei stessa non ha mai visto da fuori
• Una micro-contraddizione tra ciò che scrive e ciò che mostra
• Un oggetto, un gesto, un ruolo ricorrente nelle foto che non è il soggetto principale
• Il modo in cui scrive le captions — un'ironia, una parola che torna, il tono
• Qualcosa nella bio che è insolito o crea una domanda
Se bio e captions sono vuote o quasi, l'aggancio DEVE venire dalle immagini: luoghi, situazioni, oggetti, dettagli ricorrenti. L'assenza di testo non è mai un'osservazione.

STEP 3 — SCRIVI COME UN ESSERE UMANO BRILLANTE, NON COME UN'AI
Il messaggio non spiega l'osservazione — la usa.
Un ragazzo brillante non dice "ho notato che..." — parte diretto dall'osservazione.
Il messaggio deve sembrare spontaneo, come se avessi notato qualcosa e non potessi non dirlo. Non deve sembrare l'analisi di un profilo.

━━━ REGOLE FERREE SUI MESSAGGI ━━━

LUNGHEZZA: massimo 1 riga + eventuale domanda corta. DUE RIGHE IN TUTTO. Mai tre.

STRUTTURA VIETATA:
✗ [osservazione lunga] + [spiegazione] + [domanda filosofica]
✗ "Ho visto/notato che..."
✗ Qualsiasi apertura con "I tuoi..." riferita a viaggi, posti, avventure
✗ Domande tipo "qual è il tuo posto preferito?" o "com'è andata?"
✗ Spiegare perché hai trovato il dettaglio interessante
✗ Il trattino lungo (—) in qualsiasi posizione della frase
✗ Struttura "o sei X o Y" in qualsiasi forma
✗ Commentare ciò che manca nel profilo (bio vuota, nessuna caption, highlights senza testo) — guarda ciò che c'è
✗ Parlare del profilo come oggetto: l'handle, l'username, il numero di post o highlights, com'è organizzato, cosa "comunica". Non stai recensendo un profilo, stai scrivendo a una persona: parla di lei e di quello che vive, non di come si presenta online

STRUTTURA GIUSTA:
✓ Una frase secca che colpisce, con o senza domanda finale
✓ Ogni messaggio deve avere struttura diversa dagli altri due
✓ Almeno uno dei tre messaggi dovrebbe chiudersi con una domanda breve, solo se apre davvero qualcosa
✓ Il tono giusto: {tone_text}

━━━ OUTPUT ━━━
Rispondi SOLO con JSON valido:
{{
  "profile_summary": "Chi è questa persona in 2 righe — non cosa fa, come è.",
  "hooks": [
    "Il dettaglio non ovvio trovato (una riga — qualcosa che si vede, mai qualcosa che manca)",
    "Secondo dettaglio",
    "Terzo dettaglio"
  ],
  "messages": [
    "Messaggio 1 — max 2 righe",
    "Messaggio 2 — angolo diverso, max 2 righe",
    "Messaggio 3 — max 2 righe"
  ]
}}"""

    content = []
    for img in profile_data.get("images", [])[:7]:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img["media_type"],
                "data": img["data"],
            },
        })
    content.append({"type": "text", "text": prompt})

    # Try with extended thinking first, fall back to standard only if thinking is unsupported
    try:
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            thinking={"type": "enabled", "budget_tokens": 10000},
            messages=[{"role": "user", "content": content}],
        )
        raw = next(b.text for b in response.content if b.type == "text").strip()
    except anthropic.BadRequestError:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text.strip()

    raw = _extract_json(raw)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # One retry without thinking
        retry = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": content}],
        )
        raw = _extract_json(retry.content[0].text.strip())
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("L'AI non ha risposto nel formato atteso. Riprova.")
    result["profile_pic_url"] = profile_data.get("profile_pic_url")
    result["full_name"] = profile_data.get("full_name", "")
    result["biography"] = profile_data.get("biography", "")
    result["follower_count"] = profile_data.get("follower_count", 0)

    return result


def refine_message(profile_data: dict, tone: str, character: str, original_message: str, instruction: str = "", is_premium: bool = False) -> list:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non configurata nelle impostazioni")
    model = PREMIUM_MODEL if is_premium else FREE_MODEL

    client = anthropic.Anthropic(api_key=api_key)
    tone_text = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["curioso"])
    character_text = CHARACTER_INSTRUCTIONS.get(character, "") if character else ""
    opening = character_text if character_text else "Sei un ragazzo brillante, mai banale e sicuro di te."

    direction_section = ""
    if instruction and instruction.strip():
        direction_section = f"\nIl mittente vuole: {instruction.strip()}\n"

    prompt = f"""{opening}

Hai scritto questo primo messaggio Instagram per @{profile_data['username']}:
"{original_message}"
{direction_section}
Il messaggio ha del potenziale ma può essere migliorato. Proponi 3 varianti alternative — angoli diversi, strutture diverse tra loro.

PROFILO (per contesto):
Bio: {profile_data.get('biography') or '(nessuna bio)'}
{f"Highlights: {', '.join(profile_data['highlight_titles'][:5])}" if profile_data.get('highlight_titles') else ""}

REGOLE FERREE:
• Max 2 righe per messaggio
• Niente trattino lungo (—)
• Niente struttura "o sei X o Y"
• Non commentare ciò che manca nel profilo
• Non parlare del profilo come oggetto (handle, highlights, com'è organizzato): parla di lei
• Spontaneo, non analitico
• {tone_text}

Rispondi SOLO con JSON valido:
{{"alternatives": ["Variante 1", "Variante 2", "Variante 3"]}}"""

    response = client.messages.create(
        model=model,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    raw = _extract_json(raw)
    try:
        return json.loads(raw).get("alternatives", [])
    except json.JSONDecodeError:
        raise ValueError("L'AI non ha risposto nel formato atteso. Riprova.")
