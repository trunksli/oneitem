"""
Preview text: the two sentences that let someone decide without clicking.

The naive source -- a YouTube description or the first text scraped off an
article page -- is usually not the gist at all. Descriptions open with sponsor
reads and Patreon links; scraped pages open with cookie banners and nav chrome.
So candidate previews are quality-checked, and anything that fails falls back to
a purpose-written LLM summary of the actual content.
"""
import re

# Markers of sponsor reads, nav furniture and site chrome rather than content.
BOILERPLATE_PATTERNS = [
    r'https?://',
    r'\bsubscribe\b', r'\bsponsor(ed|ship)?\b', r'\bpatreon\b', r'\bpromo code\b',
    r'\bcheck out\b', r'\bsign up\b', r'\buse code\b', r'\bdiscount\b',
    r'\bfree trial\b', r'\bmerch\b', r'\bfollow (me|us)\b', r'\bnewsletter\b',
    r'\bclick here\b', r'\bread later\b', r'\bsave article\b', r'\bcomments?\b',
    r'\bcookie', r'\baccept all\b', r'\bsign in\b', r'\bshare this\b',
    r'\badvertisement\b', r'\ball rights reserved\b', r'\bskip to content\b',
]

_BOILERPLATE = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)

MIN_PREVIEW_CHARS = 60


def looks_like_boilerplate(text):
    """True if this reads like a sponsor pitch or page furniture, not content."""
    if not text:
        return True
    cleaned = text.strip()
    if len(cleaned) < MIN_PREVIEW_CHARS:
        return True
    if _BOILERPLATE.search(cleaned):
        return True
    # Scraped nav often has very few sentence endings across a long run of words
    if len(cleaned) > 200 and cleaned.count(".") < 1:
        return True
    return False


def is_usable(text):
    return not looks_like_boilerplate(text)


def choose_preview(*candidates):
    """First usable candidate, else the first non-empty one, else ''."""
    for text in candidates:
        if text and is_usable(text):
            return text.strip()
    for text in candidates:
        if text and text.strip():
            return text.strip()
    return ""


GIST_PROMPT = """You are writing a two-sentence preview for a content curation site.

Describe what this {kind} actually IS and what the reader or viewer will get from
it, so someone can decide whether to open it without clicking through.

Rules:
- Exactly two sentences, plain and concrete.
- Describe the content. Do not sell it, do not use marketing language.
- Ignore any sponsor messages, subscription pitches, or navigation text.
- Do not repeat the title back.
- Do not invent anything that is not in the material below.

Title: {title}
Publication or creator: {creator}
Material:
{body}

Return JSON: {{"gist": "..."}}"""


def build_gist_prompt(candidate, body, kind="article"):
    return GIST_PROMPT.format(
        kind=kind,
        title=candidate.title or "",
        creator=candidate.creator_name or "",
        body=(body or "")[:4000],
    )
