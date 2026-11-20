"""Prompt loading (CLAUDE.md prompt format) + a simple English / non-English detector.

Prompt line: {"prompt_id", "split": harmful|harmless|direction, "category", "source",
              "variant": en|kn|kn_latn|kn_mix, "text"}
All variants of a prompt share prompt_id, so a row's key is (prompt_id, variant).
Direction rows: split == "direction", category == "harmful" | "harmless" tells the two sides apart.
"""
import json
import re

# Indic scripts: Devanagari .. Malayalam, U+0900-U+0D7F
INDIC_RE = re.compile(r"[ऀ-ൿ]")
SCRIPT_TO_IT2 = [  # (start, end, IndicTrans2 code)
    (0x0900, 0x097F, "hin_Deva"), (0x0980, 0x09FF, "ben_Beng"), (0x0A00, 0x0A7F, "pan_Guru"),
    (0x0A80, 0x0AFF, "guj_Gujr"), (0x0B00, 0x0B7F, "ory_Orya"), (0x0B80, 0x0BFF, "tam_Taml"),
    (0x0C00, 0x0C7F, "tel_Telu"), (0x0C80, 0x0CFF, "kan_Knda"), (0x0D00, 0x0D7F, "mal_Mlym"),
]

# Frequent romanized Kannada (and some Hindi) words, lowercased; chosen to be rare as English words.
ROMANIZED_WORDS = set("""
enu yenu enenu hege hegey hEge maadi madi maadu madu maaDi maaDu beku illa ide idhe idu adu
nanage nange neevu neenu ninna nanna nimma namma yaake yake heli helu hELi hogu baa banni swalpa
tumba mattu alli inda haagu hagu aadare adre ella elli yaaru yavudu kodi kodu sigutte aagutte
maadodu maaduvudu maaDuvudu bEku hELu sahaaya sahaya upaaya dayavittu
hai hain kya kaise kaisa kyun nahi nahin mujhe mera meri karna karo batao chahiye
""".lower().split())
# Kannada suffixes on Latin words (locative, accusative, dative, verbal noun, ...)
KN_SUFFIX_RE = re.compile(r"[a-z]{2,}(alli|annu|inda|ige|ige|uvudu|odu|ide|ali|agi|aagi|ante|alla)$")
# ITRANS-style mid-word capitals produced by data_tools.transliterate (e.g. "mADu", "hEge", "bAMb")
ITRANS_RE = re.compile(r"^[a-z~.]*[a-z][ADTNLMRSHEIOU~.][a-zA-Z~.]*$")


def script_lang(text):
    """IndicTrans2 source code of the dominant Indic script in text, or None if no Indic chars."""
    counts = {}
    for ch in text or "":
        o = ord(ch)
        if 0x0900 <= o <= 0x0D7F:
            for a, b, code in SCRIPT_TO_IT2:
                if a <= o <= b:
                    counts[code] = counts.get(code, 0) + 1
                    break
    return max(counts, key=counts.get) if counts else None


def is_romanized_indic(text, min_hits=2, min_frac=0.2):
    words = re.findall(r"[A-Za-z~.]+", text or "")
    words = [w.strip(".") for w in words if w.strip(".")]
    if not words:
        return False
    hits = sum(w.lower() in ROMANIZED_WORDS or bool(KN_SUFFIX_RE.match(w.lower())) or bool(ITRANS_RE.match(w))
               for w in words)
    return hits >= min(min_hits, len(words)) and hits / len(words) >= min_frac


def is_non_english(text):
    """True if text has Indic script or looks like romanized / code-mixed Indic."""
    return bool(INDIC_RE.search(text or "")) or is_romanized_indic(text)


def load_prompts(path, splits=None, limit=None):
    """Rows in file order; splits = set of split values to keep (None = all). limit = first N
    distinct prompt_ids (all their variants kept)."""
    rows, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                print(f"[data] skipping bad JSON on line {i + 1}")
                continue
            if not r.get("text") or not r.get("prompt_id"):
                print(f"[data] line {i + 1}: missing text/prompt_id, skipped")
                continue
            row = {"prompt_id": str(r["prompt_id"]), "split": r.get("split", ""),
                   "category": r.get("category", ""), "source": r.get("source", ""),
                   "variant": r.get("variant", "en"), "text": r["text"]}
            if splits and row["split"] not in splits:
                continue
            key = (row["prompt_id"], row["variant"])
            if key in seen:  # duplicates would break resume
                print(f"[data] duplicate {key} skipped")
                continue
            seen.add(key)
            rows.append(row)
    if limit:
        keep, ids = set(), []
        for r in rows:
            if r["prompt_id"] not in keep and len(keep) < limit:
                keep.add(r["prompt_id"])
        rows = [r for r in rows if r["prompt_id"] in keep]
    return rows
