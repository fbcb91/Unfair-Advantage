import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

TONE_INSTRUCTIONS = {
    "diretto": (
        "TONO — Diretto e sicuro di sé, va al sodo. "
        "VIETATO: iniziare con 'Ho visto/notato che...'. "
        "Esempio di registro corretto: 'Malaga, Marbella e Siviglia — stai collezionando il sud della Spagna. Quale ti ha sorpresa di più?'"
    ),
    "curioso": (
        "TONO — Curiosità genuina su qualcosa di specifico e non ovvio. "
        "VIETATO: domande turistiche o da catalogo viaggi. "
        "Esempio di registro corretto: 'In tutti i tuoi post al tramonto sei sempre di spalle — è una scelta o viene naturale?'"
    ),
    "giocoso": (
        "TONO — Leggero, un filo ironico, come stessi scherzando con qualcuno appena conosciuto. "
        "VIETATO: humor generico o battute che funzionerebbero su qualsiasi profilo. "
        "Esempio di registro corretto: 'Ok ma quell'highlight si chiama \"Normale\" — cosa ci metti dentro esattamente?'"
    ),
    "romantico": (
        "TONO — Caldo, sincero, si sente l'interesse senza essere pesante. "
        "VIETATO: complimenti generici sull'estetica o frasi da film. "
        "Esempio di registro corretto: 'C'è qualcosa in quel post con la libreria in background che non riesce a passare inosservato — quanti ne hai letti davvero?'"
    ),
}


def analyze_profile(profile_data: dict, tone: str) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non configurata nelle impostazioni")

    client = anthropic.Anthropic(api_key=api_key)
    tone_text = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["curioso"])

    posts_text = "\n".join(
        f"• {p['caption']}"
        for p in profile_data.get("posts", [])[:9]
        if p.get("caption")
    ) or "(nessuna caption)"

    highlights_text = ""
    if profile_data.get("highlight_titles"):
        titles = ", ".join(f'"{t}"' for t in profile_data["highlight_titles"])
        highlights_text = f"Story highlights: {titles}\n"

    prompt = f"""Sei un osservatore acuto con senso dell'umorismo. Devi generare messaggi di primo contatto Instagram che sorprendano davvero — non i soliti.

PROFILO:
Nome: {profile_data.get('full_name', '')} (@{profile_data['username']})
Bio: {profile_data.get('biography') or '(nessuna bio)'}
Follower: {profile_data.get('follower_count', 0):,} | Following: {profile_data.get('following_count', 0):,}
{highlights_text}
CAPTIONS ULTIMI POST:
{posts_text}

IMMAGINI: allegate (foto profilo + post recenti) — guardале attentamente per dettagli non ovvi.

━━━ METODO DI ANALISI (seguilo in ordine) ━━━

STEP 1 — SCARTA L'OVVIO
Identifica le 3-5 cose che tutti noterebbero per prime su questo profilo
(es. "viaggia tanto", "ama il mare", "frequenta locali"). Queste sono vietate.
Sono già state dette da ogni altro uomo che le ha scritto.

STEP 2 — TROVA L'OSSERVAZIONE NON OVVIA
Cerca invece una di queste:
• Un pattern che lei non ha mai visto da fuori (es. appare sempre in un certo ruolo nelle foto di gruppo)
• Una micro-contraddizione tra bio/captions e quello che si vede nelle immagini
• Qualcosa di specifico nel modo in cui SCRIVE le captions (una parola ricorrente, un tipo di ironia, una struttura)
• Un dettaglio di sfondo o contesto che richiede vera attenzione (non il soggetto principale)
• La tensione tra cosa mostra con enfasi e cosa appare quasi per caso
• Il nome di un highlight che non si spiega da solo e crea curiosità

STEP 3 — COSTRUISCI I MESSAGGI
Ogni messaggio deve:
✓ Nascere dall'osservazione non ovvia trovata allo step 2
✓ Farle pensare "aspetta, come l'ha notato?"
✓ Finire con una domanda che NON si può rispondere con sì/no
✓ Sembrare scritto da una persona vera, non da un'AI o da un manuale di pick-up
✓ Rispettare questo tono: {tone_text}

VIETATO in tutti i messaggi:
✗ "Ho visto/notato che ti piace X"
✗ Qualsiasi riferimento ai viaggi come soggetto principale (troppo ovvio su quasi tutti i profili)
✗ Complimenti sull'aspetto fisico o sull'estetica
✗ Aprire con una domanda generica sul posto visitato
✗ Struttura: [osservazione ovvia] + [domanda turistica]
✗ Più di 3 righe

━━━ OUTPUT ━━━
Rispondi SOLO con JSON valido:
{{
  "profile_summary": "Chi è davvero questa persona — non cosa fa, ma come è. 2-3 righe.",
  "hooks": [
    "L'osservazione non ovvia su cui hai costruito i messaggi (spiega perché è non ovvia)",
    "Secondo hook non ovvio",
    "Terzo hook non ovvio"
  ],
  "messages": [
    "Messaggio 1 completo",
    "Messaggio 2 con angolo diverso",
    "Messaggio 3 alternativo"
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
