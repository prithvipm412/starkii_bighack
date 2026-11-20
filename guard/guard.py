"""LanguageBarrierGuard: a 3-layer safety guard for Indian-language chatbots (mac4).

Layers (check() runs them in order and returns the first block):
  1. input  : score the raw prompt and available Kannada-script and English views.
  2. steer  : refusal-direction steering inside the chatbot model (pipeline/steer.py, steer_gated).
              It runs inside generation, not here; check() reports it as a pass-through layer.
  3. output : translate the reply if non-English -> Llama Guard on (prompt, reply), the same
              conversation format and >0.5 threshold as pipeline/score.py (the study's judge).

Models load lazily, once: NLLB-200-distilled-600M + Llama-Guard-3-1B, on MPS, HF_HUB_OFFLINE=1.
Verdicts never contain the input or reply text.
"""
import json
import os
import re
import time

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from pipeline.data import ITRANS_RE, script_lang  # noqa: E402  (mac1's detector)

from guard.romanized import is_kanglish, is_kannada_word, keyword_view, normalized

KANNADA_RE = re.compile(r"[ಀ-೿]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]+")
THRESHOLD = 0.86
OUTPUT_THRESHOLD = 0.5
GEMMA_ID = "google/gemma-2-2b-it"
GLOSS_INSTRUCTION = "Translate this Kannada/Kanglish text to plain English. Output only the translation."
KANNADA_WORDS = {
    "hege": "ಹೇಗೆ", "hegey": "ಹೇಗೆ", "hegide": "ಹೇಗಿದೆ",
    "madu": "ಮಾಡು", "maadu": "ಮಾಡು", "madi": "ಮಾಡಿ", "maadi": "ಮಾಡಿ",
    "madodu": "ಮಾಡೋದು", "maadodu": "ಮಾಡೋದು",
    "maduvudu": "ಮಾಡುವುದು", "maaduvudu": "ಮಾಡುವುದು",
    "maduvudhu": "ಮಾಡುವುದು", "maaduvudhu": "ಮಾಡುವುದು",
    "beku": "ಬೇಕು", "beka": "ಬೇಕಾ", "enu": "ಏನು", "yenu": "ಏನು",
    "elli": "ಎಲ್ಲಿ", "yaake": "ಯಾಕೆ", "yake": "ಯಾಕೆ", "yaaru": "ಯಾರು",
    "yarannadaru": "ಯಾರನ್ನಾದರೂ", "obbarige": "ಒಬ್ಬರಿಗೆ",
    "koduvudu": "ಕೊಡುವುದು", "kodu": "ಕೊಡು", "kodi": "ಕೊಡಿ",
    "nanna": "ನನ್ನ", "nanage": "ನನಗೆ", "nange": "ನನಗೆ",
    "ninna": "ನಿನ್ನ", "nimma": "ನಿಮ್ಮ", "namma": "ನಮ್ಮ",
    "illa": "ಇಲ್ಲ", "ide": "ಇದೆ", "idu": "ಇದು", "adu": "ಅದು",
    "mattu": "ಮತ್ತು", "haagu": "ಹಾಗೂ", "swalpa": "ಸ್ವಲ್ಪ",
    "heli": "ಹೇಳಿ", "dayavittu": "ದಯವಿಟ್ಟು", "banni": "ಬನ್ನಿ",
    "anna": "ಅಣ್ಣ", "akka": "ಅಕ್ಕ", "hogu": "ಹೋಗು",
    "havaamaana": "ಹವಾಮಾನ", "chaha": "ಚಹಾ", "bengaluru": "ಬೆಂಗಳೂರು",
    "tumba": "ತುಂಬಾ", "alli": "ಅಲ್ಲಿ", "inda": "ಇಂದ", "yavudu": "ಯಾವುದು",
    "yaavudu": "ಯಾವುದು", "aadare": "ಆದರೆ", "bari": "ಬರಿ",
    "kole": "ಕೊಲೆ", "visha": "ವಿಷ",
}
# Keep canonical vowels and consonants for common words before falling back to ITRANS.
SCRIPT_WORDS = {normalized(word): value for word, value in KANNADA_WORDS.items()}
SCRIPT_WORDS.update({
    "ivattu": "ಇವತ್ತು", "hegide": "ಹೇಗಿದೆ", "beda": "ಬೇಡ", "gottu": "ಗೊತ್ತು",
    "nale": "ನಾಳೆ", "ondu": "ಒಂದು", "eradu": "ಎರಡು", "mane": "ಮನೆ",
    "ota": "ಊಟ", "kadiyodu": "ಕದಿಯೋದು", "tegeyodu": "ತೆಗೆಯೋದು",
})
LOOSE_ITRANS = re.compile(r"aa|ee|oo|uu|dh")
ITRANS_SPELLING = {"aa": "A", "ee": "I", "oo": "U", "uu": "U", "dh": "d"}


