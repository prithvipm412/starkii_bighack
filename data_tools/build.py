"""Build English, native-script, Latin-script and code-mixed JSONL variants."""
import argparse
from .common import read_jsonl, text_field, write_jsonl
from .translate import translate_texts
from .transliterate import transliterate_texts
from .codemix import code_mix_texts


def build(input_path, output_path, language="Kannada", device=None, mix_latin=False):
    rows = read_jsonl(input_path)
    texts = [row[text_field(row)] for row in rows]
    translated = translate_texts(texts, language, device=device)
    if len(translated) != len(rows):
        raise RuntimeError("translator returned a different number of prompts than it received")
    latin = transliterate_texts(translated, language)
    variants = {"en": texts, "kn": translated, "kn_latn": latin,
                "kn_mix": code_mix_texts(texts, language, latin=mix_latin, device=device)}
    code = {"kannada": "kn", "hindi": "hi", "tamil": "ta", "telugu": "te",
            "malayalam": "ml", "bengali": "bn", "marathi": "mr", "gujarati": "gu",
            "punjabi": "pa", "odia": "or", "assamese": "as"}.get(language.lower(), language.lower())
    output_rows = []
    for row, source_text, idx in zip(rows, texts, range(len(rows))):
        field = text_field(row)
        for variant, content in variants.items():
            item = dict(row)
            item[field] = content[idx]
            item["variant"] = variant if variant == "en" else variant.replace("kn", code, 1)
            output_rows.append(item)
    write_jsonl(output_path, output_rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", required=True)
    parser.add_argument("--out", dest="output_path", required=True)
    parser.add_argument("--language", default="Kannada")
    parser.add_argument("--device", choices=("mps", "cpu"))
    parser.add_argument("--mix-latin", action="store_true", help="write the code-mixed variant in Latin script")
    args = parser.parse_args()
    try:
        count = build(args.input_path, args.output_path, args.language, args.device, args.mix_latin)
        print(f"Wrote {count * 4} rows ({count} prompts × 4 variants) to {args.output_path}")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
