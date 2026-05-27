import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

TONE_INSTRUCTIONS = {
    "diretto": (
        "TONO — Diretto, sicuro, non chiede permesso. "
        "Va dritto al punto come chi sa già di essere interessante. "
        "Esempio: 'Flute di champagne in ogni highlight — è una firma o una coincidenza?'"
    ),
    "curioso": (
        "TONO — Curiosità genuina ma leggera, non invadente. "
        "Una domanda che dimostra che hai guardato davvero, non che hai 'studiato' il profilo. "
        "Esempio: 'Estate 23, Estate 24 — cosa deve succedere per finire in un highlight?'"
    ),
    "giocoso": (
        "TONO — Ironico, un filo sfacciato, si prende gioco della situazione. "
        "Come una battuta tra amici intelligenti, non una barzelletta. "
        "Esempio: 'Ho contato i flute di champagne nei tuoi highlight — vinci tu.'"
    ),
    "romantico": (
        "TONO — Caldo, lascia qualcosa in sospeso. "
        "Non dice tutto, crea una tensione leggera. "
        "Esempio: 'Estate 23, Estate 24 — mi chiedo già come finirà Estate 25.'"
    ),
}

CHARACTER_INSTRUCTIONS = {
    "chuck_bass": (
        "PERSONAGGIO — Chuck Bass (Gossip Girl). "
        "Parla come un uomo che sa di essere il migliore nella stanza e non ha bisogno di dirlo esplicitamente. "
        "Tono: sofisticato, leggermente arrogante, ma affascinante. Usa frasi brevi e dense di sottotesto. "
        "Mai banale, mai diretto come un ragazzo qualunque. "
        "Esempio reale: 'Champagne e notti a Manhattan — o stai già scrivendo il sequel?' "
        "Adatta questo stile alla vita reale: niente reference a Blair o Upper East Side, ma lo stesso carisma."
    ),
    "damon_salvatore": (
        "PERSONAGGIO — Damon Salvatore (The Vampire Diaries). "
        "Parla come uno che ha già visto tutto e quasi niente lo sorprende — quasi. "
        "Tono: sarcastico, provocatorio, magnetico. La battuta è affilata ma non cattiva. "
        "Crea tensione con pochissime parole. "
        "Esempio reale: 'Champagne agli highlight, vacanze da sola — o aspetti qualcuno abbastanza interessante?' "
        "Adatta alla vita reale: niente vampiri, solo la stessa energia irresistibile."
    ),
    "hitch": (
        "PERSONAGGIO — Hitch (Will Smith nel film). "
        "Parla come un esperto di connessioni umane: osserva i dettagli, fa domande che nessun altro farebbe. "
        "Tono: caldo, sicuro, mai invadente. Il messaggio suona spontaneo ma è chirurgico. "
        "Esempio reale: 'Estate 23, Estate 24 — le regole per finire negli highlight le accetti o le scrivi tu?' "
        "Adatta alla vita reale: lo stesso approccio calibrato e genuinamente curioso."
    ),
    "harvey_specter": (
        "PERSONAGGIO — Harvey Specter (Suits). "
        "Parla come uno che vince sempre e lo sa. Diretto, mai volgare, sempre un passo avanti. "
        "Tono: concreto, intelligente, autorevole ma non freddo. "
        "Esempio reale: 'Champagne negli highlight — questa non è una coincidenza, è uno standard.' "
        "Adatta alla vita reale: stessa sicurezza senza la giacca da avvocato."
    ),
    "michael_scott": (
        "PERSONAGGIO — Un approccio completamente diverso: entusiasmo genuino e un po' goffo ma che sorprende. "
        "Tono: spontaneo, un filo imbarazzante ma simpatico, fa ridere. Non ironico — sincero al punto da essere disarmante. "
        "Esempio reale: 'Ho passato 10 minuti a guardare i tuoi highlight. Non me ne pento.' "
        "Adatta: stessa energia inesauribile e sincerità che alla fine funziona."
    ),
}