def to_kannada_script(text: str) -> str:
    from indic_transliteration import sanscript

    def convert(match):
        word = match.group()
        canonical = SCRIPT_WORDS.get(normalized(word))
        if canonical is not None:
            return canonical
        if ITRANS_RE.fullmatch(word):
            return sanscript.transliterate(word, sanscript.ITRANS, sanscript.KANNADA)
        if is_kannada_word(word):
            phonetic = LOOSE_ITRANS.sub(lambda m: ITRANS_SPELLING[m.group()], word.lower())
            return sanscript.transliterate(phonetic, sanscript.ITRANS, sanscript.KANNADA)
        return word

    return LATIN_WORD_RE.sub(convert, text)


def detect(text: str) -> str:
    text = text or ""
    if KANNADA_RE.search(text):
        return "kn_mix" if LATIN_WORD_RE.search(text) else "kn"
    return "kn_latn" if is_kanglish(text) else "en"


class LanguageBarrierGuard:
    def __init__(self, device=None, threshold=None):
        self.device = device
        self.threshold = THRESHOLD if threshold is None else threshold
        self.output_threshold = OUTPUT_THRESHOLD if threshold is None else threshold
        self._translator = None
        self._guard = None
        self._gloss_model = None
        self._gloss_tokenizer = None

    # ---- lazy model loading (once) ----
    def _dev(self):
        if self.device is None:
            import torch
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        return self.device

    @property
    def translator(self):
        if self._translator is None:
            from baseline.run_baseline import Translator
            translator = Translator(self._dev())
            if self._dev() == "mps":
                translator.model.to(dtype=translator.torch.bfloat16)
            self._translator = translator
        return self._translator

    @property
    def guard(self):
        if self._guard is None:
            import torch
            from baseline.run_baseline import Guard
            torch.manual_seed(0)
            self._guard = Guard(self._dev())
        return self._guard

    detect = staticmethod(detect)

    def to_english(self, text: str, detected: str) -> str:
        """Translation path per detected variant (baseline_translit routing for kn_latn)."""
        if detected == "en":
            return text
        if detected == "kn_latn":
            text = to_kannada_script(text)
        src = script_lang(text) or "kan_Knda"
        if src != "kan_Knda":  # other Indic scripts: NLLB takes the same FLORES-200 codes
            self.translator.tok.src_lang = src
        try:
            return self.translator(text)
        finally:
            self.translator.tok.src_lang = "kan_Knda"

    def preload(self):
        from baseline.run_baseline import resolve
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        _ = self.guard, self.translator
        if self._gloss_model is None:
            snapshot = resolve(GEMMA_ID)
            tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
            dtype = torch.bfloat16 if self._dev() != "cpu" else torch.float32
            model = AutoModelForCausalLM.from_pretrained(
                snapshot, local_files_only=True, dtype=dtype, attn_implementation="eager"
            ).to(self._dev()).eval()
            self._gloss_tokenizer, self._gloss_model = tokenizer, model

    def gloss(self, text: str) -> str:
        import torch

        self.preload()
        tok = self._gloss_tokenizer
        message = GLOSS_INSTRUCTION + "\n\nInput: " + json.dumps(text, ensure_ascii=False)
        inputs = tok.apply_chat_template(
            [{"role": "user", "content": message}], add_generation_prompt=True,
            tokenize=True, return_dict=True, return_tensors="pt",
        ).to(self._dev())
        with torch.inference_mode():
            output = self._gloss_model.generate(**inputs, max_new_tokens=64, do_sample=False)
        return tok.decode(output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

    def input_views(self, text: str, detected: str) -> dict:
        views = {"raw": text}
        if detected == "en":
            return views
        if detected == "kn_latn":
            views["transliterated"] = to_kannada_script(text)
        source = views.get("transliterated", text)
        views["nllb"] = self.to_english(source, "kn")
        views["llm_gloss"] = self.gloss(text)
        if detected in ("kn_latn", "kn_mix"):
            views["keyword_preserving"] = keyword_view(text)
        return {name: view for name, view in views.items() if view.strip()}

    def score_input_views(self, views: dict) -> dict:
        g = self.guard
        tok = g.tok
        tokens = [g.safe_id, g.unsafe_id]
        if [tok.decode(token) for token in tokens] != ["safe", "unsafe"]:
            raise RuntimeError("Unexpected Llama Guard verdict tokens")
        # The official template ends at the assistant header. Its first generated
        # token is normally two line breaks. Prefill them to score the first verdict position.
        separator = tok.encode("\n\n", add_special_tokens=False)
        unique = list(dict.fromkeys(views.values()))
        sequences = []
        for view in unique:
            turn = [{"role": "user", "content": [{"type": "text", "text": view}]}]
            sequences.append(tok.apply_chat_template(turn) + separator)
        width = max(map(len, sequences))
        ids = g.torch.tensor(
            [[tok.eos_token_id] * (width - len(seq)) + seq for seq in sequences], device=g.device
        )
        mask = g.torch.tensor(
            [[0] * (width - len(seq)) + [1] * len(seq) for seq in sequences], device=g.device
        )
        positions = (mask.cumsum(dim=1) - 1).clamp_min(0)
        with g.torch.inference_mode():
            logits = g.model(
                input_ids=ids, attention_mask=mask, position_ids=positions, use_cache=False,
                logits_to_keep=1,
            ).logits[:, -1, tokens].float()
            probabilities = g.torch.softmax(logits, dim=-1)[:, 1].tolist()
        if not all(0 <= probability <= 1 for probability in probabilities):
            raise RuntimeError("Llama Guard returned an invalid probability")
        scores = dict(zip(unique, probabilities))
        return {name: scores[view] for name, view in views.items()}

    def input_check(self, text: str) -> dict:
        t0 = time.perf_counter()
        text = (text or "").strip()
        detected = detect(text)
        scores = self.score_input_views(self.input_views(text, detected)) if text else {}
        p = max(scores.values(), default=0.0)
        threshold = self.threshold
        return {
            "blocked": p > threshold, "layer": "input", "p_unsafe": round(p, 4),
            "detected": detected, "threshold": threshold,
            "views": [{"view": name, "p_unsafe": round(score, 4)} for name, score in scores.items()],
            "scores": {"raw": round(scores.get("raw", 0.0), 4),
                       "transliterated": round(scores["transliterated"], 4) if "transliterated" in scores else None,
                       "english": round(scores["nllb"], 4) if "nllb" in scores else
                                  round(scores.get("raw", 0.0), 4) if detected == "en" else None},
            "latency_ms": round((time.perf_counter() - t0) * 1000),
        }

    def output_check(self, reply: str, prompt: str = "") -> dict:
        """Llama Guard on (prompt, reply) after translating non-English text, as in pipeline/score.py."""
        t0 = time.perf_counter()
        g = self.guard
        p_en = self.to_english(prompt, detect(prompt)) if prompt else ""
        r_det = detect(reply or "")
        r_en = self.to_english(reply, r_det) if reply else "(empty)"
        conv = [{"role": "user", "content": [{"type": "text", "text": p_en or "(no prompt given)"}]},
                {"role": "assistant", "content": [{"type": "text", "text": r_en}]}]
        ids = g.tok.apply_chat_template(conv, return_tensors="pt").to(g.device)
        with g.torch.inference_mode():
            out = g.model.generate(ids, max_new_tokens=6, do_sample=False, pad_token_id=0,
                                   output_scores=True, return_dict_in_generate=True)
        new = out.sequences[0, ids.shape[1]:].tolist()
        p = float("nan")
        for step, tid in enumerate(new):
            if tid in (g.safe_id, g.unsafe_id):
                pair = out.scores[step][0, [g.safe_id, g.unsafe_id]].float()
                p = float(g.torch.softmax(pair, dim=0)[1])
                break
        if p != p:  # no verdict token: fall back to the decoded verdict
            p = 1.0 if g.tok.decode(new, skip_special_tokens=True).strip().lower().startswith("unsafe") else 0.0
        return {"blocked": p > self.output_threshold, "layer": "output", "p_unsafe": round(p, 4),
                "detected": r_det, "latency_ms": round((time.perf_counter() - t0) * 1000)}

    def check(self, text: str, reply: str = None) -> dict:
        """Input layer, then (if a reply is given) output layer. First block wins, else allow."""
        layers = []
        v = self.input_check(text)
        layers.append(v)
        if v["blocked"]:
            return {"verdict": "block", **v, "layers": layers}
        layers.append({"layer": "steer", "blocked": False,
                       "note": "steer_gated runs inside the chatbot model (pipeline/steer.py)"})
        if reply is not None:
            o = self.output_check(reply, prompt=text)
            layers.append(o)
            if o["blocked"]:
                return {"verdict": "block", **o, "scores": v["scores"], "views": v["views"], "layers": layers}
        return {"verdict": "allow", "blocked": False, "layer": None, "detected": v["detected"],
                "p_unsafe": v["p_unsafe"], "scores": v["scores"], "views": v["views"], "threshold": v.get("threshold", self.threshold),
                "latency_ms": sum(l.get("latency_ms", 0) for l in layers),
                "layers": layers}
