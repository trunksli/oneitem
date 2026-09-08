"""
The hourly theme taxonomy.

Deliberately a plain list rather than a database enum: this is the knob most
likely to be tuned, and a native Postgres enum would need an ALTER TYPE
migration every time a theme is added or renamed. Themes are validated in
application code instead, and unknown values fall back to "Curious".

Two axes, borrowed from how Fark labels links. Fark's tags are mostly *tone*
("tells the reader what to expect") rather than subject, which is why its front
page reads as varied even when the underlying subjects repeat. ONE keeps subject
themes for rotation, but the tone axis is what stops a day of well-scored
science from feeling like homework.
"""

# Subject themes, used for the hourly rotation label.
# Mainstream anchors first, offbeat ones after - the mix is intentional.
THEMES = [
    # Sciences and the physical world
    "Bioscience",
    "Space",
    "Nature",
    "Health",
    "Psychology",
    "Medicine",
    # Making and building
    "Engineering",
    "Architecture",
    "Technology",
    "Design",
    # People and the past
    "History",
    "Anthropology",
    "Language",
    "Money",
    "Crime",
    # Culture and taste
    "Art",
    "Music",
    "Film & TV",
    "Books",
    "Fashion",
    "Food",
    "Sport",
    "Games",
    # The offbeat end
    "Internet Culture",
    "Sex & Relationships",
    "Oddities",
    "Mysteries",
    "Curious",
]

DEFAULT_THEME = "Curious"

# Tone, tracked alongside the subject so the schedule can be paced rather than
# just rotated. A day of nothing but "Fascinating" is as monotonous as a day of
# nothing but Engineering.
TONES = [
    "Fascinating",   # the default: genuinely interesting
    "Delightful",    # charming, warm, funny
    "Unsettling",    # eerie, dark, uncomfortable
    "Impressive",    # craft, skill, scale
    "Baffling",      # absurd, inexplicable
    "Moving",        # sad, tender, human
    "Useful",        # you will actually do something with this
]

DEFAULT_TONE = "Fascinating"

# Old enum member names -> current labels, so rows written before themes became
# free text keep rendering correctly after the migration.
LEGACY_THEME_NAMES = {
    "BIOSCIENCE": "Bioscience",
    "AI": "Technology",
    "WEIRD_FOOD": "Food",
    "ARCHITECTURE": "Architecture",
    "GAMING": "Games",
    "ODDBALL": "Oddities",
    "RANDOM": "Curious",
    "HISTORY": "History",
    "ENGINEERING": "Engineering",
    "CULTURE": "Internet Culture",
}


def normalize_theme(value):
    """Coerce anything the model or an old row supplies into a known theme."""
    if not value:
        return DEFAULT_THEME
    text = str(value).strip()
    if text in THEMES:
        return text
    if text.upper() in LEGACY_THEME_NAMES:
        return LEGACY_THEME_NAMES[text.upper()]
    # Tolerate case and spacing drift from the model ("pop culture", "SPACE")
    for theme in THEMES:
        if theme.lower() == text.lower():
            return theme
    return DEFAULT_THEME


def normalize_tone(value):
    if not value:
        return DEFAULT_TONE
    text = str(value).strip()
    for tone in TONES:
        if tone.lower() == text.lower():
            return tone
    return DEFAULT_TONE