def analyze_profile(profile_data: dict, tone: str, character: str = "", user_info: str = "") -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non configurata nelle impostazioni")

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

    character_section = ""
    if character_text:
        character_section = f"""
━━━ PERSONAGGIO DA INTERPRETARE ━━━
{character_text}
I messaggi devono rispecchiare questa voce e questo stile — adattato alla vita reale, non alla fiction.
"""

    user_info_section = ""
    if user_info and user_info.strip():
        user_info_section = f"""
━━━ CHI SCRIVE (info su di te) ━━━
{user_info.strip()}
Usa queste info se aprono spunti naturali: una passione in comune, un contrasto interessante, un gancio personale.
Non citarle in modo forzato — solo se funzionano davvero.
"""

    prompt = f"""Sei un ragazzo brillante e diretto. Devi scrivere un primo messaggio Instagram che faccia alzare la testa.

PROFILO:
Nome: {profile_data.get('full_name', '')} (@{profile_data['username']})
Bio: {profile_data.get('biography') or '(nessuna bio)'}
Follower: {profile_data.get('follower_count', 0):,} | Following: {profile_data.get('following_count', 0):,}
{highlights_text}
CAPTIONS ULTIMI POST:
{posts_text}
{user_info_section}{character_section}
Guarda le immagini allegate con attenzione — dettagli, pattern, quello che si vede solo fermandosi davvero.

━━━ COME RAGIONARE ━━━

STEP 1 — BUTTA VIA L'OVVIO
Elenca mentalmente le 5 cose più ovvie su questo profilo.
Sono già state dette da chiunque le abbia scritto. Non usarle.

STEP 2 — TROVA IL DETTAGLIO CHE SORPRENDE
Cerca qualcosa che richiede vera attenzione:
• Un pattern che lei stessa non ha mai visto da fuori
• Una micro-contraddizione tra ciò che scrive e ciò che mostra
• Un oggetto, un gesto, un ruolo ricorrente nelle foto che non è il soggetto principale
• Il nome di un highlight che crea curiosità
• Il suo modo di scrivere le captions — un'ironia, una parola che torna

STEP 3 — SCRIVI COME UN ESSERE UMANO BRILLANTE, NON COME UN'AI
Il messaggio non spiega l'osservazione — la usa.
Un ragazzo brillante non dice "ho notato che il flute di champagne appare spesso nei tuoi highlight, il che suggerisce..." —
dice "Flute di champagne in ogni highlight — è una firma o una coincidenza?"

━━━ REGOLE FERREE SUI MESSAGGI ━━━

LUNGHEZZA: massimo 1 riga + eventuale domanda corta. DUE RIGHE IN TUTTO. Mai tre.

STRUTTURA VIETATA:
✗ [osservazione lunga] + [spiegazione] + [domanda filosofica]
✗ "Ho visto/notato che..."
✗ Qualsiasi apertura con "I tuoi..." riferita a viaggi, posti, avventure
✗ Domande tipo "qual è il tuo posto preferito?" o "com'è andata?"
✗ Spiegare perché hai trovato il dettaglio interessante

STRUTTURA GIUSTA:
✓ [osservazione secca o ironica] — [domanda breve e diretta]
✓ Oppure solo l'osservazione, senza domanda, se basta da sola
✓ Il tono giusto: {tone_text}

ESEMPI DI QUALITÀ ATTESA:
✓ "Flute di champagne in ogni highlight — è una firma o una coincidenza?"
✓ "Estate 23, Estate 24 — mi chiedo già come finirà Estate 25."
✓ "Ho contato i flute di champagne negli highlight — vinci tu."
✓ "'Friends' separato da tutto — c'è una lista d'attesa?"

━━━ OUTPUT ━━━
Rispondi SOLO con JSON valido:
{{
  "profile_summary": "Chi è questa persona in 2 righe — non cosa fa, come è.",
  "hooks": [
    "Il dettaglio non ovvio trovato (dillo in una riga)",
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

    # Try with extended thinking first, fall back to standard if unsupported
    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=16000,
            thinking={"type": "enabled", "budget_tokens": 10000},
            messages=[{"role": "user", "content": content}],
        )
        raw = next(b.text for b in response.content if b.type == "text").strip()
    except Exception:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text.strip()

    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("{"):
                raw = stripped
                break
        else:
            raw = parts[1].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()

    result = json.loads(raw)
    result["profile_pic_url"] = profile_data.get("profile_pic_url")
    result["full_name"] = profile_data.get("full_name", "")
    result["biography"] = profile_data.get("biography", "")
    result["follower_count"] = profile_data.get("follower_count", 0)

    return result
