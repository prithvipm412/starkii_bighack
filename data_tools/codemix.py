"""Create a simple rule-based code-mix from a translated sentence.

The rule keeps uppercase names, identifiers containing digits, and underscore
technical terms in English when IndicTrans2's entity-protected translation has
retained them; it otherwise leaves the translated wording as generated. This
conservative approach avoids unsafe word-position alignment between languages.
"""
import argparse
import re
from .transliterate import transliterate_texts
from .translate import translate_texts

TECHNICAL = re.compile(r"\b(?:[A-Z][A-Za-z0-9+./_-]*|[A-Za-z]*\d[A-Za-z0-9+./_-]*|[A-Za-z]+(?:_[A-Za-z0-9]+)+)\b")
GLOSSARY = re.compile(r"\b(?:API|AI|LLM|Python|database|server|code|internet|model|data|prompt|token)\b", re.I)
TERM_PATTERN = re.compile(f"(?:{GLOSSARY.pattern})|(?:{TECHNICAL.pattern})")


def code_mix_texts(texts, language="Kannada", latin=False, device=None):
    masked, terms_by_row = [], []
    for text in texts:
        terms = []
        def replace(match):
            term = match.group(0)
            marker = f"ZXQTERM{len(terms)}QXZ"
            terms.append((marker, term))
            return marker
        prepared = TERM_PATTERN.sub(replace, text)
        masked.append(prepared)
        terms_by_row.append(terms)
    translated = translate_texts(masked, language, device=device)
    for idx, terms in enumerate(terms_by_row):
        for marker, term in terms:
            translated[idx] = re.sub(re.escape(marker), lambda _: term, translated[idx], flags=re.I)
    if latin:
        translated = transliterate_texts(translated, language)
    return translated


def codemix_text(source, translated, language="Kannada", latin=False):
    # Retained as a single-item convenience API; proper noun/term masking happens
    # before translation in code_mix_texts so it cannot rely on word alignment.
    result = translated
    return transliterate_texts([result], language)[0] if latin else result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--language", default="Kannada")
    parser.add_argument("--latin", action="store_true")
    args = parser.parse_args()
    try:
        print(code_mix_texts([args.source], args.language, args.latin)[0])
    except Exception as exc:
        parser.error(f"code-mixing failed: {exc}")


if __name__ == "__main__":
    main()
