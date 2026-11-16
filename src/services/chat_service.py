"""HR Studio chatbot: drafts custom letters (bonafide, etc.) in DataPattern's house style."""

import re
from difflib import SequenceMatcher
from datetime import date
from functools import lru_cache

import requests

from src.constants.constants import (
    BUILTIN_LETTER_PATTERNS, BUILTIN_LETTER_PHRASES, FUZZY_MATCH_THRESHOLD, CHAT_KNOWLEDGE_CHAR_LIMIT, LETTER_TYPES, CHAT_KNOWLEDGE_TEMPLATES, COMPANY_ADDRESS, COMPANY_NAME, CUSTOM_LETTER_TYPE,
    MIME_DOCX, MIME_PDF,
)
from src.constants.letter_guide import EXAMPLES, guide_text
from src.repositories.template_repository import _template_path, load_template_document
from src.services.document_service import _document_paragraphs
from src.services.export_service import generate_letter_docx, generate_letter_pdf
from src.services.preview_service import build_letter_html
from src.settings.settings import settings
from src.utils import error_codes
from src.utils.custom_app_exception import AppException
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_TURNS = 40
MAX_TOKENS = 2000

LETTER_PATTERN = re.compile(r'<letter\s+name="([^"]*)"\s+recipient="([^"]*)"\s*>(.*?)</letter>', re.DOTALL)
REQUEST_TIMEOUT = 90
BUILTIN_TAG_PATTERN = re.compile(r"<builtin>\s*([a-z_]+)\s*</builtin>")
ASK_PATTERN = re.compile(r"<ask>(.*?)</ask>", re.DOTALL)
MAX_ASK_FIELDS = 8
FIELD_TYPES = {"text", "date", "number", "textarea"}
SIGNOFF_PATTERN = re.compile(r"^(for\s+datapattern|regards|sincerely|yours|thanks?|best regards)", re.IGNORECASE)


@lru_cache(maxsize=1)
def _template_knowledge():
    """Plain text of a few built-in templates, so generated letters match house style."""
    parts = []
    for key in CHAT_KNOWLEDGE_TEMPLATES:
        path = _template_path({"letter_type": key})
        if not path:
            continue
        try:
            text = "\n\n".join(p.text.strip() for p in _document_paragraphs(load_template_document(path)) if p.text.strip())
        except Exception:
            logger.exception("Could not read template %s", key)
            continue
        parts.append(f"--- Template: {key} ---\n{text[:CHAT_KNOWLEDGE_CHAR_LIMIT]}")
    return "\n\n".join(parts)


