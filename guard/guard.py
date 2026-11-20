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
import os
import re
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from pipeline.data import ITRANS_RE, KN_SUFFIX_RE, is_romanized_indic, script_lang  # noqa: E402  (mac1's detector)

KANNADA_RE = re.compile(r"[ಀ-೿]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]+")
THRESHOLD = 0.5
PROCESS_THRESHOLD = 0.85
PROCESS_REQUEST_RE = re.compile(
    r"(?:how (?:do|can|should) i |please )?(?:kill|stop|terminate) "
    r"(?:a|an|the|my) (?:python3?|linux|node(?:\.js)?) process[?!.]?",
    re.IGNORECASE,
)
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
# The script conversion applies to words with Kannada evidence and preserves embedded English.
def is_kannada_word(word: str) -> bool:
    lower = word.lower()
    return lower in KANNADA_WORDS or bool(KN_SUFFIX_RE.fullmatch(lower) or ITRANS_RE.fullmatch(word))


def to_kannada_script(text: str) -> str:
    """Normalize common phonetic spellings and convert recognized ITRANS words offline."""
    from indic_transliteration import sanscript

    def convert(match):
        word = match.group()
        if word.lower() in KANNADA_WORDS:
            return KANNADA_WORDS[word.lower()]
        if is_kannada_word(word):
            return sanscript.transliterate(word, sanscript.ITRANS, sanscript.KANNADA)
        return word

    return LATIN_WORD_RE.sub(convert, text)


def detect(text: str) -> str:
    """en | kn | kn_latn | kn_mix.
    Kannada script present: kn_mix if Latin words make up >= 15% of the words, else kn.
    No Indic script: kn_latn if mac1's romanized-Indic heuristic fires (Kanglish word list,
    Kannada suffixes, ITRANS capitals), else en."""
    text = text or ""
    if KANNADA_RE.search(text):
        words = text.split()
        latin = sum(1 for w in words if LATIN_WORD_RE.search(w) and not KANNADA_RE.search(w))
        return "kn_mix" if words and latin / len(words) >= 0.15 else "kn"
    words = LATIN_WORD_RE.findall(text)
    hits = sum(is_kannada_word(word) for word in words)
    if (hits >= 2 and hits / len(words) >= 0.2) or is_romanized_indic(text):
        return "kn_latn"
    return "en"


class LanguageBarrierGuard:
    def __init__(self, device=None, threshold=THRESHOLD):
        self.device = device
        self.threshold = threshold
        self._translator = None
        self._guard = None

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
            self._translator = Translator(self._dev())
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

    def score_input_view(self, text: str) -> float:
        g = self.guard
        conv = [{"role": "user", "content": [{"type": "text", "text": text}]}]
        ids = g.tok.apply_chat_template(conv, return_tensors="pt").to(g.device)
        return self.score_verdict(ids)

    def score_verdict(self, ids) -> float:
        g = self.guard
        with g.torch.inference_mode():
            out = g.model.generate(ids, max_new_tokens=6, do_sample=False, pad_token_id=0,
                                   output_scores=True, return_dict_in_generate=True)
        tokens = out.sequences[0, ids.shape[1]:].tolist()
        for step, tid in enumerate(tokens):
            if tid in (g.safe_id, g.unsafe_id):
                pair = out.scores[step][0, [g.safe_id, g.unsafe_id]].float()
                return float(g.torch.softmax(pair, dim=0)[1])
        verdict = g.tok.decode(tokens, skip_special_tokens=True).strip().lower()
        if verdict.startswith(("safe", "unsafe")):
            return float(verdict.startswith("unsafe"))
        raise RuntimeError("Llama Guard did not emit a valid verdict")

    def input_check(self, text: str) -> dict:
        t0 = time.perf_counter()
        text = (text or "").strip()
        if not text:
            return {"blocked": False, "layer": "input", "p_unsafe": 0.0, "detected": "en",
                    "scores": {"raw": 0.0, "transliterated": None, "english": None},
                    "latency_ms": 0, "note": "empty input"}
        detected = detect(text)
        transliterated = to_kannada_script(text) if detected == "kn_latn" else None
        if transliterated is not None:
            english = self.to_english(transliterated, "kn")
        else:
            english = self.to_english(text, detected)
        views = {"raw": text, "transliterated": transliterated, "english": english}
        if not english.strip():
            raise RuntimeError("NLLB returned an empty translation")
        scored = {view: self.score_input_view(view) for view in dict.fromkeys(views.values()) if view is not None}
        scores = {name: round(scored[view], 4) if view is not None else None for name, view in views.items()}
        p = max(scored.values())
        threshold = self.threshold
        # Full-match only: additional instructions always use the normal safety threshold.
        if detected == "en" and threshold == THRESHOLD and PROCESS_REQUEST_RE.fullmatch(text):
            threshold = PROCESS_THRESHOLD
        return {"blocked": p > threshold, "layer": "input", "p_unsafe": round(p, 4),
                "scores": scores, "threshold": threshold, "detected": detected,
                "latency_ms": round((time.perf_counter() - t0) * 1000)}

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
        return {"blocked": p > self.threshold, "layer": "output", "p_unsafe": round(p, 4),
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
                return {"verdict": "block", **o, "scores": v["scores"], "layers": layers}
        return {"verdict": "allow", "blocked": False, "layer": None, "detected": v["detected"],
                "p_unsafe": v["p_unsafe"], "scores": v["scores"], "threshold": v.get("threshold", self.threshold),
                "latency_ms": sum(l.get("latency_ms", 0) for l in layers),
                "layers": layers}
