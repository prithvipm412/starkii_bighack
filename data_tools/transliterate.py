"""Transliterate native Indic script into casual Latin-script text."""
import argparse


def transliterate_texts(texts, language="Kannada"):
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
    except ImportError as exc:
        raise RuntimeError("install indic-transliteration to create Latin variants") from exc
    code = language.lower()
    source = {
        "kannada": sanscript.KANNADA, "kn": sanscript.KANNADA,
        "hindi": sanscript.DEVANAGARI, "hi": sanscript.DEVANAGARI,
        "marathi": sanscript.DEVANAGARI, "mr": sanscript.DEVANAGARI,
        "nepali": sanscript.DEVANAGARI, "ta": sanscript.TAMIL, "tamil": sanscript.TAMIL,
        "te": sanscript.TELUGU, "telugu": sanscript.TELUGU,
        "ml": sanscript.MALAYALAM, "malayalam": sanscript.MALAYALAM,
        "bn": sanscript.BENGALI, "bengali": sanscript.BENGALI,
        "gu": sanscript.GUJARATI, "gujarati": sanscript.GUJARATI,
        "pa": sanscript.GURMUKHI, "punjabi": sanscript.GURMUKHI,
    }.get(code)
    if source is None:
        raise ValueError(f"no indic-transliteration script mapping for {language!r}")
    # ITRANS is a familiar informal Latin convention for typing Indic languages.
    return [transliterate(text, source, sanscript.ITRANS) for text in texts]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("texts", nargs="+")
    parser.add_argument("--language", default="Kannada")
    args = parser.parse_args()
    try:
        print("\n".join(transliterate_texts(args.texts, args.language)))
    except Exception as exc:
        parser.error(f"transliteration failed: {exc}")


if __name__ == "__main__":
    main()
