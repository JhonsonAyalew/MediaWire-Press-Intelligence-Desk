"""
services/ai_service.py — all Claude API calls live here:
  1. draft_email()   — personalized outreach email per journalist
  2. score_author()  — relevance score + beat tag for a journalist
  3. chat()           — conversational assistant that can query the local DB

Requires ANTHROPIC_API_KEY in the environment (see .env.example).
"""
import os
import json
import re

import anthropic
import db

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def _client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to backend/.env to enable AI features."
        )
    return anthropic.Anthropic(api_key=api_key)


def draft_email(author: dict, campaign_context: str, sender_name: str = "", sender_org: str = ""):
    """Generate a short, personalized pitch email for one journalist."""
    client = _client()

    profile = (
        f"Name: {author.get('name')}\n"
        f"Outlet: {author.get('outlet')}\n"
        f"Title: {author.get('title') or 'Unknown'}\n"
        f"Beat: {author.get('beat') or 'Unknown'}\n"
        f"Bio: {(author.get('bio') or '')[:500]}\n"
    )

    system = (
        "You write short, specific media pitch emails for a PR/outreach team. "
        "Never invent facts about the journalist that aren't given to you. "
        "Keep it under 150 words, no generic flattery, no subject-line clickbait. "
        "Reference something concrete from their beat or bio if available. "
        "Respond ONLY with JSON: {\"subject\": str, \"body\": str} and nothing else."
    )
    user_msg = (
        f"Journalist profile:\n{profile}\n\n"
        f"Campaign / pitch context:\n{campaign_context}\n\n"
        f"Sender: {sender_name or '[Your name]'} at {sender_org or '[Your company]'}"
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(text, fallback={"subject": "Quick question for you", "body": text})
    return data


def score_author(author: dict, campaign_context: str = ""):
    """Score relevance (1-5) and assign a beat tag for a journalist."""
    client = _client()

    profile = (
        f"Name: {author.get('name')}\n"
        f"Outlet: {author.get('outlet')}\n"
        f"Title: {author.get('title') or 'Unknown'}\n"
        f"Bio: {(author.get('bio') or '')[:600]}\n"
    )
    system = (
        "You triage journalist contact records for a PR outreach database. "
        "Given a journalist's profile and (optionally) a campaign description, "
        "return ONLY JSON: {\"score\": int 1-5, \"beat\": short string (2-3 words), "
        "\"rationale\": one sentence, \"summary\": one-sentence neutral summary of who they are}. "
        "Score 5 = perfect fit / clearly covers this exact topic; 1 = unrelated beat. "
        "If no campaign context is given, score general newsworthiness/seniority instead."
    )
    user_msg = f"Profile:\n{profile}\n\nCampaign context: {campaign_context or '(none given — score general fit)'}"

    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(text, fallback={"score": None, "beat": "", "rationale": "", "summary": ""})
    return data


def chat(session_id: str, message: str):
    """Conversational assistant with read access to dashboard stats + author search."""
    client = _client()

    history = db.get_chat_history(session_id, limit=12)
    db.add_chat_message(session_id, "user", message)

    stats = db.stats()
    # Give the model a lightweight, current snapshot of the DB instead of full tool-calling
    # round trips, plus a targeted search if the message looks like it's asking about someone.
    context_blocks = [f"Database snapshot: {json.dumps(stats)[:1500]}"]

    search_term = _guess_search_term(message)
    if search_term:
        matches = db.list_authors(search=search_term, limit=8)
        if matches:
            slim = [{"name": m["name"], "outlet": m["outlet"], "title": m["title"],
                     "email": bool(m["email"]), "beat": m["beat"]} for m in matches]
            context_blocks.append(f"Matching authors for '{search_term}': {json.dumps(slim)}")

    system = (
        "You are the AI assistant inside MediaWire, a journalist-database and outreach dashboard. "
        "Answer questions about the scraped database using the provided snapshot/context. "
        "Be concise and concrete. If asked to do something the data can't support, say so plainly. "
        "You cannot browse the live web or send emails yourself — you can only reason over what's "
        "in the local database snapshot given to you."
    )

    msgs = []
    for h in history[-10:]:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": message + "\n\n[Context]\n" + "\n".join(context_blocks)})

    resp = client.messages.create(
        model=MODEL, max_tokens=700, system=system, messages=msgs,
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    db.add_chat_message(session_id, "assistant", text)
    return text


def _guess_search_term(message: str):
    """Very light heuristic: pull a capitalized name-like phrase out of the message."""
    m = re.search(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})\b", message)
    return m.group(1) if m else ""


def _parse_json(text, fallback):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        return fallback
