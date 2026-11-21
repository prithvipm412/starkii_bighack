"""LanguageBarrierGuard: a 3-layer safety guard for Indian-language chatbots (mac4).

Layers (check() runs them in order and returns the first block):
  1. input  : detect language -> translate to English -> Llama Guard 3 1B on the user prompt.
              Same as baseline/run_baseline.py (baseline + baseline_translit), so p_unsafe matches
              results/mac4/llama-guard-3-1b_baseline*.csv; the English second view (below) can flip a 0.5-0.9 verdict.
  2. steer  : refusal-direction steering inside the chatbot model (pipeline/steer.py, steer_gated).
              It runs inside generation, not here; check() reports it as a pass-through layer.
  3. output : translate the reply if non-English -> Llama Guard on (prompt, reply), the same
              conversation format and >0.5 threshold as pipeline/score.py (the study's judge).

Models load lazily, once: NLLB-200-distilled-600M + Llama-Guard-3-1B, on MPS, HF_HUB_OFFLINE=1.
Verdicts never contain the input or reply text.

Kanglish handling (kanglish=..., or env GUARD_KANGLISH):
  "itrans"    (default) mac1's romanized-Indic detector + ITRANS -> Kannada, exactly as baseline_translit.
  "romanized" (optional, off by default) mac3's guard/romanized.py: broader informal-Kanglish detection
              and word-level phonetic transliteration. Not validated against the study CSVs.
Policy (policy=..., or env GUARD_POLICY): default off = Llama Guard's own category list.
  "tech" adds one sentence to S1 (technical computing language is not violence); baseline.run_baseline.POLICIES.
Second view (second_view=..., or env GUARD_SECOND_VIEW=1/0), English input only:
  p >= 0.9 -> block; 0.5 < p < 0.9 -> NLLB round trip en -> kn -> en, Llama Guard on that paraphrase,
  block only if it is also > 0.5; p <= 0.5 -> allow. Non-English input is unchanged.
Default threshold 0.5 = the study's judge (pipeline/score.py). See README for why 0.86 is not the default.
"""
import os
import re
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from pipeline.data import is_romanized_indic, script_lang  # noqa: E402  (mac1's detector)

KANNADA_RE = re.compile(r"[ಀ-೿]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")
THRESHOLD = 0.5
SECOND_VIEW_HIGH = 0.9
SECOND_VIEW_DEFAULT = "1"


def to_kannada_script(text: str) -> str:
    """ITRANS -> Kannada script: the reverse of data_tools.transliterate (same as baseline_translit)."""
    from indic_transliteration import sanscript
    return sanscript.transliterate(text, sanscript.ITRANS, sanscript.KANNADA)


def detect(text: str, kanglish: str = "itrans") -> str:
    """en | kn | kn_latn | kn_mix.
    Kannada script present: kn_mix if Latin words make up >= 15% of the words, else kn.
    No Indic script: kn_latn if mac1's romanized-Indic heuristic fires (Kanglish word list,
    Kannada suffixes, ITRANS capitals), else en."""
    text = text or ""
    if KANNADA_RE.search(text):
        words = text.split()
        latin = sum(1 for w in words if LATIN_WORD_RE.search(w) and not KANNADA_RE.search(w))
        return "kn_mix" if words and latin / len(words) >= 0.15 else "kn"
    if kanglish == "romanized":
        from guard.romanized import is_kanglish
        return "kn_latn" if is_kanglish(text) else "en"
    if is_romanized_indic(text):
        return "kn_latn"
    return "en"


class LanguageBarrierGuard:
    def __init__(self, device=None, threshold=THRESHOLD, kanglish=None, policy=None, second_view=None):
        self.device = device
        if second_view is None:
            second_view = os.environ.get("GUARD_SECOND_VIEW", SECOND_VIEW_DEFAULT) not in ("0", "", "false", "off")
        self.second_view = bool(second_view)
        self.policy = policy or os.environ.get("GUARD_POLICY") or None
        if self.policy == "default":
            self.policy = None
        if self.policy not in (None, "tech"):
            raise ValueError("policy must be None/'default' or 'tech'")
        self.threshold = THRESHOLD if threshold is None else float(threshold)
        self.kanglish = kanglish or os.environ.get("GUARD_KANGLISH", "itrans")
        if self.kanglish not in ("itrans", "romanized"):
            raise ValueError("kanglish must be 'itrans' or 'romanized'")
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
            self._guard = Guard(self._dev(), policy=self.policy)
        return self._guard

    def detect(self, text: str) -> str:
        return detect(text, self.kanglish)

    def to_english(self, text: str, detected: str) -> str:
        """Translation path per detected variant (baseline_translit routing for kn_latn)."""
        if detected == "en":
            return text
        if detected == "kn_latn":
            if self.kanglish == "romanized":
                from guard.romanized import to_kannada_script as romanized_to_kannada
                text = romanized_to_kannada(text)
            else:
                text = to_kannada_script(text)
        src = script_lang(text) or "kan_Knda"
        if src != "kan_Knda":  # other Indic scripts: NLLB takes the same FLORES-200 codes
            self.translator.tok.src_lang = src
        try:
            return self.translator(text)
        finally:
            self.translator.tok.src_lang = "kan_Knda"

    # ---- layers ----
    def input_check(self, text: str) -> dict:
        t0 = time.perf_counter()
        text = (text or "").strip()
        if not text:
            return {"blocked": False, "layer": "input", "p_unsafe": 0.0, "p_second_view": None,
                    "decided_by": "input", "detected": "en",
                    "latency_ms": 0, "note": "empty input"}
        detected = self.detect(text)
        english = self.to_english(text, detected)
        refused, p = self.guard(english)
        blocked, p2, decided = p > self.threshold, None, "input"
        if self.second_view and detected == "en" and self.threshold < p < SECOND_VIEW_HIGH:
            kn = self.translator.translate(text, src="eng_Latn", tgt="kan_Knda")
            _, p2 = self.guard(self.translator.translate(kn, src="kan_Knda", tgt="eng_Latn"))
            blocked, decided = p2 > self.threshold, "input+second_view"
        return {"blocked": blocked, "layer": "input", "p_unsafe": p, "p_second_view": p2,
                "decided_by": decided, "detected": detected,
                "kanglish_mode": self.kanglish, "policy": self.policy or "default",
                "latency_ms": round((time.perf_counter() - t0) * 1000)}

    def output_check(self, reply: str, prompt: str = "") -> dict:
        """Llama Guard on (prompt, reply) after translating non-English text, as in pipeline/score.py."""
        t0 = time.perf_counter()
        g = self.guard
        p_en = self.to_english(prompt, self.detect(prompt)) if prompt else ""
        r_det = self.detect(reply or "")
        r_en = self.to_english(reply, r_det) if reply else "(empty)"
        conv = [{"role": "user", "content": [{"type": "text", "text": p_en or "(no prompt given)"}]},
                {"role": "assistant", "content": [{"type": "text", "text": r_en}]}]
        ids = g.encode(conv)
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
                return {"verdict": "block", **o, "layers": layers}
        return {"verdict": "allow", "blocked": False, "layer": None, "detected": v["detected"],
                "p_unsafe": v["p_unsafe"], "p_second_view": v["p_second_view"], "decided_by": v["decided_by"],
                "latency_ms": sum(l.get("latency_ms", 0) for l in layers),
                "layers": layers}
