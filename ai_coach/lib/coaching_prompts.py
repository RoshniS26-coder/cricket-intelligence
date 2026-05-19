"""
Prompts and JSON schema for extracting structured coaching guidance from
expert explainer videos (Hindi / English / Hinglish).

Different from the few-shot critique prompts: those compare a student to
visual references. These EXTRACT teachable knowledge from a coach's spoken
explanation so it can be used as injected context in later critiques and
briefings.

All teachable text fields are stored bilingually as {en, hi} regardless of
the source video language — see _BILINGUAL_TEXT below. Downstream consumers
should use coaching_extractor._bilingual_en() to render English.
"""

COACHING_EXTRACT_SYSTEM_PROMPT = (
    "You are an expert cricket coach, transcriber, and translator. You watch a "
    "coaching tutorial video — the audio may be in Hindi, English, Hinglish, or "
    "another Indian language. You extract the technique knowledge being taught "
    "and emit it BILINGUALLY: every teachable text field has both an English "
    "version (clean Indian academy register) and a Hindi version (Devanagari "
    "script). If the coach speaks Hindi, the Hindi field is a faithful "
    "transcription and the English field is a clean translation. If the coach "
    "speaks English, the English field is the transcription and you produce a "
    "natural Hindi translation a coach would actually say. If the coach speaks "
    "Hinglish, separate the two languages cleanly. Be faithful to the coach's "
    "words — do not add advice they did not give."
)


COACHING_EXTRACT_PROMPT_TEMPLATE = """Watch this cricket coaching tutorial video. Extract the technique guidance being taught.

Subject of this tutorial: {subject_hint}
Spoken language(s): the coach may speak in Hindi, English, Hinglish, or any combination — handle gracefully.

ALWAYS PRODUCE BILINGUAL CONTENT
For every teachable text field — `point`, `coaching_cues[]`, `common_mistakes[]`, `ideal_outcome` — emit BOTH:
  - `en`: clean English (Indian academy register: "front foot," "head over the ball," "weight transfer")
  - `hi`: natural Hindi in Devanagari script (academy/coach register, e.g. "सर गेंद के ऊपर", "नज़र गेंद पर")
This holds regardless of the coach's spoken language. If they speak Hindi, `hi` is the transcription and `en` is your translation. If they speak English, `en` is the transcription and `hi` is your translation. If Hinglish, separate cleanly.

Your job:

1. **Identify the shot or skill** being explained (e.g. cover_drive, pull, front_foot_defence).
2. **Identify the reference player** the coach cites (if any — e.g. "Virat Kohli", "Sachin Tendulkar"). If no specific player is named, set to empty string.
3. **Extract 4–8 KEY TECHNIQUE POINTS** the coach emphasizes. Each point must be:
   - A direct paraphrase of something the coach actually said or showed
   - One declarative, actionable sentence
   - Provided as `point: {{en, hi}}` (bilingual; see rule above)
   - Tagged with the body region or aspect it addresses (head | stance | grip | backlift | front_foot | back_foot | bat_swing | weight_transfer | balance | follow_through | eye_line | shoulder | hip | other)
4. **Extract DRILLS** the coach demonstrates or recommends. For each:
   - `drill_name` (English label — the coach's name, or a descriptive label if unnamed)
   - `equipment` (English)
   - `duration_minutes` (integer)
   - `addresses_aspect` (one of the aspect labels above)
5. **Extract COMMON MISTAKES** the coach warns against. Each item is `{{en, hi}}` — short phrase in both languages, e.g. en="head falls across the line", hi="सर लाइन के पार गिरता है".
6. **Extract COACHING CUES** — short verbal prompts a coach uses with a player. Each item is `{{en, hi}}` — e.g. en="eyes on the ball", hi="नज़र गेंद पर".
7. **Identify the IDEAL OUTCOME** of the shot when played correctly — one sentence, bilingual `{{en, hi}}` (what should happen visually / where should the ball go).
8. **language_detected**: the coach's actual spoken language (e.g. hindi, english, hinglish, marathi). This is metadata — the bilingual fields above are produced regardless.
9. **Confidence**: 0.0–1.0 — how confidently you understood the spoken content. Lower this if audio was unclear or language was very mixed.

Stay faithful to the coach. Do not invent corrections they didn't mention. Do not generalize beyond what was taught.

Return strict JSON matching the provided schema. No markdown, no commentary outside the JSON."""


_BILINGUAL_TEXT = {
    "type": "object",
    "description": "A teachable text snippet rendered in both English and Hindi.",
    "properties": {
        "en": {"type": "string", "description": "Clean English in Indian academy register."},
        "hi": {"type": "string", "description": "Natural Hindi in Devanagari script."}
    },
    "required": ["en", "hi"]
}


COACHING_EXTRACT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "shot_or_skill": {
            "type": "string",
            "description": "e.g. cover_drive, pull, front_foot_defence, bowling_yorker"
        },
        "reference_player": {
            "type": "string",
            "description": "Player the tutorial cites as the canonical example. Empty string if none."
        },
        "language_detected": {
            "type": "string",
            "description": "Coach's spoken language: hindi, english, hinglish, marathi, etc. Metadata only — output is always bilingual."
        },
        "key_technique_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": _BILINGUAL_TEXT,
                    "aspect": {
                        "type": "string",
                        "enum": [
                            "head", "stance", "grip", "backlift",
                            "front_foot", "back_foot", "bat_swing",
                            "weight_transfer", "balance", "follow_through",
                            "eye_line", "shoulder", "hip", "other"
                        ]
                    }
                },
                "required": ["point", "aspect"]
            }
        },
        "drills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "drill_name": {"type": "string"},
                    "equipment": {"type": "string"},
                    "duration_minutes": {"type": "integer"},
                    "addresses_aspect": {"type": "string"}
                },
                "required": ["drill_name"]
            }
        },
        "common_mistakes": {
            "type": "array",
            "items": _BILINGUAL_TEXT
        },
        "coaching_cues": {
            "type": "array",
            "items": _BILINGUAL_TEXT
        },
        "ideal_outcome": _BILINGUAL_TEXT,
        "extraction_confidence": {"type": "number"}
    },
    "required": [
        "shot_or_skill",
        "key_technique_points",
        "common_mistakes",
        "coaching_cues",
        "ideal_outcome"
    ]
}


def get_coaching_system_prompt() -> str:
    return COACHING_EXTRACT_SYSTEM_PROMPT


def get_coaching_extract_prompt(subject_hint: str = "unknown shot or skill") -> str:
    return COACHING_EXTRACT_PROMPT_TEMPLATE.format(subject_hint=subject_hint)
