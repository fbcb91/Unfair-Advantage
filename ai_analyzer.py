import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

TONE_INSTRUCTIONS = {
    "diretto": (
        "TONO — Diretto e sicuro di sé. Va al sodo senza giri di parole. "
        "Chi scrive sa quello che vuole e non ha paura di mostrarlo. Frasi brevi e decise. "
        "Esempio di registro: 'Ho visto che fai surf a Bali — quando torni in acqua?'"
    ),
    "curioso": (
        "TONO — Genuinamente curioso. Fa domande sincere su qualcosa di specifico che ha notato. "
        "È interessato alla sua storia, non alla conquista. Niente di forzato. "
        "Esempio di registro: 'Quella foto da Kyoto è tua? Come ci sei finita?'"
    ),
    "giocoso": (
        "TONO — Leggero e un po' ironico. Come stessi scherzando con qualcuno appena conosciuto. "
        "Un pizzico di umorismo intelligente, mai volgare o fuori luogo. "
        "Esempio di registro: 'Ok ma quella torta la faresti anche per uno sconosciuto?'"
    ),
    "romantico": (
        "TONO — Caldo e sincero. Mostra interesse genuino per lei come persona. "
        "Non troppo intenso, ma si sente l'attrazione. Niente da copione, niente di scontato. "
        "Esempio di registro: 'Non mi capita spesso di fermarmi su un profilo così — cosa stai leggendo adesso?'"
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
    ) or "(nessuna caption disponibile)"

    highlights_text = ""
    if profile_data.get("highlight_titles"):
        titles = ", ".join(f'"{t}"' for t in profile_data["highlight_titles"])
        highlights_text = f"Story highlights salvati: {titles}\n"

    prompt = f"""Sei un esperto di comunicazione interpersonale. Analizza questo profilo Instagram e genera messaggi di primo contatto autentici e personalizzati.

PROFILO:
Nome: {profile_data.get('full_name', '')} (@{profile_data['username']})
Bio: {profile_data.get('biography') or '(nessuna bio)'}
Follower: {profile_data.get('follower_count', 0):,} | Following: {profile_data.get('following_count', 0):,}
{highlights_text}
CAPTIONS ULTIMI POST:
{posts_text}

{tone_text}

Guarda le immagini allegate (foto profilo + post recenti) per capire: interessi, luoghi, stile di vita, hobby, personalità visiva, energia che trasmette.

Rispondi ESCLUSIVAMENTE con JSON valido, zero testo fuori dal JSON:
{{
  "profile_summary": "Chi è questa persona in 2-3 righe. Cosa la rende interessante e unica.",
  "hooks": [
    "Elemento specifico 1 dal profilo su cui puoi costruire un messaggio",
    "Elemento specifico 2",
    "Elemento specifico 3"
  ],
  "messages": [
    "Primo messaggio completo pronto da inviare",
    "Secondo messaggio con angolo diverso",
    "Terzo messaggio alternativo"
  ]
}}

REGOLE FERREE per i messaggi:
- Citano qualcosa di SPECIFICO dal profilo — mai frasi generiche tipo 'bel profilo' o 'sei interessante'
- In italiano naturale, sembrano scritti da una persona vera non da un bot
- Nessun complimento sull'aspetto fisico
- Massimo 3 righe ciascuno
- Finiscono sempre con una domanda aperta che invita risposta
- Rispettano il tono indicato sopra"""

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

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1500,
        messages=[{"role": "user", "content": content}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
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