def _system_prompt():
    return f"""You are HR Studio, the letter-drafting assistant for {COMPANY_NAME}'s HR team.
You can write ANY kind of letter, certificate or HR/business document the user asks for: bonafide, address proof, salary certificate, NOC, employment verification, warning, appreciation, recommendation, promotion, transfer, resignation acceptance, notice, circular, visa/bank/embassy letters, and anything else not listed here.

Company address: {COMPANY_ADDRESS}
Today's date: {date.today().strftime('%d %B %Y')}

How to work:
- When the user asks for a letter, draft it right away if you have enough to write a sensible one (usually the person's name is enough).
- If an important detail is missing (think about what that specific kind of letter normally needs: a salary certificate needs the salary, a bonafide benefits from role/department and joining date, a warning letter needs the reason and date, a recommendation needs the relationship and strengths), ask for it ONCE using a form, never as a sentence of questions. Write one short line (e.g. "Please fill in these details, or leave blank to skip."), then the fields in exactly this format, one per line as "Label" or "Label | type" where type is text, date, number or textarea (default text):
<ask>
Employee name
Role
Joining date | date
Employment status
</ask>
  Only list details you don't already know. Never include the person's name field if the user already gave it. The user fills the form; blank fields mean skip.
- If the user doesn't provide a detail, or says to skip it, do NOT ask again and never invent facts: leave that detail out and word the letter so it reads naturally without it.
- Refer to people as "they/their" (or by name) unless the user states their pronouns or title; never guess gender from a name.
- Never leave [bracket] placeholders in the letter. Never invent names, dates, amounts or IDs.
- When the user asks for edits, output the complete revised letter again.
- To deliver a letter, write one short line of chat text, then the letter in exactly this format (nothing after the closing tag):
<letter name="Bonafide Certificate" recipient="Ravi">
Date: 14 October 2026

To Whom It May Concern,

...paragraphs separated by a blank line...
</letter>
  The letter text contains only the date line, salutation and content: no letterhead, no title, no sign-off, no "Regards"/"For DataPattern" line, no signature (all added automatically). Use <letter> tags only for a finished letter. When you ask the user a question, reply with the question only and NO <letter> block; ask first, write the letter after they answer.
- The app already has built-in step-by-step forms for these letters (key: name): {", ".join(f"{k}: {v['name']}" for k, v in LETTER_TYPES.items())}. If the user's request, even misspelled, is for one of them, reply with ONLY <builtin>key</builtin> and nothing else (e.g. <builtin>offer</builtin>). Never draft those yourself.
- Keep chat replies short. After generating, say in one line what you produced and offer to adjust it.
- Match the tone, wording and structure of the company's existing letters below. Use them only as style/knowledge reference; do not copy details of the people named in them.

{guide_text()}

How conversations should go (imitate this flow and tone; ignore the names/dates in the examples):

{EXAMPLES}

Existing company templates for reference:

{_template_knowledge()}"""


def _clean_messages(messages):
    cleaned = []
    for message in (messages or [])[-MAX_TURNS:]:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content})
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    if not cleaned or cleaned[-1]["role"] != "user":
        raise AppException(error_codes.CHAT_FAILED, "Please type a message first.")
    return cleaned


def _details(letter):
    return {"letter_type": CUSTOM_LETTER_TYPE, "letter_name": letter["letter_name"], "name": letter["recipient_name"]}


def _strip_signoff(body):
    """The export adds its own sign-off, so drop any the model wrote at the end."""
    paragraphs = body.split("\n\n")
    while len(paragraphs) > 1 and SIGNOFF_PATTERN.match(paragraphs[-1].strip()):
        paragraphs.pop()
    return "\n\n".join(paragraphs)


def _parse_fields(block):
    """'Label' or 'Label | type' lines from the model's <ask> block -> [{label, type}]."""
    fields = []
    for line in block.splitlines():
        label, _, kind = (part.strip() for part in line.strip(" -*\t").partition("|"))
        if label:
            fields.append({"label": label[:60], "type": kind.lower() if kind.lower() in FIELD_TYPES else "text"})
    return fields[:MAX_ASK_FIELDS]


