"""Translate English prompt strings with AI4Bharat IndicTrans2."""
import argparse
from .common import language_code

MODEL = "ai4bharat/indictrans2-en-indic-1B"
TARGET_CODES = {"kn": "kan_Knda", "hi": "hin_Deva", "ta": "tam_Taml", "te": "tel_Telu",
                "ml": "mal_Mlym", "bn": "ben_Beng", "mr": "mar_Deva", "gu": "guj_Gujr",
                "pa": "pan_Guru", "or": "ory_Orya", "as": "asm_Beng"}


def translate_texts(texts, language="Kannada", model_name=MODEL, device=None, batch_size=4):
    code = language_code(language)
    if code not in TARGET_CODES:
        raise ValueError(f"unsupported IndicTrans2 target language {language!r}")
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from IndicTransToolkit import IndicProcessor
    except ImportError as exc:
        raise RuntimeError("install torch, transformers, and IndicTransToolkit to translate") from exc
    device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True).to(device)
    processor = IndicProcessor(inference=True)
    results = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        prepared = processor.preprocess_batch(batch, src_lang="eng_Latn", tgt_lang=TARGET_CODES[code])
        encoded = tokenizer(prepared, return_tensors="pt", padding="longest", truncation=True, max_length=256).to(device)
        with torch.inference_mode():
            generated = model.generate(**encoded, max_length=256, num_beams=5)
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        results.extend(processor.postprocess_batch(decoded, lang=TARGET_CODES[code]))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("texts", nargs="+")
    parser.add_argument("--language", default="Kannada")
    args = parser.parse_args()
    try:
        print("\n".join(translate_texts(args.texts, args.language)))
    except Exception as exc:
        parser.error(f"translation failed: {exc}")


if __name__ == "__main__":
    main()