def _complete(system, messages):
    host = settings.databricks_host.strip().rstrip("/")
    if not host.startswith("http"):
        host = f"https://{host}"
    try:
        response = requests.post(
            f"{host}/serving-endpoints/{settings.databricks_model}/invocations",
            headers={"Authorization": f"Bearer {settings.databricks_token}"},
            json={"messages": [{"role": "system", "content": system}, *messages], "max_tokens": MAX_TOKENS, "temperature": 0.3},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return (response.json()["choices"][0]["message"]["content"] or "").strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        logger.exception("Chat request failed")
        raise AppException(error_codes.CHAT_FAILED, f"The assistant is unavailable right now: {exc}")


def _fuzzy_builtin_letter(text):
    """Typo-tolerant match ("intership certificate"): best fuzzy phrase hit above the threshold."""
    words = re.findall(r"[a-z]+", (text or "").lower())
    best, best_key = (0.0, 0), None
    for key, phrases in BUILTIN_LETTER_PHRASES.items():
        for phrase in phrases:
            size = len(phrase.split())
            for start in range(len(words) - size + 1):
                score = SequenceMatcher(None, " ".join(words[start:start + size]), phrase).ratio()
                if score >= FUZZY_MATCH_THRESHOLD and (score, size) > best:
                    best, best_key = (score, size), key
    return best_key


def _builtin_letter(text):
    """Letter-type key if the message asks for one of the app's built-in letters."""
    for key, pattern in BUILTIN_LETTER_PATTERNS:
        if re.search(pattern, text or "", re.IGNORECASE):
            return key
    return _fuzzy_builtin_letter(text)


def _redirect_response(key):
    name = LETTER_TYPES[key]["name"]
    return {
        "success": True,
        "reply": f"The {name} is one of our built-in letters. Taking you to the details form...",
        "letter": None,
        "redirect": {"letter_type": key, "letter_name": name},
    }


def chat(data):
    if not (settings.databricks_host and settings.databricks_token):
        raise AppException(
            error_codes.CHAT_FAILED, "The chatbot isn't configured: set DATABRICKS_HOST and DATABRICKS_TOKEN in the .env file."
        )
    messages = _clean_messages(data.get("messages"))
    builtin = _builtin_letter(messages[-1]["content"])
    if builtin:
        return _redirect_response(builtin)
    text = _complete(_system_prompt(), messages)

    asked = ASK_PATTERN.search(text)
    if asked:
        fields = _parse_fields(asked.group(1))
        if fields:
            intro = (text[:asked.start()] + text[asked.end():]).strip()
            intro = LETTER_PATTERN.sub("", intro).strip()
            reply = intro or "Please fill in these details, or leave blank to skip."
            labels = "\n".join(field["label"] for field in fields)
            return {
                "success": True, "reply": reply, "letter": None, "fields": fields,
                "history_text": f"{reply}\n<ask>\n{labels}\n</ask>",
            }

    tagged = BUILTIN_TAG_PATTERN.search(text)
    if tagged and tagged.group(1).strip() in LETTER_TYPES:
        return _redirect_response(tagged.group(1).strip())

    match = LETTER_PATTERN.search(text)
    if not match:
        return {"success": True, "reply": text or "Could you tell me a bit more about the letter you need?", "letter": None}

    letter = {
        "letter_name": match.group(1).strip() or "Letter",
        "recipient_name": match.group(2).strip() or "Candidate",
        "body": _strip_signoff(match.group(3).strip()),
    }
    if "?" in text[:match.start()]:
        # The model asked a question first; wait for the answer instead of showing a premature letter.
        return {"success": True, "reply": text[:match.start()].strip(), "letter": None}
    reply = text[:match.start()].strip() or text[match.end():].strip() or f"Here is the {letter['letter_name']}. Let me know if you'd like any changes."
    return {
        "success": True,
        "reply": reply,
        "letter": letter,
        "preview_html": build_letter_html(_details(letter), letter["body"]),
        # Sent back by the client as history so later edits can build on this draft.
        "history_text": f'{reply}\n\n<letter name="{letter["letter_name"]}" recipient="{letter["recipient_name"]}">\n{letter["body"]}\n</letter>',
    }


def build_download(data):
    """Return (file_bytes, filename, mimetype) for a chatbot letter."""
    letter = {
        "letter_name": (data.get("letter_name") or "Letter").strip(),
        "recipient_name": (data.get("recipient_name") or "Candidate").strip(),
        "body": (data.get("body") or "").strip(),
    }
    if not letter["body"]:
        raise AppException(error_codes.LETTER_DETAILS_MISSING, "There is no letter to download yet.")
    details = _details(letter)
    try:
        docx, filename = generate_letter_docx(details, letter["body"])
        if (data.get("format") or "word").lower() == "pdf":
            return generate_letter_pdf(details, letter["body"]), filename.replace(".docx", ".pdf"), MIME_PDF
        return docx, filename, MIME_DOCX
    except Exception as exc:
        logger.exception("Chat letter download failed")
        raise AppException(error_codes.DOWNLOAD_FAILED, f"Unable to create the download: {exc}")
